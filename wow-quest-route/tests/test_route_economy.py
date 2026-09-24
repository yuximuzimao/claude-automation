from __future__ import annotations

from copy import deepcopy

from lib.route_economy import (
    evaluate_profile_economy,
    evaluate_route_program_economy,
    evaluate_route_program_member_economy,
    load_economy_model_config,
)


def _profile() -> dict:
    return {"profile_id": "fixture-profile", "version": 1}


def _card(*, no_money_from_xp=... , quest_level: int = 60, full_xp: int = 10000) -> dict:
    rewards = {
        "reward_money_copper": 1000,
        "gear_sale_max_copper": 500,
        "full_xp": full_xp,
    }
    if no_money_from_xp is not ...:
        rewards["no_money_from_xp"] = no_money_from_xp
    return {
        "task_id": 42,
        "identity": {"repeatability": "once"},
        "availability": {"quest_level": quest_level},
        "rewards": rewards,
    }


def _xp_report(*, lower_level: int, upper_level: int | None) -> dict:
    upper = None
    if upper_level is not None:
        upper = [
            {
                "character_id": "c1",
                "before": {"level": upper_level, "xp_into_level": 0},
                "xp_gained": 0,
                "after": {"level": upper_level, "xp_into_level": 0},
            }
        ]
    return {
        "kind": "profile",
        "profile_id": "fixture-profile",
        "status": "pass",
        "input_fingerprint": "xp-fixture",
        "entry_state": {
            "source": {"kind": "fixture"},
            "characters": [{"character_id": "c1", "level": lower_level, "xp_into_level": 0}],
        },
        "turnins": [
            {
                "action_id": "turnin:42",
                "task_id": 42,
                "quest_level": 60,
                "full_xp": 10000,
                "lower": [
                    {
                        "character_id": "c1",
                        "before": {"level": lower_level, "xp_into_level": 0},
                        "xp_gained": 0,
                        "after": {"level": lower_level, "xp_into_level": 0},
                    }
                ],
                "upper": upper,
            }
        ],
    }


def _timing(*, complete: bool = True) -> dict:
    return {
        "status": "pass" if complete else "requirements",
        "complete": complete,
        "center_minutes": 60.0 if complete else None,
        "input_fingerprint": "timing-fixture",
    }


def _cost() -> dict:
    return {
        "source": {"kind": "fixture"},
        "coverage": "complete",
        "known_cost_copper_by_character": {"c1": 0},
    }


def _issue_kinds(report: dict) -> set[str]:
    return {row["kind"] for row in report["issues"]}


def test_economy_config_is_machine_valid() -> None:
    config = load_economy_model_config()
    assert config["max_level"] == 80
    assert config["xp_conversion_copper_per_base_xp"] == 6
    assert config["max_level_quest_cash_policy"] == "max_reward_money_or_xp_conversion"


def test_max_level_conversion_uses_decayed_base_xp_not_full_xp() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    turnin = report["turnins"][0]["characters"][0]
    assert turnin["xp_conversion_copper"] == 6000
    assert turnin["quest_cash_copper"] == 6000
    assert turnin["known_reward_value_copper"] == 6500
    assert report["gross_copper"] == 6500
    assert report["gross_gph"] == 0.65
    assert report["status"] == "pass"


def test_no_money_from_xp_keeps_direct_money_only_at_max_level() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=True)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    turnin = report["turnins"][0]["characters"][0]
    assert turnin["xp_conversion_copper"] == 0
    assert turnin["quest_cash_copper"] == 1000
    assert report["gross_copper"] == 1500
    assert report["status"] == "pass"


def test_missing_max_level_flag_is_fail_closed_but_preserves_known_item_value() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card()},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    assert "no_money_from_xp_fact_required" in _issue_kinds(report)
    assert report["known_gross_copper"] == 500
    assert report["gross_copper"] is None
    assert report["net_copper"] is None
    assert report["gross_gph"] is None
    assert report["status"] == "requirements"


def test_pre_max_turnin_does_not_require_no_money_flag_when_upper_bound_stays_pre_max() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card()},
        xp_report=_xp_report(lower_level=79, upper_level=79),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    assert "no_money_from_xp_fact_required" not in _issue_kinds(report)
    assert "turnin_max_level_state_not_unique" not in _issue_kinds(report)
    assert report["gross_copper"] == 1500
    assert report["status"] == "pass"


def test_ambiguous_premax_to_max_turnin_does_not_claim_exact_gross() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=79, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    assert "turnin_max_level_state_not_unique" in _issue_kinds(report)
    assert report["known_gross_copper"] == 1500
    assert report["gross_copper"] is None
    assert report["status"] == "requirements"


def test_missing_cost_or_timing_keeps_partial_values_but_blocks_final_gph() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(complete=False),
        cost_input=None,
    )
    kinds = _issue_kinds(report)
    assert "route_cost_coverage_incomplete" in kinds
    assert "fresh_complete_timing_required_for_gph" in kinds
    assert report["gross_copper"] == 6500
    assert report["known_cost_copper"] == 0
    assert report["net_copper"] == 6500
    assert report["gross_gph"] is None
    assert report["cost_coverage"] == "partial"
    assert report["status"] == "requirements"


def test_fingerprint_changes_when_reward_flag_changes() -> None:
    base = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    altered_card = _card(no_money_from_xp=True)
    changed = evaluate_profile_economy(
        _profile(),
        task_cards={42: altered_card},
        xp_report=deepcopy(_xp_report(lower_level=80, upper_level=80)),
        timing_report=_timing(),
        cost_input=_cost(),
    )
    assert base["input_fingerprint"] != changed["input_fingerprint"]


def _observation(*, clean: bool = True, version: int = 1, raw_gold: int | None = 7000, assets: list[dict] | None = None) -> dict:
    return {
        "schema_version": 1,
        "observation_set_id": "fixture-economy-observations",
        "observations": [
            {
                "observation_id": "obs-1",
                "profile_id": "fixture-profile",
                "profile_version": version,
                "scope": {"kind": "full_route"},
                "subject": {"kind": "group"},
                "raw_gold_delta_copper": raw_gold,
                "assets": assets or [],
                "clean": clean,
                "contamination": [] if clean else ["death-repair-cost-not-separated"],
                "source_ref": "fixture-run",
            }
        ],
    }


def _valuations(*, titan_copper: int | None = None) -> dict:
    assets = {}
    if titan_copper is not None:
        assets["titan_shard"] = {"copper_per_unit": titan_copper, "source_ref": "fixture-market"}
    return {
        "schema_version": 1,
        "valuation_set_id": "fixture-market-v1",
        "as_of": "2026-09-18",
        "assets": assets,
    }


def test_clean_exact_version_observation_is_comparison_not_reward_override() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
        economy_observations=_observation(raw_gold=7000),
        market_valuations=_valuations(),
    )
    assert report["gross_copper"] == 6500
    assert report["matched_observation_count"] == 1
    comparison = report["observation_comparisons"][0]
    assert comparison["observed_total_copper"] == 7000
    assert comparison["predicted_gross_copper"] == 6500
    assert comparison["observed_minus_predicted_copper"] == 500
    assert report["status"] == "pass"


def test_dirty_or_wrong_version_observation_is_not_silently_applied() -> None:
    dirty = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
        economy_observations=_observation(clean=False),
        market_valuations=_valuations(),
    )
    stale = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
        economy_observations=_observation(version=2),
        market_valuations=_valuations(),
    )
    assert dirty["matched_observation_count"] == 0
    assert stale["matched_observation_count"] == 0
    assert dirty["gross_copper"] == stale["gross_copper"] == 6500


def test_unknown_market_asset_keeps_observation_value_partial_and_requires_valuation() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
        economy_observations=_observation(raw_gold=1000, assets=[{"asset_id": "titan_shard", "quantity": 3}]),
        market_valuations=_valuations(),
    )
    comparison = report["observation_comparisons"][0]
    assert comparison["known_observed_value_copper"] == 1000
    assert comparison["observed_total_copper"] is None
    assert comparison["unknown_asset_ids"] == ["titan_shard"]
    assert "observation_market_valuation_required" in _issue_kinds(report)
    assert report["status"] == "requirements"


def test_market_asset_is_converted_only_from_explicit_valuation_set() -> None:
    report = evaluate_profile_economy(
        _profile(),
        task_cards={42: _card(no_money_from_xp=False)},
        xp_report=_xp_report(lower_level=80, upper_level=80),
        timing_report=_timing(),
        cost_input=_cost(),
        economy_observations=_observation(raw_gold=1000, assets=[{"asset_id": "titan_shard", "quantity": 3}]),
        market_valuations=_valuations(titan_copper=200),
    )
    comparison = report["observation_comparisons"][0]
    assert comparison["observed_total_copper"] == 1600
    assert comparison["valued_assets"][0]["copper_total"] == 600
    assert comparison["observed_minus_predicted_copper"] == -4900
    assert "observation_market_valuation_required" not in _issue_kinds(report)
    assert report["status"] == "pass"


def test_program_observation_compares_only_to_program_aggregate() -> None:
    program = {"program_id": "fixture-program", "version": 1, "profile_ids": ["fixture-profile"]}
    xp_member = _xp_report(lower_level=80, upper_level=80)
    timing_member = _timing()
    report = evaluate_route_program_economy(
        program,
        {"fixture-profile": _profile()},
        task_cards_by_profile={"fixture-profile": {42: _card(no_money_from_xp=False)}},
        xp_report={
            "member_reports": {"fixture-profile": xp_member},
            "input_fingerprint": "xp-program-fixture",
        },
        timing_report={
            "member_reports": {"fixture-profile": timing_member},
            "complete": True,
            "center_minutes": 60.0,
            "input_fingerprint": "timing-program-fixture",
        },
        cost_input_by_profile={"fixture-profile": _cost()},
        economy_observations={
            "schema_version": 1,
            "observation_set_id": "program-observations",
            "observations": [
                {
                    "observation_id": "program-obs-1",
                    "program_id": "fixture-program",
                    "program_version": 1,
                    "scope": {"kind": "full_route"},
                    "subject": {"kind": "group"},
                    "raw_gold_delta_copper": 7000,
                    "assets": [],
                    "clean": True,
                    "contamination": [],
                    "source_ref": "fixture-program-run",
                }
            ],
        },
        market_valuations=_valuations(),
    )
    assert report["gross_copper"] == 6500
    assert report["matched_observation_count"] == 1
    assert report["observation_comparisons"][0]["observed_minus_predicted_copper"] == 500
    assert report["member_reports"]["fixture-profile"]["matched_observation_count"] == 0
    assert report["status"] == "pass"


def test_program_economy_incremental_member_update_preserves_other_members() -> None:
    program = {"program_id": "prog", "version": 1, "profile_ids": ["first", "second"]}
    profiles = {
        "first": {"profile_id": "first", "version": 1},
        "second": {"profile_id": "second", "version": 1},
    }
    xp = {
        "member_reports": {
            "first": _xp_report(lower_level=80, upper_level=80),
            "second": _xp_report(lower_level=80, upper_level=80),
        },
        "input_fingerprint": "xp-program",
    }
    timing = {
        "member_reports": {"first": _timing(), "second": _timing()},
        "complete": True,
        "center_minutes": 120.0,
        "input_fingerprint": "timing-program",
    }
    costs = {"first": _cost(), "second": _cost()}
    cards = {
        "first": {42: _card(no_money_from_xp=False)},
        "second": {42: _card(no_money_from_xp=False)},
    }
    baseline = evaluate_route_program_economy(
        program,
        profiles,
        task_cards_by_profile=cards,
        xp_report=xp,
        timing_report=timing,
        cost_input_by_profile=costs,
    )
    first_before = deepcopy(baseline["member_reports"]["first"])
    members = deepcopy(baseline["member_reports"])
    members["second"] = evaluate_route_program_member_economy(
        program,
        "second",
        profiles["second"],
        task_cards={42: _card(no_money_from_xp=True)},
        xp_report=xp,
        timing_report=timing,
        cost_input=costs["second"],
    )
    updated = evaluate_route_program_economy(
        program,
        profiles,
        task_cards_by_profile={},
        xp_report=xp,
        timing_report=timing,
        cost_input_by_profile=costs,
        member_reports=members,
    )

    assert updated["member_reports"]["first"] == first_before
    assert updated["member_reports"]["second"]["gross_copper"] == 1500
    assert updated["gross_copper"] == 8000
