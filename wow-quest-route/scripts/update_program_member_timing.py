from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_character_profile
from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.route_timing import (
    evaluate_route_program_member_timing,
    evaluate_route_program_timing,
)
from lib.task_cards import load_task_card


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute Timing for exactly one Program member and re-aggregate Program totals "
            "without recalculating other member Timing reports."
        )
    )
    parser.add_argument("program_id")
    parser.add_argument("profile_id")
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    if args.profile_id not in program["profile_ids"]:
        raise ValueError(f"{args.profile_id} is not a member of {args.program_id}")
    profiles = {
        profile_id: load_route_profile(profile_id, validate=True, validate_task_cards=False)
        for profile_id in program["profile_ids"]
    }
    profile = profiles[args.profile_id]
    cards = {
        int(task_id): load_task_card(int(task_id), validate=True)
        for task_id in profile["task_ids"]
    }
    character_profile = load_character_profile(
        profile["scope"]["character_profile"], validate=True
    )

    continuity = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="continuity"
    )
    movement = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="movement"
    )
    service = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="service-context"
    )
    current = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="timing"
    )

    members = deepcopy(current.get("member_reports") or {})
    members[args.profile_id] = evaluate_route_program_member_timing(
        program,
        args.profile_id,
        profile,
        task_cards=cards,
        character_profile=character_profile,
        program_movement_report=movement,
        program_service_report=service,
        continuity_report=continuity,
    )
    payload = evaluate_route_program_timing(
        program,
        profiles,
        task_cards_by_profile={},
        character_profiles_by_profile={},
        program_movement_report=movement,
        continuity_report=continuity,
        program_service_report=service,
        member_reports=members,
    )
    path = write_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="timing",
        owner="route_timing",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
