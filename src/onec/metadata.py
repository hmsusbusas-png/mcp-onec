import time
import xml.etree.ElementTree as ET

from . import transport

kinds = {
    "catalog": "Catalog_",
    "document": "Document_",
    "journal": "DocumentJournal_",
    "constant": "Constant_",
    "enum": "Enum_",
    "exchange_plan": "ExchangePlan_",
    "chart_of_accounts": "ChartOfAccounts_",
    "chart_of_characteristic_types": "ChartOfCharacteristicTypes_",
    "chart_of_calculation_types": "ChartOfCalculationTypes_",
    "information": "InformationRegister_",
    "accumulation": "AccumulationRegister_",
    "accounting": "AccountingRegister_",
    "calculation": "CalculationRegister_",
    "business_process": "BusinessProcess_",
    "task": "Task_",
}
parsed = {"at": 0.0, "types": {}, "sets": []}
service_tails = ("_RowType", "_RecordType", "_SliceLast", "_SliceFirst", "_Balance", "_Turnovers", "_BalanceAndTurnovers")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def model():
    if time.monotonic() - parsed["at"] < 600 and parsed["sets"]:
        return parsed
    root = ET.fromstring(transport.metadata())
    types, sets = {}, []
    for node in root.iter():
        name = local(node.tag)
        if name in ("EntityType", "ComplexType"):
            fields, links = [], []
            for child in node:
                kind = local(child.tag)
                if kind == "Property":
                    fields.append({"name": child.get("Name"), "type": child.get("Type"), "nullable": child.get("Nullable") != "false"})
                elif kind == "NavigationProperty":
                    links.append(child.get("Name"))
            types[node.get("Name")] = {"fields": fields, "links": links}
        elif name == "EntitySet":
            sets.append(node.get("Name"))
    parsed.update(at=time.monotonic(), types=types, sets=sorted(set(sets)))
    return parsed


def entity_names(kind):
    sets = model()["sets"]
    if not kind:
        counts = {k: sum(1 for s in sets if s.startswith(p) and not s.endswith(service_tails)) for k, p in kinds.items()}
        return {"total": len(sets), "by_kind": {k: v for k, v in counts.items() if v}}
    if kind not in kinds:
        raise ValueError(f"kind is one of {', '.join(kinds)}")
    prefix = kinds[kind]
    return {"kind": kind, "names": [s for s in sets if s.startswith(prefix) and "_RowType" not in s and not s.endswith(service_tails)]}


def fields(entity):
    transport.object_name(entity)
    types = model()["types"]
    if entity not in types:
        close = [t for t in types if entity.lower() in t.lower()][:10]
        raise LookupError(f"{entity} is not in $metadata" + (f", similar: {', '.join(close)}" if close else ""))
    info = types[entity]
    tables = []
    for f in info["fields"]:
        kind = f["type"] or ""
        if kind.startswith("Collection("):
            row_type = kind[len("Collection("):-1].split(".")[-1]
            tables.append({"name": f["name"], "columns": [c["name"] for c in types.get(row_type, {}).get("fields", [])]})
    plain = [f for f in info["fields"] if not (f["type"] or "").startswith("Collection(")]
    return {
        "entity": entity,
        "fields": [{"name": f["name"], "type": (f["type"] or "").replace("Edm.", "")} for f in plain],
        "tabular_sections": tables,
        "links": info["links"],
        "virtual_tables": [s[len(entity) + 1:] for s in model()["sets"] if s.startswith(entity + "_") and s != entity],
    }
