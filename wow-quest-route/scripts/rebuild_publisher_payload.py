from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_publisher_payload import build_publisher_payload, load_route_ui_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild one Route Publisher payload from the current generated Route Display. "
            "Does not reload or reinterpret Route Profile/Task Cards/business models."
        )
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    display = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="display"
    )
    route_ui = load_route_ui_config(args.profile_id)
    payload = build_publisher_payload(display, route_ui=route_ui)
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="publisher",
        owner="route_publisher_payload",
        payload=payload,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "publishable": payload["publishable"],
                "path": str(path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
