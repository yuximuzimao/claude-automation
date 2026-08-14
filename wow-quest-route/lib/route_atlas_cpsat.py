from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Iterable

from ortools.sat.python import cp_model


TIME_SCALE = 1000  # milliseconds; keeps travel/service comparisons effectively in seconds.


@dataclass(frozen=True)
class ActionCandidate:
    id: str
    name: str
    kind: str
    x: float
    y: float
    service_seconds: float
    quest_ids: tuple[int, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    pre_accept_quest_ids: tuple[int, ...] = ()
    entity_kind: str | None = None
    entity_id: int | None = None


@dataclass(frozen=True)
class GlobalQuest:
    id: int
    name: str
    accept_actions: tuple[str, ...]
    turnin_actions: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    pre_accept_requirement_ids: tuple[str, ...] = ()
    pre_any: tuple[int, ...] = ()
    pre_all: tuple[int, ...] = ()


@dataclass
class GlobalInstance:
    actions: dict[str, ActionCandidate]
    quests: dict[int, GlobalQuest]
    requirement_actions: dict[str, tuple[str, ...]]
    accept_trigger_actions: dict[str, tuple[str, ...]]
    start_xy: tuple[float, float]
    map_width_yards: float
    map_height_yards: float
    travel_speed_yards_per_sec: float
    meta: dict[str, Any]


@dataclass
class CpSatResult:
    status: str
    cp_status: str
    objective_seconds: float | None
    best_bound_seconds: float | None
    relative_gap: float | None
    travel_seconds: float | None
    service_seconds: float | None
    wall_time_seconds: float
    branches: int
    conflicts: int
    route: list[dict[str, Any]]
    selected_actions: list[str]


def _rounded_point(value: Iterable[float]) -> tuple[float, float]:
    row = list(value)
    return (round(float(row[0]), 4), round(float(row[1]), 4))


def _travel_seconds(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    map_width_yards: float,
    map_height_yards: float,
    speed: float,
) -> float:
    dx = (b[0] - a[0]) / 100.0 * map_width_yards
    dy = (b[1] - a[1]) / 100.0 * map_height_yards
    return math.hypot(dx, dy) / speed


def _component_source_records(
    qid: int,
    component: dict[str, Any],
    audited_component: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return service-source records for one logical requirement.

    Multi-object collection components already have an aggregate duration based on all spawn
    points. Treat them as one aggregate service region at the materialized baseline point; using
    individual object aliases as if each alias alone supplied the whole pool would be wrong.
    """
    req_id = str(component["id"])
    family = component.get("family")
    if family == "object_collect_multi":
        point = component.get("baseline_point") or (component.get("baseline_source") or {}).get("representative_point")
        seconds = component.get("estimated_objective_seconds")
        if point is None or not isinstance(seconds, (int, float)):
            return []
        return [{
            "service_key": ("aggregate", req_id),
            "requirement_id": req_id,
            "quest_id": qid,
            "name": component.get("label") or req_id,
            "kind": "aggregate_object_region",
            "entity_id": None,
            "point": _rounded_point(point),
            "seconds": float(seconds),
        }]

    records: list[dict[str, Any]] = []
    for source in audited_component.get("usable_sources") or []:
        if source.get("shortcut"):
            continue
        point = source.get("point")
        seconds = source.get("service_seconds")
        if point is None or not isinstance(seconds, (int, float)):
            continue
        kind = str(source.get("kind") or "service")
        entity_id = source.get("entity_id")
        # Same resolved entity + same representative point is one physical service stream.
        if entity_id is None:
            service_key: tuple[Any, ...] = (kind, req_id, *_rounded_point(point))
        else:
            service_key = (kind, int(entity_id), *_rounded_point(point))
        records.append({
            "service_key": service_key,
            "requirement_id": req_id,
            "quest_id": qid,
            "name": source.get("name") or component.get("label") or req_id,
            "kind": kind,
            "entity_id": int(entity_id) if entity_id is not None else None,
            "point": _rounded_point(point),
            "seconds": float(seconds),
        })
    return records


def build_instance_from_materialized_data(
    atlas: dict[str, Any],
    profiles: dict[str, Any],
    audit: dict[str, Any],
    quest_ids: Iterable[int],
    *,
    start_xy: tuple[float, float],
    instance_name: str,
    assume_external_prerequisites_satisfied: bool = False,
) -> GlobalInstance:
    selected = tuple(sorted({int(q) for q in quest_ids}))
    selected_set = set(selected)
    actions: dict[str, ActionCandidate] = {}
    quests: dict[int, GlobalQuest] = {}
    requirement_actions: dict[str, list[str]] = {}
    accept_trigger_source_key: dict[str, tuple[Any, ...]] = {}

    # Collect primitive service-source records first. Later we enumerate small shared-service
    # subsets for sources that are physically the same entity/point.
    source_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

    for qid in selected:
        qtext = str(qid)
        qrow = atlas["quests"][qtext]
        profile = profiles["quests"][qtext]
        audited = audit["quests"][qtext]
        if audited.get("hard_blocker"):
            raise ValueError(f"Quest {qid} is a hard blocker in solver-input audit: {audited.get('issues')}")

        accept_ids: list[str] = []
        pre_accept_req_ids: list[str] = []
        for index, loc in enumerate(audited.get("local_starts") or [], 1):
            point = loc.get("representative_point")
            if point is None:
                continue
            aid = f"A:{qid}:{index}"
            actions[aid] = ActionCandidate(
                id=aid,
                name=f"接 {qid}《{profile.get('name')}》 @ {loc.get('name')}",
                kind="ACCEPT",
                x=float(point[0]),
                y=float(point[1]),
                service_seconds=0.0,
                quest_ids=(qid,),
                entity_kind=loc.get("kind"),
                entity_id=int(loc["id"]),
            )
            accept_ids.append(aid)

        # Item-start quests have no NPC/Object accept location. The dropped item is a real
        # pre-accept service requirement G(Q); looting/using it creates A(Q) at the same point.
        # G(Q) is kept in the shared-service pool so the same kills can progress another quest.
        if not accept_ids:
            acquisition = audited.get("start_acquisition") or {}
            acquisition_sources = acquisition.get("sources") or []
            if acquisition_sources:
                start_req_id = f"q{qid}:start_acquisition"
                pre_accept_req_ids.append(start_req_id)
                requirement_actions.setdefault(start_req_id, [])
                for index, source in enumerate(acquisition_sources, 1):
                    point = source.get("point")
                    seconds = source.get("expected_service_seconds")
                    if not (
                        isinstance(point, list)
                        and len(point) >= 2
                        and isinstance(seconds, (int, float))
                    ):
                        continue
                    rounded = _rounded_point(point)
                    kind = str(source.get("kind") or "npc")
                    entity_id = source.get("entity_id")
                    service_key: tuple[Any, ...]
                    if entity_id is None:
                        service_key = (kind, start_req_id, *rounded)
                    else:
                        service_key = (kind, int(entity_id), *rounded)
                    aid = f"A:{qid}:item:{index}"
                    actions[aid] = ActionCandidate(
                        id=aid,
                        name=f"物品触发接取 {qid}《{profile.get('name')}》 @ {source.get('name')}",
                        kind="ACCEPT",
                        x=rounded[0],
                        y=rounded[1],
                        service_seconds=0.0,
                        quest_ids=(qid,),
                        entity_kind=kind,
                        entity_id=int(entity_id) if entity_id is not None else None,
                    )
                    accept_ids.append(aid)
                    accept_trigger_source_key[aid] = service_key
                    source_groups.setdefault(service_key, []).append({
                        "service_key": service_key,
                        "requirement_id": start_req_id,
                        "quest_id": qid,
                        "phase": "pre_accept",
                        "name": source.get("name") or acquisition.get("item_name") or start_req_id,
                        "kind": kind,
                        "entity_id": int(entity_id) if entity_id is not None else None,
                        "point": rounded,
                        "seconds": float(seconds),
                    })
        if not accept_ids:
            raise ValueError(f"Quest {qid} has no local or materialized item-start accept candidate")

        turnin_ids: list[str] = []
        for index, loc in enumerate(audited.get("local_finishes") or [], 1):
            point = loc.get("representative_point")
            if point is None:
                continue
            tid = f"T:{qid}:{index}"
            actions[tid] = ActionCandidate(
                id=tid,
                name=f"交 {qid}《{profile.get('name')}》 @ {loc.get('name')}",
                kind="TURNIN",
                x=float(point[0]),
                y=float(point[1]),
                service_seconds=0.0,
                quest_ids=(qid,),
                entity_kind=loc.get("kind"),
                entity_id=int(loc["id"]),
            )
            turnin_ids.append(tid)
        if not turnin_ids:
            raise ValueError(f"Quest {qid} has no local turn-in candidate")

        audited_components = {str(c.get("id")): c for c in audited.get("components") or []}
        req_ids: list[str] = []
        for component in profile.get("components") or []:
            req_id = str(component["id"])
            audited_component = audited_components.get(req_id)
            if not audited_component:
                raise ValueError(f"Quest {qid} component {req_id} missing from audit")
            records = _component_source_records(qid, component, audited_component)
            if not records:
                raise ValueError(f"Quest {qid} component {req_id} has no usable service record")
            req_ids.append(req_id)
            requirement_actions.setdefault(req_id, [])
            for record in records:
                source_groups.setdefault(tuple(record["service_key"]), []).append(record)

        # Special fixed-duration task with no ordinary component, currently As the Crow Flies.
        if not req_ids:
            effective_type = profile.get("classification", {}).get("effective_primary")
            effective_time = profile.get("effective_time_estimate") or {}
            fixed = effective_time.get("objective_seconds")
            if effective_type == "scripted_transport" and isinstance(fixed, (int, float)) and fixed > 0:
                req_id = f"q{qid}:fixed_script"
                req_ids.append(req_id)
                requirement_actions.setdefault(req_id, [])
                start_action = actions[accept_ids[0]]
                source_groups[("fixed_script", qid)] = [{
                    "service_key": ("fixed_script", qid),
                    "requirement_id": req_id,
                    "quest_id": qid,
                    "name": profile.get("name"),
                    "kind": "fixed_script",
                    "entity_id": None,
                    "point": (start_action.x, start_action.y),
                    "seconds": float(fixed),
                }]

        raw_any = tuple(int(v) for v in qrow.get("pre_quest_single") or [])
        raw_all = tuple(abs(int(v)) for v in qrow.get("pre_quest_group") or [])
        external_any = tuple(v for v in raw_any if v not in selected_set)
        external_all = tuple(v for v in raw_all if v not in selected_set)
        # In the first-run local-zone model, an external prerequisite is treated as a runtime
        # availability condition: if Questie shows the local quest, the external requirement is
        # already satisfied; otherwise the user skips it. Exact/closed instances keep strict mode.
        if assume_external_prerequisites_satisfied and external_any:
            pre_any = ()
        else:
            pre_any = tuple(v for v in raw_any if v in selected_set)
        pre_all = tuple(v for v in raw_all if v in selected_set)
        if not assume_external_prerequisites_satisfied:
            if raw_any and not pre_any:
                raise ValueError(f"Quest {qid} OR prerequisites fall outside selected instance: {raw_any}")
            if external_all:
                raise ValueError(f"Quest {qid} AND prerequisites fall outside selected instance: {external_all}")

        quests[qid] = GlobalQuest(
            id=qid,
            name=str(profile.get("name") or qrow.get("name") or qid),
            accept_actions=tuple(accept_ids),
            turnin_actions=tuple(turnin_ids),
            requirement_ids=tuple(req_ids),
            pre_accept_requirement_ids=tuple(pre_accept_req_ids),
            pre_any=pre_any,
            pre_all=pre_all,
        )

    # Create service actions. For each physical source, enumerate every non-empty subset of
    # distinct logical requirements using it. Maximum overlap in current Zangarmarsh data is
    # small, so this remains compact and gives the exact current shared-service semantics.
    accept_trigger_actions: dict[str, list[str]] = {
        aid: [] for aid in accept_trigger_source_key
    }
    for service_key, records in sorted(source_groups.items(), key=lambda kv: str(kv[0])):
        by_req: dict[str, dict[str, Any]] = {}
        for record in records:
            req_id = str(record["requirement_id"])
            previous = by_req.get(req_id)
            if previous is None or float(record["seconds"]) < float(previous["seconds"]):
                by_req[req_id] = record
        req_records = [by_req[k] for k in sorted(by_req)]
        for width in range(1, len(req_records) + 1):
            for subset in itertools.combinations(req_records, width):
                req_ids = tuple(sorted(str(r["requirement_id"]) for r in subset))
                qids = tuple(sorted({int(r["quest_id"]) for r in subset}))
                pre_accept_qids = tuple(sorted({
                    int(r["quest_id"])
                    for r in subset
                    if r.get("phase") == "pre_accept"
                }))
                exemplar = subset[0]
                suffix = "+".join(req_ids)
                sid = f"S:{str(service_key)}:{suffix}"
                seconds = max(float(r["seconds"]) for r in subset)
                point = exemplar["point"]
                actions[sid] = ActionCandidate(
                    id=sid,
                    name=str(exemplar.get("name") or service_key),
                    kind="SERVICE",
                    x=float(point[0]),
                    y=float(point[1]),
                    service_seconds=seconds,
                    quest_ids=qids,
                    requirement_ids=req_ids,
                    pre_accept_quest_ids=pre_accept_qids,
                    entity_kind=str(exemplar.get("kind") or "service"),
                    entity_id=exemplar.get("entity_id"),
                )
                for req_id in req_ids:
                    requirement_actions.setdefault(req_id, []).append(sid)
                for aid, trigger_key in accept_trigger_source_key.items():
                    if trigger_key != service_key:
                        continue
                    trigger_qid = actions[aid].quest_ids[0]
                    if trigger_qid in pre_accept_qids:
                        accept_trigger_actions[aid].append(sid)

    missing = [rid for rid, candidate_ids in requirement_actions.items() if not candidate_ids]
    if missing:
        raise ValueError(f"Requirements without service action candidates: {missing}")

    meta = profiles.get("meta") or {}
    return GlobalInstance(
        actions=actions,
        quests=quests,
        requirement_actions={k: tuple(v) for k, v in requirement_actions.items()},
        accept_trigger_actions={k: tuple(v) for k, v in accept_trigger_actions.items()},
        start_xy=(float(start_xy[0]), float(start_xy[1])),
        map_width_yards=float(meta["map_width_yards"]),
        map_height_yards=float(meta["map_height_yards"]),
        travel_speed_yards_per_sec=float(meta["travel_speed_yards_per_sec_assumption"]),
        meta={
            "name": instance_name,
            "quest_ids": list(selected),
            "time_scale": TIME_SCALE,
            "travel_model": meta.get("travel_model"),
            "kill_model": meta.get("kill_model"),
            "drop_model": meta.get("drop_model"),
        },
    )


class RouteAtlasCpSatSolver:
    def __init__(self, instance: GlobalInstance):
        self.instance = instance

    def solve(
        self,
        *,
        max_time_seconds: float = 60.0,
        num_workers: int = 8,
        log_search_progress: bool = False,
        initial_action_order: list[str] | None = None,
        objective_upper_bound_seconds: float | None = None,
    ) -> CpSatResult:
        inst = self.instance
        model = cp_model.CpModel()

        action_ids = sorted(inst.actions)
        start_id = "__START__"
        end_id = "__END__"
        node_ids = [start_id, *action_ids, end_id]
        node_index = {node_id: i for i, node_id in enumerate(node_ids)}
        max_pos = len(node_ids)

        selected: dict[str, cp_model.IntVar] = {}
        for node_id in node_ids:
            var = model.NewBoolVar(f"sel[{node_id}]")
            selected[node_id] = var
            if node_id in {start_id, end_id}:
                model.Add(var == 1)

        # Exactly one accept and turn-in action per quest.
        for q in inst.quests.values():
            model.Add(sum(selected[a] for a in q.accept_actions) == 1)
            model.Add(sum(selected[t] for t in q.turnin_actions) == 1)

        # Every logical objective requirement is covered exactly once. A selected shared-service
        # candidate can appear in several of these equations and therefore satisfies them jointly.
        for req_id, candidates in inst.requirement_actions.items():
            model.Add(sum(selected[a] for a in candidates) == 1)

        # Item-start accept candidates are tied to the selected pre-accept acquisition service
        # at the same physical source. Exact-cover guarantees exactly one start acquisition.
        for accept_id, trigger_services in inst.accept_trigger_actions.items():
            if not trigger_services:
                raise ValueError(f"Item-start accept action {accept_id} has no triggering service candidate")
            model.Add(selected[accept_id] == sum(selected[s] for s in trigger_services))

        # Position variables provide event order for precedence constraints.
        pos: dict[str, cp_model.IntVar] = {
            node_id: model.NewIntVar(0, max_pos, f"pos[{node_id}]") for node_id in node_ids
        }
        model.Add(pos[start_id] == 0)
        for action_id in action_ids:
            model.Add(pos[action_id] >= 1).OnlyEnforceIf(selected[action_id])
            model.Add(pos[action_id] == 0).OnlyEnforceIf(selected[action_id].Not())
        model.Add(pos[end_id] >= 1)
        # With START fixed at position 0 and every active arc increasing position by one,
        # END must be exactly one step after the last selected action. This tightens the rank
        # domain substantially compared with leaving END anywhere in the loose upper bound.
        model.Add(pos[end_id] == 1 + sum(selected[a] for a in action_ids))
        for action_id in action_ids:
            model.Add(pos[action_id] < pos[end_id]).OnlyEnforceIf(selected[action_id])

        # Build unconditional action-level precedence. Besides the explicit A->Objective->T
        # relations, an AND prerequisite (and an OR prerequisite with exactly one alternative)
        # makes every selected action of the predecessor quest occur before every selected
        # action of the successor quest. Its transitive closure is safe and lets us delete many
        # impossible reverse routing arcs before the circuit is built.
        action_lookup = inst.actions
        quest_actions: dict[int, set[str]] = {
            qid: {aid for aid, action in action_lookup.items() if qid in action.quest_ids}
            for qid in inst.quests
        }
        quest_before: set[tuple[int, int]] = set()
        for q in inst.quests.values():
            for predecessor in q.pre_all:
                quest_before.add((predecessor, q.id))
            if len(q.pre_any) == 1:
                quest_before.add((q.pre_any[0], q.id))
        changed = True
        while changed:
            changed = False
            additions: set[tuple[int, int]] = set()
            for a, b in quest_before:
                for c, d in quest_before:
                    if b == c and a != d and (a, d) not in quest_before:
                        additions.add((a, d))
            if additions:
                quest_before.update(additions)
                changed = True

        must_before: set[tuple[str, str]] = set()
        for q in inst.quests.values():
            service_candidates = {
                action_id
                for req_id in q.requirement_ids
                for action_id in inst.requirement_actions[req_id]
                if q.id in action_lookup[action_id].quest_ids
            }
            pre_accept_services = {
                action_id
                for req_id in q.pre_accept_requirement_ids
                for action_id in inst.requirement_actions[req_id]
                if q.id in action_lookup[action_id].pre_accept_quest_ids
            }
            for sid in pre_accept_services:
                for aid in q.accept_actions:
                    must_before.add((sid, aid))
                for tid in q.turnin_actions:
                    must_before.add((sid, tid))
            for aid in q.accept_actions:
                for tid in q.turnin_actions:
                    must_before.add((aid, tid))
                for sid in service_candidates:
                    must_before.add((aid, sid))
            for sid in service_candidates:
                for tid in q.turnin_actions:
                    must_before.add((sid, tid))

        for before_q, after_q in quest_before:
            for left in quest_actions[before_q]:
                for right in quest_actions[after_q]:
                    if left == right:
                        # A single shared-service candidate cannot simultaneously lie before and
                        # after a mandatory quest boundary, so it is infeasible by construction.
                        model.Add(selected[left] == 0)
                    else:
                        must_before.add((left, right))

        for left, right in must_before:
            model.Add(pos[left] < pos[right]).OnlyEnforceIf([selected[left], selected[right]])

        # Single Hamiltonian path over selected action nodes, represented as a circuit with a
        # fixed zero-cost END -> START closing arc. Optional unselected nodes take self-loops.
        circuit_arcs: list[tuple[int, int, cp_model.IntVar]] = []
        arc_vars: dict[tuple[str, str], cp_model.IntVar] = {}
        for action_id in action_ids:
            circuit_arcs.append((node_index[action_id], node_index[action_id], selected[action_id].Not()))

        close = model.NewBoolVar("arc[END->START]")
        model.Add(close == 1)
        circuit_arcs.append((node_index[end_id], node_index[start_id], close))
        arc_vars[(end_id, start_id)] = close

        # Candidate directed arcs. No node except END may enter START; END has no outgoing arc
        # except the fixed closure, so the active circuit corresponds to START -> ... -> END.
        for i in node_ids:
            if i == end_id:
                continue
            for j in node_ids:
                if j == start_id or i == j:
                    continue
                if i in action_lookup and j in action_lookup and (j, i) in must_before:
                    # j is provably required before i, so the immediate reverse arc i->j
                    # can never belong to a feasible route.
                    continue
                arc = model.NewBoolVar(f"arc[{i}->{j}]")
                arc_vars[(i, j)] = arc
                circuit_arcs.append((node_index[i], node_index[j], arc))
                model.Add(arc <= selected[i])
                model.Add(arc <= selected[j])
                model.Add(pos[j] == pos[i] + 1).OnlyEnforceIf(arc)

        model.AddCircuit(circuit_arcs)

        # Quest-internal G(start item) -> A -> ordinary Objective -> T precedence.
        action_lookup = inst.actions
        for q in inst.quests.values():
            pre_accept_services = sorted({
                action_id
                for req_id in q.pre_accept_requirement_ids
                for action_id in inst.requirement_actions[req_id]
                if q.id in action_lookup[action_id].pre_accept_quest_ids
            })
            service_candidates = sorted({
                action_id
                for req_id in q.requirement_ids
                for action_id in inst.requirement_actions[req_id]
                if q.id in action_lookup[action_id].quest_ids
            })
            for sid in pre_accept_services:
                for aid in q.accept_actions:
                    model.Add(pos[sid] < pos[aid]).OnlyEnforceIf([selected[sid], selected[aid]])
            if service_candidates:
                for aid in q.accept_actions:
                    for sid in service_candidates:
                        model.Add(pos[aid] < pos[sid]).OnlyEnforceIf([selected[aid], selected[sid]])
                for sid in service_candidates:
                    for tid in q.turnin_actions:
                        model.Add(pos[sid] < pos[tid]).OnlyEnforceIf([selected[sid], selected[tid]])
            else:
                for aid in q.accept_actions:
                    for tid in q.turnin_actions:
                        model.Add(pos[aid] < pos[tid]).OnlyEnforceIf([selected[aid], selected[tid]])

        # Cross-quest prerequisites. AND means all predecessor turn-ins must precede acceptance.
        # OR uses witness literals: at least one predecessor is already turned in before A(Q).
        for q in inst.quests.values():
            for predecessor in q.pre_all:
                p = inst.quests[predecessor]
                for tid in p.turnin_actions:
                    for aid in q.accept_actions:
                        model.Add(pos[tid] < pos[aid]).OnlyEnforceIf([selected[tid], selected[aid]])
            if q.pre_any:
                witnesses: list[cp_model.IntVar] = []
                for predecessor in q.pre_any:
                    witness = model.NewBoolVar(f"or_witness[{predecessor}->{q.id}]")
                    witnesses.append(witness)
                    p = inst.quests[predecessor]
                    for tid in p.turnin_actions:
                        for aid in q.accept_actions:
                            model.Add(pos[tid] < pos[aid]).OnlyEnforceIf(
                                [witness, selected[tid], selected[aid]]
                            )
                model.Add(sum(witnesses) >= 1)

        # Integer objective in milliseconds.
        travel_terms: list[Any] = []
        service_terms: list[Any] = []
        travel_ms_by_arc: dict[tuple[str, str], int] = {}
        for (i, j), arc in arc_vars.items():
            if (i, j) == (end_id, start_id) or j == end_id:
                ms = 0
            else:
                from_xy = inst.start_xy if i == start_id else (action_lookup[i].x, action_lookup[i].y)
                to_xy = (action_lookup[j].x, action_lookup[j].y)
                seconds = _travel_seconds(
                    from_xy,
                    to_xy,
                    map_width_yards=inst.map_width_yards,
                    map_height_yards=inst.map_height_yards,
                    speed=inst.travel_speed_yards_per_sec,
                )
                ms = int(round(seconds * TIME_SCALE))
            travel_ms_by_arc[(i, j)] = ms
            if ms:
                travel_terms.append(ms * arc)

        for action_id, action in action_lookup.items():
            ms = int(round(float(action.service_seconds) * TIME_SCALE))
            if ms:
                service_terms.append(ms * selected[action_id])

        objective_expr = sum(travel_terms) + sum(service_terms)
        if objective_upper_bound_seconds is not None:
            upper_ms = int(math.floor(float(objective_upper_bound_seconds) * TIME_SCALE + 1e-9))
            model.Add(objective_expr <= upper_ms)
        model.Minimize(objective_expr)

        # A known feasible order is only a search hint / incumbent upper bound. It does not
        # alter the feasible set or the optimality proof. This is especially useful when a
        # smaller exact solver has already certified a sub-instance, as in our 8-quest regression.
        if initial_action_order:
            order = list(initial_action_order)
            if len(order) != len(set(order)):
                raise ValueError("initial_action_order contains duplicate action ids")
            unknown = [a for a in order if a not in action_lookup]
            if unknown:
                raise ValueError(f"initial_action_order contains unknown action ids: {unknown}")
            hinted_selected = set(order)
            for action_id in action_ids:
                model.AddHint(selected[action_id], 1 if action_id in hinted_selected else 0)
            model.AddHint(pos[start_id], 0)
            for index, action_id in enumerate(order, 1):
                model.AddHint(pos[action_id], index)
            model.AddHint(pos[end_id], len(order) + 1)
            hinted_arcs = {(end_id, start_id)}
            if order:
                hinted_arcs.add((start_id, order[0]))
                hinted_arcs.update(zip(order, order[1:]))
                hinted_arcs.add((order[-1], end_id))
            else:
                hinted_arcs.add((start_id, end_id))
            for edge, arc in arc_vars.items():
                model.AddHint(arc, 1 if edge in hinted_arcs else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(max_time_seconds)
        solver.parameters.num_search_workers = int(num_workers)
        solver.parameters.log_search_progress = bool(log_search_progress)
        status_code = solver.Solve(model)
        cp_status = solver.StatusName(status_code)

        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return CpSatResult(
                status="NO_SOLUTION" if status_code == cp_model.INFEASIBLE else "UNKNOWN",
                cp_status=cp_status,
                objective_seconds=None,
                best_bound_seconds=None,
                relative_gap=None,
                travel_seconds=None,
                service_seconds=None,
                wall_time_seconds=solver.WallTime(),
                branches=solver.NumBranches(),
                conflicts=solver.NumConflicts(),
                route=[],
                selected_actions=[],
            )

        objective_seconds = solver.ObjectiveValue() / TIME_SCALE
        best_bound_seconds = solver.BestObjectiveBound() / TIME_SCALE
        gap = 0.0 if objective_seconds <= 0 else max(0.0, (objective_seconds - best_bound_seconds) / objective_seconds)
        status = "PROVEN_OPTIMAL" if status_code == cp_model.OPTIMAL else "BEST_FOUND_WITH_GAP"

        selected_actions = [a for a in action_ids if solver.BooleanValue(selected[a])]
        next_node: dict[str, str] = {}
        for (i, j), arc in arc_vars.items():
            if solver.BooleanValue(arc):
                next_node[i] = j

        route: list[dict[str, Any]] = []
        travel_total = 0.0
        service_total = 0.0
        current = start_id
        safety = 0
        while current != end_id:
            safety += 1
            if safety > len(node_ids) + 2:
                raise RuntimeError("CP-SAT route reconstruction exceeded node count")
            nxt = next_node.get(current)
            if nxt is None:
                raise RuntimeError(f"No selected outgoing arc from {current}")
            travel_seconds = travel_ms_by_arc[(current, nxt)] / TIME_SCALE
            travel_total += travel_seconds
            if nxt == end_id:
                route.append({
                    "type": "END",
                    "from": current,
                    "travel_seconds": travel_seconds,
                })
                current = nxt
                continue
            action = action_lookup[nxt]
            service_seconds = int(round(action.service_seconds * TIME_SCALE)) / TIME_SCALE
            service_total += service_seconds
            route.append({
                "type": action.kind,
                "action_id": action.id,
                "name": action.name,
                "quest_ids": list(action.quest_ids),
                "requirement_ids": list(action.requirement_ids),
                "entity_kind": action.entity_kind,
                "entity_id": action.entity_id,
                "x": action.x,
                "y": action.y,
                "travel_seconds": travel_seconds,
                "service_seconds": service_seconds,
                "position": solver.Value(pos[nxt]),
            })
            current = nxt

        return CpSatResult(
            status=status,
            cp_status=cp_status,
            objective_seconds=objective_seconds,
            best_bound_seconds=best_bound_seconds,
            relative_gap=gap,
            travel_seconds=travel_total,
            service_seconds=service_total,
            wall_time_seconds=solver.WallTime(),
            branches=solver.NumBranches(),
            conflicts=solver.NumConflicts(),
            route=route,
            selected_actions=selected_actions,
        )
