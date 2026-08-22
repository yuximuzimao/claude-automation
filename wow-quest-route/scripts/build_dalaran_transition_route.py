from __future__ import annotations

"""Deprecated compatibility entry point.

The old transition-only Dalaran draft was superseded on 2026-08-22 by the formal
77-level Dalaran foundation + route. Keep this filename only so an old command
cannot resurrect stale Dragonblight/Grizzly transport assumptions.
"""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE = ROOT / "scripts/build_dalaran_route.py"

if __name__ == "__main__":
    print("DEPRECATED: forwarding to scripts/build_dalaran_route.py")
    runpy.run_path(str(AUTHORITATIVE), run_name="__main__")
