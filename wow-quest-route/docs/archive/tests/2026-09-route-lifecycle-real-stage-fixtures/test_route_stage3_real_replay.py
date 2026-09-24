from __future__ import annotations

import copy

from lib.route_dependencies import build_profile_dependency_manifest
from scripts.rebuild_route_profile import _stage3_input_fingerprint, audit_profile


# Stage 3 migration acceptance fixture. These expectations describe evaluator behavior,
# not a promise that every upstream Task Card fact is already conflict-free. Formal route
# data must never be edited merely to make this fixture pass.
def test_stage3_frozen_real_hellfire_dk_replay_expected_outcome() -> None:
    report = audit_profile("hellfire-dk-speed")
    stage3 = report["stages"][2]
    replay = report["route_replay"]

    assert stage3["name"] == "availability_route_replay"
    assert stage3["implementation_status"] == "implemented"
    assert stage3["evaluation_status"] == "requirements"
    assert stage3["publish_gate_applies"] is True
    assert stage3["detail"]["character_profile_id"] == "dk-twohand-blood-current"
    assert stage3["detail"]["availability_event_count"] == 59
    assert stage3["detail"]["accept_action_count"] == 59
    assert stage3["detail"]["hard_errors"] == []
    assert len(stage3["detail"]["input_fingerprint"]) == 64
    assert stage3["detail"]["quest_log_peak_upper_bound"] is None

    # A reusable Profile only declares minimum entry requirements. Without a Program/CURRENT
    # actual entry task log, Stage 3 must preserve the active-task set and quest-log peak as UNKNOWN.
    assert replay["task_state"]["entry_active_state_known"] is False
    assert replay["quest_log"]["entry_state_known"] is False
    assert any(issue["kind"] == "actual_entry_active_tasks_required" for issue in replay["issues"])

    # The cold-start input also omits completed_task_ids. Stage 3 must preserve that as
    # UNKNOWN instead of silently treating it as an empty completed-task set.
    assert replay["task_state"]["entry_completed_state_known"] is False
    assert replay["hearth"]["entry_state_known"] is False
    assert replay["hearth"]["final_state_known"] is True

    # XP/level ownership is Stage 8. Stage 3 may discover the gate but must not calculate
    # or guess a level result itself.
    min_level_checks = [
        check
        for event in replay["availability"]["events"]
        for check in event["checks"]
        if check["kind"] == "min_level"
    ]
    assert min_level_checks
    assert all(check["status"] == "deferred" for check in min_level_checks)
    assert all(check["resolver"] == "derived_xp" for check in min_level_checks)

    # Current DK Character Profile is Orc; the independently verified 9498 branch must
    # therefore be evaluated against Orc identity rather than a route-name heuristic.
    falcon = next(event for event in replay["availability"]["events"] if event["task_id"] == 9498)
    assert any(
        check["kind"] == "race" and check["status"] == "pass" and check["value"] == "orc"
        for check in falcon["checks"]
    )


def test_stage3_fingerprint_changes_only_for_stage3_consumed_sections() -> None:
    manifest = build_profile_dependency_manifest("hellfire-dk-speed")
    baseline = _stage3_input_fingerprint(manifest)

    presentation_only = copy.deepcopy(manifest)
    presentation_only["task_cards"]["9498"]["sections"]["presentation"] = "presentation-changed"
    assert _stage3_input_fingerprint(presentation_only) == baseline

    availability_changed = copy.deepcopy(manifest)
    availability_changed["task_cards"]["9498"]["sections"]["availability"] = "availability-changed"
    assert _stage3_input_fingerprint(availability_changed) != baseline

    action_changed = copy.deepcopy(manifest)
    action_changed["profile"]["sections"]["actions"] = "actions-changed"
    assert _stage3_input_fingerprint(action_changed) != baseline
