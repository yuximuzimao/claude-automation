from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from lib.route_movement import evaluate_profile_movement
from lib.route_profiles import load_route_profile, validate_route_profile
from lib.route_service_context import evaluate_profile_service_context
from scripts.rebuild_route_profile import audit_profile


FIXTURE = Path(__file__).parent / "fixtures" / "stage6-service-migration-expected.json"


def _expected() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_stage6_predeclared_real_service_migration_binds_without_prose_inference() -> None:
    expected = _expected()
    assert expected["schema"] == "stage6-service-migration-expected/v1"

    for profile_id, overrides in expected["profiles"].items():
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        assert profile.get("service_overrides") == overrides
        candidate = deepcopy(profile)
        candidate["service_overrides"] = deepcopy(overrides)
        validate_route_profile(candidate, expected_profile_id=profile_id, known_task_cards=None)

        report = evaluate_profile_service_context(candidate, evaluate_profile_movement(candidate))
        actual_background = {row["service_id"]: row for row in report["background_layers"]}
        actual_clusters = {row["cluster_id"]: row for row in report["target_clusters"]}

        for override in overrides:
            if override["kind"] == "background_window":
                row = actual_background[override["service_id"]]
                assert row["task_id"] == override["task_id"]
                assert row["start_action_id"] == override["start_action_id"]
                assert row["end_action_id"] == override["end_action_id"]
                assert row["end_policy"] == override["end_policy"]
            else:
                row = actual_clusters[override["service_id"]]
                assert row["action_ids"] == override["action_ids"]
                assert len(row["visit_ids"]) == 1


def test_multistage_objective_service_stays_derived_without_route_only_override() -> None:
    profile = load_route_profile("zuldrak-fivebox", validate=True, validate_task_cards=False)
    report = evaluate_profile_service_context(profile, evaluate_profile_movement(profile))
    service_actions = [
        row["service_action_id"] for row in report["foreground_services"] if row["task_id"] == 12914
    ]

    assert service_actions == ["a0044", "a0050"]
    assert not any(
        row.get("task_id") == 12914
        for row in profile.get("service_overrides") or []
        if row["kind"] == "background_window"
    )


def test_stage6_is_wired_into_the_single_rebuild_pipeline() -> None:
    report = audit_profile("zangarmarsh-fivebox")
    stage6 = report["stages"][5]

    assert stage6["name"] == "service_context"
    assert stage6["implementation_status"] == "implemented"
    assert stage6["evaluation_status"] in {"requirements", "blocked", "pass"}
    assert "service_context" not in report["unimplemented_stages"]
