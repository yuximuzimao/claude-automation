from __future__ import annotations

from copy import deepcopy

import pytest

from lib.route_continuity import evaluate_route_program_continuity
from lib.route_movement import evaluate_profile_movement, evaluate_route_program_movement
from lib.route_service_context import evaluate_profile_service_context
from lib.route_timing import (
    TimingConfigError,
    evaluate_profile_timing,
    evaluate_route_program_timing,
    validate_timing_inputs,
)


def _location(name: str, x: float, y: float, *, incoming=None):
    row = {"display_name": name, "x": x, "y": y}
    if incoming is not None:
        row["incoming_movement"] = incoming
    return row


def _profile(*, actions=None, steps=None, service_overrides=None):
    if actions is None:
        actions = [
            {"action_id": "v1", "kind": "location", "location_ref": "p1"},
            {"action_id": "a1", "kind": "accept", "task_id": 100, "location_ref": "p1"},
            {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            {"action_id": "o1", "kind": "objective", "task_id": 100, "location_ref": "p2"},
            {"action_id": "t1", "kind": "turnin", "task_id": 100, "location_ref": "p2"},
        ]
    if steps is None:
        steps = [
            {"step_id": "step-01", "title": "A", "action_ids": [row["action_id"] for row in actions]}
        ]
    profile = {
        "profile_id": "synthetic-timing",
        "version": 1,
        "scope": {
            "route_scope": "synthetic",
            "character_profile": "synthetic-fivebox",
            "game_variant_id": "timewalking-wotlk-cn",
            "primary_zone_id": 3483,
        },
        "entry_requirements": {"active_task_ids": []},
        "task_ids": sorted({int(row["task_id"]) for row in actions if "task_id" in row}),
        "actions": actions,
        "step_groups": steps,
        "geometry": {
            "locations": {
                "p1": _location("A", 10.0, 20.0),
                "p2": _location(
                    "B",
                    11.0,
                    20.0,
                    incoming={"kind": "self_move", "mode": "ride"},
                ),
            }
        },
    }
    if service_overrides is not None:
        profile["service_overrides"] = service_overrides
    return profile


def _task_card(task_id: int, rule_ref=None):
    return {"identity": {"task_id": task_id}, "timing_rule_ref": rule_ref}


def _inputs():
    return {
        "rule_registry": {
            "schema_version": 1,
            "registry_id": "test",
            "rules": {
                "zero-independent-service": {
                    "kind": "zero_service",
                    "required_inputs": [],
                },
                "shared-kill-count": {
                    "kind": "kill_count",
                    "required_inputs": ["kill_count", "combat_seconds_per_mob"],
                },
                "fixed-service-seconds": {
                    "kind": "fixed_seconds",
                    "required_inputs": ["fixed_service_seconds"],
                },
            },
        },
        "model_config": {
            "schema_version": 1,
            "model_id": "test-timing",
            "global": {
                "combat_seconds_per_mob": 15.0,
                "personal_loot_seconds_per_corpse": 9.0,
                "fixed_object_seconds_per_character": 7.0,
                "personal_drop_tail_sigma_multiplier": 1.2,
                "accept_turnin_base_seconds_per_stop": 39.0,
                "accept_turnin_per_task_seconds": 9.6,
            },
            "movement": {
                "self_move_speed_yards_per_second": {"ride": 16.8, "fly": 21.0, "swim": None},
                "path_factor_by_mode": {"ride": 1.0, "fly": 1.05, "swim": None},
                "map_dimensions_yards_by_zone": {
                    "3483": {"width": 5027.0835, "height": 3352.0833}
                },
            },
            "uncertainty": {
                "component_relative_by_kind": {
                    "move_seconds": 0.10,
                    "objective_service_seconds": 0.20,
                    "accept_turnin_seconds": 0.10,
                    "wait_seconds": 0.25,
                    "special_seconds": 0.25
                },
                "minimum_matching_clean_observations": 2
            },
        },
        "task_parameters": {"schema_version": 1, "config_id": "test", "tasks": {}},
        "profile_action_parameters": {"schema_version": 1, "config_id": "test", "profiles": {}},
        "flight_edge_bindings": {"schema_version": 1, "config_id": "test", "profiles": {}},
        "quest_source_inputs": None,
        "leatrix_flight_times": None,
        "timing_observations": None,
    }


def _evaluate(profile, cards, inputs=None, *, action_execution=None):
    movement = evaluate_profile_movement(profile)
    service = evaluate_profile_service_context(profile, movement)
    return evaluate_profile_timing(
        profile,
        task_cards=cards,
        movement_report=movement,
        service_report=service,
        character_profile={"character_profile_id": "synthetic-fivebox", "party_size": 5},
        action_execution=action_execution,
        timing_inputs=inputs or _inputs(),
    )


def test_profile_map_dimensions_override_zone_dimensions_for_same_zone_ids() -> None:
    inputs = deepcopy(_inputs())
    inputs["model_config"]["movement"]["map_dimensions_yards_by_zone"] = {}
    inputs["model_config"]["movement"]["map_dimensions_yards_by_profile"] = {
        "synthetic-timing": {"width": 5027.0835, "height": 3352.0833}
    }
    cards = {100: _task_card(100, "zero-independent-service")}
    report = _evaluate(_profile(), cards, inputs)
    assert not any(issue["kind"] == "map_dimensions_required" for issue in report["issues"])
    assert report["steps"][0]["components"]["move_seconds"] > 0


def test_unknown_task_rule_never_falls_back_to_default_minutes() -> None:
    profile = _profile()
    report = _evaluate(profile, {100: _task_card(100)})

    assert report["status"] == "requirements"
    assert report["center_minutes"] is None
    assert any(issue["kind"] == "timing_rule_ref_required" for issue in report["issues"])
    assert report["known_seconds"] > 0
    assert not any(row.get("basis") == "historical_default" for row in report["component_rows"])


def test_self_move_with_unknown_coordinates_stays_requirement() -> None:
    profile = _profile()
    profile["geometry"]["locations"]["p2"]["x"] = None
    profile["geometry"]["locations"]["p2"]["y"] = None
    report = _evaluate(profile, {100: _task_card(100, "zero-independent-service")})

    assert report["status"] == "requirements"
    assert report["center_minutes"] is None
    assert "self_move_coordinates_required" in {issue["kind"] for issue in report["issues"]}


def test_hub_base_cost_is_charged_once_per_visit_for_batched_actions() -> None:
    actions = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {"action_id": "a1", "kind": "accept", "task_id": 100, "location_ref": "p1"},
        {"action_id": "a2", "kind": "accept", "task_id": 200, "location_ref": "p1"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
        {"action_id": "o1", "kind": "objective", "task_id": 100, "location_ref": "p2"},
        {"action_id": "o2", "kind": "objective", "task_id": 200, "location_ref": "p2"},
    ]
    profile = _profile(actions=actions)
    cards = {100: _task_card(100, "zero-independent-service"), 200: _task_card(200, "zero-independent-service")}
    report = _evaluate(profile, cards)

    hub_rows = [row for row in report["component_rows"] if row["component"] == "accept_turnin"]
    assert len(hub_rows) == 1
    assert hub_rows[0]["action_ids"] == ["a1", "a2"]
    assert hub_rows[0]["seconds"] == 39.0 + 2 * 9.6


def test_shared_service_is_charged_once_not_once_per_objective() -> None:
    actions = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {"action_id": "a1", "kind": "accept", "task_id": 100, "location_ref": "p1"},
        {"action_id": "a2", "kind": "accept", "task_id": 200, "location_ref": "p1"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
        {"action_id": "o1", "kind": "objective", "task_id": 100, "location_ref": "p2"},
        {"action_id": "o2", "kind": "objective", "task_id": 200, "location_ref": "p2"},
    ]
    profile = _profile(
        actions=actions,
        service_overrides=[{"service_id": "same-pack", "kind": "shared_service", "action_ids": ["o1", "o2"]}],
    )
    inputs = _inputs()
    inputs["profile_action_parameters"]["profiles"]["synthetic-timing"] = {
        "services": {"same-pack": {"seconds": 90.0}}
    }
    cards = {100: _task_card(100), 200: _task_card(200)}
    report = _evaluate(profile, cards, inputs)

    objective_rows = [row for row in report["component_rows"] if row["component"] == "objective_service"]
    shared_rows = [row for row in objective_rows if row.get("service_id") == "same-pack"]
    assert len(shared_rows) == 1
    assert shared_rows[0]["seconds"] == 90.0
    assert not any(row.get("action_id") in {"o1", "o2"} for row in objective_rows)
    assert not any(issue["kind"] == "timing_rule_ref_required" for issue in report["issues"])


def test_background_end_policies_remain_distinct() -> None:
    profile = _profile(
        service_overrides=[
            {
                "service_id": "covered",
                "kind": "background_window",
                "task_id": 100,
                "start_action_id": "a1",
                "end_action_id": "o1",
                "end_policy": "covered_complete",
            },
            {
                "service_id": "fill",
                "kind": "background_window",
                "task_id": 100,
                "start_action_id": "a1",
                "end_action_id": "o1",
                "end_policy": "fill_if_incomplete",
            },
            {
                "service_id": "carry",
                "kind": "background_window",
                "task_id": 100,
                "start_action_id": "a1",
                "end_action_id": "o1",
                "end_policy": "carry_if_incomplete",
            },
        ]
    )
    report = _evaluate(profile, {100: _task_card(100, "zero-independent-service")})

    covered = next(row for row in report["component_rows"] if row.get("service_id") == "covered")
    assert covered["seconds"] == 0.0
    unresolved = {
        issue["service_id"]: issue["end_policy"]
        for issue in report["issues"]
        if issue["kind"] == "background_marginal_timing_input_required"
    }
    assert unresolved == {"fill": "fill_if_incomplete", "carry": "carry_if_incomplete"}


def test_taxi_requires_reviewed_binding_and_leatrix_source() -> None:
    actions = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {"action_id": "tx", "kind": "taxi", "from_name": "A", "to_name": "B"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
    ]
    profile = _profile(actions=actions)
    profile["geometry"]["locations"]["p2"]["incoming_movement"] = {"kind": "action", "action_id": "tx"}
    report = _evaluate(profile, {}, _inputs())

    assert report["center_minutes"] is None
    assert any(issue["kind"] == "flight_edge_binding_required" for issue in report["issues"])

    inputs = _inputs()
    inputs["flight_edge_bindings"]["profiles"]["synthetic-timing"] = {
        "v1->v2": {"faction": "Horde", "world_id": 530, "path_key": "1:2:3:4"}
    }
    report = _evaluate(profile, {}, inputs)
    assert any(issue["kind"] == "leatrix_flight_times_required" for issue in report["issues"])


def test_reviewed_taxi_binding_consumes_exact_imported_leatrix_seconds() -> None:
    actions = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {"action_id": "tx", "kind": "taxi", "from_name": "A", "to_name": "B"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
    ]
    profile = _profile(actions=actions)
    profile["geometry"]["locations"]["p2"]["incoming_movement"] = {"kind": "action", "action_id": "tx"}
    inputs = _inputs()
    inputs["flight_edge_bindings"]["profiles"]["synthetic-timing"] = {
        "v1->v2": {"faction": "Horde", "world_id": 530, "path_key": "1:2:3:4"}
    }
    inputs["leatrix_flight_times"] = {
        "schema_version": 1,
        "source": {"addon": "Leatrix Plus", "addon_version": "test", "zip_sha256": "b" * 64},
        "factions": {
            "Horde": {
                "worlds": {
                    "530": {
                        "1:2:3:4": {"seconds": 123, "raw_comment": "A, B"}
                    }
                }
            }
        },
    }

    report = _evaluate(profile, {}, inputs)

    move_rows = [row for row in report["component_rows"] if row["component"] == "move"]
    assert len(move_rows) == 1
    assert move_rows[0]["edge_id"] == "v1->v2"
    assert move_rows[0]["seconds"] == 123.0
    assert not any(issue["kind"] in {"flight_edge_binding_required", "leatrix_flight_times_required"} for issue in report["issues"])


def test_partial_known_cost_never_becomes_complete_route_center() -> None:
    profile = _profile()
    report = _evaluate(profile, {100: _task_card(100)})

    assert report["known_seconds"] > 0
    assert report["center_minutes"] is None
    assert report["complete"] is False
    assert report["steps"][0]["known_seconds"] > 0
    assert report["steps"][0]["center_minutes"] is None
    assert report["steps"][0]["unresolved_component_count"] > 0


def test_fully_resolved_zero_service_route_can_emit_center() -> None:
    profile = _profile()
    report = _evaluate(profile, {100: _task_card(100, "zero-independent-service")})

    assert report["status"] == "pass"
    assert report["complete"] is True
    assert report["center_minutes"] is not None
    assert report["steps"][0]["center_minutes"] is not None


def test_versioned_task_parameters_can_resolve_rule_inputs() -> None:
    profile = _profile()
    inputs = _inputs()
    inputs["task_parameters"]["tasks"]["100"] = {
        "inputs": {"kill_count": 4},
        "source_refs": ["synthetic-reviewed-evidence"],
    }
    report = _evaluate(profile, {100: _task_card(100, "shared-kill-count")}, inputs)

    assert report["status"] == "pass"
    assert report["steps"][0]["components"]["objective_service_seconds"] == 60.0


def test_effective_quest_source_supplies_baseline_rule_inputs_and_task_config_overrides_it() -> None:
    profile = _profile()
    inputs = _inputs()
    inputs["quest_source_inputs"] = {
        "schema_version": 1,
        "status": "pass",
        "source": {"questie_version": "synthetic", "source_sha256": "a" * 64},
        "tasks": {"100": {"inputs": {"kill_count": 4}, "objectives": [], "issues": []}},
        "issues": [],
    }
    cards = {100: _task_card(100, "shared-kill-count")}

    baseline = _evaluate(profile, cards, inputs)
    assert baseline["steps"][0]["components"]["objective_service_seconds"] == 60.0

    overridden = deepcopy(inputs)
    overridden["task_parameters"]["tasks"]["100"] = {"inputs": {"kill_count": 5}}
    result = _evaluate(profile, cards, overridden)
    assert result["steps"][0]["components"]["objective_service_seconds"] == 75.0


def test_missing_rule_input_stays_requirement_instead_of_using_old_fallback() -> None:
    profile = _profile()
    report = _evaluate(profile, {100: _task_card(100, "shared-kill-count")})

    assert report["status"] == "requirements"
    issue = next(issue for issue in report["issues"] if issue["kind"] == "timing_rule_inputs_required")
    assert issue["missing_inputs"] == ["kill_count"]
    assert report["steps"][0]["components"]["objective_service_seconds"] == 0.0


def test_missing_uncertainty_keeps_point_estimate_but_not_publish_complete() -> None:
    profile = _profile()
    inputs = _inputs()
    inputs["model_config"]["uncertainty"]["component_relative_by_kind"] = {}
    report = _evaluate(profile, {100: _task_card(100, "zero-independent-service")}, inputs)

    assert report["point_estimate_complete"] is True
    assert report["center_minutes"] is not None
    assert report["range_minutes"] is None
    assert report["complete"] is False
    assert report["status"] == "requirements"
    assert any(issue["kind"] == "timing_range_model_required" for issue in report["issues"])


def test_matching_clean_observations_can_supply_range_without_generic_percentage() -> None:
    profile = _profile()
    inputs = _inputs()
    inputs["model_config"]["uncertainty"]["component_relative_by_kind"] = {}
    inputs["timing_observations"] = {
        "schema_version": 1,
        "observation_set_id": "test",
        "observations": [
            {
                "observation_id": "obs-1",
                "profile_id": "synthetic-timing",
                "profile_version": 1,
                "action_scope": {"start_action_id": "v1", "end_action_id": "t1"},
                "actual_minutes": 2.0,
                "calibration_eligible": True,
            },
            {
                "observation_id": "obs-2",
                "profile_id": "synthetic-timing",
                "profile_version": 1,
                "action_scope": {"start_action_id": "v1", "end_action_id": "t1"},
                "actual_minutes": 3.0,
                "calibration_eligible": True,
            },
        ],
    }
    report = _evaluate(profile, {100: _task_card(100, "zero-independent-service")}, inputs)

    assert report["status"] == "pass"
    assert report["range_minutes"] == [2.0, 3.0]
    assert report["range_basis"]["basis"] == "matching_clean_observations"
    assert report["complete"] is True


def test_fingerprint_ignores_unrelated_profile_timing_rows_but_tracks_referenced_task_params() -> None:
    profile = _profile()
    cards = {100: _task_card(100, "shared-kill-count")}
    inputs = _inputs()
    inputs["task_parameters"]["tasks"]["100"] = {"inputs": {"kill_count": 4}}
    base = _evaluate(profile, cards, inputs)["input_fingerprint"]

    unrelated = deepcopy(inputs)
    unrelated["task_parameters"]["tasks"]["999"] = {"inputs": {"kill_count": 999}}
    unrelated["profile_action_parameters"]["profiles"]["other-profile"] = {"actions": {"x": {"seconds": 999}}}
    unrelated["flight_edge_bindings"]["profiles"]["other-profile"] = {"x->y": {"path_key": "1:2"}}
    unrelated["timing_observations"] = {
        "observations": [
            {
                "observation_id": "other",
                "profile_id": "other-profile",
                "profile_version": 1,
                "action_scope": {"start_action_id": "x", "end_action_id": "y"},
                "actual_minutes": 999,
                "calibration_eligible": True,
            }
        ]
    }
    assert _evaluate(profile, cards, unrelated)["input_fingerprint"] == base

    relevant = deepcopy(inputs)
    relevant["task_parameters"]["tasks"]["100"] = {"inputs": {"kill_count": 5}}
    assert _evaluate(profile, cards, relevant)["input_fingerprint"] != base


def test_conditional_hub_cost_consumes_replay_execution_without_rejudging_condition() -> None:
    profile = _profile()
    profile["actions"][-1]["when"] = {"kind": "task_complete", "task_id": 100}
    cards = {100: _task_card(100, "zero-independent-service")}

    executed = _evaluate(profile, cards, action_execution={"t1": "executed"})
    skipped = _evaluate(profile, cards, action_execution={"t1": "skipped"})
    maybe = _evaluate(profile, cards, action_execution={"t1": "maybe"})
    missing = _evaluate(profile, cards)

    executed_hub = sum(
        row["seconds"] for row in executed["component_rows"] if row["component"] == "accept_turnin"
    )
    skipped_hub = sum(
        row["seconds"] for row in skipped["component_rows"] if row["component"] == "accept_turnin"
    )
    assert executed_hub == 97.2
    assert skipped_hub == 48.6
    assert not any(issue["kind"].startswith("conditional_hub_action_") for issue in executed["issues"])
    assert not any(issue["kind"].startswith("conditional_hub_action_") for issue in skipped["issues"])
    assert any(issue["kind"] == "conditional_hub_action_execution_maybe" for issue in maybe["issues"])
    assert any(issue["kind"] == "conditional_hub_action_execution_required" for issue in missing["issues"])


def test_conditional_execution_status_is_part_of_timing_fingerprint() -> None:
    profile = _profile()
    profile["actions"][-1]["when"] = {"kind": "task_complete", "task_id": 100}
    cards = {100: _task_card(100, "zero-independent-service")}

    executed = _evaluate(profile, cards, action_execution={"t1": "executed"})
    skipped = _evaluate(profile, cards, action_execution={"t1": "skipped"})

    assert executed["input_fingerprint"] != skipped["input_fingerprint"]


def _program_timing_fixture():
    first = _profile(
        actions=[
            {"action_id": "v1", "kind": "location", "location_ref": "p1"},
            {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            {"action_id": "leave1", "kind": "fixed_transport", "from_name": "A", "to_name": "B"},
        ]
    )
    first["profile_id"] = "first"
    first["task_ids"] = []

    second = _profile(
        actions=[
            {"action_id": "w1", "kind": "location", "location_ref": "p1"},
        ]
    )
    second["profile_id"] = "second"
    second["task_ids"] = []
    second["scope"]["primary_zone_id"] = 3521
    second["geometry"]["locations"].pop("p2")

    program = {
        "program_id": "synthetic-program",
        "version": 1,
        "entry_state_contract": {"active_task_ids": []},
        "profile_ids": ["first", "second"],
    }
    profiles = {"first": first, "second": second}
    character = {"character_profile_id": "synthetic-fivebox", "party_size": 5}
    replay_inputs = {
        "first": {"task_cards": {}, "character_profile": character},
        "second": {"task_cards": {}, "character_profile": character},
    }
    continuity = evaluate_route_program_continuity(program, profiles, replay_inputs)
    continuity["input_fingerprint"] = "continuity-test"
    movement = evaluate_route_program_movement(program, profiles)
    inputs = _inputs()
    inputs["flight_edge_bindings"]["programs"] = {}
    inputs["profile_action_parameters"]["profiles"]["first"] = {
        "actions": {"leave1": {"seconds": 30.0}},
        "services": {},
    }
    return program, profiles, character, continuity, movement, inputs


def test_program_timing_consumes_program_boundary_and_stage4_execution_context() -> None:
    program, profiles, character, continuity, movement, inputs = _program_timing_fixture()

    report = evaluate_route_program_timing(
        program,
        profiles,
        task_cards_by_profile={"first": {}, "second": {}},
        character_profiles_by_profile={"first": character, "second": character},
        program_movement_report=movement,
        continuity_report=continuity,
        timing_inputs=inputs,
    )

    assert continuity["status"] == "ok"
    assert movement["status"] == "pass"
    assert report["status"] == "pass"
    assert report["point_estimate_complete"] is True
    assert report["complete"] is True
    assert report["center_minutes"] is not None
    assert report["boundary_rows"] == [
        {
            "edge_id": "first->second",
            "from_profile_id": "first",
            "to_profile_id": "second",
            "operation_kind": "fixed_transport",
            "seconds": 30.0,
            "range_minutes": [0.45, 0.55],
            "range_basis": {"basis": "component_relative_uncertainty"},
            "complete": True,
        }
    ]
    assert not any(
        issue["kind"] == "profile_exit_movement_timing_requires_program_context"
        for issue in report["member_reports"]["first"]["issues"]
    )


def test_program_transition_chain_timing_uses_program_operation_calibration() -> None:
    program, profiles, character, _, _, inputs = _program_timing_fixture()
    first = profiles["first"]
    first["actions"] = [row for row in first["actions"] if row["action_id"] != "leave1"]
    first["step_groups"][0]["action_ids"].remove("leave1")
    program["boundary_transitions"] = [
        {
            "from_profile_id": "first",
            "to_profile_id": "second",
            "operations": [
                {
                    "operation_id": "to-hub",
                    "kind": "fixed_transport",
                    "from_name": "B",
                    "to_name": "Hub",
                },
                {
                    "operation_id": "hub-to-second",
                    "kind": "fixed_transport",
                    "from_name": "Hub",
                    "to_name": "B",
                },
            ],
        }
    ]
    replay_inputs = {
        "first": {"task_cards": {}, "character_profile": character},
        "second": {"task_cards": {}, "character_profile": character},
    }
    continuity = evaluate_route_program_continuity(program, profiles, replay_inputs)
    continuity["input_fingerprint"] = "continuity-transition-test"
    movement = evaluate_route_program_movement(program, profiles)
    inputs["profile_action_parameters"]["profiles"] = {}
    inputs["profile_action_parameters"]["programs"] = {
        "synthetic-program": {
            "operations": {
                "to-hub": {"seconds": 12.0},
                "hub-to-second": {"seconds": 18.0},
            }
        }
    }

    report = evaluate_route_program_timing(
        program,
        profiles,
        task_cards_by_profile={"first": {}, "second": {}},
        character_profiles_by_profile={"first": character, "second": character},
        program_movement_report=movement,
        continuity_report=continuity,
        timing_inputs=inputs,
    )

    assert movement["boundaries"][0]["operation_kind"] == "transition_chain"
    assert report["status"] == "pass"
    assert report["boundary_rows"][0]["seconds"] == 30.0


def test_program_transition_chain_missing_calibration_is_explicit_requirement() -> None:
    program, profiles, character, _, _, inputs = _program_timing_fixture()
    first = profiles["first"]
    first["actions"] = [row for row in first["actions"] if row["action_id"] != "leave1"]
    first["step_groups"][0]["action_ids"].remove("leave1")
    program["boundary_transitions"] = [
        {
            "from_profile_id": "first",
            "to_profile_id": "second",
            "operations": [
                {
                    "operation_id": "to-hub",
                    "kind": "fixed_transport",
                    "from_name": "B",
                    "to_name": "Hub",
                }
            ],
        }
    ]
    replay_inputs = {
        "first": {"task_cards": {}, "character_profile": character},
        "second": {"task_cards": {}, "character_profile": character},
    }
    continuity = evaluate_route_program_continuity(program, profiles, replay_inputs)
    continuity["input_fingerprint"] = "continuity-transition-missing-test"
    movement = evaluate_route_program_movement(program, profiles)
    inputs["profile_action_parameters"]["profiles"] = {}
    inputs["profile_action_parameters"]["programs"] = {}

    report = evaluate_route_program_timing(
        program,
        profiles,
        task_cards_by_profile={"first": {}, "second": {}},
        character_profiles_by_profile={"first": character, "second": character},
        program_movement_report=movement,
        continuity_report=continuity,
        timing_inputs=inputs,
    )

    assert report["status"] == "requirements"
    assert report["boundary_rows"][0]["seconds"] is None
    assert any(issue["kind"] == "program_transition_timing_requirements" for issue in report["issues"])


def test_program_boundary_missing_timing_input_keeps_known_member_cost_but_no_center() -> None:
    program, profiles, character, continuity, movement, inputs = _program_timing_fixture()
    inputs["profile_action_parameters"]["profiles"] = {}

    report = evaluate_route_program_timing(
        program,
        profiles,
        task_cards_by_profile={"first": {}, "second": {}},
        character_profiles_by_profile={"first": character, "second": character},
        program_movement_report=movement,
        continuity_report=continuity,
        timing_inputs=inputs,
    )

    assert report["status"] == "requirements"
    assert report["known_seconds"] > 0
    assert report["center_minutes"] is None
    assert report["boundary_rows"][0]["seconds"] is None
    assert any(issue["kind"] == "program_boundary_action_timing_input_required" for issue in report["issues"])


def test_timing_config_validator_rejects_silent_bad_machine_contract() -> None:
    inputs = _inputs()
    inputs["flight_edge_bindings"]["programs"] = {}
    validate_timing_inputs(inputs)

    bad = deepcopy(inputs)
    bad["model_config"]["global"]["combat_seconds_per_mob"] = -1
    bad["flight_edge_bindings"]["profiles"]["bad"] = {
        "a->b": {"faction": "Neutral", "world_id": 1, "path_key": ""}
    }

    with pytest.raises(TimingConfigError) as exc:
        validate_timing_inputs(bad)

    text = str(exc.value)
    assert "combat_seconds_per_mob" in text
    assert "flight binding faction invalid" in text
    assert "flight binding path_key missing" in text
