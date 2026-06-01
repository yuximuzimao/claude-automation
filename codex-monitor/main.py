"""Command entry point for Codex Monitor."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.aggregate import aggregate_usage
from app.aggregate import ProjectTotal, TokenTotals, UsageAggregate
from app.autostart import (
    build_launch_agent_plist,
    install_launch_agent,
    launch_agent_path,
    launchctl_bootstrap_command,
    uninstall_launch_agent,
)
from app.config import DEFAULT_CLAUDE_PROJECTS_ROOT, DEFAULT_CODEX_SESSIONS_ROOT
from app.models import CodexQuota, RateLimitWindow
from app.packaging import build_app_bundle, choose_python_executable
from app.reader_claude import read_claude_projects
from app.reader_codex import read_codex_sessions
from app.runtime import DebouncedRefresher, PollingWatcher, RefreshRequest, start_watchdog_observer
from app.ui_tk import run_ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex Monitor")
    parser.add_argument(
        "--smoke-codex",
        action="store_true",
        help="Read Codex JSONL files and print a structure-only summary.",
    )
    parser.add_argument(
        "--smoke-claude",
        action="store_true",
        help="Read recent Claude Code JSONL files and print a structure-only summary.",
    )
    parser.add_argument(
        "--smoke-aggregate",
        action="store_true",
        help="Read local JSONL files and print aggregate structure-only summary.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Open the tkinter UI with fake data.",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Open the tkinter UI with local JSONL aggregate data.",
    )
    parser.add_argument(
        "--install-app",
        action="store_true",
        help="Build a local macOS .app wrapper for Codex Monitor.",
    )
    parser.add_argument(
        "--install-autostart",
        action="store_true",
        help="Write the macOS LaunchAgent plist for login startup.",
    )
    parser.add_argument(
        "--uninstall-autostart",
        action="store_true",
        help="Remove the macOS LaunchAgent plist.",
    )
    parser.add_argument(
        "--print-launch-agent",
        action="store_true",
        help="Print the LaunchAgent plist XML without writing it.",
    )
    parser.add_argument(
        "--sessions-root",
        default=str(DEFAULT_CODEX_SESSIONS_ROOT),
        help="Codex sessions root for smoke checks.",
    )
    parser.add_argument(
        "--claude-projects-root",
        default=str(DEFAULT_CLAUDE_PROJECTS_ROOT),
        help="Claude Code projects root for smoke checks.",
    )
    parser.add_argument(
        "--claude-days",
        default=1,
        type=float,
        help="Only include Claude JSONL files modified in the last N days.",
    )
    parser.add_argument(
        "--claude-max-files",
        default=200,
        type=int,
        help="Maximum Claude JSONL files to inspect during smoke checks.",
    )
    parser.add_argument(
        "--app-output-dir",
        default=str(Path.home() / "Applications"),
        help="Directory where Codex Monitor.app should be created.",
    )
    parser.add_argument(
        "--python-executable",
        default=None,
        help="Python executable for app and LaunchAgent wrappers.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.smoke_codex:
        summary = read_codex_sessions(Path(args.sessions_root)).to_summary()
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    if args.smoke_claude:
        modified_since = time.time() - (args.claude_days * 86400)
        summary = read_claude_projects(
            Path(args.claude_projects_root),
            modified_since=modified_since,
            max_files=args.claude_max_files,
        ).to_summary()
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    if args.smoke_aggregate:
        codex, claude = _read_local_data(args)
        print(
            json.dumps(
                aggregate_usage(codex, claude, month_start=_month_start()).to_summary(),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.demo:
        return _run_ui(_demo_aggregate(), refresh_fn=lambda _request: _demo_aggregate())

    if args.ui:
        codex, claude = _read_local_data(args)
        return _run_ui(
            aggregate_usage(codex, claude),
            refresh_fn=lambda request: _load_aggregate(args, request=request),
            runtime_factory=_build_runtime_factory(args),
        )

    if args.install_app:
        python_executable = args.python_executable or choose_python_executable()
        bundle = build_app_bundle(
            output_dir=Path(args.app_output_dir),
            project_dir=_project_dir(),
            python_executable=python_executable,
        )
        print(f"app 已写入 {bundle}")
        return 0

    if args.print_launch_agent:
        python_executable = args.python_executable or choose_python_executable()
        print(
            build_launch_agent_plist(
                project_dir=_project_dir(),
                python_executable=python_executable,
            ).decode("utf-8"),
            end="",
        )
        return 0

    if args.install_autostart:
        python_executable = args.python_executable or choose_python_executable()
        path = install_launch_agent(
            project_dir=_project_dir(),
            python_executable=python_executable,
        )
        print(f"plist 已写入 {path}")
        print("执行以下命令启用开机自启：")
        print(f"  {launchctl_bootstrap_command(path)}")
        return 0

    if args.uninstall_autostart:
        removed = uninstall_launch_agent()
        path = launch_agent_path()
        if removed:
            print(f"plist 已删除 {path}")
        else:
            print(f"plist 不存在 {path}")
        return 0

    print(
        "Codex Monitor UI is not implemented yet. "
        "Use --smoke-codex, --smoke-claude, or --smoke-aggregate."
    )
    return 0


def _month_start(timezone: str = "Asia/Shanghai") -> datetime:
    """Start of the rolling 30-day data window."""
    tz = ZoneInfo(timezone)
    return datetime.now(tz) - timedelta(days=30)


def _read_local_data(
    args: argparse.Namespace,
    *,
    request: RefreshRequest | None = None,
):
    if request and request.claude_modified_since is not None:
        modified_since = request.claude_modified_since
    else:
        modified_since = _month_start().timestamp()
    max_files = request.claude_max_files if request and request.claude_max_files is not None else args.claude_max_files
    codex = read_codex_sessions(Path(args.sessions_root))
    claude = read_claude_projects(
        Path(args.claude_projects_root),
        modified_since=modified_since,
        max_files=max_files,
    )
    return codex, claude


def _project_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_aggregate(
    args: argparse.Namespace,
    *,
    request: RefreshRequest | None = None,
) -> UsageAggregate:
    codex, claude = _read_local_data(args, request=request)
    return aggregate_usage(codex, claude, month_start=_month_start())


def _demo_aggregate() -> UsageAggregate:
    now_ts = time.time()
    return UsageAggregate(
        today=TokenTotals(codex_tokens=1_240_000, claude_tokens=310_000),
        month=TokenTotals(codex_tokens=8_400_000, claude_tokens=2_100_000),
        top_projects=(
            ProjectTotal(
                project="other",
                display_name="其他",
                codex_tokens=4_200_000,
                today_codex_tokens=1_200_000,
                month_percent=40.0,
                sample_cwds=("/Users/chat",),
            ),
            ProjectTotal(
                project="codex-monitor",
                display_name="用量监控软件",
                claude_tokens=1_500_000,
                today_claude_tokens=500_000,
                month_percent=14.3,
                sample_cwds=("/Users/chat/claude/codex-monitor",),
            ),
            ProjectTotal(
                project="product-detect",
                display_name="商品识别训练",
                claude_tokens=900_000,
                today_claude_tokens=200_000,
                month_percent=8.6,
                sample_cwds=("/Users/chat/claude/product-detect",),
            ),
        ),
        quota=CodexQuota(
            primary=RateLimitWindow(
                used_percent=42.0,
                window_minutes=300,
                resets_at=now_ts + 90 * 60,  # 1.5h from now
            ),
            secondary=RateLimitWindow(
                used_percent=11.0,
                window_minutes=10080,
                resets_at=now_ts + 50 * 3600,  # 50h from now
            ),
            timestamp="2026-06-01T13:00:00+08:00",
        ),
        last_updated="2026-06-01T13:00:00+08:00",
    )


def _build_runtime_factory(args: argparse.Namespace):
    paths = (Path(args.sessions_root), Path(args.claude_projects_root))

    def factory(root, window):
        def _make_watcher_request() -> RefreshRequest:
            return RefreshRequest(
                reason="watcher",
                claude_modified_since=_month_start().timestamp(),
                claude_max_files=args.claude_max_files,
            )

        refresher = DebouncedRefresher(
            lambda request: root.after(
                0,
                lambda: window.apply_aggregate(_load_aggregate(args, request=request)),
            ),
            incremental_window_seconds=31 * 86400,
            claude_max_files=args.claude_max_files,
        )

        def notify(path: Path) -> None:
            refresher.notify_change(path, now=time.time())

        observer = start_watchdog_observer(paths, notify)
        poller = None if observer is not None else PollingWatcher(paths, notify)
        state = {"stopped": False, "observer": observer}

        def flush_loop() -> None:
            if state["stopped"]:
                return
            refresher.flush_due(now=time.time())
            root.after(500, flush_loop)

        def poll_loop() -> None:
            if state["stopped"] or poller is None:
                return
            poller.poll_once()
            root.after(5000, poll_loop)

        def close() -> None:
            state["stopped"] = True
            if observer is not None:
                observer.stop()
                observer.join(timeout=2)
            window._on_close()

        root.protocol("WM_DELETE_WINDOW", close)
        root.after(500, flush_loop)
        if poller is not None:
            root.after(5000, poll_loop)
        return state

    return factory


def _run_ui(aggregate: UsageAggregate, refresh_fn=None, runtime_factory=None) -> int:
    try:
        run_ui(aggregate, refresh_fn=refresh_fn, runtime_factory=runtime_factory)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
