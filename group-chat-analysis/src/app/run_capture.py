"""Single formal runtime entry for resumable QQ capture and history backfill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable

from src.app.pending_scroll_recovery import raw_pages_same_view, unique_rewind_anchor
from src.app.swift_sources import CAPTURE_STEP_SOURCES
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
    expected_message_date: str | None = None


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

    def recover_pending_scroll_by_reanchor(self) -> dict:
        """Re-anchor an unknown post-scroll viewport without trusting its position.

        Recovery never promotes the failed target page.  It captures the current
        viewport as a probe, rewinds toward newer messages until two consecutive
        probes uniquely match two consecutive already-durable pages, then replays
        forward while verifying every durable page until the last known page is
        reached.  Only then is the original pending scroll cleared so the normal
        runner can re-read the missing target page from a known-safe viewport.
        """

        self._validate_config()
        state = self.state_store.load()
        if state is None:
            raise RecoveryRequired("no batch state exists for pending-scroll recovery")
        if state["batch_id"] != self.config.batch_id or state["status"] != "incomplete":
            raise RecoveryRequired("pending-scroll recovery requires the active incomplete batch")
        if set(state["groups"]) != set(self.batch_group_keys):
            raise RecoveryRequired("pending-scroll recovery group set does not match the active batch")

        pending = state["pending_capture"]
        if pending is None or pending["mode"] != "scroll":
            raise RecoveryRequired("there is no pending scroll capture to recover")
        if pending["group_key"] != self.config.group_key:
            raise RecoveryRequired("pending capture belongs to another group")

        pending_index = int(pending["page_index"])
        progress = state["groups"][self.config.group_key]
        last_page_index = progress["last_page_index"]
        if last_page_index is None or pending_index != int(last_page_index) + 1:
            raise RecoveryRequired("pending scroll is not immediately after the last durable page")
        last_page_index = int(last_page_index)
        if last_page_index < 1:
            raise RecoveryRequired("pending-scroll re-anchor needs at least two durable pages")
        if self._page_path(pending_index).exists():
            raise RecoveryRequired("pending target raw already exists; use normal pending reconciliation")

        lookback_start = max(0, last_page_index - 12)
        durable_pages = {
            index: self._load_expected_raw(self._page_path(index), index)
            for index in range(lookback_start, last_page_index + 1)
        }
        probe_dir = (
            self.runtime_root
            / "diagnostics"
            / "pending-scroll-recovery"
            / self.config.batch_id
            / self.config.group_key
        )
        shutil.rmtree(probe_dir, ignore_errors=True)
        probe_dir.mkdir(parents=True, exist_ok=True)

        try:
            probes: list[tuple[int, dict, Path]] = []
            current_path = probe_dir / f"probe-current-{pending_index:06d}.json"
            self.step_executor(self.config, "current", pending_index, current_path, None)
            current_probe = self._load_expected_raw(current_path, pending_index)
            probes.append((pending_index, current_probe, current_path))

            anchor_index: int | None = None
            for rewind_number in range(1, 7):
                probe_index = pending_index - rewind_number
                if probe_index < 0:
                    break
                previous_probe_path = probes[-1][2]
                output = probe_dir / f"probe-rewind-{rewind_number:02d}-{probe_index:06d}.json"
                try:
                    self.step_executor(
                        self.config,
                        "rewind",
                        probe_index,
                        output,
                        previous_probe_path,
                    )
                except CaptureNoChange:
                    break
                probe = self._load_expected_raw(output, probe_index)
                probes.append((probe_index, probe, output))
                if len(probes) >= 2:
                    anchor_index = unique_rewind_anchor(
                        probes[-2][1],
                        probes[-1][1],
                        durable_pages,
                    )
                    if anchor_index is not None:
                        break

            if anchor_index is None:
                raise RecoveryRequired(
                    "could not re-anchor on two consecutive durable pages after rewinding; pending scroll preserved"
                )

            current_probe = probes[-1][1]
            if not raw_pages_same_view(current_probe, durable_pages[anchor_index]):
                raise RecoveryRequired("re-anchor sequence did not end on the claimed durable page")

            for target_index in range(anchor_index + 1, last_page_index + 1):
                previous_durable = self._page_path(target_index - 1)
                output = probe_dir / f"replay-{target_index:06d}.json"
                try:
                    self.step_executor(
                        self.config,
                        "scroll",
                        target_index,
                        output,
                        previous_durable,
                    )
                except CaptureNoChange as exc:
                    raise RecoveryRequired(
                        f"re-anchor replay stopped before durable page {target_index}"
                    ) from exc
                replay = self._load_expected_raw(output, target_index)
                if not raw_pages_same_view(replay, durable_pages[target_index]):
                    raise RecoveryRequired(
                        f"re-anchor replay did not match durable page {target_index}; pending scroll preserved"
                    )

            final_probe_path = probe_dir / f"final-{last_page_index:06d}.json"
            self.step_executor(
                self.config,
                "current",
                last_page_index,
                final_probe_path,
                None,
            )
            final_probe = self._load_expected_raw(final_probe_path, last_page_index)
            if not raw_pages_same_view(final_probe, durable_pages[last_page_index]):
                raise RecoveryRequired(
                    "final recovery viewport does not match the last durable page; pending scroll preserved"
                )

            return self.state_store.abort_pending_capture(
                self.config.batch_id,
                self.config.group_key,
                pending_index,
                updated_at=self.now(),
            )
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)
            for parent in (probe_dir.parent, probe_dir.parent.parent):
                try:
                    parent.rmdir()
                except OSError:
                    pass

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
        self._validate_expected_message_date(records)
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
        self._validate_expected_message_date(records)
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

    def _validate_expected_message_date(self, records: list[dict[str, object]]) -> None:
        expected = self.config.expected_message_date
        if expected is None:
            return
        if not records:
            raise RecoveryRequired("history-date capture produced no canonical messages")
        observed = {str(record["message_date"]) for record in records if record.get("message_date") is not None}
        if expected not in observed:
            raise RecoveryRequired(
                f"history-date capture did not contain the selected date: expected={expected} observed={sorted(observed)}"
            )
        unexpected = sorted(value for value in observed if value != expected)
        if unexpected:
            raise RecoveryRequired(
                f"history-date capture contains messages from other dates: expected={expected} unexpected={unexpected}"
            )
        for record in records:
            timestamp = record.get("timestamp")
            if timestamp is None:
                continue
            if str(timestamp)[:10] != expected:
                raise RecoveryRequired(
                    f"history-date capture contains an out-of-day timestamp: expected={expected} timestamp={timestamp}"
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
        subprocess.run(
            ["swiftc", *CAPTURE_STEP_SOURCES, "-o", str(binary)],
            cwd=self.project_root,
            check=True,
        )
        return binary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run resumable QQ group capture")
    parser.add_argument("--batch-id")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="capture all groups from config/local.json to history boundary")
    mode.add_argument("--incremental", action="store_true", help="capture only messages newer than the previous completed anchors")
    parser.add_argument("--config", type=Path, default=Path("config/local.json"))
    parser.add_argument("--max-new-pages", type=int)
    parser.add_argument("--group-key")
    parser.add_argument("--expected-title")
    parser.add_argument("--pages", type=int)
    parser.add_argument("--window-x", type=float)
    parser.add_argument("--window-y", type=float)
    parser.add_argument("--window-width", type=float)
    parser.add_argument("--window-height", type=float)
    parser.add_argument("--scroll-pixels", type=int, default=630)
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    parser.add_argument("--history-date", help="single-group full capture for one QQ history date (YYYY-MM-DD)")
    parser.add_argument("--background", action="store_true", help="run history-date capture detached and return immediately")
    args = parser.parse_args()
    if args.background and args.history_date is None:
        parser.error("--background is only valid with --history-date")
    if args.history_date is not None:
        if args.incremental:
            parser.error("--history-date cannot be combined with --incremental")
        if not args.group_key:
            parser.error("--history-date requires --group-key")
        try:
            datetime.strptime(args.history_date, "%Y-%m-%d")
        except ValueError:
            parser.error("--history-date must be YYYY-MM-DD")
        args.full = True
        if args.batch_id is None:
            args.batch_id = f"history-{args.history_date.replace('-', '')}-full"
        if args.runtime_root == Path("runtime"):
            args.runtime_root = Path("runtime/history-days") / args.history_date
        if args.max_new_pages is None:
            args.max_new_pages = 1000
    else:
        if args.batch_id is None:
            parser.error("--batch-id is required unless --history-date is used")
        if args.max_new_pages is None:
            args.max_new_pages = 20

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


def history_background_paths(project_root: Path, target_date: str) -> tuple[Path, Path]:
    diagnostics = project_root / "runtime" / "diagnostics"
    log_name = f"history-{target_date.replace('-', '')}-background.log"
    return diagnostics / log_name, diagnostics / "history-background.pid"


def history_background_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.app.run_capture",
        "--history-date", str(args.history_date),
        "--group-key", str(args.group_key),
        "--batch-id", str(args.batch_id),
        "--runtime-root", str(args.runtime_root),
        "--max-new-pages", str(args.max_new_pages),
        "--config", str(args.config),
    ]


def start_history_background(project_root: Path, args: argparse.Namespace) -> tuple[int, Path]:
    if not args.background or args.history_date is None:
        raise CaptureRunError("background launch requires --history-date --background")
    log_path, pid_path = history_background_paths(project_root, args.history_date)
    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text(encoding="utf-8").strip())
            os.kill(existing_pid, 0)
        except (OSError, ValueError):
            pass
        else:
            raise CaptureRunError(
                f"history-date background capture is already running for {args.history_date} (pid={existing_pid})"
            )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab", buffering=0) as log_file:
        process = subprocess.Popen(
            history_background_command(args),
            cwd=project_root,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_path.write_text(str(process.pid), encoding="utf-8")
    return process.pid, log_path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    args = parse_args()
    try:
        if args.background:
            pid, log_path = start_history_background(project_root, args)
            print(f"STARTED history_date={args.history_date} pid={pid} log={log_path}")
            return
        if args.full or args.incremental:
            from .full_capture import FullCaptureRunner, load_local_full_capture_config

            config_path = args.config if args.config.is_absolute() else project_root / args.config
            config = load_local_full_capture_config(
                config_path,
                batch_id=args.batch_id,
                runtime_root=args.runtime_root,
                max_new_pages_per_run=args.max_new_pages,
                group_key=args.group_key,
                history_date=args.history_date,
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
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        raise SystemExit(f"ERROR {exc}") from exc
    print(
        f"DONE batch={result.batch_id} status={result.status} "
        f"pages={result.pages} messages={result.messages} current={result.current_path}"
    )


if __name__ == "__main__":
    main()
