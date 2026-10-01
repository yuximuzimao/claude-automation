"""Stage 2-3 prototype for resumable capture batch state.

The formal ``src/store`` entry is intentionally not created until the batch/state
and end-to-end dry-run gates are complete. This module keeps the state contract
executable without touching private runtime data.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import unittest


MIN_ANCHOR_COUNT = 2
STATE_SCHEMA_VERSION = "1"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "batch-state.schema.json"


class StateError(ValueError):
    """Raised when a state transition would lose or misorder capture data."""


@dataclass(frozen=True)
class Anchor:
    sequence: int
    content_text: str
    sender_display: str | None = None
    timestamp_text: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "content_text": self.content_text,
            "sender_display": self.sender_display,
            "timestamp_text": self.timestamp_text,
        }


class BatchStateStore:
    """Small JSON state store with explicit incomplete/completed transitions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError("batch state is not valid JSON") from exc
        self._validate_state(state)
        return state

    @staticmethod
    def _validate_state(state: object) -> None:
        if not isinstance(state, dict):
            raise StateError("batch state must be an object")
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            raise StateError("unsupported batch state schema version")
        if not isinstance(state.get("batch_id"), str) or not state["batch_id"]:
            raise StateError("batch_id is required")
        if state.get("status") not in {"incomplete", "completed", "analyzed"}:
            raise StateError("unsupported batch state status")
        if not isinstance(state.get("next_page_index"), int) or state["next_page_index"] < 0:
            raise StateError("next_page_index must be non-negative")
        groups = state.get("groups")
        if not isinstance(groups, dict) or not groups:
            raise StateError("at least one group is required")
        for progress in groups.values():
            if not isinstance(progress, dict):
                raise StateError("group progress must be an object")
            last_page = progress.get("last_page_index")
            if last_page is not None and (not isinstance(last_page, int) or last_page < 0):
                raise StateError("last_page_index must be non-negative or null")
            anchors = progress.get("last_completed_anchor")
            if not isinstance(anchors, list):
                raise StateError("last_completed_anchor must be an array")
            for anchor in anchors:
                if (
                    not isinstance(anchor, dict)
                    or not isinstance(anchor.get("sequence"), int)
                    or anchor["sequence"] < 0
                    or not isinstance(anchor.get("content_text"), str)
                    or not anchor["content_text"]
                    or any(
                        anchor.get(field) is not None
                        and not isinstance(anchor.get(field), str)
                        for field in ("sender_display", "timestamp_text")
                    )
                ):
                    raise StateError("invalid completed anchor")
            if state["status"] in {"completed", "analyzed"} and len(anchors) < MIN_ANCHOR_COUNT:
                raise StateError("completed state requires continuous anchors")

    def start_batch(
        self,
        batch_id: str,
        *,
        started_at: str,
        group_keys: list[str],
    ) -> dict:
        if not batch_id or not group_keys or len(set(group_keys)) != len(group_keys):
            raise StateError("batch_id and unique group_keys are required")

        previous = self.load()
        if previous is not None and previous["status"] == "incomplete":
            if previous["batch_id"] != batch_id:
                raise StateError("cannot replace an incomplete batch")
            return previous

        previous_groups = previous["groups"] if previous is not None else {}
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "batch_id": batch_id,
            "status": "incomplete",
            "started_at": started_at,
            "updated_at": started_at,
            "next_page_index": 0,
            "last_completed_batch": (
                previous["last_completed_batch"]
                if previous is not None
                else None
            ),
            "last_success_at": (
                previous["last_success_at"] if previous is not None else None
            ),
            "groups": {
                group_key: {
                    "last_page_index": None,
                    "last_completed_anchor": previous_groups.get(
                        group_key, {}
                    ).get("last_completed_anchor", []),
                }
                for group_key in group_keys
            },
        }
        self._write(state)
        return state

    def record_page(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        updated_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        group = state["groups"].get(group_key)
        if group is None:
            raise StateError("group is not part of the active batch")
        if page_index != state["next_page_index"]:
            raise StateError("page_index must continue from the recovery point")

        group["last_page_index"] = page_index
        state["next_page_index"] = page_index + 1
        state["updated_at"] = updated_at
        self._write(state)
        return state

    def complete_batch(
        self,
        batch_id: str,
        *,
        anchors: dict[str, list[Anchor]],
        completed_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if set(anchors) != set(state["groups"]):
            raise StateError("a completed batch needs an anchor for every group")

        for group_key, group_anchors in anchors.items():
            if state["groups"][group_key]["last_page_index"] is None:
                raise StateError("each group needs at least one captured page")
            if len(group_anchors) < MIN_ANCHOR_COUNT:
                raise StateError("each group needs a continuous anchor sequence")
            if any(not item.content_text for item in group_anchors):
                raise StateError("anchor content_text must be non-empty")
            sequences = [item.sequence for item in group_anchors]
            if any(sequence < 0 for sequence in sequences):
                raise StateError("anchor sequence must be non-negative")
            if sequences != list(range(sequences[0], sequences[0] + len(sequences))):
                raise StateError("anchor sequence must be adjacent and ordered")
            state["groups"][group_key]["last_completed_anchor"] = [
                item.as_dict() for item in group_anchors
            ]

        state["status"] = "completed"
        state["updated_at"] = completed_at
        state["last_completed_batch"] = batch_id
        state["last_success_at"] = completed_at
        self._write(state)
        return state

    def mark_analyzed(self, batch_id: str, *, analyzed_at: str) -> dict:
        state = self.load()
        if state is None or state["batch_id"] != batch_id:
            raise StateError("batch does not exist")
        if state["status"] != "completed":
            raise StateError("only a completed batch can be analyzed")
        state["status"] = "analyzed"
        state["updated_at"] = analyzed_at
        self._write(state)
        return state

    def can_build_inbox(self, batch_id: str) -> bool:
        state = self.load()
        return bool(
            state is not None
            and state["batch_id"] == batch_id
            and state["status"] in {"completed", "analyzed"}
        )

    def _require_incomplete(self, batch_id: str) -> dict:
        state = self.load()
        if state is None or state["batch_id"] != batch_id:
            raise StateError("batch does not exist")
        if state["status"] != "incomplete":
            raise StateError("batch is no longer incomplete")
        return state

    def _write(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


class BatchStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = BatchStateStore(Path(self.tempdir.name) / "state.json")

    def test_schema_keeps_page_recovery_at_batch_level(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        batch_properties = schema["properties"]
        group_properties = schema["$defs"]["groupProgress"]["properties"]

        self.assertIn("next_page_index", batch_properties)
        self.assertNotIn("next_page_index", group_properties)

    def test_new_batch_is_incomplete_and_resume_preserves_progress(self) -> None:
        first = self.store.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a"],
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )

        resumed = self.store.start_batch(
            "batch-1",
            started_at="2026-01-01T00:09:00Z",
            group_keys=["group-a"],
        )

        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(resumed["started_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(resumed["next_page_index"], 1)
        self.assertFalse(self.store.can_build_inbox("batch-1"))

    def test_incomplete_batch_cannot_be_replaced(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )

        with self.assertRaises(StateError):
            self.store.start_batch(
                "batch-2",
                started_at="2026-01-01T00:01:00Z",
                group_keys=["group-a"],
            )

    def test_page_recovery_point_rejects_gaps_and_duplicates(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )

        with self.assertRaises(StateError):
            self.store.record_page(
                "batch-1", "group-a", 1, updated_at="2026-01-01T00:01:00Z"
            )

        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:02:00Z"
        )
        with self.assertRaises(StateError):
            self.store.record_page(
                "batch-1", "group-a", 0, updated_at="2026-01-01T00:03:00Z"
            )

    def test_completed_batch_requires_a_captured_page_per_group(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )

        with self.assertRaises(StateError):
            self.store.complete_batch(
                "batch-1",
                anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
                completed_at="2026-01-01T00:01:00Z",
            )

    def test_completed_batch_rejects_non_contiguous_anchor_sequences(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )

        with self.assertRaises(StateError):
            self.store.complete_batch(
                "batch-1",
                anchors={"group-a": [Anchor(2, "a2"), Anchor(4, "a4")]},
                completed_at="2026-01-01T00:02:00Z",
            )

    def test_completed_batch_requires_all_group_anchors_and_opens_inbox_gate(self) -> None:
        self.store.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a", "group-b"],
        )
        for page_index, group_key in enumerate(("group-a", "group-b")):
            self.store.record_page(
                "batch-1", group_key, page_index, updated_at="2026-01-01T00:01:00Z"
            )

        with self.assertRaises(StateError):
            self.store.complete_batch(
                "batch-1",
                anchors={"group-a": [Anchor(0, "only one")]},
                completed_at="2026-01-01T00:02:00Z",
            )

        completed = self.store.complete_batch(
            "batch-1",
            anchors={
                "group-a": [Anchor(0, "a1", "Alice"), Anchor(1, "a2", "Alice")],
                "group-b": [Anchor(0, "b1"), Anchor(1, "b2")],
            },
            completed_at="2026-01-01T00:03:00Z",
        )

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["last_completed_batch"], "batch-1")
        self.assertTrue(self.store.can_build_inbox("batch-1"))

    def test_next_batch_carries_only_completed_anchors(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:02:00Z",
        )

        next_state = self.store.start_batch(
            "batch-2", started_at="2026-01-02T00:00:00Z", group_keys=["group-a"]
        )

        self.assertEqual(next_state["status"], "incomplete")
        self.assertEqual(next_state["last_completed_batch"], "batch-1")
        self.assertEqual(
            next_state["groups"]["group-a"]["last_completed_anchor"][0]["content_text"],
            "a1",
        )
        serialized = json.dumps(next_state)
        self.assertNotIn("avatar_fingerprint", serialized)

    def test_analyzed_is_a_terminal_analysis_state(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:02:00Z",
        )

        analyzed = self.store.mark_analyzed(
            "batch-1", analyzed_at="2026-01-01T00:03:00Z"
        )

        self.assertEqual(analyzed["status"], "analyzed")
        self.assertTrue(self.store.can_build_inbox("batch-1"))
        with self.assertRaises(StateError):
            self.store.record_page(
                "batch-1", "group-a", 1, updated_at="2026-01-01T00:04:00Z"
            )


if __name__ == "__main__":
    unittest.main()
