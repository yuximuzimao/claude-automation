from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from lib.route_player_assets import render_workbench_html
from scripts.rebuild_route_profile import audit_profile


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURE_DIR / "stage13-player-assets-migration-expected.json"


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


def test_stage13_real_profile_renders_diagnostics_without_overwriting_formal_assets() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    xp_input, economy_input = _upstream_inputs(fixture)
    report = audit_profile(
        fixture["profile_probe"],
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=fixture["review_input"],
    )
    stage13 = report["stages"][12]
    assets = stage13["detail"]["report"]
    expected = fixture["expected"]

    assert fixture["schema"] == "stage13-player-assets-migration-expected/v1"
    assert stage13["name"] == "html_player_view_assets"
    assert stage13["implementation_status"] == expected["stage_implementation_status"]
    assert stage13["evaluation_status"] == expected["stage_evaluation_status"]
    assert "html_player_view_assets" not in report["unimplemented_stages"]

    assert assets["status"] == expected["asset_status"]
    assert assets["publishable"] is expected["publishable"]
    assert Counter(issue["kind"] for issue in assets["issues"]) == Counter(expected["issue_counts"])
    assert assets["workbench_name"] == expected["workbench_name"]
    assert assets["workbench_bytes"] >= expected["workbench_min_bytes"]
    assert assets["referenced_assets"] == expected["referenced_assets"]

    player_view = assets["player_views"][expected["publish_key"]]
    assert len(player_view) == expected["player_view_chars"]
    for fragment in expected["player_view_required_fragments"]:
        assert fragment in player_view
    assert "<div" not in player_view
    assert "actionHtml" not in player_view
    assert "workbench-routes.json" not in player_view

    html = render_workbench_html(report["publisher_payload"])
    assert hashlib.sha256(html.encode("utf-8")).hexdigest() == assets["workbench_sha256"]
    lowered = html.lower()
    assert expected["referenced_assets"][0] in html
    assert "workbench-routes.json" not in html
    assert 'src="http://' not in lowered
    assert 'src="https://' not in lowered
    assert 'href="http://' not in lowered
    assert 'href="https://' not in lowered
    assert report["unimplemented_stages"] == expected["unimplemented_stages"]
