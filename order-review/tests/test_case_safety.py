import json
import multiprocessing
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from order_review.case_backup import (
    CaseBackupError,
    create_valid_backup,
    list_valid_backups,
    restore_case_backup,
)
from order_review.case_repository import (
    CaseRepositoryError,
    Decision,
    DecisionSource,
    JsonCaseRepository,
)
from order_review.case_restore import main as case_restore_main
from order_review.case_validation import (
    AuditIssue,
    AuditSeverity,
    CaseAuditReport,
    audit_case_file,
    validate_case_payload,
)
from order_review.instance_lock import (
    AlreadyRunningError,
    SingleInstanceGuard,
    instance_lock_path_for_case,
)
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import PackageDraft, SourceSnapshot


def _source(order_number: str, *, quantity: int = 1) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=(order_number,),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=quantity,
                    merchant_code="CODE-A",
                    spu_id="ITEM-A",
                    sku_id="SKU-A",
                    platform_order_number=order_number,
                )
            ],
        )
    )


def _confirm_worker(path: str, order_number: str, start, results) -> None:
    try:
        start.wait(5)
        source = _source(order_number)
        JsonCaseRepository(path).confirm(
            source,
            PackageDraft.single_package(source).confirm(source),
            Decision(DecisionSource.MANUAL),
        )
        results.put("")
    except Exception as exc:  # pragma: no cover - 由父进程断言具体文本
        results.put(repr(exc))


def _hold_instance_lock(path: str, ready, release) -> None:
    with SingleInstanceGuard(path):
        ready.set()
        release.wait(5)


def test_single_instance_guard_rejects_second_process(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_instance_lock,
        args=(str(tmp_path / "instance.lock"), ready, release),
    )
    process.start()
    assert ready.wait(5)
    try:
        with pytest.raises(AlreadyRunningError, match="已经在运行"):
            with SingleInstanceGuard(tmp_path / "instance.lock"):
                pass
    finally:
        release.set()
        process.join(5)
    assert process.exitcode == 0


def test_concurrent_repository_writes_do_not_lose_cases(tmp_path):
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    path = tmp_path / "cases.json"
    processes = [
        context.Process(
            target=_confirm_worker,
            args=(str(path), f"ORDER-{index}", start, results),
        )
        for index in range(6)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    errors = [results.get(timeout=2) for _ in processes]

    assert errors == [""] * len(processes)
    repository = JsonCaseRepository(path)
    assert len(repository.list_cases()) == len(processes)
    assert len(repository.list_assignments()) == len(processes)
    assert audit_case_file(path).valid


def test_repository_keeps_multiple_valid_backups_and_can_restore(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path, backup_keep=2)
    for index in range(3):
        source = _source(f"ORDER-{index}")
        repository.confirm(
            source,
            PackageDraft.single_package(source).confirm(source),
            Decision(DecisionSource.MANUAL),
        )

    backups = list_valid_backups(path)
    assert len(backups) == 2
    assert all(audit_case_file(item).valid for item in backups)
    oldest_payload = json.loads(backups[-1].read_text(encoding="utf-8"))
    assert len(oldest_payload["cases"]) == 1

    result = restore_case_backup(backups[-1], target_path=path, keep=2)

    assert result.recovery_point is not None
    assert audit_case_file(result.recovery_point).valid
    assert audit_case_file(path).valid
    assert len(JsonCaseRepository(path).list_cases()) == 1


def test_valid_backup_listing_uses_timestamp_across_prefixes_and_mtime_fallback(
    tmp_path,
    capsys,
):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    payload = json.dumps(
        {
            "schemaVersion": 1,
            "cases": [],
            "orderAssignments": [],
            "ruleStats": {},
        }
    )
    older_restore = backup_dir / "pre-restore-20260724T120000000000Z.json"
    newer_cases = backup_dir / "cases-20260724T130000000000Z.json"
    newest_by_mtime = backup_dir / "manual-valid-backup.json"
    invalid_future = backup_dir / "pre-restore-20260724T150000000000Z.json"
    for path in (older_restore, newer_cases, newest_by_mtime):
        path.write_text(payload, encoding="utf-8")
    invalid_future.write_text('{"cases":"broken"}', encoding="utf-8")
    fallback_ns = int(
        datetime(2026, 7, 24, 14, tzinfo=timezone.utc).timestamp()
        * 1_000_000_000
    )
    os.utime(newest_by_mtime, ns=(fallback_ns, fallback_ns))

    backups = list_valid_backups(
        tmp_path / "cases.json",
        backup_dir=backup_dir,
    )

    assert backups == [newest_by_mtime, newer_cases, older_restore]
    assert (
        case_restore_main(
            [
                "--list",
                "--paths-only",
                "--target",
                str(tmp_path / "cases.json"),
                "--backup-dir",
                str(backup_dir),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.splitlines() == [
        str(newest_by_mtime),
        str(newer_cases),
        str(older_restore),
    ]


def test_restore_quarantines_corrupt_official_file_then_restores_valid_backup(
    tmp_path,
):
    backup = tmp_path / "valid-backup.json"
    backup_repository = JsonCaseRepository(backup)
    source = _source("ORDER-VALID-BACKUP")
    backup_repository.confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    target = tmp_path / "official" / "cases.json"
    target.parent.mkdir()
    corrupt_bytes = b'{"schemaVersion":1,"cases":"broken"}'
    target.write_bytes(corrupt_bytes)

    result = restore_case_backup(backup, target_path=target)

    assert result.recovery_point is None
    assert result.corrupt_file is not None
    assert result.corrupt_file.read_bytes() == corrupt_bytes
    assert result.corrupt_file.name.startswith("cases.corrupt-")
    assert audit_case_file(target).valid
    assert len(JsonCaseRepository(target).list_cases()) == 1


def test_restore_refuses_while_order_review_instance_is_running(tmp_path):
    backup = tmp_path / "valid-backup.json"
    repository = JsonCaseRepository(backup)
    source = _source("ORDER-LOCKED")
    repository.confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    target = tmp_path / "official" / "cases.json"

    with SingleInstanceGuard(instance_lock_path_for_case(target)):
        with pytest.raises(CaseBackupError, match="请先退出程序"):
            restore_case_backup(backup, target_path=target)


def test_repository_restores_previous_valid_file_after_post_write_audit_failure(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    first_source = _source("ORDER-BEFORE")
    repository.confirm(
        first_source,
        PackageDraft.single_package(first_source).confirm(first_source),
        Decision(DecisionSource.MANUAL),
    )
    real_audit = audit_case_file
    failed_once = False

    def fail_first_post_write_audit(audit_path):
        nonlocal failed_once
        if Path(audit_path) == path and not failed_once:
            failed_once = True
            return CaseAuditReport(
                path=str(path),
                issues=(
                    AuditIssue(
                        AuditSeverity.ERROR,
                        "injected_post_write_failure",
                        "模拟写后校验失败",
                    ),
                ),
            )
        return real_audit(audit_path)

    monkeypatch.setattr(
        "order_review.case_repository.audit_case_file",
        fail_first_post_write_audit,
    )
    second_source = _source("ORDER-AFTER")

    with pytest.raises(CaseRepositoryError, match="正式案例已恢复到写入前版本"):
        repository.confirm(
            second_source,
            PackageDraft.single_package(second_source).confirm(second_source),
            Decision(DecisionSource.MANUAL),
        )

    assert audit_case_file(path).valid
    assert len(JsonCaseRepository(path).list_cases()) == 1
    failed_files = list(tmp_path.glob("cases.write-failed-*.json"))
    assert len(failed_files) == 1
    assert len(JsonCaseRepository(failed_files[0]).list_cases()) == 2


def test_invalid_case_file_is_never_promoted_to_official_backup(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text('{"schemaVersion": 1, "cases": "broken"}', encoding="utf-8")

    with pytest.raises(CaseBackupError, match="不会创建正式备份"):
        create_valid_backup(path)

    assert list((tmp_path / "backups").glob("*.json")) == []


def test_audit_distinguishes_reference_error_and_identity_warning(tmp_path):
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-X",),
            products=[
                Product(
                    title="无编码商品",
                    standard_name="无编码商品",
                    short_name="无编码",
                    quantity=1,
                    platform_order_number="ORDER-X",
                )
            ],
        )
    )
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    repository.confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["orderAssignments"][0]["caseId"] = "case-missing"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = audit_case_file(path)

    assert not report.valid
    assert any(issue.code == "assignment_case_missing" for issue in report.errors)
    assert any(issue.code == "product_identity_missing" for issue in report.warnings)


def test_audit_covers_duplicate_ids_version_chains_cycles_and_orphan_stats(tmp_path):
    path = tmp_path / "cases.json"
    source = _source("ORDER-AUDIT")
    JsonCaseRepository(path).confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    original_case = payload["cases"][0]
    original_assignment = payload["orderAssignments"][0]

    second_case = json.loads(json.dumps(original_case))
    second_case["caseId"] = "case-second"
    second_case["orderVersion"] = 2
    second_case["previousCaseId"] = original_case["caseId"]
    original_case["previousCaseId"] = second_case["caseId"]
    payload["cases"].append(second_case)
    ambiguous_case = json.loads(json.dumps(second_case))
    ambiguous_case["caseId"] = "case-ambiguous-version"
    payload["cases"].append(ambiguous_case)

    second_assignment = json.loads(json.dumps(original_assignment))
    second_assignment["assignmentId"] = "assignment-second"
    second_assignment["version"] = 2
    second_assignment["previousAssignmentId"] = original_assignment["assignmentId"]
    original_assignment["previousAssignmentId"] = second_assignment["assignmentId"]
    payload["orderAssignments"].append(second_assignment)
    ambiguous_assignment = json.loads(json.dumps(second_assignment))
    ambiguous_assignment["assignmentId"] = "assignment-ambiguous-version"
    payload["orderAssignments"].append(ambiguous_assignment)
    payload["ruleStats"] = {
        "rule-unused": {
            "ruleId": "rule-unused",
            "directUseCount": 0,
            "modifiedCount": 0,
        }
    }

    report = validate_case_payload(payload)
    error_codes = {issue.code for issue in report.errors}
    warning_codes = {issue.code for issue in report.warnings}

    assert {
        "case_cycle",
        "case_latest_ambiguous",
        "assignment_cycle",
        "assignment_latest_ambiguous",
    }.issubset(error_codes)
    assert "rule_stat_orphan" in warning_codes

    duplicate_payload = json.loads(path.read_text(encoding="utf-8"))
    duplicate_payload["cases"].append(duplicate_payload["cases"][0])
    duplicate_report = validate_case_payload(duplicate_payload)

    assert any(
        issue.code == "case_id_duplicate" for issue in duplicate_report.errors
    )


def test_audit_rejects_high_case_version_without_previous_case(tmp_path):
    path = tmp_path / "cases.json"
    source = _source("ORDER-MISSING-PREVIOUS")
    JsonCaseRepository(path).confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cases"][0]["orderVersion"] = 2

    report = validate_case_payload(payload)

    assert any(issue.code == "case_previous_missing" for issue in report.errors)


def test_audit_rejects_unknown_shipping_mode(tmp_path):
    path = tmp_path / "cases.json"
    source = _source("ORDER-BAD-SHIPPING")
    JsonCaseRepository(path).confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cases"][0]["decision"]["shippingMode"] = "unknown"

    report = validate_case_payload(payload)

    assert any(issue.code == "shipping_mode_invalid" for issue in report.errors)
