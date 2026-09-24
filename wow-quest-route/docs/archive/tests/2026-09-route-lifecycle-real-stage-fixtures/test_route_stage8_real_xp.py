from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


FIXTURE = Path(__file__).parent / "fixtures" / "stage8-xp-migration-expected.json"


def _xp_input(fixture: dict) -> dict:
    source = fixture["xp_input"]
    character_ids = list(source["character_ids"])
    return {
        "profiles": {
            fixture["profile_probe"]: {
                "entry_state": {
                    "source": dict(source["source"]),
                    "characters": [
                        {
                            "character_id": character_id,
                            "level": int(source["entry_level"]),
                            "xp_into_level": int(source["entry_xp_into_level"]),
                        }
                        for character_id in character_ids
                    ],
                },
                "external_xp_upper_bound_by_character": {
                    character_id: int(source["external_xp_upper_bound_each"])
                    for character_id in character_ids
                },
            }
        }
    }


def test_stage8_real_profile_executes_xp_timeline_without_repairing_route_truth() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = audit_profile(fixture["profile_probe"], xp_input=_xp_input(fixture))
    stage8 = report["stages"][7]
    xp = stage8["detail"]["reports"][0]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage8-xp-migration-expected/v1"
    assert stage8["name"] == "derived_xp"
    assert stage8["implementation_status"] == expected["stage_implementation_status"]
    assert stage8["evaluation_status"] == expected["stage_evaluation_status"]
    assert "derived_xp" not in report["unimplemented_stages"]

    assert xp["kind"] == "profile"
    assert xp["profile_id"] == fixture["profile_probe"]
    assert xp["status"] == expected["profile_status"]
    assert len(xp["turnins"]) == expected["turnin_count"]
    assert xp["guaranteed_lower_bound"] == expected["guaranteed_lower_bound"]
    assert xp["possible_upper_bound"] == expected["possible_upper_bound"]
    assert Counter(issue["kind"] for issue in xp["issues"]) == Counter(expected["issue_counts"])
    assert Counter(gate["status"] for gate in xp["level_gates"]) == Counter(expected["level_gate_status_counts"])

    exit_rows = xp["exit_state_lower"]["characters"]
    assert [row["character_id"] for row in exit_rows] == fixture["xp_input"]["character_ids"]
    assert {row["level"] for row in exit_rows} == {expected["exit_level"]}
    assert {row["xp_into_level"] for row in exit_rows} == {expected["exit_xp_into_level"]}
    assert report["unimplemented_stages"] == []
