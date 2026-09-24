from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


FIXTURE = Path(__file__).parent / "fixtures" / "stage7-timing-migration-expected.json"


def test_stage7_real_program_is_classified_without_repairing_route_truth() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = audit_profile(expected["profile_probe"])
    stage7 = report["stages"][6]
    timing = stage7["detail"]["reports"][0]
    target = expected["expected"]

    assert expected["schema"] == "stage7-timing-migration-expected/v1"
    assert stage7["name"] == "derived_timing"
    assert stage7["implementation_status"] == target["stage_implementation_status"]
    assert stage7["evaluation_status"] == target["stage_evaluation_status"]
    assert "derived_timing" not in report["unimplemented_stages"]

    assert timing["kind"] == "route_program"
    assert timing["program_id"] == expected["program_id"]
    assert timing["status"] == target["program_status"]
    assert timing["known_seconds"] == target["known_seconds"]
    assert timing["center_minutes"] == target["center_minutes"]
    assert timing["range_minutes"] == target["range_minutes"]
    assert Counter(issue["kind"] for issue in timing["issues"]) == Counter(target["issue_counts"])
    assert report["unimplemented_stages"] == []
