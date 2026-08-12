from __future__ import annotations

import json

import order_review.memory_diagnostics as memory_diagnostics
from order_review.memory_diagnostics import MemoryDiagnostics


class FakeTk:
    def call(self, *command):
        if command == ("after", "info"):
            return ("after-1", "after-2")
        if command == ("info", "commands"):
            return ("command-1", "command-2", "command-3")
        raise AssertionError(command)

    def splitlist(self, value):
        return tuple(value)


class FakeWidget:
    def __init__(self, *children):
        self.tk = FakeTk()
        self._children = list(children)

    def winfo_children(self):
        return self._children


def test_memory_diagnostics_writes_only_requested_refresh_milestones(
    tmp_path,
    monkeypatch,
):
    report_path = tmp_path / "memory-report.json"
    root = FakeWidget(FakeWidget(), FakeWidget(FakeWidget()))
    monkeypatch.setattr(memory_diagnostics, "_rss_kib", lambda: 12345)
    monkeypatch.setattr(
        memory_diagnostics,
        "_tracked_object_counts",
        lambda: {"SourceSnapshot": 1},
    )
    diagnostics = MemoryDiagnostics(
        report_path,
        refresh_milestones=(1, 3),
        runtime_counters=lambda: {"queueSize": 0},
    )

    diagnostics.record_startup(root)
    diagnostics.record_refresh(root)
    diagnostics.record_refresh(root)
    diagnostics.record_refresh(root)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["refreshMilestones"] == [1, 3]
    assert [sample["label"] for sample in payload["samples"]] == [
        "startup",
        "refresh-1",
        "refresh-3",
    ]
    assert all(sample["rssKiB"] == 12345 for sample in payload["samples"])
    assert all(sample["tkWidgetCount"] == 4 for sample in payload["samples"])
    assert all(sample["tkAfterTaskCount"] == 2 for sample in payload["samples"])
    assert all(sample["tclCommandCount"] == 3 for sample in payload["samples"])
    assert payload["samples"][-1]["runtimeCounters"] == {"queueSize": 0}
