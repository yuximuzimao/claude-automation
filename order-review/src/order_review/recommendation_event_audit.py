from __future__ import annotations

import argparse
import json
from pathlib import Path

from .recommendation_events import (
    audit_recommendation_events,
    default_event_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读检查推荐事件 JSONL 健康状态")
    parser.add_argument(
        "--path",
        type=Path,
        default=default_event_path(),
        help="推荐事件文件路径",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    report = audit_recommendation_events(args.path)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        status = "通过" if report.valid else "失败"
        print(f"推荐事件健康检查：{status}")
        print(f"文件：{report.path}")
        print(
            f"事件 {report.event_count} · 总行数 {report.line_count}"
            f" · 无效行 {report.invalid_line_count}"
        )
        for issue in report.issues:
            location = f"第 {issue.line_number} 行" if issue.line_number else "文件"
            print(f"- {issue.code} [{location}]：{issue.message}")
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
