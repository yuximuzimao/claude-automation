from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from lib.route_profiles import load_route_profile
from scripts.rebuild_route_profile import audit_profile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "stage11-display-migration-expected.json"


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


def test_stage11_real_profile_projects_display_without_repairing_migration_defects() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _upstream_inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=fixture["review_input"],
    )
    stage11 = report["stages"][10]
    display = stage11["detail"]["reports"][0]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage11-display-migration-expected/v1"
    assert stage11["name"] == "display_presentation"
    assert stage11["implementation_status"] == expected["stage_implementation_status"]
    assert stage11["evaluation_status"] == expected["stage_evaluation_status"]
    assert "display_presentation" not in report["unimplemented_stages"]
    assert display["status"] == expected["display_status"]

    assert len(display["steps"]) == expected["step_count"]
    assert sum(len(step["lines"]) for step in display["steps"]) == expected["line_count"]
    profile = load_route_profile(fixture["profile_probe"], validate=True, validate_task_cards=False)
    task_action_count = sum(1 for action in profile["actions"] if action["kind"] in {"accept", "objective", "turnin"})
    rendered_task_ref_count = sum(
        len(line.get("task_refs") or [])
        for step in display["steps"]
        for line in step["lines"]
    )
    assert task_action_count == expected["task_action_count"]
    assert rendered_task_ref_count == expected["rendered_task_ref_count"]
    assert rendered_task_ref_count == task_action_count

    presentation_count = sum(len(step["task_presentations"]) for step in display["steps"])
    pending_count = sum(
        1
        for step in display["steps"]
        for projected in step["task_presentations"]
        if projected.get("pending")
    )
    assert presentation_count == expected["presentation_count"]
    assert pending_count == expected["pending_presentation_count"]

    assert display["route_timing"]["center_minutes"] == expected["route_timing_center_minutes"]
    assert display["route_timing"]["range_minutes"] == expected["route_timing_range_minutes"]
    contains_html = "<div" in str(display) or "actionHtml" in str(display)
    assert contains_html is expected["contains_html"]

    assert Counter(issue["kind"] for issue in display["issues"]) == Counter(expected["issue_counts"])
    location_issues = [
        [issue["kind"], issue["location_ref"], issue["display_name"]]
        for issue in display["issues"]
        if issue["kind"].startswith("location_display")
    ]
    assert location_issues == expected["location_issues"]

    assert display["steps"][0]["title"] == expected["first_step_title"]
    assert [line["text"] for line in display["steps"][0]["lines"][:5]] == expected["first_step_prefix_lines"]
    assert display["steps"][-1]["title"] == expected["last_step_title"]
    assert report["unimplemented_stages"] == expected["unimplemented_stages"]
