from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash


REVIEW_TRIGGER_MODEL_CONFIG = ROOT / "data/review-trigger/model-config.json"


class ReviewTriggerError(ValueError):
    """Raised when the Stage 10 machine contract/configuration is invalid."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def load_review_trigger_config(path: Path = REVIEW_TRIGGER_MODEL_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_review_trigger_config(config)
    return config


def validate_review_trigger_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(config.get("model_id"), str) or not config["model_id"]:
        errors.append("model_id missing")
    for key in ("selection_trigger_ids", "optimization_validator_ids", "diagnoses"):
        values = config.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            errors.append(f"{key} must be a non-empty string array")
        elif len(values) != len(set(values)):
            errors.append(f"{key} contains duplicates")
    expected_diagnoses = {"no_review", "selection_review", "optimization_review", "blocked_unknown"}
    if isinstance(config.get("diagnoses"), list) and set(config["diagnoses"]) != expected_diagnoses:
        errors.append("diagnoses must be exactly no_review/selection_review/optimization_review/blocked_unknown")
    policy = config.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    elif any(value not in expected_diagnoses for value in policy.values()):
        errors.append("policy contains unsupported diagnosis")
    if errors:
        raise ReviewTriggerError("Review Trigger config invalid: " + "; ".join(errors))


def _selected_context(
    review_input: dict[str, Any] | None,
    *,
    target_kind: str,
    target_id: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(review_input, dict):
        issues.append(_issue("requirement", "review_context_required"))
        return None, issues
    if review_input.get("schema_version") != 1:
        issues.append(_issue("error", "review_input_schema_invalid", expected=1, actual=review_input.get("schema_version")))
        return None, issues
    bucket_key = "profiles" if target_kind == "profile" else "programs"
    bucket = review_input.get(bucket_key)
    if not isinstance(bucket, dict):
        issues.append(_issue("requirement", "review_context_required", target_kind=target_kind, target_id=target_id))
        return None, issues
    context = bucket.get(target_id)
    if not isinstance(context, dict):
        issues.append(_issue("requirement", "review_context_required", target_kind=target_kind, target_id=target_id))
        return None, issues
    return context, issues


def _validate_context(
    context: dict[str, Any],
    *,
    target_kind: str,
    target_id: str,
    target_version: int,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    valid_events: list[dict[str, Any]] = []
    version_key = "profile_version" if target_kind == "profile" else "program_version"
    context_version = context.get(version_key)
    if context_version != target_version:
        issues.append(
            _issue(
                "requirement",
                "stale_review_context",
                target_kind=target_kind,
                target_id=target_id,
                expected_version=target_version,
                actual_version=context_version,
            )
        )
    if context.get("coverage") != "complete":
        issues.append(
            _issue(
                "requirement",
                "review_context_coverage_incomplete",
                target_kind=target_kind,
                target_id=target_id,
                coverage=context.get("coverage"),
            )
        )
    if not isinstance(context.get("source_ref"), str) or not context["source_ref"]:
        issues.append(_issue("error", "review_context_source_ref_required", target_kind=target_kind, target_id=target_id))

    events = context.get("events")
    if not isinstance(events, list):
        issues.append(_issue("error", "review_events_array_required", target_kind=target_kind, target_id=target_id))
        return valid_events, issues

    seen: set[str] = set()
    selection_ids = set(config["selection_trigger_ids"])
    validator_ids = set(config["optimization_validator_ids"])
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            issues.append(_issue("error", "review_event_invalid", index=index, reason="not_object"))
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            issues.append(_issue("error", "review_event_id_required", index=index))
            continue
        if event_id in seen:
            issues.append(_issue("error", "duplicate_review_event_id", event_id=event_id))
            continue
        seen.add(event_id)
        if not isinstance(event.get("source_ref"), str) or not event["source_ref"]:
            issues.append(_issue("error", "review_event_source_ref_required", event_id=event_id))
            continue
        task_ids = event.get("task_ids", [])
        action_ids = event.get("action_ids", [])
        if not isinstance(task_ids, list) or not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in task_ids):
            issues.append(_issue("error", "review_event_task_ids_invalid", event_id=event_id))
            continue
        if not isinstance(action_ids, list) or not all(isinstance(value, str) and value for value in action_ids):
            issues.append(_issue("error", "review_event_action_ids_invalid", event_id=event_id))
            continue

        kind = event.get("kind")
        if kind == "selection_trigger":
            trigger_id = event.get("trigger_id")
            if trigger_id not in selection_ids:
                issues.append(_issue("error", "selection_trigger_id_invalid", event_id=event_id, trigger_id=trigger_id))
                continue
        elif kind == "optimization_validator":
            validator_id = event.get("validator_id")
            result = event.get("result")
            if validator_id not in validator_ids:
                issues.append(_issue("error", "optimization_validator_id_invalid", event_id=event_id, validator_id=validator_id))
                continue
            if result not in {"PASS", "FAIL", "UNKNOWN"}:
                issues.append(_issue("error", "optimization_validator_result_invalid", event_id=event_id, result=result))
                continue
        else:
            issues.append(_issue("error", "review_event_kind_invalid", event_id=event_id, event_kind=kind))
            continue
        valid_events.append(event)
    return valid_events, issues


def evaluate_review_trigger(
    *,
    target_kind: str,
    target_id: str,
    target_version: int,
    upstream_statuses: dict[str, str],
    review_input: dict[str, Any] | None,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = model_config or load_review_trigger_config()
    validate_review_trigger_config(config)
    if target_kind not in {"profile", "program"}:
        raise ReviewTriggerError("target_kind must be profile or program")
    if not target_id:
        raise ReviewTriggerError("target_id is required")
    if not isinstance(target_version, int) or isinstance(target_version, bool) or target_version < 1:
        raise ReviewTriggerError("target_version must be a positive integer")

    issues: list[dict[str, Any]] = []
    for stage_name, status in upstream_statuses.items():
        if status not in {"pass", "requirements", "blocked"}:
            issues.append(_issue("error", "upstream_review_status_invalid", stage_name=stage_name, status=status))
        elif status == "blocked":
            issues.append(_issue("error", "upstream_stage_blocked_for_review", stage_name=stage_name))
        elif status == "requirements":
            issues.append(_issue("requirement", "upstream_stage_requirements_for_review", stage_name=stage_name))

    context, context_issues = _selected_context(
        review_input,
        target_kind=target_kind,
        target_id=target_id,
    )
    issues.extend(context_issues)
    events: list[dict[str, Any]] = []
    if context is not None:
        events, validation_issues = _validate_context(
            context,
            target_kind=target_kind,
            target_id=target_id,
            target_version=target_version,
            config=config,
        )
        issues.extend(validation_issues)
        context_not_applicable = {
            "stale_review_context",
            "review_context_source_ref_required",
            "review_events_array_required",
        }
        if any(issue.get("kind") in context_not_applicable for issue in validation_issues):
            events = []

    diagnoses: list[str] = []
    selection_events = [event for event in events if event.get("kind") == "selection_trigger"]
    optimization_failures = [
        event
        for event in events
        if event.get("kind") == "optimization_validator" and event.get("result") == "FAIL"
    ]
    optimization_unknowns = [
        event
        for event in events
        if event.get("kind") == "optimization_validator" and event.get("result") == "UNKNOWN"
    ]
    if selection_events:
        diagnoses.append("selection_review")
    if optimization_failures:
        diagnoses.append("optimization_review")
    if issues or optimization_unknowns:
        diagnoses.append("blocked_unknown")
        for event in optimization_unknowns:
            issues.append(
                _issue(
                    "requirement",
                    "optimization_validator_unknown",
                    event_id=event["event_id"],
                    validator_id=event["validator_id"],
                )
            )
    if not diagnoses:
        diagnoses.append("no_review")

    diagnosis_order = {value: index for index, value in enumerate(config["diagnoses"])}
    diagnoses = sorted(set(diagnoses), key=lambda value: diagnosis_order[value])
    if "blocked_unknown" in diagnoses and any(issue["severity"] == "error" for issue in issues):
        status = "blocked"
    elif "blocked_unknown" in diagnoses or "selection_review" in diagnoses or "optimization_review" in diagnoses:
        status = "requirements"
    else:
        status = "pass"

    selected_context = context if isinstance(context, dict) else None
    return {
        "kind": target_kind,
        "target_id": target_id,
        "target_version": target_version,
        "status": status,
        "diagnoses": diagnoses,
        "model_id": config["model_id"],
        "input_fingerprint": canonical_json_hash(
            {
                "target_kind": target_kind,
                "target_id": target_id,
                "target_version": target_version,
                "upstream_statuses": upstream_statuses,
                "review_context": selected_context,
                "model": config,
            }
        ),
        "context_source_ref": selected_context.get("source_ref") if selected_context else None,
        "selection_events": selection_events,
        "optimization_failures": optimization_failures,
        "optimization_unknowns": optimization_unknowns,
        "issues": issues,
    }
