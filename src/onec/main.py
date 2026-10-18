import logging
import re
import sys
import time
from functools import wraps

from mcp.server.fastmcp import FastMCP

from . import registers, transport

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("onec")

app = FastMCP("onec")


def quiet(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        start = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            log.info("%s %.3fs", fn.__name__, time.monotonic() - start)
    return wrap


def _entity(kind, name):
    root = "Catalog" if kind == "catalog" else "Document"
    return f"{root}_{name}"


@app.tool(description="List catalogs and documents available through OData")
@quiet
def onec_list_entities(kind: str) -> list[str]:
    if kind not in ("catalog", "document"):
        raise ValueError("kind is catalog or document")
    root = "Catalog" if kind == "catalog" else "Document"
    meta = transport.get("$metadata")
    names = re.findall(rf'EntitySet Name="({root}_[^"]+)"', meta)
    return sorted(set(names))


@app.tool(description="Search catalog items by text")
@quiet
def onec_search_catalog(entity: str, text: str, offset: int = 0, limit: int = 50) -> dict:
    f = f"Description ct '{text}'"
    rows = transport.get(entity, {"$filter": f, "$top": limit, "$skip": offset}, entity_encoded=True)
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Read one catalog item by Ref_Key")
@quiet
def onec_get_catalog_item(entity: str, ref: str) -> dict:
    rows = transport.get(entity, {"$filter": f"Ref_Key eq guid'{ref}'"}, entity_encoded=True)
    return rows[0] if rows else {}


@app.tool(description="Search documents by period and text")
@quiet
def onec_search_documents(entity: str, since: str, until: str, text: str = "", offset: int = 0, limit: int = 50) -> dict:
    f = f"Date_Time ge datetime'{since}' and Date_Time le datetime'{until}'"
    if text:
        f += f" and Description ct '{text}'"
    rows = transport.get(entity, {"$filter": f, "$orderby": "Date_Time desc", "$top": limit, "$skip": offset}, entity_encoded=True)
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Read one document with tabular sections")
@quiet
def onec_get_document(entity: str, ref: str) -> dict:
    head = transport.get(entity, {"$filter": f"Ref_Key eq guid'{ref}'"}, entity_encoded=True)
    return head[0] if head else {}


@app.tool(description="Accumulation or accounting register balances via OData virtual table")
@quiet
def onec_balances(entity: str, since: str, until: str, extra_filter: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.balances(entity, since, until, offset, limit, extra_filter)


@app.tool(description="Accumulation or accounting register turnovers via OData virtual table")
@quiet
def onec_turnovers(entity: str, since: str, until: str, extra_filter: str = "", offset: int = 0, limit: int = 100) -> dict:
    return registers.turnovers(entity, since, until, offset, limit, extra_filter)


@app.tool(description="Register records for a period, plain table, works everywhere")
@quiet
def onec_postings(entity: str, since: str, until: str, offset: int = 0, limit: int = 100) -> dict:
    rows = transport.get(entity,
                         {"$filter": f"Period ge datetime'{since}' and Period le datetime'{until}'", "$top": limit, "$skip": offset},
                         entity_encoded=True)
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Run a published 1C report service, GET only, white listed in config.toml")
@quiet
def onec_run_report(name: str, params: dict | None = None) -> dict:
    return transport.get_service(name, params or {})


def run():
    app.run(transport="stdio")
