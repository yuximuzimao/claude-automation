from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_programs import load_all_route_programs, load_route_program
from lib.route_review_trigger import evaluate_review_trigger, load_review_trigger_config


def _review_input(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Review Trigger input must be a JSON object")
    return payload


def _status(report: dict[str, Any]) -> str:
    value = str(report.get("status") or "")
    if value == "ok":
        return "pass"
    if value in {"pass", "requirements", "blocked"}:
        return value
    raise ValueError(f"invalid upstream artifact status: {value!r}")


def _program_upstreams(program_id: str) -> dict[str, str]:
    return {
        "cross_profile_continuity": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="continuity"
            )
        ),
        "canonical_spatial_movement": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="movement"
            )
        ),
        "service_context": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="service-context"
            )
        ),
        "derived_timing": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="timing"
            )
        ),
        "derived_xp": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="xp"
            )
        ),
        "derived_economy": _status(
            read_generated_artifact(
                scope_kind="programs", scope_id=program_id, artifact_kind="economy"
            )
        ),
    }


def _profile_upstreams(profile_id: str) -> dict[str, str]:
    replay = read_generated_artifact(
        scope_kind="profiles", scope_id=profile_id, artifact_kind="replay"
    )
    replay_status = _status(replay)
    return {
        "availability_route_replay": replay_status,
        # Standalone Stage 4 only classifies the already-built Replay; it does not
        # own a second persisted state-transition artifact.
        "cross_profile_continuity": replay_status,
        "canonical_spatial_movement": _status(
            read_generated_artifact(
                scope_kind="profiles", scope_id=profile_id, artifact_kind="movement"
            )
        ),
        "service_context": _status(
            read_generated_artifact(
                scope_kind="profiles", scope_id=profile_id, artifact_kind="service-context"
            )
        ),
        "derived_timing": _status(
            read_generated_artifact(
                scope_kind="profiles", scope_id=profile_id, artifact_kind="timing"
            )
        ),
        "derived_xp": _status(
            read_generated_artifact(
                scope_kind="profiles", scope_id=profile_id, artifact_kind="xp"
            )
        ),
        "derived_economy": _status(
            read_generated_artifact(
                scope_kind="profiles", scope_id=profile_id, artifact_kind="economy"
            )
        ),
    }


def build_review_trigger(
    target_kind: str,
    target_id: str,
    *,
    review_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_review_trigger_config()
    if target_kind == "program":
        target = load_route_program(target_id, validate=True, validate_profiles=True)
        payload = evaluate_review_trigger(
            target_kind="program",
            target_id=target_id,
            target_version=int(target["version"]),
            upstream_statuses=_program_upstreams(target_id),
            review_input=review_input,
            model_config=config,
        )
        payload["program_id"] = target_id
        return payload

    if target_kind != "profile":
        raise ValueError("target_kind must be profile or program")

    profile = load_route_profile(target_id, validate=True, validate_task_cards=False)
    program_ids = [
        program_id
        for program_id, program in load_all_route_programs(
            validate=True, validate_profiles=True
        ).items()
        if target_id in program["profile_ids"]
    ]
    if program_ids:
        raise ValueError(
            f"Profile {target_id} belongs to Route Program(s) {program_ids}; "
            "build the Program Review Trigger instead"
        )
    payload = evaluate_review_trigger(
        target_kind="profile",
        target_id=target_id,
        target_version=int(profile["version"]),
        upstream_statuses=_profile_upstreams(target_id),
        review_input=review_input,
        model_config=config,
    )
    payload["profile_id"] = target_id
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize only Stage 10 Review Trigger from current generated Stage 3/4-9 "
            "artifacts plus optional version-bound review context. Never recomputes upstream owners."
        )
    )
    parser.add_argument("target_kind", choices=("profile", "program"))
    parser.add_argument("target_id")
    parser.add_argument("--review-input", type=Path)
    args = parser.parse_args()

    payload = build_review_trigger(
        args.target_kind,
        args.target_id,
        review_input=_review_input(args.review_input),
    )
    scope_kind = "programs" if args.target_kind == "program" else "profiles"
    path = write_generated_artifact(
        scope_kind=scope_kind,
        scope_id=args.target_id,
        artifact_kind="review-trigger",
        owner="route_review_trigger",
        payload=payload,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "diagnoses": payload["diagnoses"],
                "path": str(path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
