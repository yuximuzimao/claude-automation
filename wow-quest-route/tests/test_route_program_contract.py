from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from lib.route_programs import RouteProgramError, load_route_program_schema, validate_route_program


def _profile(profile_id: str, *, status: str = "draft", character_profile: str = "horde-fivebox-current") -> dict:
    return {
        "profile_id": profile_id,
        "status": status,
        "scope": {
            "game_variant_id": "timewalking-wotlk-cn",
            "character_profile": character_profile,
        },
    }


def _program() -> dict:
    return {
        "schema_version": 1,
        "program_id": "test-program",
        "version": 1,
        "status": "draft",
        "scope": {
            "program_scope": "test",
            "character_profile": "horde-fivebox-current",
            "game_variant_id": "timewalking-wotlk-cn",
        },
        "entry_state_contract": {
            "active_task_ids": [],
            "opened_flight_points": [],
        },
        "goal": {"summary": "test"},
        "profile_ids": ["a", "b"],
    }


def test_route_program_schema_is_valid_draft_2020_12() -> None:
    schema = load_route_program_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "wow-quest-route/route-program/v1"


def test_route_program_references_profiles_by_strict_order_without_copying_route_content() -> None:
    profiles = {"a": _profile("a"), "b": _profile("b")}
    validate_route_program(_program(), expected_program_id="test-program", known_profiles=profiles)

    invalid = copy.deepcopy(_program())
    invalid["actions"] = []
    with pytest.raises(RouteProgramError, match="JSON Schema"):
        validate_route_program(invalid, known_profiles=profiles)


def test_route_program_rejects_unknown_or_incompatible_profiles() -> None:
    profiles = {"a": _profile("a"), "b": _profile("b")}

    unknown = copy.deepcopy(_program())
    unknown["profile_ids"] = ["a", "missing"]
    with pytest.raises(RouteProgramError, match="unknown Route Profiles"):
        validate_route_program(unknown, known_profiles=profiles)

    incompatible = {"a": _profile("a"), "b": _profile("b", character_profile="dk-twohand-blood-current")}
    with pytest.raises(RouteProgramError, match="character_profile"):
        validate_route_program(_program(), known_profiles=incompatible)


def test_route_program_allows_only_adjacent_boundary_transition_chains() -> None:
    profiles = {"a": _profile("a"), "b": _profile("b")}
    program = _program()
    program["boundary_transitions"] = [
        {
            "from_profile_id": "a",
            "to_profile_id": "b",
            "operations": [
                {
                    "operation_id": "leave-a",
                    "kind": "fixed_transport",
                    "from_name": "A",
                    "to_name": "Hub",
                },
                {
                    "operation_id": "hub-to-b",
                    "kind": "taxi",
                    "from_name": "Hub",
                    "to_name": "B",
                },
            ],
        }
    ]
    validate_route_program(program, known_profiles=profiles)

    non_adjacent = copy.deepcopy(program)
    non_adjacent["profile_ids"] = ["a", "b", "c"]
    non_adjacent["boundary_transitions"][0]["to_profile_id"] = "c"
    profiles["c"] = _profile("c")
    with pytest.raises(RouteProgramError, match="adjacent Profile ids"):
        validate_route_program(non_adjacent, known_profiles=profiles)


def test_non_retired_program_cannot_reference_retired_profile() -> None:
    profiles = {"a": _profile("a"), "b": _profile("b", status="retired")}
    with pytest.raises(RouteProgramError, match="retired Route Profiles"):
        validate_route_program(_program(), known_profiles=profiles)

    retired_program = copy.deepcopy(_program())
    retired_program["status"] = "retired"
    validate_route_program(retired_program, known_profiles=profiles)
