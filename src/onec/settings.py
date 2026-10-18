import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv

repo_root = Path(__file__).resolve().parents[2]
load_dotenv(repo_root / ".env")
load_dotenv()

conf_path = Path(os.environ.get("ONEC_CONFIG", repo_root / "config.toml"))
conf = tomllib.loads(conf_path.read_text("utf-8")) if conf_path.exists() else {}
onec_conf = conf.get("onec", conf)

base_url = onec_conf.get("base_url", "http://localhost/base").rstrip("/")
timeout = onec_conf.get("timeout", 30)
row_limit = onec_conf.get("row_limit", 500)
cache_ttl = onec_conf.get("cache_ttl", 60)
allowed_services = list(onec_conf.get("allowed_services", onec_conf.get("http_service", {}).get("allowed_services", [])))


def credentials():
    login = os.environ.get("ONEC_USER", "")
    secret = os.environ.get("ONEC_PASSWORD", "")
    if not login or not secret:
        raise RuntimeError("ONEC_USER and ONEC_PASSWORD are not set, put them in env or .env")
    return login, secret
