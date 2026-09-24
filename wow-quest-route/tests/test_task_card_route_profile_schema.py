from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from lib.route_profiles import RouteProfileError, build_task_profile_index, load_route_profile_schema, validate_route_profile
from lib.task_cards import TaskCardError, load_task_card_schema, validate_task_card


GAME_VARIANT = "test-wotlk"


def _card(task_id: int = 1) -> dict:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "identity": {
            "name_zhcn": f"测试任务{task_id}",
            "name_en": None,
            "game_variant_id": GAME_VARIANT,
            "version_scope": "test",
            "faction": "both",
            "repeatability": "once",
        },
        "coverage": {
            "availability": "partial",
            "rewards": "unknown",
            "guide": "unknown",
        },
        "availability": {
            "quest_level": None,
            "min_level": None,
            "pre_any": [],
            "pre_all": [],
            "parent_active": [],
            "exclusive_with": [],
            "required_reputation": None,
            "required_class": [],
            "required_race": [],
            "required_skill": [],
            "hidden_requirements": [],
        },
        "rewards": {},
        "guide": [],
        "fivebox": {"status": "pending"},
        "timing_rule_ref": None,
        "evidence": [],
        "presentation": {},
    }


def _profile(task_id: int = 1) -> dict:
    return {
        "schema_version": 2,
        "profile_id": "test-profile",
        "version": 1,
        "status": "draft",
        "scope": {
            "route_scope": "test-zone",
            "character_profile": "test-character",
            "game_variant_id": GAME_VARIANT,
        },
        "entry_requirements": {"active_task_ids": []},
        "goal": {"summary": "测试结构化路线契约"},
        "display": {
            "publish_key": "test_profile",
            "order": 1,
            "title": "测试路线",
            "display_name": "测试路线",
            "subtitle": "",
            "footer": "",
            "map_image": "maps/test.jpg",
        },
        "task_ids": [task_id],
        "actions": [
            {"action_id": "a1", "kind": "location", "location_ref": "p1"},
            {"action_id": "a2", "kind": "accept", "task_id": task_id, "location_ref": "p1", "npc_name": "测试NPC"},
            {"action_id": "a3", "kind": "objective", "task_id": task_id, "location_ref": "p1"},
            {"action_id": "a4", "kind": "turnin", "task_id": task_id, "location_ref": "p1", "npc_name": "测试NPC"},
        ],
        "step_groups": [
            {"step_id": "s1", "title": "测试步骤", "summary": None, "action_ids": ["a1", "a2", "a3", "a4"]}
        ],
        "geometry": {"locations": {"p1": {"display_name": "测试地点", "x": 50.0, "y": 50.0}}},
    }


def test_json_schema_documents_are_valid_draft_2020_12() -> None:
    task_schema = load_task_card_schema()
    route_schema = load_route_profile_schema()
    Draft202012Validator.check_schema(task_schema)
    Draft202012Validator.check_schema(route_schema)
    assert task_schema["$id"] == "wow-quest-route/task-card/v1"
    assert route_schema["$id"] == "wow-quest-route/route-profile/v2"


def test_task_card_shape_is_owned_by_json_schema() -> None:
    card = _card()
    validate_task_card(card, expected_task_id=1)

    invalid = copy.deepcopy(card)
    invalid["identity"]["unexpected"] = True
    with pytest.raises(TaskCardError, match="JSON Schema"):
        validate_task_card(invalid)

    special = copy.deepcopy(card)
    special["fivebox"]["status"] = "special"
    validate_task_card(special)

    invalid = copy.deepcopy(card)
    invalid["fivebox"]["stages"] = []
    with pytest.raises(TaskCardError, match="JSON Schema"):
        validate_task_card(invalid)

    invalid = copy.deepcopy(card)
    invalid["fivebox"].pop("status")
    with pytest.raises(TaskCardError, match="JSON Schema"):
        validate_task_card(invalid)


def test_route_profile_allows_explicit_unknown_location_coordinates() -> None:
    profile = _profile()
    profile["geometry"]["locations"]["p1"]["x"] = None
    profile["geometry"]["locations"]["p1"]["y"] = None
    validate_route_profile(profile, known_task_cards={1: _card()})


def test_route_profile_allows_non_plottable_transition_context() -> None:
    profile = _profile()
    location = profile["geometry"]["locations"]["p1"]
    location["location_role"] = "transition_context"
    location["x"] = None
    location["y"] = None
    validate_route_profile(profile, known_task_cards={1: _card()})


def test_task_card_rejects_route_decisions_and_derived_reverse_links() -> None:
    invalid = _card()
    invalid["rewards"]["bad_route_leak"] = {"step_id": "s7"}
    with pytest.raises(TaskCardError, match="bad_route_leak"):
        validate_task_card(invalid)

    invalid = _card()
    invalid["availability"]["direct_followups"] = [2]
    with pytest.raises(TaskCardError, match="JSON Schema"):
        validate_task_card(invalid)


def test_route_profile_uses_structured_task_id_and_forbids_task_fact_copies() -> None:
    card = _card()
    profile = _profile()
    validate_route_profile(profile, known_task_cards={1: card})

    invalid = copy.deepcopy(profile)
    invalid["actions"][1].pop("task_id")
    invalid["actions"][1]["label"] = "接《测试任务1》"
    with pytest.raises(RouteProfileError, match="JSON Schema"):
        validate_route_profile(invalid, known_task_cards={1: card})

    invalid = copy.deepcopy(profile)
    invalid["change_log"] = [{"date": "x", "kind": "x", "summary": "x", "fivebox": "shared"}]
    with pytest.raises(RouteProfileError):
        validate_route_profile(invalid, known_task_cards={1: card})


def test_route_profile_requires_same_game_variant_as_task_card() -> None:
    card = _card()
    profile = _profile()
    profile["scope"]["game_variant_id"] = "another-variant"
    with pytest.raises(RouteProfileError, match="game_variant_id"):
        validate_route_profile(profile, known_task_cards={1: card})


def test_route_profile_actions_require_renderable_atomic_fields() -> None:
    card = _card()

    invalid = _profile()
    invalid["actions"][0] = {"action_id": "a1", "kind": "taxi"}
    with pytest.raises(RouteProfileError, match="JSON Schema"):
        validate_route_profile(invalid, known_task_cards={1: card})

    invalid = _profile()
    invalid["actions"][1].pop("npc_name")
    with pytest.raises(RouteProfileError, match="JSON Schema"):
        validate_route_profile(invalid, known_task_cards={1: card})

    invalid = _profile()
    invalid["actions"][3].pop("npc_name")
    with pytest.raises(RouteProfileError, match="JSON Schema"):
        validate_route_profile(invalid, known_task_cards={1: card})


def test_route_profile_step_groups_cover_actions_once_in_order() -> None:
    card = _card()
    invalid = _profile()
    invalid["step_groups"][0]["action_ids"] = ["a1", "a3", "a4"]
    with pytest.raises(RouteProfileError, match="cover every action exactly once"):
        validate_route_profile(invalid, known_task_cards={1: card})

    invalid = _profile()
    invalid["step_groups"][0]["action_ids"] = ["a1", "a3", "a2", "a4"]
    with pytest.raises(RouteProfileError, match="preserve action order"):
        validate_route_profile(invalid, known_task_cards={1: card})


def test_route_profile_exit_state_is_derived_instead_of_second_contract() -> None:
    card = _card()
    profile = _profile()
    profile["actions"] = profile["actions"][:-1]
    profile["step_groups"][0]["action_ids"] = ["a1", "a2", "a3"]

    # Leaving the task active is legal: Replay derives that exit state.  The Profile has
    # no second manually-maintained exit_state_contract to keep in sync.
    validate_route_profile(profile, known_task_cards={1: card})
    assert "exit_state_contract" not in profile


def test_route_profile_supports_real_hearth_conditions_and_travel_modes() -> None:
    card = _card()
    profile = _profile()
    profile["entry_requirements"]["hearth_location"] = "旧炉石点"
    profile["entry_requirements"]["completed_task_ids"] = [99]
    profile["entry_requirements"]["opened_flight_points"] = ["测试飞行点"]
    profile["actions"][3]["when"] = {"kind": "task_complete", "task_id": 1}
    profile["geometry"]["locations"]["p1"]["transport"] = "fly"
    validate_route_profile(profile, known_task_cards={1: card})

    swim = copy.deepcopy(profile)
    swim["geometry"]["locations"]["p1"]["transport"] = "swim"
    validate_route_profile(swim, known_task_cards={1: card})


def test_reverse_task_profile_index_is_derived() -> None:
    p1 = _profile()
    p2 = copy.deepcopy(p1)
    p2["profile_id"] = "test-profile-two"
    retired = copy.deepcopy(p1)
    retired["profile_id"] = "test-profile-retired"
    retired["status"] = "retired"

    profiles = {p["profile_id"]: p for p in (p1, p2, retired)}
    assert build_task_profile_index(profiles) == {1: ["test-profile", "test-profile-two"]}
    assert build_task_profile_index(profiles, include_retired=True) == {
        1: ["test-profile", "test-profile-retired", "test-profile-two"]
    }
