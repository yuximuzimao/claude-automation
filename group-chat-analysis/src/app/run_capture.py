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
from src.normalize.incremental import find_anchor_end, reindex_new_records_after_anchor
from src.normalize.page_reconstruct import validate_capture_page
from src.store import BatchStateStore, MessageStore, StateError
from src.store.finalize import finalize_batch, finalize_incremental_batch


class CaptureRunError(RuntimeError):
    """Raised when the formal runner cannot safely continue."""


class RecoveryRequired(CaptureRunError):
    """Raised when viewport state is uncertain and automatic scrolling must stop."""


class CaptureNoChange(CaptureRunError):
    """Raised when a verified scroll attempt produced no viewport change."""


class CapturePreScrollRejected(CaptureRunError):
    """Raised when capture-step rejected a scroll before any scroll side effect."""


@dataclass(frozen=True)
class CaptureRunConfig:
    batch_id: str
    group_key: str
    expected_title: str
    page_count: int | None
    window_x: float
    window_y: float
    window_width: float
    window_height: float
    scroll_pixels: int = 630
    runtime_root: Path = Path("runtime")
    batch_group_keys: tuple[str, ...] = ()
    boundary_confirmations: int = 2
    max_new_pages: int | None = None
    batch_kind: str = "capture"


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
        self.batch_group_keys = config.batch_group_keys or (config.group_key,)
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
            group_keys=list(self.batch_group_keys),
            batch_kind=self.config.batch_kind,
        )
        if state["groups"][self.config.group_key]["capture_complete"]:
            return self._finish_or_report_incomplete(state)

        state = self._reconcile_pending(state)
        self._reject_stray_next_raw(state)
        state, anchor_found = self._mark_incremental_anchor_if_found(state)
        if anchor_found:
            return self._finish_or_report_incomplete(state)
        no_change_streak = 0
        new_pages = 0

        while True:
            if (
                self.config.page_count is not None
                and self._captured_pages(state) >= self.config.page_count
            ):
                state = self.state_store.mark_group_capture_complete(
                    self.config.batch_id,
                    self.config.group_key,
                    completed_at=self.now(),
                )
                break
            if (
                self.config.max_new_pages is not None
                and new_pages >= self.config.max_new_pages
            ):
                return CaptureRunResult(
                    batch_id=self.config.batch_id,
                    status="incomplete",
                    pages=self._captured_pages(state),
                    messages=0,
                    current_path=self.current_path,
                )

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
                if pending["group_key"] != self.config.group_key:
                    raise RecoveryRequired("pending capture belongs to another group")
                if mode == "scroll":
                    raise RecoveryRequired(
                        "pending scroll has no durable target raw page; viewport position is uncertain, so automatic scrolling is stopped"
                    )

            output = self._page_path(page_index)
            previous = self._previous_page_path(state, page_index, mode)
            try:
                self.step_executor(self.config, mode, page_index, output, previous)
            except CapturePreScrollRejected:
                if mode != "scroll":
                    raise CaptureRunError("pre-scroll rejection is only valid for scroll capture")
                self.state_store.abort_pending_capture(
                    self.config.batch_id,
                    self.config.group_key,
                    page_index,
                    updated_at=self.now(),
                )
                raise RecoveryRequired(
                    "scroll was rejected before any scroll side effect; pending_capture was safely cleared, retry after the viewport is stable"
                )
            except CaptureNoChange:
                if mode != "scroll":
                    raise CaptureRunError("no-change is only valid for scroll capture")
                state = self.state_store.record_no_change(
                    self.config.batch_id,
                    self.config.group_key,
                    page_index,
                    updated_at=self.now(),
                )
                no_change_streak += 1
                if no_change_streak >= self.config.boundary_confirmations:
                    if self.config.batch_kind == "incremental":
                        raise RecoveryRequired(
                            "history boundary was reached before the previous completed anchor; refusing to complete incremental capture"
                        )
                    state = self.state_store.mark_group_capture_complete(
                        self.config.batch_id,
                        self.config.group_key,
                        completed_at=self.now(),
                    )
                    break
                continue

            page = self._load_expected_raw(output, page_index)
            state = self.state_store.record_page(
                self.config.batch_id,
                self.config.group_key,
                page_index,
                updated_at=str(page["captured_at"]),
            )
            new_pages += 1
            no_change_streak = 0
            state, anchor_found = self._mark_incremental_anchor_if_found(state)
            if anchor_found:
                break

        return self._finish_or_report_incomplete(state)

    def _mark_incremental_anchor_if_found(self, state: dict) -> tuple[dict, bool]:
        if self.config.batch_kind != "incremental":
            return state, False
        progress = state["groups"][self.config.group_key]
        if progress["capture_complete"]:
            return state, True
        if progress["last_page_index"] is None:
            return state, False
        anchors = progress["start_anchor"]
        pages = self._load_recorded_pages(state, group_key=self.config.group_key)
        assembled = assemble_capture_pages(pages)
        if find_anchor_end(assembled.records, anchors) is None:
            return state, False
        completed = self.state_store.mark_group_capture_complete(
            self.config.batch_id,
            self.config.group_key,
            completed_at=self.now(),
        )
        return completed, True

    def _finish_or_report_incomplete(self, state: dict) -> CaptureRunResult:
        if not all(
            progress["capture_complete"] for progress in state["groups"].values()
        ):
            return CaptureRunResult(
                batch_id=self.config.batch_id,
                status="incomplete",
                pages=self._captured_pages(state),
                messages=0,
                current_path=self.current_path,
            )

        records, page_count = self._assemble_all_groups(state)
        finalizer = (
            finalize_incremental_batch
            if self.config.batch_kind == "incremental"
            else finalize_batch
        )
        finalizer(
            state_store=self.state_store,
            message_store=self.message_store,
            batch_id=self.config.batch_id,
            records=records,
            completed_at=self.now(),
            current_destination=self.current_path,
        )
        return CaptureRunResult(
            batch_id=self.config.batch_id,
            status="completed",
            pages=page_count,
            messages=len(records),
            current_path=self.current_path,
        )

    def _rebuild_completed(self, state: dict) -> CaptureRunResult:
        if state.get("batch_kind") != self.config.batch_kind:
            raise CaptureRunError("completed state batch_kind does not match runner mode")
        if set(state["groups"]) != set(self.batch_group_keys):
            raise CaptureRunError("completed state groups do not match runner groups")
        records, page_count = self._assemble_all_groups(state)
        finalizer = (
            finalize_incremental_batch
            if self.config.batch_kind == "incremental"
            else finalize_batch
        )
        finalizer(
            state_store=self.state_store,
            message_store=self.message_store,
            batch_id=self.config.batch_id,
            records=records,
            completed_at=self.now(),
            current_destination=self.current_path,
        )
        return CaptureRunResult(
            batch_id=self.config.batch_id,
            status=str(state["status"]),
            pages=page_count,
            messages=len(records),
            current_path=self.current_path,
        )

    def _assemble_all_groups(self, state: dict) -> tuple[list[dict[str, object]], int]:
        records: list[dict[str, object]] = []
        page_count = 0
        for group_key in self.batch_group_keys:
            pages = self._load_recorded_pages(state, group_key=group_key)
            assembled = assemble_capture_pages(pages)
            group_records = list(assembled.records)
            if self.config.batch_kind == "incremental":
                group_records = reindex_new_records_after_anchor(
                    group_records,
                    state["groups"][group_key]["start_anchor"],
                )
            records.extend(group_records)
            page_count += len(pages)
        return records, page_count

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

    def _captured_pages(self, state: dict, *, group_key: str | None = None) -> int:
        key = group_key or self.config.group_key
        last = state["groups"][key]["last_page_index"]
        if last is None:
            return 0
        paths = self._raw_paths_up_to(int(last), group_key=key)
        return len(paths)

    def _load_recorded_pages(
        self,
        state: dict,
        *,
        group_key: str | None = None,
    ) -> list[dict]:
        key = group_key or self.config.group_key
        last = state["groups"][key]["last_page_index"]
        if last is None:
            raise CaptureRunError(f"group {key} has no recorded pages")
        paths = self._raw_paths_up_to(int(last), group_key=key)
        pages = [
            self._load_expected_raw(path, self._index_from_path(path), group_key=key)
            for path in paths
        ]
        if not pages:
            raise CaptureRunError(f"group {key} has no durable raw pages")
        return pages

    def _raw_paths_up_to(
        self,
        last_page_index: int,
        *,
        group_key: str | None = None,
    ) -> list[Path]:
        key = group_key or self.config.group_key
        raw_dir = self._raw_dir(key)
        if not raw_dir.exists():
            raise CaptureRunError(f"raw directory is missing for group {key}")
        paths = sorted(raw_dir.glob("page-*.json"))
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

    def _load_expected_raw(
        self,
        path: Path,
        page_index: int,
        *,
        group_key: str | None = None,
    ) -> dict:
        key = group_key or self.config.group_key
        try:
            page = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaptureRunError(f"raw page is unreadable: {path}") from exc
        validate_capture_page(page)
        if page["batch_id"] != self.config.batch_id:
            raise CaptureRunError("raw page batch_id does not match active batch")
        if page["group_key"] != key:
            raise CaptureRunError("raw page group_key does not match expected group")
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

    def _raw_dir(self, group_key: str) -> Path:
        return self.runtime_root / "raw" / self.config.batch_id / group_key

    def _page_path(self, page_index: int) -> Path:
        return self._raw_dir(self.config.group_key) / f"page-{page_index:06d}.json"

    @staticmethod
    def _index_from_path(path: Path) -> int:
        try:
            return int(path.stem.split("-")[-1])
        except ValueError as exc:
            raise CaptureRunError(f"invalid raw page filename: {path.name}") from exc

    def _validate_config(self) -> None:
        if not self.config.batch_id or not self.config.group_key or not self.config.expected_title:
            raise CaptureRunError("batch_id, group_key, and expected_title are required")
        if self.config.batch_kind not in {"capture", "incremental"}:
            raise CaptureRunError("batch_kind must be capture or incremental")
        if self.config.batch_kind == "incremental" and self.config.page_count is not None:
            raise CaptureRunError("incremental capture cannot use a fixed page_count")
        if self.config.group_key not in self.batch_group_keys:
            raise CaptureRunError("group_key must be part of batch_group_keys")
        if len(set(self.batch_group_keys)) != len(self.batch_group_keys):
            raise CaptureRunError("batch_group_keys must be unique")
        if self.config.page_count is not None and self.config.page_count < 1:
            raise CaptureRunError("page_count must be at least one when provided")
        if self.config.boundary_confirmations < 2:
            raise CaptureRunError("boundary_confirmations must be at least two")
        if self.config.max_new_pages is not None and self.config.max_new_pages < 1:
            raise CaptureRunError("max_new_pages must be at least one when provided")
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
        result = subprocess.run(command, cwd=self.project_root, check=False)
        if result.returncode == 10:
            raise CaptureNoChange("verified scroll produced no viewport change")
        if result.returncode == 11:
            raise CapturePreScrollRejected("capture-step rejected before scroll side effect")
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run resumable QQ group capture")
    parser.add_argument("--batch-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="capture all groups from config/local.json to history boundary")
    mode.add_argument("--incremental", action="store_true", help="capture only messages newer than the previous completed anchors")
    parser.add_argument("--config", type=Path, default=Path("config/local.json"))
    parser.add_argument("--max-new-pages", type=int, default=20)
    parser.add_argument("--group-key")
    parser.add_argument("--expected-title")
    parser.add_argument("--pages", type=int)
    parser.add_argument("--window-x", type=float)
    parser.add_argument("--window-y", type=float)
    parser.add_argument("--window-width", type=float)
    parser.add_argument("--window-height", type=float)
    parser.add_argument("--scroll-pixels", type=int, default=630)
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    args = parser.parse_args()
    if args.full or args.incremental:
        return args

    required = (
        args.group_key,
        args.expected_title,
        args.pages,
        args.window_x,
        args.window_y,
        args.window_width,
        args.window_height,
    )
    if any(value is None for value in required):
        parser.error("bounded mode requires --group-key, --expected-title, --pages and window geometry")
    return args


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    args = parse_args()
    try:
        if args.full or args.incremental:
            from .full_capture import FullCaptureRunner, load_local_full_capture_config

            config_path = args.config if args.config.is_absolute() else project_root / args.config
            config = load_local_full_capture_config(
                config_path,
                batch_id=args.batch_id,
                runtime_root=args.runtime_root,
                max_new_pages_per_run=args.max_new_pages,
            )
            if args.incremental:
                from .incremental_capture import IncrementalCaptureRunner

                result = IncrementalCaptureRunner(project_root, config).run()
            else:
                result = FullCaptureRunner(project_root, config).run()
        else:
            config = CaptureRunConfig(
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
            result = CaptureRunner(project_root, config).run()
    except (
        CaptureRunError,
        RecoveryRequired,
        StateError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        raise SystemExit(f"ERROR {exc}") from exc
    print(
        f"DONE batch={result.batch_id} status={result.status} "
        f"pages={result.pages} messages={result.messages} current={result.current_path}"
    )


if __name__ == "__main__":
    main()
