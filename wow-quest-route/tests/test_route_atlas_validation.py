from lib.route_atlas_validation import (
    CandidateAction,
    QuestConstraint,
    RouteState,
    UnknownResolution,
    ValidationStatus,
    apply_validated_action,
    quest_constraint_from_profile,
    replay_frozen_suffix,
    validate_candidate,
)


def statuses(report):
    return {result.validator: result for result in report.results}


def test_unknown_hard_fact_blocks_candidate_instead_of_silently_passing():
    state = RouteState(level=65, accepted=frozenset({9702}))
    action = CandidateAction(kind="SERVICE", quest_id=9702)
    report = validate_candidate(state, action)

    assert report.accepted is False
    result = statuses(report)
    assert result["fivebox_mechanic"].status is ValidationStatus.UNKNOWN
    assert result["spatial_service"].status is ValidationStatus.UNKNOWN
    assert result["state_continuity"].status is ValidationStatus.UNKNOWN


def test_reputation_gate_rejects_unavailable_accept():
    state = RouteState(level=65, reputation={970: 2500})
    quest = QuestConstraint(quest_id=9726, required_min_rep=(970, 3000))
    action = CandidateAction(
        kind="ACCEPT",
        quest_id=9726,
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action, quest)

    assert statuses(report)["availability"].status is ValidationStatus.FAIL
    assert report.accepted is False


def test_unknown_reputation_is_unknown_not_pass():
    state = RouteState(level=65)
    quest = QuestConstraint(quest_id=9806, required_min_rep=(970, 0))
    action = CandidateAction(
        kind="ACCEPT",
        quest_id=9806,
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action, quest)

    assert statuses(report)["availability"].status is ValidationStatus.UNKNOWN
    assert report.accepted is False


def test_full_xp_deadline_rejects_late_turnin():
    state = RouteState(
        level=68,
        accepted=frozenset({9898}),
        objectives_complete=frozenset({9898}),
    )
    quest = QuestConstraint(quest_id=9898, last_full_xp_level=67)
    action = CandidateAction(
        kind="TURNIN",
        quest_id=9898,
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action, quest)

    assert statuses(report)["xp_deadline"].status is ValidationStatus.FAIL
    assert report.accepted is False


def test_hearth_must_match_current_binding_and_cooldown():
    state = RouteState(level=65, hearth_location="萨布拉金", hearth_ready=False)
    action = CandidateAction(
        kind="MOVE",
        transport_kind="HEARTH",
        transport_target="萨布拉金",
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)

    assert statuses(report)["transport"].status is ValidationStatus.FAIL
    assert report.accepted is False


def test_known_false_conditional_branch_is_removed_as_infeasible():
    state = RouteState(level=65)
    action = CandidateAction(
        kind="MOVE",
        conditional=True,
        branch_value=False,
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)

    assert statuses(report)["branch_state"].status is ValidationStatus.FAIL
    assert report.accepted is False


def test_fully_verified_service_candidate_can_pass_all_hard_validators():
    state = RouteState(level=65, accepted=frozenset({9702}))
    action = CandidateAction(
        kind="SERVICE",
        quest_id=9702,
        fivebox_status="verified",
        spatial_status="verified",
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)

    assert report.accepted is True
    assert all(result.status is ValidationStatus.PASS for result in report.results)


def test_materialized_profile_reputation_fields_feed_real_validator():
    profile = {
        "quest_id": 9726,
        "required_level": 62,
        "last_full_xp_level": 69,
        "eligibility": {
            "required_min_rep": {"faction_id": 970, "value": 3000},
            "required_max_rep": None,
            "reputation_rewards": [{"faction_id": 970, "value": 250}],
        },
    }
    quest = quest_constraint_from_profile(profile)

    assert quest.required_level == 62
    assert quest.required_min_rep == (970, 3000)
    assert quest.reputation_rewards == ((970, 250),)
    report = validate_candidate(
        RouteState(level=65, reputation={970: 2750}),
        CandidateAction(kind="ACCEPT", quest_id=9726, downstream_state_compatible=True),
        quest,
    )
    assert statuses(report)["availability"].status is ValidationStatus.FAIL


def test_turnin_reputation_reward_changes_later_availability_state():
    reward_quest = QuestConstraint(quest_id=9744, reputation_rewards=((970, 250),))
    state = RouteState(
        level=65,
        accepted=frozenset({9744}),
        objectives_complete=frozenset({9744}),
        reputation={970: 2750},
    )
    state = apply_validated_action(
        state,
        CandidateAction(kind="TURNIN", quest_id=9744),
        reward_quest,
    )
    assert state.reputation[970] == 3000

    unlock = QuestConstraint(quest_id=9726, required_min_rep=(970, 3000))
    report = validate_candidate(
        state,
        CandidateAction(kind="ACCEPT", quest_id=9726, downstream_state_compatible=True),
        unlock,
    )
    assert statuses(report)["availability"].status is ValidationStatus.PASS


def test_fivebox_unknown_explicitly_requests_user_decision():
    state = RouteState(level=65, accepted=frozenset({9702}))
    action = CandidateAction(
        kind="SERVICE",
        quest_id=9702,
        spatial_status="verified",
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)

    result = statuses(report)["fivebox_mechanic"]
    assert result.status is ValidationStatus.UNKNOWN
    assert result.resolution is UnknownResolution.ASK_USER


def test_manual_spatial_review_can_keep_macro_route_candidate_alive():
    state = RouteState(level=65, accepted=frozenset({9814}))
    action = CandidateAction(
        kind="SERVICE",
        quest_id=9814,
        fivebox_status="verified",
        spatial_status="manual_review",
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)

    assert report.accepted is True
    assert "HTML manual review" in statuses(report)["spatial_service"].reason


def test_repeatable_turnin_does_not_permanently_complete_quest():
    quest = QuestConstraint(
        quest_id=9744,
        reputation_rewards=((970, 250),),
        repeatable=True,
    )
    state = RouteState(
        level=65,
        accepted=frozenset({9744}),
        objectives_complete=frozenset({9744}),
        reputation={970: 1000},
    )
    state = apply_validated_action(state, CandidateAction(kind="TURNIN", quest_id=9744), quest)

    assert 9744 not in state.completed
    assert state.turnin_counts[9744] == 1
    assert state.reputation[970] == 1250
    accept_again = validate_candidate(
        state,
        CandidateAction(kind="ACCEPT", quest_id=9744, downstream_state_compatible=True),
        quest,
    )
    assert statuses(accept_again)["player_state"].status is ValidationStatus.PASS


def test_service_reputation_delta_is_applied_before_next_state_check():
    state = RouteState(level=65, accepted=frozenset({9743}), reputation={970: -15})
    action = CandidateAction(
        kind="SERVICE",
        quest_id=9743,
        fivebox_status="verified",
        spatial_status="verified",
        reputation_delta=((970, 15),),
        downstream_state_compatible=True,
    )
    report = validate_candidate(state, action)
    assert report.accepted is True
    state = apply_validated_action(state, action)
    assert state.reputation[970] == 0


def test_frozen_suffix_is_replayed_dynamically_after_reputation_change():
    initial = RouteState(
        level=65,
        accepted=frozenset({9808}),
        objectives_complete=frozenset({9808}),
        reputation={970: 2750},
    )
    constraints = {
        9808: QuestConstraint(quest_id=9808, reputation_rewards=((970, 250),)),
        9809: QuestConstraint(quest_id=9809, required_max_rep=(970, 3000)),
    }
    suffix = [
        CandidateAction(kind="TURNIN", quest_id=9808),
        CandidateAction(kind="ACCEPT", quest_id=9809),
    ]

    replay = replay_frozen_suffix(initial, suffix, constraints)
    assert replay.valid is False
    assert replay.first_invalid_step is not None
    assert replay.first_invalid_step.index == 1
    availability = statuses(replay.first_invalid_step.report)["availability"]
    assert availability.status is ValidationStatus.FAIL
    assert replay.first_invalid_step.state_before.reputation[970] == 3000
