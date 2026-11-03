"""Durable QA-level review decisions for the presentation projection."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable

from .analysis_release import write_json_atomic
from .knowledge_display_projection import qa_fingerprint


DECISIONS_STATUS = "reviewed_display_qa_decisions"
ALLOWED_DECISIONS = {"discard", "knowledge", "archive"}


class DisplayReviewDecisionError(ValueError):
    pass


class DisplayReviewDecisionStore:
    def __init__(
        self,
        *,
        projection_path: Path,
        decisions_path: Path,
        now: Callable[[], str],
    ) -> None:
        self.projection_path = projection_path
        self.decisions_path = decisions_path
        self.now = now

    @staticmethod
    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _qa_map(self) -> dict[str, dict]:
        if not self.projection_path.is_file():
            return {}
        document = self._load(self.projection_path)
        if document.get("status") != "reviewed_knowledge_display_projection":
            raise DisplayReviewDecisionError("unexpected display projection status")
        result: dict[str, dict] = {}
        for item in document.get("items", []):
            kid = str(item.get("knowledge_id") or "")
            for qa in item.get("qas", []) or []:
                qa_id = str(qa.get("qa_id") or "")
                if not qa_id:
                    raise DisplayReviewDecisionError(
                        f"display projection QA missing qa_id: {kid}"
                    )
                if qa_id in result:
                    raise DisplayReviewDecisionError(f"duplicate qa_id: {qa_id}")
                result[qa_id] = {
                    **qa,
                    "knowledge_id": kid,
                    "qa_fingerprint": qa_fingerprint(kid, qa),
                }
        return result

    def _decisions(self) -> dict:
        if not self.decisions_path.exists():
            return {
                "schema_version": 1,
                "status": DECISIONS_STATUS,
                "reviewer": "user",
                "items": [],
            }
        document = self._load(self.decisions_path)
        if document.get("status") != DECISIONS_STATUS:
            raise DisplayReviewDecisionError("unexpected display review decisions status")
        if not isinstance(document.get("items"), list):
            raise DisplayReviewDecisionError("display review decisions items must be a list")
        return document

    def list_decisions(self) -> dict:
        qa_map = self._qa_map()
        rows = []
        for item in self._decisions().get("items", []):
            qa_id = str(item.get("qa_id") or "")
            current = qa_map.get(qa_id)
            if current is None:
                continue
            if str(item.get("qa_fingerprint") or "") != str(
                current.get("qa_fingerprint") or ""
            ):
                continue
            rows.append(copy.deepcopy(item))
        rows.sort(key=lambda row: row["qa_id"])
        return {
            "schema_version": 1,
            "status": "formal_display_qa_review_decisions",
            "items": rows,
        }

    def apply(self, qa_id: str, decision: str) -> dict:
        qa_id = str(qa_id or "").strip()
        decision = str(decision or "").strip()
        if decision not in ALLOWED_DECISIONS:
            raise DisplayReviewDecisionError(f"invalid display QA decision: {decision}")
        qa_map = self._qa_map()
        qa = qa_map.get(qa_id)
        if qa is None:
            raise DisplayReviewDecisionError(f"unknown qa_id: {qa_id}")

        lifecycle = str(qa.get("lifecycle") or "durable")
        if lifecycle == "time_bound" and decision == "knowledge":
            raise DisplayReviewDecisionError(
                f"time_bound QA cannot enter long-term knowledge: {qa_id}"
            )
        if lifecycle != "time_bound" and decision == "archive":
            raise DisplayReviewDecisionError(
                f"archive decision is only valid for time_bound QA: {qa_id}"
            )

        document = self._decisions()
        items = copy.deepcopy(document["items"])
        matching = [
            index for index, item in enumerate(items)
            if str(item.get("qa_id") or "") == qa_id
        ]
        if len(matching) > 1:
            raise DisplayReviewDecisionError(f"duplicate QA review decisions: {qa_id}")

        existing = items[matching[0]] if matching else None
        current_fingerprint = str(qa.get("qa_fingerprint") or "")
        if (
            existing is not None
            and existing.get("decision") == decision
            and str(existing.get("qa_fingerprint") or "") == current_fingerprint
        ):
            return {
                "status": "unchanged",
                "qa_id": qa_id,
                "decision": decision,
            }

        item = {
            "qa_id": qa_id,
            "knowledge_id": qa.get("knowledge_id"),
            "qa_fingerprint": current_fingerprint,
            "decision": decision,
            "decision_source": "user",
            "decided_at": self.now(),
        }
        if existing is not None:
            item["previous_decision"] = existing.get("decision")
            item["previous_decided_at"] = existing.get("decided_at")
            items[matching[0]] = item
        else:
            items.append(item)

        next_document = copy.deepcopy(document)
        next_document["items"] = items
        next_document["reviewer"] = "user"
        next_document["updated_at"] = item["decided_at"]
        write_json_atomic(self.decisions_path, next_document)
        return {
            "status": "updated",
            "qa_id": qa_id,
            "decision": decision,
        }
