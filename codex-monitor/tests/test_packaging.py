from __future__ import annotations

import os
import plistlib
import tempfile
import unittest
from pathlib import Path

from app.packaging import BUNDLE_IDENTIFIER, build_app_bundle


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
            launcher = launcher_path.read_text(encoding="utf-8")
            self.assertIn(f"cd {project_dir}", launcher)
            self.assertIn("exec /usr/local/bin/python3.13 main.py --ui", launcher)


if __name__ == "__main__":
    unittest.main()
