import logging
import re
import sys
import time
from functools import wraps

from mcp.server.fastmcp import FastMCP

from . import registers, transport

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("onec")

app = FastMCP("onec")


def timed(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        start = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            log.info("%s %.3fs", fn.__name__, time.monotonic() - start)
    return wrap


def period_filter(field, since, until):
    return f"{field} ge datetime'{transport.moment(since)}' and {field} le datetime'{transport.moment(until, day_end=True)}'"


@app.tool(description="List published object names of one kind: catalog, document, accumulation, accounting, information")
@timed
def onec_list_entities(kind: str) -> list[str]:
    prefixes = {
        "catalog": "Catalog_",
        "document": "Document_",
        "accumulation": "AccumulationRegister_",
        "accounting": "AccountingRegister_",
        "information": "InformationRegister_",
    }
    if kind not in prefixes:
        raise ValueError(f"kind is one of {', '.join(prefixes)}")
    names = re.findall(rf'EntitySet Name="({prefixes[kind]}[^"]+)"', transport.metadata())
    return sorted(n for n in set(names) if "_RowType" not in n and "_RecordType" not in n)


@app.tool(description="Search catalog items whose Description contains text, e.g. entity Catalog_Номенклатура")
@timed
def onec_search_catalog(entity: str, text: str = "", offset: int = 0, limit: int = 50) -> dict:
    query = {"$filter": f"substringof({transport.literal(text)}, Description)"} if text else {}
    return transport.rows(transport.segment(entity), query, offset, limit)


@app.tool(description="Read one catalog item by Ref_Key guid")
@timed
def onec_get_catalog_item(entity: str, ref: str) -> dict:
    return transport.one(entity, ref)


@app.tool(description="Documents for a period, dates as YYYY-MM-DD, optional number substring")
@timed
def onec_search_documents(entity: str, since: str, until: str, number: str = "", offset: int = 0, limit: int = 50) -> dict:
    expr = period_filter("Date", since, until)
    if number:
        expr += f" and substringof({transport.literal(number)}, Number)"
    return transport.rows(transport.segment(entity), {"$filter": expr, "$orderby": "Date desc"}, offset, limit)


@app.tool(description="Read one document by Ref_Key guid, tabular sections included")
@timed
def onec_get_document(entity: str, ref: str) -> dict:
    return transport.one(entity, ref)


@app.tool(description="Register balances at a moment via the Balance virtual table, condition is an OData filter")
@timed
def onec_balances(entity: str, at: str, condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.balances(entity, at, condition, offset, limit)


@app.tool(description="Register turnovers for a period via the Turnovers virtual table, condition is an OData filter")
@timed
def onec_turnovers(entity: str, since: str, until: str, condition: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.turnovers(entity, since, until, condition, offset, limit)


@app.tool(description="Raw register records for a period, AccumulationRegister_X is read through X_RecordType")
@timed
def onec_postings(entity: str, since: str, until: str, offset: int = 0, limit: int = 100) -> dict:
    transport.object_name(entity)
    if entity.startswith(registers.kinds) and not entity.endswith("_RecordType"):
        entity += "_RecordType"
    query = {"$filter": period_filter("Period", since, until), "$orderby": "Period"}
    return transport.rows(transport.segment(entity), query, offset, limit)


@app.tool(description="Call a published 1C http service by GET, only names listed in allowed_services")
@timed
def onec_run_report(name: str, params: dict[str, str] | None = None) -> dict | list:
    return transport.service(name, params or {})


def run():
    app.run(transport="stdio")
