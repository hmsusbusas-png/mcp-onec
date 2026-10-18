import logging
import sys
import time
from functools import wraps

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import metadata, registers, transport

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("onec")

app = FastMCP("onec", instructions=(
    "Read only access to a 1C:Enterprise infobase through the standard OData interface. Nothing can be written. "
    "Start with onec_entities to see what is published, then onec_fields for the field names of an object, "
    "then onec_query or the specialised tools. Object names look like Catalog_Номенклатура, Document_РеализацияТоваровУслуг, "
    "AccumulationRegister_ТоварыНаСкладах. References are Ref_Key guids, related objects end with _Key. "
    "Dates are YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS. Results are paged with offset and limit, follow next_offset."
))
read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def tool(description):
    def register(fn):
        @wraps(fn)
        def timed(*args, **kwargs):
            start = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                log.info("%s %.3fs", fn.__name__, time.monotonic() - start)
        app.tool(description=description, annotations=read_only)(timed)
        return fn
    return register


def period_filter(field, since, until):
    return f"{field} ge datetime'{transport.moment(since)}' and {field} le datetime'{transport.moment(until, day_end=True)}'"


@tool(f"Published objects. Without kind returns counts per kind, with kind lists names. kind: {', '.join(metadata.kinds)}")
def onec_entities(kind: str = "") -> dict:
    return metadata.entity_names(kind)


@tool("Fields with types, tabular sections with their columns, and virtual tables of one object, read from $metadata")
def onec_fields(entity: str) -> dict:
    return metadata.fields(entity)


@tool("Generic OData read: filter like \"Description eq 'Болт' and DeletionMark eq false\", select fields, orderby, expand related _Key objects")
def onec_query(entity: str, filter: str = "", select: list[str] | None = None, orderby: str = "", expand: list[str] | None = None,
               offset: int = 0, limit: int = 100) -> dict:
    query = {}
    if filter:
        query["$filter"] = filter
    if select:
        query["$select"] = ",".join(transport.object_name(f) for f in select)
    if orderby:
        query["$orderby"] = orderby
    if expand:
        query["$expand"] = ",".join(transport.object_name(f) for f in expand)
    return transport.rows(transport.segment(entity), query, offset, limit)


@tool("Number of records of an object, optionally matching an OData filter")
def onec_count(entity: str, filter: str = "") -> int:
    return transport.count(transport.segment(entity), {"$filter": filter} if filter else {})


@tool("Search catalog items whose Description contains text, skips items marked for deletion unless with_deleted")
def onec_search_catalog(entity: str, text: str = "", with_deleted: bool = False, offset: int = 0, limit: int = 50) -> dict:
    parts = [f"substringof({transport.literal(text)}, Description)"] if text else []
    if not with_deleted:
        parts.append("DeletionMark eq false")
    query = {"$filter": " and ".join(parts)} if parts else {}
    return transport.rows(transport.segment(entity), query, offset, limit)


@tool("Read one object of any kind (catalog item, document, chart of accounts...) by Ref_Key guid, tabular sections included")
def onec_get(entity: str, ref: str) -> dict:
    return transport.one(entity, ref)


@tool("Documents for a period, newest first. number is a substring of Number, posted_only skips unposted documents")
def onec_search_documents(entity: str, since: str, until: str, number: str = "", posted_only: bool = False,
                          offset: int = 0, limit: int = 50) -> dict:
    expr = period_filter("Date", since, until)
    if number:
        expr += f" and substringof({transport.literal(number)}, Number)"
    if posted_only:
        expr += " and Posted eq true"
    return transport.rows(transport.segment(entity), {"$filter": expr, "$orderby": "Date desc"}, offset, limit)


@tool("Accumulation or accounting register balances at a moment, Balance virtual table. condition is an OData filter on dimensions")
def onec_balances(entity: str, at: str, condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.balances(entity, at, condition, offset, limit)


@tool("Accumulation or accounting register turnovers for a period, Turnovers virtual table")
def onec_turnovers(entity: str, since: str, until: str, condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.turnovers(entity, since, until, condition, offset, limit)


@tool("Opening balance, turnovers and closing balance for a period, BalanceAndTurnovers virtual table")
def onec_balance_turnovers(entity: str, since: str, until: str, condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.balance_turnovers(entity, since, until, condition, offset, limit)


@tool("Information register slice: edge last gives the latest values at a moment (prices, rates), first gives the earliest after it")
def onec_slice(entity: str, at: str, edge: str = "last", condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.slice_of(entity, edge, at, condition, offset, limit)


@tool("Raw register records for a period. AccumulationRegister_X and AccountingRegister_X are read through X_RecordType")
def onec_postings(entity: str, since: str, until: str, filter: str = "", offset: int = 0, limit: int = 100) -> dict:
    transport.object_name(entity)
    if entity.startswith(registers.totals_kinds) and not entity.endswith("_RecordType"):
        entity += "_RecordType"
    expr = period_filter("Period", since, until) + (f" and ({filter})" if filter else "")
    return transport.rows(transport.segment(entity), {"$filter": expr, "$orderby": "Period"}, offset, limit)


@tool("Call a published 1C http service by GET, only names listed in allowed_services in config.toml")
def onec_run_report(name: str, params: dict[str, str] | None = None) -> dict | list:
    return transport.service(name, params or {})


def run():
    app.run(transport="stdio")
