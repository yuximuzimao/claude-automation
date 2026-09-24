from __future__ import annotations

from copy import deepcopy
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash, file_sha256


MOVEMENT_ACTION_KINDS = {"move", "taxi", "use_hearth", "fixed_transport", "quest_transport"}
SELF_MOVE_MODES = {"ride", "fly", "swim"}
LEGACY_SPECIAL_TRANSPORTS = {"script", "taxi", "hearth", "crossmap"}

PROFILE_SCHEMA = ROOT / "data/route-profiles/schema.json"
OPTIMIZATION_RULE = ROOT / "docs/rules/route-atlas-optimization.md"
LIFECYCLE_RULE = ROOT / "docs/rules/route-profile-and-lifecycle.md"
LIFECYCLE_SOP = ROOT / "docs/verified-routes/ROUTE-DESIGN-PROCESS.md"


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _result_status(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "blocked"
    if any(issue.get("severity") in {"unknown", "requirement"} for issue in issues):
        return "requirements"
    return "pass"


def movement_input_fingerprint(profile: dict[str, Any]) -> str:
    """Fingerprint only Stage-5-owned inputs plus the contracts that interpret them."""

    payload = {
        "profile_id": profile["profile_id"],
        "profile_version": profile["version"],
        "scope": profile["scope"],
        "actions": profile["actions"],
        "geometry": profile["geometry"],
        "contracts": {
            "route_profile_schema": file_sha256(PROFILE_SCHEMA),
            "route_optimization_rule": file_sha256(OPTIMIZATION_RULE),
            "route_lifecycle_rule": file_sha256(LIFECYCLE_RULE),
            "route_lifecycle_sop": file_sha256(LIFECYCLE_SOP),
        },
    }
    return canonical_json_hash(payload)


def _operation_kind(action: dict[str, Any]) -> str:
    kind = str(action["kind"])
    if kind == "use_hearth":
        return "hearth"
    return kind


def _movement_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [action for action in actions if action.get("kind") in MOVEMENT_ACTION_KINDS]


def _visit_row(
    *,
    action: dict[str, Any],
    ordinal: int,
    location: dict[str, Any],
    primary_zone_id: int | None,
) -> dict[str, Any]:
    zone_id = location.get("zone_id", primary_zone_id)
    return {
        "visit_id": str(action["action_id"]),
        "ordinal": ordinal,
        "location_ref": str(action["location_ref"]),
        "display_name": str(location["display_name"]),
        "location_role": str(location.get("location_role") or "map_anchor"),
        "zone_id": int(zone_id) if isinstance(zone_id, int) else None,
        "x": location["x"],
        "y": location["y"],
        "handoff_ref": location.get("handoff_ref"),
        "incoming_movement": location.get("incoming_movement"),
        "legacy_transport": location.get("transport"),
    }


def _action_projection(action: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "action_id": str(action["action_id"]),
        "action_kind": str(action["kind"]),
        "operation_kind": _operation_kind(action),
    }
    if action.get("kind") == "move":
        row["movement_mode"] = action.get("movement_mode")
    for key in ("from_name", "to_name", "target_name"):
        if action.get(key) is not None:
            row[key] = action[key]
    return row


def _edge_from_declared_incoming(
    *,
    source: dict[str, Any],
    target: dict[str, Any],
    segment_actions: list[dict[str, Any]],
    movement_actions: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    incoming = target["incoming_movement"]
    edge: dict[str, Any] = {
        "edge_id": f"{source['visit_id']}->{target['visit_id']}",
        "from_visit_id": source["visit_id"],
        "to_visit_id": target["visit_id"],
        "from_location_ref": source["location_ref"],
        "to_location_ref": target["location_ref"],
        "from_zone_id": source["zone_id"],
        "to_zone_id": target["zone_id"],
        "cross_zone": (
            source["zone_id"] != target["zone_id"]
            if source["zone_id"] is not None and target["zone_id"] is not None
            else None
        ),
        "source": "canonical_profile",
        "legacy_transport": target.get("legacy_transport"),
    }

    if incoming["kind"] == "self_move":
        if movement_actions:
            issues.append(
                _issue(
                    "error",
                    "self_move_edge_has_explicit_movement_action",
                    edge_id=edge["edge_id"],
                    movement_action_ids=[str(action["action_id"]) for action in movement_actions],
                )
            )
        edge.update(
            {
                "operation_kind": "self_move",
                "movement_mode": incoming.get("mode") or "ride",
                "movement_mode_source": "explicit" if incoming.get("mode") else "default_ground_mount",
            }
        )
        return edge

    action_id = str(incoming["action_id"])
    matches = [action for action in movement_actions if str(action["action_id"]) == action_id]
    if not matches:
        issues.append(
            _issue(
                "error",
                "incoming_movement_action_not_in_edge_segment",
                edge_id=edge["edge_id"],
                action_id=action_id,
                available_movement_action_ids=[str(action["action_id"]) for action in movement_actions],
            )
        )
        edge.update({"operation_kind": "unknown", "movement_action_id": action_id})
        return edge

    if len(movement_actions) > 1:
        issues.append(
            _issue(
                "error",
                "compound_movement_requires_visit_split",
                edge_id=edge["edge_id"],
                movement_action_ids=[str(action["action_id"]) for action in movement_actions],
            )
        )

    movement = matches[0]
    edge.update(
        {
            "operation_kind": _operation_kind(movement),
            "movement_action_id": action_id,
            "movement_action": _action_projection(movement),
        }
    )
    if movement["kind"] == "move":
        mode = movement.get("movement_mode") or "ride"
        edge["movement_mode"] = mode
        edge["movement_mode_source"] = "explicit" if movement.get("movement_mode") else "default_ground_mount"

    action_index = segment_actions.index(movement)
    trailing = [
        action
        for action in segment_actions[action_index + 1 :]
        if action.get("kind") not in {"location"}
    ]
    if trailing:
        issues.append(
            _issue(
                "unknown",
                "movement_action_not_terminal_before_next_visit",
                edge_id=edge["edge_id"],
                action_id=action_id,
                trailing_action_ids=[str(action["action_id"]) for action in trailing],
            )
        )
    return edge


def _edge_from_legacy_migration(
    *,
    source: dict[str, Any],
    target: dict[str, Any],
    segment_actions: list[dict[str, Any]],
    movement_actions: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    edge_id = f"{source['visit_id']}->{target['visit_id']}"
    edge: dict[str, Any] = {
        "edge_id": edge_id,
        "from_visit_id": source["visit_id"],
        "to_visit_id": target["visit_id"],
        "from_location_ref": source["location_ref"],
        "to_location_ref": target["location_ref"],
        "from_zone_id": source["zone_id"],
        "to_zone_id": target["zone_id"],
        "cross_zone": (
            source["zone_id"] != target["zone_id"]
            if source["zone_id"] is not None and target["zone_id"] is not None
            else None
        ),
        "source": "migration_candidate",
        "legacy_transport": target.get("legacy_transport"),
    }

    if len(movement_actions) > 1:
        issues.append(
            _issue(
                "error",
                "compound_movement_requires_visit_split",
                edge_id=edge_id,
                movement_action_ids=[str(action["action_id"]) for action in movement_actions],
            )
        )
        edge["operation_kind"] = "unknown"
        edge["candidate_movement_actions"] = [_action_projection(action) for action in movement_actions]
        return edge

    if len(movement_actions) == 1:
        movement = movement_actions[0]
        movement_index = segment_actions.index(movement)
        trailing = [
            action
            for action in segment_actions[movement_index + 1 :]
            if action.get("kind") != "location"
        ]
        if trailing:
            edge.update(
                {
                    "operation_kind": "unknown",
                    "candidate_movement_actions": [_action_projection(movement)],
                }
            )
            issues.append(
                _issue(
                    "unknown",
                    "movement_action_not_terminal_for_migration",
                    edge_id=edge_id,
                    action_id=str(movement["action_id"]),
                    trailing_action_ids=[str(action["action_id"]) for action in trailing],
                    reason=(
                        "a legacy segment movement action cannot become canonical incoming movement "
                        "while later actions still execute before the next visit"
                    ),
                )
            )
            return edge

        edge.update(
            {
                "operation_kind": _operation_kind(movement),
                "movement_action_id": str(movement["action_id"]),
                "movement_action": _action_projection(movement),
            }
        )
        candidate: dict[str, Any] = {"kind": "action", "action_id": str(movement["action_id"])}
        edge["migration_candidate"] = candidate
        issues.append(
            _issue(
                "unknown",
                "canonical_incoming_movement_missing",
                edge_id=edge_id,
                migration_candidate=candidate,
            )
        )
        if movement["kind"] == "move":
            mode = movement.get("movement_mode") or "ride"
            edge["movement_mode"] = mode
            edge["movement_mode_source"] = "explicit" if movement.get("movement_mode") else "default_ground_mount"
        return edge

    legacy = target.get("legacy_transport")
    if legacy in SELF_MOVE_MODES or legacy is None:
        mode = legacy if legacy in SELF_MOVE_MODES else "ride"
        edge.update(
            {
                "operation_kind": "self_move",
                "movement_mode": mode,
                "movement_mode_source": "legacy_hint" if legacy in SELF_MOVE_MODES else "default_ground_mount",
                "source": "default_autonomous_move",
            }
        )
        return edge

    edge["operation_kind"] = "unknown"
    if legacy in LEGACY_SPECIAL_TRANSPORTS:
        issues.append(
            _issue(
                "unknown",
                "legacy_transport_requires_operation_review",
                edge_id=edge_id,
                legacy_transport=legacy,
                reason="legacy line style cannot create a taxi/hearth/script/cross-zone player action",
            )
        )
    else:
        issues.append(
            _issue(
                "unknown",
                "movement_edge_unresolved",
                edge_id=edge_id,
                legacy_transport=legacy,
            )
        )
    return edge


def evaluate_profile_movement(profile: dict[str, Any]) -> dict[str, Any]:
    """Build the Stage-5 canonical visit/edge view without guessing route truth.

    Canonical `incoming_movement` wins when present. When an adjacent visit has no explicit
    movement action and no legacy special-transport evidence, it is ordinary autonomous movement
    and defaults to ground self-move; route business does not require ride/walk annotation.
    Legacy special transport and ambiguous explicit movement chains still require review.
    The function never mutates the Route Profile.
    """

    actions = list(profile["actions"])
    locations = profile["geometry"]["locations"]
    primary_zone_id = profile.get("scope", {}).get("primary_zone_id")
    if not isinstance(primary_zone_id, int):
        primary_zone_id = None

    issues: list[dict[str, Any]] = []
    location_positions = [index for index, action in enumerate(actions) if action.get("kind") == "location"]
    if not location_positions:
        issues.append(_issue("error", "profile_has_no_location_visits"))
        return {
            "profile_id": profile["profile_id"],
            "status": "blocked",
            "input_fingerprint": movement_input_fingerprint(profile),
            "visits": [],
            "edges": [],
            "exit_movement_actions": [],
            "issues": issues,
        }

    if location_positions[0] != 0:
        issues.append(
            _issue(
                "error",
                "actions_before_first_visit",
                action_ids=[str(action["action_id"]) for action in actions[: location_positions[0]]],
            )
        )

    visits: list[dict[str, Any]] = []
    refs: list[str] = []
    for ordinal, position in enumerate(location_positions, 1):
        action = actions[position]
        ref = str(action["location_ref"])
        refs.append(ref)
        location = locations[ref]
        visits.append(
            _visit_row(
                action=action,
                ordinal=ordinal,
                location=location,
                primary_zone_id=primary_zone_id,
            )
        )

    duplicate_refs = sorted({ref for ref in refs if refs.count(ref) > 1})
    if duplicate_refs:
        issues.append(
            _issue(
                "error",
                "location_ref_reused_across_visits",
                location_refs=duplicate_refs,
                reason="incoming_movement belongs to a visit occurrence, so reused refs are ambiguous",
            )
        )

    unused_locations = sorted(set(locations) - set(refs))
    if unused_locations:
        issues.append(_issue("error", "geometry_locations_without_visit", location_refs=unused_locations))

    missing_zone_visits = [visit["visit_id"] for visit in visits if visit["zone_id"] is None]
    if missing_zone_visits:
        issues.append(
            _issue(
                "unknown",
                "visit_zone_id_required",
                visit_ids=missing_zone_visits,
                reason="set scope.primary_zone_id and override only cross-zone visits",
            )
        )

    incomplete_coordinate_visits = [
        visit["visit_id"]
        for visit in visits
        if (visit.get("x") is None) != (visit.get("y") is None)
    ]
    if incomplete_coordinate_visits:
        issues.append(
            _issue(
                "error",
                "visit_coordinates_incomplete",
                visit_ids=incomplete_coordinate_visits,
                reason="x/y must either both be known or both be null",
            )
        )

    transition_context_with_coordinates = [
        visit["visit_id"]
        for visit in visits
        if visit.get("location_role") == "transition_context"
        and (visit.get("x") is not None or visit.get("y") is not None)
    ]
    if transition_context_with_coordinates:
        issues.append(
            _issue(
                "error",
                "transition_context_must_not_claim_map_coordinates",
                visit_ids=transition_context_with_coordinates,
                reason="transition_context preserves an execution/transport state, not a plotted route point",
            )
        )

    unknown_coordinate_visits = [
        visit["visit_id"]
        for visit in visits
        if visit.get("location_role") != "transition_context"
        and visit.get("x") is None
        and visit.get("y") is None
    ]
    if unknown_coordinate_visits:
        issues.append(
            _issue(
                "unknown",
                "location_coordinates_unknown",
                visit_ids=unknown_coordinate_visits,
                reason="map_anchor semantics are known but exact map coordinates are not yet evidenced",
            )
        )

    if visits[0].get("incoming_movement") is not None:
        issues.append(
            _issue(
                "error",
                "first_visit_must_not_have_incoming_movement",
                visit_id=visits[0]["visit_id"],
            )
        )

    edges: list[dict[str, Any]] = []
    for ordinal in range(len(visits) - 1):
        source = visits[ordinal]
        target = visits[ordinal + 1]
        start = location_positions[ordinal] + 1
        end = location_positions[ordinal + 1]
        segment_actions = actions[start:end]
        movement_actions = _movement_actions(segment_actions)
        if target.get("incoming_movement") is not None:
            edge = _edge_from_declared_incoming(
                source=source,
                target=target,
                segment_actions=segment_actions,
                movement_actions=movement_actions,
                issues=issues,
            )
        else:
            edge = _edge_from_legacy_migration(
                source=source,
                target=target,
                segment_actions=segment_actions,
                movement_actions=movement_actions,
                issues=issues,
            )
        edges.append(edge)

    last_position = location_positions[-1]
    trailing_actions = actions[last_position + 1 :]
    exit_movement_actions = _movement_actions(trailing_actions)
    if exit_movement_actions:
        issues.append(
            _issue(
                "unknown",
                "profile_exit_movement_requires_program_boundary",
                movement_action_ids=[str(action["action_id"]) for action in exit_movement_actions],
                reason="Stage 5 needs Route Program order to bind exit movement to the next Profile first visit",
            )
        )

    canonical_edge_count = sum(edge["source"] == "canonical_profile" for edge in edges)
    migration_candidate_count = sum(edge["source"] == "migration_candidate" for edge in edges)
    unresolved_edge_count = sum(edge.get("operation_kind") == "unknown" for edge in edges)

    return {
        "profile_id": profile["profile_id"],
        "status": _result_status(issues),
        "input_fingerprint": movement_input_fingerprint(profile),
        "primary_zone_id": primary_zone_id,
        "visits": visits,
        "edges": edges,
        "exit_movement_actions": [_action_projection(action) for action in exit_movement_actions],
        "canonical_edge_count": canonical_edge_count,
        "migration_candidate_count": migration_candidate_count,
        "unresolved_edge_count": unresolved_edge_count,
        "issues": issues,
    }


def program_movement_input_fingerprint(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> str:
    """Fingerprint Program order plus every member's Stage-5-owned inputs."""

    return canonical_json_hash(
        {
            "program_id": program["program_id"],
            "program_version": program["version"],
            "profile_ids": list(program["profile_ids"]),
            "boundary_transitions": program.get("boundary_transitions") or [],
            "member_stage5_fingerprints": {
                profile_id: movement_input_fingerprint(profiles[profile_id])
                for profile_id in program["profile_ids"]
            },
        }
    )


def _boundary_base(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    return {
        "edge_id": f"{source['profile_id']}->{target['profile_id']}",
        "from_profile_id": source["profile_id"],
        "to_profile_id": target["profile_id"],
        "from_visit_id": source["visits"][-1]["visit_id"],
        "to_visit_id": target["visits"][0]["visit_id"],
        "from_location_ref": source["visits"][-1]["location_ref"],
        "to_location_ref": target["visits"][0]["location_ref"],
        "from_zone_id": source["visits"][-1]["zone_id"],
        "to_zone_id": target["visits"][0]["zone_id"],
        "cross_zone": (
            source["visits"][-1]["zone_id"] != target["visits"][0]["zone_id"]
            if source["visits"][-1]["zone_id"] is not None
            and target["visits"][0]["zone_id"] is not None
            else None
        ),
    }


def evaluate_route_program_movement(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    member_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve Stage-5 movement across Profile boundaries without a second route layer.

    Internal visit/edge semantics are delegated to ``evaluate_profile_movement``. Program order may
    bind one explicit trailing movement action to the next Profile's first visit, or prove a zero-
    action natural handoff only when both endpoint visits share the same explicit ``handoff_ref``.
    Names, coordinates, page order and legacy transport styles never prove a boundary.
    """

    profile_ids = list(program["profile_ids"])
    if member_reports is None:
        member_reports = {
            profile_id: evaluate_profile_movement(profiles[profile_id])
            for profile_id in profile_ids
        }
    else:
        missing = [profile_id for profile_id in profile_ids if profile_id not in member_reports]
        extra = [profile_id for profile_id in member_reports if profile_id not in profile_ids]
        if missing or extra:
            raise RouteMovementError(
                f"Program member movement reports mismatch; missing={missing}, extra={extra}"
            )
    issues: list[dict[str, Any]] = []

    for index, profile_id in enumerate(profile_ids):
        report = member_reports[profile_id]
        for item in report["issues"]:
            if (
                item.get("kind") == "profile_exit_movement_requires_program_boundary"
                and index < len(profile_ids) - 1
            ):
                continue
            issues.append({**item, "profile_id": profile_id})

    transition_by_pair = {
        (str(row["from_profile_id"]), str(row["to_profile_id"])): row
        for row in program.get("boundary_transitions") or []
    }

    boundaries: list[dict[str, Any]] = []
    for index in range(len(profile_ids) - 1):
        source_id = profile_ids[index]
        target_id = profile_ids[index + 1]
        source = member_reports[source_id]
        target = member_reports[target_id]
        edge = _boundary_base(source, target)
        exit_actions = list(source["exit_movement_actions"])
        edge_issues: list[dict[str, Any]] = []

        transition = transition_by_pair.get((source_id, target_id))
        if transition is not None:
            normalized_operations: list[dict[str, Any]] = []
            if exit_actions:
                edge_issues.append(
                    _issue(
                        "error",
                        "program_boundary_transition_conflicts_with_profile_exit",
                        edge_id=edge["edge_id"],
                        movement_action_ids=[row["action_id"] for row in exit_actions],
                    )
                )
            source_handoff = source["visits"][-1].get("handoff_ref")
            target_handoff = target["visits"][0].get("handoff_ref")
            if source_handoff and source_handoff == target_handoff:
                edge_issues.append(
                    _issue(
                        "error",
                        "program_boundary_transition_conflicts_with_shared_handoff",
                        edge_id=edge["edge_id"],
                        handoff_ref=source_handoff,
                    )
                )

            previous_to: str | None = None
            for operation in transition["operations"]:
                kind = str(operation["kind"])
                operation_id = str(operation["operation_id"])
                from_name = str(operation["from_name"])
                to_name = str(operation["to_name"])
                normalized = {
                    "operation_id": operation_id,
                    "action_id": operation_id,
                    "action_kind": kind,
                    "operation_kind": "hearth" if kind == "use_hearth" else kind,
                    "from_name": from_name,
                    "to_name": to_name,
                }
                if kind == "move":
                    mode = operation.get("movement_mode")
                    normalized["movement_mode"] = mode
                    if mode not in SELF_MOVE_MODES:
                        edge_issues.append(
                            _issue(
                                "unknown",
                                "move_action_mode_required",
                                edge_id=edge["edge_id"],
                                action_id=operation_id,
                            )
                        )
                if previous_to is not None and from_name != previous_to:
                    edge_issues.append(
                        _issue(
                            "error",
                            "program_transition_operation_chain_discontinuous",
                            edge_id=edge["edge_id"],
                            operation_id=operation_id,
                            expected_from_name=previous_to,
                            actual_from_name=from_name,
                        )
                    )
                previous_to = to_name
                normalized_operations.append(normalized)

            edge.update(
                {
                    "source": "program_transition",
                    "operation_kind": "transition_chain",
                    "operations": normalized_operations,
                }
            )
        elif len(exit_actions) > 1:
            edge.update(
                {
                    "source": "profile_exit_actions",
                    "operation_kind": "unknown",
                    "candidate_movement_actions": exit_actions,
                }
            )
            edge_issues.append(
                _issue(
                    "error",
                    "compound_program_boundary_requires_visit_split",
                    edge_id=edge["edge_id"],
                    movement_action_ids=[row["action_id"] for row in exit_actions],
                )
            )
        elif len(exit_actions) == 1:
            movement = exit_actions[0]
            edge.update(
                {
                    "source": "profile_exit_action",
                    "operation_kind": movement["operation_kind"],
                    "movement_action_id": movement["action_id"],
                    "movement_action": movement,
                }
            )
            if movement["action_kind"] == "move":
                mode = movement.get("movement_mode")
                edge["movement_mode"] = mode
                if mode not in SELF_MOVE_MODES:
                    edge_issues.append(
                        _issue(
                            "unknown",
                            "move_action_mode_required",
                            edge_id=edge["edge_id"],
                            action_id=movement["action_id"],
                        )
                    )
        else:
            source_handoff = source["visits"][-1].get("handoff_ref")
            target_handoff = target["visits"][0].get("handoff_ref")
            if source_handoff and source_handoff == target_handoff:
                edge.update(
                    {
                        "source": "shared_handoff_ref",
                        "operation_kind": "handoff",
                        "handoff_ref": source_handoff,
                    }
                )
            else:
                edge.update({"source": "unproven", "operation_kind": "unknown"})
                edge_issues.append(
                    _issue(
                        "unknown",
                        "program_boundary_transition_unproven",
                        edge_id=edge["edge_id"],
                        from_handoff_ref=source_handoff,
                        to_handoff_ref=target_handoff,
                        reason=(
                            "Program order proves sequence only. Provide one explicit source Profile "
                            "exit movement action, matching endpoint handoff_ref values, or a reviewed "
                            "Program boundary_transitions operation chain."
                        ),
                    )
                )

        for item in edge_issues:
            item.setdefault("from_profile_id", source_id)
            item.setdefault("to_profile_id", target_id)
        issues.extend(edge_issues)
        edge["status"] = _result_status(edge_issues)
        edge["issues"] = edge_issues
        boundaries.append(edge)

    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "profile_ids": profile_ids,
        "status": _result_status(issues),
        "input_fingerprint": program_movement_input_fingerprint(program, profiles),
        "member_reports": member_reports,
        "boundaries": boundaries,
        "issues": issues,
    }


def program_member_movement_report(program_report: dict[str, Any], profile_id: str) -> dict[str, Any]:
    """Return the Stage-5 member view after Program boundary routing is applied.

    ``evaluate_profile_movement`` must report trailing movement as unresolved because a standalone
    Profile cannot know its next destination. Once Stage 5 has evaluated a Route Program, that
    particular uncertainty belongs to the Program boundary result and must not be re-emitted by
    Stage 6/7 as if the member Profile were still standalone. This helper removes only that routed
    duplicate; every other member movement issue remains unchanged.
    """

    members = program_report.get("member_reports") or {}
    if profile_id not in members:
        raise KeyError(f"Profile {profile_id!r} is not a member of Program movement report")

    report = deepcopy(members[profile_id])
    boundary = next(
        (
            row
            for row in program_report.get("boundaries") or []
            if row.get("from_profile_id") == profile_id
        ),
        None,
    )
    if boundary is None:
        return report

    report["issues"] = [
        row
        for row in report.get("issues") or []
        if row.get("kind") != "profile_exit_movement_requires_program_boundary"
    ]
    report["exit_movement_actions"] = []
    report["status"] = _result_status(report["issues"])
    report["program_context"] = {
        "program_id": program_report["program_id"],
        "boundary_edge_id": boundary["edge_id"],
        "boundary_status": boundary["status"],
    }
    report["input_fingerprint"] = canonical_json_hash(
        {
            "member_movement_input_fingerprint": members[profile_id]["input_fingerprint"],
            "program_movement_input_fingerprint": program_report["input_fingerprint"],
            "boundary_edge": boundary,
        }
    )
    return report


def build_movement_migration_review(profile: dict[str, Any]) -> dict[str, Any]:
    """Build a non-authoritative Stage-5 migration review manifest.

    The review is intentionally two-step: this function may suggest deterministic patches from the
    legacy representation, but it never upgrades migration evidence into route truth. Every patch is
    emitted with ``approved=False`` and can only be applied later against the exact same profile
    version/fingerprint.
    """

    report = evaluate_profile_movement(profile)
    patches: list[dict[str, Any]] = []

    if report["primary_zone_id"] is None:
        patches.append(
            {
                "patch_id": "primary-zone",
                "kind": "primary_zone_id",
                "status": "review_required",
                "approved": False,
                "zone_id": None,
                "reason": "primary zone must come from explicit route/map evidence; never infer it from title/image/name",
            }
        )

    actions = list(profile["actions"])
    action_index = {str(action["action_id"]): index for index, action in enumerate(actions)}
    exact_legacy_leading_action = {"hearth": "use_hearth", "taxi": "taxi"}

    edge_by_target_ref = {str(edge["to_location_ref"]): edge for edge in report["edges"]}
    edge_by_id = {str(edge["edge_id"]): edge for edge in report["edges"]}
    visit_index_by_ref = {
        str(visit["location_ref"]): index for index, visit in enumerate(report["visits"])
    }
    incoming_action_refs: dict[str, list[str]] = {}
    for location_ref, location in profile["geometry"]["locations"].items():
        incoming = location.get("incoming_movement")
        if isinstance(incoming, dict) and incoming.get("kind") == "action":
            action_id = str(incoming.get("action_id") or "")
            if action_id:
                incoming_action_refs.setdefault(action_id, []).append(str(location_ref))

    for action_id, refs in sorted(incoming_action_refs.items()):
        if len(refs) != 2 or action_id not in action_index:
            continue
        valid_refs: list[str] = []
        stale_refs: list[str] = []
        for location_ref in refs:
            edge = edge_by_target_ref.get(location_ref)
            if edge is None or str(edge.get("movement_action_id") or "") != action_id:
                continue
            if edge.get("operation_kind") == "unknown":
                stale_refs.append(location_ref)
            else:
                valid_refs.append(location_ref)
        if len(valid_refs) != 1 or len(stale_refs) != 1:
            continue
        keeper_ref = valid_refs[0]
        stale_ref = stale_refs[0]
        keeper_index = visit_index_by_ref.get(keeper_ref)
        stale_index = visit_index_by_ref.get(stale_ref)
        if keeper_index is None or stale_index != keeper_index + 1:
            continue
        patches.append(
            {
                "patch_id": f"remove-stale-duplicate:{action_id}:{stale_ref}",
                "kind": "remove_stale_duplicate_incoming",
                "status": "mechanical_candidate",
                "approved": False,
                "action_id": action_id,
                "keeper_location_ref": keeper_ref,
                "stale_location_ref": stale_ref,
                "value": {"kind": "action", "action_id": action_id},
                "basis": "same canonical action is valid on the immediately previous edge and invalid on this adjacent stale edge",
            }
        )

    for issue in report["issues"]:
        if issue.get("kind") != "movement_action_not_terminal_before_next_visit":
            continue
        edge = edge_by_id.get(str(issue.get("edge_id") or ""))
        action_id = str(issue.get("action_id") or "")
        if edge is None or not action_id:
            continue
        target_ref = str(edge["to_location_ref"])
        expected = {"kind": "action", "action_id": action_id}
        if profile["geometry"]["locations"][target_ref].get("incoming_movement") != expected:
            continue
        patches.append(
            {
                "patch_id": f"remove-nonterminal:{action_id}:{target_ref}",
                "kind": "remove_nonterminal_incoming_movement",
                "status": "mechanical_candidate",
                "approved": False,
                "action_id": action_id,
                "to_location_ref": target_ref,
                "value": expected,
                "edge_id": edge["edge_id"],
                "trailing_action_ids": list(issue.get("trailing_action_ids") or []),
                "basis": "canonical incoming action is proven non-terminal before the next visit",
            }
        )

    for edge in report["edges"]:
        candidate = edge.get("migration_candidate")
        if isinstance(candidate, dict):
            patches.append(
                {
                    "patch_id": f"incoming:{edge['to_location_ref']}",
                    "kind": "incoming_movement",
                    "status": "mechanical_candidate",
                    "approved": False,
                    "to_location_ref": edge["to_location_ref"],
                    "value": candidate,
                    "edge_id": edge["edge_id"],
                    "basis": (
                        edge.get("movement_action_id")
                        if candidate.get("kind") == "action"
                        else edge.get("legacy_transport")
                    ),
                }
            )

        legacy_transport = edge.get("legacy_transport")
        expected_kind = exact_legacy_leading_action.get(legacy_transport)
        if edge.get("operation_kind") == "unknown" and expected_kind is not None:
            target_visit_id = str(edge["to_visit_id"])
            target_location_ref = str(edge["to_location_ref"])
            target_location = profile["geometry"]["locations"][target_location_ref]
            target_index = action_index[target_visit_id]
            leading = actions[target_index + 1] if target_index + 1 < len(actions) else None
            if (
                target_location.get("incoming_movement") is None
                and isinstance(leading, dict)
                and leading.get("kind") == expected_kind
                and leading.get("location_ref") == target_location_ref
            ):
                patches.append(
                    {
                        "patch_id": f"reorder-leading:{leading['action_id']}",
                        "kind": "reorder_leading_movement",
                        "status": "mechanical_candidate",
                        "approved": False,
                        "action_id": str(leading["action_id"]),
                        "to_visit_id": target_visit_id,
                        "to_location_ref": str(edge["to_location_ref"]),
                        "legacy_transport": legacy_transport,
                        "value": {"kind": "action", "action_id": str(leading["action_id"])},
                        "edge_id": edge["edge_id"],
                        "basis": "existing matching movement action immediately follows legacy destination visit",
                    }
                )

        action = edge.get("movement_action")
        if (
            isinstance(action, dict)
            and action.get("action_kind") == "move"
            and action.get("movement_mode") not in SELF_MOVE_MODES
            and edge.get("legacy_transport") in SELF_MOVE_MODES
        ):
            patches.append(
                {
                    "patch_id": f"move-mode:{action['action_id']}",
                    "kind": "move_action_mode",
                    "status": "review_required",
                    "approved": False,
                    "action_id": action["action_id"],
                    "movement_mode": edge["legacy_transport"],
                    "edge_id": edge["edge_id"],
                    "basis": "legacy incoming transport is only migration evidence",
                }
            )

    for issue in report["issues"]:
        kind = issue.get("kind")
        if kind in {
            "compound_movement_requires_visit_split",
            "legacy_transport_requires_operation_review",
            "movement_edge_unresolved",
            "movement_action_not_terminal_for_migration",
            "profile_exit_movement_requires_program_boundary",
            "visit_zone_id_required",
        }:
            patches.append(
                {
                    "patch_id": f"review:{len(patches) + 1:04d}",
                    "kind": "manual_review",
                    "status": "review_required",
                    "approved": False,
                    "issue": deepcopy(issue),
                }
            )

    return {
        "schema": "route-movement-migration-review/v1",
        "profile_id": profile["profile_id"],
        "profile_version": profile["version"],
        "input_fingerprint": report["input_fingerprint"],
        "evaluation_status": report["status"],
        "patches": patches,
    }


def apply_approved_movement_review(
    profile: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    """Mechanically apply only explicitly approved Stage-5 migration patches.

    This function refuses stale reviews and never applies ``manual_review`` rows. The caller is
    responsible for persisting the returned profile and running the normal Route Profile validator.
    """

    if review.get("schema") != "route-movement-migration-review/v1":
        raise ValueError("unsupported movement migration review schema")
    if review.get("profile_id") != profile.get("profile_id"):
        raise ValueError("movement migration review profile_id mismatch")
    if review.get("profile_version") != profile.get("version"):
        raise ValueError("movement migration review profile version is stale")
    current_fingerprint = movement_input_fingerprint(profile)
    if review.get("input_fingerprint") != current_fingerprint:
        raise ValueError("movement migration review fingerprint is stale")

    result = deepcopy(profile)
    action_by_id = {str(action["action_id"]): action for action in result["actions"]}
    locations = result["geometry"]["locations"]

    for patch in review.get("patches") or []:
        if patch.get("approved") is not True:
            continue
        kind = patch.get("kind")
        if kind == "manual_review":
            raise ValueError(f"manual review patch cannot be auto-applied: {patch.get('patch_id')}")
        if kind == "primary_zone_id":
            zone_id = patch.get("zone_id")
            if not isinstance(zone_id, int) or zone_id < 1:
                raise ValueError("approved primary_zone_id patch requires a positive integer zone_id")
            existing = result["scope"].get("primary_zone_id")
            if existing is not None and existing != zone_id:
                raise ValueError("approved primary_zone_id conflicts with existing canonical value")
            result["scope"]["primary_zone_id"] = zone_id
            continue
        if kind == "incoming_movement":
            location_ref = str(patch.get("to_location_ref") or "")
            if location_ref not in locations:
                raise ValueError(f"unknown incoming movement location_ref: {location_ref}")
            value = patch.get("value")
            if not isinstance(value, dict):
                raise ValueError(f"incoming movement patch missing value: {patch.get('patch_id')}")
            existing = locations[location_ref].get("incoming_movement")
            if existing is not None and existing != value:
                raise ValueError(f"incoming movement conflicts with existing canonical value: {location_ref}")
            locations[location_ref]["incoming_movement"] = deepcopy(value)
            continue
        if kind == "remove_nonterminal_incoming_movement":
            action_id = str(patch.get("action_id") or "")
            location_ref = str(patch.get("to_location_ref") or "")
            expected = {"kind": "action", "action_id": action_id}
            if location_ref not in locations:
                raise ValueError(
                    f"nonterminal incoming cleanup references unknown location: {location_ref}"
                )
            if locations[location_ref].get("incoming_movement") != expected:
                raise ValueError(
                    f"nonterminal incoming cleanup no longer matches canonical value: {location_ref}"
                )
            del locations[location_ref]["incoming_movement"]
            continue
        if kind == "remove_stale_duplicate_incoming":
            action_id = str(patch.get("action_id") or "")
            keeper_ref = str(patch.get("keeper_location_ref") or "")
            stale_ref = str(patch.get("stale_location_ref") or "")
            expected = {"kind": "action", "action_id": action_id}
            if keeper_ref not in locations or stale_ref not in locations:
                raise ValueError("stale duplicate incoming patch references unknown location")
            if locations[keeper_ref].get("incoming_movement") != expected:
                raise ValueError(
                    f"stale duplicate keeper no longer references expected action: {keeper_ref}"
                )
            if locations[stale_ref].get("incoming_movement") != expected:
                raise ValueError(
                    f"stale duplicate location no longer references expected action: {stale_ref}"
                )
            refs = sorted(
                ref
                for ref, location in locations.items()
                if location.get("incoming_movement") == expected
            )
            if refs != sorted([keeper_ref, stale_ref]):
                raise ValueError(
                    f"stale duplicate incoming action has unexpected reference set: {action_id}"
                )
            del locations[stale_ref]["incoming_movement"]
            continue
        if kind == "move_action_mode":
            action_id = str(patch.get("action_id") or "")
            action = action_by_id.get(action_id)
            if action is None or action.get("kind") != "move":
                raise ValueError(f"move_action_mode patch references non-move action: {action_id}")
            mode = patch.get("movement_mode")
            if mode not in SELF_MOVE_MODES:
                raise ValueError(f"unsupported approved movement mode: {mode!r}")
            existing = action.get("movement_mode")
            if existing is not None and existing != mode:
                raise ValueError(f"move action mode conflicts with existing canonical value: {action_id}")
            action["movement_mode"] = mode
            continue
        if kind == "reorder_leading_movement":
            action_id = str(patch.get("action_id") or "")
            target_visit_id = str(patch.get("to_visit_id") or "")
            location_ref = str(patch.get("to_location_ref") or "")
            legacy_transport = patch.get("legacy_transport")
            expected_kind = {"hearth": "use_hearth", "taxi": "taxi"}.get(legacy_transport)
            if expected_kind is None:
                raise ValueError(f"unsupported leading movement legacy transport: {legacy_transport!r}")
            action = action_by_id.get(action_id)
            target = action_by_id.get(target_visit_id)
            if action is None or action.get("kind") != expected_kind:
                raise ValueError(f"leading movement patch references unexpected action: {action_id}")
            if target is None or target.get("kind") != "location" or target.get("location_ref") != location_ref:
                raise ValueError(f"leading movement patch references unexpected target visit: {target_visit_id}")
            if action.get("location_ref") != location_ref:
                raise ValueError(f"leading movement action location_ref mismatch: {action_id}")
            target_index = result["actions"].index(target)
            action_index = result["actions"].index(action)
            if action_index != target_index + 1:
                raise ValueError(f"leading movement action is no longer immediately after target visit: {action_id}")
            incoming = {"kind": "action", "action_id": action_id}
            existing = locations[location_ref].get("incoming_movement")
            if existing is not None:
                raise ValueError(
                    f"leading movement reorder requires empty target incoming_movement: {location_ref}"
                )

            next_location_action = next(
                (
                    row
                    for row in result["actions"][action_index + 1 :]
                    if row.get("kind") == "location"
                ),
                None,
            )
            next_location_ref = (
                str(next_location_action["location_ref"])
                if isinstance(next_location_action, dict)
                else None
            )
            existing_refs = sorted(
                ref
                for ref, location in locations.items()
                if location.get("incoming_movement") == incoming
            )
            allowed_refs = [next_location_ref] if next_location_ref else []
            if existing_refs not in ([], sorted(allowed_refs)):
                raise ValueError(
                    f"leading movement action has unexpected existing incoming references: {action_id}"
                )

            step_groups = result.get("step_groups") or []
            action_step = next(
                (step for step in step_groups if action_id in step.get("action_ids", [])),
                None,
            )
            target_step = next(
                (step for step in step_groups if target_visit_id in step.get("action_ids", [])),
                None,
            )
            if action_step is None or target_step is None:
                raise ValueError("leading movement reorder requires both actions in step_groups")
            if action_step is not target_step:
                raise ValueError(
                    f"leading movement reorder would cross step_groups: {action_id} -> {target_visit_id}"
                )
            step_action_ids = action_step["action_ids"]
            step_target_index = step_action_ids.index(target_visit_id)
            step_action_index = step_action_ids.index(action_id)
            if step_action_index != step_target_index + 1:
                raise ValueError(
                    f"leading movement step_groups order is no longer immediately after target visit: {action_id}"
                )

            result["actions"].pop(action_index)
            result["actions"].insert(target_index, action)
            step_action_ids.pop(step_action_index)
            step_action_ids.insert(step_target_index, action_id)
            if next_location_ref and locations[next_location_ref].get("incoming_movement") == incoming:
                del locations[next_location_ref]["incoming_movement"]
            locations[location_ref]["incoming_movement"] = incoming
            continue
        raise ValueError(f"unsupported approved movement patch kind: {kind!r}")

    return result
