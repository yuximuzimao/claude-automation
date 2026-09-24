from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash, file_sha256


PREREQUISITE_STAGE_ORDER = [
    "dependency_fingerprint",
    "profile_program_contract",
    "availability_route_replay",
    "cross_profile_continuity",
    "canonical_spatial_movement",
    "service_context",
    "derived_timing",
    "derived_xp",
    "derived_economy",
    "review_trigger",
    "display_presentation",
    "publisher_payload",
    "html_player_view_assets",
]

ACTIVE_LIFECYCLE_CONSUMERS = [
    "scripts/rebuild_route_profile.py",
    "lib/route_display.py",
    "lib/route_publisher_payload.py",
    "lib/route_player_assets.py",
]

TODO_PATH = ROOT / "tasks" / "todo.md"
CUTOVER_BLOCKER_RE = re.compile(r"^- \[ \].*\[CUTOVER-BLOCKER:([^\]]+)\]", re.MULTILINE)


def load_cutover_blockers(path: Path | None = None) -> list[str]:
    """Return unresolved project cutover blockers from the single Todo ledger."""
    todo_path = path or TODO_PATH
    if not todo_path.exists():
        raise FinalAuditError(f"todo missing: {todo_path}")
    try:
        text = todo_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinalAuditError(f"todo unreadable: {todo_path}") from exc
    blockers = CUTOVER_BLOCKER_RE.findall(text)
    if len(blockers) != len(set(blockers)):
        raise FinalAuditError("cutover blocker ids in Todo must be unique")
    return blockers


FORBIDDEN_ACTIVE_CONSUMER_TOKENS = (
    "workbench-routes.json",
    "from lib.route_publisher import",
    "from .route_publisher import",
    "build_route_payload(",
    "actionHtml",
    "noteHtml",
)

INTERNAL_ACTION_TOKEN_RE = re.compile(r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}")
FORBIDDEN_PLAYER_MARKERS = (
    "workbench-routes.json",
    "actionHtml",
    "noteHtml",
    "<div",
)
ADVISORY_PLAYER_MARKERS = (
    "【需要单独修正优化】",
)
PROCESS_LANGUAGE = (
    "已验证",
    "经审计",
    "已实测",
    "Questie缺陷",
    "测试结果",
    "为什么这样排序",
    "继续下一段",
    "按顺序做",
)


class FinalAuditError(ValueError):
    """Raised when Stage 14 cannot evaluate the final lifecycle contract."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(row.get("severity") == "error" for row in issues):
        return "blocked"
    if any(row.get("severity") in {"requirement", "unknown"} for row in issues):
        return "requirements"
    return "pass"


def _cold_read_step_counts(text: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    heading: str | None = None
    count = 0
    in_notes = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## 步骤 "):
            if heading is not None:
                rows.append((heading, count))
            heading = line
            count = 0
            in_notes = False
            continue
        if heading is None:
            continue
        if line == "备注：":
            in_notes = True
            continue
        if line.startswith("## "):
            rows.append((heading, count))
            heading = None
            count = 0
            in_notes = False
            continue
        if line.startswith("- ") and not in_notes:
            count += 1
    if heading is not None:
        rows.append((heading, count))
    return rows


def evaluate_profile_final_audit(
    *,
    profile_id: str,
    profile_version: int,
    root_fingerprint: str,
    prerequisite_stages: list[dict[str, Any]],
    display_reports: list[dict[str, Any]],
    publisher_payloads: list[dict[str, Any]],
    player_assets_report: dict[str, Any],
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Evaluate Stage 14 without re-running or re-interpreting Stages 1-13 business logic."""
    source_root = source_root or ROOT
    if not isinstance(profile_id, str) or not profile_id:
        raise FinalAuditError("profile_id missing")
    if not isinstance(profile_version, int) or profile_version < 1:
        raise FinalAuditError("profile_version invalid")
    if not isinstance(root_fingerprint, str) or not root_fingerprint:
        raise FinalAuditError("root_fingerprint missing")

    issues: list[dict[str, Any]] = []
    actual_order = [str(row.get("name") or "") for row in prerequisite_stages]
    if actual_order != PREREQUISITE_STAGE_ORDER:
        issues.append(
            _issue(
                "error",
                "final_audit_stage_order_mismatch",
                expected=PREREQUISITE_STAGE_ORDER,
                actual=actual_order,
            )
        )

    for row in prerequisite_stages:
        name = str(row.get("name") or "")
        implementation = row.get("implementation_status")
        evaluation = row.get("evaluation_status")
        if implementation != "implemented":
            issues.append(_issue("error", "final_audit_stage_not_implemented", stage_name=name, status=implementation))
        if evaluation == "blocked":
            issues.append(_issue("error", "final_audit_upstream_blocked", stage_name=name))
        elif evaluation == "requirements":
            issues.append(_issue("requirement", "final_audit_upstream_requirements", stage_name=name))
        elif evaluation != "pass":
            issues.append(_issue("error", "final_audit_upstream_status_invalid", stage_name=name, status=evaluation))

    if prerequisite_stages:
        stage1_root = (prerequisite_stages[0].get("detail") or {}).get("root_fingerprint")
        if stage1_root != root_fingerprint:
            issues.append(
                _issue(
                    "error",
                    "final_audit_root_fingerprint_mismatch",
                    expected=root_fingerprint,
                    actual=stage1_root,
                )
            )

    display_fingerprints = {
        (row.get("program_id"), row.get("input_fingerprint"))
        for row in display_reports
        if isinstance(row, dict)
    }
    for payload in publisher_payloads:
        if payload.get("profile_id") != profile_id or payload.get("profile_version") != profile_version:
            issues.append(
                _issue(
                    "error",
                    "final_audit_publisher_profile_mismatch",
                    publisher_profile_id=payload.get("profile_id"),
                    publisher_profile_version=payload.get("profile_version"),
                )
            )
        link = (payload.get("program_id"), payload.get("stage11_input_fingerprint"))
        if link not in display_fingerprints:
            issues.append(
                _issue(
                    "error",
                    "final_audit_stage11_stage12_fingerprint_mismatch",
                    program_id=payload.get("program_id"),
                    stage11_input_fingerprint=payload.get("stage11_input_fingerprint"),
                )
            )

    publisher_fingerprints = [payload.get("input_fingerprint") for payload in publisher_payloads]
    if player_assets_report.get("publisher_fingerprints") != publisher_fingerprints:
        issues.append(
            _issue(
                "error",
                "final_audit_stage12_stage13_fingerprint_mismatch",
                expected=publisher_fingerprints,
                actual=player_assets_report.get("publisher_fingerprints"),
            )
        )

    active_consumer_hashes: dict[str, str] = {}
    for relative in ACTIVE_LIFECYCLE_CONSUMERS:
        path = source_root / relative
        if not path.exists():
            issues.append(_issue("error", "final_audit_active_consumer_missing", path=relative))
            continue
        text = path.read_text(encoding="utf-8")
        active_consumer_hashes[relative] = file_sha256(path)
        for token in FORBIDDEN_ACTIVE_CONSUMER_TOKENS:
            if token in text:
                issues.append(
                    _issue(
                        "error",
                        "final_audit_active_legacy_consumer",
                        path=relative,
                        token=token,
                    )
                )

    scripts_dir = source_root / "scripts"
    legacy_workbench_consumers: list[str] = []
    if scripts_dir.exists():
        for path in sorted(scripts_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "workbench-routes.json" in text:
                legacy_workbench_consumers.append(str(path.relative_to(source_root)))
    if legacy_workbench_consumers:
        issues.append(
            _issue(
                "error",
                "final_audit_legacy_workbench_consumers_active",
                paths=legacy_workbench_consumers,
            )
        )

    registry_path = source_root / "scripts/README.md"
    if not registry_path.exists():
        issues.append(_issue("error", "final_audit_scripts_registry_missing"))
        registry_hash = None
    else:
        registry_hash = file_sha256(registry_path)

    player_views = player_assets_report.get("player_views")
    if not isinstance(player_views, dict) or not player_views:
        issues.append(_issue("error", "final_audit_player_view_missing"))
        player_views = {}
    cold_read: dict[str, Any] = {}
    for publish_key, text_value in player_views.items():
        text = str(text_value)
        view_issues: list[dict[str, Any]] = []
        if INTERNAL_ACTION_TOKEN_RE.search(text):
            view_issues.append(_issue("error", "cold_read_internal_action_token", publish_key=publish_key))
        for marker in FORBIDDEN_PLAYER_MARKERS:
            if marker in text:
                view_issues.append(
                    _issue(
                        "error",
                        "cold_read_forbidden_marker",
                        publish_key=publish_key,
                        marker=marker,
                    )
                )
        for marker in ADVISORY_PLAYER_MARKERS:
            if marker in text:
                view_issues.append(
                    _issue(
                        "requirement",
                        "cold_read_cleanup_marker",
                        publish_key=publish_key,
                        marker=marker,
                    )
                )
        for phrase in PROCESS_LANGUAGE:
            if phrase in text:
                view_issues.append(
                    _issue(
                        "requirement",
                        "cold_read_process_language",
                        publish_key=publish_key,
                        phrase=phrase,
                    )
                )
        step_counts = _cold_read_step_counts(text)
        for heading, action_line_count in step_counts:
            if action_line_count > 10:
                view_issues.append(
                    _issue(
                        "requirement",
                        "cold_read_step_overlong_review",
                        publish_key=publish_key,
                        step_heading=heading,
                        action_line_count=action_line_count,
                    )
                )
        issues.extend(view_issues)
        cold_read[str(publish_key)] = {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "character_count": len(text),
            "step_action_line_counts": [
                {"step_heading": heading, "action_line_count": count}
                for heading, count in step_counts
            ],
            "issues": view_issues,
        }

    status = _status(issues)
    cutover_status = "blocked" if any(row.get("severity") == "error" for row in issues) else "pass"
    input_fingerprint = canonical_json_hash(
        {
            "profile_id": profile_id,
            "profile_version": profile_version,
            "root_fingerprint": root_fingerprint,
            "stage_statuses": [
                {
                    "name": row.get("name"),
                    "implementation_status": row.get("implementation_status"),
                    "evaluation_status": row.get("evaluation_status"),
                }
                for row in prerequisite_stages
            ],
            "display_fingerprints": sorted(
                [f"{program_id or ''}:{fingerprint or ''}" for program_id, fingerprint in display_fingerprints]
            ),
            "publisher_fingerprints": publisher_fingerprints,
            "player_assets_fingerprint": player_assets_report.get("input_fingerprint"),
            "active_consumer_hashes": active_consumer_hashes,
            "registry_hash": registry_hash,
            "cold_read_hashes": {key: row["sha256"] for key, row in cold_read.items()},
        }
    )
    return {
        "kind": "profile_final_audit",
        "profile_id": profile_id,
        "profile_version": profile_version,
        "status": status,
        "publishable": status == "pass" and player_assets_report.get("publishable") is True,
        "cutover_status": cutover_status,
        "cutover_publishable": cutover_status == "pass" and player_assets_report.get("publishable") is True,
        "input_fingerprint": input_fingerprint,
        "mechanical_summary": {
            "prerequisite_stage_count": len(prerequisite_stages),
            "implemented_stage_count": sum(1 for row in prerequisite_stages if row.get("implementation_status") == "implemented"),
            "blocked_stage_count": sum(1 for row in prerequisite_stages if row.get("evaluation_status") == "blocked"),
            "requirements_stage_count": sum(1 for row in prerequisite_stages if row.get("evaluation_status") == "requirements"),
            "active_consumer_count": len(active_consumer_hashes),
        },
        "cold_read": cold_read,
        "issues": issues,
    }


def evaluate_project_final_audit(
    profile_reports: list[dict[str, Any]],
    *,
    required_profile_ids: list[str],
    cutover_blocker_ids: list[str],
) -> dict[str, Any]:
    """Project-level cutover gate. Call only after per-profile Stage 14 reports exist."""
    if not required_profile_ids:
        raise FinalAuditError("required_profile_ids must be explicit and non-empty")
    if not isinstance(cutover_blocker_ids, list):
        raise FinalAuditError("cutover_blocker_ids must be an explicit list")
    normalized_blockers = [str(value).strip() for value in cutover_blocker_ids]
    if any(not value for value in normalized_blockers):
        raise FinalAuditError("cutover blocker ids must be non-empty")
    if len(normalized_blockers) != len(set(normalized_blockers)):
        raise FinalAuditError("cutover blocker ids must be unique")

    required = list(dict.fromkeys(required_profile_ids))
    issues: list[dict[str, Any]] = []
    if normalized_blockers:
        issues.append(
            _issue(
                "requirement",
                "project_final_audit_todo_blockers_open",
                blocker_ids=normalized_blockers,
            )
        )
    by_id: dict[str, dict[str, Any]] = {}
    for report in profile_reports:
        if report.get("kind") != "profile_final_audit":
            raise FinalAuditError("project audit requires profile_final_audit reports")
        profile_id = str(report.get("profile_id") or "")
        if not profile_id:
            raise FinalAuditError("profile final audit missing profile_id")
        if profile_id in by_id:
            issues.append(_issue("error", "project_final_audit_duplicate_profile", profile_id=profile_id))
        by_id[profile_id] = report

    missing = [profile_id for profile_id in required if profile_id not in by_id]
    extra = [profile_id for profile_id in by_id if profile_id not in required]
    if missing:
        issues.append(_issue("requirement", "project_final_audit_profiles_missing", profile_ids=missing))
    if extra:
        issues.append(_issue("error", "project_final_audit_unexpected_profiles", profile_ids=extra))
    for profile_id in required:
        report = by_id.get(profile_id)
        if report is None:
            continue
        if report.get("status") == "blocked":
            issues.append(_issue("error", "project_final_audit_profile_blocked", profile_id=profile_id))
        elif report.get("status") == "requirements":
            issues.append(_issue("requirement", "project_final_audit_profile_requirements", profile_id=profile_id))
        elif report.get("status") != "pass" or report.get("publishable") is not True:
            issues.append(_issue("error", "project_final_audit_profile_not_publishable", profile_id=profile_id))

    status = _status(issues)
    cutover_issues: list[dict[str, Any]] = []
    if normalized_blockers:
        cutover_issues.append(
            _issue(
                "requirement",
                "project_final_audit_todo_blockers_open",
                blocker_ids=normalized_blockers,
            )
        )
    if missing:
        cutover_issues.append(_issue("requirement", "project_final_audit_profiles_missing", profile_ids=missing))
    if extra:
        cutover_issues.append(_issue("error", "project_final_audit_unexpected_profiles", profile_ids=extra))
    for profile_id in required:
        report = by_id.get(profile_id)
        if report is None:
            continue
        if report.get("cutover_status") == "blocked" or report.get("cutover_publishable") is not True:
            cutover_issues.append(_issue("error", "project_final_audit_profile_cutover_blocked", profile_id=profile_id))
    cutover_status = _status(cutover_issues)
    return {
        "kind": "project_final_audit",
        "status": status,
        "cutover_status": cutover_status,
        "cutover_ready": cutover_status == "pass" and len(by_id) == len(required),
        "input_fingerprint": canonical_json_hash(
            {
                "required_profile_ids": required,
                "profile_audit_fingerprints": {
                    profile_id: by_id[profile_id].get("input_fingerprint")
                    for profile_id in required
                    if profile_id in by_id
                },
                "cutover_blocker_ids": normalized_blockers,
            }
        ),
        "required_profile_ids": required,
        "received_profile_ids": sorted(by_id),
        "open_cutover_blocker_ids": normalized_blockers,
        "issues": issues,
        "cutover_issues": cutover_issues,
    }
