from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_character_profile
from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_timing import evaluate_profile_timing
from lib.task_cards import load_task_card


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute only one Profile Timing artifact. "
            "Requires current Replay/Movement/Service artifacts and never recomputes them."
        )
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    cards = {int(task_id): load_task_card(int(task_id), validate=True) for task_id in profile["task_ids"]}
    character_profile = load_character_profile(profile["scope"]["character_profile"], validate=True)

    replay = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="replay"
    )
    movement = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="movement"
    )
    service = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="service-context"
    )

    payload = evaluate_profile_timing(
        profile,
        task_cards=cards,
        movement_report=movement,
        service_report=service,
        character_profile=character_profile,
        action_execution=dict(replay.get("action_execution") or {}),
    )
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="timing",
        owner="route_timing",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
