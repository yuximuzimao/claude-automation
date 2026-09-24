from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash, file_sha256
from .route_movement import evaluate_profile_movement, program_member_movement_report

PROFILE_SCHEMA = ROOT / "data/route-profiles/schema.json"
OPTIMIZATION_RULE = ROOT / "docs/rules/route-atlas-optimization.md"
LIFECYCLE_RULE = ROOT / "docs/rules/route-profile-and-lifecycle.md"
LIFECYCLE_SOP = ROOT / "docs/verified-routes/ROUTE-DESIGN-PROCESS.md"


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(row.get("severity") == "error" for row in issues):
        return "blocked"
    if any(row.get("severity") in {"unknown", "requirement"} for row in issues):
        return "requirements"
    return "pass"


def service_override_base_fingerprint(profile: dict[str, Any]) -> str:
    """Fingerprint the Profile state against which a reviewed service override proposal was made.

    Existing ``service_overrides`` are excluded so an approved review may replace that field, while
    every other Profile atom plus the interpreting contracts remains protected from stale application.
    """

    payload = deepcopy(profile)
    payload.pop("service_overrides", None)
    return canonical_json_hash(
        {
            "profile": payload,
            "contracts": {
                "route_profile_schema": file_sha256(PROFILE_SCHEMA),
                "route_optimization_rule": file_sha256(OPTIMIZATION_RULE),
                "route_lifecycle_rule": file_sha256(LIFECYCLE_RULE),
                "route_lifecycle_sop": file_sha256(LIFECYCLE_SOP),
            },
        }
    )


def build_service_override_review(
    profile: dict[str, Any],
    proposed_overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    """Package explicit human-reviewed candidates without inferring service semantics."""

    return {
        "schema": "route-service-override-review/v1",
        "profile_id": profile["profile_id"],
        "profile_version": profile["version"],
        "base_fingerprint": service_override_base_fingerprint(profile),
        "rows": [
            {
                "review_id": f"service:{index:04d}",
                "approved": False,
                "override": deepcopy(row),
            }
            for index, row in enumerate(proposed_overrides, start=1)
        ],
    }


def apply_approved_service_override_review(
    profile: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    """Apply only explicitly approved service rows against the exact reviewed Profile base."""

    if review.get("schema") != "route-service-override-review/v1":
        raise ValueError("unsupported service override review schema")
    if review.get("profile_id") != profile.get("profile_id"):
        raise ValueError("service override review profile_id mismatch")
    if review.get("profile_version") != profile.get("version"):
        raise ValueError("service override review profile version is stale")
    if review.get("base_fingerprint") != service_override_base_fingerprint(profile):
        raise ValueError("service override review base fingerprint is stale")

    result = deepcopy(profile)
    approved = [deepcopy(row["override"]) for row in review.get("rows") or [] if row.get("approved") is True]
    if approved:
        result["service_overrides"] = approved
    else:
        result.pop("service_overrides", None)
    return result


def service_context_input_fingerprint(
    profile: dict[str, Any],
    movement_report: dict[str, Any],
) -> str:
    """Fingerprint only Stage-6-owned inputs plus the Stage-5 spatial result it consumes."""

    return canonical_json_hash(
        {
            "profile_id": profile["profile_id"],
            "profile_version": profile["version"],
            "movement_input_fingerprint": movement_report["input_fingerprint"],
            "objective_actions": [
                {
                    "action_id": action["action_id"],
                    "task_id": action["task_id"],
                    "location_ref": action.get("location_ref"),
                }
                for action in profile["actions"]
                if action["kind"] == "objective"
            ],
            "service_overrides": profile.get("service_overrides") or [],
            "contracts": {
                "route_profile_schema": file_sha256(PROFILE_SCHEMA),
                "route_optimization_rule": file_sha256(OPTIMIZATION_RULE),
                "route_lifecycle_rule": file_sha256(LIFECYCLE_RULE),
                "route_lifecycle_sop": file_sha256(LIFECYCLE_SOP),
            },
        }
    )


def _action_visit_map(
    profile: dict[str, Any],
    movement_report: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Bind every action to the latest Stage-5 visit occurrence without inventing new space."""

    visit_by_id = {str(row["visit_id"]): row for row in movement_report["visits"]}
    action_to_visit: dict[str, str] = {}
    issues: list[dict[str, Any]] = []
    current_visit_id: str | None = None

    for action in profile["actions"]:
        action_id = str(action["action_id"])
        if action["kind"] == "location":
            current_visit_id = action_id
            if current_visit_id not in visit_by_id:
                issues.append(
                    _issue(
                        "error",
                        "location_action_missing_from_stage5_visits",
                        action_id=action_id,
                    )
                )
            action_to_visit[action_id] = current_visit_id
            continue
        if current_visit_id is not None:
            action_to_visit[action_id] = current_visit_id

    return action_to_visit, visit_by_id, issues


def evaluate_profile_service_context(
    profile: dict[str, Any],
    movement_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Stage 6 Service Context from Profile atoms and fresh Stage-5 visits.

    Stage 6 never parses Task Card guide text, player notes, old target-cluster JSON, or generated HTML.
    Every explicit ``objective`` action is a foreground service event.  Multi-action target sharing and
    background coverage exist only when Route Profile ``service_overrides`` explicitly preserve a
    route-only decision that cannot be reconstructed from the action/visit timeline.
    """

    if movement_report is None:
        movement_report = evaluate_profile_movement(profile)

    issues: list[dict[str, Any]] = []
    if movement_report["status"] == "blocked":
        issues.append(
            _issue(
                "error",
                "upstream_stage5_blocked",
                reason="Stage 6 cannot claim publishable spatial/service context while canonical movement is blocked",
            )
        )
    elif movement_report["status"] == "requirements":
        issues.append(
            _issue(
                "requirement",
                "upstream_stage5_requirements",
                reason="Stage 6 may derive service identity, but exact spatial/timing use remains gated by unresolved Stage 5 inputs",
            )
        )

    action_to_visit, visit_by_id, mapping_issues = _action_visit_map(profile, movement_report)
    issues.extend(mapping_issues)
    action_by_id = {str(action["action_id"]): action for action in profile["actions"]}
    action_ordinal = {str(action["action_id"]): index for index, action in enumerate(profile["actions"])}

    foreground_services: list[dict[str, Any]] = []
    service_by_action: dict[str, dict[str, Any]] = {}
    for action in profile["actions"]:
        if action["kind"] != "objective":
            continue
        action_id = str(action["action_id"])
        visit_id = action_to_visit.get(action_id)
        if visit_id is None:
            issues.append(
                _issue(
                    "error",
                    "objective_without_preceding_visit",
                    action_id=action_id,
                    task_id=int(action["task_id"]),
                )
            )
            continue
        visit = visit_by_id.get(visit_id)
        if visit is None:
            issues.append(
                _issue(
                    "error",
                    "objective_visit_missing_from_stage5",
                    action_id=action_id,
                    visit_id=visit_id,
                )
            )
            continue
        if action.get("location_ref") != visit["location_ref"]:
            issues.append(
                _issue(
                    "error",
                    "objective_location_disagrees_with_current_visit",
                    action_id=action_id,
                    action_location_ref=action.get("location_ref"),
                    visit_location_ref=visit["location_ref"],
                )
            )
        row = {
            "service_action_id": action_id,
            "task_id": int(action["task_id"]),
            "visit_id": visit_id,
            "location_ref": visit["location_ref"],
            "zone_id": visit.get("zone_id"),
            "x": visit.get("x"),
            "y": visit.get("y"),
        }
        foreground_services.append(row)
        service_by_action[action_id] = row

    shared_override_by_action: dict[str, str] = {}
    target_clusters: list[dict[str, Any]] = []
    background_layers: list[dict[str, Any]] = []

    for override in profile.get("service_overrides") or []:
        service_id = str(override["service_id"])
        if override["kind"] == "shared_service":
            rows = []
            for action_id in override["action_ids"]:
                row = service_by_action.get(str(action_id))
                if row is None:
                    issues.append(
                        _issue(
                            "error",
                            "shared_service_references_non_foreground_action",
                            service_id=service_id,
                            action_id=str(action_id),
                        )
                    )
                    continue
                if str(action_id) in shared_override_by_action:
                    issues.append(
                        _issue(
                            "error",
                            "foreground_action_in_multiple_shared_services",
                            action_id=str(action_id),
                            first_service_id=shared_override_by_action[str(action_id)],
                            second_service_id=service_id,
                        )
                    )
                shared_override_by_action[str(action_id)] = service_id
                rows.append(row)
            visit_ids = sorted({row["visit_id"] for row in rows})
            if len(visit_ids) > 1:
                issues.append(
                    _issue(
                        "error",
                        "shared_service_spans_multiple_visits",
                        service_id=service_id,
                        visit_ids=visit_ids,
                        reason="use a background_window for service sharing across a route range",
                    )
                )
            target_clusters.append(
                {
                    "cluster_id": service_id,
                    "source": "route_service_override",
                    "action_ids": [row["service_action_id"] for row in rows],
                    "task_ids": sorted({row["task_id"] for row in rows}),
                    "visit_ids": visit_ids,
                }
            )
            continue

        start_id = str(override["start_action_id"])
        end_id = str(override["end_action_id"])
        start_ordinal = action_ordinal[start_id]
        end_ordinal = action_ordinal[end_id]
        task_id = int(override["task_id"])
        window_objectives = [
            row
            for row in foreground_services
            if row["task_id"] == task_id
            and start_ordinal <= action_ordinal[row["service_action_id"]] <= end_ordinal
        ]
        visit_ids = [
            str(visit["visit_id"])
            for visit in movement_report["visits"]
            if start_ordinal <= action_ordinal.get(str(visit["visit_id"]), -1) <= end_ordinal
        ]
        background_layers.append(
            {
                "service_id": service_id,
                "task_id": task_id,
                "start_action_id": start_id,
                "end_action_id": end_id,
                "start_ordinal": start_ordinal,
                "end_ordinal": end_ordinal,
                "end_policy": override["end_policy"],
                "visit_ids": visit_ids,
                "foreground_objective_action_ids": [row["service_action_id"] for row in window_objectives],
            }
        )

    for row in foreground_services:
        action_id = row["service_action_id"]
        if action_id in shared_override_by_action:
            continue
        target_clusters.append(
            {
                "cluster_id": f"objective-{action_id}",
                "source": "objective_action",
                "action_ids": [action_id],
                "task_ids": [row["task_id"]],
                "visit_ids": [row["visit_id"]],
            }
        )

    clusters_by_visit: dict[str, list[str]] = defaultdict(list)
    for cluster in target_clusters:
        for visit_id in cluster["visit_ids"]:
            clusters_by_visit[visit_id].append(cluster["cluster_id"])

    spatial_instances: list[dict[str, Any]] = []
    for visit_id, cluster_ids in clusters_by_visit.items():
        visit = visit_by_id[visit_id]
        spatial_instances.append(
            {
                "instance_id": f"visit-{visit_id}",
                "basis": "canonical_visit_occurrence",
                "visit_id": visit_id,
                "location_ref": visit["location_ref"],
                "zone_id": visit.get("zone_id"),
                "x": visit.get("x"),
                "y": visit.get("y"),
                "cluster_ids": sorted(cluster_ids),
            }
        )

    return {
        "profile_id": profile["profile_id"],
        "status": _status(issues),
        "input_fingerprint": service_context_input_fingerprint(profile, movement_report),
        "foreground_services": foreground_services,
        "target_clusters": sorted(target_clusters, key=lambda row: row["cluster_id"]),
        "spatial_instances": sorted(spatial_instances, key=lambda row: row["visit_id"]),
        "background_layers": background_layers,
        "issues": issues,
        "summary": {
            "foreground_service_count": len(foreground_services),
            "target_cluster_count": len(target_clusters),
            "spatial_instance_count": len(spatial_instances),
            "background_layer_count": len(background_layers),
            "shared_service_override_count": sum(
                1 for row in (profile.get("service_overrides") or []) if row["kind"] == "shared_service"
            ),
        },
    }



def evaluate_route_program_member_service_context(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    program_movement_report: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    """Evaluate Service Context for exactly one Program member."""

    if profile_id not in program.get("profile_ids", []):
        raise ValueError(f"Profile {profile_id!r} is not a member of Program {program.get('program_id')!r}")
    movement = program_member_movement_report(program_movement_report, profile_id)
    return evaluate_profile_service_context(profiles[profile_id], movement)


def evaluate_route_program_service_context(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    program_movement_report: dict[str, Any],
    *,
    member_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate Program Service Context without forcing unrelated member recomputation."""

    profile_ids = list(program["profile_ids"])
    if member_reports is None:
        member_reports = {
            profile_id: evaluate_route_program_member_service_context(
                program,
                profiles,
                program_movement_report,
                profile_id,
            )
            for profile_id in profile_ids
        }
    else:
        missing = [profile_id for profile_id in profile_ids if profile_id not in member_reports]
        extra = [profile_id for profile_id in member_reports if profile_id not in profile_ids]
        if missing or extra:
            raise ValueError(
                f"Program member service reports mismatch; missing={missing}, extra={extra}"
            )

    issues: list[dict[str, Any]] = []
    for profile_id in profile_ids:
        status = member_reports[profile_id].get("status")
        if status == "blocked":
            issues.append(_issue("error", "member_service_context_blocked", profile_id=profile_id))
        elif status == "requirements":
            issues.append(
                _issue("requirement", "member_service_context_requirements", profile_id=profile_id)
            )
        elif status != "pass":
            issues.append(
                _issue(
                    "error",
                    "member_service_context_status_invalid",
                    profile_id=profile_id,
                    status=status,
                )
            )

    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "profile_ids": profile_ids,
        "status": _status(issues),
        "input_fingerprint": canonical_json_hash(
            {
                "program_id": program["program_id"],
                "program_version": program["version"],
                "program_movement_input_fingerprint": program_movement_report.get("input_fingerprint"),
                "member_service_input_fingerprints": {
                    profile_id: member_reports[profile_id].get("input_fingerprint")
                    for profile_id in profile_ids
                },
            }
        ),
        "member_reports": member_reports,
        "issues": issues,
    }
