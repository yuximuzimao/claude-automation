"""Two-group first-full-capture orchestration over the single CaptureRunner state machine."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Callable

from src.store import BatchStateStore

from .run_capture import (
    CaptureRunConfig,
    CaptureRunResult,
    CaptureRunner,
    RecoveryRequired,
    StepExecutor,
    Now,
    utc_now,
)


@dataclass(frozen=True)
class GroupTarget:
    group_key: str
    conversation_prefix: str
    header_contains: str
    history_title: str


@dataclass(frozen=True)
class FullCaptureConfig:
    batch_id: str
    groups: tuple[GroupTarget, ...]
    window_x: float
    window_y: float
    window_width: float
    window_height: float
    scroll_pixels: int = 630
    runtime_root: Path = Path("runtime")
    boundary_confirmations: int = 2
    max_new_pages_per_run: int = 20


HistoryOpener = Callable[[GroupTarget], None]


def load_local_full_capture_config(
    path: Path,
    *,
    batch_id: str,
    runtime_root: Path = Path("runtime"),
    max_new_pages_per_run: int = 20,
) -> FullCaptureConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"local capture config is unreadable: {path}") from exc

    window = data.get("window")
    groups = data.get("groups")
    if not isinstance(window, dict) or not isinstance(groups, list) or not groups:
        raise ValueError("local capture config requires window and groups")

    try:
        targets = tuple(
            GroupTarget(
                group_key=str(item["group_key"]),
                conversation_prefix=str(item["conversation_prefix"]),
                header_contains=str(item["header_contains"]),
                history_title=str(item["history_title"]),
            )
            for item in groups
        )
        config = FullCaptureConfig(
            batch_id=batch_id,
            groups=targets,
            window_x=float(window["x"]),
            window_y=float(window["y"]),
            window_width=float(window["width"]),
            window_height=float(window["height"]),
            scroll_pixels=int(data.get("scroll_pixels", 630)),
            runtime_root=runtime_root,
            max_new_pages_per_run=max_new_pages_per_run,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("local capture config fields are invalid") from exc

    keys = [target.group_key for target in config.groups]
    if (
        not config.batch_id
        or any(not key for key in keys)
        or len(set(keys)) != len(keys)
        or config.window_width <= 100
        or config.window_height <= 100
        or config.scroll_pixels <= 0
        or config.boundary_confirmations < 2
        or config.max_new_pages_per_run < 1
    ):
        raise ValueError("local capture config values are invalid")
    return config


class FullCaptureRunner:
    """Capture configured groups serially and finalize only after every boundary is confirmed."""

    def __init__(
        self,
        project_root: Path,
        config: FullCaptureConfig,
        *,
        history_opener: HistoryOpener | None = None,
        step_executor: StepExecutor | None = None,
        now: Now = utc_now,
    ) -> None:
        self.project_root = project_root.resolve()
        self.config = config
        self.runtime_root = (
            config.runtime_root
            if config.runtime_root.is_absolute()
            else self.project_root / config.runtime_root
        )
        self.state_store = BatchStateStore(self.runtime_root / "state" / "batch-state.json")
        self.history_opener = history_opener or self._execute_open_history
        self.step_executor = step_executor
        self.now = now
        self._open_history_binary: Path | None = None

    def run(self) -> CaptureRunResult:
        state = self.state_store.load()
        expected_groups = {target.group_key for target in self.config.groups}
        if state is not None:
            if state["status"] == "incomplete" and state["batch_id"] != self.config.batch_id:
                raise RecoveryRequired(
                    "another incomplete batch already owns the runtime state; refusing any QQ UI action"
                )
            if state["batch_id"] == self.config.batch_id:
                if set(state["groups"]) != expected_groups:
                    raise RecoveryRequired(
                        "active batch group set differs from local config; refusing any QQ UI action"
                    )
                if state["status"] in {"completed", "analyzed"}:
                    return self._runner_for(self.config.groups[0]).run()
                self._preflight_pending_without_ui(state)

        for target in self.config.groups:
            state = self.state_store.load()
            if state is not None and state["batch_id"] == self.config.batch_id:
                progress = state["groups"].get(target.group_key)
                if progress is not None and progress["capture_complete"]:
                    continue
                pending = state["pending_capture"]
                if pending is not None and pending["group_key"] != target.group_key:
                    continue
                should_open = progress is None or progress["last_page_index"] is None
                if pending is not None and self._pending_raw_path(pending).exists():
                    should_open = False
            else:
                should_open = True

            if should_open:
                self.history_opener(target)

            result = self._runner_for(target).run()
            if result.status == "completed":
                return result
            state = self.state_store.load()
            if state is None:
                raise RecoveryRequired("group capture returned without durable batch state")
            if not state["groups"][target.group_key]["capture_complete"]:
                return result

        state = self.state_store.load()
        if state is None:
            raise RecoveryRequired("full capture did not create batch state")
        if all(progress["capture_complete"] for progress in state["groups"].values()):
            return self._runner_for(self.config.groups[-1]).run()
        raise RecoveryRequired("full capture stopped before all configured groups completed")

    def _preflight_pending_without_ui(self, state: dict) -> None:
        pending = state["pending_capture"]
        if pending is None:
            return
        raw_path = self._pending_raw_path(pending)
        if pending["mode"] == "scroll" and not raw_path.exists():
            raise RecoveryRequired(
                "pending scroll has no durable target raw page; refusing to switch/open any QQ history window before manual recovery"
            )

    def _pending_raw_path(self, pending: dict) -> Path:
        return (
            self.runtime_root
            / "raw"
            / self.config.batch_id
            / str(pending["group_key"])
            / f"page-{int(pending['page_index']):06d}.json"
        )

    def _runner_for(self, target: GroupTarget) -> CaptureRunner:
        return CaptureRunner(
            self.project_root,
            CaptureRunConfig(
                batch_id=self.config.batch_id,
                group_key=target.group_key,
                expected_title=target.history_title,
                page_count=None,
                window_x=self.config.window_x,
                window_y=self.config.window_y,
                window_width=self.config.window_width,
                window_height=self.config.window_height,
                scroll_pixels=self.config.scroll_pixels,
                runtime_root=self.config.runtime_root,
                batch_group_keys=tuple(item.group_key for item in self.config.groups),
                boundary_confirmations=self.config.boundary_confirmations,
                max_new_pages=self.config.max_new_pages_per_run,
            ),
            step_executor=self.step_executor,
            now=self.now,
        )

    def _execute_open_history(self, target: GroupTarget) -> None:
        if self._open_history_binary is None:
            self._open_history_binary = self._build_open_history()
        command = [
            str(self._open_history_binary),
            "--group-key", target.group_key,
            "--conversation-prefix", target.conversation_prefix,
            "--header-contains", target.header_contains,
            "--expected-history-title", target.history_title,
        ]
        subprocess.run(command, cwd=self.project_root, check=True)

    def _build_open_history(self) -> Path:
        build_dir = self.project_root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        binary = build_dir / "open-history"
        subprocess.run(
            [
                "swiftc",
                "-parse-as-library",
                "src/capture/CaptureModels.swift",
                "src/capture/ConversationSwitcher.swift",
                "src/app/open-history.swift",
                "-o",
                str(binary),
            ],
            cwd=self.project_root,
            check=True,
        )
        return binary
