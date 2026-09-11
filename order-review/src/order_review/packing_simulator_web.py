from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
import webbrowser

from .packing_simulator_service import (
    PackingSimulatorInputError,
    PackingSimulatorService,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3466
STATIC_ROOT = Path(__file__).resolve().parent / "packing_simulator_static"


class PackingSimulatorHttpApp:
    def __init__(
        self,
        service: PackingSimulatorService | None = None,
        *,
        static_root: str | Path = STATIC_ROOT,
    ) -> None:
        self.service = service or PackingSimulatorService()
        self.static_root = Path(static_root).resolve()

    def api_get(self, path: str) -> tuple[int, dict[str, Any]]:
        if path == "/api/catalog":
            return HTTPStatus.OK, self.service.catalog_view()
        if path == "/api/cases":
            return HTTPStatus.OK, self.service.list_historical_cases()
        if path.startswith("/api/cases/"):
            case_id = unquote(path.removeprefix("/api/cases/"))
            if not case_id:
                return HTTPStatus.BAD_REQUEST, {"error": "案例ID不能为空"}
            try:
                return HTTPStatus.OK, self.service.historical_case(case_id)
            except KeyError as exc:
                return HTTPStatus.NOT_FOUND, {"error": str(exc)}
        return HTTPStatus.NOT_FOUND, {"error": "未知接口"}

    def api_post(self, path: str, payload: Any) -> tuple[int, dict[str, Any]]:
        if path != "/api/assess":
            return HTTPStatus.NOT_FOUND, {"error": "未知接口"}
        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, {"error": "请求体必须是对象"}
        try:
            result = self.service.assess_request(
                brand_id=str(payload.get("brandId") or ""),
                carton_id=(str(payload.get("cartonId") or "").strip() or None),
                lines=payload.get("lines") or (),
                max_search_nodes=int(payload.get("maxSearchNodes") or 100_000),
            )
        except (PackingSimulatorInputError, TypeError, ValueError) as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
        return HTTPStatus.OK, result

    def static_file(self, request_path: str) -> tuple[int, str, bytes]:
        path = unquote(urlparse(request_path).path)
        if path == "/":
            path = "/index.html"
        candidate = (self.static_root / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(self.static_root)
        except ValueError:
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"
        if not candidate.is_file():
            return HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"not found"
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type += "; charset=utf-8"
        return HTTPStatus.OK, content_type, candidate.read_bytes()


def make_handler(app: PackingSimulatorHttpApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "OrderReviewPackingSimulator/1"

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path.startswith("/api/"):
                status, payload = app.api_get(path)
                self._send_json(status, payload)
                return
            status, content_type, body = app.static_file(self.path)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Content-Length无效"})
                return
            if length > 1_000_000:
                self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "请求体过大"})
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON格式无效"})
                return
            status, response = app.api_post(path, payload)
            self._send_json(status, response)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = False,
) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("装箱实验服务只允许绑定回环地址")
    app = PackingSimulatorHttpApp()
    server = ThreadingHTTPServer((host, port), make_handler(app))
    url = f"http://{host}:{port}/"
    print(f"装箱实验页面：{url}")
    print("仅本机回环访问；不连接ERP。Ctrl+C停止。")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="启动本地装箱实验页面")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, open_browser=args.open_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
