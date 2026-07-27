from __future__ import annotations

import argparse
import json
from pathlib import Path

from .case_repository import default_case_path
from .case_validation import AuditIssue, CaseAuditReport, audit_case_file


def _render_text(report: CaseAuditReport) -> str:
    status = "通过" if report.valid else "失败"
    lines = [
        f"案例健康检查：{status}",
        f"文件：{report.path}",
        (
            f"案例 {report.case_count} · 订单索引 {report.assignment_count}"
            f" · 规则统计 {report.rule_count}"
        ),
        f"错误 {len(report.errors)} · 警告 {len(report.warnings)}",
    ]
    for title, issues in (("错误", report.errors), ("警告", report.warnings)):
        if not issues:
            continue
        lines.append(f"\n{title}：")
        lines.extend(_format_issue(issue) for issue in issues)
    return "\n".join(lines)


def _format_issue(issue: AuditIssue) -> str:
    location = f" [{issue.location}]" if issue.location else ""
    return f"- {issue.code}{location}：{issue.message}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读检查审单案例仓库完整性")
    parser.add_argument(
        "--path",
        type=Path,
        default=default_case_path(),
        help="案例文件路径",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    report = audit_case_file(args.path)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_text(report))
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
