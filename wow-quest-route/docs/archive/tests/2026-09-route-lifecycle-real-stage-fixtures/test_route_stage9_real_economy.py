from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from lib.route_economy import evaluate_profile_economy
from lib.route_profiles import load_route_profile
from lib.task_cards import load_task_card
from scripts.rebuild_route_profile import audit_profile


PRE_FIXTURE = Path(__file__).parent / "fixtures" / "stage9-economy-migration-expected.json"
POST_FIXTURE = Path(__file__).parent / "fixtures" / "stage9-economy-post-flag-migration-expected.json"


def _inputs(fixture: dict) -> tuple[dict, dict]:
    xp_source = fixture["xp_input"]
    character_ids = list(xp_source["character_ids"])
    xp_input = {
        "profiles": {
            fixture["profile_probe"]: {
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
    economy_source = fixture["economy_input"]
    economy_input = {
        "profiles": {
            fixture["profile_probe"]: {
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


def _assert_economy(economy: dict, fixture: dict) -> None:
    expected = fixture["expected"]
    assert economy["kind"] == "profile"
    assert economy["profile_id"] == fixture["profile_probe"]
    assert economy["status"] == expected["profile_status"]
    assert len(economy["turnins"]) == expected["turnin_count"]
    assert len(economy["characters"]) == expected["character_count"]
    assert economy["known_gross_copper"] == expected["known_gross_copper"]
    assert economy["gross_copper"] == expected["gross_copper"]
    assert economy["known_cost_copper"] == expected["known_cost_copper"]
    assert economy["net_copper"] == expected["net_copper"]
    assert economy["gross_gph"] == expected["gross_gph"]
    assert Counter(issue["kind"] for issue in economy["issues"]) == Counter(expected["issue_counts"])


def test_stage9_real_profile_pre_flag_migration_diagnostic_stays_reproducible() -> None:
    fixture = json.loads(PRE_FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
    )
    stage9 = report["stages"][8]

    # Reproduce the frozen pre-migration condition without reverting current Task Card truth: use the
    # same real Profile/current upstream reports, but remove only the field that did not exist when the
    # diagnostic was captured.
    profile = load_route_profile(fixture["profile_probe"], validate=True, validate_task_cards=False)
    cards = {
        int(task_id): deepcopy(load_task_card(int(task_id), validate=True))
        for task_id in profile["task_ids"]
    }
    for card in cards.values():
        card["rewards"].pop("no_money_from_xp", None)
    economy = evaluate_profile_economy(
        profile,
        task_cards=cards,
        xp_report=report["stages"][7]["detail"]["reports"][0],
        timing_report=report["stages"][6]["detail"]["reports"][0],
        cost_input=economy_input["profiles"][fixture["profile_probe"]]["cost_input"],
    )

    assert fixture["schema"] == "stage9-economy-migration-expected/v1"
    assert stage9["name"] == "derived_economy"
    assert stage9["implementation_status"] == fixture["expected"]["stage_implementation_status"]
    assert "derived_economy" not in report["unimplemented_stages"]
    _assert_economy(economy, fixture)


def test_stage9_real_profile_after_reward_flag_migration_keeps_upstream_unknowns() -> None:
    fixture = json.loads(POST_FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
    )
    stage9 = report["stages"][8]
    economy = stage9["detail"]["reports"][0]

    assert fixture["schema"] == "stage9-economy-post-flag-migration-expected/v1"
    assert stage9["name"] == "derived_economy"
    assert stage9["implementation_status"] == fixture["expected"]["stage_implementation_status"]
    assert stage9["evaluation_status"] == fixture["expected"]["stage_evaluation_status"]
    assert "derived_economy" not in report["unimplemented_stages"]
    _assert_economy(economy, fixture)
    assert report["unimplemented_stages"] == []
