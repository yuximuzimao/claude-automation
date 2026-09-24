from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data/routes/route-atlas-workbench.html"
html = path.read_text(encoding="utf-8")
scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
if len(scripts) != 1:
    raise SystemExit(f"expected one inline script, got {len(scripts)}")

with tempfile.TemporaryDirectory(prefix="route-atlas-js-") as tmp_dir:
    tmp = Path(tmp_dir) / "workbench-inline.js"
    tmp.write_text(scripts[0], encoding="utf-8")
    result = subprocess.run(
        ["node", "--check", str(tmp)],
        text=True,
        capture_output=True,
    )

print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)
