from __future__ import annotations

import heapq
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    x: float
    y: float
    kind: str
    entity_id: int | None = None


@dataclass(frozen=True)
class Requirement:
    id: str
    quest_id: int
    label: str
    count: int
    service_locations: tuple[str, ...]
    service_entity_ids: tuple[int, ...]
    # Aligned with service_locations/service_entity_ids. Empty means the legacy
    # proxy rule (count * model.service_weight) should be used.
    service_cost_seconds: tuple[float, ...] = ()


@dataclass(frozen=True)
class QuestModel:
    id: int
    name: str
    accept_locations: tuple[str, ...]
    turnin_locations: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    pre_any: tuple[int, ...]
    pre_all: tuple[int, ...]


@dataclass
class ExactModel:
    locations: dict[str, Location]
    quests: dict[int, QuestModel]
    requirements: dict[str, Requirement]
    start_location: str
    initial_turned_in: frozenset[int]
    accept_turnin_cost: float = 0.0
    service_weight: float = 0.0
    # Default values preserve the legacy raw-coordinate metric used by v0/tests.
    # v1 supplies Zangarmarsh yard scales and mounted travel speed so every edge
    # is measured in seconds.
    x_units_to_yards: float = 1.0
    y_units_to_yards: float = 1.0
    travel_speed_yards_per_sec: float = 1.0


@dataclass(frozen=True)
class State:
    location: str
    accepted_mask: int
    requirement_mask: int
    turned_mask: int


@dataclass
class SolveResult:
    status: str
    total_cost: float
    travel_cost: float
    service_cost: float
    expanded_states: int
    route: list[dict[str, Any]]
    final_state: State


def euclidean(a: Location, b: Location) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def travel_cost_seconds(a: Location, b: Location, model: ExactModel) -> float:
    dx_yards = (b.x - a.x) * model.x_units_to_yards
    dy_yards = (b.y - a.y) * model.y_units_to_yards
    distance_yards = math.hypot(dx_yards, dy_yards)
    speed = model.travel_speed_yards_per_sec
    if speed <= 0:
        raise ValueError("travel_speed_yards_per_sec must be positive")
    return distance_yards / speed


def representative_point(points: Iterable[Iterable[float]]) -> tuple[float, float] | None:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if not pts:
        return None
    cx = sum(x for x, _ in pts) / len(pts)
    cy = sum(y for _, y in pts) / len(pts)
    return min(pts, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)


def _count_matches_before_name(text: str, name: str) -> list[int]:
    if not text or not name:
        return []
    # Chinese objective text typically looks like “8个暗泽先知” or “8份电鳗鱼片”.
    pattern = re.compile(r"(\d+)[^\d，。；;]{0,6}" + re.escape(name))
    return [int(m.group(1)) for m in pattern.finditer(text)]


def _normalized_requirement_names(name: str) -> list[tuple[str, str]]:
    """Return progressively weaker Chinese name aliases for count matching.

    The weaker suffix aliases are only accepted when every matching occurrence carries the
    same count. This catches Questie/text variants such as “一箱蘑菇” vs “10箱蘑菇” and
    “蛾子样本” vs “巨蛾样本” without silently picking one of conflicting numeric clauses.
    """
    clean = re.sub(r"^[一二三四五六七八九十两]+(?:个|只|份|枚|箱|块|株|簇|根|片|瓶|颗|张|件)?", "", name.strip())
    aliases: list[tuple[str, str]] = []
    if clean:
        aliases.append((clean, "normalized_name" if clean != name else "exact_name"))
    if len(clean) >= 2:
        for width in (4, 3, 2):
            if len(clean) > width:
                alias = clean[-width:]
                if alias not in [v for v, _ in aliases]:
                    aliases.append((alias, f"suffix_{width}"))
    return aliases


def infer_requirement_count_detail(quest: dict[str, Any], targets: list[dict[str, Any]]) -> dict[str, Any]:
    text = str(quest.get("objective") or "")
    candidate_names: list[tuple[str, str]] = []
    for target in targets:
        if target.get("source_item_name"):
            candidate_names.append((str(target["source_item_name"]), "source_item_name"))
    for target in targets:
        if target.get("name"):
            candidate_names.append((str(target["name"]), "target_name"))

    tried: list[dict[str, Any]] = []
    seen_aliases: set[str] = set()
    for original, origin in candidate_names:
        for alias, alias_kind in _normalized_requirement_names(original):
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)
            matches = _count_matches_before_name(text, alias)
            tried.append({"alias": alias, "origin": origin, "alias_kind": alias_kind, "matches": matches})
            if not matches:
                continue
            unique = sorted(set(matches))
            if len(unique) == 1:
                confidence = "high" if alias_kind in ("exact_name", "normalized_name") else "medium"
                return {
                    "value": unique[0],
                    "source": f"objective_text:{origin}:{alias_kind}",
                    "confidence": confidence,
                    "matched_alias": alias,
                    "matches": matches,
                    "tried": tried,
                }
            # Ambiguous suffix/name: do not guess from conflicting counts.
            return {
                "value": 1,
                "source": f"default_one_after_ambiguous:{origin}:{alias_kind}",
                "confidence": "low",
                "matched_alias": alias,
                "matches": matches,
                "tried": tried,
            }
    return {
        "value": 1,
        "source": "default_one_no_text_match",
        "confidence": "low",
        "matched_alias": None,
        "matches": [],
        "tried": tried,
    }


def infer_requirement_count(quest: dict[str, Any], targets: list[dict[str, Any]]) -> int:
    return int(infer_requirement_count_detail(quest, targets)["value"])


def build_compressed_model(
    data: dict[str, Any],
    quest_ids: list[int],
    *,
    start_xy: tuple[float, float],
    start_name: str = "START",
    initial_turned_in: Iterable[int] = (),
    service_weight: float = 0.0,
    accept_turnin_cost: float = 0.0,
    task_profiles: dict[str, Any] | None = None,
    x_units_to_yards: float = 1.0,
    y_units_to_yards: float = 1.0,
    travel_speed_yards_per_sec: float = 1.0,
) -> ExactModel:
    selected = set(quest_ids)
    npc_rows = {int(n["id"]): n for n in data.get("npcs", [])}
    locations: dict[str, Location] = {
        "START": Location("START", start_name, float(start_xy[0]), float(start_xy[1]), "start")
    }

    def ensure_npc_location(npc_id: int) -> str:
        loc_id = f"npc:{npc_id}"
        if loc_id in locations:
            return loc_id
        row = npc_rows.get(npc_id)
        if not row:
            raise ValueError(f"NPC {npc_id} has no local row")
        point = representative_point(row.get("spawns") or [])
        if point is None:
            raise ValueError(f"NPC {npc_id} has no local spawn")
        locations[loc_id] = Location(loc_id, str(row.get("name") or npc_id), point[0], point[1], "npc", npc_id)
        return loc_id

    requirements: dict[str, Requirement] = {}
    quests: dict[int, QuestModel] = {}
    profile_quests = (task_profiles or {}).get("quests", {}) if isinstance(task_profiles, dict) else {}

    def profile_component_for(qid: int, group_key: str) -> dict[str, Any] | None:
        profile = profile_quests.get(str(qid)) if isinstance(profile_quests, dict) else None
        if not isinstance(profile, dict):
            return None
        for component in profile.get("components") or []:
            if isinstance(component, dict) and component.get("requirement_key") == group_key:
                return component
        return None

    def profile_source_cost(component: dict[str, Any] | None, entity_id: int) -> tuple[float | None, bool]:
        """Return (seconds, skip_source).

        For mob-drop tasks the task layer already distinguishes ordinary baseline sources
        from one-off Boss/rare shortcut sources. Exact baseline routing must not turn those
        shortcuts into a task property, so low_density_shortcut sources are excluded here.
        """
        if not component:
            return None, False
        family = component.get("family")
        if family == "mob_drop":
            for source in component.get("sources") or []:
                if int(source.get("entity_id") or -1) != entity_id:
                    continue
                if source.get("low_density_shortcut"):
                    return None, True
                value = source.get("expected_service_seconds")
                return (float(value), False) if isinstance(value, (int, float)) else (None, False)
            return None, False
        value = component.get("estimated_objective_seconds")
        return (float(value), False) if isinstance(value, (int, float)) else (None, False)

    for qid in quest_ids:
        quest = data["quests"][str(qid)]
        if quest.get("missing"):
            raise ValueError(f"Quest {qid} missing")

        accept_locs: list[str] = []
        turnin_locs: list[str] = []
        for ref in quest.get("started_by") or []:
            if ref.get("kind") == "npcs":
                accept_locs.append(ensure_npc_location(int(ref["id"])))
        for ref in quest.get("finished_by") or []:
            if ref.get("kind") == "npcs":
                turnin_locs.append(ensure_npc_location(int(ref["id"])))
        if not accept_locs or not turnin_locs:
            raise ValueError(f"Quest {qid} needs NPC accept/turnin locations in exact v0")

        # Direct targets are separate requirements. Item-source targets sharing one source_item_id
        # are alternatives for one logical item requirement.
        groups: list[tuple[str, list[dict[str, Any]]]] = []
        item_groups: dict[int, list[dict[str, Any]]] = {}
        for target in quest.get("objective_targets") or []:
            kind = target.get("kind")
            if kind in ("item_npc", "item_object") and target.get("source_item_id") is not None:
                item_groups.setdefault(int(target["source_item_id"]), []).append(target)
            else:
                groups.append((f"entity:{target.get('kind')}:{target.get('entity_id')}", [target]))
        groups.extend((f"item:{item_id}", rows) for item_id, rows in sorted(item_groups.items()))

        req_ids: list[str] = []
        for group_key, targets in groups:
            count = infer_requirement_count(quest, targets)
            component = profile_component_for(qid, group_key)
            service_locs: list[str] = []
            entity_ids: list[int] = []
            service_costs: list[float] = []
            for target in targets:
                spawns = target.get("spawns") or []
                entity_id = int(target["entity_id"])
                profiled_cost, skip_source = profile_source_cost(component, entity_id)
                if skip_source:
                    continue
                # Legacy v0 fallback: before task-profile data existed, very sparse alternate
                # item sources were rejected by spawn capacity. When a materialized profile is
                # supplied, its explicit ordinary/shortcut classification is authoritative.
                if component is None and group_key.startswith("item:") and count > 1 and len(spawns) < count:
                    continue
                point = representative_point(spawns)
                if point is None:
                    continue
                if task_profiles is not None and profiled_cost is None:
                    # A seconds-based v1 model must not silently fall back to an abstract
                    # count-weight for one source. Missing cost data is a modeling error.
                    continue
                loc_id = f"service:{entity_id}"
                if loc_id not in locations:
                    locations[loc_id] = Location(
                        loc_id,
                        str(target.get("name") or entity_id),
                        point[0],
                        point[1],
                        "service",
                        entity_id,
                    )
                service_locs.append(loc_id)
                entity_ids.append(entity_id)
                if profiled_cost is not None:
                    service_costs.append(profiled_cost)
            if not service_locs:
                raise ValueError(f"Quest {qid} requirement {group_key} has no usable compressed service source")
            req_id = f"q{qid}:{group_key}"
            label = str(targets[0].get("source_item_name") or targets[0].get("name") or group_key)
            requirements[req_id] = Requirement(
                req_id,
                qid,
                label,
                count,
                tuple(service_locs),
                tuple(entity_ids),
                tuple(service_costs),
            )
            req_ids.append(req_id)

        # Special fixed-duration action with no ordinary Questie Objective, e.g.
        # 9718 As the Crow Flies. Without this synthetic requirement A/T at the
        # same NPC would collapse to zero time and the solver would turn it in instantly.
        if not req_ids and task_profiles is not None:
            profile = profile_quests.get(str(qid)) if isinstance(profile_quests, dict) else None
            manual = profile.get("manual_override") if isinstance(profile, dict) else None
            time_override = manual.get("time_override") if isinstance(manual, dict) else None
            fixed_seconds = time_override.get("result") if isinstance(time_override, dict) else None
            if isinstance(fixed_seconds, (int, float)) and fixed_seconds > 0:
                if not accept_locs:
                    raise ValueError(f"Quest {qid} fixed service requires an accept location")
                req_id = f"q{qid}:manual_fixed_service"
                synthetic_entity = -1_000_000 - qid
                requirements[req_id] = Requirement(
                    req_id,
                    qid,
                    str(profile.get("name") or quest.get("name") or qid),
                    1,
                    (accept_locs[0],),
                    (synthetic_entity,),
                    (float(fixed_seconds),),
                )
                req_ids.append(req_id)

        pre_any = tuple(int(v) for v in quest.get("pre_quest_single") or [])
        pre_all = tuple(abs(int(v)) for v in quest.get("pre_quest_group") or [])
        initial_set = set(int(v) for v in initial_turned_in)
        external_all_unsatisfied = [p for p in pre_all if p not in selected and p not in initial_set]
        if external_all_unsatisfied:
            raise ValueError(f"Quest {qid} has external AND prerequisites not declared complete: {external_all_unsatisfied}")
        if pre_any and not any(p in selected or p in initial_set for p in pre_any):
            raise ValueError(f"Quest {qid} has no satisfiable OR prerequisite inside the selected model: {pre_any}")

        quests[qid] = QuestModel(
            id=qid,
            name=str(quest.get("name") or qid),
            accept_locations=tuple(dict.fromkeys(accept_locs)),
            turnin_locations=tuple(dict.fromkeys(turnin_locs)),
            requirement_ids=tuple(req_ids),
            pre_any=pre_any,
            pre_all=pre_all,
        )

    return ExactModel(
        locations=locations,
        quests=quests,
        requirements=requirements,
        start_location="START",
        initial_turned_in=frozenset(int(v) for v in initial_turned_in),
        accept_turnin_cost=accept_turnin_cost,
        service_weight=service_weight,
        x_units_to_yards=x_units_to_yards,
        y_units_to_yards=y_units_to_yards,
        travel_speed_yards_per_sec=travel_speed_yards_per_sec,
    )


class ExactSolver:
    """Exact Dijkstra solver for the compressed deterministic Route Atlas v0 model.

    This proves optimality only for the supplied compressed model. Objective counts are
    represented as whole-requirement service costs, and movement uses the provided metric.
    """

    def __init__(self, model: ExactModel):
        self.model = model
        self.quest_ids = sorted(model.quests)
        self.quest_index = {qid: i for i, qid in enumerate(self.quest_ids)}
        self.req_ids = sorted(model.requirements)
        self.req_index = {rid: i for i, rid in enumerate(self.req_ids)}
        self.quest_req_mask: dict[int, int] = {}
        for qid, q in model.quests.items():
            mask = 0
            for rid in q.requirement_ids:
                mask |= 1 << self.req_index[rid]
            self.quest_req_mask[qid] = mask
        self.all_turned_mask = (1 << len(self.quest_ids)) - 1
        self.loc_ids = sorted(model.locations)
        self.move_cost = {
            (a, b): travel_cost_seconds(model.locations[a], model.locations[b], model)
            for a in self.loc_ids
            for b in self.loc_ids
        }
        self.service_entities_at_loc: dict[str, set[int]] = {loc: set() for loc in self.loc_ids}
        for rid, req in model.requirements.items():
            for loc, entity_id in zip(req.service_locations, req.service_entity_ids):
                self.service_entities_at_loc.setdefault(loc, set()).add(entity_id)

    def _turned(self, state: State, qid: int) -> bool:
        if qid in self.model.initial_turned_in:
            return True
        idx = self.quest_index.get(qid)
        return idx is not None and bool(state.turned_mask & (1 << idx))

    def _available(self, state: State, q: QuestModel) -> bool:
        if q.pre_any and not any(self._turned(state, p) for p in q.pre_any):
            return False
        if q.pre_all and not all(self._turned(state, p) for p in q.pre_all):
            return False
        return True

    def _closure(self, state: State) -> tuple[State, float, list[dict[str, Any]]]:
        accepted = state.accepted_mask
        turned = state.turned_mask
        cost = 0.0
        actions: list[dict[str, Any]] = []
        changed = True
        while changed:
            changed = False
            temp = State(state.location, accepted, state.requirement_mask, turned)
            for qid in self.quest_ids:
                q = self.model.quests[qid]
                bit = 1 << self.quest_index[qid]
                if not (accepted & bit) and not (turned & bit) and state.location in q.accept_locations and self._available(temp, q):
                    accepted |= bit
                    cost += self.model.accept_turnin_cost
                    actions.append({"type": "ACCEPT", "quest_id": qid, "quest": q.name, "location": state.location})
                    changed = True
                    temp = State(state.location, accepted, state.requirement_mask, turned)
                if (accepted & bit) and not (turned & bit):
                    req_mask = self.quest_req_mask[qid]
                    complete = (state.requirement_mask & req_mask) == req_mask
                    if complete and state.location in q.turnin_locations:
                        turned |= bit
                        cost += self.model.accept_turnin_cost
                        actions.append({"type": "TURNIN", "quest_id": qid, "quest": q.name, "location": state.location})
                        changed = True
                        temp = State(state.location, accepted, state.requirement_mask, turned)
        return State(state.location, accepted, state.requirement_mask, turned), cost, actions

    def _requirement_service_cost(self, req: Requirement, location: str, entity_id: int) -> float:
        if req.service_cost_seconds:
            for index, (loc, ent) in enumerate(zip(req.service_locations, req.service_entity_ids)):
                if loc == location and ent == entity_id:
                    if index >= len(req.service_cost_seconds):
                        break
                    value = req.service_cost_seconds[index]
                    if value < 0:
                        raise ValueError(f"Negative service cost for {req.id}")
                    return float(value)
            raise ValueError(f"No aligned service cost for {req.id} at {location}/{entity_id}")
        return float(req.count) * self.model.service_weight

    def _service_transitions(self, state: State) -> list[tuple[State, float, list[dict[str, Any]]]]:
        transitions: list[tuple[State, float, list[dict[str, Any]]]] = []
        for entity_id in sorted(self.service_entities_at_loc.get(state.location, set())):
            cover_mask = 0
            covered: list[Requirement] = []
            for rid in self.req_ids:
                req = self.model.requirements[rid]
                qbit = 1 << self.quest_index[req.quest_id]
                rbit = 1 << self.req_index[rid]
                if not (state.accepted_mask & qbit) or (state.requirement_mask & rbit):
                    continue
                if entity_id in req.service_entity_ids and state.location in req.service_locations:
                    cover_mask |= rbit
                    covered.append(req)
            if not cover_mask:
                continue
            # One physical kill/interaction stream may satisfy several already-accepted
            # requirements at once. They are therefore not additive: the shared service
            # block lasts until the slowest covered requirement is complete.
            requirement_costs = {
                req.id: self._requirement_service_cost(req, state.location, entity_id)
                for req in covered
            }
            service_cost = max(requirement_costs.values(), default=0.0)
            new_req = state.requirement_mask | cover_mask
            actions = [{
                "type": "SERVICE",
                "entity_id": entity_id,
                "entity": self.model.locations[state.location].name,
                "location": state.location,
                "requirements": [req.id for req in covered],
                "quests": [req.quest_id for req in covered],
                "counts": {req.id: req.count for req in covered},
                "requirement_service_costs": requirement_costs,
                "service_cost": service_cost,
            }]
            before_complete = {
                qid: (state.requirement_mask & self.quest_req_mask[qid]) == self.quest_req_mask[qid]
                for qid in self.quest_ids
            }
            after = State(state.location, state.accepted_mask, new_req, state.turned_mask)
            for qid in self.quest_ids:
                if not before_complete[qid] and (new_req & self.quest_req_mask[qid]) == self.quest_req_mask[qid]:
                    if state.accepted_mask & (1 << self.quest_index[qid]):
                        actions.append({"type": "COMPLETE", "quest_id": qid, "quest": self.model.quests[qid].name, "location": state.location})
            after, closure_cost, closure_actions = self._closure(after)
            transitions.append((after, service_cost + closure_cost, actions + closure_actions))
        return transitions

    def _transition_targets(self, state: State) -> list[str]:
        """Locations where at least one useful action is executable after moving now.

        Under the current complete metric travel model, visiting an inert location before
        its action becomes available cannot improve a route: direct travel later is never
        more expensive than detouring through that point. Removing those moves is therefore
        exact state-space pruning, not a heuristic approximation.
        """
        targets: set[str] = set()
        for qid in self.quest_ids:
            q = self.model.quests[qid]
            qbit = 1 << self.quest_index[qid]
            accepted = bool(state.accepted_mask & qbit)
            turned = bool(state.turned_mask & qbit)
            if not accepted and not turned and self._available(state, q):
                targets.update(q.accept_locations)
            if accepted and not turned:
                req_mask = self.quest_req_mask[qid]
                complete = (state.requirement_mask & req_mask) == req_mask
                if complete:
                    targets.update(q.turnin_locations)
        for rid in self.req_ids:
            req = self.model.requirements[rid]
            rbit = 1 << self.req_index[rid]
            qbit = 1 << self.quest_index[req.quest_id]
            if not (state.accepted_mask & qbit) or (state.requirement_mask & rbit):
                continue
            targets.update(req.service_locations)
        targets.discard(state.location)
        return sorted(targets)

    def solve(self) -> SolveResult:
        initial = State(self.model.start_location, 0, 0, 0)
        initial, initial_cost, initial_actions = self._closure(initial)
        dist: dict[State, float] = {initial: initial_cost}
        travel_paid: dict[State, float] = {initial: 0.0}
        service_paid: dict[State, float] = {initial: initial_cost}
        parent: dict[State, tuple[State | None, list[dict[str, Any]]]] = {initial: (None, initial_actions)}
        heap: list[tuple[float, int, State]] = [(initial_cost, 0, initial)]
        counter = 1
        expanded = 0
        goal: State | None = None

        while heap:
            cost, _, state = heapq.heappop(heap)
            if cost != dist.get(state):
                continue
            expanded += 1
            if state.turned_mask == self.all_turned_mask:
                goal = state
                break

            # Service at current location.
            for nxt, edge_cost, actions in self._service_transitions(state):
                new_cost = cost + edge_cost
                if new_cost + 1e-12 < dist.get(nxt, math.inf):
                    dist[nxt] = new_cost
                    travel_paid[nxt] = travel_paid[state]
                    service_paid[nxt] = service_paid[state] + edge_cost
                    parent[nxt] = (state, actions)
                    heapq.heappush(heap, (new_cost, counter, nxt)); counter += 1

            # Move only to locations that can currently or eventually host useful selected work.
            for loc_id in self.loc_ids:
                if loc_id == state.location:
                    continue
                move = self.move_cost[(state.location, loc_id)]
                moved = State(loc_id, state.accepted_mask, state.requirement_mask, state.turned_mask)
                moved, closure_cost, closure_actions = self._closure(moved)
                edge_cost = move + closure_cost
                new_cost = cost + edge_cost
                if new_cost + 1e-12 < dist.get(moved, math.inf):
                    dist[moved] = new_cost
                    travel_paid[moved] = travel_paid[state] + move
                    service_paid[moved] = service_paid[state] + closure_cost
                    actions = [{
                        "type": "MOVE",
                        "from": state.location,
                        "to": loc_id,
                        "distance": move,
                        "travel_cost": move,
                        "from_name": self.model.locations[state.location].name,
                        "to_name": self.model.locations[loc_id].name,
                    }] + closure_actions
                    parent[moved] = (state, actions)
                    heapq.heappush(heap, (new_cost, counter, moved)); counter += 1

        if goal is None:
            raise RuntimeError("No feasible route found")

        chunks: list[list[dict[str, Any]]] = []
        cursor: State | None = goal
        while cursor is not None:
            prev, actions = parent[cursor]
            if actions:
                chunks.append(actions)
            cursor = prev
        route = [action for chunk in reversed(chunks) for action in chunk]
        return SolveResult(
            status="PROVEN_OPTIMAL",
            total_cost=dist[goal],
            travel_cost=travel_paid[goal],
            service_cost=service_paid[goal],
            expanded_states=expanded,
            route=route,
            final_state=goal,
        )
