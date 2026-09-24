from __future__ import annotations

import lib.route_movement as route_movement
from lib.route_movement import (
    evaluate_profile_movement,
    evaluate_route_program_movement,
    program_member_movement_report,
)


def _profile(actions, locations, *, primary_zone_id=3483):
    scope = {
        "route_scope": "synthetic",
        "character_profile": "synthetic",
        "game_variant_id": "timewalking-wotlk-cn",
    }
    if primary_zone_id is not None:
        scope["primary_zone_id"] = primary_zone_id
    return {
        "profile_id": "synthetic-route",
        "version": 1,
        "scope": scope,
        "actions": actions,
        "geometry": {"locations": locations},
    }


def _loc(name, *, incoming=None, zone_id=None, legacy=None):
    row = {"display_name": name, "x": 10.0, "y": 20.0}
    if incoming is not None:
        row["incoming_movement"] = incoming
    if zone_id is not None:
        row["zone_id"] = zone_id
    if legacy is not None:
        row["transport"] = legacy
    return row


def test_canonical_self_move_uses_visit_incoming_edge_and_primary_zone() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("A"),
                "p2": _loc("B", incoming={"kind": "self_move", "mode": "ride"}),
            },
        )
    )

    assert result["status"] == "pass"
    assert result["canonical_edge_count"] == 1
    assert result["migration_candidate_count"] == 0
    edge = result["edges"][0]
    assert edge["operation_kind"] == "self_move"
    assert edge["movement_mode"] == "ride"
    assert edge["cross_zone"] is False
    assert edge["from_zone_id"] == 3483
    assert edge["to_zone_id"] == 3483


def test_canonical_self_move_without_mode_defaults_to_ground_mount() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("A"),
                "p2": _loc("B", incoming={"kind": "self_move"}),
            },
        )
    )

    assert result["status"] == "pass"
    assert result["edges"][0]["movement_mode"] == "ride"
    assert result["edges"][0]["movement_mode_source"] == "default_ground_mount"


def test_canonical_explicit_action_edge_references_action_without_copying_kind() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "taxi", "from_name": "A", "to_name": "B"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("A"),
                "p2": _loc("B", incoming={"kind": "action", "action_id": "m1"}),
            },
        )
    )

    assert result["status"] == "pass"
    edge = result["edges"][0]
    assert edge["movement_action_id"] == "m1"
    assert edge["operation_kind"] == "taxi"
    assert edge["source"] == "canonical_profile"


def test_cross_zone_is_derived_from_visit_zones_not_a_transport_mode() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "fixed_transport", "from_name": "A", "to_name": "C"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("A"),
                "p2": _loc("C", zone_id=4, incoming={"kind": "action", "action_id": "m1"}),
            },
        )
    )

    assert result["status"] == "pass"
    edge = result["edges"][0]
    assert edge["operation_kind"] == "fixed_transport"
    assert edge["cross_zone"] is True


def test_unknown_location_coordinates_are_explicit_requirement_not_fake_position() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "fixed_transport", "from_name": "A", "to_name": "B"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("A"),
                "p2": {
                    "display_name": "B",
                    "x": None,
                    "y": None,
                    "incoming_movement": {"kind": "action", "action_id": "m1"},
                },
            },
        )
    )

    assert result["status"] == "requirements"
    assert result["visits"][1]["x"] is None
    assert result["visits"][1]["y"] is None
    assert any(issue["kind"] == "location_coordinates_unknown" for issue in result["issues"])
    assert result["edges"][0]["operation_kind"] == "fixed_transport"


def test_transition_context_does_not_require_map_coordinates() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "quest_transport", "from_name": "A", "to_name": "Transient"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
                {"action_id": "m2", "kind": "fixed_transport", "from_name": "Transient", "to_name": "B"},
                {"action_id": "v3", "kind": "location", "location_ref": "p3"},
            ],
            {
                "p1": _loc("A"),
                "p2": {
                    "display_name": "Transient",
                    "location_role": "transition_context",
                    "x": None,
                    "y": None,
                    "incoming_movement": {"kind": "action", "action_id": "m1"},
                },
                "p3": _loc("B", incoming={"kind": "action", "action_id": "m2"}),
            },
        )
    )

    assert result["status"] == "pass"
    assert result["visits"][1]["location_role"] == "transition_context"
    assert result["visits"][1]["x"] is None
    assert not any(issue["kind"] == "location_coordinates_unknown" for issue in result["issues"])


def test_missing_incoming_defaults_to_autonomous_ground_move() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {"p1": _loc("A"), "p2": _loc("B")},
        )
    )

    assert result["status"] == "pass"
    edge = result["edges"][0]
    assert edge["source"] == "default_autonomous_move"
    assert edge["operation_kind"] == "self_move"
    assert edge["movement_mode"] == "ride"
    assert edge["movement_mode_source"] == "default_ground_mount"


def test_legacy_self_move_hint_is_accepted_without_forcing_profile_annotation() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {"p1": _loc("A"), "p2": _loc("B", legacy="fly")},
        )
    )

    assert result["status"] == "pass"
    edge = result["edges"][0]
    assert edge["source"] == "default_autonomous_move"
    assert edge["operation_kind"] == "self_move"
    assert edge["movement_mode"] == "fly"
    assert edge["movement_mode_source"] == "legacy_hint"


def test_legacy_special_line_style_cannot_invent_player_operation() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {"p1": _loc("A"), "p2": _loc("B", legacy="hearth")},
        )
    )

    assert result["status"] == "requirements"
    assert result["edges"][0]["operation_kind"] == "unknown"
    assert any(issue["kind"] == "legacy_transport_requires_operation_review" for issue in result["issues"])


def test_compound_movement_between_two_visits_requires_visit_split() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "taxi", "from_name": "A", "to_name": "B"},
                {"action_id": "m2", "kind": "fixed_transport", "from_name": "B", "to_name": "C"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {"p1": _loc("A"), "p2": _loc("C", legacy="crossmap")},
        )
    )

    assert result["status"] == "blocked"
    assert any(issue["kind"] == "compound_movement_requires_visit_split" for issue in result["issues"])


def test_move_action_without_mode_defaults_to_ground_self_move() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "m1", "kind": "move", "to_name": "洞穴内部"},
                {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            ],
            {
                "p1": _loc("洞口"),
                "p2": _loc("洞内", incoming={"kind": "action", "action_id": "m1"}),
            },
        )
    )

    assert result["status"] == "pass"
    assert result["edges"][0]["movement_mode"] == "ride"
    assert result["edges"][0]["movement_mode_source"] == "default_ground_mount"


def test_reusing_one_location_ref_for_multiple_visits_is_ambiguous() -> None:
    result = evaluate_profile_movement(
        _profile(
            [
                {"action_id": "v1", "kind": "location", "location_ref": "p1"},
                {"action_id": "v2", "kind": "location", "location_ref": "p1"},
            ],
            {"p1": _loc("同一营地", incoming={"kind": "self_move", "mode": "ride"})},
        )
    )

    assert result["status"] == "blocked"
    assert any(issue["kind"] == "location_ref_reused_across_visits" for issue in result["issues"])


def _program_profiles(*, boundary_kind: str):
    first_locations = {
        "a1": _loc("A"),
        "a2": _loc("边界A", incoming={"kind": "self_move", "mode": "ride"}),
    }
    second_locations = {"b1": _loc("边界B")}
    if boundary_kind == "handoff":
        first_locations["a2"]["handoff_ref"] = "shared-border"
        second_locations["b1"]["handoff_ref"] = "shared-border"

    first_actions = [
        {"action_id": "av1", "kind": "location", "location_ref": "a1"},
        {"action_id": "av2", "kind": "location", "location_ref": "a2"},
    ]
    if boundary_kind == "action":
        first_actions.append(
            {
                "action_id": "leave1",
                "kind": "fixed_transport",
                "from_name": "边界A",
                "to_name": "边界B",
            }
        )
    elif boundary_kind == "compound":
        first_actions.extend(
            [
                {"action_id": "leave1", "kind": "taxi", "from_name": "A", "to_name": "X"},
                {"action_id": "leave2", "kind": "fixed_transport", "from_name": "X", "to_name": "B"},
            ]
        )

    first = _profile(first_actions, first_locations)
    first["profile_id"] = "first"
    second = _profile(
        [{"action_id": "bv1", "kind": "location", "location_ref": "b1"}],
        second_locations,
        primary_zone_id=3521,
    )
    second["profile_id"] = "second"
    program = {"program_id": "synthetic-program", "version": 1, "profile_ids": ["first", "second"]}
    return program, {"first": first, "second": second}


def test_program_boundary_binds_one_source_exit_action_to_next_first_visit() -> None:
    program, profiles = _program_profiles(boundary_kind="action")
    result = evaluate_route_program_movement(program, profiles)

    boundary = result["boundaries"][0]
    assert boundary["status"] == "pass"
    assert boundary["source"] == "profile_exit_action"
    assert boundary["movement_action_id"] == "leave1"
    assert boundary["operation_kind"] == "fixed_transport"
    assert boundary["cross_zone"] is True
    assert not any(issue["kind"] == "profile_exit_movement_requires_program_boundary" for issue in result["issues"])


def test_program_boundary_allows_explicit_shared_natural_handoff() -> None:
    program, profiles = _program_profiles(boundary_kind="handoff")
    result = evaluate_route_program_movement(program, profiles)

    boundary = result["boundaries"][0]
    assert boundary["status"] == "pass"
    assert boundary["source"] == "shared_handoff_ref"
    assert boundary["operation_kind"] == "handoff"
    assert boundary["handoff_ref"] == "shared-border"


def test_program_boundary_transition_chain_is_program_owned_truth() -> None:
    program, profiles = _program_profiles(boundary_kind="missing")
    program["boundary_transitions"] = [
        {
            "from_profile_id": "first",
            "to_profile_id": "second",
            "operations": [
                {
                    "operation_id": "to-hub",
                    "kind": "fixed_transport",
                    "from_name": "边界A",
                    "to_name": "中转Hub",
                },
                {
                    "operation_id": "to-b",
                    "kind": "move",
                    "from_name": "中转Hub",
                    "to_name": "边界B",
                    "movement_mode": "ride",
                },
            ],
        }
    ]

    result = evaluate_route_program_movement(program, profiles)
    boundary = result["boundaries"][0]
    assert boundary["status"] == "pass"
    assert boundary["source"] == "program_transition"
    assert boundary["operation_kind"] == "transition_chain"
    assert [row["operation_id"] for row in boundary["operations"]] == ["to-hub", "to-b"]


def test_program_boundary_transition_chain_rejects_double_truth() -> None:
    program, profiles = _program_profiles(boundary_kind="action")
    program["boundary_transitions"] = [
        {
            "from_profile_id": "first",
            "to_profile_id": "second",
            "operations": [
                {
                    "operation_id": "program-leave",
                    "kind": "fixed_transport",
                    "from_name": "边界A",
                    "to_name": "边界B",
                }
            ],
        }
    ]
    result = evaluate_route_program_movement(program, profiles)
    assert result["status"] == "blocked"
    assert any(
        issue["kind"] == "program_boundary_transition_conflicts_with_profile_exit"
        for issue in result["issues"]
    )


def test_program_order_alone_does_not_prove_cross_profile_transition() -> None:
    program, profiles = _program_profiles(boundary_kind="missing")
    result = evaluate_route_program_movement(program, profiles)

    assert result["status"] == "requirements"
    assert result["boundaries"][0]["operation_kind"] == "unknown"
    assert any(issue["kind"] == "program_boundary_transition_unproven" for issue in result["issues"])


def test_program_boundary_with_multiple_exit_movements_requires_visit_split() -> None:
    program, profiles = _program_profiles(boundary_kind="compound")
    result = evaluate_route_program_movement(program, profiles)

    assert result["status"] == "blocked"
    assert any(issue["kind"] == "compound_program_boundary_requires_visit_split" for issue in result["issues"])


def test_program_member_view_routes_exit_boundary_requirement_without_erasing_other_stage5_issues() -> None:
    program, profiles = _program_profiles(boundary_kind="action")
    raw = evaluate_route_program_movement(program, profiles)
    member = program_member_movement_report(raw, "first")

    assert member["program_context"]["program_id"] == "synthetic-program"
    assert member["program_context"]["boundary_edge_id"] == "first->second"
    assert member["exit_movement_actions"] == []
    assert not any(issue["kind"] == "profile_exit_movement_requires_program_boundary" for issue in member["issues"])
    assert member["input_fingerprint"] != raw["member_reports"]["first"]["input_fingerprint"]

    final_member = program_member_movement_report(raw, "second")
    assert "program_context" not in final_member
    assert final_member["input_fingerprint"] == raw["member_reports"]["second"]["input_fingerprint"]


def test_program_movement_uses_supplied_member_reports_without_recomputing(monkeypatch) -> None:
    program, profiles = _program_profiles(boundary_kind="action")
    member_reports = {
        profile_id: evaluate_profile_movement(profile)
        for profile_id, profile in profiles.items()
    }

    def _unexpected_recompute(_profile):
        raise AssertionError("Program Movement must consume supplied member artifacts")

    monkeypatch.setattr(route_movement, "evaluate_profile_movement", _unexpected_recompute)
    result = route_movement.evaluate_route_program_movement(
        program,
        profiles,
        member_reports=member_reports,
    )

    assert result["member_reports"] == member_reports
    assert result["boundaries"][0]["status"] == "pass"
