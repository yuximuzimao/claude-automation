from __future__ import annotations

from copy import deepcopy

import lib.route_continuity as route_continuity
from lib.route_continuity import (
    evaluate_route_program_continuity,
    evaluate_standalone_continuity,
    update_route_program_continuity_from_profile,
)
from lib.route_replay import RouteReplay


def _profile(
    profile_id: str,
    actions=(),
    *,
    entry_active=(),
    entry_extra=None,
) -> dict:
    entry = {"active_task_ids": list(entry_active)}
    if entry_extra:
        entry.update(entry_extra)
    return {
        "profile_id": profile_id,
        "entry_requirements": entry,
        "actions": list(actions),
    }


def _program(profile_ids, *, entry_active=(), entry_extra=None) -> dict:
    entry = {"active_task_ids": list(entry_active)}
    if entry_extra:
        entry.update(entry_extra)
    return {
        "program_id": "program",
        "entry_state_contract": entry,
        "profile_ids": list(profile_ids),
    }


def test_program_continuity_uses_single_replay_engine_to_propagate_task_state() -> None:
    profiles = {
        "a": _profile(
            "a",
            [
                {"action_id": "a1", "kind": "accept", "task_id": 1},
                {"action_id": "t1", "kind": "turnin", "task_id": 1},
                {"action_id": "a10", "kind": "accept", "task_id": 10},
            ],
        ),
        "b": _profile(
            "b",
            [{"action_id": "t10", "kind": "turnin", "task_id": 10}],
            entry_active=(10,),
        ),
    }

    result = evaluate_route_program_continuity(
        _program(["a", "b"], entry_extra={"completed_task_ids": []}),
        profiles,
        {"a": {}, "b": {}},
    )

    assert result["status"] == "ok"
    assert [edge["status"] for edge in result["edges"]] == ["ok", "ok"]
    assert result["final_state"]["active_task_ids"] == []
    assert result["final_state"]["completed_task_ids"] == [1, 10]
    assert result["final_state"]["completed_tasks_known"] is True


def test_program_continuity_rejects_declared_active_handoff_mismatch() -> None:
    profiles = {
        "a": _profile(
            "a",
            [{"action_id": "a10", "kind": "accept", "task_id": 10}],
        ),
        "b": _profile("b", entry_active=(11,)),
    }

    result = evaluate_route_program_continuity(
        _program(["a", "b"]), profiles, {"a": {}, "b": {}}
    )

    assert result["status"] == "blocked"
    second_edge = result["edges"][1]
    assert any(issue["kind"] == "required_active_tasks_missing" for issue in second_edge["issues"])


def test_program_continuity_preserves_unknown_as_requirement_not_hard_failure() -> None:
    profiles = {
        "a": _profile("a", entry_extra={"completed_task_ids": [99]}),
    }

    result = evaluate_route_program_continuity(
        _program(["a"]), profiles, {"a": {}}
    )

    assert result["status"] == "requirements"
    assert any(
        issue["kind"] == "required_completed_tasks_not_provable"
        for issue in result["issues"]
    )


def test_program_continuity_passes_hearth_and_flight_state_back_into_replay() -> None:
    profiles = {
        "a": _profile(
            "a",
            [
                {"action_id": "h1", "kind": "bind_hearth", "target_name": "萨尔玛"},
                {"action_id": "f1", "kind": "open_flight_point", "target_name": "萨尔玛"},
                {"action_id": "f2", "kind": "open_flight_point", "target_name": "赞加入口"},
            ],
        ),
        "b": _profile(
            "b",
            [
                {"action_id": "h2", "kind": "use_hearth", "target_name": "萨尔玛"},
                {"action_id": "t2", "kind": "taxi", "from_name": "萨尔玛", "to_name": "赞加入口"},
            ],
            entry_extra={
                "hearth_location": "萨尔玛",
                "opened_flight_points": ["萨尔玛", "赞加入口"],
            },
        ),
    }

    result = evaluate_route_program_continuity(
        _program(
            ["a", "b"],
            entry_extra={
                "completed_task_ids": [],
                "hearth_location": None,
                "opened_flight_points": [],
            },
        ),
        profiles,
        {"a": {}, "b": {}},
    )

    assert result["status"] == "ok"
    assert result["final_state"]["hearth_location"] == "萨尔玛"
    assert result["final_state"]["opened_flight_points"] == ["萨尔玛", "赞加入口"]
    assert result["final_state"]["opened_flight_points_known"] is True


def test_program_context_derives_exit_state_from_actions_without_second_contract() -> None:
    profiles = {
        "a": _profile(
            "a",
            [{"action_id": "a10", "kind": "accept", "task_id": 10}],
        ),
    }

    result = evaluate_route_program_continuity(
        _program(["a"]), profiles, {"a": {}}
    )

    assert result["status"] == "ok"
    assert result["final_state"]["active_task_ids"] == [10]


def test_standalone_continuity_preserves_unresolved_entry_requirement_without_hard_failure() -> None:
    profile = _profile("standalone")
    replay = RouteReplay(
        profile_id="standalone",
        external_state_requirements=[
            {
                "action_id": "a1",
                "task_id": 2,
                "kind": "completed_task",
                "required_task_id": 99,
                "relation": "pre_all",
            }
        ],
    )

    result = evaluate_standalone_continuity(profile, replay)

    assert result["status"] == "requirements"
    assert any(issue["kind"] == "unresolved_external_state_requirement" for issue in result["issues"])


def test_incremental_program_continuity_stops_when_output_state_converges(monkeypatch) -> None:
    baseline_profiles = {
        "a": _profile(
            "a",
            [
                {"action_id": "a10", "kind": "accept", "task_id": 10},
                {"action_id": "t10", "kind": "turnin", "task_id": 10},
            ],
        ),
        "b": _profile(
            "b",
            [{"action_id": "a20", "kind": "accept", "task_id": 20}],
        ),
        "c": _profile(
            "c",
            [{"action_id": "t20", "kind": "turnin", "task_id": 20}],
            entry_active=(20,),
        ),
    }
    program = _program(["a", "b", "c"])
    baseline = evaluate_route_program_continuity(
        program,
        baseline_profiles,
        {"a": {}, "b": {}, "c": {}},
    )
    new_profiles = {
        "a": _profile(
            "a",
            [{"action_id": "a10", "kind": "accept", "task_id": 10}],
        ),
        "b": _profile(
            "b",
            [
                {"action_id": "t10", "kind": "turnin", "task_id": 10},
                {"action_id": "a20", "kind": "accept", "task_id": 20},
            ],
            entry_active=(10,),
        ),
        "c": baseline_profiles["c"],
    }
    old_c_edge = deepcopy(baseline["edges"][2])
    original_replay = route_continuity.replay_route_profile
    replayed_profiles: list[str] = []

    def _counting_replay(profile, **kwargs):
        replayed_profiles.append(profile["profile_id"])
        return original_replay(profile, **kwargs)

    monkeypatch.setattr(route_continuity, "replay_route_profile", _counting_replay)
    updated = update_route_program_continuity_from_profile(
        program,
        new_profiles,
        {"a": {}, "b": {}, "c": {}},
        current_report=baseline,
        start_profile_id="a",
    )

    assert replayed_profiles == ["a", "b"]
    assert updated["edges"][2] == old_c_edge
    assert updated["final_state"] == baseline["final_state"]
    assert (
        updated["member_input_fingerprints"]["c"]
        == baseline["member_input_fingerprints"]["c"]
    )


def test_incremental_program_continuity_rejects_program_contract_change() -> None:
    profiles = {"a": _profile("a")}
    program = _program(["a"])
    baseline = evaluate_route_program_continuity(program, profiles, {"a": {}})
    changed = _program(["a"], entry_active=(99,))

    try:
        update_route_program_continuity_from_profile(
            changed,
            profiles,
            {"a": {}},
            current_report=baseline,
            start_profile_id="a",
        )
    except ValueError as exc:
        assert "entry_state_contract changed" in str(exc)
    else:
        raise AssertionError("incremental Continuity must reject Program entry contract changes")
