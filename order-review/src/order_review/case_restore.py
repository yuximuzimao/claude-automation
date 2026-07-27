from __future__ import annotations

import argparse
from pathlib import Path

from .case_backup import (
    CaseBackupError,
    list_valid_backups,
    restore_case_backup,
)
from .case_repository import default_case_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="人工恢复审单案例备份")
    parser.add_argument(
        "--target",
        type=Path,
        default=default_case_path(),
        help="要恢复的正式案例文件",
    )
    parser.add_argument("--list", action="store_true", help="列出可用有效备份")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="列出备份时使用的目录；默认使用正式案例旁的 backups",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="列出备份时最多显示的数量",
    )
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="列出备份时只输出路径；没有有效备份时不输出提示",
    )
    parser.add_argument("--from", dest="source", type=Path, help="恢复来源备份")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="明确确认执行恢复；未提供时只显示计划",
    )
    args = parser.parse_args(argv)

    if args.list:
        if args.limit is not None and args.limit < 1:
            parser.error("--limit 必须大于 0")
        backups = list_valid_backups(
            args.target,
            backup_dir=args.backup_dir,
        )
        if args.limit is not None:
            backups = backups[: args.limit]
        if not backups:
            if not args.paths_only:
                print("没有找到可读取且校验有效的案例备份。")
            return 0
        for path in backups:
            print(path)
        return 0

    if args.source is None:
        parser.error("恢复时必须提供 --from，或使用 --list 查看备份")
    if not args.yes:
        print(f"准备从以下备份恢复：{args.source}")
        print(f"目标文件：{args.target}")
        print("未执行。确认路径无误后追加 --yes。")
        return 2
    try:
        result = restore_case_backup(
            args.source,
            target_path=args.target,
        )
    except CaseBackupError as exc:
        print(f"恢复失败：{exc}")
        return 1
    print(f"恢复完成：{args.target}")
    if result.recovery_point is not None:
        print(f"恢复前版本已备份：{result.recovery_point}")
    if result.corrupt_file is not None:
        print(f"损坏正式文件已隔离：{result.corrupt_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
