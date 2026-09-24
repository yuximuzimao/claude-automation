from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_economy import evaluate_route_program_economy, load_economy_inputs
from lib.route_profiles import load_route_profile
from lib.route_programs import load_route_program
from lib.task_cards import load_task_card


def _runtime(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Program Economy runtime input must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the current Program Economy baseline from current Program XP/Timing artifacts. "
            "Optional runtime JSON may provide cost_input_by_profile."
        )
    )
    parser.add_argument("program_id")
    parser.add_argument("--runtime-input", type=Path)
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    xp = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="xp"
    )
    timing = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="timing"
    )
    runtime = _runtime(args.runtime_input)
    inputs = load_economy_inputs()

    if not (xp.get("member_reports") or {}):
        payload = evaluate_route_program_economy(
            program,
            {},
            task_cards_by_profile={},
            xp_report=xp,
            timing_report=timing,
            cost_input_by_profile=runtime.get("cost_input_by_profile"),
            economy_observations=inputs["economy_observations"],
            market_valuations=inputs["market_valuations"],
            model_config=inputs["model_config"],
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
        payload = evaluate_route_program_economy(
            program,
            profiles,
            task_cards_by_profile=cards,
            xp_report=xp,
            timing_report=timing,
            cost_input_by_profile=runtime.get("cost_input_by_profile"),
            economy_observations=inputs["economy_observations"],
            market_valuations=inputs["market_valuations"],
            model_config=inputs["model_config"],
        )
    path = write_generated_artifact(
        scope_kind="programs",
        scope_id=args.program_id,
        artifact_kind="economy",
        owner="route_economy",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
