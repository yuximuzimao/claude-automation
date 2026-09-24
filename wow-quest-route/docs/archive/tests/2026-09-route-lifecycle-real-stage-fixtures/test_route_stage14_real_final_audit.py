from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts.rebuild_route_profile import audit_profile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "stage14-final-audit-migration-expected.json"


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


def test_stage14_real_profile_closes_implementation_without_faking_artifact_readiness() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _upstream_inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=fixture["review_input"],
    )
    stage14 = report["stages"][13]
    audit = stage14["detail"]["report"]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage14-final-audit-migration-expected/v1"
    assert report["implementation_status"] == expected["implementation_status"]
    assert report["unimplemented_stages"] == expected["unimplemented_stages"]
    assert report["artifact_evaluation_status"] == expected["artifact_evaluation_status"]

    assert stage14["name"] == "mechanical_audit_cold_read"
    assert stage14["implementation_status"] == expected["stage_implementation_status"]
    assert stage14["evaluation_status"] == expected["stage_evaluation_status"]
    assert audit["status"] == expected["audit_status"]
    assert audit["publishable"] is expected["publishable"]

    summary = audit["mechanical_summary"]
    assert summary["prerequisite_stage_count"] == expected["prerequisite_stage_count"]
    assert summary["implemented_stage_count"] == expected["implemented_stage_count"]
    assert summary["blocked_stage_count"] == expected["blocked_stage_count"]
    assert summary["requirements_stage_count"] == expected["requirements_stage_count"]
    assert summary["active_consumer_count"] == expected["active_consumer_count"]

    prerequisite_stages = report["stages"][:13]
    assert [row["name"] for row in prerequisite_stages if row["evaluation_status"] == "blocked"] == expected["blocked_stage_names"]
    assert [row["name"] for row in prerequisite_stages if row["evaluation_status"] == "requirements"] == expected["requirement_stage_names"]
    assert Counter(issue["kind"] for issue in audit["issues"]) == Counter(expected["issue_counts"])

    cold = audit["cold_read"][expected["publish_key"]]
    assert [row["action_line_count"] for row in cold["step_action_line_counts"]] == expected["cold_read_step_action_line_counts"]
    forbidden_inference_issues = [
        issue
        for issue in audit["issues"]
        if issue["kind"] in {
            "final_audit_stage11_stage12_fingerprint_mismatch",
            "final_audit_stage12_stage13_fingerprint_mismatch",
            "final_audit_active_legacy_consumer",
            "cold_read_internal_action_token",
            "cold_read_forbidden_marker",
        }
    ]
    assert len(forbidden_inference_issues) == expected["cold_read_forbidden_business_inference_issue_count"]
