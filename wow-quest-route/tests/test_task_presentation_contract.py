from __future__ import annotations

import copy

from lib.task_presentation import project_task_presentation


def _card(status: str = "pending") -> dict:
    return {
        "task_id": 1,
        "identity": {"name_zhcn": "测试任务"},
        "fivebox": {"status": status},
        "presentation": {},
    }


def test_fivebox_status_is_the_player_label_source() -> None:
    assert project_task_presentation(_card("shared"), profile_id="route-a")["badge"] == "shared"
    assert project_task_presentation(_card("not_shared"), profile_id="route-a")["badge"] == "not_shared"
    assert project_task_presentation(_card("sequential_loot"), profile_id="route-a")["badge"] == "sequential_loot"
    assert project_task_presentation(_card("special"), profile_id="route-a")["badge"] == "special"
    assert project_task_presentation(_card("not_applicable"), profile_id="route-a")["badge"] is None


def test_pending_is_only_a_fivebox_status() -> None:
    assert project_task_presentation(_card("pending"), profile_id="route-a")["pending"] is True
    assert project_task_presentation(_card("shared"), profile_id="route-a")["pending"] is False
    assert project_task_presentation(_card("special"), profile_id="route-a")["pending"] is False
    assert project_task_presentation(_card("not_applicable"), profile_id="route-a")["pending"] is False


def test_note_override_is_independent_from_fivebox_label_and_can_be_explicitly_empty() -> None:
    card = _card("shared")
    original_fivebox = copy.deepcopy(card["fivebox"])
    card["presentation"] = {
        "note_override": {
            "text": "",
            "scope": "route_profile:route-a",
            "source_ref": "user-confirmed",
            "reason": "标签已经足够，不需要额外备注",
        }
    }

    a = project_task_presentation(card, profile_id="route-a")
    b = project_task_presentation(card, profile_id="route-b")

    assert a["badge"] == "shared"
    assert a["note"] == ""
    assert a["note_override_applied"] is True
    assert b["badge"] == "shared"
    assert b["note"] is None
    assert card["fivebox"] == original_fivebox


def test_note_text_never_changes_machine_status() -> None:
    card = _card("not_shared")
    card["presentation"] = {
        "note_override": {
            "text": "这是一条人工备注，文字里即使出现共享二字也不能改机器状态。",
            "scope": "all",
            "source_ref": "user-confirmed",
            "reason": "contract test",
        }
    }
    projected = project_task_presentation(card, profile_id="route-a")
    assert projected["badge"] == "not_shared"
    assert projected["note"]


def test_migrated_note_projection_removes_self_name_process_wrapper_and_redundant_status() -> None:
    card = _card("shared")
    card["presentation"] = {
        "note_override": {
            "text": "【需要单独修正优化】《测试任务》地狱火半岛DK第二组实跑确认：任务进度共享。",
            "scope": "all",
            "source_ref": "migration",
            "reason": "fixture",
        }
    }
    projected = project_task_presentation(card, profile_id="route-a")
    assert projected["note"] == ""
    assert projected["badge"] == "shared"


def test_migrated_note_projection_keeps_only_execution_value() -> None:
    card = _card("not_shared")
    card["presentation"] = {
        "note_override": {
            "text": "《测试任务》：不共享：五号分别点击机关；机关约90秒刷新。",
            "scope": "all",
            "source_ref": "migration",
            "reason": "fixture",
        }
    }
    projected = project_task_presentation(card, profile_id="route-a")
    assert projected["note"] == "五号分别点击机关；机关约90秒刷新。"
    assert "《测试任务》" not in projected["note"]


def test_action_display_override_and_note_show_on_are_profile_scoped_presentation_only() -> None:
    card = _card("special")
    card["presentation"] = {
        "note_override": {
            "text": "接取阶段有特殊操作。",
            "scope": "route_profile:route-a",
            "source_ref": "fixture",
            "reason": "fixture",
            "show_on": ["accept"],
        },
        "action_display_override": {
            "suppress_kinds": ["accept"],
            "scope": "route_profile:route-a",
            "source_ref": "fixture",
            "reason": "fixture",
        },
    }
    a = project_task_presentation(card, profile_id="route-a")
    b = project_task_presentation(card, profile_id="route-b")
    assert a["note_show_on"] == ["accept"]
    assert a["suppress_action_kinds"] == ["accept"]
    assert b["note_show_on"] == []
    assert b["suppress_action_kinds"] == []
