from __future__ import annotations

from copy import deepcopy

import pytest

from lib.route_player_assets import (
    PlayerAssetsError,
    evaluate_player_assets,
    render_player_view,
    render_workbench_html,
    write_player_assets,
)


def _payload(*, status: str = "pass", publishable: bool = True) -> dict:
    return {
        "schema_version": 1,
        "kind": "publisher_payload",
        "profile_id": "assets-fixture",
        "profile_version": 4,
        "program_id": None,
        "status": status,
        "publishable": publishable,
        "input_fingerprint": "publisher-fixture-v4",
        "stage11_input_fingerprint": "display-fixture-v4",
        "display": {
            "publish_key": "assets_fixture",
            "order": 1,
            "title": "资产测试路线",
            "display_name": "资产测试",
            "subtitle": "只读Publisher payload。",
            "footer": "页尾",
        },
        "map": {
            "image": "maps/test-map.jpg",
            "labels": [{"x": 20.0, "y": 30.0, "display_name": "视觉标签"}],
            "geometry": {
                "status": "pass",
                "input_fingerprint": "movement-fixture-v4",
                "visits": [
                    {
                        "visit_id": "a1",
                        "ordinal": 1,
                        "location_ref": "p1",
                        "display_name": "起点",
                        "x": 10.0,
                        "y": 20.0,
                        "step_id": "step-01",
                    },
                    {
                        "visit_id": "a3",
                        "ordinal": 2,
                        "location_ref": "p2",
                        "display_name": "终点",
                        "x": 40.0,
                        "y": 50.0,
                        "step_id": "step-02",
                    },
                ],
                "edges": [
                    {
                        "edge_id": "a1->a3",
                        "from_visit_id": "a1",
                        "to_visit_id": "a3",
                        "from_location_ref": "p1",
                        "to_location_ref": "p2",
                        "operation_kind": "self_move",
                        "movement_mode": "ride",
                        "movement_action_id": None,
                        "source": "canonical",
                    }
                ],
            },
        },
        "hearth_chain": ["起点旅店", "终点旅店"],
        "route_timing": {
            "status": "pass",
            "center_minutes": 12.5,
            "range_minutes": [11.0, 14.0],
            "input_fingerprint": "timing-fixture-v4",
        },
        "steps": [
            {
                "step_id": "step-01",
                "title": "接任务",
                "summary": "",
                "action_ids": ["a1", "a2"],
                "lines": [
                    {"type": "location", "text": "起点", "location_ref": "p1", "action_ids": ["a1"], "task_refs": []},
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
                        "note": "必须先点任务物。",
                        "note_override_applied": True,
                        "pending": False,
                    }
                ],
                "timing": {"status": "pass", "center_minutes": 3.0, "range_minutes": [2.5, 3.5]},
            },
            {
                "step_id": "step-02",
                "title": "交任务",
                "summary": "结束本段",
                "action_ids": ["a3", "a4"],
                "lines": [
                    {"type": "location", "text": "终点", "location_ref": "p2", "action_ids": ["a3"], "task_refs": []},
                    {
                        "type": "task_action",
                        "text": "测试NPC → 交《测试任务》",
                        "actor": {"kind": "npc", "name": "测试NPC"},
                        "task_refs": [{"task_id": 1, "name": "测试任务", "kind": "turnin"}],
                        "action_ids": ["a4"],
                    },
                ],
                "task_presentations": [],
                "timing": {"status": "pass", "center_minutes": 9.5, "range_minutes": [8.5, 10.5]},
            },
        ],
        "issues": [],
    }


def _map(tmp_path) -> None:
    maps = tmp_path / "maps"
    maps.mkdir(parents=True, exist_ok=True)
    (maps / "test-map.jpg").write_bytes(b"fixture-map")


def test_player_view_consumes_structured_publisher_payload_without_html_roundtrip() -> None:
    text = render_player_view(_payload())
    assert "# 资产测试路线" in text
    assert "炉石：起点旅店 → 终点旅店" in text
    assert "预计总时间：12.5分钟" in text
    assert "- 测试NPC → 接【共享】《测试任务》" in text
    assert "- 《测试任务》：必须先点任务物。" in text
    assert "《测试任务》：共享；" not in text
    assert "<div" not in text
    assert "actionHtml" not in text


def test_workbench_embeds_stage12_payload_and_has_required_offline_controls() -> None:
    html = render_workbench_html([_payload()])
    assert 'const ROUTES=[{"schema_version":1,"kind":"publisher_payload"' in html
    assert "maps/test-map.jpg" in html
    assert "上一段" in html
    assert "下一段" in html
    assert "播放当前段" in html
    assert "播放剩余路线" in html
    assert "跟随当前段" not in html
    assert 'id="follow"' not in html
    assert "route-atlas:last-route" in html
    assert "route-atlas:last-step:" in html
    assert "PLAY_EDGE_MS=1400" in html
    assert "PLAY_JUMP_MS=850" in html
    assert "PLAY_RATE=1.8" in html
    assert 'id="mapLabels"' in html
    assert "mapLabel" in html
    assert "createElementNS('http://www.w3.org/2000/svg','text')" not in html
    assert '<button id="collapse" class="hudToggle">收起 ▲</button>' in html
    assert "fmtStepTiming" in html
    assert "本段预计：—" in html
    assert "pendingTag" in html
    assert "return'待实测'" in html
    assert "五开待实测" not in html
    assert ".hudBody{padding:10px 12px;overflow:auto;font-size:14px}" in html
    assert ".routeAction.open_flight_point{color:#ff9f68}" in html
    assert ".routeAction.bind_hearth{color:#cf9cff}" in html
    assert "row.classList.add('routeAction',String(line.action_kind))" in html
    assert "notesTitle','备注'" in html
    assert "PingFang SC" in html
    assert r"bits.join('\n')" in html
    assert "bits.join('\n')" not in html
    assert "const used=new Set()" in html
    assert "visibleTaskKind" in html
    assert "candidates.find(token=>token.ref.kind===inferred)" in html
    assert "used.add(best.index)" in html
    assert "步骤 ${stepIndex+1}/${r.steps.length}" in html
    assert "presentationByTask" in html
    lowered = html.lower()
    assert 'src="http://' not in lowered
    assert 'src="https://' not in lowered
    assert 'href="http://' not in lowered
    assert 'href="https://' not in lowered
    assert "url(http" not in lowered
    assert "workbench-routes.json" not in html


def test_workbench_keeps_unknown_visit_coordinates_out_of_svg_math() -> None:
    payload = _payload(status="requirements", publishable=False)
    payload["map"]["geometry"]["status"] = "requirements"
    payload["map"]["geometry"]["visits"][1]["x"] = None
    payload["map"]["geometry"]["visits"][1]["y"] = None
    html = render_workbench_html([payload])

    assert '"x":null' in html
    assert "function positioned(v)" in html
    assert "if(!positioned(v))continue" in html
    assert "positioned(x.a)&&positioned(x.b)" in html


def test_asset_evaluation_requires_local_map_and_publishable_stage12(tmp_path) -> None:
    _map(tmp_path)
    report = evaluate_player_assets([_payload()], routes_root=tmp_path)
    assert report["status"] == "pass"
    assert report["publishable"] is True
    assert report["referenced_assets"] == ["maps/test-map.jpg"]
    assert report["workbench_bytes"] > 1000
    assert "assets_fixture" in report["player_views"]

    blocked = evaluate_player_assets([_payload(status="blocked", publishable=False)], routes_root=tmp_path)
    assert blocked["status"] == "blocked"
    assert blocked["publishable"] is False
    assert "player_assets_publisher_blocked" in {issue["kind"] for issue in blocked["issues"]}
    assert blocked["player_views"]["assets_fixture"]


def test_asset_evaluation_blocks_missing_map(tmp_path) -> None:
    report = evaluate_player_assets([_payload()], routes_root=tmp_path)
    assert report["status"] == "blocked"
    assert report["publishable"] is False
    assert "player_assets_map_missing" in {issue["kind"] for issue in report["issues"]}


def test_write_gate_refuses_blocked_and_writes_single_workbench_plus_player_view(tmp_path) -> None:
    _map(tmp_path)
    with pytest.raises(PlayerAssetsError, match="non-publishable"):
        write_player_assets([_payload(status="blocked", publishable=False)], output_dir=tmp_path)

    report = write_player_assets([_payload()], output_dir=tmp_path)
    assert report["publishable"] is True
    assert (tmp_path / "route-atlas-workbench.html").exists()
    assert (tmp_path / "player-view" / "assets_fixture.md").exists()
    assert not list(tmp_path.glob("*candidate*.html"))


def test_duplicate_publish_key_is_rejected_before_render() -> None:
    duplicate = deepcopy(_payload())
    duplicate["profile_id"] = "other-profile"
    duplicate["input_fingerprint"] = "publisher-other"
    with pytest.raises(PlayerAssetsError, match="duplicate publish_key"):
        render_workbench_html([_payload(), duplicate])
