"""Offline tests for the deadline used by capture and publication."""
import datetime as dt
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app.run_analysis import AnalysisRunner
from src.app.runtime_deadline import Deadline, DeadlineExceeded, run_bounded


class RuntimeDeadlineTests(unittest.TestCase):
    def test_clock_rollback_cannot_extend_deadline(self):
        wall = [100.0]
        monotonic = [10.0]
        deadline = Deadline('1970-01-01T00:01:50+00:00', now=lambda: wall[0],
                            monotonic=lambda: monotonic[0])
        wall[0] = 50.0
        monotonic[0] = 20.0
        with self.assertRaises(DeadlineExceeded):
            deadline.check()

    def test_deadline_kills_child_group_and_preserves_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'escaped'
            pending = root / 'pending.json'
            script = root / 'worker.py'
            grandchild = f"import time,pathlib;time.sleep(1.2);pathlib.Path({str(marker)!r}).write_text('bad')"
            script.write_text(
                "import subprocess, sys, time, pathlib\n"
                "pathlib.Path(sys.argv[1]).write_text('pending scroll')\n"
                f"subprocess.Popen([sys.executable, '-c', {grandchild!r}])\n"
                "time.sleep(30)\n"
            )
            end = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=0.4)).isoformat()
            with self.assertRaises(DeadlineExceeded):
                run_bounded([sys.executable, str(script), str(pending)], deadline=Deadline(end),
                            cwd=root, log=root / 'log')
            self.assertEqual(pending.read_text(), 'pending scroll')
            time.sleep(1.3)
            self.assertFalse(marker.exists())

    def test_expired_publish_never_moves_pointer(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {'GCA_DEADLINE_UTC': '2000-01-01T00:00:00+00:00'}
        ):
            runner = AnalysisRunner(Path(directory))
            with self.assertRaises(DeadlineExceeded):
                runner._publish_release('not-created')
            self.assertFalse(runner.current_link.exists())
