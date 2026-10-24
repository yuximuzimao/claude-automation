from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.store import (
    Anchor,
    BatchStateStore,
    IncrementalCheckpointError,
    IncrementalCheckpointStore,
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageStore,
)
from src.store.finalize import finalize_batch


def record(
    batch_id: str,
    group_key: str,
    sequence: int,
    text: str,
    sender: str,
    time_text: str,
) -> dict[str, object]:
    return {
        "schema_version": MESSAGE_SCHEMA_VERSION,
        "record_id": f"{batch_id}:{group_key}:{sequence}",
        "batch_id": batch_id,
        "group_key": group_key,
        "group_display": group_key,
        "sequence": sequence,
        "sender_display": sender,
        "timestamp": None,
        "timestamp_text": time_text,
        "message_type": "text",
        "content_text": text,
        "ocr_confidence": 1.0,
        "observed_at": "2026-01-02T00:00:00Z",
        "source": MESSAGE_SOURCE,
        "capture_refs": [],
    }


class IncrementalCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.runtime = self.root / "runtime"
        self.source_runtime = self.root / "runtime" / "history-days" / "2026-01-02"
        self.group = "group-a"
        self._seed_main_baseline()
        self._seed_source_runtime()

    def _seed_main_baseline(self) -> None:
        store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        store.start_batch(
            "baseline-main",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a", "group-b"],
        )
        for page_index, group_key in enumerate(("group-a", "group-b")):
            store.begin_capture(
                "baseline-main",
                group_key,
                page_index,
                mode="current",
                started_at=f"2026-01-01T00:01:0{page_index}Z",
            )
            store.record_page(
                "baseline-main",
                group_key,
                page_index,
                updated_at=f"2026-01-01T00:01:1{page_index}Z",
            )
            store.mark_group_capture_complete(
                "baseline-main",
                group_key,
                completed_at=f"2026-01-01T00:01:2{page_index}Z",
            )
        store.complete_batch(
            "baseline-main",
            anchors={
                "group-a": [
                    Anchor(10, "old-a-1", "A", "09:00"),
                    Anchor(11, "old-a-2", "A", "09:01"),
                ],
                "group-b": [
                    Anchor(20, "old-b-1", "B", "09:00"),
                    Anchor(21, "old-b-2", "B", "09:01"),
                ],
            },
            completed_at="2026-01-01T00:02:00Z",
        )

    def _seed_source_runtime(self) -> None:
        state = BatchStateStore(
            self.source_runtime / "state" / "batch-state.json"
        )
        messages = MessageStore(
            self.source_runtime / "messages" / "messages.jsonl"
        )
        state.start_batch(
            "history-20260102-full",
            started_at="2026-01-02T00:00:00Z",
            group_keys=[self.group],
        )
        state.begin_capture(
            "history-20260102-full",
            self.group,
            0,
            mode="current",
            started_at="2026-01-02T00:01:00Z",
        )
        state.record_page(
            "history-20260102-full",
            self.group,
            0,
            updated_at="2026-01-02T00:01:10Z",
        )
        state.mark_group_capture_complete(
            "history-20260102-full",
            self.group,
            completed_at="2026-01-02T00:01:20Z",
        )
        rows = [
            record(
                "history-20260102-full",
                self.group,
                0,
                "newer-a-1",
                "A",
                "23:58",
            ),
            record(
                "history-20260102-full",
                self.group,
                1,
                "newer-a-2",
                "A",
                "23:59",
            ),
        ]
        finalize_batch(
            state_store=state,
            message_store=messages,
            batch_id="history-20260102-full",
            records=rows,
            completed_at="2026-01-02T00:02:00Z",
            current_destination=self.source_runtime / "inbox" / "current.md",
        )

    def store(self) -> IncrementalCheckpointStore:
        return IncrementalCheckpointStore(self.root, self.runtime)

    def test_create_and_resolve_checkpoint_for_exact_base(self) -> None:
        checkpoint = self.store()
        created = checkpoint.create_from_completed_runtime(
            source_runtime=self.source_runtime,
            group_key=self.group,
            created_at="2026-01-03T00:00:00Z",
        )

        self.assertEqual(created["status"], "ready")
        self.assertEqual(created["base_batch_id"], "baseline-main")
        previous = BatchStateStore(
            self.runtime / "state" / "batch-state.json"
        ).load()
        overrides = checkpoint.resolve_for_next_batch(
            previous_state=previous,
            group_keys=["group-a", "group-b"],
        )
        self.assertEqual(
            [row["content_text"] for row in overrides["group-a"]],
            ["newer-a-1", "newer-a-2"],
        )
        self.assertEqual(set(overrides), {"group-a"})

    def test_stale_checkpoint_is_ignored_after_base_changes(self) -> None:
        checkpoint = self.store()
        checkpoint.create_from_completed_runtime(
            source_runtime=self.source_runtime,
            group_key=self.group,
            created_at="2026-01-03T00:00:00Z",
        )
        previous = BatchStateStore(
            self.runtime / "state" / "batch-state.json"
        ).load()
        stale_view = dict(previous)
        stale_view["batch_id"] = "newer-main-batch"

        self.assertEqual(
            checkpoint.resolve_for_next_batch(
                previous_state=stale_view,
                group_keys=["group-a", "group-b"],
            ),
            {},
        )

    def test_source_messages_tamper_blocks_before_anchor_use(self) -> None:
        checkpoint = self.store()
        checkpoint.create_from_completed_runtime(
            source_runtime=self.source_runtime,
            group_key=self.group,
            created_at="2026-01-03T00:00:00Z",
        )
        messages_path = self.source_runtime / "messages" / "messages.jsonl"
        messages_path.write_text(
            messages_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        previous = BatchStateStore(
            self.runtime / "state" / "batch-state.json"
        ).load()

        with self.assertRaisesRegex(
            IncrementalCheckpointError,
            "source messages changed",
        ):
            checkpoint.resolve_for_next_batch(
                previous_state=previous,
                group_keys=["group-a", "group-b"],
            )

    def test_source_state_tamper_blocks_before_anchor_use(self) -> None:
        checkpoint = self.store()
        checkpoint.create_from_completed_runtime(
            source_runtime=self.source_runtime,
            group_key=self.group,
            created_at="2026-01-03T00:00:00Z",
        )
        state_path = self.source_runtime / "state" / "batch-state.json"
        document = json.loads(state_path.read_text(encoding="utf-8"))
        document["updated_at"] = "2026-01-02T00:03:00Z"
        state_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        previous = BatchStateStore(
            self.runtime / "state" / "batch-state.json"
        ).load()

        with self.assertRaisesRegex(
            IncrementalCheckpointError,
            "source state changed",
        ):
            checkpoint.resolve_for_next_batch(
                previous_state=previous,
                group_keys=["group-a", "group-b"],
            )

    def test_create_rejects_source_anchor_that_is_not_canonical_tail(self) -> None:
        source_state_store = BatchStateStore(
            self.source_runtime / "state" / "batch-state.json"
        )
        source_state = source_state_store.load()
        source_state["groups"][self.group]["last_completed_anchor"] = [
            Anchor(0, "wrong-1", "A", "23:58").as_dict(),
            Anchor(1, "wrong-2", "A", "23:59").as_dict(),
        ]
        source_state_store._write(source_state)

        with self.assertRaisesRegex(
            IncrementalCheckpointError,
            "canonical message tail",
        ):
            self.store().create_from_completed_runtime(
                source_runtime=self.source_runtime,
                group_key=self.group,
                created_at="2026-01-03T00:00:00Z",
            )

    def test_checkpoint_group_outside_requested_incremental_is_rejected(self) -> None:
        checkpoint = self.store()
        checkpoint.create_from_completed_runtime(
            source_runtime=self.source_runtime,
            group_key=self.group,
            created_at="2026-01-03T00:00:00Z",
        )
        previous = BatchStateStore(
            self.runtime / "state" / "batch-state.json"
        ).load()

        with self.assertRaisesRegex(
            IncrementalCheckpointError,
            "outside the requested",
        ):
            checkpoint.resolve_for_next_batch(
                previous_state=previous,
                group_keys=["group-b"],
            )


if __name__ == "__main__":
    unittest.main()
