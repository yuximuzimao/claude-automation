from __future__ import annotations

from copy import deepcopy

import pytest

from lib.route_service_context import (
    apply_approved_service_override_review,
    build_service_override_review,
)


def _profile() -> dict:
    return {
        "profile_id": "synthetic-service-migration",
        "version": 4,
        "scope": {"primary_zone_id": 3483},
        "task_ids": [100],
        "actions": [
            {"action_id": "v1", "kind": "location", "location_ref": "p1"},
            {"action_id": "a1", "kind": "accept", "task_id": 100, "location_ref": "p1"},
            {"action_id": "v2", "kind": "location", "location_ref": "p2"},
            {"action_id": "o1", "kind": "objective", "task_id": 100, "location_ref": "p2"},
        ],
        "geometry": {"locations": {"p1": {"display_name": "A", "x": 1, "y": 1}, "p2": {"display_name": "B", "x": 2, "y": 2}}},
    }


def _proposal() -> list[dict]:
    return [
        {
            "service_id": "background-100",
            "kind": "background_window",
            "task_id": 100,
            "start_action_id": "a1",
            "end_action_id": "o1",
            "end_policy": "fill_if_incomplete",
        }
    ]


def test_service_migration_review_never_auto_approves_explicit_proposal() -> None:
    profile = _profile()
    review = build_service_override_review(profile, _proposal())

    assert review["schema"] == "route-service-override-review/v1"
    assert review["profile_version"] == 4
    assert len(review["base_fingerprint"]) == 64
    assert review["rows"][0]["approved"] is False
    assert review["rows"][0]["override"] == _proposal()[0]

    unchanged = apply_approved_service_override_review(profile, review)
    assert "service_overrides" not in unchanged


def test_approved_service_review_applies_only_after_explicit_approval() -> None:
    profile = _profile()
    review = build_service_override_review(profile, _proposal())
    review["rows"][0]["approved"] = True

    updated = apply_approved_service_override_review(profile, review)
    assert updated["service_overrides"] == _proposal()
    assert "service_overrides" not in profile


def test_service_review_becomes_stale_when_non_service_profile_truth_changes() -> None:
    profile = _profile()
    review = build_service_override_review(profile, _proposal())
    review["rows"][0]["approved"] = True
    changed = deepcopy(profile)
    changed["actions"][3]["location_ref"] = "p1"

    with pytest.raises(ValueError, match="base fingerprint is stale"):
        apply_approved_service_override_review(changed, review)


def test_existing_service_overrides_do_not_invalidate_same_review_base() -> None:
    profile = _profile()
    review = build_service_override_review(profile, _proposal())
    current = deepcopy(profile)
    current["service_overrides"] = [
        {
            "service_id": "old",
            "kind": "background_window",
            "task_id": 100,
            "start_action_id": "a1",
            "end_action_id": "a1",
            "end_policy": "carry_if_incomplete",
        }
    ]
    review["rows"][0]["approved"] = True

    updated = apply_approved_service_override_review(current, review)
    assert updated["service_overrides"] == _proposal()
