from scripts.build_zangarmarsh_task_profiles import (
    FIVE_BOX_CHARACTERS,
    FIXED_KILL_SECONDS,
    five_box_collect_wait_seconds,
    kill_seconds,
)


def test_first_run_kill_cost_is_fixed_15_seconds_per_mob():
    assert FIXED_KILL_SECONDS == 15.0
    assert kill_seconds(None) == 15.0
    assert 10 * kill_seconds(None) == 150.0


def test_five_box_collect_wait_uses_respawn_times_rounds_minus_one():
    # User example: 6 per character × 5 = 30 items, 10 spawn points, 120s respawn.
    # Three pickup rounds are needed; the first round is immediately available, so wait twice.
    rounds, wait_rounds, seconds = five_box_collect_wait_seconds(6, 10, 120.0)
    assert FIVE_BOX_CHARACTERS == 5
    assert rounds == 3
    assert wait_rounds == 2
    assert seconds == 240.0


def test_five_box_collect_has_no_wait_when_first_round_is_enough():
    rounds, wait_rounds, seconds = five_box_collect_wait_seconds(6, 30, 181.0)
    assert rounds == 1
    assert wait_rounds == 0
    assert seconds == 0.0
