import json
import os
import socket
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import pytest

with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

conf = Path(tempfile.mkdtemp(prefix="onec-test-")) / "config.toml"
conf.write_text(
    f'[onec]\nbase_url = "http://127.0.0.1:{port}/base"\nrow_limit = 3\ncache_ttl = 0\nallowed_services = ["sales/summary"]\n',
    encoding="utf-8",
)
os.environ["ONEC_CONFIG"] = str(conf)
os.environ["ONEC_USER"] = "test-user"
os.environ["ONEC_PASSWORD"] = "test-pass"

metadata_xml = """<?xml version="1.0" encoding="UTF-8"?>
<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx" Version="1.0">
<edmx:DataServices><Schema xmlns="http://schemas.microsoft.com/ado/2009/11/edm" Namespace="StandardODATA">
<EntityType Name="Catalog_Номенклатура"><Property Name="Ref_Key" Type="Edm.Guid"/><Property Name="Description" Type="Edm.String"/>
<Property Name="Штрихкоды" Type="Collection(StandardODATA.Catalog_Номенклатура_Штрихкоды_RowType)"/>
<NavigationProperty Name="ЕдиницаИзмерения"/></EntityType>
<ComplexType Name="Catalog_Номенклатура_Штрихкоды_RowType"><Property Name="Штрихкод" Type="Edm.String"/></ComplexType>
<EntityContainer Name="EnterpriseV8">
<EntitySet Name="Catalog_Номенклатура"/><EntitySet Name="Document_Реализация"/>
<EntitySet Name="InformationRegister_Цены"/><EntitySet Name="InformationRegister_Цены_SliceLast"/>
<EntitySet Name="AccumulationRegister_Остатки"/><EntitySet Name="AccumulationRegister_Остатки_RecordType"/>
</EntityContainer></Schema></edmx:DataServices></edmx:Edmx>"""


class FakeOneC(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def answer(self, code, text, kind="application/json"):
        raw = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = unquote(self.path)
        self.seen.append(("GET", path, self.headers.get("Authorization", "")))
        if path.endswith("$metadata"):
            return self.answer(200, metadata_xml, "application/xml")
        if "/$count" in path:
            return self.answer(200, "\N{ZERO WIDTH NO-BREAK SPACE}7", "text/plain")
        if "/hs/" in path:
            return self.answer(200, json.dumps({"report": "ok"}))
        if "Missing" in path:
            return self.answer(404, "{}")
        rows = [{"Ref_Key": f"00000000-0000-0000-0000-00000000000{i}", "Description": f"Болт {i}"} for i in range(3)]
        if "(guid'" in path:
            return self.answer(200, json.dumps(rows[1], ensure_ascii=False))
        return self.answer(200, json.dumps({"odata.count": "7", "value": rows}, ensure_ascii=False))

    def do_POST(self):
        self.seen.append(("POST", self.path, ""))
        self.answer(200, "{}")

    do_PUT = do_PATCH = do_DELETE = do_POST


@pytest.fixture(scope="session", autouse=True)
def fake_onec():
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeOneC)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield FakeOneC.seen
    server.shutdown()


@pytest.fixture
def seen(fake_onec):
    fake_onec.clear()
    return fake_onec
