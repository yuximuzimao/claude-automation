from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import gc
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import tkinter as tk
import tracemalloc
from typing import Any


TRACKED_OBJECT_TYPES = (
    "ConfirmedCase",
    "OrderAssignment",
    "RepositorySnapshot",
    "SidebarView",
    "SourceSnapshot",
)


class MemoryDiagnostics:
    """在正式 UI 进程内按固定刷新节点记录轻量内存诊断。"""

    def __init__(
        self,
        output_path: Path,
        *,
        refresh_milestones: Sequence[int] = (1, 5, 20),
        runtime_counters: Callable[[], Mapping[str, int]] | None = None,
    ) -> None:
        milestones = tuple(sorted(set(refresh_milestones)))
        if not milestones or milestones[0] <= 0:
            raise ValueError("刷新采样节点必须是正整数")
        self.output_path = output_path
        self.refresh_milestones = milestones
        self.runtime_counters = runtime_counters
        self.refresh_count = 0
        self.started_at = time.time()
        self.started_monotonic = time.monotonic()
        self.samples: list[dict[str, Any]] = []
        if not tracemalloc.is_tracing():
            tracemalloc.start(1)

    def record_startup(self, root: tk.Misc) -> None:
        self._record(root, label="startup")

    def record_refresh(self, root: tk.Misc) -> None:
        self.refresh_count += 1
        if self.refresh_count in self.refresh_milestones:
            self._record(root, label=f"refresh-{self.refresh_count}")

    def _record(self, root: tk.Misc, *, label: str) -> None:
        gc.collect()
        traced_current, traced_peak = tracemalloc.get_traced_memory()
        sample = {
            "label": label,
            "refreshCount": self.refresh_count,
            "elapsedSeconds": round(time.monotonic() - self.started_monotonic, 3),
            "rssKiB": _rss_kib(),
            "tracedCurrentKiB": traced_current // 1024,
            "tracedPeakKiB": traced_peak // 1024,
            "tkWidgetCount": _widget_count(root),
            "tkAfterTaskCount": _tcl_item_count(root, "after", "info"),
            "tclCommandCount": _tcl_item_count(root, "info", "commands"),
            "threadCount": threading.active_count(),
            "trackedPythonObjects": _tracked_object_counts(),
            "runtimeCounters": (
                dict(self.runtime_counters()) if self.runtime_counters else {}
            ),
        }
        self.samples.append(sample)
        self._write_report()

    def _write_report(self) -> None:
        payload = {
            "schemaVersion": 1,
            "pid": os.getpid(),
            "startedAtEpochSeconds": self.started_at,
            "refreshMilestones": list(self.refresh_milestones),
            "samples": self.samples,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.output_path.with_name(
            f".{self.output_path.name}.{os.getpid()}.tmp"
        )
        try:
            with temporary_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.output_path)
        finally:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _rss_kib() -> int:
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def _widget_count(root: tk.Misc) -> int:
    total = 1
    pending = list(root.winfo_children())
    while pending:
        widget = pending.pop()
        total += 1
        pending.extend(widget.winfo_children())
    return total


def _tcl_item_count(root: tk.Misc, *command: str) -> int:
    value = root.tk.call(*command)
    if not value:
        return 0
    if isinstance(value, tuple):
        return len(value)
    return len(root.tk.splitlist(value))


def _tracked_object_counts() -> dict[str, int]:
    counts = {name: 0 for name in TRACKED_OBJECT_TYPES}
    for item in gc.get_objects():
        name = type(item).__name__
        if name in counts:
            counts[name] += 1
    return counts
