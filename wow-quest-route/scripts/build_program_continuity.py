from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_character_profile
from lib.generated_artifacts import write_generated_artifact
from lib.route_continuity import evaluate_route_program_continuity
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.task_cards import load_task_card


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute one full Route Program Continuity baseline only. "
            "Use this when Program order/version/entry contract changes or when no incremental "
            "baseline exists. It does not run Movement/Service/Timing/XP/Economy/Display/Publisher."
        )
    )
    parser.add_argument("program_id")
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    profiles = {
        profile_id: load_route_profile(
            profile_id, validate=True, validate_task_cards=False
        )
        for profile_id in program["profile_ids"]
    }
    replay_inputs: dict[str, dict] = {}
    for profile_id, profile in profiles.items():
        cards = {
            int(task_id): load_task_card(int(task_id), validate=True)
            for task_id in profile["task_ids"]
        }
        replay_inputs[profile_id] = {
            "task_cards": cards,
            "character_profile": load_character_profile(
                profile["scope"]["character_profile"], validate=True
            ),
        }

    payload = evaluate_route_program_continuity(program, profiles, replay_inputs)
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
