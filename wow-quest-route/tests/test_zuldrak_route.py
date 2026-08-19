from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE = ROOT / "data/route-atlas/zuldrak-route-coverage.json"
FOUNDATION = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
FLIGHT_AUDIT = ROOT / "data/route-atlas/flight-state-audit.json"
VIDEO_AUDIT = ROOT / "data/route-atlas/northrend-video-reverse-audit.json"
TIMING = ROOT / "data/route-atlas/route-atlas-timing-estimates.json"
ADVERSARIAL = ROOT / "data/route-atlas/zuldrak-adversarial-audit.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def test_zuldrak_full_clear_route_is_closed() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["zuldrak"]
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))

    assert foundation["formal_task_count"] == 104
    assert foundation["dependency_hard_gap_count"] == 0
    assert coverage["formal_task_count"] == 104
    assert coverage["covered_task_count"] == 104
    assert coverage["intentional_defer"] == {}
    assert coverage["missing"] == []
    assert coverage["unexpected"] == []
    assert len(route["points"]) == 107
    assert len(route["stepGroups"]) == 12


def test_zuldrak_route_uses_cluster_insertions_found_by_video_reverse_review() -> None:
    route = json.loads(ROUTES.read_text(encoding="utf-8"))["zuldrak"]
    text = json.dumps(route, ensure_ascii=False)

    # Gymer's second material is collected at Ebon Watch, then the route returns to close Gymer.
    assert "黑锋入口·硅藻土" in text
    assert "北伐军前线·盖米尔材料回收" in text
    # Lab work is inserted into the first northward patrol loop.
    assert "赫布瓦罗岗哨·第一次" in text
    # The southern corridor combines pain/water/elemental-fluid objectives.
    assert "水罂粟 + 水元素走廊" in text
    # The first rescue is deliberately held until Cocooned unlocks, so the rescue area is entered once.
    assert "救援区·两个救人任务合并" in text
    assert "暂不做《一个也不能少》救援" in text
    # Adversarial review removed the fake Ebon Watch revisits: Stefan is summoned locally by horn.
    assert "痛苦之匣·吹号第一轮" in text
    assert "痛苦之匣·吹号最终" in text
    assert "达库鲁的最后愿望" in text
    assert "斯特凡·沃尔塔鲁斯第二轮" not in text


def test_zuldrak_adversarial_dependency_and_arena_breadcrumb_rules() -> None:
    route = json.loads(ROUTES.read_text(encoding="utf-8"))["zuldrak"]
    actions = [str(point[3]) for point in route["points"]]

    strange_mojo_turnin = next(i for i, action in enumerate(actions) if "交《奇怪的魔精》" in action)
    water_troll_accept = next(i for i, action in enumerate(actions) if "接《达卡莱巨魔不需要水元素！》" in action)
    champion_accept = next(i for i, action in enumerate(actions) if "接《勇士的召唤！》" in action)
    champion_turnin = next(i for i, action in enumerate(actions) if "交《勇士的召唤！》" in action)
    arena_accept = next(i for i, action in enumerate(actions) if "接《痛苦斗兽场：伊戈达斯！》" in action)

    assert strange_mojo_turnin <= water_troll_accept
    assert champion_accept < champion_turnin <= arena_accept
    route_text = json.dumps(route, ensure_ascii=False)
    assert "银色前沿·达拉然短往返" in route_text
    assert "痛苦斗兽场·第一场门槛 + 六连" in route_text
    assert "战斗能力和五开共享双重门槛" in route_text
    assert "若只有部分角色完成，重新触发伊戈达斯把漏号补齐" in route_text

    audit = json.loads(ADVERSARIAL.read_text(encoding="utf-8"))
    assert audit["status"] == "pass"
    assert audit["hard_failures"] == []
    assert audit["lifecycle"]["max_active"] <= 25
    assert audit["lifecycle"]["prerequisite_violations"] == []
    assert audit["fivebox_missing_checks"] == []
    assert audit["unresolved_long_ride_edges"] == []


def test_zuldrak_video_reverse_review_and_flight_state_pass() -> None:
    flight = json.loads(FLIGHT_AUDIT.read_text(encoding="utf-8"))["routes"]["zuldrak"]
    video = json.loads(VIDEO_AUDIT.read_text(encoding="utf-8"))["maps"]["zuldrak"]

    assert flight["flight_count"] == 5
    assert flight["violation_count"] == 0
    assert flight["unknown_destination_count"] == 0
    assert video["critical_video_omission_count"] == 0
    assert video["common_explicit_completion_count"] == 37
    assert video["unresolved_adjacent_reversal_count"] == 0
    assert video["route_order_review_status"] == "pass_whole_map_video_reverse_review"


def test_zuldrak_timing_and_html_are_published() -> None:
    timing = json.loads(TIMING.read_text(encoding="utf-8"))["zuldrak"]
    html = HTML.read_text(encoding="utf-8")

    assert timing["centerMinutes"] > 0
    assert timing["rangeMinutes"][0] < timing["centerMinutes"] < timing["rangeMinutes"][1]
    assert timing["actualRuns"] == []
    assert "祖达克" in html
    assert "沃尔塔鲁斯" in html
    assert "痛苦斗兽场" in html
    assert "痛苦斗兽场·第一场门槛 + 六连" in html
    assert "战斗能力和五开共享双重门槛" in html
    assert "救援区·两个救人任务合并" in html
