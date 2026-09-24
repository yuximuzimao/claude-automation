from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash
from .route_xp import base_quest_xp_at_level_values


ECONOMY_MODEL_CONFIG = ROOT / "data/economy-model/model-config.json"
ECONOMY_OBSERVATIONS = ROOT / "data/observations/route-economy-observations.json"
MARKET_VALUATIONS = ROOT / "data/economy-model/market-valuations.json"


class EconomyModelError(ValueError):
    """Raised when the Stage 9 machine contract is invalid."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(issue["severity"] == "error" for issue in issues):
        return "blocked"
    if any(issue["severity"] in {"requirement", "unknown"} for issue in issues):
        return "requirements"
    return "pass"


def load_economy_model_config(path: Path = ECONOMY_MODEL_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_economy_model_config(config)
    return config


def validate_economy_model_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(config.get("model_id"), str) or not config["model_id"]:
        errors.append("model_id missing")
    if not isinstance(config.get("game_variant_id"), str) or not config["game_variant_id"]:
        errors.append("game_variant_id missing")
    max_level = config.get("max_level")
    if not isinstance(max_level, int) or isinstance(max_level, bool) or max_level < 2:
        errors.append("max_level must be an integer >= 2")
    copper = config.get("xp_conversion_copper_per_base_xp")
    if not isinstance(copper, int) or isinstance(copper, bool) or copper <= 0:
        errors.append("xp_conversion_copper_per_base_xp must be a positive integer")
    if config.get("max_level_quest_cash_policy") != "max_reward_money_or_xp_conversion":
        errors.append("unsupported max_level_quest_cash_policy")
    if config.get("fixed_reward_policy") != "all_vendor_total":
        errors.append("unsupported fixed_reward_policy")
    if config.get("choice_reward_policy") != "max_vendor_total_one_choice":
        errors.append("unsupported choice_reward_policy")
    cost_policy = config.get("cost_policy")
    if not isinstance(cost_policy, dict) or cost_policy.get("missing_cost_input_coverage") not in {"partial", "unknown"}:
        errors.append("cost_policy.missing_cost_input_coverage must be partial or unknown")
    if errors:
        raise EconomyModelError("Economy model config invalid: " + "; ".join(errors))


def validate_economy_observations(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(payload.get("observation_set_id"), str) or not payload["observation_set_id"]:
        errors.append("observation_set_id missing")
    observations = payload.get("observations")
    if not isinstance(observations, list):
        errors.append("observations must be an array")
        observations = []
    seen: set[str] = set()
    for index, row in enumerate(observations):
        prefix = f"observations[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        observation_id = row.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id:
            errors.append(f"{prefix}.observation_id missing")
        elif observation_id in seen:
            errors.append(f"duplicate observation_id: {observation_id}")
        else:
            seen.add(observation_id)
        profile_id = row.get("profile_id")
        program_id = row.get("program_id")
        has_profile = isinstance(profile_id, str) and bool(profile_id)
        has_program = isinstance(program_id, str) and bool(program_id)
        if has_profile == has_program:
            errors.append(f"{prefix} must bind exactly one of profile_id or program_id")
        if has_profile:
            version = row.get("profile_version")
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                errors.append(f"{prefix}.profile_version must be positive integer")
            if row.get("program_version") is not None:
                errors.append(f"{prefix}.program_version is invalid for profile observation")
        if has_program:
            version = row.get("program_version")
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                errors.append(f"{prefix}.program_version must be positive integer")
            if row.get("profile_version") is not None:
                errors.append(f"{prefix}.profile_version is invalid for program observation")
        scope = row.get("scope")
        if not isinstance(scope, dict) or scope.get("kind") not in {"full_route", "action_range"}:
            errors.append(f"{prefix}.scope.kind must be full_route or action_range")
        elif scope.get("kind") == "action_range":
            if has_program:
                errors.append(f"{prefix}.scope.action_range is not supported for program observations")
            if not isinstance(scope.get("start_action_id"), str) or not scope["start_action_id"]:
                errors.append(f"{prefix}.scope.start_action_id missing")
            if not isinstance(scope.get("end_action_id"), str) or not scope["end_action_id"]:
                errors.append(f"{prefix}.scope.end_action_id missing")
        subject = row.get("subject")
        if not isinstance(subject, dict) or subject.get("kind") not in {"group", "character"}:
            errors.append(f"{prefix}.subject.kind must be group or character")
        elif subject.get("kind") == "character" and (not isinstance(subject.get("character_id"), str) or not subject["character_id"]):
            errors.append(f"{prefix}.subject.character_id missing")
        gold = row.get("raw_gold_delta_copper")
        if gold is not None and (not isinstance(gold, int) or isinstance(gold, bool)):
            errors.append(f"{prefix}.raw_gold_delta_copper must be integer or null")
        assets = row.get("assets")
        if not isinstance(assets, list):
            errors.append(f"{prefix}.assets must be an array")
            assets = []
        for asset_index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                errors.append(f"{prefix}.assets[{asset_index}] must be an object")
                continue
            if not isinstance(asset.get("asset_id"), str) or not asset["asset_id"]:
                errors.append(f"{prefix}.assets[{asset_index}].asset_id missing")
            quantity = asset.get("quantity")
            if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity < 0:
                errors.append(f"{prefix}.assets[{asset_index}].quantity must be >= 0")
        if gold is None and not assets:
            errors.append(f"{prefix} must contain raw gold delta or at least one asset quantity")
        if not isinstance(row.get("clean"), bool):
            errors.append(f"{prefix}.clean must be boolean")
        contamination = row.get("contamination")
        if not isinstance(contamination, list) or not all(isinstance(item, str) and item for item in contamination):
            errors.append(f"{prefix}.contamination must be a string array")
        if not isinstance(row.get("source_ref"), str) or not row["source_ref"]:
            errors.append(f"{prefix}.source_ref missing")
    if errors:
        raise EconomyModelError("Economy observations invalid: " + "; ".join(errors))


def validate_market_valuations(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(payload.get("valuation_set_id"), str) or not payload["valuation_set_id"]:
        errors.append("valuation_set_id missing")
    assets = payload.get("assets")
    if not isinstance(assets, dict):
        errors.append("assets must be an object")
        assets = {}
    for asset_id, row in assets.items():
        if not isinstance(asset_id, str) or not asset_id:
            errors.append("asset id must be non-empty string")
            continue
        if not isinstance(row, dict):
            errors.append(f"assets[{asset_id}] must be an object")
            continue
        copper = row.get("copper_per_unit")
        if not isinstance(copper, int) or isinstance(copper, bool) or copper < 0:
            errors.append(f"assets[{asset_id}].copper_per_unit must be non-negative integer")
        if not isinstance(row.get("source_ref"), str) or not row["source_ref"]:
            errors.append(f"assets[{asset_id}].source_ref missing")
    if errors:
        raise EconomyModelError("Market valuations invalid: " + "; ".join(errors))


def load_economy_inputs() -> dict[str, Any]:
    model_config = load_economy_model_config()
    observations = json.loads(ECONOMY_OBSERVATIONS.read_text(encoding="utf-8"))
    valuations = json.loads(MARKET_VALUATIONS.read_text(encoding="utf-8"))
    validate_economy_observations(observations)
    validate_market_valuations(valuations)
    return {
        "model_config": model_config,
        "economy_observations": observations,
        "market_valuations": valuations,
    }


def _matching_observations(
    *,
    target_kind: str,
    target_id: str,
    target_version: int,
    payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    id_key = "profile_id" if target_kind == "profile" else "program_id"
    version_key = "profile_version" if target_kind == "profile" else "program_version"
    return [
        row
        for row in payload.get("observations") or []
        if isinstance(row, dict)
        and row.get(id_key) == target_id
        and row.get(version_key) == target_version
        and isinstance(row.get("scope"), dict)
        and row["scope"].get("kind") == "full_route"
        and row.get("clean") is True
        and not (row.get("contamination") or [])
    ]


def _observation_comparisons(
    *,
    target_kind: str,
    target_id: str,
    target_version: int,
    characters: list[dict[str, Any]],
    group_gross_copper: int | None,
    observations: dict[str, Any] | None,
    valuations: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    matched = _matching_observations(
        target_kind=target_kind,
        target_id=target_id,
        target_version=target_version,
        payload=observations,
    )
    valuation_assets = (valuations or {}).get("assets") or {}
    valuation_set_id = (valuations or {}).get("valuation_set_id")
    by_character = {row["character_id"]: row for row in characters}
    issues: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    selected_valuations: dict[str, Any] = {}
    for observation in matched:
        raw_gold = observation.get("raw_gold_delta_copper")
        asset_known = 0
        unknown_assets: list[str] = []
        valued_assets: list[dict[str, Any]] = []
        for asset in observation.get("assets") or []:
            asset_id = str(asset["asset_id"])
            quantity = float(asset["quantity"])
            valuation = valuation_assets.get(asset_id)
            if not isinstance(valuation, dict):
                unknown_assets.append(asset_id)
                continue
            copper_per_unit = int(valuation["copper_per_unit"])
            copper_total = int(round(quantity * copper_per_unit))
            asset_known += copper_total
            selected_valuations[asset_id] = valuation
            valued_assets.append(
                {
                    "asset_id": asset_id,
                    "quantity": quantity,
                    "copper_per_unit": copper_per_unit,
                    "copper_total": copper_total,
                }
            )
        if unknown_assets:
            issues.append(
                _issue(
                    "requirement",
                    "observation_market_valuation_required",
                    observation_id=observation["observation_id"],
                    asset_ids=sorted(set(unknown_assets)),
                )
            )
        known_observed = (int(raw_gold) if raw_gold is not None else 0) + asset_known
        observed_total = known_observed if raw_gold is not None and not unknown_assets else None
        subject = observation["subject"]
        predicted = group_gross_copper
        if subject.get("kind") == "character":
            character = by_character.get(subject.get("character_id"))
            predicted = character.get("gross_copper") if isinstance(character, dict) else None
        comparisons.append(
            {
                "observation_id": observation["observation_id"],
                "subject": subject,
                "raw_gold_delta_copper": raw_gold,
                "valued_assets": valued_assets,
                "unknown_asset_ids": sorted(set(unknown_assets)),
                "known_observed_value_copper": known_observed,
                "observed_total_copper": observed_total,
                "predicted_gross_copper": predicted,
                "observed_minus_predicted_copper": (
                    observed_total - int(predicted)
                    if observed_total is not None and predicted is not None
                    else None
                ),
                "valuation_set_id": valuation_set_id,
                "source_ref": observation["source_ref"],
            }
        )
    fingerprint_inputs = {
        "observations": matched,
        "valuation_set_id": valuation_set_id if matched else None,
        "valuations": selected_valuations,
    }
    return comparisons, issues, fingerprint_inputs


def _reward_inputs(card: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(card, dict):
        return None
    rewards = card.get("rewards")
    availability = card.get("availability")
    if not isinstance(rewards, dict) or not isinstance(availability, dict):
        return None
    required = ("reward_money_copper", "gear_sale_max_copper", "full_xp")
    if any(not isinstance(rewards.get(key), int) or isinstance(rewards.get(key), bool) or rewards[key] < 0 for key in required):
        return None
    quest_level = availability.get("quest_level")
    if not isinstance(quest_level, int) or isinstance(quest_level, bool):
        return None
    return {
        "quest_level": quest_level,
        "full_xp": int(rewards["full_xp"]),
        "reward_money_copper": int(rewards["reward_money_copper"]),
        "gear_sale_max_copper": int(rewards["gear_sale_max_copper"]),
        "no_money_from_xp": rewards.get("no_money_from_xp"),
        "repeatability": ((card.get("identity") or {}).get("repeatability")),
    }


def _character_map(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]] | None:
    if rows is None:
        return None
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        character_id = row.get("character_id")
        if isinstance(character_id, str) and character_id:
            result[character_id] = row
    return result


def _max_level_conversion_copper(
    *,
    quest_level: int,
    full_xp: int,
    no_money_from_xp: bool,
    model_config: dict[str, Any],
) -> int:
    if no_money_from_xp:
        return 0
    base_xp = base_quest_xp_at_level_values(
        quest_level=quest_level,
        full_xp=full_xp,
        player_level=int(model_config["max_level"]),
    )
    return base_xp * int(model_config["xp_conversion_copper_per_base_xp"])


def _normalize_cost_input(
    character_ids: list[str],
    cost_input: dict[str, Any] | None,
) -> tuple[dict[str, int], str, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if cost_input is None:
        issues.append(
            _issue(
                "requirement",
                "route_cost_coverage_incomplete",
                note="No structured current-scope cost input was supplied; known cost remains zero with partial coverage.",
            )
        )
        return {character_id: 0 for character_id in character_ids}, "partial", issues
    if not isinstance(cost_input, dict):
        raise EconomyModelError("cost_input must be an object")
    coverage = cost_input.get("coverage")
    if coverage not in {"complete", "partial"}:
        raise EconomyModelError("cost_input.coverage must be complete or partial")
    source = cost_input.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("kind"), str) or not source["kind"]:
        raise EconomyModelError("cost_input requires source.kind")
    raw = cost_input.get("known_cost_copper_by_character")
    if not isinstance(raw, dict):
        raise EconomyModelError("cost_input.known_cost_copper_by_character must be an object")
    costs: dict[str, int] = {}
    for character_id in character_ids:
        value = raw.get(character_id)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise EconomyModelError(f"missing/invalid known cost for {character_id}")
        costs[character_id] = value
    if coverage != "complete":
        issues.append(_issue("requirement", "route_cost_coverage_incomplete", coverage=coverage))
    return costs, coverage, issues


def evaluate_profile_economy(
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    xp_report: dict[str, Any],
    timing_report: dict[str, Any] | None,
    cost_input: dict[str, Any] | None = None,
    economy_observations: dict[str, Any] | None = None,
    market_valuations: dict[str, Any] | None = None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = model_config or load_economy_model_config()
    validate_economy_model_config(config)
    issues: list[dict[str, Any]] = []

    if xp_report.get("status") == "blocked":
        issues.append(_issue("error", "upstream_stage8_blocked", profile_id=profile["profile_id"]))
    elif xp_report.get("status") == "requirements":
        issues.append(_issue("requirement", "upstream_stage8_requirements", profile_id=profile["profile_id"]))

    entry_state = xp_report.get("entry_state")
    character_rows = (entry_state or {}).get("characters") if isinstance(entry_state, dict) else None
    if not isinstance(character_rows, list) or not character_rows:
        issues.append(_issue("requirement", "economy_character_state_required", profile_id=profile["profile_id"]))
        character_ids: list[str] = []
    else:
        character_ids = [str(row["character_id"]) for row in character_rows if isinstance(row, dict) and row.get("character_id")]

    costs, cost_coverage, cost_issues = _normalize_cost_input(character_ids, cost_input)
    issues.extend(cost_issues)

    known_gross = {character_id: 0 for character_id in character_ids}
    exact = {character_id: True for character_id in character_ids}
    quest_cash = {character_id: 0 for character_id in character_ids}
    gear_cash = {character_id: 0 for character_id in character_ids}
    turnin_rows: list[dict[str, Any]] = []
    seen_once: dict[str, set[int]] = defaultdict(set)
    max_level = int(config["max_level"])

    for turnin in xp_report.get("turnins") or []:
        task_id = int(turnin["task_id"])
        action_id = str(turnin["action_id"])
        reward = _reward_inputs(task_cards.get(task_id))
        if reward is None:
            issues.append(_issue("requirement", "task_reward_input_required", action_id=action_id, task_id=task_id))
            for character_id in character_ids:
                exact[character_id] = False
            continue

        lower = _character_map(turnin.get("lower")) or {}
        upper = _character_map(turnin.get("upper"))
        character_economy: list[dict[str, Any]] = []
        for character_id in character_ids:
            lower_row = lower.get(character_id)
            if lower_row is None:
                issues.append(_issue("error", "xp_turnin_character_missing", action_id=action_id, task_id=task_id, character_id=character_id))
                exact[character_id] = False
                continue
            if reward["repeatability"] == "once" and task_id in seen_once[character_id]:
                issues.append(_issue("error", "duplicate_once_task_turnin", action_id=action_id, task_id=task_id, character_id=character_id))
                exact[character_id] = False
                continue
            seen_once[character_id].add(task_id)

            lower_level = int((lower_row.get("before") or {}).get("level", 0))
            upper_row = upper.get(character_id) if upper is not None else None
            upper_level = int((upper_row.get("before") or {}).get("level", 0)) if upper_row is not None else None
            lower_at_max = lower_level >= max_level
            max_level_state_exact = lower_at_max or (upper_level is not None and upper_level < max_level)
            if not max_level_state_exact:
                issues.append(
                    _issue(
                        "requirement",
                        "turnin_max_level_state_not_unique",
                        action_id=action_id,
                        task_id=task_id,
                        character_id=character_id,
                        lower_level=lower_level,
                        upper_level=upper_level,
                    )
                )
                exact[character_id] = False

            cash_value: int | None = None
            conversion: int | None = 0
            if lower_at_max:
                flag = reward["no_money_from_xp"]
                if not isinstance(flag, bool):
                    issues.append(
                        _issue(
                            "requirement",
                            "no_money_from_xp_fact_required",
                            action_id=action_id,
                            task_id=task_id,
                            character_id=character_id,
                        )
                    )
                    exact[character_id] = False
                    conversion = None
                else:
                    conversion = _max_level_conversion_copper(
                        quest_level=int(reward["quest_level"]),
                        full_xp=int(reward["full_xp"]),
                        no_money_from_xp=flag,
                        model_config=config,
                    )
                    cash_value = max(int(reward["reward_money_copper"]), conversion)
            else:
                cash_value = int(reward["reward_money_copper"])

            gear_value = int(reward["gear_sale_max_copper"])
            gear_cash[character_id] += gear_value
            known_gross[character_id] += gear_value
            if cash_value is not None:
                quest_cash[character_id] += cash_value
                known_gross[character_id] += cash_value
            else:
                exact[character_id] = False

            character_economy.append(
                {
                    "character_id": character_id,
                    "lower_turnin_level": lower_level,
                    "upper_turnin_level": upper_level,
                    "max_level_state_exact": max_level_state_exact,
                    "quest_cash_copper": cash_value,
                    "xp_conversion_copper": conversion,
                    "gear_sale_copper": gear_value,
                    "known_reward_value_copper": (cash_value + gear_value) if cash_value is not None else None,
                }
            )
        turnin_rows.append(
            {
                "action_id": action_id,
                "task_id": task_id,
                "quest_level": int(reward["quest_level"]),
                "full_xp": int(reward["full_xp"]),
                "no_money_from_xp": reward["no_money_from_xp"],
                "characters": character_economy,
            }
        )

    characters: list[dict[str, Any]] = []
    for character_id in character_ids:
        gross = known_gross[character_id] if exact[character_id] else None
        known_cost = costs[character_id]
        net = gross - known_cost if gross is not None else None
        characters.append(
            {
                "character_id": character_id,
                "quest_cash_copper": quest_cash[character_id],
                "gear_sale_copper": gear_cash[character_id],
                "known_gross_copper": known_gross[character_id],
                "gross_copper": gross,
                "known_cost_copper": known_cost,
                "net_copper": net,
                "exact_reward_total": exact[character_id],
            }
        )

    group_known_gross = sum(row["known_gross_copper"] for row in characters)
    group_gross = sum(int(row["gross_copper"]) for row in characters) if characters and all(row["gross_copper"] is not None for row in characters) else None
    group_known_cost = sum(row["known_cost_copper"] for row in characters)
    group_net = group_gross - group_known_cost if group_gross is not None else None

    observation_comparisons, observation_issues, observation_fingerprint_inputs = _observation_comparisons(
        target_kind="profile",
        target_id=str(profile["profile_id"]),
        target_version=int(profile["version"]),
        characters=characters,
        group_gross_copper=group_gross,
        observations=economy_observations,
        valuations=market_valuations,
    )
    issues.extend(observation_issues)

    timing_complete = bool(timing_report and timing_report.get("complete") and timing_report.get("center_minutes"))
    gross_gph = None
    net_gph = None
    if timing_complete and group_gross is not None:
        hours = float(timing_report["center_minutes"]) / 60.0
        if hours > 0:
            gross_gph = round(group_gross / 10000.0 / hours, 3)
            if group_net is not None:
                net_gph = round(group_net / 10000.0 / hours, 3)
    else:
        issues.append(
            _issue(
                "requirement",
                "fresh_complete_timing_required_for_gph",
                timing_status=timing_report.get("status") if isinstance(timing_report, dict) else None,
                timing_input_fingerprint=timing_report.get("input_fingerprint") if isinstance(timing_report, dict) else None,
            )
        )

    input_fingerprint = canonical_json_hash(
        {
            "profile_id": profile["profile_id"],
            "profile_version": profile["version"],
            "task_rewards": {
                str(task_id): {
                    "availability_quest_level": (task_cards[task_id].get("availability") or {}).get("quest_level"),
                    "rewards": task_cards[task_id].get("rewards"),
                    "repeatability": (task_cards[task_id].get("identity") or {}).get("repeatability"),
                }
                for task_id in sorted(task_cards)
            },
            "xp_input_fingerprint": xp_report.get("input_fingerprint"),
            "timing_input_fingerprint": timing_report.get("input_fingerprint") if isinstance(timing_report, dict) else None,
            "cost_input": cost_input,
            "observation_inputs": observation_fingerprint_inputs,
            "model": config,
        }
    )

    return {
        "kind": "profile",
        "profile_id": profile["profile_id"],
        "status": _status(issues),
        "model_id": config["model_id"],
        "input_fingerprint": input_fingerprint,
        "cost_coverage": cost_coverage,
        "turnins": turnin_rows,
        "characters": characters,
        "known_gross_copper": group_known_gross,
        "gross_copper": group_gross,
        "known_cost_copper": group_known_cost,
        "net_copper": group_net,
        "gross_gph": gross_gph,
        "net_gph": net_gph,
        "observation_comparisons": observation_comparisons,
        "matched_observation_count": len(observation_comparisons),
        "timing_input_fingerprint": timing_report.get("input_fingerprint") if isinstance(timing_report, dict) else None,
        "xp_input_fingerprint": xp_report.get("input_fingerprint"),
        "issues": issues,
    }


def evaluate_route_program_member_economy(
    program: dict[str, Any],
    profile_id: str,
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    xp_report: dict[str, Any],
    timing_report: dict[str, Any] | None,
    cost_input: dict[str, Any] | None = None,
    economy_observations: dict[str, Any] | None = None,
    market_valuations: dict[str, Any] | None = None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute Economy for exactly one Route Program member."""

    if profile_id not in program.get("profile_ids", []):
        raise EconomyModelError(
            f"Profile {profile_id!r} is not a member of Program {program.get('program_id')!r}"
        )
    xp_member = (xp_report.get("member_reports") or {}).get(profile_id)
    if not isinstance(xp_member, dict):
        raise EconomyModelError(f"Program XP missing member report for {profile_id}")
    timing_member = ((timing_report or {}).get("member_reports") or {}).get(profile_id)
    return evaluate_profile_economy(
        profile,
        task_cards=task_cards,
        xp_report=xp_member,
        timing_report=timing_member,
        cost_input=cost_input,
        economy_observations=economy_observations,
        market_valuations=market_valuations,
        model_config=model_config,
    )


def evaluate_route_program_economy(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    task_cards_by_profile: dict[str, dict[int, dict[str, Any]]],
    xp_report: dict[str, Any],
    timing_report: dict[str, Any] | None,
    cost_input_by_profile: dict[str, dict[str, Any]] | None = None,
    economy_observations: dict[str, Any] | None = None,
    market_valuations: dict[str, Any] | None = None,
    model_config: dict[str, Any] | None = None,
    member_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config = model_config or load_economy_model_config()
    validate_economy_model_config(config)
    issues: list[dict[str, Any]] = []
    cost_inputs = cost_input_by_profile or {}

    if member_reports is None:
        member_reports = {}
        xp_members = xp_report.get("member_reports") or {}
        timing_members = (timing_report or {}).get("member_reports") or {}
        for profile_id in program["profile_ids"]:
            member_xp = xp_members.get(profile_id)
            if not isinstance(member_xp, dict):
                issues.append(
                    _issue("requirement", "member_xp_report_required", profile_id=profile_id)
                )
                continue
            member_reports[profile_id] = evaluate_profile_economy(
                profiles[profile_id],
                task_cards=task_cards_by_profile[profile_id],
                xp_report=member_xp,
                timing_report=timing_members.get(profile_id),
                cost_input=cost_inputs.get(profile_id),
                economy_observations=economy_observations,
                market_valuations=market_valuations,
                model_config=config,
            )
    else:
        missing = [
            profile_id for profile_id in program["profile_ids"]
            if profile_id not in member_reports
        ]
        extra = [
            profile_id for profile_id in member_reports
            if profile_id not in program["profile_ids"]
        ]
        if missing or extra:
            raise EconomyModelError(
                f"Program member Economy reports mismatch; missing={missing}, extra={extra}"
            )

    for profile_id in program["profile_ids"]:
        member = member_reports.get(profile_id)
        if not isinstance(member, dict):
            continue
        if member["status"] == "blocked":
            issues.append(_issue("error", "member_economy_blocked", profile_id=profile_id))
        elif member["status"] == "requirements":
            issues.append(_issue("requirement", "member_economy_requirements", profile_id=profile_id))

    character_totals: dict[str, dict[str, Any]] = {}
    for profile_id in program["profile_ids"]:
        member = member_reports.get(profile_id)
        if member is None:
            continue
        for row in member["characters"]:
            character_id = row["character_id"]
            target = character_totals.setdefault(
                character_id,
                {
                    "character_id": character_id,
                    "known_gross_copper": 0,
                    "gross_copper": 0,
                    "known_cost_copper": 0,
                    "net_copper": 0,
                    "exact_reward_total": True,
                },
            )
            target["known_gross_copper"] += row["known_gross_copper"]
            target["known_cost_copper"] += row["known_cost_copper"]
            if row["gross_copper"] is None:
                target["gross_copper"] = None
                target["net_copper"] = None
                target["exact_reward_total"] = False
            elif target["gross_copper"] is not None:
                target["gross_copper"] += row["gross_copper"]
                target["net_copper"] = target["gross_copper"] - target["known_cost_copper"]

    characters = [character_totals[key] for key in sorted(character_totals)]
    known_gross = sum(row["known_gross_copper"] for row in characters)
    gross = sum(int(row["gross_copper"]) for row in characters) if characters and all(row["gross_copper"] is not None for row in characters) else None
    known_cost = sum(row["known_cost_copper"] for row in characters)
    net = gross - known_cost if gross is not None else None
    cost_coverage = "complete" if member_reports and all(member["cost_coverage"] == "complete" for member in member_reports.values()) else "partial"

    observation_comparisons, observation_issues, observation_fingerprint_inputs = _observation_comparisons(
        target_kind="program",
        target_id=str(program["program_id"]),
        target_version=int(program["version"]),
        characters=characters,
        group_gross_copper=gross,
        observations=economy_observations,
        valuations=market_valuations,
    )
    issues.extend(observation_issues)

    timing_complete = bool(timing_report and timing_report.get("complete") and timing_report.get("center_minutes"))
    gross_gph = None
    net_gph = None
    if timing_complete and gross is not None:
        hours = float(timing_report["center_minutes"]) / 60.0
        if hours > 0:
            gross_gph = round(gross / 10000.0 / hours, 3)
            if net is not None:
                net_gph = round(net / 10000.0 / hours, 3)
    else:
        issues.append(_issue("requirement", "fresh_complete_program_timing_required_for_gph"))

    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "status": _status(issues),
        "model_id": config["model_id"],
        "input_fingerprint": canonical_json_hash(
            {
                "program_id": program["program_id"],
                "program_version": program["version"],
                "profile_ids": list(program["profile_ids"]),
                "member_input_fingerprints": {key: value["input_fingerprint"] for key, value in member_reports.items()},
                "xp_input_fingerprint": xp_report.get("input_fingerprint"),
                "timing_input_fingerprint": timing_report.get("input_fingerprint") if isinstance(timing_report, dict) else None,
                "cost_input_by_profile": cost_input_by_profile,
                "observation_inputs": observation_fingerprint_inputs,
                "model": config,
            }
        ),
        "member_reports": member_reports,
        "cost_input_by_profile": cost_input_by_profile,
        "characters": characters,
        "cost_coverage": cost_coverage,
        "known_gross_copper": known_gross,
        "gross_copper": gross,
        "known_cost_copper": known_cost,
        "net_copper": net,
        "gross_gph": gross_gph,
        "net_gph": net_gph,
        "observation_comparisons": observation_comparisons,
        "matched_observation_count": len(observation_comparisons),
        "xp_input_fingerprint": xp_report.get("input_fingerprint"),
        "timing_input_fingerprint": timing_report.get("input_fingerprint") if isinstance(timing_report, dict) else None,
        "issues": issues,
    }
