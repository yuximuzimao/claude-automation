from lib.route_atlas_cpsat import (
    ActionCandidate,
    GlobalInstance,
    GlobalQuest,
    RouteAtlasCpSatSolver,
)
from lib.route_atlas_initial_solution import build_greedy_feasible_order


def item_start_instance() -> GlobalInstance:
    actions = {
        "G": ActionCandidate(
            id="G",
            name="获取起始物",
            kind="SERVICE",
            x=1.0,
            y=0.0,
            service_seconds=10.0,
            quest_ids=(1,),
            requirement_ids=("q1:start",),
            pre_accept_quest_ids=(1,),
            entity_kind="npc",
            entity_id=100,
        ),
        "A": ActionCandidate(
            id="A",
            name="物品触发接任务",
            kind="ACCEPT",
            x=1.0,
            y=0.0,
            service_seconds=0.0,
            quest_ids=(1,),
            entity_kind="npc",
            entity_id=100,
        ),
        "T": ActionCandidate(
            id="T",
            name="交任务",
            kind="TURNIN",
            x=2.0,
            y=0.0,
            service_seconds=0.0,
            quest_ids=(1,),
            entity_kind="npc",
            entity_id=200,
        ),
    }
    return GlobalInstance(
        actions=actions,
        quests={
            1: GlobalQuest(
                id=1,
                name="Item Start",
                accept_actions=("A",),
                turnin_actions=("T",),
                requirement_ids=(),
                pre_accept_requirement_ids=("q1:start",),
            )
        },
        requirement_actions={"q1:start": ("G",)},
        accept_trigger_actions={"A": ("G",)},
        start_xy=(0.0, 0.0),
        map_width_yards=100.0,
        map_height_yards=100.0,
        travel_speed_yards_per_sec=1.0,
        meta={"name": "item-start-test"},
    )


def test_greedy_item_start_requires_acquisition_before_accept():
    result = build_greedy_feasible_order(item_start_instance())
    assert result.status == "FEASIBLE_HEURISTIC"
    assert result.action_order == ["G", "A", "T"]


def test_cpsat_item_start_proves_g_before_accept():
    result = RouteAtlasCpSatSolver(item_start_instance()).solve(
        max_time_seconds=5,
        num_workers=1,
        initial_action_order=["G", "A", "T"],
        objective_upper_bound_seconds=12.1,
    )
    assert result.status == "PROVEN_OPTIMAL"
    assert [row["action_id"] for row in result.route if row.get("action_id")] == ["G", "A", "T"]
    assert result.objective_seconds == 12.0
