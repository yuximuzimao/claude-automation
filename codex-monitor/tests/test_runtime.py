from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.runtime import DebouncedRefresher, PollingWatcher, RefreshRequest


class RuntimeTests(unittest.TestCase):
    def test_debounced_refresher_coalesces_changes_and_uses_incremental_gate(self) -> None:
        requests: list[RefreshRequest] = []
        refresher = DebouncedRefresher(
            requests.append,
            delay_seconds=0.5,
            incremental_window_seconds=300,
            claude_max_files=50,
        )

        refresher.notify_change(Path("a.jsonl"), now=100.0)
        refresher.notify_change(Path("b.jsonl"), now=100.2)

        self.assertFalse(refresher.flush_due(now=100.6))
        self.assertEqual(requests, [])

        self.assertTrue(refresher.flush_due(now=100.8))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].claude_modified_since, 100.8 - 300)
        self.assertEqual(requests[0].claude_max_files, 50)
        self.assertEqual(requests[0].reason, "watcher")

    def test_manual_request_keeps_existing_scope(self) -> None:
        request = RefreshRequest.manual()

        self.assertIsNone(request.claude_modified_since)
        self.assertIsNone(request.claude_max_files)
        self.assertEqual(request.reason, "manual")

    def test_polling_watcher_detects_mtime_changes_without_reading_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "session.jsonl"
            path.write_text("{}", encoding="utf-8")
            changes: list[Path] = []
            watcher = PollingWatcher((path,), changes.append)
            watcher.poll_once()
            self.assertEqual(changes, [])
            path.write_text("{}\n", encoding="utf-8")

            with patch.object(Path, "open", side_effect=AssertionError("must not read")):
                watcher.poll_once()

            self.assertEqual(changes, [path])


if __name__ == "__main__":
    unittest.main()
