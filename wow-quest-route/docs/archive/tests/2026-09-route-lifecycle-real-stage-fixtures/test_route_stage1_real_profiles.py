from __future__ import annotations

from lib.route_dependencies import build_dependency_index, build_profile_dependency_manifest
from scripts.rebuild_route_profile import audit_profile


# Stage 1 migration acceptance fixture.
# These expectations are declared from the current formal topology before using the
# Stage-1 result as proof: 14 Route Profiles exist, the one formal Route Program owns
# 12 fivebox Profiles, and the DK Hellfire Profile is intentionally standalone with
# 59 Task Cards. This test must not "fix" formal route data to make the assertions pass.
def test_stage1_frozen_real_profile_expected_outcome() -> None:
    dependency_index = build_dependency_index()

    assert dependency_index["summary"] == {
        "profile_count": 14,
        "program_count": 1,
        "task_reverse_index_count": 1079,
        "profile_program_reverse_index_count": 12,
    }
    assert dependency_index["unknown_program_profile_refs"] == []
    assert dependency_index["program_to_profiles"]["horde-fivebox-full-clear"] == [
        "hellfire-fivebox",
        "zangarmarsh-fivebox",
        "nagrand-fivebox-67-68",
        "borean-fivebox",
        "dragonblight-fivebox",
        "dalaran-mainline-77",
        "storm-peaks-fivebox",
        "icecrown-fivebox",
        "sholazar-fivebox",
        "zuldrak-fivebox",
        "grizzly-fivebox",
        "howling-fivebox",
    ]

    manifest = build_profile_dependency_manifest("hellfire-dk-speed")
    assert len(manifest["task_cards"]) == 59
    assert manifest["route_programs"] == {}
    assert manifest["source_inventory"]["character_profile"]["path"] == (
        "data/character-profiles/dk-twohand-blood-current.json"
    )
    assert manifest["source_inventory"]["route_ui"]["path"] == "data/route-ui/hellfire-dk-speed.json"
    assert {
        name: row["path"] for name, row in manifest["source_inventory"]["schemas"].items()
    } == {
        "character_profile": "data/character-profiles/schema.json",
        "route_profile": "data/route-profiles/schema.json",
        "route_program": "data/route-programs/schema.json",
        "task_card": "data/task-cards/schema.json",
    }
    assert len(manifest["root_fingerprint"]) == 64
    assert len(manifest["manifest_fingerprint"]) == 64


def test_stage1_rebuild_entrypoint_executes_real_dependency_gate() -> None:
    report = audit_profile("hellfire-dk-speed")
    stage1 = report["stages"][0]

    assert stage1["name"] == "dependency_fingerprint"
    assert stage1["implementation_status"] == "implemented"
    assert stage1["evaluation_status"] == "pass"
    assert stage1["detail"]["task_card_count"] == 59
    assert stage1["detail"]["route_program_ids"] == []
    assert set(stage1["detail"]["source_inventory"]["schemas"]) == {
        "character_profile",
        "route_profile",
        "route_program",
        "task_card",
    }
    # The whole pipeline is deliberately not expected to be ready yet; later stages
    # remain blocked until they independently satisfy SOP §17.2.
    assert report["status"] == "blocked"
