from __future__ import annotations

from copy import deepcopy

import pytest

from lib.route_xp import (
    XpModelError,
    evaluate_profile_xp,
    evaluate_route_program_xp,
    update_route_program_xp_from_profile,
    load_xp_model_config,
    quest_xp_at_level,
    validate_xp_model_config,
)


def _entry(level: int, xp: int, count: int = 1) -> dict:
    return {
        "source": {"kind": "explicit_test_fixture", "ref": "synthetic"},
        "characters": [
            {"character_id": f"c{index + 1}", "level": level, "xp_into_level": xp}
            for index in range(count)
        ],
    }


def _card(task_id: int, *, quest_level: int, full_xp: int, min_level: int | None = None) -> dict:
    return {
        "task_id": task_id,
        "availability": {
            "quest_level": quest_level,
            "min_level": min_level if min_level is not None else max(1, quest_level - 5),
        },
        "rewards": {"full_xp": full_xp},
    }


def _profile(profile_id: str, actions: list[dict]) -> dict:
    return {
        "profile_id": profile_id,
        "version": 1,
        "scope": {"game_variant_id": "timewalking-wotlk-cn"},
        "actions": actions,
    }


def test_xp_model_config_is_single_complete_level_threshold_owner() -> None:
    config = load_xp_model_config()
    table = config["xp_to_next_by_level"]

    assert table["39"] == 70200
    assert table["55"] == 148200
    assert table["60"] == 290000
    assert table["68"] == 648000
    assert table["70"] == 1523800
    assert table["79"] == 1670800
    assert set(table) == {str(level) for level in range(1, 80)}


def test_xp_config_validator_rejects_gap_and_bad_multiplier() -> None:
    bad = deepcopy(load_xp_model_config())
    bad["server_quest_xp_multiplier"] = 0
    bad["xp_to_next_by_level"].pop("68")

    with pytest.raises(XpModelError) as exc:
        validate_xp_model_config(bad)

    text = str(exc.value)
    assert "server_quest_xp_multiplier" in text
    assert "68" in text


def test_quest_xp_uses_actual_turnin_level_and_versioned_server_multiplier() -> None:
    config = load_xp_model_config()

    assert quest_xp_at_level(
        quest_level=60,
        full_xp=10000,
        player_level=65,
        model_config=config,
    ) == 20000
    assert quest_xp_at_level(
        quest_level=60,
        full_xp=10000,
        player_level=66,
        model_config=config,
    ) == 16000
    assert quest_xp_at_level(
        quest_level=60,
        full_xp=10000,
        player_level=70,
        model_config=config,
    ) == 2000
    assert quest_xp_at_level(
        quest_level=60,
        full_xp=10000,
        player_level=80,
        model_config=config,
    ) == 0


def test_profile_xp_resolves_stage3_level_gate_from_actual_turnin_timeline() -> None:
    profile = _profile(
        "p1",
        [
            {"action_id": "a1", "kind": "accept", "task_id": 100},
            {"action_id": "t1", "kind": "turnin", "task_id": 100},
            {"action_id": "a2", "kind": "accept", "task_id": 200},
        ],
    )
    cards = {
        100: _card(100, quest_level=59, full_xp=10000),
        200: _card(200, quest_level=60, full_xp=10000, min_level=60),
    }
    deferred = [
        {
            "action_id": "a2",
            "task_id": 200,
            "kind": "min_level",
            "required_min_level": 60,
            "resolver": "derived_xp",
        }
    ]

    report = evaluate_profile_xp(
        profile,
        task_cards=cards,
        action_execution={"a1": "executed", "t1": "executed", "a2": "executed"},
        deferred_gates=deferred,
        entry_state=_entry(59, 160000, count=5),
        external_xp_upper_bound_by_character={f"c{i}": 0 for i in range(1, 6)},
    )

    assert report["status"] == "pass"
    assert report["level_gates"][0]["status"] == "pass"
    assert {row["level"] for row in report["exit_state_lower"]["characters"]} == {60}
    assert report["guaranteed_lower_bound"] == 20000
    assert report["possible_upper_bound"] == 20000


def test_profile_xp_keeps_risk_upper_unknown_without_explicit_external_bound() -> None:
    profile = _profile(
        "p1",
        [{"action_id": "t1", "kind": "turnin", "task_id": 100}],
    )
    report = evaluate_profile_xp(
        profile,
        task_cards={100: _card(100, quest_level=59, full_xp=10000)},
        action_execution={"t1": "executed"},
        deferred_gates=[],
        entry_state=_entry(59, 0, count=5),
    )

    assert report["status"] == "requirements"
    assert report["guaranteed_lower_bound"] == 20000
    assert report["possible_upper_bound"] is None
    assert any(issue["kind"] == "external_xp_upper_bound_required" for issue in report["issues"])


def test_profile_risk_upper_does_not_masquerade_as_total_upper_when_decay_changes() -> None:
    profile = _profile("p1", [{"action_id": "t1", "kind": "turnin", "task_id": 100}])
    report = evaluate_profile_xp(
        profile,
        task_cards={100: _card(100, quest_level=50, full_xp=10000)},
        action_execution={"t1": "executed"},
        deferred_gates=[],
        entry_state=_entry(55, 0),
        external_xp_upper_bound_by_character={"c1": 148200},
    )

    assert report["guaranteed_lower_bound"] == 20000
    assert report["exit_state_risk_upper"] is not None
    assert report["possible_upper_bound"] is None
    assert report["status"] == "requirements"
    assert any(
        issue["kind"] == "external_xp_timing_required_for_upper_bound"
        for issue in report["issues"]
    )


def test_profile_xp_never_infers_entry_level_from_profile_text() -> None:
    profile = _profile("p1", [{"action_id": "t1", "kind": "turnin", "task_id": 100}])
    profile["goal"] = {"summary": "58→64"}
    profile["display"] = {"title": "58—64路线"}

    report = evaluate_profile_xp(
        profile,
        task_cards={100: _card(100, quest_level=59, full_xp=10000)},
        action_execution={"t1": "executed"},
        deferred_gates=[],
        entry_state=None,
    )

    assert report["status"] == "requirements"
    assert report["entry_state"] is None
    assert any(issue["kind"] == "xp_entry_state_required" for issue in report["issues"])


def test_program_xp_propagates_fresh_profile_exit_into_next_profile_gate() -> None:
    first = _profile("first", [{"action_id": "t1", "kind": "turnin", "task_id": 100}])
    second = _profile("second", [{"action_id": "a2", "kind": "accept", "task_id": 200}])
    program = {"program_id": "prog", "version": 1, "profile_ids": ["first", "second"]}
    continuity = {
        "status": "ok",
        "input_fingerprint": "stage4",
        "edges": [
            {
                "to": "first",
                "action_execution": {"t1": "executed"},
                "deferred_gates": [],
            },
            {
                "to": "second",
                "action_execution": {"a2": "executed"},
                "deferred_gates": [
                    {
                        "action_id": "a2",
                        "task_id": 200,
                        "kind": "min_level",
                        "required_min_level": 60,
                        "resolver": "derived_xp",
                    }
                ],
            },
        ],
    }
    cards = {
        "first": {100: _card(100, quest_level=59, full_xp=10000)},
        "second": {200: _card(200, quest_level=60, full_xp=10000, min_level=60)},
    }
    zero_upper = {
        "first": {f"c{i}": 0 for i in range(1, 6)},
        "second": {f"c{i}": 0 for i in range(1, 6)},
    }

    report = evaluate_route_program_xp(
        program,
        {"first": first, "second": second},
        task_cards_by_profile=cards,
        continuity_report=continuity,
        entry_state=_entry(59, 160000, count=5),
        external_xp_upper_bound_by_profile=zero_upper,
    )

    assert report["status"] == "pass"
    assert report["member_reports"]["second"]["level_gates"][0]["status"] == "pass"
    assert {row["level"] for row in report["exit_state_lower"]["characters"]} == {60}


def test_program_xp_requires_machine_entry_state_even_when_program_order_is_known() -> None:
    program = {"program_id": "prog", "version": 1, "profile_ids": ["first"]}
    continuity = {"status": "ok", "input_fingerprint": "stage4", "edges": []}

    report = evaluate_route_program_xp(
        program,
        {"first": _profile("first", [])},
        task_cards_by_profile={"first": {}},
        continuity_report=continuity,
        entry_state=None,
    )

    assert report["status"] == "requirements"
    assert report["member_reports"] == {}
    assert any(issue["kind"] == "xp_entry_state_required" for issue in report["issues"])


def test_program_xp_incremental_update_preserves_prefix_and_recomputes_suffix() -> None:
    first = _profile("first", [{"action_id": "t1", "kind": "turnin", "task_id": 100}])
    second = _profile("second", [{"action_id": "a2", "kind": "accept", "task_id": 200}])
    program = {"program_id": "prog", "version": 1, "profile_ids": ["first", "second"]}
    continuity = {
        "status": "ok",
        "input_fingerprint": "stage4",
        "edges": [
            {
                "to": "first",
                "action_execution": {"t1": "executed"},
                "deferred_gates": [],
            },
            {
                "to": "second",
                "action_execution": {"a2": "executed"},
                "deferred_gates": [
                    {
                        "action_id": "a2",
                        "task_id": 200,
                        "kind": "min_level",
                        "required_min_level": 60,
                        "resolver": "derived_xp",
                    }
                ],
            },
        ],
    }
    cards = {
        "first": {100: _card(100, quest_level=59, full_xp=10000)},
        "second": {200: _card(200, quest_level=60, full_xp=10000, min_level=60)},
    }
    zero_upper = {
        "first": {f"c{i}": 0 for i in range(1, 6)},
        "second": {f"c{i}": 0 for i in range(1, 6)},
    }
    baseline = evaluate_route_program_xp(
        program,
        {"first": first, "second": second},
        task_cards_by_profile=cards,
        continuity_report=continuity,
        entry_state=_entry(59, 160000, count=5),
        external_xp_upper_bound_by_profile=zero_upper,
    )
    first_before = deepcopy(baseline["member_reports"]["first"])

    updated = update_route_program_xp_from_profile(
        program,
        {"first": first, "second": second},
        task_cards_by_profile=cards,
        continuity_report=continuity,
        current_report=baseline,
        start_profile_id="second",
        external_xp_upper_bound_by_profile=zero_upper,
    )

    assert updated["member_reports"]["first"] == first_before
    assert updated["member_reports"]["second"]["level_gates"][0]["status"] == "pass"
    assert updated["exit_state_lower"] == baseline["exit_state_lower"]
