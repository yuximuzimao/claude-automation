from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TASK_KINDS = {"accept", "objective", "turnin"}


class RouteReplayError(ValueError):
    """Raised when a Route Profile cannot be replayed consistently."""


@dataclass
class ReplayState:
    """Structured RouteState passed into the single Stage 3 replay engine.

    Stage 4 may order Profiles and pass this state between them, but it must not
    implement a second copy of the task/hearth/flight transition logic.
    """

    active_tasks: set[int] = field(default_factory=set)
    maybe_active_tasks: set[int] = field(default_factory=set)
    active_tasks_known: bool = False
    completed_tasks: set[int] = field(default_factory=set)
    maybe_completed_tasks: set[int] = field(default_factory=set)
    completed_tasks_known: bool = False
    hearth_location: str | None = None
    hearth_location_known: bool = False
    opened_flight_points: set[str] = field(default_factory=set)
    opened_flight_points_known: bool = False


@dataclass
class RouteReplay:
    profile_id: str
    active_tasks: set[int] = field(default_factory=set)
    maybe_active_tasks: set[int] = field(default_factory=set)
    active_tasks_known: bool = False
    entry_active_tasks_known: bool = False
    completed_tasks: set[int] = field(default_factory=set)
    maybe_completed_tasks: set[int] = field(default_factory=set)
    completed_tasks_known: bool = False
    quest_log_peak_upper_bound: int | None = None
    quest_log_events: list[dict[str, Any]] = field(default_factory=list)
    hearth_location: str | None = None
    entry_hearth_location_known: bool = False
    hearth_location_known: bool = False
    hearth_events: list[dict[str, Any]] = field(default_factory=list)
    opened_flight_points: set[str] = field(default_factory=set)
    opened_flight_points_known: bool = False
    required_entry_flight_points: set[str] = field(default_factory=set)
    required_entry_hearth_locations: set[str] = field(default_factory=set)
    flight_events: list[dict[str, Any]] = field(default_factory=list)
    availability_events: list[dict[str, Any]] = field(default_factory=list)
    action_execution: dict[str, str] = field(default_factory=dict)
    external_state_requirements: list[dict[str, Any]] = field(default_factory=list)
    deferred_gates: list[dict[str, Any]] = field(default_factory=list)
    reputation_reward_delta: dict[int, int] = field(default_factory=dict)
    maybe_reputation_reward_delta: dict[int, int] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)

    def _quest_log_upper_bound(self) -> int | None:
        if not self.active_tasks_known:
            return None
        return len(self.active_tasks | self.maybe_active_tasks)

    def _record_quest_log(self, action: dict[str, Any]) -> None:
        count = self._quest_log_upper_bound()
        if count is not None:
            self.quest_log_peak_upper_bound = max(self.quest_log_peak_upper_bound or 0, count)
        self.quest_log_events.append(
            {
                "action_id": action["action_id"],
                "kind": action["kind"],
                "task_id": action.get("task_id"),
                "active_count": len(self.active_tasks),
                "maybe_active_count": len(self.maybe_active_tasks),
                "active_state_known": self.active_tasks_known,
                "upper_bound": count,
            }
        )
        if count is not None and count > 25:
            self.issues.append(
                {
                    "severity": "error",
                    "kind": "quest_log_cap_exceeded",
                    "action_id": action["action_id"],
                    "count": count,
                    "cap": 25,
                }
            )

    def _external_requirement(self, *, action_id: str, task_id: int, kind: str, **detail: Any) -> None:
        self.external_state_requirements.append(
            {"action_id": action_id, "task_id": task_id, "kind": kind, **detail}
        )

    def _deferred_gate(self, *, action_id: str, task_id: int, kind: str, **detail: Any) -> None:
        self.deferred_gates.append({"action_id": action_id, "task_id": task_id, "kind": kind, **detail})

    def _error(self, *, action_id: str, kind: str, task_id: int | None = None, **detail: Any) -> None:
        row: dict[str, Any] = {"severity": "error", "kind": kind, "action_id": action_id, **detail}
        if task_id is not None:
            row["task_id"] = task_id
        self.issues.append(row)


def _evaluate_accept_availability(
    replay: RouteReplay,
    *,
    action: dict[str, Any],
    task_card: dict[str, Any],
    character_profile: dict[str, Any] | None,
) -> None:
    action_id = str(action["action_id"])
    task_id = int(action["task_id"])
    identity = task_card.get("identity") or {}
    availability = task_card.get("availability") or {}
    checks: list[dict[str, Any]] = []

    def record(kind: str, status: str, **detail: Any) -> None:
        checks.append({"kind": kind, "status": status, **detail})

    # Static faction/race/class are provided by the Character Profile. The route profile string ID
    # itself has no semantic meaning.
    task_faction = identity.get("faction")
    if task_faction in {"horde", "alliance"}:
        if character_profile is None:
            record("faction", "deferred", required=task_faction)
            replay._deferred_gate(
                action_id=action_id, task_id=task_id, kind="missing_character_profile", field="faction"
            )
        elif character_profile["faction"] != task_faction:
            record("faction", "fail", required=task_faction, actual=character_profile["faction"])
            replay._error(
                action_id=action_id,
                task_id=task_id,
                kind="availability_faction_mismatch",
                required=task_faction,
                actual=character_profile["faction"],
            )
        else:
            record("faction", "pass", value=task_faction)
    elif task_faction == "unknown":
        record("faction", "deferred", required="unknown")
        replay._deferred_gate(action_id=action_id, task_id=task_id, kind="unknown_task_faction")

    required_race = list(availability.get("required_race") or [])
    if required_race:
        if character_profile is None:
            record("race", "deferred", allowed=required_race)
            replay._deferred_gate(
                action_id=action_id, task_id=task_id, kind="missing_character_profile", field="race"
            )
        elif character_profile["race"] not in required_race:
            record("race", "fail", allowed=required_race, actual=character_profile["race"])
            replay._error(
                action_id=action_id,
                task_id=task_id,
                kind="availability_race_mismatch",
                allowed=required_race,
                actual=character_profile["race"],
            )
        else:
            record("race", "pass", value=character_profile["race"])

    required_class = list(availability.get("required_class") or [])
    if required_class:
        if character_profile is None:
            record("class", "deferred", allowed=required_class)
            replay._deferred_gate(
                action_id=action_id, task_id=task_id, kind="missing_character_profile", field="class"
            )
        elif character_profile["class"] not in required_class:
            record("class", "fail", allowed=required_class, actual=character_profile["class"])
            replay._error(
                action_id=action_id,
                task_id=task_id,
                kind="availability_class_mismatch",
                allowed=required_class,
                actual=character_profile["class"],
            )
        else:
            record("class", "pass", value=character_profile["class"])

    # Level is dynamic inside a Profile. Stage 3 records the hard gate; Stage 8 resolves it against
    # the derived level timeline instead of guessing from route titles/subtitles.
    min_level = availability.get("min_level")
    if isinstance(min_level, int):
        record("min_level", "deferred", required=min_level, resolver="derived_xp")
        replay._deferred_gate(
            action_id=action_id,
            task_id=task_id,
            kind="min_level",
            required_min_level=min_level,
            resolver="derived_xp",
        )

    reputation = availability.get("required_reputation")
    if reputation is not None:
        record("reputation", "deferred", required=reputation, resolver="reputation_calibration")
        replay._deferred_gate(
            action_id=action_id,
            task_id=task_id,
            kind="reputation",
            required_reputation=reputation,
            resolver="reputation_calibration",
        )

    required_skill = list(availability.get("required_skill") or [])
    if required_skill:
        record("skill", "deferred", required=required_skill)
        replay._deferred_gate(
            action_id=action_id, task_id=task_id, kind="skill", required_skill=required_skill
        )

    hidden = list(availability.get("hidden_requirements") or [])
    for requirement in hidden:
        record("hidden_requirement", "deferred", requirement=requirement)
        replay._deferred_gate(
            action_id=action_id,
            task_id=task_id,
            kind="hidden_requirement",
            requirement=requirement,
        )

    # Questie may expose the same predecessor through preQuest* and parentQuest.
    # parent_active is the stronger action-time contract: the parent must still be active,
    # so an overlapping predecessor must not also be required to have been turned in.
    parent_active = [int(x) for x in availability.get("parent_active") or []]
    parent_active_set = set(parent_active)
    pre_all = [int(x) for x in availability.get("pre_all") or [] if int(x) not in parent_active_set]
    missing_pre_all: list[int] = []
    unknown_pre_all: list[int] = []
    for predecessor in pre_all:
        if predecessor in replay.completed_tasks:
            continue
        if predecessor in replay.maybe_completed_tasks:
            replay._deferred_gate(
                action_id=action_id,
                task_id=task_id,
                kind="pre_all_maybe_completed",
                predecessor_task_id=predecessor,
            )
            continue
        if not replay.completed_tasks_known:
            unknown_pre_all.append(predecessor)
            replay._external_requirement(
                action_id=action_id,
                task_id=task_id,
                kind="completed_task",
                required_task_id=predecessor,
                relation="pre_all",
            )
            continue
        missing_pre_all.append(predecessor)
    if missing_pre_all:
        record("pre_all", "fail", missing=missing_pre_all)
        replay._error(
            action_id=action_id,
            task_id=task_id,
            kind="pre_all_not_completed_before_accept",
            missing_task_ids=missing_pre_all,
        )
    elif unknown_pre_all:
        record("pre_all", "required_external_state", task_ids=unknown_pre_all)
    elif pre_all:
        record("pre_all", "pass", task_ids=pre_all)

    pre_any = [int(x) for x in availability.get("pre_any") or [] if int(x) not in parent_active_set]
    if pre_any:
        if any(predecessor in replay.completed_tasks for predecessor in pre_any):
            record("pre_any", "pass", task_ids=pre_any)
        elif any(predecessor in replay.maybe_completed_tasks for predecessor in pre_any):
            record("pre_any", "deferred", task_ids=pre_any)
            replay._deferred_gate(
                action_id=action_id, task_id=task_id, kind="pre_any_maybe_completed", task_ids=pre_any
            )
        elif not replay.completed_tasks_known:
            record("pre_any", "required_external_state", task_ids=pre_any)
            replay._external_requirement(
                action_id=action_id,
                task_id=task_id,
                kind="any_completed_task",
                required_task_ids=pre_any,
                relation="pre_any",
            )
        else:
            record("pre_any", "fail", missing=pre_any)
            replay._error(
                action_id=action_id,
                task_id=task_id,
                kind="pre_any_not_completed_before_accept",
                candidate_task_ids=pre_any,
            )

    missing_active: list[int] = []
    unknown_active: list[int] = []
    for parent_task_id in parent_active:
        if parent_task_id in replay.active_tasks:
            continue
        if parent_task_id in replay.maybe_active_tasks:
            replay._deferred_gate(
                action_id=action_id,
                task_id=task_id,
                kind="parent_maybe_active",
                parent_task_id=parent_task_id,
            )
            continue
        if not replay.active_tasks_known:
            unknown_active.append(parent_task_id)
            replay._external_requirement(
                action_id=action_id,
                task_id=task_id,
                kind="active_task",
                required_task_id=parent_task_id,
                relation="parent_active",
            )
            replay.active_tasks.add(parent_task_id)
            continue
        missing_active.append(parent_task_id)
    if missing_active:
        record("parent_active", "fail", missing=missing_active)
        replay._error(
            action_id=action_id,
            task_id=task_id,
            kind="parent_not_active_at_accept",
            missing_task_ids=missing_active,
        )
    elif unknown_active:
        record("parent_active", "required_external_state", task_ids=unknown_active)
    elif parent_active:
        record("parent_active", "pass_or_deferred", task_ids=parent_active)

    exclusive_with = [int(x) for x in availability.get("exclusive_with") or []]
    conflicts = [
        other
        for other in exclusive_with
        if other in replay.active_tasks or other in replay.completed_tasks
    ]
    maybe_conflicts = [
        other
        for other in exclusive_with
        if other in replay.maybe_active_tasks or other in replay.maybe_completed_tasks
    ]
    if conflicts:
        record("exclusive_with", "fail", conflicts=conflicts)
        replay._error(
            action_id=action_id,
            task_id=task_id,
            kind="exclusive_task_conflict",
            conflicting_task_ids=conflicts,
        )
    elif maybe_conflicts:
        record("exclusive_with", "deferred", possible_conflicts=maybe_conflicts)
        replay._deferred_gate(
            action_id=action_id,
            task_id=task_id,
            kind="exclusive_maybe_conflict",
            conflicting_task_ids=maybe_conflicts,
        )
    elif exclusive_with and (not replay.active_tasks_known or not replay.completed_tasks_known):
        record("exclusive_with", "required_external_state", must_be_absent=exclusive_with)
        replay._external_requirement(
            action_id=action_id,
            task_id=task_id,
            kind="absent_completed_or_active_tasks",
            required_absent_task_ids=exclusive_with,
            relation="exclusive_with",
        )
    elif exclusive_with:
        record("exclusive_with", "pass", task_ids=exclusive_with)

    if identity.get("repeatability") == "once" and task_id in replay.completed_tasks:
        replay._error(
            action_id=action_id,
            task_id=task_id,
            kind="accept_completed_once_task",
        )
        record("repeatability", "fail", value="once_already_completed")
    elif identity.get("repeatability") == "once" and not replay.completed_tasks_known:
        replay._deferred_gate(
            action_id=action_id,
            task_id=task_id,
            kind="once_task_entry_completion_unknown",
        )
        record("repeatability", "deferred", value="entry_completion_unknown")

    replay.availability_events.append(
        {
            "action_id": action_id,
            "task_id": task_id,
            "checks": checks,
        }
    )


def _apply_reputation_rewards(
    replay: RouteReplay,
    *,
    task_id: int,
    task_cards: dict[int, dict[str, Any]] | None,
    definite: bool,
) -> None:
    if task_cards is None:
        return
    card = task_cards.get(task_id)
    if card is None:
        return
    bucket = replay.reputation_reward_delta if definite else replay.maybe_reputation_reward_delta
    for reward in (card.get("rewards") or {}).get("reputation_rewards") or []:
        faction_id = int(reward["faction_id"])
        bucket[faction_id] = bucket.get(faction_id, 0) + int(reward["amount"])


def replay_state_from_contract(contract: dict[str, Any]) -> ReplayState:
    """Build an actual RouteState baseline (used by Route Program/CURRENT)."""

    return ReplayState(
        active_tasks={int(task_id) for task_id in contract.get("active_task_ids", [])},
        active_tasks_known="active_task_ids" in contract,
        completed_tasks={int(task_id) for task_id in contract.get("completed_task_ids", [])},
        completed_tasks_known="completed_task_ids" in contract,
        hearth_location=contract.get("hearth_location"),
        hearth_location_known="hearth_location" in contract,
        opened_flight_points={str(name) for name in contract.get("opened_flight_points", [])},
        opened_flight_points_known="opened_flight_points" in contract,
    )


def replay_state_from_requirements(requirements: dict[str, Any]) -> ReplayState:
    """Build the minimum known state for standalone Profile validation.

    Profile requirements are lower bounds, never a complete character snapshot.  In
    particular, an empty completed/flight list means "no requirement", not "known empty".
    """

    return ReplayState(
        active_tasks={int(task_id) for task_id in requirements.get("active_task_ids", [])},
        active_tasks_known=False,
        completed_tasks={int(task_id) for task_id in requirements.get("completed_task_ids", [])},
        completed_tasks_known=False,
        hearth_location=requirements.get("hearth_location"),
        hearth_location_known="hearth_location" in requirements,
        opened_flight_points={str(name) for name in requirements.get("opened_flight_points", [])},
        opened_flight_points_known=False,
    )


def replay_state_from_replay(replay: RouteReplay) -> ReplayState:
    return ReplayState(
        active_tasks=set(replay.active_tasks),
        maybe_active_tasks=set(replay.maybe_active_tasks),
        active_tasks_known=replay.active_tasks_known and not replay.maybe_active_tasks,
        completed_tasks=set(replay.completed_tasks),
        maybe_completed_tasks=set(replay.maybe_completed_tasks),
        completed_tasks_known=replay.completed_tasks_known and not replay.maybe_completed_tasks,
        hearth_location=replay.hearth_location,
        hearth_location_known=replay.hearth_location_known,
        opened_flight_points=set(replay.opened_flight_points),
        opened_flight_points_known=replay.opened_flight_points_known,
    )


def replay_route_profile(
    profile: dict[str, Any],
    *,
    task_cards: dict[int, dict[str, Any]] | None = None,
    character_profile: dict[str, Any] | None = None,
    entry_state: ReplayState | None = None,
) -> RouteReplay:
    """Replay deterministic route state and classify Availability at each accept action.

    Without ``task_cards`` this preserves the generic state-only mode used by low-level tests and
    diagnostics. With Task Cards + a Character Profile it becomes the Stage 3 evaluator: facts it
    can prove become pass/fail, previous-profile requirements become external-state requirements,
    and level/reputation/other unavailable dynamic inputs remain explicit deferred gates. Stage 4
    may provide ``entry_state`` when composing a Route Program; the state transition still happens
    only here, so continuity does not maintain a second replay implementation.
    """

    profile_id = str(profile["profile_id"])
    requirements = profile.get("entry_requirements") or {}
    initial = entry_state or replay_state_from_requirements(requirements)
    replay = RouteReplay(
        profile_id=profile_id,
        active_tasks=set(initial.active_tasks),
        maybe_active_tasks=set(initial.maybe_active_tasks),
        active_tasks_known=initial.active_tasks_known,
        entry_active_tasks_known=initial.active_tasks_known,
        completed_tasks=set(initial.completed_tasks),
        maybe_completed_tasks=set(initial.maybe_completed_tasks),
        completed_tasks_known=initial.completed_tasks_known,
        hearth_location=initial.hearth_location,
        entry_hearth_location_known=initial.hearth_location_known,
        hearth_location_known=initial.hearth_location_known,
        opened_flight_points=set(initial.opened_flight_points),
        opened_flight_points_known=initial.opened_flight_points_known,
    )
    replay.quest_log_peak_upper_bound = replay._quest_log_upper_bound()
    if not replay.active_tasks_known and any(action["kind"] == "accept" for action in profile["actions"]):
        replay.issues.append(
            {
                "severity": "requirement",
                "kind": "actual_entry_active_tasks_required",
                "reason": (
                    "Profile entry_requirements are minimum lower bounds; an actual entry RouteState "
                    "is required to prove duplicate-accept legality and quest-log capacity."
                ),
            }
        )

    for action in profile["actions"]:
        kind = str(action["kind"])
        action_id = str(action["action_id"])

        if kind == "accept":
            task_id = int(action["task_id"])
            if task_cards is not None:
                card = task_cards.get(task_id)
                if card is None:
                    replay._error(action_id=action_id, task_id=task_id, kind="missing_task_card")
                else:
                    _evaluate_accept_availability(
                        replay,
                        action=action,
                        task_card=card,
                        character_profile=character_profile,
                    )

            condition = action.get("when")
            if task_id in replay.active_tasks or task_id in replay.maybe_active_tasks:
                replay._error(action_id=action_id, task_id=task_id, kind="duplicate_accept")
            elif condition is None:
                replay.active_tasks.add(task_id)
                replay.action_execution[action_id] = "executed"
            elif condition.get("kind") == "has_item":
                replay.maybe_active_tasks.add(task_id)
                replay.action_execution[action_id] = "maybe"
            else:
                replay._error(
                    action_id=action_id,
                    task_id=task_id,
                    kind="unsupported_accept_condition",
                    condition=condition,
                )
                replay.action_execution[action_id] = "maybe"
            replay._record_quest_log(action)
            continue

        if kind == "objective":
            task_id = int(action["task_id"])
            replay.action_execution[action_id] = "executed"
            if task_id not in replay.active_tasks and task_id not in replay.maybe_active_tasks:
                if replay.active_tasks_known:
                    replay._error(action_id=action_id, task_id=task_id, kind="objective_for_inactive_task")
                else:
                    replay._external_requirement(
                        action_id=action_id,
                        task_id=task_id,
                        kind="active_task",
                        relation="objective_requires_active",
                    )
                    # A legal objective action proves the task is active from this point forward,
                    # while the rest of the entry task log remains unknown.
                    replay.active_tasks.add(task_id)
            continue

        if kind == "turnin":
            task_id = int(action["task_id"])
            condition = action.get("when")
            if condition is None:
                replay.action_execution[action_id] = "executed"
                if task_id in replay.active_tasks:
                    replay.active_tasks.remove(task_id)
                    replay.completed_tasks.add(task_id)
                    _apply_reputation_rewards(
                        replay, task_id=task_id, task_cards=task_cards, definite=True
                    )
                elif replay.active_tasks_known:
                    replay._error(action_id=action_id, task_id=task_id, kind="turnin_for_inactive_task")
                else:
                    replay._external_requirement(
                        action_id=action_id,
                        task_id=task_id,
                        kind="active_task",
                        relation="turnin_requires_active",
                    )
                    # A successful unconditional turn-in proves the task was active immediately before it.
                    replay.completed_tasks.add(task_id)
                    _apply_reputation_rewards(
                        replay, task_id=task_id, task_cards=task_cards, definite=True
                    )
            else:
                condition_kind = condition.get("kind")
                if condition_kind not in {"task_active", "task_complete"} or int(condition.get("task_id", -1)) != task_id:
                    replay._error(
                        action_id=action_id,
                        task_id=task_id,
                        kind="invalid_turnin_condition",
                        condition=condition,
                    )
                    replay.action_execution[action_id] = "maybe"
                elif condition_kind == "task_active":
                    if task_id in replay.active_tasks:
                        replay.active_tasks.remove(task_id)
                        replay.completed_tasks.add(task_id)
                        replay.action_execution[action_id] = "executed"
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=True
                        )
                    elif task_id in replay.maybe_active_tasks:
                        replay.maybe_active_tasks.remove(task_id)
                        replay.maybe_completed_tasks.add(task_id)
                        replay.action_execution[action_id] = "maybe"
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=False
                        )
                    elif replay.active_tasks_known:
                        replay.action_execution[action_id] = "skipped"
                    else:
                        # Unknown entry state: the task may have been absent (skip) or active (turn in).
                        replay.maybe_completed_tasks.add(task_id)
                        replay.action_execution[action_id] = "maybe"
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=False
                        )
                else:  # task_complete
                    # Replay owns task active/completed-history state, but it does not invent objective
                    # completion. Therefore task_complete is a real execution branch unless a future
                    # upstream completion fact proves it. If incomplete, the task remains active; if
                    # complete, this action turns it in.
                    replay.action_execution[action_id] = "maybe"
                    if task_id in replay.active_tasks:
                        replay.active_tasks.remove(task_id)
                        replay.maybe_active_tasks.add(task_id)
                        replay.maybe_completed_tasks.add(task_id)
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=False
                        )
                    elif task_id in replay.maybe_active_tasks:
                        replay.maybe_completed_tasks.add(task_id)
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=False
                        )
                    elif replay.active_tasks_known:
                        replay.action_execution[action_id] = "skipped"
                    else:
                        replay.maybe_active_tasks.add(task_id)
                        replay.maybe_completed_tasks.add(task_id)
                        _apply_reputation_rewards(
                            replay, task_id=task_id, task_cards=task_cards, definite=False
                        )
            replay._record_quest_log(action)
            continue

        if kind == "bind_hearth":
            target = str(action["target_name"])
            replay.hearth_location = target
            replay.hearth_location_known = True
            replay.hearth_events.append(
                {"action_id": action_id, "kind": kind, "target": target, "status": "bound"}
            )
            continue

        if kind == "use_hearth":
            target = str(action["target_name"])
            if not replay.hearth_location_known:
                replay.required_entry_hearth_locations.add(target)
                replay.issues.append(
                    {
                        "severity": "requirement",
                        "kind": "missing_entry_hearth_contract",
                        "action_id": action_id,
                        "required_hearth_location": target,
                    }
                )
                # If this action is legal, using the hearth proves the pre-action bind target.
                replay.hearth_location = target
                replay.hearth_location_known = True
            elif replay.hearth_location is None:
                replay._error(
                    action_id=action_id,
                    kind="hearth_not_bound",
                    target=target,
                )
            elif replay.hearth_location != target:
                replay._error(
                    action_id=action_id,
                    kind="hearth_target_mismatch",
                    bound_hearth_location=replay.hearth_location,
                    target=target,
                )
            replay.hearth_events.append(
                {"action_id": action_id, "kind": kind, "target": target, "status": "used"}
            )
            continue

        if kind == "open_flight_point":
            target = str(action["target_name"])
            replay.opened_flight_points.add(target)
            replay.flight_events.append(
                {"action_id": action_id, "kind": kind, "flight_point": target}
            )
            continue

        if kind == "taxi":
            origin = str(action["from_name"])
            destination = str(action["to_name"])
            missing = [
                point
                for point in (origin, destination)
                if point not in replay.opened_flight_points
            ]
            if missing and replay.opened_flight_points_known:
                replay._error(
                    action_id=action_id,
                    kind="taxi_requires_unopened_flight_point",
                    missing_flight_points=missing,
                )
            elif missing:
                replay.required_entry_flight_points.update(missing)
            # A legal taxi use itself proves both endpoints are opened from this point onward.
            replay.opened_flight_points.update((origin, destination))
            replay.flight_events.append(
                {
                    "action_id": action_id,
                    "kind": kind,
                    "from": origin,
                    "to": destination,
                    "missing_entry_flight_points": missing,
                }
            )
            continue

    if replay.maybe_active_tasks or replay.maybe_completed_tasks:
        replay.issues.append(
            {
                "severity": "requirement",
                "kind": "conditional_task_exit_state_branch",
                "maybe_active_task_ids": sorted(replay.maybe_active_tasks),
                "maybe_completed_task_ids": sorted(replay.maybe_completed_tasks),
                "reason": (
                    "Conditional route actions leave more than one legitimate exit state. "
                    "Preserve the branch for downstream Program/Timing/Review instead of inventing one outcome."
                ),
            }
        )

    return replay


def replay_summary(replay: RouteReplay) -> dict[str, Any]:
    return {
        "profile_id": replay.profile_id,
        "task_state": {
            "entry_active_state_known": replay.entry_active_tasks_known,
            "final_active_state_known": replay.active_tasks_known and not replay.maybe_active_tasks,
            "final_active_task_ids": sorted(replay.active_tasks),
            "final_maybe_active_task_ids": sorted(replay.maybe_active_tasks),
            "known_completed_task_ids": sorted(replay.completed_tasks),
            "maybe_completed_task_ids": sorted(replay.maybe_completed_tasks),
            "entry_completed_state_known": replay.completed_tasks_known,
        },
        "quest_log": {
            "entry_state_known": replay.entry_active_tasks_known,
            "peak_upper_bound": replay.quest_log_peak_upper_bound,
            "final_active_task_ids": sorted(replay.active_tasks),
            "final_maybe_active_task_ids": sorted(replay.maybe_active_tasks),
        },
        "hearth": {
            "entry_state_known": replay.entry_hearth_location_known,
            "final_location": replay.hearth_location,
            "final_state_known": replay.hearth_location_known,
            "required_entry_locations": sorted(replay.required_entry_hearth_locations),
            "events": replay.hearth_events,
        },
        "flight": {
            "entry_state_known": replay.opened_flight_points_known,
            "required_entry_flight_points": sorted(replay.required_entry_flight_points),
            "guaranteed_opened_by_exit": sorted(replay.opened_flight_points),
            "events": replay.flight_events,
        },
        "availability": {
            "events": replay.availability_events,
            "external_state_requirements": replay.external_state_requirements,
            "deferred_gates": replay.deferred_gates,
        },
        "action_execution": dict(sorted(replay.action_execution.items())),
        "reputation": {
            "definite_task_reward_delta": {
                str(faction_id): amount for faction_id, amount in sorted(replay.reputation_reward_delta.items())
            },
            "possible_task_reward_delta": {
                str(faction_id): amount
                for faction_id, amount in sorted(replay.maybe_reputation_reward_delta.items())
            },
        },
        "issues": replay.issues,
    }
