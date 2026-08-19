from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"
TIMING_RUNS = ROOT / "data/observations/route-timing-runs.json"


def test_all_official_routes_have_hearth_and_timing_contract() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    assert set(routes) >= {"zang", "nagrand", "borean", "dragonblight"}

    for key in ("zang", "nagrand", "borean", "dragonblight"):
        route = routes[key]
        assert not route.get("badgeTitle"), key
        assert isinstance(route["hearthChain"], list) and route["hearthChain"], key
        timing = route["timing"]
        assert timing["centerMinutes"] > 0, key
        assert len(timing["rangeMinutes"]) == 2, key
        assert timing["rangeMinutes"][0] <= timing["centerMinutes"] <= timing["rangeMinutes"][1], key
        assert "炉石：" in route["badge"] and "预计总时间：" in route["badge"], key
        assert "\n预计总时间：" in route["badge"], key
        for index, group in enumerate(route["stepGroups"], 1):
            step_timing = group["timing"]
            assert step_timing["centerMinutes"] > 0, (key, index)
            assert len(step_timing["rangeMinutes"]) == 2, (key, index)
            assert step_timing["rangeMinutes"][0] <= step_timing["centerMinutes"] <= step_timing["rangeMinutes"][1], (key, index)


def test_hearth_chain_is_current_verified_binding_chain() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    assert routes["zang"]["hearthChain"] == ["萨布拉金"]
    assert routes["nagrand"]["hearthChain"] == ["加拉达尔"]
    assert routes["borean"]["hearthChain"] == ["战歌要塞"]
    assert routes["dragonblight"]["hearthChain"] == ["阿格玛之锤"]


def test_actual_time_is_omitted_when_not_reliably_recorded() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    assert routes["zang"]["timing"]["actualRuns"] == []
    assert routes["dragonblight"]["timing"]["actualRuns"] == []
    assert routes["nagrand"]["timing"]["actualRuns"]
    assert routes["borean"]["timing"]["actualRuns"] == []
    assert "实测" not in routes["zang"]["badge"]
    assert "实测" not in routes["borean"]["badge"]
    assert "实测" not in routes["dragonblight"]["badge"]


def test_hud_fixed_slot_renders_step_timing_not_coordinates() -> None:
    html = HTML.read_text(encoding="utf-8")
    assert "function fmtRouteMinutes" in html
    assert "本段预计：约" in html
    assert "route().stepGroups?.[cur]?.timing" in html
    assert 'id="badgeTitle"' not in html
    assert '"badgeTitle"' not in html
    assert "white-space:pre-line" in html


def test_northrend_68_80_veteran_benchmark_is_preserved_as_long_term_target() -> None:
    data = json.loads(TIMING_RUNS.read_text(encoding="utf-8"))
    target = next(row for row in data["long_term_targets"] if row["id"] == "northrend_68_80_veteran_fastest")
    assert target["target_minutes"] == 840
    assert target["target_hours"] == 14
    assert target["status"] == "user_reported_veteran_benchmark"
    assert "推测" in target["route_characteristic_inference"]
    contract = data["recording_contract"]
    assert "approximate" in contract["time_precision"]
    assert "局部实测不得冒充整图实测" in contract["scope"]
