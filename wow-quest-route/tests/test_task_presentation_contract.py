from __future__ import annotations

import copy

from lib.task_presentation import project_task_presentation


def _card(status: str = "pending") -> dict:
    return {
        "task_id": 1,
        "identity": {"name_zhcn": "测试任务"},
        "fivebox": {
            "status": status,
            "stages": [
                {"stage_id": "a", "mode": "personal_progress"},
                {"stage_id": "b", "mode": "shared_progress"},
            ],
        },
        "verification": {"open_questions": []},
        "presentation": {},
    }


def test_fivebox_status_is_the_player_label_source() -> None:
    assert project_task_presentation(_card("shared"), profile_id="route-a")["badge"] == "shared"
    assert project_task_presentation(_card("not_shared"), profile_id="route-a")["badge"] == "not_shared"
    assert project_task_presentation(_card("sequential_loot"), profile_id="route-a")["badge"] == "sequential_loot"


def test_pending_is_a_fivebox_status_not_an_open_question_side_effect() -> None:
    card = _card("pending")
    card["verification"]["open_questions"] = []
    assert project_task_presentation(card, profile_id="route-a")["pending"] is True

    card = _card("shared")
    card["verification"]["open_questions"] = [
        {
            "question_id": "timing-only",
            "status": "unknown",
            "variable": "timing.sample",
            "close_condition": "collect sample",
        }
    ]
    assert project_task_presentation(card, profile_id="route-a")["pending"] is False


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
