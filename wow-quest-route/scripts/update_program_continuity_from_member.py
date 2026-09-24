from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_character_profile
from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_continuity import update_route_program_continuity_from_profile
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.task_cards import load_task_card


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute Program Continuity only from one changed member through the dependent suffix. "
            "Earlier Program edges are preserved exactly. Program order/version/entry changes require "
            "build_program_continuity.py instead."
        )
    )
    parser.add_argument("program_id")
    parser.add_argument("profile_id")
    parser.add_argument(
        "--changed-profile",
        action="append",
        default=[],
        help=(
            "Additional Program member changed in the same edit. "
            "Pass once per extra changed member so Continuity may stop as soon as state converges after the last changed member."
        ),
    )
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    if args.profile_id not in program["profile_ids"]:
        raise ValueError(f"{args.profile_id} is not a member of {args.program_id}")
    changed_profile_ids = {args.profile_id, *args.changed_profile}
    unknown_changed = sorted(changed_profile_ids - set(program["profile_ids"]))
    if unknown_changed:
        raise ValueError(f"changed profiles are not members of {args.program_id}: {unknown_changed}")
    earliest_changed = min(
        program["profile_ids"].index(profile_id) for profile_id in changed_profile_ids
    )
    if program["profile_ids"][earliest_changed] != args.profile_id:
        raise ValueError(
            "profile_id must be the earliest changed member; "
            f"earliest={program['profile_ids'][earliest_changed]}"
        )

    # Profiles are cheap structural truth. Task Card / Character replay inputs are loaded lazily
    # only if propagation actually reaches that member.
    profiles = {
        profile_id: load_route_profile(
            profile_id, validate=True, validate_task_cards=False
        )
        for profile_id in program["profile_ids"]
    }
    replay_inputs: dict[str, dict] = {}

    def load_replay_inputs(profile_id: str) -> dict:
        profile = profiles[profile_id]
        return {
            "task_cards": {
                int(task_id): load_task_card(int(task_id), validate=True)
                for task_id in profile["task_ids"]
            },
            "character_profile": load_character_profile(
                profile["scope"]["character_profile"], validate=True
            ),
        }

    current = read_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="continuity",
    )
    payload = update_route_program_continuity_from_profile(
        program,
        profiles,
        replay_inputs,
        current_report=current,
        start_profile_id=args.profile_id,
        changed_profile_ids=changed_profile_ids,
        replay_input_loader=load_replay_inputs,
    )
    path = write_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="continuity",
        owner="route_continuity",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
