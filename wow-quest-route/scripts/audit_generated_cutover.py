from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import GeneratedArtifactError, read_generated_artifact
from lib.route_dependencies import build_all_profile_dependency_manifests
from lib.route_final_audit import (
    evaluate_profile_final_audit,
    evaluate_project_final_audit,
    load_cutover_blockers,
)
from lib.route_movement import program_member_movement_report
from lib.route_player_assets import evaluate_player_assets
from lib.route_profiles import load_all_route_profiles
from lib.route_programs import load_all_route_programs


REQUIRED_CUTOVER_PROFILE_IDS = [
    "hellfire-fivebox",
    "zangarmarsh-fivebox",
    "nagrand-fivebox-67-68",
    "borean-fivebox",
    "dragonblight-fivebox",
    "dalaran-mainline-77",
    "storm-peaks-fivebox",
    "icecrown-fivebox",
    "sholazar-fivebox",
    "zuldrak-fivebox",
    "grizzly-fivebox",
    "howling-fivebox",
    "hellfire-dk-speed",
    "zangarmarsh-dk-speed",
]


def _evaluation_status(value: Any, *, missing: str | None = None) -> str:
    if missing is not None:
        return "requirements"
    text = str(value or "")
    if text == "ok":
        return "pass"
    if text in {"pass", "requirements", "blocked"}:
        return text
    raise ValueError(f"invalid generated artifact status: {value!r}")


def _stage(
    name: str,
    evaluation_status: str,
    *,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "implementation_status": "implemented",
        "evaluation_status": evaluation_status,
        "detail": detail or {},
    }


def _optional_profile_artifact(profile_id: str, artifact_kind: str) -> dict[str, Any] | None:
    try:
        return read_generated_artifact(
            scope_kind="profiles",
            scope_id=profile_id,
            artifact_kind=artifact_kind,
        )
    except (FileNotFoundError, GeneratedArtifactError):
        return None


def _program_artifact(
    cache: dict[tuple[str, str], dict[str, Any]],
    program_id: str,
    artifact_kind: str,
) -> dict[str, Any]:
    key = (program_id, artifact_kind)
    if key not in cache:
        cache[key] = read_generated_artifact(
            scope_kind="programs",
            scope_id=program_id,
            artifact_kind=artifact_kind,
        )
    return cache[key]


def _program_member(
    report: dict[str, Any],
    profile_id: str,
) -> dict[str, Any] | None:
    value = (report.get("member_reports") or {}).get(profile_id)
    return value if isinstance(value, dict) else None


def _continuity_edge(
    report: dict[str, Any],
    profile_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            edge
            for edge in report.get("edges") or []
            if edge.get("to") == profile_id
        ),
        None,
    )


def main() -> None:
    profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
    discovered_ids = set(profiles)
    required_ids = set(REQUIRED_CUTOVER_PROFILE_IDS)
    if discovered_ids != required_ids:
        raise RuntimeError(
            "formal Route Profile set differs from explicit cutover contract; "
            f"missing={sorted(required_ids - discovered_ids)}, "
            f"extra={sorted(discovered_ids - required_ids)}"
        )

    programs = load_all_route_programs(validate=True, validate_profiles=True)
    profile_programs: dict[str, list[str]] = {profile_id: [] for profile_id in profiles}
    for program_id, program in programs.items():
        for profile_id in program["profile_ids"]:
            if profile_id in profile_programs:
                profile_programs[profile_id].append(program_id)
    multiply_owned = {
        profile_id: owners
        for profile_id, owners in profile_programs.items()
        if len(owners) > 1
    }
    if multiply_owned:
        raise RuntimeError(f"profiles belong to multiple Route Programs: {multiply_owned}")

    manifests = build_all_profile_dependency_manifests(profiles=profiles)
    program_cache: dict[tuple[str, str], dict[str, Any]] = {}
    profile_reports: list[dict[str, Any]] = []

    for profile_id in REQUIRED_CUTOVER_PROFILE_IDS:
        profile = profiles[profile_id]
        manifest = manifests[profile_id]
        owners = profile_programs[profile_id]
        program_id = owners[0] if owners else None

        if program_id is not None:
            continuity = _program_artifact(program_cache, program_id, "continuity")
            continuity_edge = _continuity_edge(continuity, profile_id)
            if continuity_edge is None:
                raise RuntimeError(
                    f"Program Continuity missing member edge for {profile_id}"
                )
            movement_program = _program_artifact(program_cache, program_id, "movement")
            movement = program_member_movement_report(movement_program, profile_id)
            service_program = _program_artifact(
                program_cache, program_id, "service-context"
            )
            service = _program_member(service_program, profile_id)
            if service is None:
                raise RuntimeError(f"Program Service Context missing {profile_id}")
            timing_program = _program_artifact(program_cache, program_id, "timing")
            timing = _program_member(timing_program, profile_id)
            if timing is None:
                raise RuntimeError(f"Program Timing missing {profile_id}")
            xp_program = _program_artifact(program_cache, program_id, "xp")
            xp = _program_member(xp_program, profile_id)
            economy_program = _program_artifact(program_cache, program_id, "economy")
            economy = _program_member(economy_program, profile_id)
            review = _program_artifact(program_cache, program_id, "review-trigger")

            replay_status = _evaluation_status(continuity_edge.get("status"))
            continuity_status = replay_status
            xp_status = (
                _evaluation_status(xp.get("status"))
                if xp is not None
                else _evaluation_status(
                    xp_program.get("status"),
                    missing="Program XP member result awaits explicit runtime entry state",
                )
            )
            economy_status = (
                _evaluation_status(economy.get("status"))
                if economy is not None
                else _evaluation_status(
                    economy_program.get("status"),
                    missing="Program Economy member result awaits XP/runtime inputs",
                )
            )
        else:
            replay = _optional_profile_artifact(profile_id, "replay")
            if replay is None:
                raise RuntimeError(f"standalone Replay baseline missing for {profile_id}")
            movement = _optional_profile_artifact(profile_id, "movement")
            service = _optional_profile_artifact(profile_id, "service-context")
            timing = _optional_profile_artifact(profile_id, "timing")
            if movement is None or service is None or timing is None:
                raise RuntimeError(
                    f"standalone static owner baseline incomplete for {profile_id}"
                )
            xp = _optional_profile_artifact(profile_id, "xp")
            economy = _optional_profile_artifact(profile_id, "economy")
            review = _optional_profile_artifact(profile_id, "review-trigger")
            if review is None:
                raise RuntimeError(f"standalone Review Trigger baseline missing for {profile_id}")
            replay_status = _evaluation_status(replay.get("status"))
            continuity_status = replay_status
            xp_status = (
                _evaluation_status(xp.get("status"))
                if xp is not None
                else "requirements"
            )
            economy_status = (
                _evaluation_status(economy.get("status"))
                if economy is not None
                else "requirements"
            )

        display = read_generated_artifact(
            scope_kind="profiles",
            scope_id=profile_id,
            artifact_kind="display",
        )
        publisher = read_generated_artifact(
            scope_kind="profiles",
            scope_id=profile_id,
            artifact_kind="publisher",
        )
        assets = evaluate_player_assets([publisher], routes_root=ROOT / "data/routes")

        stages = [
            _stage(
                "dependency_fingerprint",
                "pass",
                detail={"root_fingerprint": manifest["root_fingerprint"]},
            ),
            _stage(
                "profile_program_contract",
                "pass",
                detail={"program_id": program_id},
            ),
            _stage("availability_route_replay", replay_status),
            _stage("cross_profile_continuity", continuity_status),
            _stage(
                "canonical_spatial_movement",
                _evaluation_status(movement.get("status")),
            ),
            _stage(
                "service_context",
                _evaluation_status(service.get("status")),
            ),
            _stage(
                "derived_timing",
                _evaluation_status(timing.get("status")),
            ),
            _stage("derived_xp", xp_status),
            _stage("derived_economy", economy_status),
            _stage(
                "review_trigger",
                _evaluation_status(review.get("status")),
                detail={
                    "target_kind": review.get("kind"),
                    "target_id": review.get("target_id"),
                    "diagnoses": list(review.get("diagnoses") or []),
                    "input_fingerprint": review.get("input_fingerprint"),
                },
            ),
            _stage(
                "display_presentation",
                _evaluation_status(display.get("status")),
            ),
            _stage(
                "publisher_payload",
                _evaluation_status(publisher.get("status")),
            ),
            _stage(
                "html_player_view_assets",
                _evaluation_status(assets.get("status")),
            ),
        ]

        profile_reports.append(
            evaluate_profile_final_audit(
                profile_id=profile_id,
                profile_version=int(profile["version"]),
                root_fingerprint=manifest["root_fingerprint"],
                prerequisite_stages=stages,
                display_reports=[display],
                publisher_payloads=[publisher],
                player_assets_report=assets,
            )
        )

    project = evaluate_project_final_audit(
        profile_reports,
        required_profile_ids=REQUIRED_CUTOVER_PROFILE_IDS,
        cutover_blocker_ids=load_cutover_blockers(),
    )
    summary = {
        "project_status": project["status"],
        "cutover_status": project["cutover_status"],
        "cutover_ready": project["cutover_ready"],
        "open_cutover_blocker_ids": project["open_cutover_blocker_ids"],
        "cutover_issues": project["cutover_issues"],
        "profiles": {
            report["profile_id"]: {
                "status": report["status"],
                "cutover_status": report["cutover_status"],
                "cutover_publishable": report["cutover_publishable"],
                "error_count": sum(
                    1 for issue in report["issues"] if issue.get("severity") == "error"
                ),
                "requirement_count": sum(
                    1
                    for issue in report["issues"]
                    if issue.get("severity") in {"requirement", "unknown"}
                ),
            }
            for report in profile_reports
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
