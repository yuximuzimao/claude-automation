import json
from pathlib import Path

from lib.route_atlas_reputation import ReputationBlockedQueue, max_rep_expiry_risks
from lib.route_atlas_validation import quest_constraint_from_profile


ROOT = Path(__file__).resolve().parents[1]


def load_profiles():
    data = json.loads((ROOT / "data/route-atlas/zangarmarsh-task-profiles.json").read_text())
    return data["quests"]


def test_blocked_queue_exposes_only_lowest_unreached_threshold_first():
    profiles = load_profiles()
    queue = ReputationBlockedQueue.from_profiles(profiles, {970: -1})

    threshold, quest_ids = queue.next_threshold(970, -1)
    assert threshold == 0
    assert 9806 in quest_ids
    assert 9919 in quest_ids
    assert 9726 not in quest_ids


def test_reputation_transition_emits_newly_unlocked_tasks_one_by_one_in_stable_order():
    profiles = load_profiles()
    queue = ReputationBlockedQueue.from_profiles(profiles, {970: 2750})

    events = queue.newly_unlocked(970, 2750, 3000)
    assert events
    assert all(event.threshold == 3000 for event in events)
    assert [event.quest_id for event in events] == sorted(event.quest_id for event in events)
    assert 9726 in [event.quest_id for event in events]
    assert 9727 in [event.quest_id for event in events]


def test_reputation_jump_crossing_multiple_thresholds_keeps_low_to_high_event_order():
    profiles = load_profiles()
    queue = ReputationBlockedQueue.from_profiles(profiles, {970: -1})

    events = queue.newly_unlocked(970, -1, 3000)
    thresholds = [event.threshold for event in events]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == 0
    assert thresholds[-1] == 3000


def test_max_rep_crossing_warns_before_low_reputation_tasks_are_closed():
    profiles = load_profiles()
    constraints = [quest_constraint_from_profile(profile) for profile in profiles.values()]

    risks = max_rep_expiry_risks(constraints, 970, 2750, 3000)
    risk_ids = {risk.quest_id for risk in risks}
    assert {9739, 9742, 9743, 9744, 9808, 9809}.issubset(risk_ids)


def test_completed_repeatable_task_still_counts_as_max_rep_expiry_risk():
    profiles = load_profiles()
    constraints = [quest_constraint_from_profile(profile) for profile in profiles.values()]

    risks = max_rep_expiry_risks(
        constraints,
        970,
        2750,
        3000,
        already_completed=frozenset({9744}),
    )
    assert 9744 in {risk.quest_id for risk in risks}


def test_already_accepted_low_rep_task_is_not_reported_as_new_acceptance_expiry_risk():
    profiles = load_profiles()
    constraints = [quest_constraint_from_profile(profile) for profile in profiles.values()]

    risks = max_rep_expiry_risks(
        constraints,
        970,
        2750,
        3000,
        already_accepted=frozenset({9808}),
    )
    assert 9808 not in {risk.quest_id for risk in risks}
