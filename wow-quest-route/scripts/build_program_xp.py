from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.route_xp import evaluate_route_program_xp
from lib.task_cards import load_task_card


def _runtime(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Program XP runtime input must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the current Program XP baseline. Runtime JSON may provide entry_state and "
            "external_xp_upper_bound_by_profile. Missing entry_state remains requirements."
        )
    )
    parser.add_argument("program_id")
    parser.add_argument("--runtime-input", type=Path)
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    continuity = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="continuity"
    )
    runtime = _runtime(args.runtime_input)
    entry_state = runtime.get("entry_state")
    external_upper = runtime.get("external_xp_upper_bound_by_profile")

    if entry_state is None:
        payload = evaluate_route_program_xp(
            program,
            {},
            task_cards_by_profile={},
            continuity_report=continuity,
            entry_state=None,
            external_xp_upper_bound_by_profile=external_upper,
        )
    else:
        profiles = {
            profile_id: load_route_profile(profile_id, validate=True, validate_task_cards=False)
            for profile_id in program["profile_ids"]
        }
        cards = {
            profile_id: {
                int(task_id): load_task_card(int(task_id), validate=True)
                for task_id in profile["task_ids"]
            }
            for profile_id, profile in profiles.items()
        }
        payload = evaluate_route_program_xp(
            program,
            profiles,
            task_cards_by_profile=cards,
            continuity_report=continuity,
            entry_state=entry_state,
            external_xp_upper_bound_by_profile=external_upper,
        )
    path = write_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="xp",
        owner="route_xp",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
