import hashlib
import json
import time
from typing import Any
from urllib.parse import quote

import httpx

from .settings import endpoint

_store: dict[str, tuple[float, Any]] = {}
_gate = httpx.Client(timeout=endpoint.timeout, auth=endpoint.auth)


def _key(url, params):
    raw = json.dumps([url, sorted(params.items())], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def enc_entity(name):
    # 1C entity names are often russian: Catalog_Контрагенты
    return quote(name, safe="")


def get(path, params=None, cache=True, entity_encoded=False):
    if path == "$metadata":
        url = f"{endpoint.base}/odata/standard.odata/$metadata"
        r = _gate.get(url)
        r.raise_for_status()
        return r.text
    part = enc_entity(path) if entity_encoded else path
    url, params = endpoint.odata_url(part, params)
    if cache:
        hit = _store.get(_key(url, params))
        if hit and time.time() - hit[0] < endpoint.cache_ttl:
            return hit[1]
    r = _gate.get(url, params=params)
    r.raise_for_status()
    body = r.json()["value"]
    if cache:
        _store[_key(url, params)] = (time.time(), body)
    return body


def get_service(name, params=None):
    # read-only by design: white listed services, GET only
    allowed = endpoint.allowed_services
    if name not in allowed:
        raise PermissionError(f"service {name!r} not in allowed_services in config.toml")
    url, qs = endpoint.service_url(name, params)
    r = _gate.get(url, params=qs)
    r.raise_for_status()
    return r.json()


def page(items, offset, limit=None):
    limit = limit or endpoint.row_limit
    return items[offset:offset + limit], len(items), offset + len(items[offset:offset + limit])
