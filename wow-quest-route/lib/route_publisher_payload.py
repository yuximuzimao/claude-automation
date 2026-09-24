from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash


ROUTE_UI_DIR = ROOT / "data/route-ui"


class PublisherPayloadError(ValueError):
    """Raised when Stage 12 cannot build a trustworthy publisher payload."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def load_route_ui_config(profile_id: str, path: Path | None = None) -> dict[str, Any]:
    source = path or (ROUTE_UI_DIR / f"{profile_id}.json")
    if not source.exists():
        return {
            "schema_version": 1,
            "profile_id": profile_id,
            "map_labels": [],
        }
    payload = json.loads(source.read_text(encoding="utf-8"))
    validate_route_ui_config(payload, expected_profile_id=profile_id)
    return payload


def validate_route_ui_config(payload: dict[str, Any], *, expected_profile_id: str | None = None) -> None:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    profile_id = payload.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        errors.append("profile_id missing")
    elif expected_profile_id is not None and profile_id != expected_profile_id:
        errors.append(f"profile_id mismatch: {profile_id!r} != {expected_profile_id!r}")
    labels = payload.get("map_labels")
    if not isinstance(labels, list):
        errors.append("map_labels must be an array")
        labels = []
    for index, row in enumerate(labels):
        prefix = f"map_labels[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        x = row.get("x")
        y = row.get("y")
        name = row.get("display_name")
        if not isinstance(x, (int, float)) or isinstance(x, bool) or not 0 <= float(x) <= 100:
            errors.append(f"{prefix}.x must be numeric 0..100")
        if not isinstance(y, (int, float)) or isinstance(y, bool) or not 0 <= float(y) <= 100:
            errors.append(f"{prefix}.y must be numeric 0..100")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}.display_name missing")
    if errors:
        raise PublisherPayloadError("Route UI config invalid: " + "; ".join(errors))


def build_publisher_payload(
    display_report: dict[str, Any],
    *,
    route_ui: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the sole Stage 12 JSON publisher payload from Stage 11 semantic output.

    Stage 12 never reads Route Profile, Task Card, old Timing models, workbench JSON, semantic prose,
    or HTML. Non-pass Stage 11 input may be wrapped for diagnostics, but it can never become a
    publishable payload.
    """

    if display_report.get("kind") != "route_display":
        raise PublisherPayloadError("Stage 12 requires a Stage 11 route_display report")
    profile_id = display_report.get("profile_id")
    version = display_report.get("profile_version")
    if not isinstance(profile_id, str) or not profile_id:
        raise PublisherPayloadError("display_report.profile_id missing")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise PublisherPayloadError("display_report.profile_version invalid")
    display_fingerprint = display_report.get("input_fingerprint")
    if not isinstance(display_fingerprint, str) or not display_fingerprint:
        raise PublisherPayloadError("display_report.input_fingerprint missing")
    program_id = display_report.get("program_id")
    if program_id is not None and (not isinstance(program_id, str) or not program_id):
        raise PublisherPayloadError("display_report.program_id must be a non-empty string or null")
    display_status = display_report.get("status")
    if display_status not in {"pass", "requirements", "blocked"}:
        raise PublisherPayloadError(f"unsupported Stage 11 status: {display_status!r}")

    ui = route_ui if route_ui is not None else load_route_ui_config(profile_id)
    validate_route_ui_config(ui, expected_profile_id=profile_id)

    display = display_report.get("display")
    map_geometry = display_report.get("map_geometry")
    hearth_chain = display_report.get("hearth_chain")
    steps = display_report.get("steps")
    route_timing = display_report.get("route_timing")
    if not isinstance(display, dict):
        raise PublisherPayloadError("display_report.display must be an object")
    if not isinstance(map_geometry, dict):
        raise PublisherPayloadError("display_report.map_geometry must be an object")
    if not isinstance(map_geometry.get("visits"), list) or not isinstance(map_geometry.get("edges"), list):
        raise PublisherPayloadError("display_report.map_geometry visits/edges must be arrays")
    if not isinstance(hearth_chain, list) or not all(isinstance(value, str) and value for value in hearth_chain):
        raise PublisherPayloadError("display_report.hearth_chain must be an array of non-empty strings")
    if not isinstance(steps, list):
        raise PublisherPayloadError("display_report.steps must be an array")
    if not isinstance(route_timing, dict):
        raise PublisherPayloadError("display_report.route_timing must be an object")

    issues: list[dict[str, Any]] = []
    if display_status == "blocked":
        issues.append(_issue("error", "publisher_stage11_blocked"))
    elif display_status == "requirements":
        issues.append(_issue("requirement", "publisher_stage11_requirements"))

    map_image = display.get("map_image")
    if not isinstance(map_image, str) or not map_image:
        issues.append(_issue("error", "publisher_map_image_missing"))
    elif not map_image.startswith("maps/"):
        issues.append(_issue("error", "publisher_map_image_must_be_relative_maps_path", map_image=map_image))

    labels = [
        {
            "x": float(row["x"]),
            "y": float(row["y"]),
            "display_name": str(row["display_name"]),
        }
        for row in ui.get("map_labels") or []
    ]

    status = "blocked" if any(row["severity"] == "error" for row in issues) else (
        "requirements" if issues else "pass"
    )
    publishable = status == "pass"
    ui_projection = {
        "schema_version": int(ui["schema_version"]),
        "profile_id": profile_id,
        "map_labels": labels,
    }
    payload_fingerprint = canonical_json_hash(
        {
            "profile_id": profile_id,
            "profile_version": version,
            "program_id": program_id,
            "stage11_input_fingerprint": display_fingerprint,
            "route_ui": ui_projection,
        }
    )

    return {
        "schema_version": 1,
        "kind": "publisher_payload",
        "profile_id": profile_id,
        "profile_version": version,
        "program_id": program_id,
        "status": status,
        "publishable": publishable,
        "input_fingerprint": payload_fingerprint,
        "stage11_input_fingerprint": display_fingerprint,
        "display": {
            "publish_key": display.get("publish_key"),
            "order": display.get("order"),
            "title": display.get("title"),
            "display_name": display.get("display_name"),
            "subtitle": display.get("subtitle"),
            "footer": display.get("footer"),
        },
        "map": {
            "image": map_image,
            "labels": labels,
            "geometry": map_geometry,
        },
        "hearth_chain": list(hearth_chain),
        "route_timing": route_timing,
        "steps": steps,
        "issues": issues,
    }
