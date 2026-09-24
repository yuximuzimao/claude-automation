from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .route_dependencies import canonical_json_hash
from .route_replay import (
    ReplayState,
    RouteReplay,
    replay_route_profile,
    replay_state_from_contract,
    replay_state_from_replay,
    replay_state_from_requirements,
)


CONTINUITY_DEFERRED_KINDS = {
    "once_task_entry_completion_unknown",
}


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _result_status(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "blocked"
    if issues:
        return "requirements"
    return "ok"


def _state_summary(state: ReplayState) -> dict[str, Any]:
    return {
        "active_task_ids": sorted(state.active_tasks),
        "maybe_active_task_ids": sorted(state.maybe_active_tasks),
        "active_tasks_known": state.active_tasks_known,
        "completed_task_ids": sorted(state.completed_tasks),
        "maybe_completed_task_ids": sorted(state.maybe_completed_tasks),
        "completed_tasks_known": state.completed_tasks_known,
        "hearth_location": state.hearth_location,
        "hearth_location_known": state.hearth_location_known,
        "opened_flight_points": sorted(state.opened_flight_points),
        "opened_flight_points_known": state.opened_flight_points_known,
    }




def _replay_state_from_summary(summary: dict[str, Any]) -> ReplayState:
    return ReplayState(
        active_tasks={int(value) for value in summary.get("active_task_ids", [])},
        maybe_active_tasks={int(value) for value in summary.get("maybe_active_task_ids", [])},
        active_tasks_known=bool(summary.get("active_tasks_known")),
        completed_tasks={int(value) for value in summary.get("completed_task_ids", [])},
        maybe_completed_tasks={int(value) for value in summary.get("maybe_completed_task_ids", [])},
        completed_tasks_known=bool(summary.get("completed_tasks_known")),
        hearth_location=summary.get("hearth_location"),
        hearth_location_known=bool(summary.get("hearth_location_known")),
        opened_flight_points={str(value) for value in summary.get("opened_flight_points", [])},
        opened_flight_points_known=bool(summary.get("opened_flight_points_known")),
    )


def route_program_continuity_member_input_fingerprint(
    profile: dict[str, Any],
    replay_input: dict[str, Any],
) -> str:
    return canonical_json_hash(
        {
            "profile_id": profile["profile_id"],
            "profile_version": profile.get("version"),
            "actions": profile["actions"],
            "entry_requirements": profile["entry_requirements"],
            "task_cards": replay_input.get("task_cards"),
            "character_profile": replay_input.get("character_profile"),
        }
    )


def _route_program_continuity_fingerprint_from_members(
    program: dict[str, Any],
    member_input_fingerprints: dict[str, str],
) -> str:
    return canonical_json_hash(
        {
            "program_id": program["program_id"],
            "program_version": program.get("version"),
            "profile_ids": program["profile_ids"],
            "entry_state_contract": program["entry_state_contract"],
            "member_input_fingerprints": member_input_fingerprints,
        }
    )


def route_program_continuity_input_fingerprint(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    replay_inputs: dict[str, dict[str, Any]],
) -> str:
    member_input_fingerprints = {
        profile_id: route_program_continuity_member_input_fingerprint(
            profiles[profile_id], replay_inputs.get(profile_id) or {}
        )
        for profile_id in program["profile_ids"]
    }
    return _route_program_continuity_fingerprint_from_members(
        program, member_input_fingerprints
    )


def _compare_entry_requirements(source: ReplayState, requirements: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the minimum requirements of one Profile against Program-supplied state.

    Requirements are lower bounds: extra carried tasks/completed tasks/flight points are valid
    and must keep flowing through the single Stage 3 replay engine.
    """

    issues: list[dict[str, Any]] = []

    required_active = {int(task_id) for task_id in requirements.get("active_task_ids", [])}
    missing_active = sorted(required_active - source.active_tasks - source.maybe_active_tasks)
    maybe_active = sorted(required_active & source.maybe_active_tasks)
    if missing_active:
        issues.append(
            _issue(
                "error" if source.active_tasks_known else "unknown",
                "required_active_tasks_missing" if source.active_tasks_known else "required_active_tasks_not_provable",
                task_ids=missing_active,
            )
        )
    if maybe_active:
        issues.append(
            _issue(
                "unknown",
                "required_active_tasks_only_maybe_proven",
                task_ids=maybe_active,
            )
        )

    required_completed = {int(task_id) for task_id in requirements.get("completed_task_ids", [])}
    missing_completed = sorted(required_completed - source.completed_tasks - source.maybe_completed_tasks)
    maybe_completed = sorted(required_completed & source.maybe_completed_tasks)
    if missing_completed:
        issues.append(
            _issue(
                "error" if source.completed_tasks_known else "unknown",
                "required_completed_tasks_missing" if source.completed_tasks_known else "required_completed_tasks_not_provable",
                task_ids=missing_completed,
            )
        )
    if maybe_completed:
        issues.append(
            _issue(
                "unknown",
                "required_completed_tasks_only_maybe_proven",
                task_ids=maybe_completed,
            )
        )

    if "hearth_location" in requirements:
        required_hearth = requirements.get("hearth_location")
        if not source.hearth_location_known:
            issues.append(
                _issue(
                    "unknown",
                    "required_hearth_not_provable",
                    required=required_hearth,
                )
            )
        elif source.hearth_location != required_hearth:
            issues.append(
                _issue(
                    "error",
                    "required_hearth_mismatch",
                    upstream=source.hearth_location,
                    required=required_hearth,
                )
            )

    required_flight = {str(name) for name in requirements.get("opened_flight_points", [])}
    missing_flight = sorted(required_flight - source.opened_flight_points)
    if missing_flight:
        issues.append(
            _issue(
                "error" if source.opened_flight_points_known else "unknown",
                "required_flight_points_missing" if source.opened_flight_points_known else "required_flight_points_not_provable",
                flight_points=missing_flight,
            )
        )

    return issues

def _continuity_requirements_from_replay(replay: RouteReplay) -> list[dict[str, Any]]:
    """Expose only Stage-4-owned UNKNOWNs without re-evaluating them.

    Availability/state logic already ran in Stage 3. Stage 4 merely carries forward
    the unresolved entry requirements that Stage 3 emitted. XP/reputation/skill and
    other model-owned deferred gates remain with their own later stages.
    """

    issues: list[dict[str, Any]] = []

    for item in replay.issues:
        if item.get("severity") != "requirement":
            continue
        issues.append({**item, "severity": "unknown"})

    for requirement in replay.external_state_requirements:
        issues.append(
            _issue(
                "unknown",
                "unresolved_external_state_requirement",
                requirement=requirement,
            )
        )

    if replay.required_entry_flight_points:
        issues.append(
            _issue(
                "unknown",
                "unresolved_entry_flight_points",
                flight_points=sorted(replay.required_entry_flight_points),
            )
        )

    for gate in replay.deferred_gates:
        if gate.get("kind") not in CONTINUITY_DEFERRED_KINDS:
            continue
        issues.append(
            _issue(
                "unknown",
                "unresolved_entry_task_state",
                gate=gate,
            )
        )

    return issues


def _hard_replay_issues(replay: RouteReplay) -> list[dict[str, Any]]:
    return [dict(issue) for issue in replay.issues if issue.get("severity") == "error"]


def evaluate_route_program_continuity(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    replay_inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate Program boundaries while delegating every RouteState transition to Stage 3.

    ``replay_inputs`` contains only the Task Cards and Character Profile needed by the
    Stage 3 evaluator for each member Profile. Stage 4 owns Program order and boundary
    contracts; it never owns a second task/hearth/flight transition implementation.
    """

    source = replay_state_from_contract(program["entry_state_contract"])
    source_id = f"program:{program['program_id']}"
    edges: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []

    for profile_id in program["profile_ids"]:
        profile = profiles[profile_id]
        inputs = replay_inputs.get(profile_id) or {}

        boundary_issues = _compare_entry_requirements(source, profile["entry_requirements"])
        replay = replay_route_profile(
            profile,
            task_cards=inputs.get("task_cards"),
            character_profile=inputs.get("character_profile"),
            entry_state=source,
        )
        edge_issues = boundary_issues + _hard_replay_issues(replay) + _continuity_requirements_from_replay(replay)

        for issue in edge_issues:
            issue.setdefault("from", source_id)
            issue.setdefault("to", profile_id)
        all_issues.extend(edge_issues)

        output_state = replay_state_from_replay(replay)
        edges.append(
            {
                "from": source_id,
                "to": profile_id,
                "status": _result_status(edge_issues),
                "issues": edge_issues,
                "upstream_state": _state_summary(source),
                "output_state": _state_summary(output_state),
                "action_execution": dict(sorted(replay.action_execution.items())),
                "deferred_gates": list(replay.deferred_gates),
                "stage3_hard_error_count": len(_hard_replay_issues(replay)),
                "stage4_requirement_count": len(_continuity_requirements_from_replay(replay)),
            }
        )
        source = output_state
        source_id = profile_id

    member_input_fingerprints = {
        profile_id: route_program_continuity_member_input_fingerprint(
            profiles[profile_id], replay_inputs.get(profile_id) or {}
        )
        for profile_id in program["profile_ids"]
    }
    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "program_version": program.get("version"),
        "entry_state_contract": deepcopy(program["entry_state_contract"]),
        "profile_ids": list(program["profile_ids"]),
        "status": _result_status(all_issues),
        "issues": all_issues,
        "edges": edges,
        "final_state": _state_summary(source),
        "member_input_fingerprints": member_input_fingerprints,
        "input_fingerprint": _route_program_continuity_fingerprint_from_members(
            program, member_input_fingerprints
        ),
    }



def update_route_program_continuity_from_profile(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    replay_inputs: dict[str, dict[str, Any]],
    *,
    current_report: dict[str, Any],
    start_profile_id: str,
    changed_profile_ids: set[str] | None = None,
    replay_input_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-run Program Continuity only from one changed member through the dependent suffix."""

    profile_ids = list(program["profile_ids"])
    if start_profile_id not in profile_ids:
        raise ValueError(
            f"Profile {start_profile_id!r} is not a member of Program {program['program_id']!r}"
        )
    if current_report.get("program_id") != program["program_id"]:
        raise ValueError("current Program Continuity artifact belongs to a different Program")
    if current_report.get("profile_ids") != profile_ids:
        raise ValueError(
            "Program profile order changed; rebuild Program Continuity from the Program start"
        )
    if current_report.get("program_version") != program.get("version"):
        raise ValueError(
            "Program version changed; rebuild Program Continuity from the Program start"
        )
    if current_report.get("entry_state_contract") != program["entry_state_contract"]:
        raise ValueError(
            "Program entry_state_contract changed; rebuild Program Continuity from the Program start"
        )

    start_index = profile_ids.index(start_profile_id)
    changed_ids = set(changed_profile_ids or {start_profile_id})
    unknown_changed = sorted(changed_ids - set(profile_ids))
    if unknown_changed:
        raise ValueError(f"changed profiles are not Program members: {unknown_changed}")
    changed_before_start = [
        profile_id for profile_id in profile_ids[:start_index] if profile_id in changed_ids
    ]
    if changed_before_start:
        raise ValueError(
            f"start_profile_id must be the earliest changed member; earlier changes={changed_before_start}"
        )
    current_edges = list(current_report.get("edges") or [])
    if len(current_edges) != len(profile_ids):
        raise ValueError(
            "current Program Continuity edge count does not match Program membership; rebuild full Continuity"
        )
    for index, profile_id in enumerate(profile_ids):
        if current_edges[index].get("to") != profile_id:
            raise ValueError(
                "current Program Continuity edge order does not match Program membership; rebuild full Continuity"
            )

    current_member_fingerprints = current_report.get("member_input_fingerprints")
    if not isinstance(current_member_fingerprints, dict):
        raise ValueError(
            "current Program Continuity artifact predates member fingerprints; rebuild full Continuity once"
        )

    edges = deepcopy(current_edges[:start_index])
    all_issues: list[dict[str, Any]] = []
    for edge in edges:
        all_issues.extend(deepcopy(edge.get("issues") or []))

    if start_index == 0:
        source = replay_state_from_contract(program["entry_state_contract"])
        source_id = f"program:{program['program_id']}"
    else:
        previous_edge = edges[-1]
        output_state = previous_edge.get("output_state")
        if not isinstance(output_state, dict):
            raise ValueError(
                "current Program Continuity prefix lacks output_state; rebuild full Continuity"
            )
        source = _replay_state_from_summary(output_state)
        source_id = profile_ids[start_index - 1]

    member_input_fingerprints = deepcopy(current_member_fingerprints)
    for profile_id in profile_ids[start_index:]:
        profile = profiles[profile_id]
        inputs = replay_inputs.get(profile_id)
        if not isinstance(inputs, dict) and replay_input_loader is not None:
            inputs = replay_input_loader(profile_id)
            replay_inputs[profile_id] = inputs
        if not isinstance(inputs, dict):
            raise ValueError(
                f"incremental Program Continuity missing replay inputs for {profile_id}"
            )

        boundary_issues = _compare_entry_requirements(
            source, profile["entry_requirements"]
        )
        replay = replay_route_profile(
            profile,
            task_cards=inputs.get("task_cards"),
            character_profile=inputs.get("character_profile"),
            entry_state=source,
        )
        hard_issues = _hard_replay_issues(replay)
        continuity_requirements = _continuity_requirements_from_replay(replay)
        edge_issues = boundary_issues + hard_issues + continuity_requirements

        for issue in edge_issues:
            issue.setdefault("from", source_id)
            issue.setdefault("to", profile_id)
        all_issues.extend(edge_issues)

        output_state = replay_state_from_replay(replay)
        edges.append(
            {
                "from": source_id,
                "to": profile_id,
                "status": _result_status(edge_issues),
                "issues": edge_issues,
                "upstream_state": _state_summary(source),
                "output_state": _state_summary(output_state),
                "action_execution": dict(sorted(replay.action_execution.items())),
                "deferred_gates": list(replay.deferred_gates),
                "stage3_hard_error_count": len(hard_issues),
                "stage4_requirement_count": len(continuity_requirements),
            }
        )
        member_input_fingerprints[profile_id] = (
            route_program_continuity_member_input_fingerprint(profile, inputs)
        )
        source = output_state
        source_id = profile_id

        index = profile_ids.index(profile_id)
        current_output_state = current_edges[index].get("output_state")
        if _state_summary(output_state) == current_output_state:
            later_changed = any(
                downstream_profile_id in changed_ids
                for downstream_profile_id in profile_ids[index + 1 :]
            )
            if not later_changed:
                reused_edges = deepcopy(current_edges[index + 1 :])
                edges.extend(reused_edges)
                for edge in reused_edges:
                    all_issues.extend(deepcopy(edge.get("issues") or []))
                if reused_edges:
                    final_summary = reused_edges[-1].get("output_state")
                    if not isinstance(final_summary, dict):
                        raise ValueError(
                            "current Program Continuity suffix lacks output_state; cannot reuse suffix"
                        )
                    source = _replay_state_from_summary(final_summary)
                break

    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "program_version": program.get("version"),
        "entry_state_contract": deepcopy(program["entry_state_contract"]),
        "profile_ids": profile_ids,
        "status": _result_status(all_issues),
        "issues": all_issues,
        "edges": edges,
        "final_state": _state_summary(source),
        "member_input_fingerprints": member_input_fingerprints,
        "input_fingerprint": _route_program_continuity_fingerprint_from_members(
            program, member_input_fingerprints
        ),
    }


def evaluate_standalone_continuity(
    profile: dict[str, Any],
    replay: RouteReplay,
) -> dict[str, Any]:
    """Classify a standalone Stage 3 replay without implementing any state transition."""

    issues = _hard_replay_issues(replay) + _continuity_requirements_from_replay(replay)
    minimum_entry_state = replay_state_from_requirements(profile["entry_requirements"])
    final_state = replay_state_from_replay(replay)
    return {
        "kind": "standalone",
        "profile_id": profile["profile_id"],
        "status": _result_status(issues),
        "issues": issues,
        "entry_requirements_state": _state_summary(minimum_entry_state),
        "final_state": _state_summary(final_state),
    }
