"""Durable user review decisions for formal Silver queue units."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable

from .analysis_release import write_json_atomic
from .reviewed_semantic_state import build_reviewed_semantic_state
from .semantic_fingerprint import semantic_fingerprint


ALLOWED_DECISIONS = {"discard", "knowledge"}
DECISIONS_STATUS = "reviewed_user_semantic_decisions"


class ReviewDecisionError(ValueError):
    pass


class ReviewDecisionStore:
    def __init__(
        self,
        *,
        silver_path: Path,
        decisions_path: Path,
        state_path: Path,
        now: Callable[[], str],
    ) -> None:
        self.silver_path = silver_path
        self.decisions_path = decisions_path
        self.state_path = state_path
        self.now = now

    @staticmethod
    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _silver(self) -> dict:
        if not self.silver_path.is_file():
            raise ReviewDecisionError("formal Silver file does not exist")
        return self._load(self.silver_path)

    def _decisions(self) -> dict:
        if not self.decisions_path.exists():
            return {
                "schema_version": 1,
                "status": DECISIONS_STATUS,
                "reviewer": "user",
                "decision_basis": "Explicit user decisions from the review page.",
                "items": [],
            }
        document = self._load(self.decisions_path)
        if document.get("status") != DECISIONS_STATUS:
            raise ReviewDecisionError("unexpected reviewed semantic decisions status")
        if not isinstance(document.get("items"), list):
            raise ReviewDecisionError("reviewed semantic decisions items must be a list")
        return document

    @staticmethod
    def _unit_map(silver: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for unit in silver.get("units", []):
            kid = str(unit.get("knowledge_id") or "")
            if not kid:
                raise ReviewDecisionError("Silver unit missing knowledge_id")
            if kid in result:
                raise ReviewDecisionError(f"duplicate Silver knowledge_id: {kid}")
            result[kid] = unit
        return result

    def list_formal_decisions(self) -> dict:
        """Return only durable decisions tied to formal knowledge IDs."""
        silver = self._silver()
        units = self._unit_map(silver)
        state = build_reviewed_semantic_state(silver, self._decisions())
        rows = []
        for row in state.get("states", []):
            for kid in (row.get("aliases") or {}).get("knowledge_ids", []):
                if kid not in units:
                    continue
                rows.append({
                    "knowledge_id": kid,
                    "decision": row["decision"],
                    "semantic_fingerprint": row["semantic_fingerprint"],
                })
        rows.sort(key=lambda item: item["knowledge_id"])
        return {
            "schema_version": 1,
            "status": "formal_user_review_decisions",
            "items": rows,
        }

    def apply(self, knowledge_id: str, decision: str) -> dict:
        knowledge_id = str(knowledge_id or "").strip()
        decision = str(decision or "").strip()
        if decision not in ALLOWED_DECISIONS:
            raise ReviewDecisionError(f"invalid user review decision: {decision}")
        if not knowledge_id:
            raise ReviewDecisionError("knowledge_id is required")

        silver = self._silver()
        units = self._unit_map(silver)
        unit = units.get(knowledge_id)
        if unit is None:
            raise ReviewDecisionError(f"unknown formal Silver knowledge_id: {knowledge_id}")
        if unit.get("initial_state") != "queue":
            raise ReviewDecisionError(
                "page review decisions may only target formal Silver queue units"
            )

        document = self._decisions()
        items = copy.deepcopy(document["items"])
        matching_indexes = [
            index
            for index, item in enumerate(items)
            if str(item.get("knowledge_id") or "") == knowledge_id
        ]
        if len(matching_indexes) > 1:
            raise ReviewDecisionError(
                f"duplicate user review decisions for knowledge_id: {knowledge_id}"
            )

        fingerprint = semantic_fingerprint(unit)
        existing = items[matching_indexes[0]] if matching_indexes else None
        if existing is not None and existing.get("decision") == decision:
            state = build_reviewed_semantic_state(silver, document)
            return {
                "status": "unchanged",
                "knowledge_id": knowledge_id,
                "decision": decision,
                "semantic_fingerprint": fingerprint,
                "state_counts": state["counts"],
            }

        timestamp = self.now()
        item = {
            "decision": decision,
            "decision_source": "user",
            "knowledge_id": knowledge_id,
            "reason": "page_user_review",
            "decided_at": timestamp,
        }
        if existing is not None:
            item["previous_decision"] = existing.get("decision")
            item["previous_decided_at"] = existing.get("decided_at")
            items[matching_indexes[0]] = item
        else:
            items.append(item)

        next_document = copy.deepcopy(document)
        next_document["items"] = items
        next_document["reviewer"] = "user"
        next_document["updated_at"] = timestamp

        # Validate the complete state before mutating either durable file.  This catches
        # conflicts with legacy card-only decisions or formal knowledge state.
        state = build_reviewed_semantic_state(silver, next_document)

        write_json_atomic(self.decisions_path, next_document)
        write_json_atomic(self.state_path, state)
        return {
            "status": "updated",
            "knowledge_id": knowledge_id,
            "decision": decision,
            "semantic_fingerprint": fingerprint,
            "state_counts": state["counts"],
        }
