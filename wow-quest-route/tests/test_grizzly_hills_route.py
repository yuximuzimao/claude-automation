from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE = ROOT / "data/route-atlas/grizzly-hills-route-coverage.json"
FOUNDATION = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
FLIGHT_AUDIT = ROOT / "data/route-atlas/flight-state-audit.json"
TIMING = ROOT / "data/route-atlas/route-atlas-timing-estimates.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def test_grizzly_full_clear_route_is_closed() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["grizzly"]
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))

    assert foundation["formal_task_count"] == 83
    assert foundation["dependency_hard_gap_count"] == 0
    assert coverage["expected_world_task_count"] == 83
    assert coverage["covered_task_count"] == 83
    assert coverage["missing"] == []
    assert coverage["unexpected"] == []
    assert len(route["points"]) == 70
    assert len(route["stepGroups"]) == 11


def test_grizzly_from_zero_transport_and_flight_state_are_valid() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["grizzly"]
    text = json.dumps(route, ensure_ascii=False)
    flight = json.loads(FLIGHT_AUDIT.read_text(encoding="utf-8"))["routes"]["grizzly"]

    assert route["points"][0][6] == "crossmap"
    assert "沿公路进入征服堡" in route["points"][0][2]
    assert "开启征服堡飞行点" in text
    assert "开启欧尼瓦飞行点" in text
    assert flight["flight_count"] == 5
    assert flight["violation_count"] == 0
    assert flight["unknown_destination_count"] == 0


def test_grizzly_restores_full_clear_tasks_and_excludes_structural_nonroute_items() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route_text = json.dumps(routes["grizzly"], ensure_ascii=False)
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    formal_ids = set(foundation["formal_task_ids"])

    # Legitimate Grizzly tasks missed by the old auto route must be restored.
    for qid in (12082, 12327, 12330, 12427, 12428, 12429, 12430, 12431):
        assert qid in formal_ids
        assert foundation["tasks"][[int(t["quest_id"]) for t in foundation["tasks"]].index(qid)]["name"] in route_text

    # Current Horde outdoor axis does not include the mutually exclusive / repeat / Alliance items.
    for qid in (11981, 11997, 12434, 12446, 12763):
        assert qid not in formal_ids

    # The falsely classified vendor quest is back in the outdoor route.
    task_12177 = next(t for t in foundation["tasks"] if int(t["quest_id"]) == 12177)
    assert task_12177["is_dungeon"] is False
    assert "休尼克的掩饰" in route_text


def test_grizzly_timing_and_html_are_published() -> None:
    timing = json.loads(TIMING.read_text(encoding="utf-8"))["grizzly"]
    html = HTML.read_text(encoding="utf-8")

    assert timing["centerMinutes"] > 0
    assert timing["rangeMinutes"][0] < timing["centerMinutes"] < timing["rangeMinutes"][1]
    assert timing["actualRuns"] == []
    assert "灰熊丘陵" in html
    assert "征服斗兽场" in html
    assert "Dun Argol" in html
