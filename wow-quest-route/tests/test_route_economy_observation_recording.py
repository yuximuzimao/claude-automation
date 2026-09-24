from __future__ import annotations

import json

import pytest

from scripts.record_route_economy_observation import append_observation, build_observation, parse_asset


def _empty_payload() -> dict:
    return {
        "schema_version": 1,
        "observation_set_id": "fixture-observations",
        "policy": "fixture",
        "observations": [],
    }


def test_parse_asset_preserves_quantity_without_valuation() -> None:
    assert parse_asset("titan_shard=12") == {"asset_id": "titan_shard", "quantity": 12.0}


def test_clean_observation_cannot_hide_contamination() -> None:
    with pytest.raises(ValueError, match="clean observation cannot contain contamination"):
        build_observation(
            observation_id="obs-1",
            target_kind="profile",
            target_id="hellfire-dk-speed",
            target_version=1,
            source_ref="live-run",
            raw_gold_delta_copper=100,
            assets=[],
            clean=True,
            contamination=["death-repair-cost"],
        )


def test_nonclean_observation_requires_explicit_contamination_reason() -> None:
    with pytest.raises(ValueError, match="requires at least one contamination reason"):
        build_observation(
            observation_id="obs-1",
            target_kind="profile",
            target_id="hellfire-dk-speed",
            target_version=1,
            source_ref="live-run",
            raw_gold_delta_copper=100,
            assets=[],
            clean=False,
            contamination=[],
        )


def test_append_preserves_raw_evidence_and_rejects_duplicate_id(tmp_path) -> None:
    path = tmp_path / "economy-observations.json"
    path.write_text(json.dumps(_empty_payload(), ensure_ascii=False), encoding="utf-8")
    observation = build_observation(
        observation_id="obs-1",
        target_kind="profile",
        target_id="hellfire-dk-speed",
        target_version=1,
        source_ref="live-run-2026-09-18",
        raw_gold_delta_copper=12345,
        assets=[{"asset_id": "titan_shard", "quantity": 7}],
        clean=True,
        contamination=[],
    )

    updated = append_observation(path, observation)
    stored = updated["observations"][0]
    assert stored["raw_gold_delta_copper"] == 12345
    assert stored["assets"] == [{"asset_id": "titan_shard", "quantity": 7}]
    assert stored["source_ref"] == "live-run-2026-09-18"

    with pytest.raises(ValueError, match="duplicate observation_id"):
        append_observation(path, observation)


def test_program_observation_binds_program_without_profile_fields() -> None:
    observation = build_observation(
        observation_id="program-obs-1",
        target_kind="program",
        target_id="dk-55-80-world",
        target_version=3,
        source_ref="full-program-live-run",
        raw_gold_delta_copper=500000,
        assets=[{"asset_id": "titan_shard", "quantity": 42}],
        clean=True,
        contamination=[],
    )
    assert observation["program_id"] == "dk-55-80-world"
    assert observation["program_version"] == 3
    assert "profile_id" not in observation
    assert "profile_version" not in observation
