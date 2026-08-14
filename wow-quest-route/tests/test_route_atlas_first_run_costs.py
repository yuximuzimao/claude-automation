from scripts.audit_zangarmarsh_task_profiles import apply_component_overrides
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


def test_shared_corpse_drop_override_does_not_multiply_drop_attempts_by_five():
    profile = {
        "components": [
            {
                "family": "mob_drop",
                "requirement_key": "item:24373",
                "needed_count": 1,
                "sources": [
                    {"entity_id": 1, "drop_rate_percent": 10.0, "single_kill_seconds": 15.0},
                    {"entity_id": 2, "drop_rate_percent": 100.0, "single_kill_seconds": 15.0},
                ],
                "baseline_source": {"entity_id": 2, "drop_rate_percent": 100.0, "single_kill_seconds": 15.0},
                "estimated_objective_seconds": 75.0,
            }
        ],
        "solo_time_estimate": {"total_travel_seconds": 0.0, "calculations": {}},
    }
    apply_component_overrides(
        profile,
        {"component_overrides": {"item:24373": {"effective_drop_demand_characters": 1}}},
    )
    sources = profile["components"][0]["sources"]
    assert sources[0]["expected_kills"] == 10.0
    assert sources[1]["expected_kills"] == 1.0
    assert profile["components"][0]["estimated_objective_seconds"] == 15.0
