"""Single formal runtime entry for one-group capture with conservative recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
from typing import Callable

from src.normalize.assemble import assemble_capture_pages
from src.normalize.page_reconstruct import validate_capture_page
from src.store import BatchStateStore, MessageStore, StateError
from src.store.finalize import finalize_batch


class CaptureRunError(RuntimeError):
    """Raised when the formal runner cannot safely continue."""


class RecoveryRequired(CaptureRunError):
    """Raised when viewport state is uncertain and automatic scrolling must stop."""


@dataclass(frozen=True)
class CaptureRunConfig:
    batch_id: str
    group_key: str
    expected_title: str
    page_count: int
    window_x: float
    window_y: float
    window_width: float
    window_height: float
    scroll_pixels: int = 630
    runtime_root: Path = Path("runtime")


@dataclass(frozen=True)
class CaptureRunResult:
    batch_id: str
    status: str
    pages: int
    messages: int
    current_path: Path


StepExecutor = Callable[[CaptureRunConfig, str, int, Path, Path | None], None]
Now = Callable[[], str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CaptureRunner:
    def __init__(
        self,
        project_root: Path,
        config: CaptureRunConfig,
        *,
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
        self.message_store = MessageStore(self.runtime_root / "messages" / "messages.jsonl")
        self.current_path = self.runtime_root / "inbox" / "current.md"
        self.raw_dir = (
            self.runtime_root
            / "raw"
            / self.config.batch_id
            / self.config.group_key
        )
        self.step_executor = step_executor or self._execute_swift_step
        self.now = now
        self._capture_step_binary: Path | None = None

    def run(self) -> CaptureRunResult:
        self._validate_config()
        state = self.state_store.load()

        if (
            state is not None
            and state["batch_id"] == self.config.batch_id
            and state["status"] in {"completed", "analyzed"}
        ):
            return self._rebuild_completed(state)

        state = self.state_store.start_batch(
            self.config.batch_id,
            started_at=self.now(),
            group_keys=[self.config.group_key],
        )
        state = self._reconcile_pending(state)
        self._reject_stray_next_raw(state)

        while self._captured_pages(state) < self.config.page_count:
            pending = state["pending_capture"]
            if pending is None:
                page_index = state["next_page_index"]
                mode = (
                    "current"
                    if state["groups"][self.config.group_key]["last_page_index"] is None
                    else "scroll"
                )
                state = self.state_store.begin_capture(
                    self.config.batch_id,
                    self.config.group_key,
                    page_index,
                    mode=mode,
                    started_at=self.now(),
                )
                pending = state["pending_capture"]
            else:
                page_index = pending["page_index"]
                mode = pending["mode"]
                if mode == "scroll":
                    raise RecoveryRequired(
                        "pending scroll has no durable target raw page; viewport position is uncertain, so automatic scrolling is stopped"
                    )

            output = self._page_path(page_index)
            previous = self._previous_page_path(state, page_index, mode)
            self.step_executor(self.config, mode, page_index, output, previous)
            page = self._load_expected_raw(output, page_index)
            state = self.state_store.record_page(
                self.config.batch_id,
                self.config.group_key,
                page_index,
                updated_at=str(page["captured_at"]),
            )

        pages = self._load_recorded_pages(state)
        assembled = assemble_capture_pages(pages)
        finalize_batch(
            state_store=self.state_store,
            message_store=self.message_store,
            batch_id=self.config.batch_id,
            records=assembled.records,
            completed_at=self.now(),
            current_destination=self.current_path,
        )
        return CaptureRunResult(
            batch_id=self.config.batch_id,
            status="completed",
            pages=len(pages),
            messages=len(assembled.records),
            current_path=self.current_path,
        )

    def _rebuild_completed(self, state: dict) -> CaptureRunResult:
        if set(state["groups"]) != {self.config.group_key}:
            raise CaptureRunError("completed state group does not match runner group")
        pages = self._load_recorded_pages(state)
        assembled = assemble_capture_pages(pages)
        finalize_batch(
            state_store=self.state_store,
            message_store=self.message_store,
            batch_id=self.config.batch_id,
            records=assembled.records,
            completed_at=self.now(),
            current_destination=self.current_path,
        )
        return CaptureRunResult(
            batch_id=self.config.batch_id,
            status=str(state["status"]),
            pages=len(pages),
            messages=len(assembled.records),
            current_path=self.current_path,
        )

    def _reconcile_pending(self, state: dict) -> dict:
        pending = state["pending_capture"]
        if pending is None:
            return state
        if pending["group_key"] != self.config.group_key:
            raise RecoveryRequired("pending capture belongs to another group")

        page_index = int(pending["page_index"])
        raw_path = self._page_path(page_index)
        if raw_path.exists():
            page = self._load_expected_raw(raw_path, page_index)
            return self.state_store.record_page(
                self.config.batch_id,
                self.config.group_key,
                page_index,
                updated_at=str(page["captured_at"]),
            )

        if pending["mode"] == "scroll":
            raise RecoveryRequired(
                "a scroll capture was started but its target raw page is missing; the current viewport may already have moved"
            )
        return state

    def _reject_stray_next_raw(self, state: dict) -> None:
        if state["pending_capture"] is not None or not self.raw_dir.exists():
            return
        next_page_index = int(state["next_page_index"])
        stray = sorted(
            path
            for path in self.raw_dir.glob("page-*.json")
            if self._index_from_path(path) >= next_page_index
        )
        if stray:
            raise RecoveryRequired(
                "unrecorded raw page exists at or after next_page_index without pending_capture; refusing to infer how it was produced"
            )

    def _captured_pages(self, state: dict) -> int:
        last = state["groups"][self.config.group_key]["last_page_index"]
        if last is None:
            return 0
        paths = self._raw_paths_up_to(int(last))
        return len(paths)

    def _load_recorded_pages(self, state: dict) -> list[dict]:
        last = state["groups"][self.config.group_key]["last_page_index"]
        if last is None:
            raise CaptureRunError("batch has no recorded pages")
        paths = self._raw_paths_up_to(int(last))
        pages = [self._load_expected_raw(path, self._index_from_path(path)) for path in paths]
        if not pages:
            raise CaptureRunError("recorded batch has no raw pages")
        return pages

    def _raw_paths_up_to(self, last_page_index: int) -> list[Path]:
        if not self.raw_dir.exists():
            raise CaptureRunError("raw directory is missing")
        paths = sorted(self.raw_dir.glob("page-*.json"))
        expected = [
            path
            for path in paths
            if self._index_from_path(path) <= last_page_index
        ]
        indices = [self._index_from_path(path) for path in expected]
        if indices:
            start = indices[0]
            if indices != list(range(start, last_page_index + 1)):
                raise CaptureRunError("durable raw pages are not contiguous through state last_page_index")
        return expected

    def _load_expected_raw(self, path: Path, page_index: int) -> dict:
        try:
            page = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaptureRunError(f"raw page is unreadable: {path}") from exc
        validate_capture_page(page)
        if page["batch_id"] != self.config.batch_id:
            raise CaptureRunError("raw page batch_id does not match active batch")
        if page["group_key"] != self.config.group_key:
            raise CaptureRunError("raw page group_key does not match active group")
        if page["page_index"] != page_index:
            raise CaptureRunError("raw page_index does not match its durable slot")
        return page

    def _previous_page_path(self, state: dict, page_index: int, mode: str) -> Path | None:
        if mode == "current":
            return None
        group_last = state["groups"][self.config.group_key]["last_page_index"]
        if group_last is None or int(group_last) != page_index - 1:
            raise RecoveryRequired("scroll capture has no immediately previous durable page")
        previous = self._page_path(page_index - 1)
        self._load_expected_raw(previous, page_index - 1)
        return previous

    def _page_path(self, page_index: int) -> Path:
        return self.raw_dir / f"page-{page_index:06d}.json"

    @staticmethod
    def _index_from_path(path: Path) -> int:
        try:
            return int(path.stem.split("-")[-1])
        except ValueError as exc:
            raise CaptureRunError(f"invalid raw page filename: {path.name}") from exc

    def _validate_config(self) -> None:
        if not self.config.batch_id or not self.config.group_key or not self.config.expected_title:
            raise CaptureRunError("batch_id, group_key, and expected_title are required")
        if self.config.page_count < 1:
            raise CaptureRunError("page_count must be at least one")
        if self.config.scroll_pixels <= 0:
            raise CaptureRunError("scroll_pixels must be positive")

    def _execute_swift_step(
        self,
        config: CaptureRunConfig,
        mode: str,
        page_index: int,
        output: Path,
        previous: Path | None,
    ) -> None:
        if self._capture_step_binary is None:
            self._capture_step_binary = self._build_capture_step()
        binary = self._capture_step_binary
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(binary),
            "--mode", mode,
            "--group-key", config.group_key,
            "--expected-title", config.expected_title,
            "--batch-id", config.batch_id,
            "--page-index", str(page_index),
            "--output", str(output),
            "--window-x", str(config.window_x),
            "--window-y", str(config.window_y),
            "--window-width", str(config.window_width),
            "--window-height", str(config.window_height),
            "--scroll-pixels", str(config.scroll_pixels),
        ]
        if previous is not None:
            command.extend(["--previous-raw", str(previous)])
        subprocess.run(command, cwd=self.project_root, check=True)

    def _build_capture_step(self) -> Path:
        build_dir = self.project_root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        binary = build_dir / "capture-step"
        sources = [
            "src/capture/CaptureModels.swift",
            "src/capture/VisualFingerprint.swift",
            "src/capture/ContentRegion.swift",
            "src/capture/WindowPreparation.swift",
            "src/capture/ChangeDetector.swift",
            "src/capture/QQHistoryCapture.swift",
            "src/capture/RawPageWriter.swift",
            "src/app/capture-step.swift",
        ]
        subprocess.run(
            ["swiftc", *sources, "-o", str(binary)],
            cwd=self.project_root,
            check=True,
        )
        return binary


def parse_args() -> CaptureRunConfig:
    parser = argparse.ArgumentParser(description="Run one resumable QQ group capture batch")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--group-key", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--pages", type=int, required=True)
    parser.add_argument("--window-x", type=float, required=True)
    parser.add_argument("--window-y", type=float, required=True)
    parser.add_argument("--window-width", type=float, required=True)
    parser.add_argument("--window-height", type=float, required=True)
    parser.add_argument("--scroll-pixels", type=int, default=630)
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    args = parser.parse_args()
    return CaptureRunConfig(
        batch_id=args.batch_id,
        group_key=args.group_key,
        expected_title=args.expected_title,
        page_count=args.pages,
        window_x=args.window_x,
        window_y=args.window_y,
        window_width=args.window_width,
        window_height=args.window_height,
        scroll_pixels=args.scroll_pixels,
        runtime_root=args.runtime_root,
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = parse_args()
    try:
        result = CaptureRunner(project_root, config).run()
    except (CaptureRunError, RecoveryRequired, StateError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"ERROR {exc}") from exc
    print(
        f"DONE batch={result.batch_id} status={result.status} "
        f"pages={result.pages} messages={result.messages} current={result.current_path}"
    )


if __name__ == "__main__":
    main()
