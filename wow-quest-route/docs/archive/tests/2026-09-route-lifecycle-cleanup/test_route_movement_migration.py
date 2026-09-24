from __future__ import annotations

from copy import deepcopy
import json

import pytest
import scripts.migrate_route_profile_movement as movement_script

from lib.route_movement import apply_approved_movement_review, build_movement_migration_review
from scripts.migrate_route_profile_movement import (
    approve_mechanical_candidates,
    approve_primary_zones_from_map_manifest,
    build_reviews,
)


def _profile() -> dict:
    return {
        "profile_id": "synthetic-movement-migration",
        "version": 3,
        "scope": {
            "route_scope": "synthetic",
            "character_profile": "synthetic",
            "game_variant_id": "timewalking-wotlk-cn",
        },
        "actions": [
            {"action_id": "v1", "kind": "location", "location_ref": "p1"},
            {"action_id": "v2", "kind": "location", "location_ref": "p2"},
        ],
        "geometry": {
            "locations": {
                "p1": {"display_name": "A", "x": 10.0, "y": 20.0, "transport": "ride"},
                "p2": {"display_name": "B", "x": 20.0, "y": 30.0, "transport": "fly"},
            }
        },
    }


def _leading_hearth_profile() -> dict:
    profile = _profile()
    profile["scope"]["primary_zone_id"] = 3483
    profile["actions"] = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
        {
            "action_id": "h1",
            "kind": "use_hearth",
            "location_ref": "p2",
            "target_name": "B",
        },
        {"action_id": "v3", "kind": "location", "location_ref": "p3"},
    ]
    profile["geometry"]["locations"] = {
        "p1": {"display_name": "A", "x": 10.0, "y": 20.0, "transport": "ride"},
        "p2": {"display_name": "B", "x": 20.0, "y": 30.0, "transport": "hearth"},
        "p3": {
            "display_name": "C",
            "x": 30.0,
            "y": 40.0,
            "transport": "ride",
            "incoming_movement": {"kind": "action", "action_id": "h1"},
        },
    }
    profile["step_groups"] = [
        {"step_id": "step-01", "action_ids": ["v1", "v2", "h1", "v3"]},
    ]
    return profile


def test_review_generation_never_auto_approves_migration_evidence() -> None:
    review = build_movement_migration_review(_profile())

    assert review["schema"] == "route-movement-migration-review/v1"
    assert review["profile_version"] == 3
    assert review["evaluation_status"] == "requirements"
    assert review["patches"]
    assert all(patch["approved"] is False for patch in review["patches"])
    incoming = next(patch for patch in review["patches"] if patch["kind"] == "incoming_movement")
    assert incoming["to_location_ref"] == "p2"
    assert incoming["value"] == {"kind": "self_move", "mode": "fly"}
    primary = next(patch for patch in review["patches"] if patch["kind"] == "primary_zone_id")
    assert primary["zone_id"] is None


def test_mechanical_approval_marks_only_deterministic_incoming_candidates() -> None:
    review = build_movement_migration_review(_profile())
    payload = {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": 1,
        "profiles": [review],
    }

    approved = approve_mechanical_candidates(payload)

    assert approved["mechanical_candidate_approval_count"] == 1
    incoming = next(patch for patch in review["patches"] if patch["kind"] == "incoming_movement")
    primary = next(patch for patch in review["patches"] if patch["kind"] == "primary_zone_id")
    assert incoming["approved"] is True
    assert incoming["approval_basis"] == "deterministic_stage5_mechanical_candidate"
    assert primary["approved"] is False


def test_existing_leading_hearth_action_is_a_review_gated_mechanical_reorder() -> None:
    profile = _leading_hearth_profile()
    review = build_movement_migration_review(profile)
    reorder = next(patch for patch in review["patches"] if patch["kind"] == "reorder_leading_movement")

    assert reorder["status"] == "mechanical_candidate"
    assert reorder["approved"] is False
    assert reorder["action_id"] == "h1"
    assert reorder["to_visit_id"] == "v2"
    assert reorder["to_location_ref"] == "p2"
    assert reorder["legacy_transport"] == "hearth"

    payload = {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": 1,
        "profiles": [review],
    }
    approve_mechanical_candidates(payload)
    assert reorder["approved"] is True

    updated = apply_approved_movement_review(profile, review)
    assert [action["action_id"] for action in updated["actions"][:4]] == ["v1", "h1", "v2", "v3"]
    assert updated["step_groups"][0]["action_ids"] == ["v1", "h1", "v2", "v3"]
    assert updated["geometry"]["locations"]["p2"]["incoming_movement"] == {
        "kind": "action",
        "action_id": "h1",
    }
    assert "incoming_movement" not in updated["geometry"]["locations"]["p3"]


def test_stale_duplicate_incoming_is_review_gated_mechanical_cleanup() -> None:
    profile = _leading_hearth_profile()
    review = build_movement_migration_review(profile)
    reorder = next(patch for patch in review["patches"] if patch["kind"] == "reorder_leading_movement")
    reorder["approved"] = True
    moved = apply_approved_movement_review(profile, review)
    moved["geometry"]["locations"]["p3"]["incoming_movement"] = {
        "kind": "action",
        "action_id": "h1",
    }

    cleanup_review = build_movement_migration_review(moved)
    cleanup = next(
        patch
        for patch in cleanup_review["patches"]
        if patch["kind"] == "remove_stale_duplicate_incoming"
    )
    assert cleanup["status"] == "mechanical_candidate"
    assert cleanup["approved"] is False
    assert cleanup["keeper_location_ref"] == "p2"
    assert cleanup["stale_location_ref"] == "p3"

    payload = {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": 1,
        "profiles": [cleanup_review],
    }
    approve_mechanical_candidates(payload)
    assert cleanup["approved"] is True

    cleaned = apply_approved_movement_review(moved, cleanup_review)
    assert cleaned["geometry"]["locations"]["p2"]["incoming_movement"] == {
        "kind": "action",
        "action_id": "h1",
    }
    assert "incoming_movement" not in cleaned["geometry"]["locations"]["p3"]


def test_nonterminal_movement_is_cleaned_and_never_repromoted() -> None:
    profile = _profile()
    profile["scope"]["primary_zone_id"] = 3483
    profile["actions"] = [
        {"action_id": "v1", "kind": "location", "location_ref": "p1"},
        {
            "action_id": "m1",
            "kind": "fixed_transport",
            "location_ref": "p1",
            "from_name": "A",
            "to_name": "internal platform",
        },
        {"action_id": "x1", "kind": "interact", "location_ref": "p1"},
        {"action_id": "v2", "kind": "location", "location_ref": "p2"},
    ]
    profile["geometry"]["locations"]["p2"]["incoming_movement"] = {
        "kind": "action",
        "action_id": "m1",
    }
    profile["step_groups"] = [
        {"step_id": "step-01", "action_ids": ["v1", "m1", "x1", "v2"]},
    ]

    review = build_movement_migration_review(profile)
    cleanup = next(
        patch
        for patch in review["patches"]
        if patch["kind"] == "remove_nonterminal_incoming_movement"
    )
    assert cleanup["status"] == "mechanical_candidate"
    assert cleanup["approved"] is False
    assert cleanup["action_id"] == "m1"
    assert cleanup["to_location_ref"] == "p2"

    payload = {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": 1,
        "profiles": [review],
    }
    approve_mechanical_candidates(payload)
    assert cleanup["approved"] is True
    cleaned = apply_approved_movement_review(profile, review)
    assert "incoming_movement" not in cleaned["geometry"]["locations"]["p2"]

    followup = build_movement_migration_review(cleaned)
    assert not any(
        patch["kind"] == "incoming_movement" and patch.get("to_location_ref") == "p2"
        for patch in followup["patches"]
    )
    manual_kinds = {
        (patch.get("issue") or {}).get("kind")
        for patch in followup["patches"]
        if patch["kind"] == "manual_review"
    }
    assert "movement_action_not_terminal_for_migration" in manual_kinds


def test_leading_movement_reorder_refuses_cross_step_changes() -> None:
    profile = _leading_hearth_profile()
    profile["step_groups"] = [
        {"step_id": "step-01", "action_ids": ["v1", "v2"]},
        {"step_id": "step-02", "action_ids": ["h1", "v3"]},
    ]
    review = build_movement_migration_review(profile)
    reorder = next(patch for patch in review["patches"] if patch["kind"] == "reorder_leading_movement")
    reorder["approved"] = True

    with pytest.raises(ValueError, match="would cross step_groups"):
        apply_approved_movement_review(profile, review)


def test_primary_zone_approval_uses_exact_map_manifest_and_skips_crossmap_profiles(
    tmp_path, monkeypatch
) -> None:
    maps_dir = tmp_path / "data/routes/maps"
    maps_dir.mkdir(parents=True)
    (maps_dir / "manifest.json").write_text(
        json.dumps(
            {
                "maps": [
                    {"zone_id": 3521, "file": "3521-zangarmarsh.jpg", "hd_file": "3521-zangarmarsh-hd.jpg"}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(movement_script, "ROOT", tmp_path)
    profiles = {
        "safe": {"profile_id": "safe", "display": {"map_image": "maps/3521-zangarmarsh-hd.jpg"}},
        "cross": {"profile_id": "cross", "display": {"map_image": "maps/3521-zangarmarsh-hd.jpg"}},
    }
    monkeypatch.setattr(movement_script, "load_route_profile", lambda profile_id, **_: profiles[profile_id])
    payload = {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": 2,
        "profiles": [
            {
                "schema": "route-movement-migration-review/v1",
                "profile_id": "safe",
                "patches": [
                    {
                        "patch_id": "primary-zone",
                        "kind": "primary_zone_id",
                        "status": "review_required",
                        "approved": False,
                        "zone_id": None,
                    }
                ],
            },
            {
                "schema": "route-movement-migration-review/v1",
                "profile_id": "cross",
                "patches": [
                    {
                        "patch_id": "primary-zone",
                        "kind": "primary_zone_id",
                        "status": "review_required",
                        "approved": False,
                        "zone_id": None,
                    },
                    {
                        "patch_id": "review-crossmap",
                        "kind": "manual_review",
                        "status": "review_required",
                        "approved": False,
                        "issue": {
                            "kind": "legacy_transport_requires_operation_review",
                            "legacy_transport": "crossmap",
                        },
                    },
                ],
            },
        ],
    }

    approved = approve_primary_zones_from_map_manifest(payload)
    by_profile = {row["profile_id"]: row for row in approved["profiles"]}

    assert approved["primary_zone_approval_count"] == 1
    assert approved["primary_zone_skipped_crossmap_profiles"] == ["cross"]
    assert approved["primary_zone_missing_asset_match_profiles"] == []
    safe_primary = next(patch for patch in by_profile["safe"]["patches"] if patch["kind"] == "primary_zone_id")
    cross_primary = next(patch for patch in by_profile["cross"]["patches"] if patch["kind"] == "primary_zone_id")
    assert safe_primary["approved"] is True
    assert safe_primary["zone_id"] == 3521
    assert safe_primary["approval_basis"] == "exact_route_map_asset_manifest_match_no_unresolved_crossmap"
    assert cross_primary["approved"] is False
    assert cross_primary["zone_id"] is None


def test_apply_review_only_writes_explicitly_approved_machine_patches() -> None:
    profile = _profile()
    review = build_movement_migration_review(profile)
    approved = deepcopy(review)
    for patch in approved["patches"]:
        if patch["kind"] == "primary_zone_id":
            patch["zone_id"] = 3483
            patch["approved"] = True
        if patch["kind"] == "incoming_movement":
            patch["approved"] = True

    updated = apply_approved_movement_review(profile, approved)

    assert "primary_zone_id" not in profile["scope"]
    assert "incoming_movement" not in profile["geometry"]["locations"]["p2"]
    assert updated["scope"]["primary_zone_id"] == 3483
    assert updated["geometry"]["locations"]["p2"]["incoming_movement"] == {
        "kind": "self_move",
        "mode": "fly",
    }


def test_stale_review_cannot_apply_after_stage5_input_changes() -> None:
    profile = _profile()
    review = build_movement_migration_review(profile)
    changed = deepcopy(profile)
    changed["geometry"]["locations"]["p2"]["x"] = 21.0

    with pytest.raises(ValueError, match="fingerprint is stale"):
        apply_approved_movement_review(changed, review)


def test_manual_review_row_can_never_be_auto_applied() -> None:
    profile = _profile()
    review = build_movement_migration_review(profile)
    review["patches"].append(
        {
            "patch_id": "manual-test",
            "kind": "manual_review",
            "status": "review_required",
            "approved": True,
            "issue": {"kind": "synthetic"},
        }
    )

    with pytest.raises(ValueError, match="manual review patch cannot be auto-applied"):
        apply_approved_movement_review(profile, review)
