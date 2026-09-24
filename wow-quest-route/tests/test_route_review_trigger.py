from __future__ import annotations

from copy import deepcopy

from lib.route_review_trigger import evaluate_review_trigger, load_review_trigger_config


def _upstream(status: str = "pass") -> dict[str, str]:
    return {
        "cross_profile_continuity": status,
        "canonical_spatial_movement": status,
        "service_context": status,
        "derived_timing": status,
        "derived_xp": status,
        "derived_economy": status,
    }


def _profile_context(events: list[dict] | None = None, *, version: int = 1, coverage: str = "complete") -> dict:
    return {
        "schema_version": 1,
        "profiles": {
            "hellfire-dk-speed": {
                "profile_version": version,
                "coverage": coverage,
                "source_ref": "fixture-review-context",
                "events": events or [],
            }
        },
    }


def test_review_trigger_config_matches_owner_machine_ids() -> None:
    config = load_review_trigger_config()
    assert config["diagnoses"] == ["no_review", "selection_review", "optimization_review", "blocked_unknown"]
    assert config["selection_trigger_ids"] == [
        "user_selection_request",
        "task_fact_cost_or_benefit_changed",
        "live_run_cost_or_variance_anomaly",
        "route_overlap_structure_changed",
        "xp_gap_or_redundancy",
        "availability_changed",
        "profile_goal_or_scope_changed",
        "recalled_or_new_task",
    ]
    assert config["optimization_validator_ids"] == [
        "player_state",
        "quest_prerequisite",
        "availability",
        "objective_ready",
        "xp_deadline",
        "transport",
        "branch_state",
        "fivebox_mechanic",
        "spatial_service",
        "background_capacity",
        "no_dead_step",
        "trigger_source_ready",
        "state_continuity",
        "map_transition_contract",
    ]


def test_missing_review_context_is_blocked_unknown_not_silent_no_review() -> None:
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=None,
    )
    assert report["diagnoses"] == ["blocked_unknown"]
    assert report["status"] == "requirements"
    assert {issue["kind"] for issue in report["issues"]} == {"review_context_required"}


def test_explicit_complete_empty_context_is_the_only_no_review_path() -> None:
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=_profile_context(),
    )
    assert report["diagnoses"] == ["no_review"]
    assert report["status"] == "pass"
    assert report["issues"] == []


def test_real_hellfire_live_anomaly_routes_to_selection_review_without_deciding_task_fate() -> None:
    review_input = _profile_context(
        [
            {
                "event_id": "2026-09-17-dirty-work-live-anomaly",
                "kind": "selection_trigger",
                "trigger_id": "live_run_cost_or_variance_anomaly",
                "task_ids": [10629],
                "action_ids": [],
                "source_ref": "tasks/todo.md:2026-09-17 hellfire live feedback; user abandoned 肮脏的工作 as too difficult",
            }
        ]
    )
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=review_input,
    )
    assert report["diagnoses"] == ["selection_review"]
    assert report["status"] == "requirements"
    event = report["selection_events"][0]
    assert event["task_ids"] == [10629]
    assert "decision" not in report
    assert "now" not in report and "later" not in report and "never" not in report


def test_hard_validator_fail_routes_to_optimization_review_not_task_deletion() -> None:
    review_input = _profile_context(
        [
            {
                "event_id": "transport-placement-fail",
                "kind": "optimization_validator",
                "validator_id": "transport",
                "result": "FAIL",
                "task_ids": [],
                "action_ids": ["move:test"],
                "source_ref": "fixture-hard-validator",
            }
        ]
    )
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=review_input,
    )
    assert report["diagnoses"] == ["optimization_review"]
    assert report["status"] == "requirements"
    assert report["optimization_failures"][0]["validator_id"] == "transport"
    assert "delete_task_ids" not in report


def test_hard_validator_unknown_is_fail_closed() -> None:
    review_input = _profile_context(
        [
            {
                "event_id": "unknown-background-capacity",
                "kind": "optimization_validator",
                "validator_id": "background_capacity",
                "result": "UNKNOWN",
                "task_ids": [10629],
                "action_ids": [],
                "source_ref": "fixture-hard-validator",
            }
        ]
    )
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=review_input,
    )
    assert report["diagnoses"] == ["blocked_unknown"]
    assert report["status"] == "requirements"
    assert "optimization_validator_unknown" in {issue["kind"] for issue in report["issues"]}


def test_upstream_nonfresh_state_blocks_review_conclusion_even_with_complete_context() -> None:
    statuses = _upstream()
    statuses["derived_timing"] = "requirements"
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=statuses,
        review_input=_profile_context(),
    )
    assert report["diagnoses"] == ["blocked_unknown"]
    assert report["status"] == "requirements"

    statuses["derived_timing"] = "blocked"
    blocked = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=statuses,
        review_input=_profile_context(),
    )
    assert blocked["diagnoses"] == ["blocked_unknown"]
    assert blocked["status"] == "blocked"


def test_stale_review_context_does_not_apply_to_new_profile_version() -> None:
    stale_input = _profile_context(
        [
            {
                "event_id": "stale-selection-event",
                "kind": "selection_trigger",
                "trigger_id": "live_run_cost_or_variance_anomaly",
                "task_ids": [10629],
                "action_ids": [],
                "source_ref": "old-version-live-run",
            }
        ],
        version=1,
    )
    report = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=2,
        upstream_statuses=_upstream(),
        review_input=stale_input,
    )
    assert report["diagnoses"] == ["blocked_unknown"]
    assert report["status"] == "requirements"
    assert report["selection_events"] == []
    assert report["optimization_failures"] == []
    assert "stale_review_context" in {issue["kind"] for issue in report["issues"]}


def test_fingerprint_changes_with_review_event() -> None:
    base = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=_upstream(),
        review_input=_profile_context(),
    )
    changed_input = _profile_context(
        [
            {
                "event_id": "new-task",
                "kind": "selection_trigger",
                "trigger_id": "recalled_or_new_task",
                "task_ids": [99999],
                "action_ids": [],
                "source_ref": "fixture-new-task",
            }
        ]
    )
    changed = evaluate_review_trigger(
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        upstream_statuses=deepcopy(_upstream()),
        review_input=changed_input,
    )
    assert base["input_fingerprint"] != changed["input_fingerprint"]


def test_program_context_is_version_bound_independently_from_profile_context() -> None:
    review_input = {
        "schema_version": 1,
        "programs": {
            "fixture-program": {
                "program_version": 3,
                "coverage": "complete",
                "source_ref": "fixture-program-review",
                "events": [],
            }
        },
    }
    report = evaluate_review_trigger(
        target_kind="program",
        target_id="fixture-program",
        target_version=3,
        upstream_statuses=_upstream(),
        review_input=review_input,
    )
    assert report["diagnoses"] == ["no_review"]
    assert report["status"] == "pass"
