from __future__ import annotations

import copy

import pytest

from lib.route_dependencies import (
    DependencyError,
    build_dependency_index,
    build_profile_dependency_manifest,
    build_profile_program_index,
    canonical_json_hash,
    compose_fingerprint,
    fingerprint_route_profile,
    fingerprint_route_program_discovery,
    fingerprint_task_card,
    schema_source_inventory,
)


def _card() -> dict:
    return {
        "schema_version": 1,
        "task_id": 1,
        "identity": {
            "name_zhcn": "测试任务",
            "name_en": None,
            "game_variant_id": "test-wotlk",
            "version_scope": "test",
            "faction": "both",
            "repeatability": "once",
        },
        "coverage": {"availability": "verified", "rewards": "verified", "guide": "verified"},
        "availability": {
            "quest_level": 60,
            "min_level": 58,
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
        "rewards": {"full_xp": 1000, "reward_money_copper": 100},
        "guide": ["测试攻略"],
        "fivebox": {"status": "shared"},
        "timing_rule_ref": None,
        "evidence": [],
        "presentation": {"note_override": {"text": ""}},
    }


def _profile(profile_id: str = "test-profile") -> dict:
    return {
        "schema_version": 2,
        "profile_id": profile_id,
        "version": 1,
        "status": "current",
        "scope": {
            "route_scope": "test-zone",
            "character_profile": "test-character",
            "game_variant_id": "test-wotlk",
        },
        "entry_requirements": {"active_task_ids": []},
        "goal": {"summary": "test"},
        "display": {
            "publish_key": profile_id.replace("-", "_"),
            "order": 1,
            "title": "test",
            "display_name": "test",
            "subtitle": "",
            "footer": "",
            "map_image": "maps/test.jpg",
        },
        "task_ids": [1],
        "actions": [],
        "step_groups": [],
        "geometry": {"locations": {}},
    }


def test_canonical_hash_is_key_order_independent() -> None:
    assert canonical_json_hash({"a": 1, "b": 2}) == canonical_json_hash({"b": 2, "a": 1})
    assert compose_fingerprint(["a", "b"]) != compose_fingerprint(["b", "a"])


def test_task_card_section_hashes_allow_precise_downstream_invalidation() -> None:
    original = fingerprint_task_card(_card())
    changed_card = copy.deepcopy(_card())
    changed_card["presentation"]["note_override"]["text"] = "只改展示"
    changed = fingerprint_task_card(changed_card)

    assert original["hash"] != changed["hash"]
    assert original["sections"]["presentation"] != changed["sections"]["presentation"]
    for section in original["sections"]:
        if section != "presentation":
            assert original["sections"][section] == changed["sections"][section]


def test_profile_section_hashes_do_not_turn_display_change_into_route_change() -> None:
    original = fingerprint_route_profile(_profile())
    changed_profile = copy.deepcopy(_profile())
    changed_profile["display"]["title"] = "新标题"
    changed = fingerprint_route_profile(changed_profile)

    assert original["hash"] != changed["hash"]
    assert original["sections"]["display"] != changed["sections"]["display"]
    for section in original["sections"]:
        if section != "display":
            assert original["sections"][section] == changed["sections"][section]


def test_route_program_section_hashes_allow_precise_downstream_invalidation() -> None:
    program = {
        "schema_version": 1,
        "program_id": "program",
        "version": 1,
        "status": "current",
        "scope": {"character_profile": "test-character", "game_variant_id": "test-wotlk"},
        "entry_state_contract": {"active_task_ids": []},
        "goal": {"summary": "test"},
        "profile_ids": ["a", "b"],
        "change_log": [],
    }
    original = fingerprint_route_program_discovery(program)
    changed_program = copy.deepcopy(program)
    changed_program["goal"]["summary"] = "new goal"
    changed = fingerprint_route_program_discovery(changed_program)

    assert original["hash"] != changed["hash"]
    assert original["sections"]["goal"] != changed["sections"]["goal"]
    for section in original["sections"]:
        if section != "goal":
            assert original["sections"][section] == changed["sections"][section]


def test_profile_program_reverse_index_is_mechanical_and_excludes_retired() -> None:
    programs = {
        "p1": {"program_id": "p1", "status": "current", "profile_ids": ["a", "b"]},
        "p2": {"program_id": "p2", "status": "current", "profile_ids": ["b", "c"]},
        "old": {"program_id": "old", "status": "retired", "profile_ids": ["a"]},
    }
    assert build_profile_program_index(programs) == {"a": ["p1"], "b": ["p1", "p2"], "c": ["p2"]}
    assert build_profile_program_index(programs, include_retired=True) == {
        "a": ["old", "p1"],
        "b": ["p1", "p2"],
        "c": ["p2"],
    }


def test_schema_inventory_fails_closed_when_required_schema_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "lib.route_dependencies.SCHEMA_SOURCES",
        {"missing_schema": tmp_path / "missing-schema.json"},
    )
    with pytest.raises(DependencyError, match="missing dependency schemas"):
        schema_source_inventory()


def test_manifest_fails_closed_when_character_profile_reference_is_missing() -> None:
    with pytest.raises(DependencyError, match="references missing character profile"):
        build_profile_dependency_manifest(
            "test-profile",
            profile=_profile(),
            cards={1: _card()},
            programs={},
            shared_source_inventory={
                "schemas": {},
                "rules": [],
                "observations": [],
                "external_timing_inputs": [],
            },
        )


def test_dependency_index_reports_unknown_program_profile_refs_without_guessing() -> None:
    profiles = {"a": _profile("a"), "b": _profile("b")}
    programs = {
        "program": {
            "program_id": "program",
            "status": "current",
            "profile_ids": ["a", "missing-profile", "b"],
        }
    }
    index = build_dependency_index(profiles=profiles, programs=programs)
    assert index["task_to_profiles"] == {"1": ["a", "b"]}
    assert index["profile_to_programs"] == {
        "a": ["program"],
        "b": ["program"],
        "missing-profile": ["program"],
    }
    assert index["unknown_program_profile_refs"] == ["missing-profile"]
