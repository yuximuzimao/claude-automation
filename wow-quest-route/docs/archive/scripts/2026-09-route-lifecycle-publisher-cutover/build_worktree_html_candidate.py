from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact
from lib.route_player_assets import render_player_view, render_workbench_html


PROFILE_IDS = [
    "hellfire-fivebox",
    "zangarmarsh-fivebox",
    "nagrand-fivebox-67-68",
    "borean-fivebox",
    "dragonblight-fivebox",
    "dalaran-mainline-77",
    "storm-peaks-fivebox",
    "icecrown-fivebox",
    "sholazar-fivebox",
    "zuldrak-fivebox",
    "grizzly-fivebox",
    "howling-fivebox",
    "hellfire-dk-speed",
    "zangarmarsh-dk-speed",
]


def main() -> None:
    routes_dir = ROOT / "data/routes"
    payloads = [
        read_generated_artifact(
            scope_kind="profiles",
            scope_id=profile_id,
            artifact_kind="publisher",
        )
        for profile_id in PROFILE_IDS
    ]
    html = render_workbench_html(payloads)
    next_path = routes_dir / "route-atlas-workbench-next.html"
    next_path.write_text(html, encoding="utf-8")

    player_dir = routes_dir / "player-view-next"
    player_dir.mkdir(parents=True, exist_ok=True)
    for payload in payloads:
        key = str(payload["display"]["publish_key"])
        (player_dir / f"{key}.md").write_text(
            render_player_view(payload),
            encoding="utf-8",
        )

    print(json.dumps({
        "profile_count": len(payloads),
        "next_html": str(next_path),
        "player_view_dir": str(player_dir),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
