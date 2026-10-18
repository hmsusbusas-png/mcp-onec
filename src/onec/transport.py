import hashlib
import json
import time
from typing import Any

import httpx

from .settings import endpoint

_store: dict[str, tuple[float, Any]] = {}
_gate = httpx.Client(timeout=endpoint.timeout, auth=endpoint.auth)


def _key(url, params):
    raw = json.dumps([url, sorted(params.items())], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def get(path, params=None, cache=True):
    if path == "$metadata":
        url = f"{endpoint.base}/odata/standard.odata/$metadata"
        r = _gate.get(url)
        r.raise_for_status()
        return r.text
    url, params = endpoint.odata_url(path, params)
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


def post_service(name, payload):
    url, _ = endpoint.service_url(name)
    r = _gate.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def page(items, offset, limit=None):
    limit = limit or endpoint.row_limit
    return items[offset:offset + limit], len(items), offset + len(items[offset:offset + limit])
