from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .case_validation import (
    audit_case_file,
    audit_case_file_isolated,
    validate_case_payload,
)
from .file_lock import exclusive_file_lock


DEFAULT_BACKUP_KEEP = 30
_BACKUP_TIMESTAMP_PATTERN = re.compile(
    r"-(?P<timestamp>\d{8}T\d{6}(?:\d{1,6})?Z)\.json$"
)
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CaseBackupError(RuntimeError):
    """案例备份或恢复失败。"""


@dataclass(frozen=True)
class RestoreResult:
    target_path: Path
    recovery_point: Path | None = None
    corrupt_file: Path | None = None
    failed_restore_file: Path | None = None


def default_backup_dir(case_path: str | Path) -> Path:
    return Path(case_path).parent / "backups"


def create_valid_backup(
    source_path: str | Path,
    *,
    backup_dir: str | Path | None = None,
    keep: int = DEFAULT_BACKUP_KEEP,
    prefix: str = "cases",
) -> Path | None:
    source = Path(source_path)
    if not source.exists():
        return None
    report = audit_case_file_isolated(source)
    if not report.valid:
        details = "；".join(issue.message for issue in report.errors)
        raise CaseBackupError(f"现有案例未通过校验，不会创建正式备份：{details}")
    data = source.read_bytes()
    destination_dir = (
        Path(backup_dir) if backup_dir is not None else default_backup_dir(source)
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = destination_dir / f"{prefix}-{timestamp}.json"
    atomic_write_bytes(destination, data)
    copied_report = audit_case_file_isolated(destination)
    if not copied_report.valid:
        destination.unlink(missing_ok=True)
        raise CaseBackupError("备份写入后未通过校验，已移除无效备份")
    _prune_backups(destination_dir, prefix=prefix, keep=keep)
    return destination


def list_valid_backups(
    case_path: str | Path,
    *,
    backup_dir: str | Path | None = None,
) -> list[Path]:
    source = Path(case_path)
    directory = Path(backup_dir) if backup_dir else default_backup_dir(source)
    if not directory.exists():
        return []
    valid_backups: list[tuple[tuple[int, int, str], Path]] = []
    for path in directory.glob("*.json"):
        if not audit_case_file(path).valid:
            continue
        try:
            sort_key = _backup_sort_key(path)
        except OSError:
            continue
        valid_backups.append((sort_key, path))
    valid_backups.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in valid_backups]


def restore_case_backup(
    backup_path: str | Path,
    *,
    target_path: str | Path,
    keep: int = DEFAULT_BACKUP_KEEP,
) -> RestoreResult:
    from .instance_lock import (  # 延迟导入，避免案例仓库初始化时循环依赖
        AlreadyRunningError,
        SingleInstanceGuard,
        instance_lock_path_for_case,
    )

    backup = Path(backup_path)
    target = Path(target_path)
    try:
        backup_data = backup.read_bytes()
        backup_payload = json.loads(backup_data.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaseBackupError(f"恢复来源无法读取：{exc}") from exc
    backup_report = validate_case_payload(
        backup_payload,
        path=str(backup),
    )
    if not backup_report.valid:
        details = "；".join(issue.message for issue in backup_report.errors)
        raise CaseBackupError(f"恢复来源未通过校验：{details}")

    try:
        with SingleInstanceGuard(instance_lock_path_for_case(target)):
            return _restore_with_case_lock(
                backup_data,
                target=target,
                keep=keep,
            )
    except AlreadyRunningError as exc:
        raise CaseBackupError("审单悬浮窗仍在运行；请先退出程序再恢复案例。") from exc


def _restore_with_case_lock(
    backup_data: bytes,
    *,
    target: Path,
    keep: int,
) -> RestoreResult:
    lock_path = target.with_name(f"{target.name}.lock")
    with exclusive_file_lock(lock_path):
        recovery_point: Path | None = None
        corrupt_file: Path | None = None
        failed_restore_file: Path | None = None
        if target.exists():
            current_report = audit_case_file(target)
            if current_report.valid:
                recovery_point = create_valid_backup(
                    target,
                    keep=keep,
                    prefix="pre-restore",
                )
            else:
                corrupt_file = quarantine_file(target, label="corrupt")

        replacement_completed = False
        try:
            atomic_write_bytes(target, backup_data)
            replacement_completed = True
            restored_report = audit_case_file(target)
            if not restored_report.valid:
                details = "；".join(
                    issue.message for issue in restored_report.errors
                )
                raise CaseBackupError(f"恢复后的案例文件未通过校验：{details}")
        except Exception as exc:
            if replacement_completed and target.exists():
                failed_restore_file = quarantine_file(
                    target,
                    label="restore-failed",
                )
            if recovery_point is not None:
                try:
                    atomic_write_bytes(target, recovery_point.read_bytes())
                    rollback_report = audit_case_file(target)
                    if not rollback_report.valid:
                        raise CaseBackupError("恢复前版本写回后仍未通过校验")
                except Exception as rollback_exc:
                    raise CaseBackupError(
                        "案例恢复失败，且恢复前有效版本自动写回失败；"
                        f"有效恢复点仍保留在：{recovery_point}"
                    ) from rollback_exc
            raise CaseBackupError(
                "案例恢复失败；恢复来源和已隔离的故障文件均已保留。"
            ) from exc

        return RestoreResult(
            target_path=target,
            recovery_point=recovery_point,
            corrupt_file=corrupt_file,
            failed_restore_file=failed_restore_file,
        )


def validate_payload_or_raise(payload: Any) -> None:
    report = validate_case_payload(payload)
    if report.errors:
        details = "；".join(issue.message for issue in report.errors)
        raise CaseBackupError(f"待写入案例未通过校验：{details}")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def quarantine_file(path: str | Path, *, label: str) -> Path:
    source = Path(path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = source.with_name(
        f"{source.stem}.{label}-{timestamp}{source.suffix}"
    )
    os.replace(source, destination)
    return destination


def _prune_backups(directory: Path, *, prefix: str, keep: int) -> None:
    if keep < 1:
        raise CaseBackupError("备份保留数量必须大于 0")
    candidates = sorted(directory.glob(f"{prefix}-*.json"), reverse=True)
    for stale in candidates[keep:]:
        stale.unlink()


def _backup_sort_key(path: Path) -> tuple[int, int, str]:
    modified_ns = path.stat().st_mtime_ns
    match = _BACKUP_TIMESTAMP_PATTERN.search(path.name)
    if match is None:
        effective_ns = modified_ns
    else:
        try:
            timestamp = datetime.strptime(
                match.group("timestamp"),
                "%Y%m%dT%H%M%S%fZ",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            effective_ns = modified_ns
        else:
            elapsed = timestamp - _UNIX_EPOCH
            effective_ns = (
                (elapsed.days * 86_400 + elapsed.seconds) * 1_000_000_000
                + elapsed.microseconds * 1_000
            )
    return effective_ns, modified_ns, path.name
