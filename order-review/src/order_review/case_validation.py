from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

from .order_identity import same_order_signature_key
from .package_plan import (
    PackageDraft,
    PackagePlan,
    SCHEMA_VERSION,
    SourceSnapshot,
)


class AuditSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class AuditIssue:
    severity: AuditSeverity
    code: str
    message: str
    location: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }


@dataclass(frozen=True)
class CaseAuditReport:
    path: str
    issues: tuple[AuditIssue, ...]
    case_count: int = 0
    assignment_count: int = 0
    rule_count: int = 0

    @property
    def errors(self) -> tuple[AuditIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity is AuditSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[AuditIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity is AuditSeverity.WARNING
        )

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "valid": self.valid,
            "caseCount": self.case_count,
            "assignmentCount": self.assignment_count,
            "ruleCount": self.rule_count,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def audit_case_file(path: str | Path) -> CaseAuditReport:
    file_path = Path(path)
    if not file_path.exists():
        return CaseAuditReport(
            path=str(file_path),
            issues=(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "file_missing",
                    "案例文件不存在",
                    str(file_path),
                ),
            ),
        )
    try:
        value = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CaseAuditReport(
            path=str(file_path),
            issues=(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "json_invalid",
                    f"案例文件无法读取：{exc}",
                    str(file_path),
                ),
            ),
        )
    return validate_case_payload(value, path=str(file_path))


def audit_case_file_isolated(path: str | Path) -> CaseAuditReport:
    """在短生命周期子进程中校验大案例文件，避免主进程保留解析高水位。"""
    file_path = Path(path)
    environment = dict(os.environ)
    source_root = str(Path(__file__).resolve().parents[1])
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else source_root
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "order_review.case_audit",
                "--path",
                str(file_path),
                "--json",
            ],
            check=False,
            capture_output=True,
            env=environment,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _single_error(
            str(file_path),
            "audit_process_failed",
            f"案例隔离校验无法完成：{exc}",
        )
    try:
        payload = json.loads(completed.stdout)
        raw_issues = [
            *payload.get("errors", []),
            *payload.get("warnings", []),
        ]
        issues = tuple(
            AuditIssue(
                severity=AuditSeverity(str(item["severity"])),
                code=str(item["code"]),
                message=str(item["message"]),
                location=str(item.get("location", "")),
            )
            for item in raw_issues
        )
        return CaseAuditReport(
            path=str(payload.get("path", file_path)),
            issues=issues,
            case_count=int(payload.get("caseCount", 0)),
            assignment_count=int(payload.get("assignmentCount", 0)),
            rule_count=int(payload.get("ruleCount", 0)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        details = completed.stderr.strip() or completed.stdout.strip()
        suffix = f"；输出：{details[:300]}" if details else ""
        return _single_error(
            str(file_path),
            "audit_process_invalid",
            f"案例隔离校验返回无效结果：{exc}{suffix}",
        )


def validate_case_payload(
    value: Any,
    *,
    path: str = "<memory>",
) -> CaseAuditReport:
    issues: list[AuditIssue] = []
    if not isinstance(value, Mapping):
        return _single_error(path, "root_invalid", "案例文件根节点必须是对象")
    if value.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "schema_unsupported",
                f"不支持的 schemaVersion：{value.get('schemaVersion')!r}",
                "schemaVersion",
            )
        )

    raw_cases = value.get("cases")
    raw_assignments = value.get("orderAssignments", [])
    raw_stats = value.get("ruleStats", {})
    if not isinstance(raw_cases, list):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "cases_invalid",
                "cases 必须是数组",
                "cases",
            )
        )
        raw_cases = []
    if not isinstance(raw_assignments, list):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "assignments_invalid",
                "orderAssignments 必须是数组",
                "orderAssignments",
            )
        )
        raw_assignments = []
    if not isinstance(raw_stats, Mapping):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "rule_stats_invalid",
                "ruleStats 必须是对象",
                "ruleStats",
            )
        )
        raw_stats = {}

    parsed_cases: dict[str, tuple[SourceSnapshot, Mapping[str, Any]]] = {}
    missing_identity_products = 0
    missing_order_cases = 0
    case_ids: list[str] = []
    for index, raw_case in enumerate(raw_cases):
        location = f"cases[{index}]"
        if not isinstance(raw_case, Mapping):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_invalid",
                    "案例必须是对象",
                    location,
                )
            )
            continue
        case_id = str(raw_case.get("caseId", "")).strip()
        if not case_id:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_id_missing",
                    "案例缺少 caseId",
                    location,
                )
            )
            continue
        case_ids.append(case_id)
        try:
            source = SourceSnapshot.from_dict(raw_case["sourceSnapshot"])
            plan = PackagePlan.from_dict(raw_case["packagePlan"])
            PackageDraft(
                snapshot_id=source.snapshot_id,
                packages=plan.packages,
            ).confirm(source)
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_content_invalid",
                    f"案例快照或包裹方案无效：{exc}",
                    location,
                )
            )
            continue
        parsed_cases[case_id] = (source, raw_case)
        if same_order_signature_key(source) is None:
            missing_order_cases += 1
        for product in source.products:
            if not any(
                (
                    product.merchant_code.strip(),
                    (product.main_merchant_code or "").strip(),
                    product.platform_product_id.strip(),
                    product.platform_sku_id.strip(),
                )
            ):
                missing_identity_products += 1
        order_version = raw_case.get("orderVersion", 1)
        if not isinstance(order_version, int) or order_version < 1:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "order_version_invalid",
                    "orderVersion 必须是大于 0 的整数",
                    f"{location}.orderVersion",
                )
            )
        _validate_shipping_decision(
            issues,
            raw_case.get("decision", {}),
            location=f"{location}.decision",
        )

    _duplicate_issues(
        issues,
        case_ids,
        code="case_id_duplicate",
        label="caseId",
        location="cases",
    )

    assignment_ids: list[str] = []
    parsed_assignments: dict[str, Mapping[str, Any]] = {}
    assignments_by_signature: dict[str, list[Mapping[str, Any]]] = {}
    referenced_rule_ids: set[str] = set()
    for index, raw_assignment in enumerate(raw_assignments):
        location = f"orderAssignments[{index}]"
        if not isinstance(raw_assignment, Mapping):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_invalid",
                    "订单索引必须是对象",
                    location,
                )
            )
            continue
        assignment_id = str(raw_assignment.get("assignmentId", "")).strip()
        signature = str(raw_assignment.get("sameOrderSignature", "")).strip()
        case_id = str(raw_assignment.get("caseId", "")).strip()
        version = raw_assignment.get("version", 1)
        if not assignment_id:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_id_missing",
                    "订单索引缺少 assignmentId",
                    location,
                )
            )
        else:
            assignment_ids.append(assignment_id)
            parsed_assignments[assignment_id] = raw_assignment
        if not signature:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_signature_missing",
                    "订单索引缺少同订单签名",
                    location,
                )
            )
        else:
            assignments_by_signature.setdefault(signature, []).append(raw_assignment)
        if case_id not in parsed_cases:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_case_missing",
                    f"订单索引引用了不存在的案例：{case_id}",
                    f"{location}.caseId",
                )
            )
        if not isinstance(version, int) or version < 1:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_version_invalid",
                    "订单索引 version 必须是大于 0 的整数",
                    f"{location}.version",
                )
            )
        rule_id = raw_assignment.get("ruleId")
        if isinstance(rule_id, str) and rule_id:
            referenced_rule_ids.add(rule_id)
        decision = raw_assignment.get("decision")
        if decision is not None:
            _validate_shipping_decision(
                issues,
                decision,
                location=f"{location}.decision",
            )

    _duplicate_issues(
        issues,
        assignment_ids,
        code="assignment_id_duplicate",
        label="assignmentId",
        location="orderAssignments",
    )

    for assignment_id, assignment in parsed_assignments.items():
        previous_id = assignment.get("previousAssignmentId")
        version = assignment.get("version", 1)
        if previous_id is None:
            if isinstance(version, int) and version > 1:
                issues.append(
                    AuditIssue(
                        AuditSeverity.ERROR,
                        "assignment_previous_missing",
                        "高版本订单索引缺少 previousAssignmentId",
                        assignment_id,
                    )
                )
            continue
        previous = parsed_assignments.get(str(previous_id))
        if previous is None:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_previous_invalid",
                    f"previousAssignmentId 不存在：{previous_id}",
                    assignment_id,
                )
            )
            continue
        if previous.get("sameOrderSignature") != assignment.get("sameOrderSignature"):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_previous_cross_order",
                    "订单索引版本链跨越了不同订单签名",
                    assignment_id,
                )
            )
        if (
            isinstance(version, int)
            and isinstance(previous.get("version", 1), int)
            and version != int(previous.get("version", 1)) + 1
        ):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_version_gap",
                    "订单索引版本号与上一版本不连续",
                    assignment_id,
                )
            )

    _cycle_issues(
        issues,
        parsed_assignments,
        link_field="previousAssignmentId",
        code="assignment_cycle",
        label="订单索引",
    )

    for signature, assignments in assignments_by_signature.items():
        versions = [item.get("version", 1) for item in assignments]
        integer_versions = [item for item in versions if isinstance(item, int)]
        if len(integer_versions) != len(set(integer_versions)):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "assignment_latest_ambiguous",
                    "同一订单存在重复索引版本，无法唯一确定最新方案",
                    signature,
                )
            )

    assignments_for_relation = [
        assignment
        for assignment in raw_assignments
        if isinstance(assignment, Mapping)
    ]
    cases_by_signature: dict[str, list[Mapping[str, Any]]] = {}
    parsed_case_links: dict[str, Mapping[str, Any]] = {}
    for case_id, (source, raw_case) in parsed_cases.items():
        parsed_case_links[case_id] = raw_case
        signature = same_order_signature_key(source)
        if signature is not None:
            cases_by_signature.setdefault(signature, []).append(raw_case)
        decision = raw_case.get("decision")
        if isinstance(decision, Mapping):
            recommendation_id = decision.get("recommendationId")
            if isinstance(recommendation_id, str) and recommendation_id:
                referenced_rule_ids.add(recommendation_id)

        previous_id = raw_case.get("previousCaseId")
        if previous_id is None:
            current_version = raw_case.get("orderVersion", 1)
            if isinstance(current_version, int) and current_version > 1:
                issues.append(
                    AuditIssue(
                        AuditSeverity.ERROR,
                        "case_previous_missing",
                        "高版本案例缺少 previousCaseId",
                        case_id,
                    )
                )
            continue
        previous = parsed_cases.get(str(previous_id))
        if previous is None:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_previous_invalid",
                    f"previousCaseId 不存在：{previous_id}",
                    case_id,
                )
            )
            continue
        previous_source, previous_raw = previous
        previous_matches = (
            signature is not None
            and same_order_signature_key(previous_source) == signature
        ) or (
            signature is None
            and previous_source.snapshot_id == source.snapshot_id
        )
        assignment_links = signature is not None and any(
            item.get("sameOrderSignature") == signature
            and item.get("caseId") == previous_id
            for item in assignments_for_relation
        )
        if not previous_matches and not assignment_links:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_previous_cross_order",
                    "案例版本链跨越了无关联订单",
                    case_id,
                )
            )
        current_version = raw_case.get("orderVersion", 1)
        previous_version = previous_raw.get("orderVersion", 1)
        if (
            isinstance(current_version, int)
            and isinstance(previous_version, int)
            and current_version != previous_version + 1
        ):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_version_gap",
                    "案例 orderVersion 与上一版本不连续",
                    case_id,
                )
            )

    _cycle_issues(
        issues,
        parsed_case_links,
        link_field="previousCaseId",
        code="case_cycle",
        label="案例",
    )

    for signature, cases in cases_by_signature.items():
        versions = [item.get("orderVersion", 1) for item in cases]
        integer_versions = [item for item in versions if isinstance(item, int)]
        if len(integer_versions) != len(set(integer_versions)):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "case_latest_ambiguous",
                    "同一订单存在重复方案版本，无法唯一确定最新方案",
                    signature,
                )
            )

    for rule_id, raw_stat in raw_stats.items():
        location = f"ruleStats.{rule_id}"
        if not isinstance(raw_stat, Mapping):
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "rule_stat_invalid",
                    "规则统计必须是对象",
                    location,
                )
            )
            continue
        embedded_rule_id = raw_stat.get("ruleId", rule_id)
        if embedded_rule_id != rule_id:
            issues.append(
                AuditIssue(
                    AuditSeverity.ERROR,
                    "rule_id_mismatch",
                    "规则统计键与 ruleId 不一致",
                    location,
                )
            )
        for field_name in ("directUseCount", "modifiedCount"):
            count = raw_stat.get(field_name, 0)
            if not isinstance(count, int) or count < 0:
                issues.append(
                    AuditIssue(
                        AuditSeverity.ERROR,
                        "rule_count_invalid",
                        f"{field_name} 必须是非负整数",
                        f"{location}.{field_name}",
                    )
                )
        if str(rule_id) not in referenced_rule_ids:
            issues.append(
                AuditIssue(
                    AuditSeverity.WARNING,
                    "rule_stat_orphan",
                    "规则统计暂未被案例或订单索引引用",
                    location,
                )
            )

    if missing_identity_products:
        issues.append(
            AuditIssue(
                AuditSeverity.WARNING,
                "product_identity_missing",
                f"{missing_identity_products} 条商品缺少商家编码和平台商品/SKU ID",
                "cases",
            )
        )
    if missing_order_cases:
        issues.append(
            AuditIssue(
                AuditSeverity.WARNING,
                "platform_order_missing",
                f"{missing_order_cases} 个案例缺少可靠平台单号，无法进行同订单识别",
                "cases",
            )
        )

    return CaseAuditReport(
        path=path,
        issues=tuple(issues),
        case_count=len(raw_cases),
        assignment_count=len(raw_assignments),
        rule_count=len(raw_stats),
    )


def _single_error(path: str, code: str, message: str) -> CaseAuditReport:
    return CaseAuditReport(
        path=path,
        issues=(AuditIssue(AuditSeverity.ERROR, code, message, path),),
    )


def _duplicate_issues(
    issues: list[AuditIssue],
    values: list[str],
    *,
    code: str,
    label: str,
    location: str,
) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    for value in duplicates:
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                code,
                f"{label} 重复：{value}",
                location,
            )
        )


def _validate_shipping_decision(
    issues: list[AuditIssue],
    value: Any,
    *,
    location: str,
) -> None:
    if not isinstance(value, Mapping):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "decision_invalid",
                "decision 必须是对象",
                location,
            )
        )
        return
    shipping_mode = value.get("shippingMode", "parcel")
    if shipping_mode not in {"parcel", "freight"}:
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "shipping_mode_invalid",
                "shippingMode 必须是 parcel 或 freight",
                f"{location}.shippingMode",
            )
        )
    estimated_band = value.get("estimatedPackageBand")
    if estimated_band is not None and (
        not isinstance(estimated_band, str) or not estimated_band.strip()
    ):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "estimated_package_band_invalid",
                "estimatedPackageBand 必须是非空字符串或 null",
                f"{location}.estimatedPackageBand",
            )
        )
    reasons = value.get("shippingReasons", [])
    if not isinstance(reasons, list) or any(
        not isinstance(item, str) or not item.strip() for item in reasons
    ):
        issues.append(
            AuditIssue(
                AuditSeverity.ERROR,
                "shipping_reasons_invalid",
                "shippingReasons 必须是非空字符串数组",
                f"{location}.shippingReasons",
            )
        )


def _cycle_issues(
    issues: list[AuditIssue],
    items: Mapping[str, Mapping[str, Any]],
    *,
    link_field: str,
    code: str,
    label: str,
) -> None:
    for start in items:
        seen: set[str] = set()
        current: str | None = start
        while current is not None and current in items:
            if current in seen:
                issues.append(
                    AuditIssue(
                        AuditSeverity.ERROR,
                        code,
                        f"{label}版本链存在循环",
                        start,
                    )
                )
                break
            seen.add(current)
            next_value = items[current].get(link_field)
            current = str(next_value) if next_value is not None else None
