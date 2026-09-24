from __future__ import annotations

from lib.route_replay import ReplayState, replay_route_profile, replay_state_from_replay


def _profile(actions, *, entry_tasks=(), entry_hearth=None):
    return {
        "profile_id": "synthetic-route",
        "entry_requirements": {
            "active_task_ids": list(entry_tasks),
            **({"hearth_location": entry_hearth} if entry_hearth is not None else {}),
        },
        "actions": actions,
    }


def test_route_replay_derives_quest_log_peak_and_flight_entry_requirements() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "accept", "task_id": 10},
            {"action_id": "a2", "kind": "accept", "task_id": 11},
            {"action_id": "a3", "kind": "turnin", "task_id": 10},
            {"action_id": "a4", "kind": "open_flight_point", "target_name": "A"},
            {"action_id": "a5", "kind": "taxi", "from_name": "A", "to_name": "B"},
            {"action_id": "a6", "kind": "turnin", "task_id": 11},
        ]
    )

    replay = replay_route_profile(profile, entry_state=ReplayState(active_tasks_known=True))

    assert replay.quest_log_peak_upper_bound == 2
    assert replay.required_entry_flight_points == {"B"}
    assert replay.opened_flight_points == {"A", "B"}
    assert replay.issues == []


def test_route_replay_does_not_treat_minimum_entry_requirements_as_complete_task_log() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "accept", "task_id": 10},
            {"action_id": "o99", "kind": "objective", "task_id": 99},
            {"action_id": "t99", "kind": "turnin", "task_id": 99},
        ]
    )

    replay = replay_route_profile(profile)

    assert replay.entry_active_tasks_known is False
    assert replay.quest_log_peak_upper_bound is None
    assert any(issue["kind"] == "actual_entry_active_tasks_required" for issue in replay.issues)
    assert not any(issue["kind"] == "objective_for_inactive_task" for issue in replay.issues)
    assert not any(issue["kind"] == "turnin_for_inactive_task" for issue in replay.issues)
    assert any(
        requirement["kind"] == "active_task" and requirement["task_id"] == 99
        for requirement in replay.external_state_requirements
    )
    assert 99 in replay.completed_tasks


def test_route_replay_accepts_program_supplied_entry_state_without_second_transition_engine() -> None:
    profile = _profile(
        [{"action_id": "t10", "kind": "turnin", "task_id": 10}],
    )
    supplied = ReplayState(
        active_tasks={10},
        active_tasks_known=True,
        completed_tasks={1},
        completed_tasks_known=False,
        hearth_location="萨尔玛",
        hearth_location_known=True,
        opened_flight_points={"萨尔玛"},
        opened_flight_points_known=False,
    )

    replay = replay_route_profile(profile, entry_state=supplied)
    output = replay_state_from_replay(replay)

    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    assert output.active_tasks == set()
    assert output.completed_tasks == {1, 10}
    assert output.hearth_location == "萨尔玛"
    assert output.hearth_location_known is True
    assert output.opened_flight_points == {"萨尔玛"}


def test_route_replay_requires_entry_hearth_when_used_before_any_bind() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "use_hearth", "target_name": "征服堡"},
        ],
    )

    replay = replay_route_profile(profile)

    assert any(issue["kind"] == "missing_entry_hearth_contract" for issue in replay.issues)


def test_route_replay_uses_upper_bound_for_conditional_task_log_capacity() -> None:
    actions = []
    for task_id in range(1, 26):
        actions.append({"action_id": f"a{task_id}", "kind": "accept", "task_id": task_id})
    actions.append(
        {
            "action_id": "a26",
            "kind": "accept",
            "task_id": 26,
            "when": {"kind": "has_item", "item_id": 999},
        }
    )
    actions.append(
        {
            "action_id": "a27",
            "kind": "turnin",
            "task_id": 26,
            "when": {"kind": "task_active", "task_id": 26},
        }
    )
    for task_id in range(1, 26):
        actions.append({"action_id": f"t{task_id}", "kind": "turnin", "task_id": task_id})

    replay = replay_route_profile(
        _profile(actions),
        entry_state=ReplayState(active_tasks_known=True),
    )

    assert replay.quest_log_peak_upper_bound == 26
    assert any(issue["kind"] == "quest_log_cap_exceeded" for issue in replay.issues)


def _availability_card(
    task_id: int,
    *,
    pre_all=(),
    pre_any=(),
    parent_active=(),
    required_race=(),
    min_level=58,
    required_reputation=None,
):
    return {
        "task_id": task_id,
        "identity": {"faction": "horde", "repeatability": "once"},
        "availability": {
            "min_level": min_level,
            "pre_all": list(pre_all),
            "pre_any": list(pre_any),
            "parent_active": list(parent_active),
            "exclusive_with": [],
            "required_race": list(required_race),
            "required_class": [],
            "required_skill": [],
            "required_reputation": required_reputation,
            "hidden_requirements": [],
        },
        "rewards": {"reputation_rewards": []},
    }


def test_stage3_availability_uses_action_time_completed_state_and_defers_dynamic_gates() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "accept", "task_id": 1},
            {"action_id": "t1", "kind": "turnin", "task_id": 1},
            {"action_id": "a2", "kind": "accept", "task_id": 2},
            {"action_id": "t2", "kind": "turnin", "task_id": 2},
        ]
    )
    profile["task_ids"] = [1, 2]
    cards = {
        1: _availability_card(1),
        2: _availability_card(
            2,
            pre_all=(1,),
            required_race=("blood_elf",),
            min_level=60,
            required_reputation={"min": {"1": 942, "2": 3000}, "max": None},
        ),
    }
    character = {"faction": "horde", "race": "blood_elf", "class": "paladin"}

    replay = replay_route_profile(profile, task_cards=cards, character_profile=character)

    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    assert replay.completed_tasks == {1, 2}
    assert any(gate["kind"] == "min_level" and gate["task_id"] == 2 for gate in replay.deferred_gates)
    assert any(gate["kind"] == "reputation" and gate["task_id"] == 2 for gate in replay.deferred_gates)
    event = next(event for event in replay.availability_events if event["task_id"] == 2)
    assert any(check["kind"] == "pre_all" and check["status"] == "pass" for check in event["checks"])
    assert any(check["kind"] == "race" and check["status"] == "pass" for check in event["checks"])


def test_stage3_parent_active_overrides_overlapping_prequest_completion_semantics() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "accept", "task_id": 1},
            {"action_id": "a2", "kind": "accept", "task_id": 2},
            {"action_id": "t2", "kind": "turnin", "task_id": 2},
            {"action_id": "t1", "kind": "turnin", "task_id": 1},
        ]
    )
    profile["task_ids"] = [1, 2]
    cards = {
        1: _availability_card(1),
        2: _availability_card(2, pre_any=(1,), parent_active=(1,)),
    }
    character = {"faction": "horde", "race": "blood_elf", "class": "paladin"}

    replay = replay_route_profile(profile, task_cards=cards, character_profile=character)

    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    event = next(event for event in replay.availability_events if event["task_id"] == 2)
    assert any(check["kind"] == "parent_active" and check["status"] == "pass_or_deferred" for check in event["checks"])
    assert not any(check["kind"] == "pre_any" for check in event["checks"])
    assert not any(req.get("required_task_ids") == [1] for req in replay.external_state_requirements)


def test_stage3_availability_surfaces_external_prerequisite_without_calling_it_local_failure() -> None:
    profile = _profile(
        [
            {"action_id": "a2", "kind": "accept", "task_id": 2},
            {"action_id": "t2", "kind": "turnin", "task_id": 2},
        ]
    )
    profile["task_ids"] = [2]
    cards = {2: _availability_card(2, pre_all=(99,))}
    character = {"faction": "horde", "race": "blood_elf", "class": "paladin"}

    replay = replay_route_profile(profile, task_cards=cards, character_profile=character)

    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    assert any(
        req["kind"] == "completed_task" and req["required_task_id"] == 99
        for req in replay.external_state_requirements
    )


def test_stage3_availability_rejects_static_race_mismatch() -> None:
    profile = _profile(
        [
            {"action_id": "a1", "kind": "accept", "task_id": 1},
            {"action_id": "t1", "kind": "turnin", "task_id": 1},
        ]
    )
    profile["task_ids"] = [1]
    cards = {1: _availability_card(1, required_race=("orc",))}
    character = {"faction": "horde", "race": "blood_elf", "class": "paladin"}

    replay = replay_route_profile(profile, task_cards=cards, character_profile=character)

    assert any(issue["kind"] == "availability_race_mismatch" for issue in replay.issues)


def test_stage3_program_entry_completed_state_unknown_vs_known_empty() -> None:
    character = {"faction": "horde", "race": "blood_elf", "class": "paladin"}
    cards = {2: _availability_card(2, pre_all=(99,))}
    profile = _profile(
        [
            {"action_id": "a2", "kind": "accept", "task_id": 2},
            {"action_id": "t2", "kind": "turnin", "task_id": 2},
        ]
    )
    profile["task_ids"] = [2]

    unknown_replay = replay_route_profile(profile, task_cards=cards, character_profile=character)
    assert not [issue for issue in unknown_replay.issues if issue["severity"] == "error"]
    assert any(req["kind"] == "completed_task" for req in unknown_replay.external_state_requirements)

    known_empty = ReplayState(completed_tasks=set(), completed_tasks_known=True)
    known_empty_replay = replay_route_profile(
        profile, task_cards=cards, character_profile=character, entry_state=known_empty
    )
    assert any(issue["kind"] == "pre_all_not_completed_before_accept" for issue in known_empty_replay.issues)


def test_stage3_program_entry_hearth_unknown_vs_known_unbound() -> None:
    profile = _profile([{"action_id": "a1", "kind": "use_hearth", "target_name": "征服堡"}])
    unknown_replay = replay_route_profile(profile)
    assert any(issue["kind"] == "missing_entry_hearth_contract" for issue in unknown_replay.issues)
    assert not any(issue["kind"] == "hearth_not_bound" for issue in unknown_replay.issues)

    known_unbound = ReplayState(hearth_location=None, hearth_location_known=True)
    known_unbound_replay = replay_route_profile(profile, entry_state=known_unbound)
    assert any(issue["kind"] == "hearth_not_bound" for issue in known_unbound_replay.issues)


def test_stage3_program_entry_flight_state_unknown_vs_known_empty() -> None:
    actions = [{"action_id": "a1", "kind": "taxi", "from_name": "A", "to_name": "B"}]
    profile = _profile(actions)
    unknown_replay = replay_route_profile(profile)
    assert unknown_replay.required_entry_flight_points == {"A", "B"}
    assert not any(issue["kind"] == "taxi_requires_unopened_flight_point" for issue in unknown_replay.issues)

    known_empty = ReplayState(opened_flight_points=set(), opened_flight_points_known=True)
    known_empty_replay = replay_route_profile(profile, entry_state=known_empty)
    assert any(issue["kind"] == "taxi_requires_unopened_flight_point" for issue in known_empty_replay.issues)


def test_stage3_exit_hearth_is_derived_without_second_contract() -> None:
    profile = _profile([])
    supplied = ReplayState(hearth_location="征服堡", hearth_location_known=True)
    replay = replay_route_profile(profile, entry_state=supplied)
    output = replay_state_from_replay(replay)

    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    assert output.hearth_location == "征服堡"
    assert output.hearth_location_known is True


def test_task_complete_turnin_preserves_real_complete_or_carry_branch() -> None:
    profile = _profile(
        [
            {"action_id": "t10", "kind": "turnin", "task_id": 10, "when": {"kind": "task_complete", "task_id": 10}},
        ]
    )
    supplied = ReplayState(active_tasks={10}, active_tasks_known=True)

    replay = replay_route_profile(profile, entry_state=supplied)
    output = replay_state_from_replay(replay)

    assert replay.action_execution["t10"] == "maybe"
    assert replay.active_tasks == set()
    assert replay.maybe_active_tasks == {10}
    assert replay.maybe_completed_tasks == {10}
    assert output.maybe_active_tasks == {10}
    assert output.maybe_completed_tasks == {10}
    assert not [issue for issue in replay.issues if issue["severity"] == "error"]
    branch = next(issue for issue in replay.issues if issue["kind"] == "conditional_task_exit_state_branch")
    assert branch["severity"] == "requirement"
    assert branch["maybe_active_task_ids"] == [10]
    assert branch["maybe_completed_task_ids"] == [10]


def test_task_complete_turnin_is_skipped_when_task_is_known_absent() -> None:
    profile = _profile(
        [
            {"action_id": "t10", "kind": "turnin", "task_id": 10, "when": {"kind": "task_complete", "task_id": 10}},
        ]
    )
    supplied = ReplayState(active_tasks=set(), active_tasks_known=True)

    replay = replay_route_profile(profile, entry_state=supplied)

    assert replay.action_execution["t10"] == "skipped"
    assert replay.maybe_active_tasks == set()
    assert replay.maybe_completed_tasks == set()
    assert not any(issue["kind"] == "conditional_task_exit_state_branch" for issue in replay.issues)


def test_task_active_turnin_executes_when_active_and_branches_when_maybe_active() -> None:
    profile = _profile(
        [
            {"action_id": "t10", "kind": "turnin", "task_id": 10, "when": {"kind": "task_active", "task_id": 10}},
        ]
    )

    definite = replay_route_profile(
        profile,
        entry_state=ReplayState(active_tasks={10}, active_tasks_known=True),
    )
    assert definite.action_execution["t10"] == "executed"
    assert definite.completed_tasks == {10}
    assert definite.maybe_completed_tasks == set()

    maybe = replay_route_profile(
        profile,
        entry_state=ReplayState(maybe_active_tasks={10}, active_tasks_known=False),
    )
    assert maybe.action_execution["t10"] == "maybe"
    assert maybe.maybe_active_tasks == set()
    assert maybe.maybe_completed_tasks == {10}
    assert any(issue["kind"] == "conditional_task_exit_state_branch" for issue in maybe.issues)


def test_action_execution_marks_unconditional_task_actions_as_executed() -> None:
    profile = _profile(
        [
            {"action_id": "a10", "kind": "accept", "task_id": 10},
            {"action_id": "o10", "kind": "objective", "task_id": 10},
            {"action_id": "t10", "kind": "turnin", "task_id": 10},
        ]
    )
    replay = replay_route_profile(profile, entry_state=ReplayState(active_tasks_known=True))

    assert replay.action_execution == {"a10": "executed", "o10": "executed", "t10": "executed"}
