from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ortools.linear_solver import pywraplp

from lib.route_atlas_cpsat import GlobalInstance, _travel_seconds


@dataclass
class MipResult:
    status: str
    solver_status: str
    objective_seconds: float | None
    best_bound_seconds: float | None
    relative_gap: float | None
    travel_seconds: float | None
    service_seconds: float | None
    wall_time_seconds: float
    iterations: int
    nodes: int
    route: list[dict[str, Any]]
    selected_actions: list[str]


def _mandatory_precedence(instance: GlobalInstance) -> tuple[set[tuple[str, str]], set[str]]:
    """Return action-level mandatory precedence pairs and impossible shared actions."""
    action_lookup = instance.actions
    quest_actions: dict[int, set[str]] = {
        qid: {aid for aid, action in action_lookup.items() if qid in action.quest_ids}
        for qid in instance.quests
    }

    quest_before: set[tuple[int, int]] = set()
    for q in instance.quests.values():
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
    impossible: set[str] = set()

    for q in instance.quests.values():
        service_candidates = {
            aid
            for rid in q.requirement_ids
            for aid in instance.requirement_actions[rid]
            if q.id in action_lookup[aid].quest_ids
        }
        pre_accept_services = {
            aid
            for rid in q.pre_accept_requirement_ids
            for aid in instance.requirement_actions[rid]
            if q.id in action_lookup[aid].pre_accept_quest_ids
        }
        for service in pre_accept_services:
            for accept in q.accept_actions:
                must_before.add((service, accept))
            for turnin in q.turnin_actions:
                must_before.add((service, turnin))
        for accept in q.accept_actions:
            for turnin in q.turnin_actions:
                must_before.add((accept, turnin))
            for service in service_candidates:
                must_before.add((accept, service))
        for service in service_candidates:
            for turnin in q.turnin_actions:
                must_before.add((service, turnin))

    for before_q, after_q in quest_before:
        for left in quest_actions[before_q]:
            for right in quest_actions[after_q]:
                if left == right:
                    impossible.add(left)
                else:
                    must_before.add((left, right))

    return must_before, impossible


class RouteAtlasMipSolver:
    """Exact MIP route formulation using SCIP through OR-Tools MPSolver.

    Binary action-selection variables choose one accept/turn-in and an exact cover of logical
    Objective requirements. Binary arc variables form a single START->...->END path. Continuous
    order variables eliminate subtours and encode event precedence. The objective is travel
    seconds plus materialized service seconds.
    """

    def __init__(self, instance: GlobalInstance):
        self.instance = instance

    def solve(
        self,
        *,
        max_time_seconds: float = 60.0,
        num_threads: int = 8,
        initial_action_order: list[str] | None = None,
        objective_upper_bound_seconds: float | None = None,
    ) -> MipResult:
        inst = self.instance
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if solver is None:
            raise RuntimeError("SCIP backend is unavailable")
        solver.SetTimeLimit(int(round(max_time_seconds * 1000)))
        if num_threads > 0:
            solver.SetNumThreads(int(num_threads))

        actions = inst.actions
        action_ids = sorted(actions)
        start_id = "__START__"
        end_id = "__END__"
        n = len(action_ids)
        big_m = n + 2
        inf = solver.infinity()

        selected = {aid: solver.BoolVar(f"sel[{aid}]") for aid in action_ids}

        # Exactly one accept and one turn-in per quest.
        for q in inst.quests.values():
            solver.Add(sum(selected[a] for a in q.accept_actions) == 1)
            solver.Add(sum(selected[t] for t in q.turnin_actions) == 1)

        # Exact cover of every logical Objective requirement. A shared-service action may appear
        # in several equations and satisfy those requirements jointly.
        for req_id, candidates in inst.requirement_actions.items():
            solver.Add(sum(selected[a] for a in candidates) == 1)
        for accept_id, trigger_services in inst.accept_trigger_actions.items():
            if not trigger_services:
                raise ValueError(f"Item-start accept action {accept_id} has no triggering service candidate")
            solver.Add(selected[accept_id] == sum(selected[s] for s in trigger_services))

        must_before, impossible = _mandatory_precedence(inst)
        for aid in impossible:
            solver.Add(selected[aid] == 0)

        # Directed path arcs. We omit any immediate reverse arc that contradicts a proven
        # mandatory action precedence.
        nodes_from = [start_id, *action_ids]
        nodes_to = [*action_ids, end_id]
        arcs: dict[tuple[str, str], pywraplp.Variable] = {}
        travel_cost: dict[tuple[str, str], float] = {}

        for i in nodes_from:
            for j in nodes_to:
                if i == j:
                    continue
                if i in actions and j in actions and (j, i) in must_before:
                    continue
                x = solver.BoolVar(f"arc[{i}->{j}]")
                arcs[(i, j)] = x
                if j == end_id:
                    cost = 0.0
                else:
                    from_xy = inst.start_xy if i == start_id else (actions[i].x, actions[i].y)
                    to_xy = (actions[j].x, actions[j].y)
                    cost = _travel_seconds(
                        from_xy,
                        to_xy,
                        map_width_yards=inst.map_width_yards,
                        map_height_yards=inst.map_height_yards,
                        speed=inst.travel_speed_yards_per_sec,
                    )
                travel_cost[(i, j)] = cost

        # START has one outgoing edge and no incoming edge; END has one incoming edge and no
        # outgoing edge. Every selected action has exactly one incoming and one outgoing edge.
        solver.Add(sum(x for (i, _), x in arcs.items() if i == start_id) == 1)
        solver.Add(sum(x for (_, j), x in arcs.items() if j == end_id) == 1)
        for aid in action_ids:
            incoming = [x for (i, j), x in arcs.items() if j == aid]
            outgoing = [x for (i, j), x in arcs.items() if i == aid]
            solver.Add(sum(incoming) == selected[aid])
            solver.Add(sum(outgoing) == selected[aid])

        # Continuous path ranks are sufficient for MTZ-style subtour elimination because arc
        # variables are binary. Unselected actions are fixed to rank zero.
        rank = {aid: solver.NumVar(0.0, float(big_m), f"rank[{aid}]") for aid in action_ids}
        end_rank = solver.NumVar(1.0, float(big_m), "rank[END]")
        selected_count = sum(selected.values())
        solver.Add(end_rank == selected_count + 1)
        for aid in action_ids:
            solver.Add(rank[aid] >= selected[aid])
            solver.Add(rank[aid] <= big_m * selected[aid])
            solver.Add(rank[aid] <= end_rank - selected[aid])

        # Every selected arc advances the rank by at least one. Together with path-flow balance,
        # this eliminates disconnected subtours.
        for (i, j), x in arcs.items():
            if j == end_id:
                if i == start_id:
                    solver.Add(end_rank >= 1 - big_m * (1 - x))
                else:
                    solver.Add(end_rank >= rank[i] + 1 - big_m * (1 - x))
            elif i == start_id:
                solver.Add(rank[j] >= 1 - big_m * (1 - x))
            else:
                solver.Add(rank[j] >= rank[i] + 1 - big_m * (1 - x))

        # Action-level hard precedence. Because optional alternatives may be unselected, the
        # constraint is relaxed unless both endpoints are active.
        for left, right in must_before:
            solver.Add(
                rank[right] >= rank[left] + 1 - big_m * (2 - selected[left] - selected[right])
            )

        # Multi-alternative OR prerequisites need a witness: at least one predecessor turn-in is
        # before the selected accept action. Single-alternative ORs are already in must_before.
        for q in inst.quests.values():
            if len(q.pre_any) <= 1:
                continue
            witnesses = []
            for predecessor in q.pre_any:
                w = solver.BoolVar(f"or_witness[{predecessor}->{q.id}]")
                witnesses.append(w)
                p = inst.quests[predecessor]
                for tid in p.turnin_actions:
                    for aid in q.accept_actions:
                        solver.Add(
                            rank[aid]
                            >= rank[tid]
                            + 1
                            - big_m * (3 - w - selected[tid] - selected[aid])
                        )
            solver.Add(sum(witnesses) >= 1)

        objective = solver.Objective()
        for edge, x in arcs.items():
            objective.SetCoefficient(x, travel_cost[edge])
        for aid, action in actions.items():
            objective.SetCoefficient(selected[aid], float(action.service_seconds))
        objective.SetMinimization()

        if objective_upper_bound_seconds is not None:
            upper = solver.Constraint(-inf, float(objective_upper_bound_seconds), "known_upper_bound")
            for edge, x in arcs.items():
                upper.SetCoefficient(x, travel_cost[edge])
            for aid, action in actions.items():
                upper.SetCoefficient(selected[aid], float(action.service_seconds))

        # Search hint only; it does not constrain the model.
        if initial_action_order:
            order = list(initial_action_order)
            if len(order) != len(set(order)):
                raise ValueError("initial_action_order contains duplicates")
            unknown = [a for a in order if a not in actions]
            if unknown:
                raise ValueError(f"Unknown action ids in hint: {unknown}")
            hinted = set(order)
            hint_vars: list[pywraplp.Variable] = []
            hint_values: list[float] = []
            for aid in action_ids:
                hint_vars.append(selected[aid])
                hint_values.append(1.0 if aid in hinted else 0.0)
                hint_vars.append(rank[aid])
                hint_values.append(float(order.index(aid) + 1) if aid in hinted else 0.0)
            hinted_edges: set[tuple[str, str]] = set()
            if order:
                hinted_edges.add((start_id, order[0]))
                hinted_edges.update(zip(order, order[1:]))
                hinted_edges.add((order[-1], end_id))
            else:
                hinted_edges.add((start_id, end_id))
            for edge, var in arcs.items():
                hint_vars.append(var)
                hint_values.append(1.0 if edge in hinted_edges else 0.0)
            solver.SetHint(hint_vars, hint_values)

        status_code = solver.Solve()
        status_names = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
            pywraplp.Solver.ABNORMAL: "ABNORMAL",
            pywraplp.Solver.MODEL_INVALID: "MODEL_INVALID",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
        }
        solver_status = status_names.get(status_code, str(status_code))
        wall_time_seconds = solver.WallTime() / 1000.0

        if status_code not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return MipResult(
                status="NO_SOLUTION" if status_code == pywraplp.Solver.INFEASIBLE else "UNKNOWN",
                solver_status=solver_status,
                objective_seconds=None,
                best_bound_seconds=None,
                relative_gap=None,
                travel_seconds=None,
                service_seconds=None,
                wall_time_seconds=wall_time_seconds,
                iterations=solver.Iterations(),
                nodes=solver.nodes(),
                route=[],
                selected_actions=[],
            )

        objective_seconds = objective.Value()
        best_bound_seconds = objective.BestBound()
        relative_gap = (
            0.0
            if objective_seconds <= 0
            else max(0.0, (objective_seconds - best_bound_seconds) / objective_seconds)
        )
        status = "PROVEN_OPTIMAL" if status_code == pywraplp.Solver.OPTIMAL else "BEST_FOUND_WITH_GAP"

        chosen = [aid for aid in action_ids if selected[aid].solution_value() > 0.5]
        next_node: dict[str, str] = {}
        for edge, var in arcs.items():
            if var.solution_value() > 0.5:
                next_node[edge[0]] = edge[1]

        route: list[dict[str, Any]] = []
        travel_total = 0.0
        service_total = 0.0
        current = start_id
        safety = 0
        while current != end_id:
            safety += 1
            if safety > len(action_ids) + 2:
                raise RuntimeError("MIP route reconstruction exceeded node count")
            nxt = next_node.get(current)
            if nxt is None:
                raise RuntimeError(f"No chosen outgoing arc from {current}")
            edge_travel = travel_cost[(current, nxt)]
            travel_total += edge_travel
            if nxt == end_id:
                route.append({"type": "END", "from": current, "travel_seconds": edge_travel})
                current = nxt
                continue
            action = actions[nxt]
            service_total += float(action.service_seconds)
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
                "travel_seconds": edge_travel,
                "service_seconds": float(action.service_seconds),
                "rank": rank[nxt].solution_value(),
            })
            current = nxt

        return MipResult(
            status=status,
            solver_status=solver_status,
            objective_seconds=objective_seconds,
            best_bound_seconds=best_bound_seconds,
            relative_gap=relative_gap,
            travel_seconds=travel_total,
            service_seconds=service_total,
            wall_time_seconds=wall_time_seconds,
            iterations=solver.Iterations(),
            nodes=solver.nodes(),
            route=route,
            selected_actions=chosen,
        )
