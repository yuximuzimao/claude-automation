from lib.route_atlas_exact import (
    ExactModel,
    ExactSolver,
    Location,
    QuestModel,
    Requirement,
    State,
    infer_requirement_count,
    infer_requirement_count_detail,
)


def test_infer_requirement_count_from_chinese_objective():
    quest = {"objective": "杀死卡塔鲁、8个暗泽先知、6个暗泽巫医。"}
    target = [{"name": "暗泽先知"}]
    assert infer_requirement_count(quest, target) == 8


def test_infer_requirement_count_handles_classifier_name_variant():
    quest = {"objective": "将10箱蘑菇交给赞加沼泽塞纳里奥岗哨的观察者莉萨奥。"}
    targets = [{"source_item_name": "一箱蘑菇", "name": "安葛洛什食魂者"}]
    detail = infer_requirement_count_detail(quest, targets)
    assert detail["value"] == 10
    assert detail["confidence"] == "high"


def test_infer_requirement_count_uses_unambiguous_suffix_alias():
    quest = {"objective": "收集4份巨蛾样本和4份邪恶巨蛾样本。"}
    targets = [{"source_item_name": "蛾子样本", "name": "巨蛾"}]
    detail = infer_requirement_count_detail(quest, targets)
    assert detail["value"] == 4
    assert detail["confidence"] in {"medium", "high"}


def test_exact_solver_obeys_chain_and_returns_to_unlock_next_quest():
    locations = {
        "START": Location("START", "start", 0, 0, "start"),
        "hub": Location("hub", "hub", 0, 0, "npc", 1),
        "east": Location("east", "east", 10, 0, "service", 101),
    }
    requirements = {
        "q1:r": Requirement("q1:r", 1, "r1", 1, ("east",), (101,)),
        "q2:r": Requirement("q2:r", 2, "r2", 1, ("east",), (101,)),
    }
    quests = {
        1: QuestModel(1, "Q1", ("hub",), ("hub",), ("q1:r",), (), ()),
        2: QuestModel(2, "Q2", ("hub",), ("hub",), ("q2:r",), (), (1,)),
    }
    model = ExactModel(locations, quests, requirements, "START", frozenset())
    result = ExactSolver(model).solve()
    assert result.status == "PROVEN_OPTIMAL"
    assert result.travel_cost == 40
    action_types = [a["type"] for a in result.route]
    assert action_types.count("ACCEPT") == 2
    assert action_types.count("SERVICE") == 2
    assert action_types.count("TURNIN") == 2


def test_shared_service_covers_two_requirements_once():
    locations = {
        "START": Location("START", "hub", 0, 0, "start"),
        "hub": Location("hub", "hub", 0, 0, "npc", 1),
        "mob": Location("mob", "mob", 5, 0, "service", 101),
    }
    requirements = {
        "q1:r": Requirement("q1:r", 1, "kill", 8, ("mob",), (101,)),
        "q2:r": Requirement("q2:r", 2, "drop", 10, ("mob",), (101,)),
    }
    quests = {
        1: QuestModel(1, "Q1", ("hub",), ("hub",), ("q1:r",), (), ()),
        2: QuestModel(2, "Q2", ("hub",), ("hub",), ("q2:r",), (), ()),
    }
    model = ExactModel(locations, quests, requirements, "START", frozenset(), service_weight=1.0)
    # Start coordinate and hub are distinct location IDs but zero movement apart.
    result = ExactSolver(model).solve()
    service_actions = [a for a in result.route if a["type"] == "SERVICE"]
    assert len(service_actions) == 1
    assert set(service_actions[0]["quests"]) == {1, 2}
    assert service_actions[0]["service_cost"] == 10
    assert result.travel_cost == 10
