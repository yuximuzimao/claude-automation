from __future__ import annotations

from copy import deepcopy

from lib.route_movement import evaluate_profile_movement
from lib.route_service_context import evaluate_profile_service_context


def _loc(name: str, *, incoming=None):
    row = {"display_name": name, "x": 10.0, "y": 20.0}
    if incoming is not None:
        row["incoming_movement"] = incoming
    return row


def _profile(*, service_overrides=None):
    profile = {
        "profile_id": "synthetic-service",
        "version": 1,
        "scope": {
            "route_scope": "synthetic",
            "character_profile": "synthetic",
            "game_variant_id": "timewalking-wotlk-cn",
            "primary_zone_id": 3483,
        },
        "actions": [
            {"action_id": "v1", "kind": "location", "location_ref": "p1"},
            {"action_id": "a1", "kind": "accept", "task_id": 100, "location_ref": "p1"},
            {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            {"action_id": "o1", "kind": "objective", "task_id": 100, "location_ref": "p2"},
            {"action_id": "o2", "kind": "objective", "task_id": 200, "location_ref": "p2"},
            {"action_id": "v3", "kind": "location", "location_ref": "p3"},
            {"action_id": "o3", "kind": "objective", "task_id": 100, "location_ref": "p3"},
            {"action_id": "t1", "kind": "turnin", "task_id": 100, "location_ref": "p3"},
        ],
        "geometry": {
            "locations": {
                "p1": _loc("A"),
                "p2": _loc("B", incoming={"kind": "self_move", "mode": "ride"}),
                "p3": _loc("C", incoming={"kind": "self_move", "mode": "ride"}),
            }
        },
    }
    if service_overrides is not None:
        profile["service_overrides"] = service_overrides
    return profile


def test_objective_actions_become_foreground_services_without_auto_sharing() -> None:
    profile = _profile()
    movement = evaluate_profile_movement(profile)
    report = evaluate_profile_service_context(profile, movement)

    assert report["status"] == "pass"
    assert [row["service_action_id"] for row in report["foreground_services"]] == ["o1", "o2", "o3"]
    assert {row["cluster_id"] for row in report["target_clusters"]} == {
        "objective-o1",
        "objective-o2",
        "objective-o3",
    }
    p2_instance = next(row for row in report["spatial_instances"] if row["visit_id"] == "v2")
    assert p2_instance["cluster_ids"] == ["objective-o1", "objective-o2"]


def test_shared_service_requires_explicit_override_and_merges_same_visit_actions() -> None:
    profile = _profile(
        service_overrides=[
            {
                "service_id": "same-target",
                "kind": "shared_service",
                "action_ids": ["o1", "o2"],
            }
        ]
    )
    report = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))

    assert report["status"] == "pass"
    cluster = next(row for row in report["target_clusters"] if row["cluster_id"] == "same-target")
    assert cluster["action_ids"] == ["o1", "o2"]
    assert cluster["task_ids"] == [100, 200]
    assert cluster["visit_ids"] == ["v2"]


def test_shared_service_cannot_claim_zero_cost_overlap_across_different_visits() -> None:
    profile = _profile(
        service_overrides=[
            {
                "service_id": "bad-cross-visit-share",
                "kind": "shared_service",
                "action_ids": ["o1", "o3"],
            }
        ]
    )
    report = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))

    assert report["status"] == "blocked"
    assert any(issue["kind"] == "shared_service_spans_multiple_visits" for issue in report["issues"])


def test_background_window_preserves_coverage_range_and_end_policy() -> None:
    profile = _profile(
        service_overrides=[
            {
                "service_id": "background-100",
                "kind": "background_window",
                "task_id": 100,
                "start_action_id": "a1",
                "end_action_id": "o3",
                "end_policy": "fill_if_incomplete",
            }
        ]
    )
    report = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))

    layer = report["background_layers"][0]
    assert layer["task_id"] == 100
    assert layer["end_policy"] == "fill_if_incomplete"
    assert layer["foreground_objective_action_ids"] == ["o1", "o3"]
    assert layer["visit_ids"] == ["v2", "v3"]


def test_background_policy_can_express_carry_or_zero_extra_service_without_fake_objective() -> None:
    profile = _profile(
        service_overrides=[
            {
                "service_id": "carry-100",
                "kind": "background_window",
                "task_id": 100,
                "start_action_id": "a1",
                "end_action_id": "v2",
                "end_policy": "carry_if_incomplete",
            },
            {
                "service_id": "covered-200",
                "kind": "background_window",
                "task_id": 200,
                "start_action_id": "v2",
                "end_action_id": "v3",
                "end_policy": "covered_complete",
            },
        ]
    )
    report = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))

    assert report["status"] == "pass"
    policies = {row["service_id"]: row["end_policy"] for row in report["background_layers"]}
    assert policies == {"carry-100": "carry_if_incomplete", "covered-200": "covered_complete"}


def test_stage6_fingerprint_changes_when_only_route_service_decision_changes() -> None:
    profile = _profile()
    base = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))
    changed = deepcopy(profile)
    changed["service_overrides"] = [
        {
            "service_id": "background-100",
            "kind": "background_window",
            "task_id": 100,
            "start_action_id": "a1",
            "end_action_id": "o3",
            "end_policy": "fill_if_incomplete",
        }
    ]
    changed_report = evaluate_profile_service_context(changed, evaluate_profile_movement(changed))

    assert changed_report["input_fingerprint"] != base["input_fingerprint"]
