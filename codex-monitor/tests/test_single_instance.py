from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_second_instance_cannot_acquire_same_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "codex-monitor.lock"
            with SingleInstance(lock_path) as first:
                self.assertTrue(first.acquired)
                with SingleInstance(lock_path) as second:
                    self.assertFalse(second.acquired)

    def test_releases_lock_when_context_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "codex-monitor.lock"
            with SingleInstance(lock_path) as first:
                self.assertTrue(first.acquired)

            with SingleInstance(lock_path) as second:
                self.assertTrue(second.acquired)

    def test_waits_for_lock_to_be_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "codex-monitor.lock"
            release = threading.Event()

            def hold_lock() -> None:
                with SingleInstance(lock_path) as first:
                    self.assertTrue(first.acquired)
                    release.wait(timeout=1)

            thread = threading.Thread(target=hold_lock)
            thread.start()
            time.sleep(0.05)

            acquired = []

            def acquire_second() -> None:
                with SingleInstance(lock_path, wait_seconds=1.0, poll_interval=0.01) as second:
                    acquired.append(second.acquired)

            second_thread = threading.Thread(target=acquire_second)
            second_thread.start()
            time.sleep(0.05)
            self.assertEqual(acquired, [])
            release.set()
            second_thread.join(timeout=1)
            thread.join(timeout=1)

            self.assertEqual(acquired, [True])

    def test_times_out_when_lock_is_not_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "codex-monitor.lock"
            with SingleInstance(lock_path) as first:
                self.assertTrue(first.acquired)
                with SingleInstance(lock_path, wait_seconds=0.02, poll_interval=0.01) as second:
                    self.assertFalse(second.acquired)


if __name__ == "__main__":
    unittest.main()
