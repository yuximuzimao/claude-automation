from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_economy import evaluate_profile_economy, load_economy_inputs
from lib.route_profiles import load_route_profile
from lib.task_cards import load_task_card


def _runtime(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Economy runtime input must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute only one Profile Economy/G-hour artifact. "
            "Requires current XP and Timing artifacts and never recomputes them."
        )
    )
    parser.add_argument("profile_id")
    parser.add_argument("--runtime-input", type=Path)
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    cards = {int(task_id): load_task_card(int(task_id), validate=True) for task_id in profile["task_ids"]}
    xp = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="xp"
    )
    timing = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="timing"
    )
    runtime = _runtime(args.runtime_input)
    inputs = load_economy_inputs()

    payload = evaluate_profile_economy(
        profile,
        task_cards=cards,
        xp_report=xp,
        timing_report=timing,
        cost_input=runtime.get("cost_input"),
        economy_observations=inputs["economy_observations"],
        market_valuations=inputs["market_valuations"],
        model_config=inputs["model_config"],
    )
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="economy",
        owner="route_economy",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
