from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

from app.autostart import (
    LAUNCH_AGENT_LABEL,
    build_launch_agent_plist,
    install_launch_agent,
    launch_agent_path,
    launchctl_bootstrap_command,
    uninstall_launch_agent,
)


class AutostartTests(unittest.TestCase):
    def test_build_launch_agent_plist_uses_safe_macos_log_paths(self) -> None:
        home = Path("/Users/chat")
        project_dir = Path("/Users/chat/claude/codex-monitor")

        plist = plistlib.loads(
            build_launch_agent_plist(
                home=home,
                project_dir=project_dir,
                python_executable="/usr/local/bin/python3.13",
            )
        )

        self.assertEqual(plist["Label"], LAUNCH_AGENT_LABEL)
        self.assertEqual(
            plist["ProgramArguments"],
            ["/usr/local/bin/python3.13", str(project_dir / "main.py"), "--ui"],
        )
        self.assertTrue(plist["RunAtLoad"])
        self.assertFalse(plist["KeepAlive"])
        self.assertEqual(
            plist["StandardOutPath"],
            "/Users/chat/Library/Logs/Codex Monitor/stdout.log",
        )
        self.assertEqual(
            plist["StandardErrorPath"],
            "/Users/chat/Library/Logs/Codex Monitor/stderr.log",
        )

    def test_install_launch_agent_writes_plist_without_running_launchctl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            project_dir = home / "codex-monitor"
            project_dir.mkdir()

            path = install_launch_agent(
                home=home,
                project_dir=project_dir,
                python_executable="python3.13",
            )

            self.assertEqual(path, launch_agent_path(home))
            self.assertTrue(path.exists())
            plist = plistlib.loads(path.read_bytes())
            self.assertEqual(plist["Label"], LAUNCH_AGENT_LABEL)
            self.assertIn(str(path), launchctl_bootstrap_command(path, uid=501))

    def test_uninstall_launch_agent_removes_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            path = launch_agent_path(home)
            path.parent.mkdir(parents=True)
            path.write_text("placeholder", encoding="utf-8")

            self.assertTrue(uninstall_launch_agent(home=home))
            self.assertFalse(path.exists())
            self.assertFalse(uninstall_launch_agent(home=home))


if __name__ == "__main__":
    unittest.main()
