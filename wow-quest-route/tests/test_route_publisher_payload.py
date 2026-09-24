from __future__ import annotations

from copy import deepcopy

import pytest

from lib.route_publisher_payload import PublisherPayloadError, build_publisher_payload, validate_route_ui_config


def _display(status: str = "pass") -> dict:
    return {
        "kind": "route_display",
        "profile_id": "publisher-fixture",
        "profile_version": 3,
        "status": status,
        "input_fingerprint": "display-fingerprint-v3",
        "display": {
            "publish_key": "publisher_fixture",
            "order": 12,
            "title": "发布测试路线",
            "display_name": "发布测试",
            "subtitle": "说明",
            "footer": "页尾",
            "map_image": "maps/test-map.jpg",
        },
        "map_geometry": {
            "status": "pass",
            "input_fingerprint": "movement-fingerprint",
            "visits": [
                {
                    "visit_id": "a1",
                    "ordinal": 1,
                    "location_ref": "p1",
                    "display_name": "测试地点",
                    "x": 12.0,
                    "y": 34.0,
                    "step_id": "step-01",
                }
            ],
            "edges": [],
        },
        "hearth_chain": ["旧炉石点", "新炉石点"],
        "route_timing": {
            "status": "pass",
            "center_minutes": 12.5,
            "range_minutes": [11.0, 14.0],
            "input_fingerprint": "timing-fingerprint",
        },
        "steps": [
            {
                "step_id": "step-01",
                "title": "第一步",
                "summary": "",
                "action_ids": ["a1", "a2"],
                "lines": [
                    {"type": "location", "text": "测试地点", "location_ref": "p1", "action_ids": ["a1"], "task_refs": []},
                    {
                        "type": "task_action",
                        "text": "测试NPC → 接《测试任务》",
                        "actor": {"kind": "npc", "name": "测试NPC"},
                        "task_refs": [{"task_id": 1, "name": "测试任务", "kind": "accept"}],
                        "action_ids": ["a2"],
                    },
                ],
                "task_presentations": [
                    {
                        "task_id": 1,
                        "name": "测试任务",
                        "badge": "shared",
                        "note": "最短必要备注。",
                        "note_override_applied": True,
                        "pending": False,
                    }
                ],
                "timing": {"status": "pass", "center_minutes": 3.0, "range_minutes": [2.5, 3.5]},
            }
        ],
        "issues": [],
    }


def _ui() -> dict:
    return {
        "schema_version": 1,
        "profile_id": "publisher-fixture",
        "map_labels": [{"x": 12.0, "y": 34.0, "display_name": "视觉标签"}],
    }


def test_stage12_payload_is_pure_wrapper_over_stage11_semantics_and_ui() -> None:
    display = _display()
    payload = build_publisher_payload(display, route_ui=_ui())
    assert payload["status"] == "pass"
    assert payload["publishable"] is True
    assert payload["profile_id"] == "publisher-fixture"
    assert payload["profile_version"] == 3
    assert payload["stage11_input_fingerprint"] == display["input_fingerprint"]
    assert payload["steps"] == display["steps"]
    assert payload["hearth_chain"] == ["旧炉石点", "新炉石点"]
    assert payload["route_timing"] == display["route_timing"]
    assert payload["map"]["image"] == "maps/test-map.jpg"
    assert payload["map"]["labels"] == [{"x": 12.0, "y": 34.0, "display_name": "视觉标签"}]
    assert payload["map"]["geometry"] == display["map_geometry"]
    assert payload["map"]["geometry"]["visits"][0]["step_id"] == "step-01"
    text = str(payload)
    assert "actionHtml" not in text
    assert "noteHtml" not in text
    assert "points" not in payload


def test_nonpass_stage11_can_be_wrapped_for_diagnostics_but_never_publishable() -> None:
    requirements = build_publisher_payload(_display("requirements"), route_ui=_ui())
    assert requirements["status"] == "requirements"
    assert requirements["publishable"] is False
    assert requirements["issues"] == [{"severity": "requirement", "kind": "publisher_stage11_requirements"}]

    blocked = build_publisher_payload(_display("blocked"), route_ui=_ui())
    assert blocked["status"] == "blocked"
    assert blocked["publishable"] is False
    assert blocked["issues"] == [{"severity": "error", "kind": "publisher_stage11_blocked"}]


def test_stage12_rejects_non_stage11_input() -> None:
    with pytest.raises(PublisherPayloadError, match="route_display"):
        build_publisher_payload({"kind": "route_profile"}, route_ui=_ui())


def test_route_ui_is_profile_bound_and_coordinates_are_bounded() -> None:
    bad_profile = _ui()
    bad_profile["profile_id"] = "other-profile"
    with pytest.raises(PublisherPayloadError, match="profile_id mismatch"):
        build_publisher_payload(_display(), route_ui=bad_profile)

    bad_coord = _ui()
    bad_coord["map_labels"][0]["x"] = 101
    with pytest.raises(PublisherPayloadError, match="0..100"):
        validate_route_ui_config(bad_coord, expected_profile_id="publisher-fixture")


def test_map_path_must_be_offline_relative_maps_path() -> None:
    display = _display()
    display["display"]["map_image"] = "https://example.test/map.jpg"
    payload = build_publisher_payload(display, route_ui=_ui())
    assert payload["status"] == "blocked"
    assert payload["publishable"] is False
    assert "publisher_map_image_must_be_relative_maps_path" in {issue["kind"] for issue in payload["issues"]}


def test_payload_fingerprint_changes_when_stage11_or_ui_changes() -> None:
    base = build_publisher_payload(_display(), route_ui=_ui())

    display_changed = _display()
    display_changed["input_fingerprint"] = "display-fingerprint-v4"
    changed_display = build_publisher_payload(display_changed, route_ui=_ui())
    assert base["input_fingerprint"] != changed_display["input_fingerprint"]

    ui_changed = deepcopy(_ui())
    ui_changed["map_labels"][0]["display_name"] = "另一个视觉标签"
    changed_ui = build_publisher_payload(_display(), route_ui=ui_changed)
    assert base["input_fingerprint"] != changed_ui["input_fingerprint"]
