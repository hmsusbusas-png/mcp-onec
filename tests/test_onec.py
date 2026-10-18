import asyncio

import pytest

from onec import main, transport
from onec.main import app

ref = "00000000-0000-0000-0000-000000000001"


def test_every_tool_is_registered_and_read_only():
    tools = asyncio.run(app.list_tools())
    assert len(tools) == 13
    assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)


@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE"])
def test_write_methods_never_leave_the_process(seen, verb):
    with pytest.raises(PermissionError):
        transport.gate().request(verb, transport.odata_root + "/Catalog_Номенклатура")
    assert seen == []


def test_metadata_tools(seen):
    assert main.onec_entities() == {"total": 6, "by_kind": {"catalog": 1, "document": 1, "information": 1, "accumulation": 1}}
    assert main.onec_entities("information")["names"] == ["InformationRegister_Цены"]
    fields = main.onec_fields("Catalog_Номенклатура")
    assert [f["name"] for f in fields["fields"]] == ["Ref_Key", "Description"]
    assert fields["tabular_sections"] == [{"name": "Штрихкоды", "columns": ["Штрихкод"]}]
    assert fields["links"] == ["ЕдиницаИзмерения"]
    with pytest.raises(LookupError, match="similar: Catalog_Номенклатура"):
        main.onec_fields("Номенклатура")


def test_query_encoding_and_paging(seen):
    page = main.onec_query("Catalog_Номенклатура", filter="Description eq 'Болт''s'", select=["Ref_Key", "Description"],
                           orderby="Description", expand=["ЕдиницаИзмерения"], offset=3, limit=3)
    assert page["total"] == 7 and page["next_offset"] == 6 and len(page["items"]) == 3
    method, path, auth = seen[-1]
    assert auth.startswith("Basic ")
    assert path == ("/base/odata/standard.odata/Catalog_Номенклатура?$filter=Description eq 'Болт''s'"
                    "&$select=Ref_Key,Description&$orderby=Description&$expand=ЕдиницаИзмерения"
                    "&$top=3&$skip=3&$inlinecount=allpages&$format=json")
    last = main.onec_query("Catalog_Номенклатура", offset=6, limit=3)
    assert last["next_offset"] is None
    assert main.onec_count("Catalog_Номенклатура", "DeletionMark eq false") == 7


def test_search_and_get(seen):
    main.onec_search_catalog("Catalog_Номенклатура", "o'k")
    assert "substringof('o''k', Description) and DeletionMark eq false" in seen[-1][1]
    assert main.onec_get("Document_Реализация", ref)["Description"] == "Болт 1"
    assert seen[-1][1].startswith(f"/base/odata/standard.odata/Document_Реализация(guid'{ref}')")
    main.onec_search_documents("Document_Реализация", "2024-01-01", "2024-01-31", number="00", posted_only=True)
    assert ("Date ge datetime'2024-01-01T00:00:00' and Date le datetime'2024-01-31T23:59:59' "
            "and substringof('00', Number) and Posted eq true") in seen[-1][1]


def test_register_virtual_tables(seen):
    main.onec_balances("AccumulationRegister_Остатки", "2024-02-01", "Склад_Key eq guid'" + ref + "'")
    assert f"/AccumulationRegister_Остатки/Balance(Period=datetime'2024-02-01T00:00:00',Condition='Склад_Key eq guid''{ref}''')" in seen[-1][1]
    main.onec_turnovers("AccumulationRegister_Остатки", "2024-01-01", "2024-01-31")
    assert "/Turnovers(StartPeriod=datetime'2024-01-01T00:00:00',EndPeriod=datetime'2024-01-31T23:59:59')" in seen[-1][1]
    main.onec_balance_turnovers("AccumulationRegister_Остатки", "2024-01-01", "2024-01-31")
    assert "/BalanceAndTurnovers(" in seen[-1][1]
    main.onec_slice("InformationRegister_Цены", "2024-02-01")
    assert "/InformationRegister_Цены/SliceLast(Period=datetime'2024-02-01T23:59:59')" in seen[-1][1]
    main.onec_postings("AccumulationRegister_Остатки", "2024-01-01", "2024-01-31", filter="Active eq true")
    assert "/AccumulationRegister_Остатки_RecordType?$filter=Period ge" in seen[-1][1] and "and (Active eq true)" in seen[-1][1]


def test_report_whitelist(seen):
    assert main.onec_run_report("sales/summary", {"Период": "2024"}) == {"report": "ok"}
    assert seen[-1][1] == "/base/hs/sales/summary?Период=2024"
    with pytest.raises(PermissionError):
        main.onec_run_report("admin/delete")


def test_validation(seen):
    with pytest.raises(ValueError):
        main.onec_get("Catalog_Номенклатура", "1' or 1 eq 1")
    with pytest.raises(ValueError):
        main.onec_query("Catalog_X/../../hs/evil")
    with pytest.raises(ValueError):
        main.onec_query("Catalog_Номенклатура", select=["Ref_Key,Description;drop"])
    with pytest.raises(ValueError):
        main.onec_search_documents("Document_Реализация", "yesterday", "2024-01-31")
    with pytest.raises(ValueError):
        main.onec_balances("Catalog_Номенклатура", "2024-01-01")
    with pytest.raises(ValueError):
        main.onec_slice("AccumulationRegister_Остатки", "2024-01-01")
    with pytest.raises(LookupError):
        main.onec_get("Document_Missing", ref)
    assert all(method == "GET" for method, _, _ in seen)
