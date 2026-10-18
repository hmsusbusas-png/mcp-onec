import re
import time
from urllib.parse import quote

import httpx

from . import settings

odata_root = f"{settings.base_url}/odata/standard.odata"
name_rule = re.compile(r"^\w+$")
guid_rule = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
moment_rule = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")

recent: dict[str, tuple[float, object]] = {}
client = None


def refuse_writes(request):
    if request.method != "GET":
        raise PermissionError(f"onec is read only, {request.method} blocked")


def gate():
    global client
    if client is None:
        client = httpx.Client(
            timeout=settings.timeout,
            auth=httpx.BasicAuth(*settings.credentials()),
            event_hooks={"request": [refuse_writes]},
        )
    return client


def object_name(name):
    if not name_rule.match(name or ""):
        raise ValueError(f"bad object name {name!r}, expected something like Catalog_Номенклатура")
    return name


def guid(ref):
    if not guid_rule.match(ref or ""):
        raise ValueError(f"bad Ref_Key {ref!r}, expected a guid")
    return ref


def moment(stamp, day_end=False):
    if not moment_rule.match(stamp or ""):
        raise ValueError(f"bad date {stamp!r}, use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    if "T" in stamp:
        return stamp
    return stamp + ("T23:59:59" if day_end else "T00:00:00")


def encode_query(query):
    # 1C wants %20 for spaces, httpx would send +
    return "&".join(quote(k, safe="$") + "=" + quote(str(v), safe="'(),:=") for k, v in query.items())


def literal(text):
    return "'" + text.replace("'", "''") + "'"


def fetch(url, query=None, use_cache=True):
    query = dict(query or {})
    query.setdefault("$format", "json")
    key = url + "?" + encode_query(query)
    hit = recent.get(key)
    if use_cache and hit and time.monotonic() - hit[0] < settings.cache_ttl:
        return hit[1]
    reply = gate().get(key)
    if reply.status_code == 401:
        raise PermissionError("1C rejected the login, check ONEC_USER and ONEC_PASSWORD")
    if reply.status_code == 404:
        raise LookupError(f"1C returned 404 for {url.removeprefix(odata_root)}, object is not published or misspelled")
    reply.raise_for_status()
    body = reply.json()
    if use_cache:
        recent[key] = (time.monotonic(), body)
    return body


def metadata():
    reply = gate().get(f"{odata_root}/$metadata")
    reply.raise_for_status()
    return reply.text


def rows(path, query, offset, limit):
    limit = max(1, min(limit, settings.row_limit))
    query = {**query, "$top": limit, "$skip": max(0, offset), "$inlinecount": "allpages"}
    body = fetch(f"{odata_root}/{path}", query)
    items = body.get("value", [])
    total = body.get("odata.count")
    total = int(total) if total is not None else None
    more = len(items) == limit and (total is None or offset + limit < total)
    return {"items": items, "total": total, "next_offset": offset + len(items) if more else None}


def one(entity, ref):
    path = quote(f"{object_name(entity)}(guid'{guid(ref)}')", safe="()'")
    return fetch(f"{odata_root}/{path}")


def segment(entity):
    return quote(object_name(entity), safe="")


def service(name, params):
    if name not in settings.allowed_services:
        raise PermissionError(f"service {name!r} is not in allowed_services in config.toml")
    path = "/".join(quote(part, safe="") for part in name.split("/"))
    tail = "?" + encode_query(params) if params else ""
    reply = gate().get(f"{settings.base_url}/hs/{path}{tail}")
    reply.raise_for_status()
    try:
        return reply.json()
    except ValueError:
        return {"text": reply.text[:20000]}
