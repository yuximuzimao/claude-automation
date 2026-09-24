from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "stage10-review-trigger-migration-expected.json"


def _upstream_inputs(fixture: dict) -> tuple[dict, dict]:
    source = json.loads((FIXTURE_DIR / fixture["input_source_fixture"]).read_text(encoding="utf-8"))
    xp_source = source["xp_input"]
    character_ids = list(xp_source["character_ids"])
    xp_input = {
        "profiles": {
            source["profile_probe"]: {
                "entry_state": {
                    "source": dict(xp_source["source"]),
                    "characters": [
                        {
                            "character_id": character_id,
                            "level": int(xp_source["entry_level"]),
                            "xp_into_level": int(xp_source["entry_xp_into_level"]),
                        }
                        for character_id in character_ids
                    ],
                },
                "external_xp_upper_bound_by_character": {
                    character_id: int(xp_source["external_xp_upper_bound_each"])
                    for character_id in character_ids
                },
            }
        }
    }
    economy_source = source["economy_input"]
    economy_input = {
        "profiles": {
            source["profile_probe"]: {
                "cost_input": {
                    "source": dict(economy_source["source"]),
                    "coverage": economy_source["cost_coverage"],
                    "known_cost_copper_by_character": {
                        character_id: int(economy_source["known_cost_copper_each"])
                        for character_id in character_ids
                    },
                }
            }
        }
    }
    return xp_input, economy_input


def test_stage10_real_profile_fails_closed_without_repairing_route_truth() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _upstream_inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=fixture["review_input"],
    )
    stage10 = report["stages"][9]
    review = stage10["detail"]["reports"][0]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage10-review-trigger-migration-expected/v1"
    assert stage10["name"] == "review_trigger"
    assert stage10["implementation_status"] == expected["stage_implementation_status"]
    assert stage10["evaluation_status"] == expected["stage_evaluation_status"]
    assert "review_trigger" not in report["unimplemented_stages"]

    assert review["kind"] == expected["report_kind"]
    assert review["target_id"] == expected["target_id"]
    assert review["target_version"] == expected["target_version"]
    assert review["status"] == expected["report_status"]
    assert review["diagnoses"] == expected["diagnoses"]
    assert Counter(issue["kind"] for issue in review["issues"]) == Counter(expected["issue_counts"])

    blocked = sorted(
        issue["stage_name"]
        for issue in review["issues"]
        if issue["kind"] == "upstream_stage_blocked_for_review"
    )
    requirements = sorted(
        issue["stage_name"]
        for issue in review["issues"]
        if issue["kind"] == "upstream_stage_requirements_for_review"
    )
    assert blocked == sorted(expected["blocked_upstream_stages"])
    assert requirements == sorted(expected["requirement_upstream_stages"])

    assert review["selection_events"] == []
    assert review["optimization_failures"] == []
    assert "decision" not in review
    assert "delete_task_ids" not in review
    assert report["unimplemented_stages"] == expected["unimplemented_stages"]
