from __future__ import annotations

import json

from scripts.migrate_timing_observations import build_payload


def test_legacy_timing_runs_are_preserved_but_only_exact_clean_scopes_become_calibration_eligible(tmp_path) -> None:
    source = tmp_path / "route-timing-runs.json"
    runs = [
        {
            "date": "2026-09-01",
            "route_key": "borean",
            "profile_version": 7,
            "start_action_id": "a1",
            "end_action_id": "a9",
            "actual_minutes": 12.5,
            "time_precision": "exact",
            "actual_contains_learning_or_route_errors": False,
            "note": "clean exact scope",
        },
        {
            "date": "2026-09-02",
            "route_key": "borean",
            "profile_version": 7,
            "start_action_id": "a1",
            "end_action_id": "a9",
            "actual_minutes": 20.0,
            "actual_contains_learning_or_route_errors": True,
            "note": "same scope but contaminated",
        },
        {
            "date": "2026-09-03",
            "route_key": "borean",
            "actual_minutes": 13.0,
            "actual_contains_learning_or_route_errors": False,
            "note": "clean but historical prose scope only",
        },
    ]
    source.write_text(json.dumps({"runs": runs}, ensure_ascii=False), encoding="utf-8")

    payload = build_payload(source)
    observations = payload["observations"]

    assert len(observations) == 3
    assert observations[0]["profile_id"] == "borean-fivebox"
    assert observations[0]["profile_version"] == 7
    assert observations[0]["action_scope"] == {"start_action_id": "a1", "end_action_id": "a9"}
    assert observations[0]["calibration_eligible"] is True
    assert observations[0]["source_record"] == runs[0]

    assert observations[1]["calibration_eligible"] is False
    assert "contains_learning_or_route_errors" in observations[1]["ineligibility_reasons"]

    assert observations[2]["calibration_eligible"] is False
    assert "profile_version_missing" in observations[2]["ineligibility_reasons"]
    assert "stable_action_scope_missing" in observations[2]["ineligibility_reasons"]


def test_unmapped_legacy_route_never_becomes_calibration_input_by_accident(tmp_path) -> None:
    source = tmp_path / "route-timing-runs.json"
    source.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "route_key": "dk_starting_zone",
                        "profile_version": 1,
                        "start_action_id": "a1",
                        "end_action_id": "a2",
                        "actual_minutes": 5,
                        "actual_contains_learning_or_route_errors": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    observation = build_payload(source)["observations"][0]

    assert observation["profile_id"] is None
    assert observation["calibration_eligible"] is False
    assert "profile_mapping_missing" in observation["ineligibility_reasons"]
