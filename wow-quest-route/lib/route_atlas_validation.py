from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Mapping


HARD_VALIDATORS = (
    "player_state",
    "quest_prerequisite",
    "availability",
    "objective_ready",
    "xp_deadline",
    "transport",
    "branch_state",
    "fivebox_mechanic",
    "spatial_service",
    "background_capacity",
    "no_dead_step",
    "state_continuity",
)


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class UnknownResolution(str, Enum):
    RESEARCH_PUBLIC = "RESEARCH_PUBLIC"
    ASK_USER = "ASK_USER"
    BLOCK_ROUTE = "BLOCK_ROUTE"


@dataclass(frozen=True)
class ValidationResult:
    validator: str
    status: ValidationStatus
    reason: str = ""
    resolution: UnknownResolution | None = None


@dataclass(frozen=True)
class QuestConstraint:
    quest_id: int
    pre_all: frozenset[int] = frozenset()
    pre_any: frozenset[int] = frozenset()
    required_level: int | None = None
    required_min_rep: tuple[int, int] | None = None
    required_max_rep: tuple[int, int] | None = None
    reputation_rewards: tuple[tuple[int, int], ...] = ()
    repeatable: bool = False
    last_full_xp_level: int | None = None


def quest_constraint_from_profile(profile: Mapping[str, object]) -> QuestConstraint:
    """Build the validator-facing constraint subset from a materialized task profile."""

    eligibility = profile.get("eligibility") or {}
    if not isinstance(eligibility, Mapping):
        eligibility = {}

    def rep_pair(key: str) -> tuple[int, int] | None:
        raw = eligibility.get(key)
        if not isinstance(raw, Mapping):
            return None
        faction_id = raw.get("faction_id")
        value = raw.get("value")
        if not isinstance(faction_id, int) or not isinstance(value, int):
            return None
        return faction_id, value

    rewards: list[tuple[int, int]] = []
    raw_rewards = eligibility.get("reputation_rewards") or []
    if isinstance(raw_rewards, list):
        for raw in raw_rewards:
            if not isinstance(raw, Mapping):
                continue
            faction_id = raw.get("faction_id")
            value = raw.get("value")
            if isinstance(faction_id, int) and isinstance(value, int):
                rewards.append((faction_id, value))

    quest_id = profile.get("quest_id")
    if not isinstance(quest_id, int):
        raise ValueError("task profile is missing integer quest_id")
    required_level = profile.get("required_level")
    last_full_xp_level = profile.get("last_full_xp_level")
    return QuestConstraint(
        quest_id=quest_id,
        required_level=required_level if isinstance(required_level, int) else None,
        required_min_rep=rep_pair("required_min_rep"),
        required_max_rep=rep_pair("required_max_rep"),
        reputation_rewards=tuple(rewards),
        repeatable=bool(profile.get("repeatable", False)),
        last_full_xp_level=(
            last_full_xp_level if isinstance(last_full_xp_level, int) else None
        ),
    )


@dataclass(frozen=True)
class RouteState:
    level: int
    xp: int | None = None
    accepted: frozenset[int] = frozenset()
    completed: frozenset[int] = frozenset()
    objectives_complete: frozenset[int] = frozenset()
    reputation: Mapping[int, int] = field(default_factory=dict)
    turnin_counts: Mapping[int, int] = field(default_factory=dict)
    hearth_location: str | None = None
    hearth_ready: bool | None = None
    open_flight_points: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CandidateAction:
    kind: str
    quest_id: int | None = None
    transport_kind: str | None = None
    transport_target: str | None = None
    conditional: bool = False
    branch_value: bool | None = None
    fivebox_status: str = "not_applicable"
    spatial_status: str = "not_applicable"
    is_background: bool = False
    background_capacity_sufficient: bool | None = None
    has_effect: bool = True
    reputation_delta: tuple[tuple[int, int], ...] = ()
    downstream_state_compatible: bool | None = None


@dataclass(frozen=True)
class CandidateValidationReport:
    results: tuple[ValidationResult, ...]

    @property
    def accepted(self) -> bool:
        return all(result.status is ValidationStatus.PASS for result in self.results)

    @property
    def failures(self) -> tuple[ValidationResult, ...]:
        return tuple(result for result in self.results if result.status is not ValidationStatus.PASS)


@dataclass(frozen=True)
class ReplayStepResult:
    index: int
    action: CandidateAction
    report: CandidateValidationReport
    state_before: RouteState
    state_after: RouteState | None


@dataclass(frozen=True)
class ReplayReport:
    valid: bool
    final_state: RouteState
    steps: tuple[ReplayStepResult, ...]

    @property
    def first_invalid_step(self) -> ReplayStepResult | None:
        return next((step for step in self.steps if not step.report.accepted), None)


def _pass(name: str, reason: str = "") -> ValidationResult:
    return ValidationResult(name, ValidationStatus.PASS, reason)


def _fail(name: str, reason: str) -> ValidationResult:
    return ValidationResult(name, ValidationStatus.FAIL, reason)


def _unknown(
    name: str,
    reason: str,
    resolution: UnknownResolution = UnknownResolution.BLOCK_ROUTE,
) -> ValidationResult:
    return ValidationResult(name, ValidationStatus.UNKNOWN, reason, resolution)


def _player_state(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None,
) -> ValidationResult:
    name = "player_state"
    qid = action.quest_id
    if qid is None:
        return _pass(name, "non-quest action")
    if action.kind == "ACCEPT":
        if qid in state.completed and not (quest and quest.repeatable):
            return _fail(name, f"quest {qid} already completed")
        if qid in state.accepted:
            return _fail(name, f"quest {qid} already accepted")
    elif action.kind == "SERVICE":
        if qid not in state.accepted:
            return _fail(name, f"quest {qid} is not active")
        if qid in state.objectives_complete:
            return _fail(name, f"quest {qid} objective already complete")
    elif action.kind == "TURNIN":
        if qid not in state.accepted:
            return _fail(name, f"quest {qid} is not active")
    return _pass(name)


def _quest_prerequisite(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None,
) -> ValidationResult:
    name = "quest_prerequisite"
    if action.kind != "ACCEPT" or quest is None:
        return _pass(name, "not applicable")
    if quest.pre_all and not quest.pre_all.issubset(state.completed):
        missing = sorted(quest.pre_all - state.completed)
        return _fail(name, f"missing all-of prerequisites: {missing}")
    if quest.pre_any and not (quest.pre_any & state.completed):
        return _fail(name, f"none of any-of prerequisites completed: {sorted(quest.pre_any)}")
    return _pass(name)


def _availability(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None,
) -> ValidationResult:
    name = "availability"
    if action.kind != "ACCEPT" or quest is None:
        return _pass(name, "not applicable")
    if quest.required_level is not None and state.level < quest.required_level:
        return _fail(name, f"level {state.level} < required {quest.required_level}")
    for requirement, relation in (
        (quest.required_min_rep, "min"),
        (quest.required_max_rep, "max"),
    ):
        if requirement is None:
            continue
        faction_id, threshold = requirement
        if faction_id not in state.reputation:
            return _unknown(
                name,
                f"reputation for faction {faction_id} is unknown",
                UnknownResolution.ASK_USER,
            )
        value = state.reputation[faction_id]
        if relation == "min" and value < threshold:
            return _fail(name, f"faction {faction_id} rep {value} < required {threshold}")
        if relation == "max" and value >= threshold:
            return _fail(name, f"faction {faction_id} rep {value} >= maximum {threshold}")
    return _pass(name)


def _objective_ready(state: RouteState, action: CandidateAction) -> ValidationResult:
    name = "objective_ready"
    qid = action.quest_id
    if qid is None:
        return _pass(name, "non-quest action")
    if action.kind == "TURNIN" and qid not in state.objectives_complete:
        return _fail(name, f"quest {qid} objectives are not complete")
    return _pass(name)


def _xp_deadline(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None,
) -> ValidationResult:
    name = "xp_deadline"
    if action.kind != "TURNIN" or quest is None or quest.last_full_xp_level is None:
        return _pass(name, "not applicable")
    if state.level > quest.last_full_xp_level:
        return _fail(
            name,
            f"level {state.level} exceeds full-XP deadline {quest.last_full_xp_level}",
        )
    return _pass(name)


def _transport(state: RouteState, action: CandidateAction) -> ValidationResult:
    name = "transport"
    if action.transport_kind is None:
        return _pass(name, "not applicable")
    if action.transport_kind == "HEARTH":
        if action.transport_target is None:
            return _unknown(name, "hearth target is unspecified", UnknownResolution.BLOCK_ROUTE)
        if state.hearth_location is None:
            return _unknown(
                name,
                "current hearth bind is unknown",
                UnknownResolution.ASK_USER,
            )
        if state.hearth_location != action.transport_target:
            return _fail(
                name,
                f"hearth bound to {state.hearth_location}, not {action.transport_target}",
            )
        if state.hearth_ready is None:
            return _unknown(
                name,
                "hearth cooldown state is unknown",
                UnknownResolution.ASK_USER,
            )
        if not state.hearth_ready:
            return _fail(name, "hearth is on cooldown")
        return _pass(name)
    if action.transport_kind == "FLIGHT":
        if action.transport_target is None:
            return _unknown(name, "flight target is unspecified")
        if action.transport_target not in state.open_flight_points:
            return _fail(name, f"flight point {action.transport_target} is not open")
        return _pass(name)
    return _unknown(name, f"unsupported transport kind: {action.transport_kind}")


def _branch_state(action: CandidateAction) -> ValidationResult:
    name = "branch_state"
    if not action.conditional:
        return _pass(name, "not conditional")
    if action.branch_value is None:
        return _unknown(
            name,
            "conditional branch value is unresolved",
            UnknownResolution.ASK_USER,
        )
    if not action.branch_value:
        return _fail(name, "conditional branch is false in current state")
    return _pass(name)


def _fivebox_mechanic(action: CandidateAction) -> ValidationResult:
    name = "fivebox_mechanic"
    if action.kind != "SERVICE":
        return _pass(name, "not applicable")
    if action.fivebox_status == "verified":
        return _pass(name)
    if action.fivebox_status == "conflict":
        return _fail(name, "five-box mechanic conflicts with candidate service model")
    return _unknown(
        name,
        "five-box mechanic is not verified",
        UnknownResolution.ASK_USER,
    )


def _spatial_service(action: CandidateAction) -> ValidationResult:
    name = "spatial_service"
    if action.kind != "SERVICE":
        return _pass(name, "not applicable")
    if action.spatial_status == "verified":
        return _pass(name)
    if action.spatial_status == "manual_review":
        return _pass(
            name,
            "macro service area is known; local loop/entry geometry is delegated to HTML manual review",
        )
    if action.spatial_status == "invalid":
        return _fail(name, "spatial service model is known invalid")
    return _unknown(
        name,
        "macro spatial service area is not verified",
        UnknownResolution.RESEARCH_PUBLIC,
    )


def _background_capacity(action: CandidateAction) -> ValidationResult:
    name = "background_capacity"
    if not action.is_background:
        return _pass(name, "not a background service")
    if action.background_capacity_sufficient is None:
        return _unknown(
            name,
            "background coverage capacity is not proven",
            UnknownResolution.ASK_USER,
        )
    if not action.background_capacity_sufficient:
        return _fail(name, "background route does not cover required service demand")
    return _pass(name)


def _no_dead_step(action: CandidateAction) -> ValidationResult:
    name = "no_dead_step"
    if not action.has_effect:
        return _fail(name, "candidate produces a no-op/dead step")
    return _pass(name)


def _state_continuity(action: CandidateAction) -> ValidationResult:
    name = "state_continuity"
    if action.downstream_state_compatible is None:
        return _unknown(name, "downstream frozen state has not been simulated")
    if not action.downstream_state_compatible:
        return _fail(name, "candidate cannot reconnect to downstream frozen state")
    return _pass(name)


def apply_validated_action(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None = None,
) -> RouteState:
    """Apply one validated action to the dynamic route state.

    Quest reputation rewards are applied on TURNIN. `action.reputation_delta` carries service-time
    reputation such as known per-kill faction gains after the service model has converted kills into
    a concrete delta. Inventory, XP/level progression and hearth cooldown passage remain separate
    models and must not be invented here.
    """

    reputation = dict(state.reputation)
    for faction_id, value in action.reputation_delta:
        reputation[faction_id] = reputation.get(faction_id, 0) + value
    state = replace(state, reputation=reputation)

    qid = action.quest_id
    if qid is None:
        return state
    if action.kind == "ACCEPT":
        return replace(state, accepted=state.accepted | {qid})
    if action.kind == "SERVICE":
        return replace(state, objectives_complete=state.objectives_complete | {qid})
    if action.kind == "TURNIN":
        reputation = dict(state.reputation)
        if quest is not None:
            for faction_id, value in quest.reputation_rewards:
                reputation[faction_id] = reputation.get(faction_id, 0) + value
        turnin_counts = dict(state.turnin_counts)
        turnin_counts[qid] = turnin_counts.get(qid, 0) + 1
        completed = state.completed
        if not (quest and quest.repeatable):
            completed = completed | {qid}
        return replace(
            state,
            accepted=state.accepted - {qid},
            objectives_complete=state.objectives_complete - {qid},
            completed=completed,
            reputation=reputation,
            turnin_counts=turnin_counts,
        )
    return state


def validate_candidate(
    state: RouteState,
    action: CandidateAction,
    quest: QuestConstraint | None = None,
) -> CandidateValidationReport:
    """Run every hard validator and never treat unknown information as feasible.

    This function is intentionally conservative. A candidate is accepted only when all fixed hard
    validators explicitly return PASS; a missing/unknown fact must remain visible as UNKNOWN.
    """

    checks = (
        _player_state(state, action, quest),
        _quest_prerequisite(state, action, quest),
        _availability(state, action, quest),
        _objective_ready(state, action),
        _xp_deadline(state, action, quest),
        _transport(state, action),
        _branch_state(action),
        _fivebox_mechanic(action),
        _spatial_service(action),
        _background_capacity(action),
        _no_dead_step(action),
        _state_continuity(action),
    )
    assert tuple(result.validator for result in checks) == HARD_VALIDATORS
    return CandidateValidationReport(checks)


def replay_frozen_suffix(
    initial_state: RouteState,
    actions: tuple[CandidateAction, ...] | list[CandidateAction],
    constraints: Mapping[int, QuestConstraint],
) -> ReplayReport:
    """Replay the frozen suffix against the new dynamic state instead of comparing states.

    `state_continuity` is established by this replay itself, so each replayed action gets a local
    continuity PASS marker. Any other validator failure/unknown stops the replay at the first
    invalid step and tells the caller where the affected route window must expand.
    """

    state = initial_state
    steps: list[ReplayStepResult] = []
    for index, original_action in enumerate(actions):
        action = replace(original_action, downstream_state_compatible=True)
        quest = constraints.get(action.quest_id) if action.quest_id is not None else None
        report = validate_candidate(state, action, quest)
        if not report.accepted:
            steps.append(
                ReplayStepResult(
                    index=index,
                    action=original_action,
                    report=report,
                    state_before=state,
                    state_after=None,
                )
            )
            return ReplayReport(valid=False, final_state=state, steps=tuple(steps))
        next_state = apply_validated_action(state, action, quest)
        steps.append(
            ReplayStepResult(
                index=index,
                action=original_action,
                report=report,
                state_before=state,
                state_after=next_state,
            )
        )
        state = next_state
    return ReplayReport(valid=True, final_state=state, steps=tuple(steps))
