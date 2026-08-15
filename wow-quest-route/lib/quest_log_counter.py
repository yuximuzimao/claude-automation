from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class QuestLogCounter:
    """Deterministic 25-slot quest-log model for Route Atlas insertion audits."""

    cap: int = 25
    soft_warning: int = 22
    active: set[int] = field(default_factory=set)
    peak: int = 0
    events: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.peak = max(self.peak, len(self.active))
        if len(self.active) > self.cap:
            raise ValueError(f"initial quest log exceeds cap: {len(self.active)} > {self.cap}")

    @property
    def count(self) -> int:
        return len(self.active)

    @property
    def remaining(self) -> int:
        return self.cap - len(self.active)

    def accept(self, quest_id: int, *, step: str = "") -> dict[str, object]:
        quest_id = int(quest_id)
        before = len(self.active)
        if quest_id in self.active:
            raise ValueError(f"quest {quest_id} already active")
        if before >= self.cap:
            raise ValueError(f"quest log cap exceeded by accepting {quest_id}: {before}/{self.cap}")
        self.active.add(quest_id)
        after = len(self.active)
        self.peak = max(self.peak, after)
        event = {
            "action": "accept",
            "quest_id": quest_id,
            "step": step,
            "before": before,
            "after": after,
            "remaining": self.cap - after,
            "soft_warning": after >= self.soft_warning,
        }
        self.events.append(event)
        return event

    def turnin(self, quest_id: int, *, step: str = "") -> dict[str, object]:
        quest_id = int(quest_id)
        before = len(self.active)
        if quest_id not in self.active:
            raise ValueError(f"quest {quest_id} not active at turn-in")
        self.active.remove(quest_id)
        after = len(self.active)
        event = {
            "action": "turnin",
            "quest_id": quest_id,
            "step": step,
            "before": before,
            "after": after,
            "remaining": self.cap - after,
            "soft_warning": after >= self.soft_warning,
        }
        self.events.append(event)
        return event

    def snapshot(self) -> dict[str, object]:
        return {
            "cap": self.cap,
            "soft_warning": self.soft_warning,
            "count": len(self.active),
            "remaining": self.remaining,
            "peak": self.peak,
            "active_quest_ids": sorted(self.active),
        }


def simulate_quest_log(
    events: Iterable[tuple[str, int, str]],
    *,
    initial_active: Iterable[int] = (),
    cap: int = 25,
    soft_warning: int = 22,
) -> QuestLogCounter:
    counter = QuestLogCounter(cap=cap, soft_warning=soft_warning, active={int(qid) for qid in initial_active})
    for action, quest_id, step in events:
        if action == "accept":
            counter.accept(quest_id, step=step)
        elif action == "turnin":
            counter.turnin(quest_id, step=step)
        else:
            raise ValueError(f"unknown quest log action: {action}")
    return counter
