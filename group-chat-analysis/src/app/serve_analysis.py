"""Local-only review UI server with durable user decisions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Callable
from urllib.parse import unquote, urlsplit

from src.analysis.review_decision_store import (
    ReviewDecisionError,
    ReviewDecisionStore,
)


MAX_BODY_BYTES = 16 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ReviewApp:
    def __init__(
        self,
        project_root: Path,
        *,
        csrf_token: str | None = None,
        now: Callable[[], str] = utc_now,
        render_executor: Callable[[Path, Path], dict] | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.work = self.project_root / "runtime" / "analysis-work"
        self.live_root = self.project_root / "runtime" / "reports" / "review-live"
        self.page_path = self.live_root / "page.html"
        self.details_dir = self.live_root / "page-v2-details"
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)
        self.store = ReviewDecisionStore(
            silver_path=self.work / "silver-knowledge-v1.json",
            decisions_path=self.work / "reviewed-semantic-decisions-v1.json",
            state_path=self.work / "reviewed-semantic-state-v1.json",
            now=now,
        )
        self.render_executor = render_executor or self._render

    def _render(self, page: Path, details: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.analysis.page_builder",
                "--output",
                str(page),
                "--details-dir",
                str(details),
            ],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"formal page builder failed with exit code {result.returncode}"
            )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return {}
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def rebuild(self) -> dict:
        self.live_root.mkdir(parents=True, exist_ok=True)
        return self.render_executor(self.page_path, self.details_dir)

    def injected_page(self) -> bytes:
        if not self.page_path.is_file():
            raise FileNotFoundError(self.page_path)
        text = self.page_path.read_text(encoding="utf-8")
        injection = (
            "<script>window.GCA_REVIEW_API="
            + json.dumps({"csrf": self.csrf_token}, ensure_ascii=False)
            + ";</script>"
        )
        if "</head>" in text:
            text = text.replace("</head>", injection + "</head>", 1)
        else:
            text = injection + text
        return text.encode("utf-8")

    def detail_file(self, request_path: str) -> Path | None:
        prefix = "/page-v2-details/"
        if not request_path.startswith(prefix):
            return None
        name = unquote(request_path[len(prefix):])
        if (
            not name
            or "/" in name
            or "\\" in name
            or not name.endswith(".html")
        ):
            return None
        candidate = (self.details_dir / name).resolve()
        try:
            candidate.relative_to(self.details_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "GCAReview/1"
    app: ReviewApp

    def log_message(self, format: str, *args) -> None:
        # Keep private message content out of default access logs.
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.client_address[0], self.log_date_time_string(), format % args)
        )

    def _host_is_local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":", 1)[0].lower()
        return host in {"127.0.0.1", "localhost"}

    def _origin_is_local(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlsplit(origin)
        except ValueError:
            return False
        return parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
        }

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _reject_nonlocal(self) -> bool:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._json(403, {"error": "loopback_only"})
            return True
        if not self._host_is_local():
            self._json(403, {"error": "invalid_host"})
            return True
        return False

    def do_GET(self) -> None:
        if self._reject_nonlocal():
            return
        path = urlsplit(self.path).path
        if path == "/api/review-state":
            try:
                self._json(200, self.app.store.list_formal_decisions())
            except Exception as exc:
                self._json(500, {"error": type(exc).__name__, "message": str(exc)})
            return
        if path in {"/", "/index.html"}:
            try:
                self._bytes(
                    200,
                    self.app.injected_page(),
                    "text/html; charset=utf-8",
                )
            except FileNotFoundError:
                self._json(503, {"error": "review_page_not_built"})
            return
        detail = self.app.detail_file(path)
        if detail is not None:
            content_type = mimetypes.guess_type(detail.name)[0] or "text/html"
            self._bytes(
                200,
                detail.read_bytes(),
                content_type + "; charset=utf-8",
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self._reject_nonlocal():
            return
        path = urlsplit(self.path).path
        if path != "/api/review-decision":
            self._json(404, {"error": "not_found"})
            return
        if not self._origin_is_local():
            self._json(403, {"error": "invalid_origin"})
            return
        if self.headers.get("X-GCA-CSRF") != self.app.csrf_token:
            self._json(403, {"error": "invalid_csrf"})
            return
        if (self.headers.get("Content-Type") or "").split(";", 1)[0].strip() != "application/json":
            self._json(415, {"error": "json_required"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._json(400, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": "invalid_body_size"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "invalid_json"})
            return
        if not isinstance(body, dict):
            self._json(400, {"error": "json_object_required"})
            return
        try:
            result = self.app.store.apply(
                body.get("knowledge_id"),
                body.get("decision"),
            )
        except ReviewDecisionError as exc:
            self._json(400, {"error": "invalid_review_decision", "message": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": type(exc).__name__, "message": str(exc)})
            return

        render_status = "not_needed"
        if result["status"] == "updated":
            try:
                self.app.rebuild()
                render_status = "rebuilt"
            except Exception as exc:
                # The decision is already durable.  Report the render issue without
                # pretending the write failed; a later rebuild can recover it.
                render_status = f"failed:{type(exc).__name__}"
        response = dict(result)
        response["render_status"] = render_status
        self._json(200, response)

    def do_OPTIONS(self) -> None:
        # Deliberately no CORS support. Cross-origin JSON writes must fail preflight.
        self._json(405, {"error": "cors_not_supported"})


def make_server(
    app: ReviewApp,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("review server may only bind to 127.0.0.1")
    handler = type(
        "BoundReviewHandler",
        (ReviewHandler,),
        {"app": app},
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()

    app = ReviewApp(args.project_root)
    if not args.no_rebuild:
        summary = app.rebuild()
        print(
            json.dumps(
                {"status": "page_built", "summary": summary},
                ensure_ascii=False,
            )
        )
    server = make_server(app, port=args.port)
    print(
        json.dumps(
            {
                "status": "serving",
                "url": f"http://127.0.0.1:{server.server_port}/",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
