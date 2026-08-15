from __future__ import annotations

import pytest

from lib.quest_log_counter import QuestLogCounter, simulate_quest_log


def test_quest_log_accept_turnin_and_peak() -> None:
    counter = QuestLogCounter(cap=25, soft_warning=22)
    for quest_id in range(1, 23):
        event = counter.accept(quest_id, step=f"accept-{quest_id}")
    assert counter.count == 22
    assert counter.peak == 22
    assert event["soft_warning"] is True
    assert event["remaining"] == 3

    turnin = counter.turnin(5, step="turnin-5")
    assert turnin["before"] == 22
    assert turnin["after"] == 21
    assert counter.remaining == 4


def test_quest_log_hard_cap_blocks_26th_accept() -> None:
    counter = QuestLogCounter(cap=25)
    for quest_id in range(1, 26):
        counter.accept(quest_id)
    assert counter.count == 25
    assert counter.remaining == 0
    with pytest.raises(ValueError, match="cap exceeded"):
        counter.accept(26)


def test_simulation_replays_accept_and_turnin_events() -> None:
    counter = simulate_quest_log(
        [
            ("accept", 11585, "warsong"),
            ("turnin", 11585, "garrosh"),
            ("accept", 11596, "saurfang"),
            ("turnin", 11596, "razgor"),
            ("accept", 11598, "quarry"),
        ]
    )
    assert counter.count == 1
    assert counter.peak == 1
    assert counter.snapshot()["active_quest_ids"] == [11598]
