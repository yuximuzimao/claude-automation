from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_service_context import evaluate_profile_service_context


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute only one Profile Service Context artifact. "
            "Requires the current Movement artifact and never recomputes Movement."
        )
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    movement = read_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="movement",
    )
    payload = evaluate_profile_service_context(profile, movement_report=movement)
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="service-context",
        owner="route_service_context",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
