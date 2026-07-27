from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from uuid import uuid4

from .case_backup import (
    DEFAULT_BACKUP_KEEP,
    CaseBackupError,
    atomic_write_bytes,
    create_valid_backup,
    quarantine_file,
    validate_payload_or_raise,
)
from .case_validation import audit_case_file
from .file_lock import exclusive_file_lock
from .order_identity import same_order_signature_key
from .package_plan import PackageDraft, PackagePlan, SCHEMA_VERSION, SourceSnapshot


class CaseRepositoryError(RuntimeError):
    """本地案例仓库读取或写入失败。"""


class DuplicateCaseError(CaseRepositoryError):
    """同一订单已经确认过包裹方案。"""


class DecisionSource(StrEnum):
    MANUAL = "manual"
    RECOMMENDED_ACCEPTED = "recommended_accepted"
    RECOMMENDED_MODIFIED = "recommended_modified"
    RECOMMENDED_REJECTED = "recommended_rejected"  # 兼容旧数据，不再新增
    ORDER_VERSION = "order_version"


class ShippingMode(StrEnum):
    PARCEL = "parcel"
    FREIGHT = "freight"


@dataclass(frozen=True)
class Decision:
    source: DecisionSource
    recommendation_id: str | None = None
    recommendation_modified: bool = False
    recommendation_case_ids: tuple[str, ...] = ()
    recommendation_algorithm_version: int | None = None
    recommendation_match_type: str | None = None
    shipping_mode: ShippingMode = ShippingMode.PARCEL
    estimated_package_band: str | None = None
    shipping_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "recommendationId": self.recommendation_id,
            "recommendationModified": self.recommendation_modified,
            "recommendationCaseIds": list(self.recommendation_case_ids),
            "recommendationAlgorithmVersion": self.recommendation_algorithm_version,
            "recommendationMatchType": self.recommendation_match_type,
            "shippingMode": self.shipping_mode.value,
            "estimatedPackageBand": self.estimated_package_band,
            "shippingReasons": list(self.shipping_reasons),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Decision:
        return cls(
            source=DecisionSource(str(value.get("source", "manual"))),
            recommendation_id=value.get("recommendationId"),
            recommendation_modified=bool(value.get("recommendationModified")),
            recommendation_case_ids=tuple(value.get("recommendationCaseIds", [])),
            recommendation_algorithm_version=value.get(
                "recommendationAlgorithmVersion"
            ),
            recommendation_match_type=value.get("recommendationMatchType"),
            shipping_mode=ShippingMode(str(value.get("shippingMode", "parcel"))),
            estimated_package_band=value.get("estimatedPackageBand"),
            shipping_reasons=tuple(
                str(item) for item in value.get("shippingReasons", [])
            ),
        )


@dataclass(frozen=True)
class ConfirmedCase:
    schema_version: int
    case_id: str
    confirmed_at: str
    source_snapshot: SourceSnapshot
    package_plan: PackagePlan
    decision: Decision
    previous_case_id: str | None = None
    order_version: int = 1

    @property
    def is_freight(self) -> bool:
        return self.decision.shipping_mode is ShippingMode.FREIGHT

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "caseId": self.case_id,
            "confirmedAt": self.confirmed_at,
            "sourceSnapshot": self.source_snapshot.to_dict(),
            "packagePlan": self.package_plan.to_dict(),
            "decision": self.decision.to_dict(),
            "previousCaseId": self.previous_case_id,
            "orderVersion": self.order_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ConfirmedCase:
        source_snapshot = SourceSnapshot.from_dict(value["sourceSnapshot"])
        package_plan = PackagePlan.from_dict(value["packagePlan"])
        validated_plan = PackageDraft(
            snapshot_id=source_snapshot.snapshot_id,
            packages=package_plan.packages,
        ).confirm(source_snapshot)
        return cls(
            schema_version=int(value.get("schemaVersion", SCHEMA_VERSION)),
            case_id=str(value["caseId"]),
            confirmed_at=str(value["confirmedAt"]),
            source_snapshot=source_snapshot,
            package_plan=validated_plan,
            decision=Decision.from_dict(value.get("decision", {})),
            previous_case_id=value.get("previousCaseId"),
            order_version=int(value.get("orderVersion", 1)),
        )


@dataclass(frozen=True)
class OrderAssignment:
    assignment_id: str
    assigned_at: str
    same_order_signature: str
    case_id: str
    rule_id: str | None = None
    decision: Decision | None = None
    version: int = 1
    previous_assignment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignmentId": self.assignment_id,
            "assignedAt": self.assigned_at,
            "sameOrderSignature": self.same_order_signature,
            "caseId": self.case_id,
            "ruleId": self.rule_id,
            "decision": self.decision.to_dict() if self.decision else None,
            "version": self.version,
            "previousAssignmentId": self.previous_assignment_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> OrderAssignment:
        return cls(
            assignment_id=str(value["assignmentId"]),
            assigned_at=str(value["assignedAt"]),
            same_order_signature=str(value["sameOrderSignature"]),
            case_id=str(value["caseId"]),
            rule_id=value.get("ruleId"),
            decision=(
                Decision.from_dict(value["decision"])
                if isinstance(value.get("decision"), Mapping)
                else None
            ),
            version=int(value.get("version", 1)),
            previous_assignment_id=value.get("previousAssignmentId"),
        )


@dataclass(frozen=True)
class RuleStats:
    rule_id: str
    direct_use_count: int = 0
    modified_count: int = 0
    last_used_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "directUseCount": self.direct_use_count,
            "modifiedCount": self.modified_count,
            "lastUsedAt": self.last_used_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RuleStats:
        return cls(
            rule_id=str(value["ruleId"]),
            direct_use_count=int(value.get("directUseCount", 0)),
            modified_count=int(value.get("modifiedCount", 0)),
            last_used_at=value.get("lastUsedAt"),
        )


@dataclass(frozen=True)
class ResolvedOrderHistory:
    case: ConfirmedCase
    assignment: OrderAssignment | None = None


@dataclass(frozen=True)
class RuleAdoption:
    case: ConfirmedCase
    assignment: OrderAssignment | None
    package_plan: PackagePlan


def default_case_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "Order Review" / "cases.json"


class JsonCaseRepository:
    def __init__(
        self,
        path: str | Path | None = None,
        *,
        backup_keep: int = DEFAULT_BACKUP_KEEP,
        lock_timeout: float = 5.0,
    ) -> None:
        self.path = Path(path) if path is not None else default_case_path()
        self.backup_keep = backup_keep
        self.lock_timeout = lock_timeout
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def list_cases(self) -> list[ConfirmedCase]:
        payload = self._load_payload()
        try:
            return [ConfirmedCase.from_dict(item) for item in payload["cases"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseRepositoryError(f"本地案例内容无效：{exc}") from exc

    def list_assignments(self) -> list[OrderAssignment]:
        payload = self._load_payload()
        try:
            return [
                OrderAssignment.from_dict(item)
                for item in payload.get("orderAssignments", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseRepositoryError(f"本地订单方案索引无效：{exc}") from exc

    def get_rule_stats(self) -> dict[str, RuleStats]:
        payload = self._load_payload()
        raw = payload.get("ruleStats", {})
        if not isinstance(raw, dict):
            raise CaseRepositoryError("本地规则统计结构无效")
        try:
            return {
                str(rule_id): RuleStats.from_dict(
                    {"ruleId": rule_id, **(value if isinstance(value, dict) else {})}
                )
                for rule_id, value in raw.items()
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseRepositoryError(f"本地规则统计内容无效：{exc}") from exc

    def find_same_order(self, source: SourceSnapshot) -> ResolvedOrderHistory | None:
        signature = same_order_signature_key(source)
        if signature is None:
            return None
        cases = self.list_cases()
        cases_by_id = {case.case_id: case for case in cases}
        matching_assignments = [
            item
            for item in self.list_assignments()
            if item.same_order_signature == signature and item.case_id in cases_by_id
        ]
        if matching_assignments:
            assignment = max(
                matching_assignments,
                key=lambda item: (item.version, item.assigned_at, item.assignment_id),
            )
            return ResolvedOrderHistory(cases_by_id[assignment.case_id], assignment)

        matching_cases = [
            case
            for case in cases
            if same_order_signature_key(case.source_snapshot) == signature
        ]
        if not matching_cases:
            return None
        case = max(
            matching_cases,
            key=lambda item: (item.order_version, item.confirmed_at, item.case_id),
        )
        return ResolvedOrderHistory(case=case)

    def confirm(
        self,
        source_snapshot: SourceSnapshot,
        package_plan: PackagePlan,
        decision: Decision,
        *,
        confirmed_at: str | None = None,
        allow_same_snapshot: bool = False,
        previous_case_id: str | None = None,
        rule_id: str | None = None,
    ) -> ConfirmedCase:
        with exclusive_file_lock(self.lock_path, timeout=self.lock_timeout):
            return self._confirm_locked(
                source_snapshot,
                package_plan,
                decision,
                confirmed_at=confirmed_at,
                allow_same_snapshot=allow_same_snapshot,
                previous_case_id=previous_case_id,
                rule_id=rule_id,
            )

    def _confirm_locked(
        self,
        source_snapshot: SourceSnapshot,
        package_plan: PackagePlan,
        decision: Decision,
        *,
        confirmed_at: str | None,
        allow_same_snapshot: bool,
        previous_case_id: str | None,
        rule_id: str | None,
    ) -> ConfirmedCase:
        payload = self._load_payload()
        cases = [ConfirmedCase.from_dict(item) for item in payload["cases"]]
        assignments = [
            OrderAssignment.from_dict(item)
            for item in payload.get("orderAssignments", [])
        ]
        stats = self._parse_rule_stats(payload)
        package_plan = PackageDraft(
            snapshot_id=source_snapshot.snapshot_id,
            packages=package_plan.packages,
        ).confirm(source_snapshot)

        signature = same_order_signature_key(source_snapshot)
        same_order_cases = [
            case
            for case in cases
            if signature is not None
            and same_order_signature_key(case.source_snapshot) == signature
        ]
        if signature is None:
            same_order_cases = [
                case
                for case in cases
                if case.source_snapshot.snapshot_id == source_snapshot.snapshot_id
            ]

        previous_case: ConfirmedCase | None = None
        if previous_case_id is not None:
            previous_case = next(
                (case for case in cases if case.case_id == previous_case_id),
                None,
            )
            if previous_case is None:
                raise CaseRepositoryError("同一订单的上一方案版本不存在")
            previous_matches_order = (
                signature is not None
                and same_order_signature_key(previous_case.source_snapshot) == signature
            ) or (
                signature is None
                and previous_case.source_snapshot.snapshot_id == source_snapshot.snapshot_id
            )
            assignment_links_previous = signature is not None and any(
                item.same_order_signature == signature
                and item.case_id == previous_case_id
                for item in assignments
            )
            if not previous_matches_order and not assignment_links_previous:
                raise CaseRepositoryError("上一方案版本与当前订单没有关联")
        elif same_order_cases:
            if not allow_same_snapshot:
                raise DuplicateCaseError("当前订单已经确认过并保存了包裹方案，不会重复保存")
            previous_case = max(
                same_order_cases,
                key=lambda item: (item.order_version, item.confirmed_at, item.case_id),
            )

        now = confirmed_at or _utc_now()
        confirmed = ConfirmedCase(
            schema_version=SCHEMA_VERSION,
            case_id=f"case-{uuid4()}",
            confirmed_at=now,
            source_snapshot=source_snapshot,
            package_plan=package_plan,
            decision=decision,
            previous_case_id=previous_case.case_id if previous_case else None,
            order_version=(previous_case.order_version + 1 if previous_case else 1),
        )
        cases.append(confirmed)

        if signature is not None:
            assignments.append(
                self._new_assignment(
                    signature,
                    confirmed.case_id,
                    assignments,
                    assigned_at=now,
                    rule_id=rule_id,
                    decision=decision,
                )
            )
        if rule_id and decision.source is DecisionSource.RECOMMENDED_ACCEPTED:
            stats[rule_id] = _increment_stats(stats.get(rule_id), rule_id, modified=False)
        elif rule_id and decision.source in {
            DecisionSource.RECOMMENDED_MODIFIED,
            DecisionSource.ORDER_VERSION,
        }:
            stats[rule_id] = _increment_stats(stats.get(rule_id), rule_id, modified=True)

        self._write_state(cases, assignments, stats)
        return confirmed

    def record_rule_adoption(
        self,
        source_snapshot: SourceSnapshot,
        package_plan: PackagePlan,
        decision: Decision,
        *,
        source_case_id: str,
        rule_id: str,
        assigned_at: str | None = None,
    ) -> RuleAdoption:
        with exclusive_file_lock(self.lock_path, timeout=self.lock_timeout):
            return self._record_rule_adoption_locked(
                source_snapshot,
                package_plan,
                decision,
                source_case_id=source_case_id,
                rule_id=rule_id,
                assigned_at=assigned_at,
            )

    def _record_rule_adoption_locked(
        self,
        source_snapshot: SourceSnapshot,
        package_plan: PackagePlan,
        decision: Decision,
        *,
        source_case_id: str,
        rule_id: str,
        assigned_at: str | None,
    ) -> RuleAdoption:
        payload = self._load_payload()
        cases = [ConfirmedCase.from_dict(item) for item in payload["cases"]]
        assignments = [
            OrderAssignment.from_dict(item)
            for item in payload.get("orderAssignments", [])
        ]
        stats = self._parse_rule_stats(payload)
        package_plan = PackageDraft(
            snapshot_id=source_snapshot.snapshot_id,
            packages=package_plan.packages,
        ).confirm(source_snapshot)
        source_case = next(
            (case for case in cases if case.case_id == source_case_id),
            None,
        )
        if source_case is None:
            raise CaseRepositoryError("历史规则来源案例不存在")

        signature = same_order_signature_key(source_snapshot)
        assignment: OrderAssignment | None = None
        if signature is not None:
            if any(item.same_order_signature == signature for item in assignments):
                raise DuplicateCaseError("当前订单已经保存过包裹方案，不会重复采用")
            assignment = self._new_assignment(
                signature,
                source_case.case_id,
                assignments,
                assigned_at=assigned_at or _utc_now(),
                rule_id=rule_id,
                decision=decision,
            )
            assignments.append(assignment)
        stats[rule_id] = _increment_stats(stats.get(rule_id), rule_id, modified=False)
        self._write_state(cases, assignments, stats)
        return RuleAdoption(source_case, assignment, package_plan)

    def _new_assignment(
        self,
        signature: str,
        case_id: str,
        assignments: list[OrderAssignment],
        *,
        assigned_at: str,
        rule_id: str | None,
        decision: Decision | None,
    ) -> OrderAssignment:
        previous = [
            item for item in assignments if item.same_order_signature == signature
        ]
        latest = (
            max(previous, key=lambda item: (item.version, item.assigned_at))
            if previous
            else None
        )
        return OrderAssignment(
            assignment_id=f"assignment-{uuid4()}",
            assigned_at=assigned_at,
            same_order_signature=signature,
            case_id=case_id,
            rule_id=rule_id,
            decision=decision,
            version=(latest.version + 1 if latest else 1),
            previous_assignment_id=latest.assignment_id if latest else None,
        )

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schemaVersion": SCHEMA_VERSION,
                "cases": [],
                "orderAssignments": [],
                "ruleStats": {},
            }
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaseRepositoryError(f"读取本地案例失败：{exc}") from exc
        if not isinstance(value, dict) or value.get("schemaVersion") != SCHEMA_VERSION:
            raise CaseRepositoryError("本地案例文件版本不受支持")
        cases = value.get("cases")
        if not isinstance(cases, list):
            raise CaseRepositoryError("本地案例文件结构无效")
        assignments = value.get("orderAssignments", [])
        if not isinstance(assignments, list):
            raise CaseRepositoryError("本地订单方案索引结构无效")
        value.setdefault("orderAssignments", [])
        value.setdefault("ruleStats", {})
        return value

    def _parse_rule_stats(self, payload: Mapping[str, Any]) -> dict[str, RuleStats]:
        raw = payload.get("ruleStats", {})
        if not isinstance(raw, dict):
            raise CaseRepositoryError("本地规则统计结构无效")
        return {
            str(rule_id): RuleStats.from_dict(
                {"ruleId": rule_id, **(value if isinstance(value, dict) else {})}
            )
            for rule_id, value in raw.items()
        }

    def _write_state(
        self,
        cases: list[ConfirmedCase],
        assignments: list[OrderAssignment],
        stats: Mapping[str, RuleStats],
    ) -> None:
        self._atomic_write(
            {
                "schemaVersion": SCHEMA_VERSION,
                "cases": [item.to_dict() for item in cases],
                "orderAssignments": [item.to_dict() for item in assignments],
                "ruleStats": {rule_id: item.to_dict() for rule_id, item in stats.items()},
            }
        )

    def _atomic_write(self, payload: Mapping[str, Any]) -> None:
        backup_path: Path | None = None
        try:
            validate_payload_or_raise(payload)
            if self.path.exists():
                backup_path = create_valid_backup(
                    self.path,
                    keep=self.backup_keep,
                )
        except CaseBackupError as exc:
            raise CaseRepositoryError(str(exc)) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
        report = audit_case_file(self.path)
        if not report.valid:
            details = "；".join(issue.message for issue in report.errors)
            try:
                failed_file = quarantine_file(self.path, label="write-failed")
            except OSError as exc:
                raise CaseRepositoryError(
                    "案例写入后校验失败，且无法隔离错误正式文件；"
                    f"有效旧备份仍保留。原错误：{details}"
                ) from exc
            if backup_path is None:
                raise CaseRepositoryError(
                    "案例首次写入后校验失败，错误文件已隔离："
                    f"{failed_file}"
                )
            try:
                atomic_write_bytes(self.path, backup_path.read_bytes())
                rollback_report = audit_case_file(self.path)
                if not rollback_report.valid:
                    raise CaseRepositoryError("有效旧备份写回后仍未通过校验")
            except Exception as exc:
                raise CaseRepositoryError(
                    "案例写入后校验失败，自动恢复旧版本也失败；"
                    f"有效备份仍保留在：{backup_path}"
                ) from exc
            raise CaseRepositoryError(
                "案例写入后校验失败，错误文件已隔离，正式案例已恢复到写入前版本："
                f"{failed_file}"
            )


def _increment_stats(
    current: RuleStats | None,
    rule_id: str,
    *,
    modified: bool,
) -> RuleStats:
    current = current or RuleStats(rule_id=rule_id)
    return RuleStats(
        rule_id=rule_id,
        direct_use_count=current.direct_use_count + (0 if modified else 1),
        modified_count=current.modified_count + (1 if modified else 0),
        last_used_at=_utc_now(),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
