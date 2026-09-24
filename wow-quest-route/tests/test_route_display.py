from __future__ import annotations

from copy import deepcopy

from lib.route_display import project_route_display, refresh_task_card_display


def _card(task_id: int, name: str, *, status: str = "shared", note: str | None = None) -> dict:
    presentation = {}
    if note is not None:
        presentation = {
            "note_override": {
                "text": note,
                "scope": "route_profile:display-fixture",
                "source_ref": "fixture",
                "reason": "fixture",
            }
        }
    return {
        "task_id": task_id,
        "identity": {"name_zhcn": name},
        "fivebox": {"status": status},
        "presentation": presentation,
    }


def _profile() -> dict:
    return {
        "profile_id": "display-fixture",
        "version": 2,
        "entry_requirements": {"active_task_ids": [], "hearth_location": "旧炉石点"},
        "display": {
            "publish_key": "display_fixture",
            "order": 1,
            "title": "展示测试路线",
            "display_name": "展示测试",
            "subtitle": "",
            "footer": "",
            "map_image": "maps/test.jpg",
        },
        "task_ids": [1, 2],
        "actions": [
            {"action_id": "a1", "kind": "location", "location_ref": "hub"},
            {"action_id": "a2", "kind": "accept", "task_id": 1, "location_ref": "hub", "npc_name": "测试NPC"},
            {"action_id": "a3", "kind": "accept", "task_id": 2, "location_ref": "hub", "npc_name": "测试NPC"},
            {"action_id": "a4", "kind": "objective", "task_id": 1, "location_ref": "field"},
            {"action_id": "a5", "kind": "objective", "task_id": 2, "location_ref": "field"},
            {"action_id": "a6", "kind": "location", "location_ref": "field"},
            {"action_id": "a7", "kind": "turnin", "task_id": 1, "location_ref": "field", "npc_name": "交任务NPC", "when": {"kind": "task_complete", "task_id": 1}},
            {"action_id": "a8", "kind": "taxi", "from_name": "起点", "to_name": "终点"},
        ],
        "step_groups": [
            {"step_id": "step-01", "title": "接任务", "summary": None, "action_ids": ["a1", "a2", "a3"]},
            {"step_id": "step-02", "title": "外出", "summary": "", "action_ids": ["a4", "a5", "a6", "a7", "a8"]},
        ],
        "geometry": {
            "locations": {
                "hub": {"display_name": "测试Hub", "x": 10.0, "y": 20.0},
                "field": {"display_name": "测试野外", "x": 30.0, "y": 40.0},
            }
        },
    }


def _cards() -> dict[int, dict]:
    return {
        1: _card(1, "任务甲", status="shared", note="必须先点任务物。"),
        2: _card(2, "任务乙", status="pending", note=""),
    }


def _movement(*, status: str = "pass") -> dict:
    return {
        "profile_id": "display-fixture",
        "status": status,
        "input_fingerprint": "movement-fixture-v1",
        "visits": [
            {
                "visit_id": "a1",
                "ordinal": 1,
                "location_ref": "hub",
                "display_name": "测试Hub",
                "x": 10.0,
                "y": 20.0,
            },
            {
                "visit_id": "a6",
                "ordinal": 2,
                "location_ref": "field",
                "display_name": "测试野外",
                "x": 30.0,
                "y": 40.0,
            },
        ],
        "edges": [
            {
                "edge_id": "a1->a6",
                "from_visit_id": "a1",
                "to_visit_id": "a6",
                "from_location_ref": "hub",
                "to_location_ref": "field",
                "operation_kind": "self_move",
                "movement_mode": "ride",
                "movement_action_id": None,
                "source": "canonical",
            }
        ],
    }


def _timing(*, complete: bool = True) -> dict:
    return {
        "profile_id": "display-fixture",
        "status": "pass" if complete else "requirements",
        "input_fingerprint": "timing-fixture-v1",
        "complete": complete,
        "center_minutes": 12.5 if complete else None,
        "range_minutes": [11.0, 14.0] if complete else None,
        "steps": [
            {
                "step_id": "step-01",
                "complete": True,
                "center_minutes": 3.0,
                "range_minutes": [2.5, 3.5],
            },
            {
                "step_id": "step-02",
                "complete": complete,
                "center_minutes": 9.5 if complete else None,
                "range_minutes": [8.5, 10.5] if complete else None,
            },
        ],
    }


def _upstream(status: str = "pass") -> dict[str, str]:
    return {
        "canonical_spatial_movement": status,
        "derived_timing": status,
        "review_trigger": status,
    }


def test_route_display_projects_structured_actions_without_html_or_legacy_text() -> None:
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    assert report["status"] == "pass"
    assert len(report["steps"]) == 2
    first = report["steps"][0]
    second = report["steps"][1]
    assert first["lines"][0] == {
        "type": "location",
        "text": "测试Hub",
        "location_ref": "hub",
        "action_ids": ["a1"],
        "task_refs": [],
    }
    assert first["lines"][1]["text"] == "测试NPC → 接《任务甲》、《任务乙》"
    assert second["lines"][0]["text"] == "↳ 做《任务甲》、《任务乙》"
    assert second["lines"][1]["text"] == "测试野外"
    assert second["lines"][2]["text"] == "若已完成：交任务NPC → 交《任务甲》"
    assert second["lines"][3]["text"] == "系统飞行：起点 → 终点"
    assert report["map_geometry"]["status"] == "pass"
    assert [row["visit_id"] for row in report["map_geometry"]["visits"]] == ["a1", "a6"]
    assert report["map_geometry"]["visits"][0]["step_id"] == "step-01"
    assert report["map_geometry"]["visits"][1]["step_id"] == "step-02"
    assert report["map_geometry"]["edges"][0]["operation_kind"] == "self_move"
    assert report["hearth_chain"] == ["旧炉石点"]
    assert "<div" not in str(report)
    assert "actionHtml" not in str(report)


def test_location_ending_with_same_npc_merges_without_repeating_npc() -> None:
    profile = _profile()
    profile["geometry"]["locations"]["hub"]["display_name"] = "测试区·测试NPC"
    report = project_route_display(
        profile,
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    first = report["steps"][0]
    assert first["lines"][0]["text"] == "测试区·测试NPC → 接《任务甲》、《任务乙》"
    assert first["lines"][0]["type"] == "task_action"
    assert first["lines"][0]["action_ids"] == ["a1", "a2", "a3"]
    assert len(first["lines"]) == 1


def test_plain_location_does_not_hide_distinct_npc_actions() -> None:
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    first = report["steps"][0]
    assert first["lines"][0]["text"] == "测试Hub"
    assert first["lines"][1]["text"] == "测试NPC → 接《任务甲》、《任务乙》"


def test_same_npc_consecutive_turnin_then_accept_renders_as_one_run() -> None:
    profile = _profile()
    profile["actions"][1] = {
        "action_id": "a2",
        "kind": "turnin",
        "task_id": 1,
        "location_ref": "hub",
        "npc_name": "测试NPC",
    }
    profile["actions"][2] = {
        "action_id": "a3",
        "kind": "accept",
        "task_id": 2,
        "location_ref": "hub",
        "npc_name": "测试NPC",
    }
    report = project_route_display(
        profile,
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    assert report["steps"][0]["lines"][1]["text"] == "测试NPC → 交《任务甲》 → 接《任务乙》"


def test_has_item_accept_condition_stays_machine_only_and_action_text_is_clean() -> None:
    profile = _profile()
    profile["actions"][1]["when"] = {"kind": "has_item", "item_name": "测试触发物"}
    report = project_route_display(
        profile,
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    assert report["steps"][0]["lines"][1]["text"] == "测试NPC → 接《任务甲》"
    assert report["steps"][0]["task_presentations"][0]["note"] == "必须先点任务物。"
    assert report["steps"][0]["task_presentations"][0]["note_visible"] is True


def test_task_presentation_is_attached_once_per_task_per_step_and_keeps_empty_note_distinct() -> None:
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    first_presentations = report["steps"][0]["task_presentations"]
    assert [row["task_id"] for row in first_presentations] == [1, 2]
    assert first_presentations[0]["badge"] == "shared"
    assert first_presentations[0]["note"] is None
    assert first_presentations[0]["note_visible"] is False
    assert first_presentations[1]["pending"] is True
    assert first_presentations[1]["note"] is None
    assert first_presentations[1]["note_visible"] is False
    assert first_presentations[1]["note_override_applied"] is True
    second_presentations = report["steps"][1]["task_presentations"]
    assert second_presentations[0]["note"] == "必须先点任务物。"
    assert second_presentations[0]["note_visible"] is True


def test_display_only_exposes_complete_current_timing_values() -> None:
    complete = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(complete=True),
        upstream_statuses=_upstream(),
    )
    assert complete["route_timing"]["center_minutes"] == 12.5
    assert complete["steps"][1]["timing"]["center_minutes"] == 9.5

    partial = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(complete=False),
        upstream_statuses={**_upstream(), "derived_timing": "requirements"},
    )
    assert partial["status"] == "pass"
    assert partial["route_timing"]["center_minutes"] is None
    assert partial["route_timing"]["range_minutes"] is None
    assert partial["steps"][0]["timing"]["center_minutes"] == 3.0
    assert partial["steps"][1]["timing"]["center_minutes"] is None


def test_non_display_upstream_block_does_not_block_static_projection() -> None:
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(complete=False),
        upstream_statuses={**_upstream(), "review_trigger": "blocked"},
    )
    assert report["status"] == "pass"
    assert report["steps"]
    assert "display_upstream_blocked" not in {issue["kind"] for issue in report["issues"]}


def test_blocked_movement_still_blocks_static_projection() -> None:
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(status="blocked"),
        timing_report=_timing(),
        upstream_statuses={**_upstream(), "canonical_spatial_movement": "blocked"},
    )
    assert report["status"] == "blocked"
    assert "display_upstream_blocked" in {issue["kind"] for issue in report["issues"]}


def test_process_language_is_removed_from_player_note_projection() -> None:
    cards = _cards()
    cards[1] = _card(1, "任务甲", note="已实测：必须先点任务物。")
    report = project_route_display(
        _profile(),
        cards=cards,
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    assert report["status"] == "pass"
    assert report["steps"][0]["task_presentations"][0]["note"] is None
    assert report["steps"][1]["task_presentations"][0]["note"] == "必须先点任务物。"
    assert "player_note_contains_process_language" not in {issue["kind"] for issue in report["issues"]}


def test_location_layer_diagnoses_npc_or_route_action_text_without_rewriting_it() -> None:
    profile = _profile()
    profile["geometry"]["locations"]["hub"]["display_name"] = "测试NPC"
    profile["geometry"]["locations"]["field"]["display_name"] = "测试Hub → 测试野外"
    report = project_route_display(
        profile,
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    assert report["status"] == "pass"
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "location_display_matches_npc_name" in kinds
    assert "location_display_encodes_route_action" in kinds
    assert report["steps"][0]["lines"][0]["text"] == "测试NPC"
    assert any(line["text"] == "测试Hub → 测试野外" for line in report["steps"][1]["lines"])


def test_display_preserves_unknown_map_position_as_requirement() -> None:
    movement = _movement(status="requirements")
    movement["visits"][1]["x"] = None
    movement["visits"][1]["y"] = None
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=movement,
        timing_report=_timing(),
        upstream_statuses={**_upstream(), "canonical_spatial_movement": "requirements"},
    )

    assert report["status"] == "requirements"
    visit = report["map_geometry"]["visits"][1]
    assert visit["x"] is None
    assert visit["y"] is None
    assert "display_movement_visit_position_unknown" in {issue["kind"] for issue in report["issues"]}


def test_display_accepts_non_plottable_transition_context_without_requirement() -> None:
    movement = _movement()
    movement["visits"][1]["location_role"] = "transition_context"
    movement["visits"][1]["x"] = None
    movement["visits"][1]["y"] = None
    report = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=movement,
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )

    assert report["status"] == "pass"
    visit = report["map_geometry"]["visits"][1]
    assert visit["location_role"] == "transition_context"
    assert visit["x"] is None
    assert visit["y"] is None
    assert "display_movement_visit_position_unknown" not in {issue["kind"] for issue in report["issues"]}


def test_display_fingerprint_changes_only_with_consumed_display_inputs() -> None:
    base = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
        upstream_fingerprints={"movement": "m1", "review": "r1"},
    )
    cards = deepcopy(_cards())
    cards[1]["presentation"]["note_override"]["text"] = "换一条玩家备注。"
    changed = project_route_display(
        _profile(),
        cards=cards,
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
        upstream_fingerprints={"movement": "m1", "review": "r1"},
    )
    assert base["input_fingerprint"] != changed["input_fingerprint"]



def test_incremental_task_note_refresh_preserves_unrelated_display_data() -> None:
    base = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    presentation = {
        "task_id": 1,
        "name": "任务甲",
        "badge": "shared",
        "note": "新的短备注。",
        "note_override_applied": True,
        "pending": False,
    }

    refreshed = refresh_task_card_display(base, presentation)

    assert refreshed["input_fingerprint"] != base["input_fingerprint"]
    assert refreshed["map_geometry"] == base["map_geometry"]
    assert refreshed["route_timing"] == base["route_timing"]
    assert refreshed["steps"][0]["lines"] == base["steps"][0]["lines"]
    assert refreshed["steps"][0]["task_presentations"][0]["note"] is None
    assert refreshed["steps"][0]["task_presentations"][0]["note_visible"] is False
    assert refreshed["steps"][1]["task_presentations"][0]["note"] == "新的短备注。"
    assert refreshed["steps"][1]["task_presentations"][0]["note_visible"] is True


def test_incremental_task_identity_refresh_updates_only_task_text_and_presentation() -> None:
    base = project_route_display(
        _profile(),
        cards=_cards(),
        movement_report=_movement(),
        timing_report=_timing(),
        upstream_statuses=_upstream(),
    )
    presentation = {
        "task_id": 1,
        "name": "任务甲新名字",
        "badge": "shared",
        "note": "必须先点任务物。",
        "note_override_applied": True,
        "pending": False,
    }

    refreshed = refresh_task_card_display(base, presentation, update_action_text=True)

    assert refreshed["map_geometry"] == base["map_geometry"]
    assert refreshed["route_timing"] == base["route_timing"]
    assert "《任务甲新名字》" in refreshed["steps"][0]["lines"][1]["text"]
    assert "《任务甲新名字》" in refreshed["steps"][1]["lines"][0]["text"]
    assert refreshed["steps"][0]["task_presentations"][0]["name"] == "任务甲新名字"
