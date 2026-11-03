from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from src.app.serve_analysis import ReviewApp, make_server


def unit(kid: str, state: str) -> dict:
    return {
        "knowledge_id": kid,
        "subject": "测试",
        "question": f"{kid} 是否保留？",
        "kind": "mechanism",
        "scope": {"game_variant": "时光服"},
        "canonical_facts": ["事实"],
        "structured": {},
        "evidence_refs": [{"card_id": "T1", "coverage": "full"}],
        "initial_state": state,
    }


class AnalysisReviewServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        work = self.root / "runtime" / "analysis-work"
        work.mkdir(parents=True)
        (work / "silver-knowledge-v1.json").write_text(
            json.dumps(
                {"units": [unit("K-Q", "queue"), unit("K-K", "knowledge")]},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (work / "reviewed-semantic-decisions-v1.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "reviewed_user_semantic_decisions",
                    "items": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (work / "knowledge-display-projection-v1.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "reviewed_knowledge_display_projection",
                    "items": [{
                        "knowledge_id": "K-Q",
                        "display_status": "visible",
                        "qas": [
                            {
                                "qa_id": "K-Q::q01",
                                "question": "长期问题？",
                                "answer": "长期结论。",
                                "confidence": "high",
                                "lifecycle": "durable",
                                "time_context": "",
                                "verification_note": "",
                                "evidence_refs": ["T1"],
                            },
                            {
                                "qa_id": "K-Q::q02",
                                "question": "阶段问题？",
                                "answer": "阶段结论。",
                                "confidence": "medium",
                                "lifecycle": "time_bound",
                                "time_context": "P6首周",
                                "verification_note": "阶段信息",
                                "evidence_refs": ["T1"],
                            },
                        ],
                    }],
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.render_calls = 0

        def render(page: Path, details: Path) -> dict:
            self.render_calls += 1
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(
                "<html><head></head><body>review</body></html>",
                encoding="utf-8",
            )
            details.mkdir(parents=True, exist_ok=True)
            (details / "T1.html").write_text("detail", encoding="utf-8")
            return {"effective_v3_queue": 1}

        self.app = ReviewApp(
            self.root,
            csrf_token="fixed-token",
            now=lambda: "2026-01-01T00:00:00Z",
            render_executor=render,
        )
        self.app.rebuild()
        self.server = make_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._shutdown)

    def _shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        token: str | None = None,
        origin: str | None = None,
    ) -> tuple[int, bytes]:
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        headers = {}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-GCA-CSRF"] = token
        if origin is not None:
            headers["Origin"] = origin
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        status = response.status
        conn.close()
        return status, data

    def test_page_injects_csrf_and_detail_is_served(self) -> None:
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"fixed-token", page)
        status, detail = self.request("GET", "/page-v2-details/T1.html")
        self.assertEqual(status, 200)
        self.assertEqual(detail, b"detail")

    def test_review_state_returns_formal_knowledge(self) -> None:
        status, body = self.request("GET", "/api/review-state")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        rows = {row["knowledge_id"]: row["decision"] for row in payload["items"]}
        self.assertEqual(rows, {"K-K": "knowledge"})

    def test_valid_post_persists_and_rebuilds(self) -> None:
        status, body = self.request(
            "POST",
            "/api/review-decision",
            body={"knowledge_id": "K-Q", "decision": "knowledge"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["status"], "updated")
        self.assertEqual(payload["render_status"], "rebuilt")
        self.assertEqual(self.render_calls, 2)
        decisions = json.loads(
            (
                self.root
                / "runtime"
                / "analysis-work"
                / "reviewed-semantic-decisions-v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(decisions["items"][0]["decision"], "knowledge")

    def test_display_review_decisions_are_granular_and_persistent(self) -> None:
        status, body = self.request(
            "POST",
            "/api/display-review-decision",
            body={"qa_id": "K-Q::q01", "decision": "discard"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["qa_id"], "K-Q::q01")
        self.assertEqual(payload["decision"], "discard")

        status, body = self.request("GET", "/api/display-review-state")
        self.assertEqual(status, 200)
        rows = {row["qa_id"]: row["decision"] for row in json.loads(body)["items"]}
        self.assertEqual(rows, {"K-Q::q01": "discard"})

    def test_display_review_state_survives_confidence_only_change(self) -> None:
        status, _ = self.request(
            "POST",
            "/api/display-review-decision",
            body={"qa_id": "K-Q::q01", "decision": "discard"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 200)
        projection_path = (
            self.root / "runtime" / "analysis-work" / "knowledge-display-projection-v1.json"
        )
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        projection["items"][0]["qas"][0]["confidence"] = "medium"
        projection_path.write_text(
            json.dumps(projection, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        status, body = self.request("GET", "/api/display-review-state")
        self.assertEqual(status, 200)
        rows = {row["qa_id"]: row["decision"] for row in json.loads(body)["items"]}
        self.assertEqual(rows, {"K-Q::q01": "discard"})

    def test_display_review_state_drops_stale_semantic_decision(self) -> None:
        status, _ = self.request(
            "POST",
            "/api/display-review-decision",
            body={"qa_id": "K-Q::q01", "decision": "discard"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 200)
        projection_path = (
            self.root / "runtime" / "analysis-work" / "knowledge-display-projection-v1.json"
        )
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        projection["items"][0]["qas"][0]["answer"] = "结论已经改变。"
        projection_path.write_text(
            json.dumps(projection, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        status, body = self.request("GET", "/api/display-review-state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"], [])

    def test_time_bound_qa_cannot_enter_long_term_knowledge(self) -> None:
        status, body = self.request(
            "POST",
            "/api/display-review-decision",
            body={"qa_id": "K-Q::q02", "decision": "knowledge"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 400)
        self.assertIn("time_bound", json.loads(body)["message"])

    def test_time_bound_qa_can_be_archived(self) -> None:
        status, body = self.request(
            "POST",
            "/api/display-review-decision",
            body={"qa_id": "K-Q::q02", "decision": "archive"},
            token="fixed-token",
            origin=f"http://127.0.0.1:{self.server.server_port}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["decision"], "archive")

    def test_csrf_and_cross_origin_are_rejected(self) -> None:
        status, _ = self.request(
            "POST",
            "/api/review-decision",
            body={"knowledge_id": "K-Q", "decision": "discard"},
            token="wrong",
        )
        self.assertEqual(status, 403)
        status, _ = self.request(
            "POST",
            "/api/review-decision",
            body={"knowledge_id": "K-Q", "decision": "discard"},
            token="fixed-token",
            origin="https://evil.example",
        )
        self.assertEqual(status, 403)

    def test_nonlocal_bind_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            make_server(self.app, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
