from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash

XP_MODEL_CONFIG = ROOT / "data/xp-model/model-config.json"


class XpModelError(ValueError):
    """Raised when the Stage 8 machine contract is invalid."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _result_status(issues: list[dict[str, Any]]) -> str:
    if any(issue["severity"] == "error" for issue in issues):
        return "blocked"
    if any(issue["severity"] == "requirement" for issue in issues):
        return "requirements"
    return "pass"


def load_xp_model_config(path: Path = XP_MODEL_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_xp_model_config(config)
    return config


def validate_xp_model_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(config.get("model_id"), str) or not config["model_id"]:
        errors.append("model_id missing")
    if not isinstance(config.get("game_variant_id"), str) or not config["game_variant_id"]:
        errors.append("game_variant_id missing")
    multiplier = config.get("server_quest_xp_multiplier")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or multiplier <= 0:
        errors.append("server_quest_xp_multiplier must be > 0")
    max_level = config.get("max_level")
    if not isinstance(max_level, int) or max_level < 2:
        errors.append("max_level must be an integer >= 2")
    table = config.get("xp_to_next_by_level")
    if not isinstance(table, dict):
        errors.append("xp_to_next_by_level must be an object")
    elif isinstance(max_level, int):
        expected = {str(level) for level in range(1, max_level)}
        actual = set(table)
        missing = sorted(expected - actual, key=int)
        extra = sorted(actual - expected, key=lambda value: int(value) if str(value).isdigit() else 10**9)
        if missing:
            errors.append(f"xp_to_next_by_level missing levels: {missing}")
        if extra:
            errors.append(f"xp_to_next_by_level unexpected levels: {extra}")
        for level in sorted(expected, key=int):
            value = table.get(level)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"xp_to_next_by_level[{level}] must be positive integer")
    if errors:
        raise XpModelError("XP model config invalid: " + "; ".join(errors))


def _round_quest_xp(value: float) -> int:
    if value <= 100:
        return int(5 * math.floor((value + 2) / 5))
    if value <= 500:
        return int(10 * math.floor((value + 5) / 10))
    if value <= 1000:
        return int(25 * math.floor((value + 12) / 25))
    return int(50 * math.floor((value + 25) / 50))


def base_quest_xp_at_level_values(*, quest_level: int, full_xp: int, player_level: int) -> int:
    """Return unmultiplied WotLK quest XP at a turn-in level.

    This is the sole code implementation of the WotLK quest-level decay/rounding formula. Stage 8
    applies the versioned server multiplier; Stage 9 may reuse the base value for max-level money.
    """

    if full_xp <= 0:
        return 0
    multiplier10 = max(1, min(10, 2 * (int(quest_level) - int(player_level)) + 20))
    return _round_quest_xp(int(full_xp) * multiplier10 / 10.0)


def quest_xp_at_level(
    *,
    quest_level: int,
    full_xp: int,
    player_level: int,
    model_config: dict[str, Any],
) -> int:
    """Return server-rate quest XP at the actual turn-in level.

    The formula is owned by docs/rules/xp-model.md. The server multiplier is a versioned
    machine input. At max level Stage 8 awards no leveling XP; Stage 9 owns XP-to-money.
    """

    max_level = int(model_config["max_level"])
    if player_level >= max_level:
        return 0
    base_xp = base_quest_xp_at_level_values(
        quest_level=quest_level,
        full_xp=full_xp,
        player_level=player_level,
    )
    return int(math.floor(base_xp * float(model_config["server_quest_xp_multiplier"])))


def _xp_to_next(model_config: dict[str, Any], level: int) -> int:
    try:
        return int(model_config["xp_to_next_by_level"][str(level)])
    except (KeyError, TypeError, ValueError) as exc:
        raise XpModelError(f"missing XP threshold for level {level}") from exc


def _validate_entry_state(entry_state: dict[str, Any], model_config: dict[str, Any]) -> None:
    if not isinstance(entry_state, dict):
        raise XpModelError("XP entry state must be an object")
    source = entry_state.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("kind"), str) or not source["kind"]:
        raise XpModelError("XP entry state requires source.kind")
    characters = entry_state.get("characters")
    if not isinstance(characters, list) or not characters:
        raise XpModelError("XP entry state requires non-empty characters")
    max_level = int(model_config["max_level"])
    seen: set[str] = set()
    for row in characters:
        if not isinstance(row, dict):
            raise XpModelError("XP character state must be an object")
        character_id = row.get("character_id")
        level = row.get("level")
        xp_into_level = row.get("xp_into_level")
        if not isinstance(character_id, str) or not character_id:
            raise XpModelError("XP character state requires character_id")
        if character_id in seen:
            raise XpModelError(f"duplicate XP character_id: {character_id}")
        seen.add(character_id)
        if not isinstance(level, int) or isinstance(level, bool) or not (1 <= level <= max_level):
            raise XpModelError(f"invalid level for {character_id}: {level}")
        if not isinstance(xp_into_level, int) or isinstance(xp_into_level, bool) or xp_into_level < 0:
            raise XpModelError(f"invalid xp_into_level for {character_id}: {xp_into_level}")
        if level >= max_level:
            if xp_into_level != 0:
                raise XpModelError(f"max-level character {character_id} must use xp_into_level=0")
        elif xp_into_level >= _xp_to_next(model_config, level):
            raise XpModelError(f"xp_into_level exceeds threshold for {character_id} level {level}")


def _copy_characters(entry_state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "character_id": str(row["character_id"]),
            "level": int(row["level"]),
            "xp_into_level": int(row["xp_into_level"]),
        }
        for row in entry_state["characters"]
    ]


def _advance_character(row: dict[str, Any], gained: int, model_config: dict[str, Any]) -> None:
    max_level = int(model_config["max_level"])
    if row["level"] >= max_level or gained <= 0:
        return
    row["xp_into_level"] += int(gained)
    while row["level"] < max_level:
        threshold = _xp_to_next(model_config, int(row["level"]))
        if row["xp_into_level"] < threshold:
            break
        row["xp_into_level"] -= threshold
        row["level"] += 1
        if row["level"] >= max_level:
            row["xp_into_level"] = 0
            break


def _absolute_progress(row: dict[str, Any], model_config: dict[str, Any]) -> int:
    level = int(row["level"])
    return sum(_xp_to_next(model_config, value) for value in range(1, level)) + int(row["xp_into_level"])


def _state_payload(source: dict[str, Any], characters: list[dict[str, Any]]) -> dict[str, Any]:
    return {"source": deepcopy(source), "characters": deepcopy(characters)}


def _quest_xp_inputs(card: dict[str, Any] | None) -> tuple[int, int] | None:
    if not isinstance(card, dict):
        return None
    availability = card.get("availability") or {}
    rewards = card.get("rewards") or {}
    quest_level = availability.get("quest_level")
    full_xp = rewards.get("full_xp")
    if not isinstance(quest_level, int) or not isinstance(full_xp, int):
        return None
    return int(quest_level), int(full_xp)


def _evaluate_profile_scenarios(
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    lower_characters: list[dict[str, Any]],
    upper_characters: list[dict[str, Any]] | None,
    action_execution: dict[str, str],
    deferred_gates: list[dict[str, Any]],
    model_config: dict[str, Any],
    upper_bound_known: bool,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    turnins: list[dict[str, Any]] = []
    level_gates: list[dict[str, Any]] = []
    gates_by_action: dict[str, list[dict[str, Any]]] = {}
    for gate in deferred_gates:
        if gate.get("kind") == "min_level" and gate.get("resolver") == "derived_xp":
            gates_by_action.setdefault(str(gate["action_id"]), []).append(gate)

    for action in profile["actions"]:
        action_id = str(action["action_id"])
        execution = action_execution.get(action_id, "executed")
        if execution == "skipped":
            continue
        if execution not in {"executed", "maybe"}:
            issues.append(_issue("requirement", "stage4_action_execution_required", action_id=action_id))
            continue

        for gate in gates_by_action.get(action_id, []):
            required = int(gate["required_min_level"])
            lower_levels = {row["character_id"]: int(row["level"]) for row in lower_characters}
            upper_levels = (
                {row["character_id"]: int(row["level"]) for row in upper_characters}
                if upper_characters is not None
                else None
            )
            if execution == "maybe":
                gate_status = "requirements"
                issues.append(
                    _issue(
                        "requirement",
                        "conditional_level_gate_execution_maybe",
                        action_id=action_id,
                        task_id=int(gate["task_id"]),
                        required_min_level=required,
                    )
                )
            elif min(lower_levels.values()) >= required:
                gate_status = "pass"
            elif upper_levels is not None and min(upper_levels.values()) < required:
                gate_status = "blocked"
                issues.append(
                    _issue(
                        "error",
                        "min_level_unreachable_within_xp_upper_bound",
                        action_id=action_id,
                        task_id=int(gate["task_id"]),
                        required_min_level=required,
                        lower_levels=lower_levels,
                        upper_levels=upper_levels,
                    )
                )
            else:
                gate_status = "requirements"
                issues.append(
                    _issue(
                        "requirement",
                        "min_level_not_guaranteed",
                        action_id=action_id,
                        task_id=int(gate["task_id"]),
                        required_min_level=required,
                        lower_levels=lower_levels,
                        upper_levels=upper_levels,
                    )
                )
            level_gates.append(
                {
                    "action_id": action_id,
                    "task_id": int(gate["task_id"]),
                    "required_min_level": required,
                    "status": gate_status,
                    "lower_levels": lower_levels,
                    "upper_levels": upper_levels,
                }
            )

        if action.get("kind") != "turnin":
            continue
        task_id = int(action["task_id"])
        if execution == "maybe":
            issues.append(
                _issue(
                    "requirement",
                    "conditional_turnin_execution_maybe",
                    action_id=action_id,
                    task_id=task_id,
                )
            )
            continue
        inputs = _quest_xp_inputs(task_cards.get(task_id))
        if inputs is None:
            issues.append(
                _issue(
                    "requirement",
                    "task_xp_input_required",
                    action_id=action_id,
                    task_id=task_id,
                )
            )
            continue
        quest_level, full_xp = inputs
        lower_results: list[dict[str, Any]] = []
        upper_results: list[dict[str, Any]] | None = [] if upper_characters is not None else None
        for row in lower_characters:
            before = {"level": row["level"], "xp_into_level": row["xp_into_level"]}
            gained = quest_xp_at_level(
                quest_level=quest_level,
                full_xp=full_xp,
                player_level=int(row["level"]),
                model_config=model_config,
            )
            _advance_character(row, gained, model_config)
            lower_results.append(
                {
                    "character_id": row["character_id"],
                    "before": before,
                    "xp_gained": gained,
                    "after": {"level": row["level"], "xp_into_level": row["xp_into_level"]},
                    "last_full_xp_level": quest_level + 5,
                    "decayed": before["level"] > quest_level + 5,
                }
            )
        if upper_characters is not None and upper_results is not None:
            for row in upper_characters:
                before = {"level": row["level"], "xp_into_level": row["xp_into_level"]}
                gained = quest_xp_at_level(
                    quest_level=quest_level,
                    full_xp=full_xp,
                    player_level=int(row["level"]),
                    model_config=model_config,
                )
                _advance_character(row, gained, model_config)
                upper_results.append(
                    {
                        "character_id": row["character_id"],
                        "before": before,
                        "xp_gained": gained,
                        "after": {"level": row["level"], "xp_into_level": row["xp_into_level"]},
                        "last_full_xp_level": quest_level + 5,
                        "decayed": before["level"] > quest_level + 5,
                    }
                )
        turnins.append(
            {
                "action_id": action_id,
                "task_id": task_id,
                "quest_level": quest_level,
                "full_xp": full_xp,
                "lower": lower_results,
                "upper": upper_results,
            }
        )

    if not upper_bound_known:
        issues.append(
            _issue(
                "requirement",
                "external_xp_upper_bound_required",
                profile_id=profile["profile_id"],
                note="Risk upper bound cannot be inferred from route prose, timing, or historical natural-XP ratios.",
            )
        )

    return {
        "profile_id": profile["profile_id"],
        "issues": issues,
        "turnins": turnins,
        "level_gates": level_gates,
        "lower_characters": lower_characters,
        "upper_characters": upper_characters,
    }


def evaluate_profile_xp(
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    action_execution: dict[str, str],
    deferred_gates: list[dict[str, Any]],
    entry_state: dict[str, Any] | None,
    external_xp_upper_bound_by_character: dict[str, int] | None = None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = model_config or load_xp_model_config()
    issues: list[dict[str, Any]] = []
    if profile.get("scope", {}).get("game_variant_id") != config["game_variant_id"]:
        issues.append(
            _issue(
                "error",
                "xp_model_game_variant_mismatch",
                profile_id=profile["profile_id"],
                profile_variant=profile.get("scope", {}).get("game_variant_id"),
                model_variant=config["game_variant_id"],
            )
        )
    if entry_state is None:
        issues.append(_issue("requirement", "xp_entry_state_required", profile_id=profile["profile_id"]))
        return {
            "kind": "profile",
            "profile_id": profile["profile_id"],
            "status": _result_status(issues),
            "issues": issues,
            "input_fingerprint": canonical_json_hash(
                {
                    "profile_id": profile["profile_id"],
                    "profile_version": profile["version"],
                    "model": config,
                    "entry_state": None,
                    "action_execution": action_execution,
                    "deferred_gates": deferred_gates,
                }
            ),
            "entry_state": None,
            "exit_state_lower": None,
            "exit_state_risk_upper": None,
            "turnins": [],
            "level_gates": [],
            "guaranteed_lower_bound": None,
            "possible_upper_bound": None,
        }

    _validate_entry_state(entry_state, config)
    lower = _copy_characters(entry_state)
    upper = _copy_characters(entry_state) if external_xp_upper_bound_by_character is not None else None
    upper_known = external_xp_upper_bound_by_character is not None
    if upper is not None:
        ids = {row["character_id"] for row in upper}
        if set(external_xp_upper_bound_by_character or {}) != ids:
            raise XpModelError("external_xp_upper_bound_by_character must exactly match entry character ids")
        for row in upper:
            value = external_xp_upper_bound_by_character[row["character_id"]]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise XpModelError("external XP upper bounds must be non-negative integers")
            _advance_character(row, value, config)

    lower_start = _copy_characters(entry_state)
    upper_start = deepcopy(upper) if upper is not None else None
    evaluated = _evaluate_profile_scenarios(
        profile,
        task_cards=task_cards,
        lower_characters=lower,
        upper_characters=upper,
        action_execution=action_execution,
        deferred_gates=deferred_gates,
        model_config=config,
        upper_bound_known=upper_known,
    )
    issues.extend(evaluated["issues"])

    lower_gains = [
        _absolute_progress(end, config) - _absolute_progress(start, config)
        for start, end in zip(lower_start, evaluated["lower_characters"])
    ]
    upper_gains: list[int] | None = None
    upper_total_bound_proven = evaluated["upper_characters"] is not None and upper_start is not None
    if evaluated["upper_characters"] is not None and upper_start is not None:
        # The external allowance is deliberately placed before route actions to maximize level-risk
        # at gates. If that earlier level causes any later quest to award less XP than the lower
        # scenario, this risk scenario is not a mathematical upper bound on final total XP; keep the
        # scalar upper bound UNKNOWN until the external-XP timing is itself structured.
        upper_gains = [
            _absolute_progress(end, config) - _absolute_progress(real_start, config)
            for real_start, end in zip(lower_start, evaluated["upper_characters"])
        ]
        for turnin in evaluated["turnins"]:
            lower_by_character = {row["character_id"]: row["xp_gained"] for row in turnin["lower"]}
            for row in turnin.get("upper") or []:
                if int(row["xp_gained"]) < int(lower_by_character[row["character_id"]]):
                    upper_total_bound_proven = False
                    break
            if not upper_total_bound_proven:
                break
        if not upper_total_bound_proven:
            issues.append(
                _issue(
                    "requirement",
                    "external_xp_timing_required_for_upper_bound",
                    profile_id=profile["profile_id"],
                    note=(
                        "The pre-Profile risk allowance changes quest decay, so it can bound early-level risk "
                        "but cannot prove the maximum final XP total without an ordered external-XP timeline."
                    ),
                )
            )

    fingerprint_payload = {
        "profile": {
            "profile_id": profile["profile_id"],
            "version": profile["version"],
            "game_variant_id": profile.get("scope", {}).get("game_variant_id"),
            "actions": [
                {
                    "action_id": row["action_id"],
                    "kind": row["kind"],
                    "task_id": row.get("task_id"),
                    "when": row.get("when"),
                }
                for row in profile["actions"]
                if row.get("kind") in {"accept", "turnin"}
            ],
        },
        "task_xp_inputs": {
            str(task_id): {
                "quest_level": (card.get("availability") or {}).get("quest_level"),
                "full_xp": (card.get("rewards") or {}).get("full_xp"),
            }
            for task_id, card in sorted(task_cards.items())
            if task_id in {int(row["task_id"]) for row in profile["actions"] if row.get("task_id") is not None}
        },
        "model": config,
        "entry_state": entry_state,
        "external_xp_upper_bound_by_character": external_xp_upper_bound_by_character,
        "action_execution": action_execution,
        "xp_deferred_gates": [
            gate
            for gate in deferred_gates
            if gate.get("kind") == "min_level" and gate.get("resolver") == "derived_xp"
        ],
    }
    return {
        "kind": "profile",
        "profile_id": profile["profile_id"],
        "status": _result_status(issues),
        "issues": issues,
        "input_fingerprint": canonical_json_hash(fingerprint_payload),
        "entry_state": deepcopy(entry_state),
        "exit_state_lower": _state_payload(entry_state["source"], evaluated["lower_characters"]),
        "exit_state_risk_upper": (
            _state_payload(entry_state["source"], evaluated["upper_characters"])
            if evaluated["upper_characters"] is not None
            else None
        ),
        "turnins": evaluated["turnins"],
        "level_gates": evaluated["level_gates"],
        "guaranteed_lower_bound": min(lower_gains) if lower_gains else 0,
        "possible_upper_bound": (
            max(upper_gains)
            if upper_total_bound_proven and upper_gains is not None and upper_gains
            else None
        ),
    }


def evaluate_route_program_xp(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    task_cards_by_profile: dict[str, dict[int, dict[str, Any]]],
    continuity_report: dict[str, Any],
    entry_state: dict[str, Any] | None,
    external_xp_upper_bound_by_profile: dict[str, dict[str, int]] | None = None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = model_config or load_xp_model_config()
    issues: list[dict[str, Any]] = []
    continuity_status = continuity_report.get("status")
    if continuity_status == "blocked":
        issues.append(_issue("error", "upstream_stage4_blocked"))
    elif continuity_status == "requirements":
        issues.append(_issue("requirement", "upstream_stage4_requirements"))

    if entry_state is None:
        issues.append(_issue("requirement", "xp_entry_state_required", program_id=program["program_id"]))
        return {
            "kind": "route_program",
            "program_id": program["program_id"],
            "status": _result_status(issues),
            "issues": issues,
            "input_fingerprint": canonical_json_hash(
                {
                    "program_id": program["program_id"],
                    "program_version": program["version"],
                    "profile_ids": program["profile_ids"],
                    "continuity_input_fingerprint": continuity_report.get("input_fingerprint"),
                    "model": config,
                    "entry_state": None,
                }
            ),
            "entry_state": None,
            "external_xp_upper_bound_by_profile": deepcopy(external_xp_upper_bound_by_profile),
            "member_reports": {},
            "propagated_upper_exit_state_by_profile": {},
            "exit_state_lower": None,
            "exit_state_risk_upper": None,
            "guaranteed_lower_bound": None,
            "possible_upper_bound": None,
        }

    _validate_entry_state(entry_state, config)
    edge_by_profile = {str(edge["to"]): edge for edge in continuity_report.get("edges") or []}
    lower_state = deepcopy(entry_state)
    upper_state = deepcopy(entry_state) if external_xp_upper_bound_by_profile is not None else None
    program_upper_total_bound_proven = external_xp_upper_bound_by_profile is not None
    member_reports: dict[str, dict[str, Any]] = {}
    propagated_upper_exit_state_by_profile: dict[str, dict[str, Any]] = {}
    program_start = _copy_characters(entry_state)

    for profile_id in program["profile_ids"]:
        profile = profiles[profile_id]
        edge = edge_by_profile.get(profile_id)
        if edge is None:
            issues.append(_issue("error", "stage4_program_edge_missing", profile_id=profile_id))
            continue
        external_upper = None
        if external_xp_upper_bound_by_profile is not None:
            external_upper = external_xp_upper_bound_by_profile.get(profile_id)
            if external_upper is None:
                issues.append(_issue("requirement", "profile_external_xp_upper_bound_required", profile_id=profile_id))
        # The member evaluator owns one Profile. For Program propagation the lower exit is exact for
        # guaranteed task XP. The upper scenario is rebuilt from its propagated upper entry below.
        member_entry = deepcopy(lower_state)
        report = evaluate_profile_xp(
            profile,
            task_cards=task_cards_by_profile[profile_id],
            action_execution=dict(edge.get("action_execution") or {}),
            deferred_gates=list(edge.get("deferred_gates") or []),
            entry_state=member_entry,
            external_xp_upper_bound_by_character=external_upper,
            model_config=config,
        )
        member_reports[profile_id] = report
        if report["status"] == "blocked":
            issues.append(_issue("error", "member_xp_blocked", profile_id=profile_id))
        elif report["status"] == "requirements":
            issues.append(_issue("requirement", "member_xp_requirements", profile_id=profile_id))
        if external_upper is not None and report["possible_upper_bound"] is None:
            program_upper_total_bound_proven = False
        lower_state = deepcopy(report["exit_state_lower"] or lower_state)

        if upper_state is not None:
            # Re-evaluate the same Profile from the propagated upper boundary so early extra XP can
            # affect later quest decay and min-level gates instead of being reset per Profile.
            upper_report = evaluate_profile_xp(
                profile,
                task_cards=task_cards_by_profile[profile_id],
                action_execution=dict(edge.get("action_execution") or {}),
                deferred_gates=list(edge.get("deferred_gates") or []),
                entry_state=upper_state,
                external_xp_upper_bound_by_character=external_upper,
                model_config=config,
            )
            if external_upper is not None and upper_report["possible_upper_bound"] is None:
                program_upper_total_bound_proven = False
            upper_state = deepcopy(
                upper_report["exit_state_risk_upper"] or upper_report["exit_state_lower"] or upper_state
            )
            propagated_upper_exit_state_by_profile[profile_id] = deepcopy(upper_state)

    lower_end = lower_state["characters"] if lower_state is not None else []
    lower_gains = [
        _absolute_progress(end, config) - _absolute_progress(start, config)
        for start, end in zip(program_start, lower_end)
    ]
    upper_gains: list[int] | None = None
    if upper_state is not None:
        upper_gains = [
            _absolute_progress(end, config) - _absolute_progress(start, config)
            for start, end in zip(program_start, upper_state["characters"])
        ]
        if not program_upper_total_bound_proven:
            issues.append(
                _issue(
                    "requirement",
                    "program_external_xp_timing_required_for_upper_bound",
                    program_id=program["program_id"],
                    note=(
                        "The Program risk-upper scenario is still useful for early-level gates, but the final "
                        "possible XP total remains UNKNOWN when earlier extra XP changes quest decay."
                    ),
                )
            )

    fingerprint = canonical_json_hash(
        {
            "program_id": program["program_id"],
            "program_version": program["version"],
            "profile_ids": list(program["profile_ids"]),
            "continuity_input_fingerprint": continuity_report.get("input_fingerprint"),
            "model": config,
            "entry_state": entry_state,
            "external_xp_upper_bound_by_profile": external_xp_upper_bound_by_profile,
            "member_input_fingerprints": {
                profile_id: report["input_fingerprint"] for profile_id, report in member_reports.items()
            },
        }
    )
    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "status": _result_status(issues),
        "issues": issues,
        "input_fingerprint": fingerprint,
        "entry_state": deepcopy(entry_state),
        "external_xp_upper_bound_by_profile": deepcopy(external_xp_upper_bound_by_profile),
        "member_reports": member_reports,
        "propagated_upper_exit_state_by_profile": propagated_upper_exit_state_by_profile,
        "exit_state_lower": lower_state,
        "exit_state_risk_upper": upper_state,
        "guaranteed_lower_bound": min(lower_gains) if lower_gains else 0,
        "possible_upper_bound": (
            max(upper_gains)
            if program_upper_total_bound_proven and upper_gains is not None and upper_gains
            else None
        ),
    }



def update_route_program_xp_from_profile(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    task_cards_by_profile: dict[str, dict[int, dict[str, Any]]],
    continuity_report: dict[str, Any],
    current_report: dict[str, Any],
    start_profile_id: str,
    external_xp_upper_bound_by_profile: dict[str, dict[str, int]] | None = None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute Program XP only from one changed member through the dependent suffix."""

    config = model_config or load_xp_model_config()
    profile_ids = list(program["profile_ids"])
    if start_profile_id not in profile_ids:
        raise XpModelError(
            f"Profile {start_profile_id!r} is not a member of Program {program['program_id']!r}"
        )
    if current_report.get("program_id") != program["program_id"]:
        raise XpModelError("current Program XP artifact belongs to a different Program")
    entry_state = current_report.get("entry_state")
    if not isinstance(entry_state, dict):
        raise XpModelError(
            "incremental Program XP requires an existing baseline with explicit entry_state"
        )
    _validate_entry_state(entry_state, config)

    start_index = profile_ids.index(start_profile_id)
    members = deepcopy(current_report.get("member_reports") or {})
    upper_trace = deepcopy(
        current_report.get("propagated_upper_exit_state_by_profile") or {}
    )

    for profile_id in profile_ids[:start_index]:
        report = members.get(profile_id)
        if not isinstance(report, dict) or not isinstance(report.get("exit_state_lower"), dict):
            raise XpModelError(
                f"incremental Program XP prefix missing usable report for {profile_id}"
            )

    for profile_id in profile_ids[start_index:]:
        members.pop(profile_id, None)
        upper_trace.pop(profile_id, None)

    if start_index == 0:
        lower_state = deepcopy(entry_state)
    else:
        previous_id = profile_ids[start_index - 1]
        lower_state = deepcopy(members[previous_id]["exit_state_lower"])

    upper_state: dict[str, Any] | None = None
    if external_xp_upper_bound_by_profile is not None:
        if start_index == 0:
            upper_state = deepcopy(entry_state)
        else:
            previous_id = profile_ids[start_index - 1]
            previous_upper = upper_trace.get(previous_id)
            if not isinstance(previous_upper, dict):
                raise XpModelError(
                    "incremental Program XP upper-bound propagation requires a baseline "
                    f"upper state after {previous_id}; rebuild from the Program start"
                )
            upper_state = deepcopy(previous_upper)

    edge_by_profile = {
        str(edge["to"]): edge for edge in continuity_report.get("edges") or []
    }
    for profile_id in profile_ids[start_index:]:
        profile = profiles[profile_id]
        edge = edge_by_profile.get(profile_id)
        if edge is None:
            raise XpModelError(f"Program Continuity missing member edge for {profile_id}")

        external_upper = None
        if external_xp_upper_bound_by_profile is not None:
            external_upper = external_xp_upper_bound_by_profile.get(profile_id)

        report = evaluate_profile_xp(
            profile,
            task_cards=task_cards_by_profile[profile_id],
            action_execution=dict(edge.get("action_execution") or {}),
            deferred_gates=list(edge.get("deferred_gates") or []),
            entry_state=deepcopy(lower_state),
            external_xp_upper_bound_by_character=external_upper,
            model_config=config,
        )
        members[profile_id] = report
        if isinstance(report.get("exit_state_lower"), dict):
            lower_state = deepcopy(report["exit_state_lower"])

        if upper_state is not None:
            upper_report = evaluate_profile_xp(
                profile,
                task_cards=task_cards_by_profile[profile_id],
                action_execution=dict(edge.get("action_execution") or {}),
                deferred_gates=list(edge.get("deferred_gates") or []),
                entry_state=deepcopy(upper_state),
                external_xp_upper_bound_by_character=external_upper,
                model_config=config,
            )
            upper_state = deepcopy(
                upper_report.get("exit_state_risk_upper")
                or upper_report.get("exit_state_lower")
                or upper_state
            )
            upper_trace[profile_id] = deepcopy(upper_state)

    issues: list[dict[str, Any]] = []
    continuity_status = continuity_report.get("status")
    if continuity_status == "blocked":
        issues.append(_issue("error", "upstream_stage4_blocked"))
    elif continuity_status == "requirements":
        issues.append(_issue("requirement", "upstream_stage4_requirements"))

    for profile_id in profile_ids:
        report = members.get(profile_id)
        if not isinstance(report, dict):
            issues.append(_issue("error", "member_xp_report_missing", profile_id=profile_id))
            continue
        if report.get("status") == "blocked":
            issues.append(_issue("error", "member_xp_blocked", profile_id=profile_id))
        elif report.get("status") == "requirements":
            issues.append(_issue("requirement", "member_xp_requirements", profile_id=profile_id))
        if (
            external_xp_upper_bound_by_profile is not None
            and external_xp_upper_bound_by_profile.get(profile_id) is None
        ):
            issues.append(
                _issue(
                    "requirement",
                    "profile_external_xp_upper_bound_required",
                    profile_id=profile_id,
                )
            )

    program_upper_total_bound_proven = external_xp_upper_bound_by_profile is not None
    if program_upper_total_bound_proven and start_index > 0:
        program_upper_total_bound_proven = current_report.get("possible_upper_bound") is not None
    if program_upper_total_bound_proven:
        for profile_id in profile_ids[start_index:]:
            report = members.get(profile_id) or {}
            if report.get("possible_upper_bound") is None:
                program_upper_total_bound_proven = False
                break

    program_start = _copy_characters(entry_state)
    lower_end = lower_state.get("characters") if isinstance(lower_state, dict) else []
    lower_gains = [
        _absolute_progress(end, config) - _absolute_progress(start, config)
        for start, end in zip(program_start, lower_end)
    ]

    upper_gains: list[int] | None = None
    if upper_state is not None:
        upper_gains = [
            _absolute_progress(end, config) - _absolute_progress(start, config)
            for start, end in zip(program_start, upper_state["characters"])
        ]
        if not program_upper_total_bound_proven:
            issues.append(
                _issue(
                    "requirement",
                    "program_external_xp_timing_required_for_upper_bound",
                    program_id=program["program_id"],
                )
            )

    fingerprint = canonical_json_hash(
        {
            "program_id": program["program_id"],
            "program_version": program["version"],
            "profile_ids": profile_ids,
            "continuity_input_fingerprint": continuity_report.get("input_fingerprint"),
            "model": config,
            "entry_state": entry_state,
            "external_xp_upper_bound_by_profile": external_xp_upper_bound_by_profile,
            "member_input_fingerprints": {
                profile_id: members[profile_id].get("input_fingerprint")
                for profile_id in profile_ids
                if profile_id in members
            },
        }
    )
    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "status": _result_status(issues),
        "issues": issues,
        "input_fingerprint": fingerprint,
        "entry_state": deepcopy(entry_state),
        "external_xp_upper_bound_by_profile": deepcopy(external_xp_upper_bound_by_profile),
        "member_reports": members,
        "propagated_upper_exit_state_by_profile": upper_trace,
        "exit_state_lower": deepcopy(lower_state),
        "exit_state_risk_upper": deepcopy(upper_state),
        "guaranteed_lower_bound": min(lower_gains) if lower_gains else 0,
        "possible_upper_bound": (
            max(upper_gains)
            if program_upper_total_bound_proven and upper_gains is not None and upper_gains
            else None
        ),
    }
