"""Regression tests for the formal resumable batch-state store."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.store import Anchor, BatchStateStore, MIN_ANCHOR_COUNT, StateError


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "batch-state.schema.json"


class BatchStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = BatchStateStore(Path(self.tempdir.name) / "state.json")

    def _record_page(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        updated_at: str,
    ) -> dict:
        state = self.store.load()
        mode = (
            "scroll"
            if state is not None
            and state["groups"][group_key]["last_page_index"] is not None
            else "current"
        )
        self.store.begin_capture(
            batch_id,
            group_key,
            page_index,
            mode=mode,
            started_at=updated_at,
        )
        return self.store.record_page(
            batch_id,
            group_key,
            page_index,
            updated_at=updated_at,
        )

    def _complete_group(
        self,
        batch_id: str,
        group_key: str,
        *,
        completed_at: str,
    ) -> dict:
        return self.store.mark_group_capture_complete(
            batch_id,
            group_key,
            completed_at=completed_at,
        )

    def test_schema_keeps_page_recovery_at_batch_level(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        batch_properties = schema["properties"]
        group_properties = schema["$defs"]["groupProgress"]["properties"]

        self.assertIn("next_page_index", batch_properties)
        self.assertNotIn("next_page_index", group_properties)
        self.assertIn("capture_complete", group_properties)
        self.assertNotIn("minItems", group_properties["last_completed_anchor"])
        completed_gate = schema["allOf"][0]
        self.assertTrue(
            completed_gate["then"]["properties"]["groups"]["additionalProperties"]
            ["properties"]["capture_complete"]["const"]
        )
        self.assertEqual(
            completed_gate["then"]["properties"]["groups"]["additionalProperties"]
            ["properties"]["last_completed_anchor"]["minItems"],
            MIN_ANCHOR_COUNT,
        )

    def test_new_batch_is_incomplete_and_resume_preserves_progress(self) -> None:
        first = self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )

        resumed = self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:09:00Z", group_keys=["group-a"]
        )

        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(resumed["started_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(resumed["next_page_index"], 1)
        self.assertFalse(self.store.can_build_inbox("batch-1"))

    def test_v2_state_is_migrated_without_guessing_incomplete_group_completion(self) -> None:
        state = self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        legacy = json.loads(json.dumps(state))
        legacy["schema_version"] = "2"
        legacy["groups"]["group-a"].pop("capture_complete")
        self.store.path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], "4")
        self.assertEqual(migrated["batch_kind"], "capture")
        self.assertFalse(migrated["groups"]["group-a"]["capture_complete"])
        self.assertEqual(migrated["groups"]["group-a"]["start_anchor"], [])
        persisted = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["schema_version"], "4")

    def test_v3_state_is_migrated_to_capture_with_empty_start_anchor(self) -> None:
        state = self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        legacy = json.loads(json.dumps(state))
        legacy["schema_version"] = "3"
        legacy.pop("batch_kind")
        legacy["groups"]["group-a"].pop("start_anchor")
        self.store.path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = self.store.load()

        self.assertEqual(migrated["schema_version"], "4")
        self.assertEqual(migrated["batch_kind"], "capture")
        self.assertEqual(migrated["groups"]["group-a"]["start_anchor"], [])

    def test_incremental_batch_copies_previous_completed_anchor_as_start_anchor(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self._complete_group(
            "batch-1", "group-a", completed_at="2026-01-01T00:01:30Z"
        )
        anchors = [Anchor(4, "old-1", "Alice", "09:01"), Anchor(5, "old-2", "Bob", "09:02")]
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": anchors},
            completed_at="2026-01-01T00:02:00Z",
        )

        incremental = self.store.start_batch(
            "batch-2",
            started_at="2026-01-02T00:00:00Z",
            group_keys=["group-a"],
            batch_kind="incremental",
        )

        self.assertEqual(incremental["batch_kind"], "incremental")
        self.assertEqual(
            incremental["groups"]["group-a"]["start_anchor"],
            [item.as_dict() for item in anchors],
        )
        self.assertEqual(
            incremental["groups"]["group-a"]["last_completed_anchor"],
            [item.as_dict() for item in anchors],
        )

    def test_incremental_batch_without_previous_anchor_is_rejected(self) -> None:
        with self.assertRaises(StateError):
            self.store.start_batch(
                "batch-1",
                started_at="2026-01-01T00:00:00Z",
                group_keys=["group-a"],
                batch_kind="incremental",
            )

    def test_incomplete_batch_cannot_resume_with_different_batch_kind(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        with self.assertRaises(StateError):
            self.store.start_batch(
                "batch-1",
                started_at="2026-01-01T00:01:00Z",
                group_keys=["group-a"],
                batch_kind="incremental",
            )

    def test_incomplete_batch_cannot_be_replaced(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        with self.assertRaises(StateError):
            self.store.start_batch(
                "batch-2", started_at="2026-01-01T00:01:00Z", group_keys=["group-a"]
            )

    def test_incomplete_batch_cannot_resume_with_different_groups(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        with self.assertRaises(StateError):
            self.store.start_batch(
                "batch-1",
                started_at="2026-01-01T00:01:00Z",
                group_keys=["group-a", "group-b"],
            )

    def test_page_recovery_point_rejects_gaps_and_duplicates(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        with self.assertRaises(StateError):
            self._record_page(
                "batch-1", "group-a", 1, updated_at="2026-01-01T00:01:00Z"
            )
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:02:00Z"
        )
        with self.assertRaises(StateError):
            self._record_page(
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
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self._complete_group(
            "batch-1", "group-a", completed_at="2026-01-01T00:01:30Z"
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
            self._record_page(
                "batch-1", group_key, page_index, updated_at="2026-01-01T00:01:00Z"
            )
            self._complete_group(
                "batch-1", group_key, completed_at="2026-01-01T00:01:30Z"
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
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self._complete_group(
            "batch-1", "group-a", completed_at="2026-01-01T00:01:30Z"
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
        self.assertNotIn("avatar_fingerprint", json.dumps(next_state))

    def test_analyzed_is_a_terminal_analysis_state(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self._record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self._complete_group(
            "batch-1", "group-a", completed_at="2026-01-01T00:01:30Z"
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
            self._record_page(
                "batch-1", "group-a", 1, updated_at="2026-01-01T00:04:00Z"
            )


if __name__ == "__main__":
    unittest.main()
