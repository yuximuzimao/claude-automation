from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from lib.route_atlas_validation import QuestConstraint, quest_constraint_from_profile


@dataclass(frozen=True)
class ReputationBlockedQuest:
    quest_id: int
    faction_id: int
    required_value: int


@dataclass(frozen=True)
class ReputationUnlockEvent:
    faction_id: int
    threshold: int
    quest_id: int


@dataclass(frozen=True)
class ReputationExpiryRisk:
    faction_id: int
    threshold: int
    quest_id: int


class ReputationBlockedQueue:
    """Ordered library of quests blocked by requiredMinRep.

    The queue is intentionally event-driven. It never reorders all reputation-gated quests at once;
    callers ask for the next threshold or for quests newly unlocked by one reputation transition.
    """

    def __init__(self, blocked: Iterable[ReputationBlockedQuest]):
        self._blocked = tuple(
            sorted(blocked, key=lambda item: (item.faction_id, item.required_value, item.quest_id))
        )

    @classmethod
    def from_profiles(
        cls,
        profiles: Mapping[str, Mapping[str, object]],
        current_reputation: Mapping[int, int],
    ) -> "ReputationBlockedQueue":
        blocked: list[ReputationBlockedQuest] = []
        for profile in profiles.values():
            constraint = quest_constraint_from_profile(profile)
            if constraint.required_min_rep is None:
                continue
            faction_id, threshold = constraint.required_min_rep
            current = current_reputation.get(faction_id)
            if current is None or current < threshold:
                blocked.append(
                    ReputationBlockedQuest(
                        quest_id=constraint.quest_id,
                        faction_id=faction_id,
                        required_value=threshold,
                    )
                )
        return cls(blocked)

    def blocked_for_faction(self, faction_id: int) -> tuple[ReputationBlockedQuest, ...]:
        return tuple(item for item in self._blocked if item.faction_id == faction_id)

    def next_threshold(
        self,
        faction_id: int,
        current_value: int,
    ) -> tuple[int, tuple[int, ...]] | None:
        candidates = [
            item for item in self._blocked
            if item.faction_id == faction_id and item.required_value > current_value
        ]
        if not candidates:
            return None
        threshold = min(item.required_value for item in candidates)
        quest_ids = tuple(item.quest_id for item in candidates if item.required_value == threshold)
        return threshold, quest_ids

    def newly_unlocked(
        self,
        faction_id: int,
        before: int,
        after: int,
    ) -> tuple[ReputationUnlockEvent, ...]:
        """Return one event per newly unlocked quest, ordered low-threshold then stable quest id."""

        if after <= before:
            return ()
        events = [
            ReputationUnlockEvent(item.faction_id, item.required_value, item.quest_id)
            for item in self._blocked
            if item.faction_id == faction_id and before < item.required_value <= after
        ]
        return tuple(sorted(events, key=lambda event: (event.threshold, event.quest_id)))


def max_rep_expiry_risks(
    constraints: Iterable[QuestConstraint],
    faction_id: int,
    before: int,
    after: int,
    *,
    already_accepted: frozenset[int] = frozenset(),
    already_completed: frozenset[int] = frozenset(),
) -> tuple[ReputationExpiryRisk, ...]:
    """Find not-yet-accepted quests that would become unavailable after a reputation increase."""

    if after <= before:
        return ()
    risks: list[ReputationExpiryRisk] = []
    for constraint in constraints:
        if constraint.quest_id in already_accepted:
            continue
        if constraint.quest_id in already_completed and not constraint.repeatable:
            continue
        if constraint.required_max_rep is None:
            continue
        req_faction, threshold = constraint.required_max_rep
        if req_faction != faction_id:
            continue
        if before < threshold <= after:
            risks.append(
                ReputationExpiryRisk(
                    faction_id=faction_id,
                    threshold=threshold,
                    quest_id=constraint.quest_id,
                )
            )
    return tuple(sorted(risks, key=lambda risk: (risk.threshold, risk.quest_id)))
