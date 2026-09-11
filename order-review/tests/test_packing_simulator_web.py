from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.request import urlopen

from order_review.packing_simulator_web import PackingSimulatorHttpApp, make_handler


class StubService:
    def catalog_view(self):
        return {"brands": []}

    def list_historical_cases(self):
        return {"readOnly": True, "cases": []}

    def historical_case(self, case_id):
        if case_id == "known":
            return {"readOnly": True, "case": {"caseId": case_id}}
        raise KeyError(case_id)

    def assess_request(self, **kwargs):
        return {"request": kwargs, "business": {"status": "experiment_allowed"}}


def test_http_app_exposes_read_only_catalog_and_cases(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("hello", encoding="utf-8")
    app = PackingSimulatorHttpApp(StubService(), static_root=static)

    status, catalog = app.api_get("/api/catalog")
    assert status == HTTPStatus.OK
    assert catalog == {"brands": []}

    status, cases = app.api_get("/api/cases")
    assert status == HTTPStatus.OK
    assert cases["readOnly"] is True

    status, case = app.api_get("/api/cases/known")
    assert status == HTTPStatus.OK
    assert case["case"]["caseId"] == "known"


def test_http_app_assess_passes_explicit_selected_carton(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    app = PackingSimulatorHttpApp(StubService(), static_root=static)

    status, result = app.api_post(
        "/api/assess",
        {
            "brandId": "kgos",
            "cartonId": "carton-08",
            "lines": [{"merchantCode": "A", "quantity": 3}],
        },
    )

    assert status == HTTPStatus.OK
    assert result["request"]["brand_id"] == "kgos"
    assert result["request"]["carton_id"] == "carton-08"


def test_http_app_allows_automatic_carton_selection(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    app = PackingSimulatorHttpApp(StubService(), static_root=static)

    status, result = app.api_post(
        "/api/assess",
        {
            "brandId": "kgos",
            "cartonId": None,
            "lines": [{"merchantCode": "A", "quantity": 3}],
        },
    )

    assert status == HTTPStatus.OK
    assert result["request"]["carton_id"] is None


def test_static_files_cannot_escape_static_root(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("hello", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    app = PackingSimulatorHttpApp(StubService(), static_root=static)

    status, content_type, body = app.static_file("/")
    assert status == HTTPStatus.OK
    assert content_type.startswith("text/html")
    assert body == b"hello"

    status, _, body = app.static_file("/../secret.txt")
    assert status == HTTPStatus.NOT_FOUND
    assert body == b"not found"


def test_real_http_server_serves_static_and_api_without_residual_thread(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("packing-lab", encoding="utf-8")
    app = PackingSimulatorHttpApp(StubService(), static_root=static)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        host, port = server.server_address
        with urlopen(f"http://{host}:{port}/", timeout=2) as response:
            assert response.read() == b"packing-lab"
        with urlopen(f"http://{host}:{port}/api/catalog", timeout=2) as response:
            assert json.loads(response.read()) == {"brands": []}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()
