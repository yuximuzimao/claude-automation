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
from lib.route_service_context import evaluate_route_program_service_context


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the initial/current Program Service Context from the existing Program Movement. "
            "This does not recompute Profile Movement."
        )
    )
    parser.add_argument("program_id")
    args = parser.parse_args()

    program = load_route_program(args.program_id, validate=True, validate_profiles=True)
    profiles = {
        profile_id: load_route_profile(profile_id, validate=True, validate_task_cards=False)
        for profile_id in program["profile_ids"]
    }
    movement = read_generated_artifact(
        scope_kind="programs", scope_id=args.program_id, artifact_kind="movement"
    )
    payload = evaluate_route_program_service_context(program, profiles, movement)
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
