from __future__ import annotations

import re

from lib.route_profiles import load_route_profile
from lib.route_publisher import build_route_payload, load_route_timing_model
from lib.task_cards import load_all_task_cards
from lib.task_presentation import DEFERRED_NOTE_OPTIMIZATION_MARKER, project_task_presentation
from scripts.migrate_hellfire_dk_route_profile import _migrate_actions


def test_legacy_entry_line_keeps_task_specific_npcs() -> None:
    route = {
        "labels": [],
        "points": [
            [
                87.35,
                49.78,
                "黑暗之门",
                "奥格瑞玛 → 精神谷传送门区 → 诅咒之地黑暗之门前；督军达图恩 → 接《跨越黑暗之门》 → 穿过黑暗之门进入外域；沃雷恩中将 → 交《跨越黑暗之门》 → 接《抵达外域》",
                "entry",
                "",
                "ride",
            ]
        ],
    }
    actions, _, _ = _migrate_actions(route, {"跨越黑暗之门": 9407, "抵达外域": 10120})
    task_actions = [action for action in actions if action.get("task_id")]
    assert [(a["task_id"], a["kind"], a.get("npc_name")) for a in task_actions] == [
        (9407, "accept", "督军达图恩"),
        (9407, "turnin", "沃雷恩中将"),
        (10120, "accept", "沃雷恩中将"),
    ]


def test_task_presentation_hides_deferred_note_marker_but_keeps_note_text() -> None:
    card = {
        "task_id": 1,
        "identity": {"name_zhcn": "测试任务"},
        "fivebox": {"status": "shared"},
        "presentation": {
            "note_override": {
                "text": f"{DEFERRED_NOTE_OPTIMIZATION_MARKER}需要以后精简，但玩家当前仍要看到正文。",
                "scope": "all",
            }
        },
    }
    projected = project_task_presentation(card, profile_id="test")
    assert DEFERRED_NOTE_OPTIMIZATION_MARKER not in projected["note"]
    assert "需要以后精简" in projected["note"]


def test_publisher_preserves_inherited_hearth_pending_timing_and_ui_labels() -> None:
    cards = {
        1: {
            "task_id": 1,
            "identity": {"name_zhcn": "测试任务"},
            "fivebox": {"status": "pending"},
            "presentation": {},
        }
    }
    profile = {
        "profile_id": "test-profile",
        "entry_requirements": {"active_task_ids": [], "hearth_location": "继承炉石点"},
        "display": {
            "order": 1,
            "title": "测试路线",
            "display_name": "测试路线",
            "subtitle": "",
            "footer": "",
            "map_image": "maps/test.jpg",
        },
        "actions": [
            {"action_id": "a1", "kind": "location", "location_ref": "p1"},
            {"action_id": "a2", "kind": "bind_hearth", "location_ref": "p1", "target_name": "新炉石点"},
            {"action_id": "a3", "kind": "accept", "task_id": 1, "location_ref": "p1", "npc_name": "测试NPC"},
            {"action_id": "a4", "kind": "objective", "task_id": 1, "location_ref": "p1"},
            {"action_id": "a5", "kind": "turnin", "task_id": 1, "location_ref": "p1", "npc_name": "测试NPC", "when": {"kind": "task_complete", "task_id": 1}},
        ],
        "step_groups": [
            {"step_id": "step-01", "title": "测试步骤", "summary": None, "action_ids": ["a1", "a2", "a3", "a4", "a5"]}
        ],
        "geometry": {
            "locations": {
                "p1": {"display_name": "真实路线点", "x": 50.0, "y": 50.0, "phase": "test", "transport": "fly"}
            }
        },
    }
    timing = {
        "profile_id": "test-profile",
        "display_badge": "炉石：继承炉石点-新炉石点\n预计总时间：待重算",
        "route": {"center_minutes": 0.0, "range_minutes": [0.0, 0.0]},
        "steps": {
            "step-01": {"center_minutes": None, "range_minutes": None, "include_in_total": True, "status": "pending_recalibration"}
        },
    }
    route_ui = {
        "profile_id": "test-profile",
        "map_labels": [{"x": 12.0, "y": 34.0, "display_name": "视觉标签"}],
    }
    route = build_route_payload(
        "test-profile",
        profile=profile,
        cards=cards,
        timing_model=timing,
        route_ui=route_ui,
    )
    assert route["hearthChain"] == ["继承炉石点", "新炉石点"]
    assert route["badge"] == timing["display_badge"]
    assert route["stepGroups"][0]["timing"] == {
        "centerMinutes": None,
        "rangeMinutes": None,
        "includeInTotal": True,
        "status": "pending_recalibration",
    }
    assert route["labels"] == [[12.0, 34.0, "视觉标签"]]
    assert route["points"][0][0:2] == [50.0, 50.0]
    assert "若已完成：测试NPC → 交《测试任务》" in route["points"][0][3]


def test_hellfire_candidate_publisher_projects_complete_profile_without_legacy_marker() -> None:
    cards = load_all_task_cards()
    profile = load_route_profile("hellfire-dk-speed", validate=True, validate_task_cards=False)
    route = build_route_payload(
        "hellfire-dk-speed",
        profile=profile,
        cards=cards,
        timing_model=load_route_timing_model("hellfire-dk-speed"),
    )
    assert len(route["points"]) == 63
    assert len(route["stepGroups"]) == 11
    assert len(route["labels"]) == 11
    assert route["hearthChain"] == ["萨尔玛"]
    assert route["timing"]["centerMinutes"] == 330.0
    assert DEFERRED_NOTE_OPTIMIZATION_MARKER not in str(route)
    assert "固定交通：奥格瑞玛·精神谷传送门区 → 诅咒之地·黑暗之门前" in route["points"][0][3]
    assert "督军达图恩" in route["points"][0][3]
    assert "固定交通：诅咒之地·黑暗之门 → 外域·黑暗之门" in route["points"][0][3]
    assert "沃雷恩中将" in route["points"][0][3]
    assert "陆路：塞纳里奥哨站 → 赞加沼泽·塞纳里奥庇护所" in route["points"][-1][3]

    name_to_id = {
        card["identity"]["name_zhcn"]: task_id
        for task_id, card in cards.items()
        if task_id in profile["task_ids"]
    }
    expected_task_actions = [
        (action["kind"], action["task_id"])
        for action in profile["actions"]
        if action["kind"] in {"accept", "objective", "turnin"}
    ]
    rendered_task_actions: list[tuple[str, int]] = []
    for point in route["points"]:
        for line in str(point[3]).splitlines():
            for match in re.finditer(r"(接|做|交)((?:《[^》]+》(?:、)?)+)", line):
                kind = {"接": "accept", "做": "objective", "交": "turnin"}[match.group(1)]
                for name in re.findall(r"《([^》]+)》", match.group(2)):
                    rendered_task_actions.append((kind, name_to_id[name]))
    assert rendered_task_actions == expected_task_actions
