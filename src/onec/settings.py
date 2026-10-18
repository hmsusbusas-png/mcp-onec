import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv
from httpx import Auth

load_dotenv()

_cfg = {}
_cfg_path = os.environ.get("ONEC_CONFIG", "config.toml")
if Path(_cfg_path).exists():
    _cfg = tomllib.loads(Path(_cfg_path).read_text("utf-8"))


class BasicAuth(Auth):
    def __init__(self):
        self.user = os.environ.get("ONEC_USER", "")
        self.pwd = os.environ.get("ONEC_PASSWORD", "")
        if not self.user or not self.pwd:
            raise RuntimeError("ONEC_USER and ONEC_PASSWORD must be set in env")

    def auth_flow(self, request):
        import base64
        token = base64.b64encode(f"{self.user}:{self.pwd}".encode()).decode()
        request.headers["Authorization"] = f"Basic {token}"
        yield request


class Endpoint:
    def __init__(self):
        self.mode = _cfg.get("mode", "odata")
        self.base = _cfg.get("base_url", "http://localhost").rstrip("/")
        self.timeout = _cfg.get("timeout", 30)
        self.row_limit = _cfg.get("row_limit", 500)
        self.cache_ttl = _cfg.get("cache_ttl", 60)
        self.reports = _cfg.get("http_service", {}).get("reports_root", "")
        self.auth = BasicAuth()

    def odata_url(self, path, params=None):
        url = f"{self.base}/odata/standard.odata/{path}"
        if params is None:
            params = {}
        params.setdefault("$format", "json")
        return url, params

    def service_url(self, name, params=None):
        # 1C http services are published per config; adapter expects full path
        url = f"{self.base}/hs/{name}"
        return url, params or {}


endpoint = Endpoint()
