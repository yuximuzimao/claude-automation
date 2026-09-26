from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact
from lib.route_player_assets import write_player_assets


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Purely render HTML/player-view from current generated Publisher payloads. "
            "This command never runs route business calculations."
        )
    )
    parser.add_argument("profile_ids", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    payloads = [
        read_generated_artifact(
            scope_kind="profiles", scope_id=profile_id, artifact_kind="publisher"
        )
        for profile_id in args.profile_ids
    ]
    report = write_player_assets(payloads, output_dir=args.output_dir)
    summary = {key: value for key, value in report.items() if key != "player_views"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
