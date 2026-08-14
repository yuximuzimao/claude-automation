from __future__ import annotations

from dataclasses import dataclass

from ortools.linear_solver import pywraplp

from lib.route_atlas_cpsat import GlobalInstance, _travel_seconds


@dataclass(frozen=True)
class LowerBoundResult:
    name: str
    status: str
    objective_seconds: float | None
    best_bound_seconds: float | None
    wall_time_seconds: float
    selected_actions: int


def service_only_lower_bound(instance: GlobalInstance, *, max_time_seconds: float = 10.0) -> LowerBoundResult:
    """Exact/valid lower bound obtained by dropping all movement and event-order constraints."""
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("SCIP backend unavailable")
    solver.SetTimeLimit(int(max_time_seconds * 1000))

    service_ids = [aid for aid, action in instance.actions.items() if action.kind == "SERVICE"]
    selected = {aid: solver.BoolVar(f"sel[{aid}]") for aid in service_ids}
    for req_id, candidates in instance.requirement_actions.items():
        solver.Add(sum(selected[aid] for aid in candidates) == 1)

    objective = solver.Objective()
    for aid in service_ids:
        objective.SetCoefficient(selected[aid], float(instance.actions[aid].service_seconds))
    objective.SetMinimization()
    status = solver.Solve()

    status_name = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }.get(status, str(status))
    has_solution = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)
    return LowerBoundResult(
        name="service_only",
        status=status_name,
        objective_seconds=objective.Value() if has_solution else None,
        best_bound_seconds=objective.BestBound() if has_solution else None,
        wall_time_seconds=solver.WallTime() / 1000.0,
        selected_actions=sum(1 for aid in service_ids if has_solution and selected[aid].solution_value() > 0.5),
    )


def disconnected_path_cover_lower_bound(
    instance: GlobalInstance,
    *,
    max_time_seconds: float = 30.0,
    num_threads: int = 8,
) -> LowerBoundResult:
    """Travel+service lower bound using an assignment/path-cover relaxation.

    It keeps exact action/source selection, all travel costs, START out-degree, END in-degree,
    and one predecessor/successor for every selected action. It deliberately drops connectivity,
    subtour elimination and event-order precedence, so disconnected cycles are allowed. Every
    feasible Route Atlas route is feasible in this relaxation; therefore its optimum (or SCIP
    best bound while solving it) is a mathematically valid lower bound on the full route.
    """
    inst = instance
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("SCIP backend unavailable")
    solver.SetTimeLimit(int(max_time_seconds * 1000))
    if num_threads > 0:
        solver.SetNumThreads(num_threads)

    action_ids = sorted(inst.actions)
    start_id = "__START__"
    end_id = "__END__"
    selected = {aid: solver.BoolVar(f"sel[{aid}]") for aid in action_ids}

    for quest in inst.quests.values():
        solver.Add(sum(selected[aid] for aid in quest.accept_actions) == 1)
        solver.Add(sum(selected[aid] for aid in quest.turnin_actions) == 1)
    for req_id, candidates in inst.requirement_actions.items():
        solver.Add(sum(selected[aid] for aid in candidates) == 1)
    for accept_id, trigger_services in inst.accept_trigger_actions.items():
        solver.Add(selected[accept_id] == sum(selected[aid] for aid in trigger_services))

    arcs: dict[tuple[str, str], pywraplp.Variable] = {}
    travel_cost: dict[tuple[str, str], float] = {}
    from_nodes = [start_id, *action_ids]
    to_nodes = [*action_ids, end_id]
    for left in from_nodes:
        for right in to_nodes:
            if left == right:
                continue
            var = solver.BoolVar(f"arc[{left}->{right}]")
            arcs[(left, right)] = var
            if right == end_id:
                seconds = 0.0
            else:
                left_xy = inst.start_xy if left == start_id else (inst.actions[left].x, inst.actions[left].y)
                right_xy = (inst.actions[right].x, inst.actions[right].y)
                seconds = _travel_seconds(
                    left_xy,
                    right_xy,
                    map_width_yards=inst.map_width_yards,
                    map_height_yards=inst.map_height_yards,
                    speed=inst.travel_speed_yards_per_sec,
                )
            travel_cost[(left, right)] = seconds

    solver.Add(sum(var for (left, _), var in arcs.items() if left == start_id) == 1)
    solver.Add(sum(var for (_, right), var in arcs.items() if right == end_id) == 1)
    for aid in action_ids:
        solver.Add(sum(var for (_, right), var in arcs.items() if right == aid) == selected[aid])
        solver.Add(sum(var for (left, _), var in arcs.items() if left == aid) == selected[aid])

    objective = solver.Objective()
    for edge, var in arcs.items():
        objective.SetCoefficient(var, travel_cost[edge])
    for aid, var in selected.items():
        objective.SetCoefficient(var, float(inst.actions[aid].service_seconds))
    objective.SetMinimization()

    status = solver.Solve()
    status_name = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }.get(status, str(status))
    has_solution = status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)
    return LowerBoundResult(
        name="disconnected_path_cover",
        status=status_name,
        objective_seconds=objective.Value() if has_solution else None,
        best_bound_seconds=objective.BestBound() if has_solution else None,
        wall_time_seconds=solver.WallTime() / 1000.0,
        selected_actions=sum(1 for aid in action_ids if has_solution and selected[aid].solution_value() > 0.5),
    )
