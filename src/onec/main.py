import json
import logging
import re
import sys
import time
from functools import wraps

from mcp.server.fastmcp import FastMCP

from . import transport

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


def entities(kind, ref=False):
    # kind: Catalog or Document; ref narrows to reference data
    rows = transport.get(f"{kind}?$select=Ref_Key,Description,Code" if ref else f"{kind}?$select=Ref_Key,Description,Posted,Date_Time")
    return rows


@app.tool(description="List catalogs and documents available through OData")
@quiet
def onec_list_entities(kind: str) -> list[str]:
    if kind not in ("catalog", "document"):
        raise ValueError("kind is catalog or document")
    root = "Catalog" if kind == "catalog" else "Document"
    meta = transport.get("$metadata")
    names = re.findall(rf'EntitySet Name="({root}_[A-Za-z0-9_]+)"', meta)
    return sorted(set(names))


@app.tool(description="Search catalog items by text")
@quiet
def onec_search_catalog(entity: str, text: str, offset: int = 0, limit: int = 50) -> dict:
    f = f"Description ct '{text}'"
    rows = transport.get(entity, {"$filter": f, "$top": limit, "$skip": offset})
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Read one catalog item by Ref_Key")
@quiet
def onec_get_catalog_item(entity: str, ref: str) -> dict:
    rows = transport.get(entity, {"$filter": f"Ref_Key eq guid'{ref}'"})
    return rows[0] if rows else {}


@app.tool(description="Search documents by period and text")
@quiet
def onec_search_documents(entity: str, since: str, until: str, text: str = "", offset: int = 0, limit: int = 50) -> dict:
    f = f"Date_Time ge datetime'{since}' and Date_Time le datetime'{until}'"
    if text:
        f += f" and Description ct '{text}'"
    rows = transport.get(entity, {"$filter": f, "$orderby": "Date_Time desc", "$top": limit, "$skip": offset})
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Read one document with tabular sections")
@quiet
def onec_get_document(entity: str, ref: str) -> dict:
    head = transport.get(entity, {"$filter": f"Ref_Key eq guid'{ref}'"})
    return head[0] if head else {}


@app.tool(description="Account or register balances")
@quiet
def onec_balances(entity: str, since: str, until: str, dimension: str = "", offset: int = 0, limit: int = 100) -> dict:
    params = {"$filter": f"Period ge datetime'{since}' and Period le datetime'{until}'", "$top": limit, "$skip": offset}
    if dimension:
        params["$filter"] += f" and contains({dimension}, '')"
    rows = transport.get(f"InformationRegister_{entity}_Balance", params)
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Account or register turnovers")
@quiet
def onec_turnovers(entity: str, since: str, until: str, offset: int = 0, limit: int = 100) -> dict:
    rows = transport.get(f"InformationRegister_{entity}_Turnovers",
                         {"$filter": f"Period ge datetime'{since}' and Period le datetime'{until}'", "$top": limit, "$skip": offset})
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Accounting entries of a document or period")
@quiet
def onec_postings(entity: str, since: str, until: str, offset: int = 0, limit: int = 100) -> dict:
    rows = transport.get(f"AccountingRegister_{entity}",
                         {"$filter": f"Period ge datetime'{since}' and Period le datetime'{until}'", "$top": limit, "$skip": offset})
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


@app.tool(description="Run a published 1C report service, adapter fills the URL")
@quiet
def onec_run_report(name: str, params: dict) -> dict:
    return transport.post_service(name, params)


def run():
    app.run(transport="stdio")
