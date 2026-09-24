from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from lib.route_movement import evaluate_profile_movement, evaluate_route_program_movement
from lib.route_profiles import load_all_route_profiles, load_route_profile
from lib.route_programs import load_all_route_programs
from scripts.rebuild_route_profile import audit_profile


FIXTURE = Path(__file__).parent / "fixtures" / "stage5-pre-migration-expected.json"


def _expected() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_stage5_frozen_real_hellfire_dk_pre_migration_expected_outcome() -> None:
    expected = _expected()["profile"]
    profile = load_route_profile(expected["profile_id"], validate=True, validate_task_cards=False)
    report = evaluate_profile_movement(profile)

    assert profile["version"] == expected["profile_version"]
    assert report["status"] == expected["status"]
    assert len(report["visits"]) == expected["visit_count"]
    assert len(report["edges"]) == expected["edge_count"]
    assert report["canonical_edge_count"] == expected["canonical_edge_count"]
    assert report["migration_candidate_count"] == expected["migration_candidate_count"]
    assert report["unresolved_edge_count"] == expected["unresolved_edge_count"]
    assert [row["action_id"] for row in report["exit_movement_actions"]] == expected["exit_movement_action_ids"]
    assert Counter(issue["kind"] for issue in report["issues"]) == expected["issue_counts"]

    compound = {
        issue["edge_id"]: issue["movement_action_ids"]
        for issue in report["issues"]
        if issue["kind"] == "compound_movement_requires_visit_split"
    }
    assert compound == expected["compound_edges"]


def test_stage5_frozen_real_program_boundaries_pre_migration_expected_outcome() -> None:
    expected = _expected()["program"]
    program = load_all_route_programs()[expected["program_id"]]
    profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
    report = evaluate_route_program_movement(program, profiles)

    assert len(report["profile_ids"]) == expected["profile_count"]
    assert len(report["boundaries"]) == expected["boundary_count"]
    assert report["status"] == expected["status"]
    assert Counter(issue["kind"] for issue in report["issues"]) == expected["issue_counts"]
    assert Counter(row["status"] for row in report["boundaries"]) == expected["boundary_status_counts"]

    proved = expected["proved_boundary"]
    boundary = next(row for row in report["boundaries"] if row["edge_id"] == proved["edge_id"])
    assert boundary["source"] == proved["source"]
    assert boundary["operation_kind"] == proved["operation_kind"]
    assert boundary["status"] == "pass"

    compound = expected["compound_boundary"]
    boundary = next(row for row in report["boundaries"] if row["edge_id"] == compound["edge_id"])
    assert any(issue["kind"] == compound["issue_kind"] for issue in boundary["issues"])


def test_stage5_implementation_readiness_is_independent_from_current_migration_state() -> None:
    report = audit_profile("hellfire-fivebox")
    stage5 = report["stages"][4]

    assert stage5["name"] == "canonical_spatial_movement"
    assert stage5["implementation_status"] == "implemented"
    assert stage5["evaluation_status"] == "blocked"
    assert stage5["publish_gate_applies"] is True
    assert "canonical_spatial_movement" in report["artifact_blocked_stages"]
    assert "canonical_spatial_movement" not in report["unimplemented_stages"]
