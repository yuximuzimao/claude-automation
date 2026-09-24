from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_display import project_route_display
from lib.route_movement import program_member_movement_report
from lib.route_profiles import load_route_profile
from lib.route_programs import load_all_route_programs
from lib.task_cards import load_task_card


def _program_id_for_profile(profile_id: str) -> str | None:
    matches = [
        program_id
        for program_id, program in load_all_route_programs(
            validate=True, validate_profiles=True
        ).items()
        if profile_id in program["profile_ids"]
    ]
    if len(matches) > 1:
        raise ValueError(f"Profile {profile_id} belongs to multiple active Route Programs: {matches}")
    return matches[0] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild one full Route Display from current Profile truth plus existing Movement/Timing "
            "artifacts. Does not recompute Replay/Program/Movement/Service/Timing/XP/Economy."
        )
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    cards = {
        int(task_id): load_task_card(int(task_id), validate=True)
        for task_id in profile["task_ids"]
    }
    program_id = _program_id_for_profile(args.profile_id)
    if program_id is None:
        movement = read_generated_artifact(
            scope_kind="profiles", scope_id=args.profile_id, artifact_kind="movement"
        )
        timing = read_generated_artifact(
            scope_kind="profiles", scope_id=args.profile_id, artifact_kind="timing"
        )
    else:
        program_movement = read_generated_artifact(
            scope_kind="programs", scope_id=program_id, artifact_kind="movement"
        )
        movement = program_member_movement_report(program_movement, args.profile_id)
        program_timing = read_generated_artifact(
            scope_kind="programs", scope_id=program_id, artifact_kind="timing"
        )
        timing = (program_timing.get("member_reports") or {}).get(args.profile_id)
        if not isinstance(timing, dict):
            raise ValueError(
                f"Program Timing {program_id} has no member report for {args.profile_id}"
            )

    payload = project_route_display(
        profile,
        cards=cards,
        movement_report=movement,
        timing_report=timing,
        upstream_statuses={
            "canonical_spatial_movement": str(movement.get("status") or "blocked"),
            "derived_timing": str(timing.get("status") or "blocked"),
        },
        upstream_fingerprints={
            "movement": movement.get("input_fingerprint"),
            "timing": timing.get("input_fingerprint"),
        },
    )
    if program_id is not None:
        payload["program_id"] = program_id

    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="display",
        owner="route_display",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
