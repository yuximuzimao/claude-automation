from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash, file_sha256
from .route_movement import program_member_movement_report
from .route_service_context import evaluate_profile_service_context

RULE_REGISTRY = ROOT / "data/timing/rule-registry.json"
MODEL_CONFIG = ROOT / "data/timing/model-config.json"
TASK_PARAMETERS = ROOT / "data/timing/task-parameters.json"
PROFILE_ACTION_PARAMETERS = ROOT / "data/timing/profile-action-parameters.json"
FLIGHT_EDGE_BINDINGS = ROOT / "data/timing/flight-edge-bindings.json"
QUEST_SOURCE_INPUTS = ROOT / "data/timing/quest-source-inputs.json"
LEATRIX_FLIGHT_TIMES = ROOT / "data/timing/leatrix-flight-times.json"
TIMING_OBSERVATIONS = ROOT / "data/observations/route-timing-observations.json"
TIMING_RULE = ROOT / "docs/rules/timing-and-benchmarking.md"
LIFECYCLE_SOP = ROOT / "docs/verified-routes/ROUTE-DESIGN-PROCESS.md"


class TimingConfigError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_timing_inputs(inputs: dict[str, Any]) -> None:
    errors: list[str] = []

    def mapping(name: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            errors.append(f"{name} must be an object")
            return {}
        return value

    registry = mapping("rule_registry", inputs.get("rule_registry"))
    if registry.get("schema_version") != 1:
        errors.append("rule_registry.schema_version must be 1")
    rules = mapping("rule_registry.rules", registry.get("rules"))
    allowed_rule_kinds = {"zero_service", "kill_count", "personal_drop", "fixed_object", "fixed_seconds"}
    for rule_id, rule_raw in rules.items():
        rule = mapping(f"rule_registry.rules.{rule_id}", rule_raw)
        if rule.get("kind") not in allowed_rule_kinds:
            errors.append(f"rule_registry.rules.{rule_id}.kind is unsupported")
        required = rule.get("required_inputs")
        if not isinstance(required, list) or any(not isinstance(value, str) or not value for value in required):
            errors.append(f"rule_registry.rules.{rule_id}.required_inputs must be a string array")
        elif len(required) != len(set(required)):
            errors.append(f"rule_registry.rules.{rule_id}.required_inputs contains duplicates")

    model = mapping("model_config", inputs.get("model_config"))
    if model.get("schema_version") != 1:
        errors.append("model_config.schema_version must be 1")
    global_params = mapping("model_config.global", model.get("global"))
    for name in (
        "combat_seconds_per_mob",
        "personal_loot_seconds_per_corpse",
        "fixed_object_seconds_per_character",
        "personal_drop_tail_sigma_multiplier",
        "accept_turnin_base_seconds_per_stop",
        "accept_turnin_per_task_seconds",
    ):
        value = global_params.get(name)
        if not isinstance(value, (int, float)) or value < 0:
            errors.append(f"model_config.global.{name} must be a non-negative number")
    movement = mapping("model_config.movement", model.get("movement"))
    speeds = mapping("model_config.movement.self_move_speed_yards_per_second", movement.get("self_move_speed_yards_per_second"))
    factors = mapping("model_config.movement.path_factor_by_mode", movement.get("path_factor_by_mode"))
    for mode in ("ride", "fly", "swim"):
        for label, table in (("speed", speeds), ("path_factor", factors)):
            value = table.get(mode)
            if value is not None and (not isinstance(value, (int, float)) or value <= 0):
                errors.append(f"model_config.movement {mode} {label} must be positive or null")
    dimensions = mapping("model_config.movement.map_dimensions_yards_by_zone", movement.get("map_dimensions_yards_by_zone"))
    for zone_id, raw in dimensions.items():
        row = mapping(f"model_config.movement.map_dimensions_yards_by_zone.{zone_id}", raw)
        for dimension in ("width", "height"):
            value = row.get(dimension)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"map dimension {zone_id}.{dimension} must be positive")
    profile_dimensions = mapping(
        "model_config.movement.map_dimensions_yards_by_profile",
        movement.get("map_dimensions_yards_by_profile", {}),
    )
    for profile_id, raw in profile_dimensions.items():
        row = mapping(f"model_config.movement.map_dimensions_yards_by_profile.{profile_id}", raw)
        for dimension in ("width", "height"):
            value = row.get(dimension)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"profile map dimension {profile_id}.{dimension} must be positive")
    uncertainty = mapping("model_config.uncertainty", model.get("uncertainty"))
    relative = mapping("model_config.uncertainty.component_relative_by_kind", uncertainty.get("component_relative_by_kind"))
    for kind, value in relative.items():
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            errors.append(f"uncertainty {kind} must be between 0 and 1")
    minimum = uncertainty.get("minimum_matching_clean_observations")
    if not isinstance(minimum, int) or minimum < 1:
        errors.append("model_config.uncertainty.minimum_matching_clean_observations must be >= 1")

    task_config = mapping("task_parameters", inputs.get("task_parameters"))
    if task_config.get("schema_version") != 1:
        errors.append("task_parameters.schema_version must be 1")
    for task_id, raw in mapping("task_parameters.tasks", task_config.get("tasks")).items():
        row = mapping(f"task_parameters.tasks.{task_id}", raw)
        mapping(f"task_parameters.tasks.{task_id}.inputs", row.get("inputs"))

    action_config = mapping("profile_action_parameters", inputs.get("profile_action_parameters"))
    if action_config.get("schema_version") != 1:
        errors.append("profile_action_parameters.schema_version must be 1")
    for profile_id, raw in mapping("profile_action_parameters.profiles", action_config.get("profiles")).items():
        profile_row = mapping(f"profile_action_parameters.profiles.{profile_id}", raw)
        for bucket in ("actions", "services"):
            for row_id, value_raw in mapping(f"profile_action_parameters.profiles.{profile_id}.{bucket}", profile_row.get(bucket, {})).items():
                value = mapping(f"profile_action_parameters.profiles.{profile_id}.{bucket}.{row_id}", value_raw)
                seconds = value.get("seconds")
                if seconds is not None and (not isinstance(seconds, (int, float)) or seconds < 0):
                    errors.append(f"profile action/service seconds must be non-negative: {profile_id}/{bucket}/{row_id}")
    for program_id, raw in mapping("profile_action_parameters.programs", action_config.get("programs", {})).items():
        program_row = mapping(f"profile_action_parameters.programs.{program_id}", raw)
        for operation_id, value_raw in mapping(
            f"profile_action_parameters.programs.{program_id}.operations",
            program_row.get("operations", {}),
        ).items():
            value = mapping(
                f"profile_action_parameters.programs.{program_id}.operations.{operation_id}",
                value_raw,
            )
            seconds = value.get("seconds")
            if seconds is not None and (not isinstance(seconds, (int, float)) or seconds < 0):
                errors.append(
                    f"program transition seconds must be non-negative: {program_id}/operations/{operation_id}"
                )

    bindings = mapping("flight_edge_bindings", inputs.get("flight_edge_bindings"))
    if bindings.get("schema_version") != 1:
        errors.append("flight_edge_bindings.schema_version must be 1")
    for scope_name in ("profiles", "programs"):
        for scope_id, raw in mapping(f"flight_edge_bindings.{scope_name}", bindings.get(scope_name, {})).items():
            for edge_id, binding_raw in mapping(f"flight_edge_bindings.{scope_name}.{scope_id}", raw).items():
                binding = mapping(f"flight_edge_bindings.{scope_name}.{scope_id}.{edge_id}", binding_raw)
                if binding.get("faction") not in {"Horde", "Alliance"}:
                    errors.append(f"flight binding faction invalid: {scope_name}/{scope_id}/{edge_id}")
                if not isinstance(binding.get("world_id"), (int, str)):
                    errors.append(f"flight binding world_id missing: {scope_name}/{scope_id}/{edge_id}")
                if not isinstance(binding.get("path_key"), str) or not binding.get("path_key"):
                    errors.append(f"flight binding path_key missing: {scope_name}/{scope_id}/{edge_id}")

    quest_source = inputs.get("quest_source_inputs")
    if quest_source is not None:
        quest_source = mapping("quest_source_inputs", quest_source)
        if quest_source.get("schema_version") != 1:
            errors.append("quest_source_inputs.schema_version must be 1")
        mapping("quest_source_inputs.tasks", quest_source.get("tasks"))

    observations = inputs.get("timing_observations")
    if observations is not None:
        observations = mapping("timing_observations", observations)
        if observations.get("schema_version") != 1:
            errors.append("timing_observations.schema_version must be 1")
        if not isinstance(observations.get("observations"), list):
            errors.append("timing_observations.observations must be an array")

    leatrix = inputs.get("leatrix_flight_times")
    if leatrix is not None:
        leatrix = mapping("leatrix_flight_times", leatrix)
        if leatrix.get("schema_version") != 1:
            errors.append("leatrix_flight_times.schema_version must be 1")
        mapping("leatrix_flight_times.factions", leatrix.get("factions"))

    if errors:
        raise TimingConfigError("Timing input validation failed: " + "; ".join(errors))


def load_timing_inputs() -> dict[str, Any]:
    inputs = {
        "rule_registry": _load_json(RULE_REGISTRY),
        "model_config": _load_json(MODEL_CONFIG),
        "task_parameters": _load_json(TASK_PARAMETERS),
        "profile_action_parameters": _load_json(PROFILE_ACTION_PARAMETERS),
        "flight_edge_bindings": _load_json(FLIGHT_EDGE_BINDINGS),
        "quest_source_inputs": _load_json(QUEST_SOURCE_INPUTS) if QUEST_SOURCE_INPUTS.exists() else None,
        "leatrix_flight_times": _load_json(LEATRIX_FLIGHT_TIMES) if LEATRIX_FLIGHT_TIMES.exists() else None,
        "timing_observations": _load_json(TIMING_OBSERVATIONS) if TIMING_OBSERVATIONS.exists() else None,
    }
    validate_timing_inputs(inputs)
    return inputs


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(row.get("severity") == "error" for row in issues):
        return "blocked"
    if any(row.get("severity") in {"unknown", "requirement"} for row in issues):
        return "requirements"
    return "pass"


def timing_input_fingerprint(
    profile: dict[str, Any],
    task_cards: dict[int, dict[str, Any]],
    movement_report: dict[str, Any],
    service_report: dict[str, Any],
    character_profile: dict[str, Any],
    inputs: dict[str, Any],
    action_execution: dict[str, str] | None,
) -> str:
    referenced = sorted({int(task_id) for task_id in profile.get("task_ids") or []})
    profile_id = str(profile["profile_id"])
    rule_refs = {
        str(task_id): (task_cards.get(task_id) or {}).get("timing_rule_ref")
        for task_id in referenced
    }
    registry = inputs.get("rule_registry") or {}
    rules = registry.get("rules") or {}
    selected_rules = {
        str(rule_ref): rules.get(str(rule_ref))
        for rule_ref in sorted({value for value in rule_refs.values() if value})
    }
    task_rows = (inputs.get("task_parameters") or {}).get("tasks") or {}
    selected_task_parameters = {
        str(task_id): task_rows[str(task_id)]
        for task_id in referenced
        if str(task_id) in task_rows
    }
    quest_payload = inputs.get("quest_source_inputs")
    quest_rows = (quest_payload.get("tasks") or {}) if isinstance(quest_payload, dict) else {}
    selected_quest_inputs = {
        str(task_id): quest_rows[str(task_id)]
        for task_id in referenced
        if str(task_id) in quest_rows
    }
    quest_source_identity = None
    if selected_quest_inputs and isinstance(quest_payload, dict):
        source = quest_payload.get("source") or {}
        quest_source_identity = {
            "questie_version": source.get("questie_version"),
            "source_sha256": source.get("source_sha256"),
            "correction_parse_failures": source.get("correction_parse_failures"),
        }
    action_profiles = (inputs.get("profile_action_parameters") or {}).get("profiles") or {}
    selected_action_parameters = action_profiles.get(profile_id)
    flight_profiles = (inputs.get("flight_edge_bindings") or {}).get("profiles") or {}
    selected_flight_bindings = flight_profiles.get(profile_id)
    observations = []
    observation_payload = inputs.get("timing_observations")
    if isinstance(observation_payload, dict):
        observations = [
            row
            for row in observation_payload.get("observations") or []
            if row.get("calibration_eligible") is True
            and row.get("profile_id") == profile_id
            and row.get("profile_version") == profile.get("version")
        ]
    model = inputs.get("model_config") or {}
    scoped_model = {
        "schema_version": model.get("schema_version"),
        "model_id": model.get("model_id"),
        "calibration_status": model.get("calibration_status"),
        "global": model.get("global"),
        "movement": model.get("movement"),
        "uncertainty": model.get("uncertainty"),
        "profile_override": (model.get("profile_overrides") or {}).get(profile_id),
    }
    return canonical_json_hash(
        {
            "profile_id": profile_id,
            "profile_version": profile["version"],
            "actions": profile["actions"],
            "step_groups": profile["step_groups"],
            "task_rules": rule_refs,
            "character_profile": character_profile,
            "action_execution": {
                str(action["action_id"]): (action_execution or {}).get(str(action["action_id"]))
                for action in profile["actions"]
                if action.get("when") is not None and action.get("kind") in {"accept", "turnin"}
            },
            "movement_input_fingerprint": movement_report["input_fingerprint"],
            "service_input_fingerprint": service_report["input_fingerprint"],
            "timing_inputs": {
                "rule_registry_identity": {
                    "schema_version": registry.get("schema_version"),
                    "registry_id": registry.get("registry_id"),
                },
                "selected_rules": selected_rules,
                "model": scoped_model,
                "quest_source_identity": quest_source_identity,
                "quest_source_inputs": selected_quest_inputs,
                "task_parameters": selected_task_parameters,
                "profile_action_parameters": selected_action_parameters,
                "flight_edge_bindings": selected_flight_bindings,
                "eligible_observations": observations,
            },
            "leatrix_source": (
                (inputs.get("leatrix_flight_times") or {}).get("source")
                if selected_flight_bindings and inputs.get("leatrix_flight_times") is not None
                else None
            ),
            "contracts": {
                "timing_rule": file_sha256(TIMING_RULE),
                "lifecycle_sop": file_sha256(LIFECYCLE_SOP),
            },
        }
    )


def _task_rule_seconds(
    *,
    task_id: int,
    card: dict[str, Any] | None,
    party_size: int,
    inputs: dict[str, Any],
) -> tuple[float | None, list[dict[str, Any]], dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if card is None:
        return None, [_issue("error", "timing_task_card_missing", task_id=task_id)], {}

    rule_ref = card.get("timing_rule_ref")
    if not rule_ref:
        return (
            None,
            [_issue("requirement", "timing_rule_ref_required", task_id=task_id)],
            {"task_id": task_id, "rule_ref": None},
        )

    registry = inputs["rule_registry"].get("rules") or {}
    rule = registry.get(str(rule_ref))
    if not isinstance(rule, dict):
        return (
            None,
            [_issue("error", "unknown_timing_rule_ref", task_id=task_id, rule_ref=rule_ref)],
            {"task_id": task_id, "rule_ref": rule_ref},
        )

    global_params = (inputs["model_config"].get("global") or {}).copy()
    quest_payload = inputs.get("quest_source_inputs")
    quest_row = (
        ((quest_payload.get("tasks") or {}).get(str(task_id)) or {})
        if isinstance(quest_payload, dict)
        else {}
    )
    quest_params = dict(quest_row.get("inputs") or {})
    task_row = ((inputs["task_parameters"].get("tasks") or {}).get(str(task_id)) or {})
    task_params = dict(task_row.get("inputs") or {})
    # Effective Quest Source provides mechanical baseline quantities. Explicit versioned task Timing
    # parameters are higher-priority reviewed overrides and may replace those baseline values.
    params = {**global_params, **quest_params, **task_params, "party_size": party_size}
    missing = [name for name in rule.get("required_inputs") or [] if params.get(name) is None]
    if missing:
        return (
            None,
            [
                _issue(
                    "requirement",
                    "timing_rule_inputs_required",
                    task_id=task_id,
                    rule_ref=rule_ref,
                    missing_inputs=missing,
                )
            ],
            {"task_id": task_id, "rule_ref": rule_ref, "resolved_inputs": params},
        )

    kind = str(rule.get("kind") or "")
    seconds: float | None = None
    if kind == "zero_service":
        seconds = 0.0
    elif kind == "fixed_seconds":
        seconds = float(params["fixed_service_seconds"])
    elif kind == "kill_count":
        seconds = float(params["kill_count"]) * float(params["combat_seconds_per_mob"])
    elif kind == "fixed_object":
        multiplier = 1 if params["interaction_scope"] == "shared" else int(params["party_size"])
        seconds = (
            float(params["interaction_count"])
            * multiplier
            * float(params["fixed_object_seconds_per_character"])
        )
    elif kind == "personal_drop":
        if int(params["party_size"]) != 5:
            issues.append(
                _issue(
                    "requirement",
                    "personal_drop_party_calibration_required",
                    task_id=task_id,
                    party_size=int(params["party_size"]),
                )
            )
        else:
            required = float(params["required_count"])
            drop_rate = float(params["drop_rate"])
            if not 0 < drop_rate <= 1:
                issues.append(
                    _issue("error", "invalid_drop_rate", task_id=task_id, drop_rate=drop_rate)
                )
            else:
                mean = required / drop_rate
                std = math.sqrt(required * (1.0 - drop_rate)) / drop_rate
                tail = float(params["personal_drop_tail_sigma_multiplier"])
                expected_kills = mean + tail * std
                seconds = expected_kills * (
                    float(params["combat_seconds_per_mob"])
                    + float(params["personal_loot_seconds_per_corpse"])
                )
    else:
        issues.append(
            _issue("error", "unsupported_timing_rule_kind", task_id=task_id, rule_ref=rule_ref, kind=kind)
        )

    return seconds, issues, {
        "task_id": task_id,
        "rule_ref": rule_ref,
        "rule_kind": kind,
        "resolved_inputs": params,
    }


def _action_maps(profile: dict[str, Any]) -> tuple[dict[str, str], dict[str, str | None]]:
    step_by_action: dict[str, str] = {}
    for step in profile["step_groups"]:
        for action_id in step["action_ids"]:
            step_by_action[str(action_id)] = str(step["step_id"])

    visit_by_action: dict[str, str | None] = {}
    current_visit: str | None = None
    for action in profile["actions"]:
        action_id = str(action["action_id"])
        if action["kind"] == "location":
            current_visit = action_id
        visit_by_action[action_id] = current_visit
    return step_by_action, visit_by_action


def _self_move_seconds(
    edge: dict[str, Any],
    visit_by_id: dict[str, dict[str, Any]],
    model_config: dict[str, Any],
    character_profile: dict[str, Any] | None = None,
    profile_id: str | None = None,
) -> tuple[float | None, dict[str, Any] | None]:
    from_visit = visit_by_id[edge["from_visit_id"]]
    to_visit = visit_by_id[edge["to_visit_id"]]
    zone_id = from_visit.get("zone_id")
    to_zone_id = to_visit.get("zone_id")
    if zone_id is not None and to_zone_id is not None and to_zone_id != zone_id:
        # Cross-map self movement is transition overhead, not part of either map's wall-clock baseline.
        return 0.0, None
    if zone_id is None:
        return None, _issue(
            "requirement",
            "self_move_zone_model_required",
            edge_id=edge["edge_id"],
            from_zone_id=zone_id,
            to_zone_id=to_zone_id,
        )
    movement_config = model_config.get("movement") or {}
    dims = None
    if profile_id:
        dims = (movement_config.get("map_dimensions_yards_by_profile") or {}).get(str(profile_id))
    if not isinstance(dims, dict):
        dims = (movement_config.get("map_dimensions_yards_by_zone") or {}).get(str(zone_id))
    if not isinstance(dims, dict):
        return None, _issue(
            "requirement",
            "map_dimensions_required",
            edge_id=edge["edge_id"],
            zone_id=zone_id,
            profile_id=profile_id,
        )
    mode = edge.get("movement_mode")
    speeds = (model_config.get("movement") or {}).get("self_move_speed_yards_per_second") or {}
    factors = (model_config.get("movement") or {}).get("path_factor_by_mode") or {}
    speed = speeds.get(str(mode))
    factor = factors.get(str(mode))
    if speed is not None and mode == "ride" and isinstance(character_profile, dict):
        class_name = character_profile.get("class")
        class_multipliers = (model_config.get("movement") or {}).get("ride_speed_multiplier_by_class") or {}
        speed = float(speed) * float(class_multipliers.get(str(class_name), 1.0))
    if speed is None or factor is None:
        return None, _issue(
            "requirement", "self_move_calibration_required", edge_id=edge["edge_id"], movement_mode=mode
        )
    coordinates = (
        from_visit.get("x"),
        from_visit.get("y"),
        to_visit.get("x"),
        to_visit.get("y"),
    )
    if any(
        not isinstance(value, (int, float)) or isinstance(value, bool)
        for value in coordinates
    ):
        return None, _issue(
            "requirement",
            "self_move_coordinates_required",
            edge_id=edge["edge_id"],
            from_location_ref=from_visit.get("location_ref"),
            to_location_ref=to_visit.get("location_ref"),
        )

    width = float(dims["width"])
    height = float(dims["height"])
    dx = (float(to_visit["x"]) - float(from_visit["x"])) / 100.0 * width
    dy = (float(to_visit["y"]) - float(from_visit["y"])) / 100.0 * height
    distance = math.hypot(dx, dy) * float(factor)
    return distance / float(speed), None


def _taxi_seconds(
    *,
    scope_kind: str,
    scope_id: str,
    edge: dict[str, Any],
    inputs: dict[str, Any],
) -> tuple[float | None, dict[str, Any] | None]:
    scope_bindings = (inputs["flight_edge_bindings"].get(scope_kind) or {}).get(scope_id) or {}
    binding = scope_bindings.get(edge["edge_id"])
    if not isinstance(binding, dict):
        return None, _issue(
            "requirement", "flight_edge_binding_required", edge_id=edge["edge_id"]
        )
    leatrix = inputs.get("leatrix_flight_times")
    if not isinstance(leatrix, dict):
        return None, _issue(
            "requirement", "leatrix_flight_times_required", edge_id=edge["edge_id"]
        )
    faction = str(binding["faction"])
    world_id = str(binding["world_id"])
    path_key = str(binding["path_key"])
    try:
        seconds = leatrix["factions"][faction]["worlds"][world_id][path_key]["seconds"]
    except KeyError:
        return None, _issue(
            "error",
            "flight_edge_binding_not_found_in_leatrix",
            edge_id=edge["edge_id"],
            binding=binding,
        )
    return float(seconds), None


def _matching_observation_range(
    *,
    profile: dict[str, Any],
    start_action_id: str,
    end_action_id: str,
    inputs: dict[str, Any],
) -> tuple[list[float] | None, list[str]]:
    payload = inputs.get("timing_observations")
    if not isinstance(payload, dict):
        return None, []
    matches: list[tuple[str, float]] = []
    for row in payload.get("observations") or []:
        if row.get("calibration_eligible") is not True:
            continue
        if row.get("profile_id") != profile.get("profile_id") or row.get("profile_version") != profile.get("version"):
            continue
        scope = row.get("action_scope") or {}
        if scope.get("start_action_id") != start_action_id or scope.get("end_action_id") != end_action_id:
            continue
        actual = row.get("actual_minutes")
        if isinstance(actual, (int, float)) and actual >= 0:
            matches.append((str(row.get("observation_id")), float(actual)))
    minimum = int(((inputs["model_config"].get("uncertainty") or {}).get("minimum_matching_clean_observations") or 2))
    if len(matches) < minimum:
        return None, [row[0] for row in matches]
    values = [row[1] for row in matches]
    return [min(values), max(values)], [row[0] for row in matches]


def _component_uncertainty_range(
    components: dict[str, float],
    model_config: dict[str, Any],
) -> tuple[list[float] | None, list[str]]:
    relative = ((model_config.get("uncertainty") or {}).get("component_relative_by_kind") or {})
    missing = sorted(kind for kind, value in components.items() if value > 0 and relative.get(kind) is None)
    if missing:
        return None, missing
    low = 0.0
    high = 0.0
    for kind, value in components.items():
        if value <= 0:
            continue
        ratio = float(relative[kind])
        low += max(0.0, value * (1.0 - ratio))
        high += value * (1.0 + ratio)
    return [low / 60.0, high / 60.0], []


def _timing_range_for_scope(
    *,
    profile: dict[str, Any],
    start_action_id: str,
    end_action_id: str,
    components: dict[str, float],
    inputs: dict[str, Any],
) -> tuple[list[float] | None, dict[str, Any]]:
    observed, observation_ids = _matching_observation_range(
        profile=profile,
        start_action_id=start_action_id,
        end_action_id=end_action_id,
        inputs=inputs,
    )
    if observed is not None:
        return observed, {"basis": "matching_clean_observations", "observation_ids": observation_ids}
    modeled, missing = _component_uncertainty_range(components, inputs["model_config"])
    if modeled is not None:
        return modeled, {"basis": "component_relative_uncertainty"}
    return None, {
        "basis": "unresolved",
        "matching_observation_ids": observation_ids,
        "missing_component_uncertainty": missing,
    }


def evaluate_profile_timing(
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    movement_report: dict[str, Any],
    service_report: dict[str, Any],
    character_profile: dict[str, Any],
    action_execution: dict[str, str] | None = None,
    timing_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stage-7 prototype: derive only timing components whose machine inputs are actually resolved.

    No guide/presentation/generated-page text is parsed. Unknown task rules, movement calibrations,
    background marginal cost, flight bindings, conditional execution or special action durations remain
    explicit requirements. A precise route center is emitted only when every required component closes.
    """

    inputs = timing_inputs or load_timing_inputs()
    issues: list[dict[str, Any]] = []
    if movement_report["status"] == "blocked":
        issues.append(_issue("error", "upstream_stage5_blocked"))
    elif movement_report["status"] == "requirements":
        issues.append(_issue("requirement", "upstream_stage5_requirements"))
    if service_report["status"] == "blocked":
        issues.append(_issue("error", "upstream_stage6_blocked"))
    elif service_report["status"] == "requirements":
        issues.append(_issue("requirement", "upstream_stage6_requirements"))

    party_size = int(character_profile.get("party_size") or 1)
    step_by_action, visit_by_action = _action_maps(profile)
    action_by_id = {str(row["action_id"]): row for row in profile["actions"]}
    visit_by_id = {str(row["visit_id"]): row for row in movement_report["visits"]}
    step_components: dict[str, dict[str, float]] = {
        str(step["step_id"]): {
            "move_seconds": 0.0,
            "objective_service_seconds": 0.0,
            "accept_turnin_seconds": 0.0,
            "wait_seconds": 0.0,
            "special_seconds": 0.0,
        }
        for step in profile["step_groups"]
    }
    component_rows: list[dict[str, Any]] = []

    # Movement cost belongs to the step containing the target visit.
    action_params = ((inputs["profile_action_parameters"].get("profiles") or {}).get(profile["profile_id"]) or {})
    action_seconds = action_params.get("actions") or {}
    for edge in movement_report["edges"]:
        step_id = step_by_action.get(str(edge["to_visit_id"]))
        operation = edge.get("operation_kind")
        seconds: float | None = None
        issue: dict[str, Any] | None = None
        if operation in {"self_move", "move"}:
            seconds, issue = _self_move_seconds(
                edge,
                visit_by_id,
                inputs["model_config"],
                character_profile,
                str(profile["profile_id"]),
            )
        elif operation == "taxi":
            seconds, issue = _taxi_seconds(
                scope_kind="profiles",
                scope_id=str(profile["profile_id"]),
                edge=edge,
                inputs=inputs,
            )
        elif operation in {"hearth", "fixed_transport", "quest_transport"}:
            movement_action_id = str(edge.get("movement_action_id") or "")
            row = action_seconds.get(movement_action_id) or {}
            if row.get("seconds") is None:
                issue = _issue(
                    "requirement",
                    "movement_action_timing_input_required",
                    edge_id=edge["edge_id"],
                    action_id=movement_action_id,
                    operation_kind=operation,
                )
            else:
                seconds = float(row["seconds"])
        else:
            issue = _issue(
                "requirement",
                "movement_operation_timing_unresolved",
                edge_id=edge["edge_id"],
                operation_kind=operation,
            )
        if issue is not None:
            if step_id is not None:
                issue["step_id"] = step_id
            issues.append(issue)
        if seconds is not None and step_id is not None:
            step_components[step_id]["move_seconds"] += seconds
            component_rows.append(
                {"component": "move", "edge_id": edge["edge_id"], "step_id": step_id, "seconds": seconds}
            )

    if movement_report.get("exit_movement_actions"):
        issues.append(
            _issue(
                "requirement",
                "profile_exit_movement_timing_requires_program_context",
                action_ids=[row["action_id"] for row in movement_report["exit_movement_actions"]],
            )
        )

    # Hub handling: one base charge per physical visit. Conditional task actions consume the single
    # Stage-3 Replay execution result; Timing never re-evaluates task_active/task_complete/has_item.
    hub_by_visit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in profile["actions"]:
        if action["kind"] not in {"accept", "turnin"}:
            continue
        action_id = str(action["action_id"])
        visit_id = visit_by_action.get(action_id)
        if visit_id is None:
            issues.append(_issue("error", "hub_action_without_visit", action_id=action_id))
            continue
        if action.get("when") is not None:
            execution = (action_execution or {}).get(action_id)
            if execution == "skipped":
                continue
            if execution == "maybe":
                issues.append(
                    _issue(
                        "requirement",
                        "conditional_hub_action_execution_maybe",
                        action_id=action_id,
                        task_id=int(action["task_id"]),
                        step_id=step_by_action.get(action_id),
                    )
                )
                continue
            if execution != "executed":
                issues.append(
                    _issue(
                        "requirement",
                        "conditional_hub_action_execution_required",
                        action_id=action_id,
                        task_id=int(action["task_id"]),
                        step_id=step_by_action.get(action_id),
                    )
                )
                continue
        hub_by_visit[str(visit_id)].append(action)

    global_params = inputs["model_config"].get("global") or {}
    hub_base = float(global_params["accept_turnin_base_seconds_per_stop"])
    hub_per_task = float(global_params["accept_turnin_per_task_seconds"])
    for visit_id, actions in hub_by_visit.items():
        if not actions:
            continue
        first_id = str(actions[0]["action_id"])
        step_id = step_by_action.get(first_id)
        seconds = hub_base + hub_per_task * len(actions)
        if step_id is not None:
            step_components[step_id]["accept_turnin_seconds"] += seconds
        component_rows.append(
            {
                "component": "accept_turnin",
                "visit_id": visit_id,
                "action_ids": [str(row["action_id"]) for row in actions],
                "step_id": step_id,
                "seconds": seconds,
            }
        )

    # Foreground objective service. Explicit shared-service clusters are not double-charged.
    foreground_by_action = {
        str(row["service_action_id"]): row for row in service_report["foreground_services"]
    }
    shared_action_ids: set[str] = set()
    for cluster in service_report["target_clusters"]:
        action_ids = [str(value) for value in cluster.get("action_ids") or []]
        if cluster.get("source") != "route_service_override" or len(action_ids) < 2:
            continue
        shared_action_ids.update(action_ids)
        service_cfg = (action_params.get("services") or {}).get(str(cluster["cluster_id"])) or {}
        step_ids = {step_by_action.get(action_id) for action_id in action_ids}
        step_ids.discard(None)
        if len(step_ids) != 1:
            issues.append(
                _issue(
                    "error",
                    "shared_service_crosses_timing_steps",
                    service_id=cluster["cluster_id"],
                    action_ids=action_ids,
                    step_ids=sorted(step_ids),
                )
            )
            continue
        step_id = next(iter(step_ids)) if step_ids else None
        if service_cfg.get("seconds") is None:
            issues.append(
                _issue(
                    "requirement",
                    "shared_service_timing_input_required",
                    service_id=cluster["cluster_id"],
                    action_ids=action_ids,
                    step_id=step_id,
                )
            )
            continue
        seconds = float(service_cfg["seconds"])
        if step_id is not None:
            step_components[step_id]["objective_service_seconds"] += seconds
        component_rows.append(
            {
                "component": "objective_service",
                "basis": "shared_service_override",
                "service_id": cluster["cluster_id"],
                "action_ids": action_ids,
                "step_id": step_id,
                "seconds": seconds,
            }
        )

    for action_id, service in foreground_by_action.items():
        if action_id in shared_action_ids:
            continue
        task_id = int(service["task_id"])
        seconds, task_issues, resolution = _task_rule_seconds(
            task_id=task_id,
            card=task_cards.get(task_id),
            party_size=party_size,
            inputs=inputs,
        )
        step_id = step_by_action.get(action_id)
        for issue in task_issues:
            issue.setdefault("action_id", action_id)
            issue.setdefault("step_id", step_id)
            issues.append(issue)
        if seconds is not None and step_id is not None:
            step_components[step_id]["objective_service_seconds"] += seconds
            component_rows.append(
                {
                    "component": "objective_service",
                    "action_id": action_id,
                    "task_id": task_id,
                    "step_id": step_id,
                    "seconds": seconds,
                    "resolution": resolution,
                }
            )

    # Route-only background coverage is explicit, but its marginal service still needs timing input
    # unless the route decision itself says it is fully covered with zero independent service.
    for layer in service_report["background_layers"]:
        policy = str(layer["end_policy"])
        service_id = str(layer["service_id"])
        step_id = step_by_action.get(str(layer["end_action_id"]))
        if policy == "covered_complete":
            component_rows.append(
                {
                    "component": "objective_service",
                    "basis": "background_covered_complete",
                    "service_id": service_id,
                    "task_id": int(layer["task_id"]),
                    "step_id": step_id,
                    "seconds": 0.0,
                }
            )
            continue
        service_cfg = (action_params.get("services") or {}).get(service_id) or {}
        if service_cfg.get("seconds") is None:
            issues.append(
                _issue(
                    "requirement",
                    "background_marginal_timing_input_required",
                    service_id=service_id,
                    task_id=int(layer["task_id"]),
                    end_policy=policy,
                    step_id=step_id,
                )
            )
            continue
        seconds = float(service_cfg["seconds"])
        if step_id is not None:
            step_components[step_id]["objective_service_seconds"] += seconds
        component_rows.append(
            {
                "component": "objective_service",
                "basis": "background_service_calibration",
                "service_id": service_id,
                "task_id": int(layer["task_id"]),
                "step_id": step_id,
                "seconds": seconds,
            }
        )

    # Cost resolution and range resolution are separate. A point estimate may be machine-complete
    # while uncertainty is still missing; in that case keep the center and mark the artifact as a
    # requirement rather than erasing known work or inventing a generic +/- percentage.
    cost_issues = list(issues)
    unresolved_by_step: dict[str, int] = defaultdict(int)
    global_unresolved = 0
    for issue in cost_issues:
        if issue.get("severity") not in {"requirement", "unknown", "error"}:
            continue
        step_id = issue.get("step_id")
        if step_id is None:
            global_unresolved += 1
        else:
            unresolved_by_step[str(step_id)] += 1

    steps: list[dict[str, Any]] = []
    total_known_seconds = 0.0
    route_components: dict[str, float] = defaultdict(float)
    for step in profile["step_groups"]:
        step_id = str(step["step_id"])
        components = step_components[step_id]
        known_seconds = sum(components.values())
        total_known_seconds += known_seconds
        for kind, value in components.items():
            route_components[kind] += value
        unresolved = unresolved_by_step.get(step_id, 0) + global_unresolved
        point_estimate_complete = unresolved == 0
        range_minutes: list[float] | None = None
        range_basis: dict[str, Any] | None = None
        if point_estimate_complete:
            action_ids = [str(value) for value in step["action_ids"]]
            range_minutes, range_basis = _timing_range_for_scope(
                profile=profile,
                start_action_id=action_ids[0],
                end_action_id=action_ids[-1],
                components=components,
                inputs=inputs,
            )
            if range_minutes is None:
                issues.append(
                    _issue(
                        "requirement",
                        "timing_range_model_required",
                        step_id=step_id,
                        scope="step",
                        detail=range_basis,
                    )
                )
        steps.append(
            {
                "step_id": step_id,
                "title": step.get("title"),
                "known_seconds": round(known_seconds, 3),
                "center_minutes": round(known_seconds / 60.0, 3) if point_estimate_complete else None,
                "range_minutes": [round(value, 3) for value in range_minutes] if range_minutes is not None else None,
                "range_basis": range_basis,
                "point_estimate_complete": point_estimate_complete,
                "complete": point_estimate_complete and range_minutes is not None,
                "unresolved_component_count": unresolved,
                "components": {key: round(value, 3) for key, value in components.items()},
            }
        )

    route_point_estimate_complete = not any(
        row.get("severity") in {"requirement", "unknown", "error"} for row in cost_issues
    )
    route_range: list[float] | None = None
    route_range_basis: dict[str, Any] | None = None
    if route_point_estimate_complete and profile["actions"]:
        route_range, route_range_basis = _timing_range_for_scope(
            profile=profile,
            start_action_id=str(profile["actions"][0]["action_id"]),
            end_action_id=str(profile["actions"][-1]["action_id"]),
            components=dict(route_components),
            inputs=inputs,
        )
        if route_range is None:
            issues.append(
                _issue(
                    "requirement",
                    "timing_range_model_required",
                    scope="profile",
                    detail=route_range_basis,
                )
            )

    status = _status(issues)
    complete = route_point_estimate_complete and route_range is not None and status == "pass"
    return {
        "profile_id": profile["profile_id"],
        "status": status,
        "model_id": inputs["model_config"].get("model_id"),
        "input_fingerprint": timing_input_fingerprint(
            profile,
            task_cards,
            movement_report,
            service_report,
            character_profile,
            inputs,
            action_execution,
        ),
        "known_seconds": round(total_known_seconds, 3),
        "center_minutes": round(total_known_seconds / 60.0, 3) if route_point_estimate_complete else None,
        "range_minutes": [round(value, 3) for value in route_range] if route_range is not None else None,
        "range_basis": route_range_basis,
        "point_estimate_complete": route_point_estimate_complete,
        "complete": complete,
        "steps": steps,
        "component_rows": component_rows,
        "issues": issues,
        "summary": {
            "step_count": len(steps),
            "issue_count": len(issues),
            "requirement_count": sum(1 for row in issues if row.get("severity") in {"requirement", "unknown"}),
            "error_count": sum(1 for row in issues if row.get("severity") == "error"),
            "range_model_status": "resolved" if route_range is not None else "requirements",
        },
    }


def _program_boundary_seconds(
    *,
    program_id: str,
    boundary: dict[str, Any],
    program_movement_report: dict[str, Any],
    inputs: dict[str, Any],
) -> tuple[float | None, dict[str, Any] | None]:
    if boundary.get("status") == "blocked":
        return None, _issue(
            "error",
            "upstream_stage5_program_boundary_blocked",
            edge_id=boundary["edge_id"],
            upstream_issues=boundary.get("issues") or [],
        )
    if boundary.get("status") == "requirements":
        return None, _issue(
            "requirement",
            "upstream_stage5_program_boundary_requirements",
            edge_id=boundary["edge_id"],
            upstream_issues=boundary.get("issues") or [],
        )

    operation = boundary.get("operation_kind")
    if operation == "handoff":
        return 0.0, None
    if operation == "transition_chain":
        total_seconds = 0.0
        operation_issues: list[dict[str, Any]] = []
        program_cfg = ((inputs["profile_action_parameters"].get("programs") or {}).get(program_id) or {})
        operation_params = program_cfg.get("operations") or {}
        for row in boundary.get("operations") or []:
            operation_id = str(row["operation_id"])
            operation_kind = str(row["operation_kind"])
            if operation_kind == "taxi":
                seconds, issue = _taxi_seconds(
                    scope_kind="programs",
                    scope_id=program_id,
                    edge={**row, "edge_id": operation_id},
                    inputs=inputs,
                )
            else:
                configured = operation_params.get(operation_id) or {}
                seconds = configured.get("seconds")
                issue = None
                if seconds is None:
                    issue = _issue(
                        "requirement",
                        "program_transition_operation_timing_input_required",
                        edge_id=boundary["edge_id"],
                        operation_id=operation_id,
                        operation_kind=operation_kind,
                    )
                else:
                    seconds = float(seconds)
            if issue is not None:
                operation_issues.append(issue)
            elif seconds is not None:
                total_seconds += float(seconds)

        if operation_issues:
            return None, _issue(
                "requirement",
                "program_transition_timing_requirements",
                edge_id=boundary["edge_id"],
                operation_issues=operation_issues,
            )
        return total_seconds, None
    if operation in {"self_move", "move"}:
        members = program_movement_report["member_reports"]
        source = members[boundary["from_profile_id"]]
        target = members[boundary["to_profile_id"]]
        from_visit = source["visits"][-1]
        to_visit = target["visits"][0]
        synthetic = {
            **boundary,
            "from_visit_id": "__from__",
            "to_visit_id": "__to__",
        }
        return _self_move_seconds(
            synthetic,
            {"__from__": from_visit, "__to__": to_visit},
            inputs["model_config"],
        )
    if operation == "taxi":
        return _taxi_seconds(
            scope_kind="programs",
            scope_id=program_id,
            edge=boundary,
            inputs=inputs,
        )
    if operation in {"hearth", "fixed_transport", "quest_transport"}:
        source_profile_id = str(boundary["from_profile_id"])
        action_id = str(boundary.get("movement_action_id") or "")
        profile_cfg = ((inputs["profile_action_parameters"].get("profiles") or {}).get(source_profile_id) or {})
        row = (profile_cfg.get("actions") or {}).get(action_id) or {}
        if row.get("seconds") is None:
            return None, _issue(
                "requirement",
                "program_boundary_action_timing_input_required",
                edge_id=boundary["edge_id"],
                profile_id=source_profile_id,
                action_id=action_id,
                operation_kind=operation,
            )
        return float(row["seconds"]), None
    return None, _issue(
        "requirement",
        "program_boundary_timing_unresolved",
        edge_id=boundary["edge_id"],
        operation_kind=operation,
    )


def evaluate_route_program_member_timing(
    program: dict[str, Any],
    profile_id: str,
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]],
    character_profile: dict[str, Any],
    program_movement_report: dict[str, Any],
    program_service_report: dict[str, Any],
    continuity_report: dict[str, Any],
    timing_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate Timing for exactly one Program member using current Program-context artifacts."""

    if profile_id not in program.get("profile_ids", []):
        raise TimingConfigError(
            f"Profile {profile_id!r} is not a member of Program {program.get('program_id')!r}"
        )
    service = ((program_service_report.get("member_reports") or {}).get(profile_id))
    if not isinstance(service, dict):
        raise TimingConfigError(f"Program Service Context missing member report for {profile_id}")
    edge = next(
        (
            row
            for row in continuity_report.get("edges") or []
            if row.get("to") == profile_id
        ),
        None,
    )
    if not isinstance(edge, dict):
        raise TimingConfigError(f"Program Continuity missing member edge for {profile_id}")

    movement = program_member_movement_report(program_movement_report, profile_id)
    return evaluate_profile_timing(
        profile,
        task_cards=task_cards,
        movement_report=movement,
        service_report=service,
        character_profile=character_profile,
        action_execution=dict(edge.get("action_execution") or {}),
        timing_inputs=timing_inputs,
    )


def evaluate_route_program_timing(
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    *,
    task_cards_by_profile: dict[str, dict[int, dict[str, Any]]],
    character_profiles_by_profile: dict[str, dict[str, Any]],
    program_movement_report: dict[str, Any],
    continuity_report: dict[str, Any],
    timing_inputs: dict[str, Any] | None = None,
    program_service_report: dict[str, Any] | None = None,
    member_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate Stage 7 in Program context without creating a second Replay or movement engine."""

    inputs = timing_inputs or load_timing_inputs()
    issues: list[dict[str, Any]] = []
    continuity_status = continuity_report.get("status")
    if continuity_status == "blocked":
        issues.append(_issue("error", "upstream_stage4_blocked"))
    elif continuity_status == "requirements":
        issues.append(_issue("requirement", "upstream_stage4_requirements"))

    execution_by_profile = {
        str(edge["to"]): dict(edge.get("action_execution") or {})
        for edge in continuity_report.get("edges") or []
        if edge.get("to") in program["profile_ids"]
    }

    if member_reports is None:
        member_reports = {}
        program_service_members = (
            (program_service_report or {}).get("member_reports") or {}
            if program_service_report is not None
            else {}
        )
        for profile_id in program["profile_ids"]:
            profile = profiles[profile_id]
            movement = program_member_movement_report(program_movement_report, profile_id)
            if program_service_report is not None:
                service = program_service_members.get(profile_id)
                if not isinstance(service, dict):
                    raise TimingConfigError(
                        f"Program Service Context missing member report for {profile_id}"
                    )
            else:
                service = evaluate_profile_service_context(profile, movement)
            timing = evaluate_profile_timing(
                profile,
                task_cards=task_cards_by_profile[profile_id],
                movement_report=movement,
                service_report=service,
                character_profile=character_profiles_by_profile[profile_id],
                action_execution=execution_by_profile.get(profile_id),
                timing_inputs=inputs,
            )
            member_reports[profile_id] = timing
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
            raise TimingConfigError(
                f"Program member Timing reports mismatch; missing={missing}, extra={extra}"
            )

    member_ranges: list[list[float]] = []
    total_known_seconds = 0.0
    member_point_complete = True
    for profile_id in program["profile_ids"]:
        timing = member_reports[profile_id]
        total_known_seconds += float(timing["known_seconds"])
        if not timing["point_estimate_complete"]:
            member_point_complete = False
        if timing["range_minutes"] is None:
            member_ranges = []
        elif member_ranges is not None:
            member_ranges.append(list(timing["range_minutes"]))
        if timing["status"] == "blocked":
            issues.append(_issue("error", "member_timing_blocked", profile_id=profile_id))
        elif timing["status"] == "requirements":
            issues.append(_issue("requirement", "member_timing_requirements", profile_id=profile_id))

    boundary_rows: list[dict[str, Any]] = []
    boundary_range_minutes: list[list[float]] = []
    boundary_point_complete = True
    for boundary in program_movement_report.get("boundaries") or []:
        seconds, issue = _program_boundary_seconds(
            program_id=str(program["program_id"]),
            boundary=boundary,
            program_movement_report=program_movement_report,
            inputs=inputs,
        )
        if issue is not None:
            issues.append(issue)
        range_minutes: list[float] | None = None
        range_basis: dict[str, Any] | None = None
        if seconds is None:
            boundary_point_complete = False
        elif seconds == 0:
            range_minutes = [0.0, 0.0]
            range_basis = {"basis": "zero_cost_handoff"}
            total_known_seconds += seconds
        else:
            total_known_seconds += seconds
            modeled, missing = _component_uncertainty_range(
                {"move_seconds": float(seconds)},
                inputs["model_config"],
            )
            if modeled is None:
                issues.append(
                    _issue(
                        "requirement",
                        "program_boundary_range_model_required",
                        edge_id=boundary["edge_id"],
                        missing_component_uncertainty=missing,
                    )
                )
            else:
                range_minutes = modeled
                range_basis = {"basis": "component_relative_uncertainty"}
        if range_minutes is not None:
            boundary_range_minutes.append(range_minutes)
        boundary_rows.append(
            {
                "edge_id": boundary["edge_id"],
                "from_profile_id": boundary["from_profile_id"],
                "to_profile_id": boundary["to_profile_id"],
                "operation_kind": boundary.get("operation_kind"),
                "seconds": round(seconds, 3) if seconds is not None else None,
                "range_minutes": [round(value, 3) for value in range_minutes] if range_minutes else None,
                "range_basis": range_basis,
                "complete": seconds is not None and range_minutes is not None,
            }
        )

    point_estimate_complete = (
        continuity_status in {"ok", "pass"}
        and member_point_complete
        and boundary_point_complete
    )
    all_member_ranges = all(report.get("range_minutes") is not None for report in member_reports.values())
    all_boundary_ranges = all(row.get("range_minutes") is not None for row in boundary_rows)
    program_range: list[float] | None = None
    if point_estimate_complete and all_member_ranges and all_boundary_ranges:
        low = sum(float(report["range_minutes"][0]) for report in member_reports.values())
        high = sum(float(report["range_minutes"][1]) for report in member_reports.values())
        low += sum(float(row["range_minutes"][0]) for row in boundary_rows)
        high += sum(float(row["range_minutes"][1]) for row in boundary_rows)
        program_range = [round(low, 3), round(high, 3)]

    selected_program_binding = ((inputs["flight_edge_bindings"].get("programs") or {}).get(program["program_id"]) or {})
    selected_program_transition_parameters = (
        (inputs["profile_action_parameters"].get("programs") or {}).get(program["program_id"]) or {}
    )
    selected_boundary_actions: dict[str, Any] = {}
    action_profiles = inputs["profile_action_parameters"].get("profiles") or {}
    for boundary in program_movement_report.get("boundaries") or []:
        if not boundary.get("movement_action_id"):
            continue
        source_cfg = action_profiles.get(str(boundary["from_profile_id"])) or {}
        selected_boundary_actions[str(boundary["edge_id"])] = (source_cfg.get("actions") or {}).get(
            str(boundary["movement_action_id"])
        )
    input_fingerprint = canonical_json_hash(
        {
            "program_id": program["program_id"],
            "program_version": program["version"],
            "profile_ids": list(program["profile_ids"]),
            "program_movement_input_fingerprint": program_movement_report.get("input_fingerprint"),
            "continuity_input_fingerprint": continuity_report.get("input_fingerprint"),
            "action_execution": execution_by_profile,
            "member_timing_input_fingerprints": {
                profile_id: report["input_fingerprint"] for profile_id, report in member_reports.items()
            },
            "program_flight_bindings": selected_program_binding,
            "program_transition_parameters": selected_program_transition_parameters,
            "boundary_action_parameters": selected_boundary_actions,
            "movement_uncertainty": (inputs["model_config"].get("uncertainty") or {}).get("component_relative_by_kind"),
            "leatrix_source": (
                (inputs.get("leatrix_flight_times") or {}).get("source")
                if selected_program_binding and inputs.get("leatrix_flight_times") is not None
                else None
            ),
            "contracts": {
                "timing_rule": file_sha256(TIMING_RULE),
                "lifecycle_sop": file_sha256(LIFECYCLE_SOP),
            },
        }
    )

    status = _status(issues)
    complete = point_estimate_complete and program_range is not None and status == "pass"
    return {
        "kind": "route_program",
        "program_id": program["program_id"],
        "status": status,
        "model_id": inputs["model_config"].get("model_id"),
        "input_fingerprint": input_fingerprint,
        "known_seconds": round(total_known_seconds, 3),
        "center_minutes": round(total_known_seconds / 60.0, 3) if point_estimate_complete else None,
        "range_minutes": program_range,
        "point_estimate_complete": point_estimate_complete,
        "complete": complete,
        "member_reports": member_reports,
        "boundary_rows": boundary_rows,
        "issues": issues,
        "summary": {
            "profile_count": len(member_reports),
            "boundary_count": len(boundary_rows),
            "issue_count": len(issues),
            "requirement_count": sum(1 for row in issues if row.get("severity") in {"requirement", "unknown"}),
            "error_count": sum(1 for row in issues if row.get("severity") == "error"),
        },
    }
