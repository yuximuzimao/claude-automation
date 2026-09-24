from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "stage12-publisher-payload-migration-expected.json"


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


def test_stage12_real_profile_wraps_blocked_stage11_without_fake_publication() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _upstream_inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=fixture["review_input"],
    )
    stage12 = report["stages"][11]
    payload = stage12["detail"]["payloads"][0]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage12-publisher-payload-migration-expected/v1"
    assert stage12["name"] == "publisher_payload"
    assert stage12["implementation_status"] == expected["stage_implementation_status"]
    assert stage12["evaluation_status"] == expected["stage_evaluation_status"]
    assert "publisher_payload" not in report["unimplemented_stages"]

    assert payload["kind"] == "publisher_payload"
    assert payload["status"] == expected["payload_status"]
    assert payload["publishable"] is expected["publishable"]
    assert Counter(issue["kind"] for issue in payload["issues"]) == Counter(expected["issue_counts"])
    assert payload["program_id"] == expected["program_id"]
    assert payload["hearth_chain"] == expected["hearth_chain"]
    assert payload["display"]["publish_key"] == expected["publish_key"]
    assert payload["map"]["image"] == expected["map_image"]
    assert len(payload["map"]["labels"]) == expected["map_label_count"]
    geometry = payload["map"]["geometry"]
    assert len(geometry["visits"]) == expected["map_visit_count"]
    assert len(geometry["edges"]) == expected["map_edge_count"]
    assert sum(1 for visit in geometry["visits"] if not visit.get("step_id")) == expected["map_visit_without_step_count"]
    assert geometry["visits"][0]["step_id"] == "step-01"
    assert geometry["visits"][-1]["step_id"] == "step-11"
    assert len(payload["steps"]) == expected["step_count"]
    rendered_task_refs = sum(
        len(line.get("task_refs") or [])
        for step in payload["steps"]
        for line in step["lines"]
    )
    assert rendered_task_refs == expected["rendered_task_ref_count"]
    contains_legacy = any(token in str(payload) for token in ("actionHtml", "noteHtml")) or "points" in payload
    assert contains_legacy is expected["contains_legacy_payload_fields"]
    assert report["unimplemented_stages"] == expected["unimplemented_stages"]
