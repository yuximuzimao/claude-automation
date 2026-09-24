from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.route_service_context import (
    evaluate_route_program_member_service_context,
    evaluate_route_program_service_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute Service Context for exactly one Program member, then re-aggregate Program "
            "Service status without recalculating the other members."
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
    movement = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="movement"
    )
    current = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="service-context"
    )
    members = deepcopy(current.get("member_reports") or {})
    members[args.profile_id] = evaluate_route_program_member_service_context(
        program,
        profiles,
        movement,
        args.profile_id,
    )
    payload = evaluate_route_program_service_context(
        program,
        profiles,
        movement,
        member_reports=members,
    )
    path = write_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="service-context",
        owner="route_service_context",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
