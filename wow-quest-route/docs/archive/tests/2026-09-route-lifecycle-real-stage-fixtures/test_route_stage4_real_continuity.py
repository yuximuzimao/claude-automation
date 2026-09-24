from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


# Frozen Route Profile v2 real-program outcome declared after the contract redesign but before
# any Stage-4-driven route/action repair.  The former v1 fixture intentionally became invalid
# when exit_state_contract was removed; this v2 snapshot again prevents circular validator proof.
def test_stage4_v2_frozen_real_program_pre_repair_expected_outcome() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "stage4-v2-pre-route-repair-diagnostic.json").read_text()
    )
    continuity = fixture

    assert fixture["fixture_id"] == "stage4-v2-pre-route-repair-2026-09-16"
    assert continuity["status"] == "blocked"
    assert continuity["program_id"] == "horde-fivebox-full-clear"
    assert continuity["profile_ids"] == [
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
    assert len(continuity["input_fingerprint"]) == 64

    hard = [issue for issue in continuity["issues"] if issue["severity"] == "error"]
    counts = Counter(issue["kind"] for issue in hard)
    assert len(hard) == 17
    assert counts == {
        "required_active_tasks_missing": 6,
        "turnin_for_inactive_task": 8,
        "objective_for_inactive_task": 2,
        "exclusive_task_conflict": 1,
    }

    # Representative migration-fidelity failures independently understood before repair.
    assert any(
        issue["kind"] == "turnin_for_inactive_task"
        and issue.get("task_id") == 9797
        and issue.get("to") == "nagrand-fivebox-67-68"
        for issue in hard
    )
    assert any(
        issue["kind"] == "turnin_for_inactive_task"
        and issue.get("task_id") == 11864
        and issue.get("to") == "borean-fivebox"
        for issue in hard
    )
    assert any(
        issue["kind"] == "objective_for_inactive_task"
        and issue.get("task_id") == 13264
        and issue.get("to") == "icecrown-fivebox"
        for issue in hard
    )
    assert any(
        issue["kind"] == "exclusive_task_conflict"
        and issue.get("task_id") == 12181
        and issue.get("to") == "howling-fivebox"
        for issue in hard
    )

    unknown = [issue for issue in continuity["issues"] if issue["severity"] == "unknown"]
    assert unknown
    assert any(issue["kind"] == "unresolved_entry_task_state" for issue in unknown)


def test_stage4_implementation_readiness_is_independent_from_current_program_result() -> None:
    report = audit_profile("hellfire-fivebox")
    stage4 = report["stages"][3]

    stage3 = report["stages"][2]
    assert stage3["evaluation_status"] == "requirements"
    assert stage3["publish_gate_applies"] is False  # Stage 4 replays this Program member with actual Program state.

    assert stage4["name"] == "cross_profile_continuity"
    assert stage4["implementation_status"] == "implemented"
    assert stage4["evaluation_status"] == "blocked"
    assert stage4["publish_gate_applies"] is True
    assert report["implementation_status"] == "incomplete"  # Stages 5-14 are intentionally unfinished.
    assert "cross_profile_continuity" in report["artifact_blocked_stages"]
    assert "cross_profile_continuity" not in report["unimplemented_stages"]

