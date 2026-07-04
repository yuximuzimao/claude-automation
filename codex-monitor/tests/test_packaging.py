from __future__ import annotations

import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.packaging import BUNDLE_IDENTIFIER, build_app_bundle, choose_python_executable


class PackagingTests(unittest.TestCase):
    def test_build_app_bundle_creates_info_plist_and_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            project_dir = output_dir / "codex-monitor"
            project_dir.mkdir()
            (project_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")

            bundle = build_app_bundle(
                output_dir=output_dir,
                project_dir=project_dir,
                python_executable="/usr/local/bin/python3.13",
            )

            self.assertEqual(bundle, output_dir / "Codex Monitor.app")
            info_path = bundle / "Contents" / "Info.plist"
            launcher_path = bundle / "Contents" / "MacOS" / "Codex Monitor"
            self.assertTrue(info_path.exists())
            self.assertTrue(launcher_path.exists())
            self.assertTrue(os.access(launcher_path, os.X_OK))
            plist = plistlib.loads(info_path.read_bytes())
            self.assertEqual(plist["CFBundleIdentifier"], BUNDLE_IDENTIFIER)
            self.assertFalse(plist.get("LSUIElement", False))
            launcher = launcher_path.read_text(encoding="utf-8")
            self.assertIn(f"cd {project_dir}", launcher)
            self.assertIn("AUTOSTART_WAS_RUNNING=0", launcher)
            self.assertIn('if launchctl print "gui/$(id -u)/com.local.codex-monitor"', launcher)
            self.assertIn("AUTOSTART_WAS_RUNNING=1", launcher)
            self.assertIn("restore_autostart()", launcher)
            self.assertIn("trap restore_autostart EXIT", launcher)
            self.assertIn('if [ "$AUTOSTART_WAS_RUNNING" = "1" ]; then', launcher)
            self.assertIn("launchctl bootstrap \"gui/$(id -u)\"", launcher)
            self.assertIn("launchctl bootout \"gui/$(id -u)/com.local.codex-monitor\"", launcher)
            self.assertIn("/usr/local/bin/python3.13 main.py --ui --visible-app", launcher)
            self.assertNotIn("exec /usr/local/bin/python3.13", launcher)

    def test_choose_python_executable_prefers_user_miniconda_python(self) -> None:
        def exists(path: Path) -> bool:
            return str(path) == "/Users/chat/miniconda3/bin/python3.13"

        with patch("app.packaging.Path.exists", exists):
            self.assertEqual(choose_python_executable(), "/Users/chat/miniconda3/bin/python3.13")


if __name__ == "__main__":
    unittest.main()
