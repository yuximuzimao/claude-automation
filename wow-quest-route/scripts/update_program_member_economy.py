from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_economy import (
    evaluate_route_program_economy,
    evaluate_route_program_member_economy,
    load_economy_inputs,
)
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
            "Recompute Economy for exactly one Program member and re-aggregate Program totals. "
            "All other member Economy reports are preserved."
        )
    )
    parser.add_argument("program_id")
    parser.add_argument("profile_id")
    parser.add_argument("--runtime-input", type=Path)
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
    xp = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="xp"
    )
    timing = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="timing"
    )
    current = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="economy"
    )
    runtime = _runtime(args.runtime_input)
    cost_inputs = (
        runtime["cost_input_by_profile"]
        if "cost_input_by_profile" in runtime
        else (current.get("cost_input_by_profile") or {})
    )
    inputs = load_economy_inputs()
    members = deepcopy(current.get("member_reports") or {})
    members[args.profile_id] = evaluate_route_program_member_economy(
        program,
        args.profile_id,
        profile,
        task_cards=cards,
        xp_report=xp,
        timing_report=timing,
        cost_input=cost_inputs.get(args.profile_id),
        economy_observations=inputs["economy_observations"],
        market_valuations=inputs["market_valuations"],
        model_config=inputs["model_config"],
    )
    payload = evaluate_route_program_economy(
        program,
        profiles,
        task_cards_by_profile={},
        xp_report=xp,
        timing_report=timing,
        cost_input_by_profile=cost_inputs,
        economy_observations=inputs["economy_observations"],
        market_valuations=inputs["market_valuations"],
        model_config=inputs["model_config"],
        member_reports=members,
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
