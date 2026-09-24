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
    raise RuntimeError(
        "RETIRED: the legacy Dalaran workbench builder is disabled; edit the Route Profile "
        "and publish through scripts/rebuild_route_profile.py"
    )
