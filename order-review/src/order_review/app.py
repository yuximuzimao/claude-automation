from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .instance_lock import AlreadyRunningError, SingleInstanceGuard
from .memory_diagnostics import MemoryDiagnostics
from .ui import run_app


def main() -> int:
    parser = argparse.ArgumentParser(description="审单悬浮窗")
    parser.add_argument("--version", action="version", version="order-review 0.1.0")
    parser.add_argument(
        "--memory-report",
        type=Path,
        help="在启动及第 1/5/20 次成功刷新后写入匿名内存诊断 JSON",
    )
    args = parser.parse_args()
    try:
        with SingleInstanceGuard():
            diagnostics = (
                MemoryDiagnostics(args.memory_report)
                if args.memory_report is not None
                else None
            )
            run_app(diagnostics)
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
