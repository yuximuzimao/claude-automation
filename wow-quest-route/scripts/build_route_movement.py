from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import write_generated_artifact
from lib.route_movement import evaluate_profile_movement
from lib.route_profiles import load_route_profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute only one Profile canonical Movement artifact."
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    payload = evaluate_profile_movement(profile)
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="movement",
        owner="route_movement",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
