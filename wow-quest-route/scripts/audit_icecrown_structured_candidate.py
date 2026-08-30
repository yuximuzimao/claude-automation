from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "data/route-atlas/icecrown-route-structured-candidate.json"
COVERAGE = ROOT / "data/route-atlas/icecrown-route-structured-coverage.json"
OUT = ROOT / "data/route-atlas/icecrown-structured-candidate-audit.json"

EXTERNAL_PLACES = ("无拘林地", "杉达拉废墟", "月光林地", "雷姆洛斯神殿", "龙眠神殿", "红玉巨龙圣地", "沙塔斯", "达拉然")
SAME_ANCHOR_PREFIXES = (
    "做《", "↳", "五号", "先", "每", "离开条件", "单号", "使用", "接受", "接《", "交《",
    "白骨巨人", "同一片墓地", "继续", "以上", "三项", "两项", "第一具", "第一只", "个人目标",
)
PLACE_TOKEN = re.compile(r"(基地|林地|废墟|墓地|神殿|港口|大教堂|堡垒|营地|村|高地|前线|大厅|矿洞|之峰|之墓|之庭|之门|拱顶|观察站|海姆|雷卡里斯|杜萨|采掘场)")
# These are intentional same-anchor actions even though their prose contains a place-like noun.
SAME_ANCHOR_EXCEPTIONS = {
    (2, 2), (2, 4), (2, 5), (2, 6),
    (23, 4), (23, 5), (24, 2), (24, 3), (38, 6),
}


def main() -> None:
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    hard: list[dict] = []
    classified: list[dict] = []

    points = route.get("points") or []
    groups = route.get("stepGroups") or []
    for idx, point in enumerate(points):
        if len(point) < 9 or not (0 <= float(point[0]) <= 100 and 0 <= float(point[1]) <= 100):
            hard.append({"type": "invalid_point", "index": idx, "point": point})

    expected_start = 0
    for step, group in enumerate(groups, start=1):
        if int(group["start"]) != expected_start or int(group["end"]) < int(group["start"]):
            hard.append({"type": "non_contiguous_group", "step": step, "group": group})
        expected_start = int(group["end"]) + 1
    if expected_start != len(points):
        hard.append({"type": "group_point_coverage_mismatch", "covered_until": expected_start, "points": len(points)})

    fallbacks = ((route.get("geometryAudit") or {}).get("fallbackActions") or [])
    for row in fallbacks:
        step = int(row["step"])
        action = int(row["action"])
        text = str(row["text"])
        prefix = text.split("→", 1)[0].split("↳", 1)[0].strip()
        key = (step, action)
        if any(place in prefix for place in EXTERNAL_PLACES):
            status = "crossmap_not_drawn_on_icecrown_map"
        elif key in SAME_ANCHOR_EXCEPTIONS or prefix.startswith(SAME_ANCHOR_PREFIXES):
            status = "same_anchor_action"
        elif not PLACE_TOKEN.search(prefix):
            status = "same_hub_npc_or_instruction"
        else:
            status = "hard_unresolved_location"
            hard.append({"type": status, **row, "prefix": prefix})
        classified.append({**row, "classification": status})

    large_segments: list[dict] = []
    for idx in range(1, len(points)):
        distance = math.hypot(float(points[idx][0]) - float(points[idx - 1][0]), float(points[idx][1]) - float(points[idx - 1][1]))
        if distance >= 35:
            large_segments.append({
                "fromIndex": idx - 1,
                "toIndex": idx,
                "distance": round(distance, 2),
                "movement": points[idx][6],
                "from": points[idx - 1][2],
                "to": points[idx][2],
            })
        if distance > 60 and points[idx][6] not in {"script", "crossmap", "hearth"}:
            hard.append({"type": "implausible_single_map_segment", "index": idx, "distance": round(distance, 2)})

    action_text = "\n".join(str(point[3]) for point in points)

    expected_system_actions = {
        "开飞行点：银色比武场",
        "开飞行点：银色前线基地",
        "开飞行点：北伐军之峰（五号分别）",
        "开飞行点：暗影拱顶（五号分别）",
        "炉石绑定：暗影拱顶",
        "开飞行点：死亡高地（五号分别）",
    }
    actual_system_actions = {
        line for line in action_text.splitlines()
        if line.startswith("开飞行点：") or line.startswith("炉石绑定：")
    }
    if actual_system_actions != expected_system_actions:
        hard.append({
            "type": "transport_state_action_mismatch",
            "expected": sorted(expected_system_actions),
            "actual": sorted(actual_system_actions),
        })

    center_sum = sum(float(group["timing"]["centerMinutes"]) for group in groups)
    route_center = float((route.get("timing") or {}).get("centerMinutes", -1))
    if round(center_sum, 6) != round(route_center, 6):
        hard.append({"type": "timing_center_mismatch", "groups": center_sum, "route": route_center})

    if coverage.get("missing") or coverage.get("unexpected") or int(coverage.get("coveredTaskCount") or 0) != int(coverage.get("formalTaskCount") or -1):
        hard.append({"type": "coverage_not_closed", "coverage": coverage})

    payload = {
        "status": "PASS" if not hard else "FAIL",
        "hardIssueCount": len(hard),
        "hardIssues": hard,
        "pointCount": len(points),
        "stepGroupCount": len(groups),
        "geometryFallbackCount": len(fallbacks),
        "geometryFallbackClassifications": classified,
        "largeSegmentReview": large_segments,
        "transportStateActions": sorted(actual_system_actions),
        "timingCenterMinutes": center_sum,
        "coverage": {
            "formal": coverage.get("formalTaskCount"),
            "covered": coverage.get("coveredTaskCount"),
            "missing": coverage.get("missing"),
            "unexpected": coverage.get("unexpected"),
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"], "hard": len(hard), "points": len(points), "groups": len(groups),
        "fallbacks": len(fallbacks), "large_segments_for_review": len(large_segments), "timing_center": center_sum,
    }, ensure_ascii=False, indent=2))
    if hard:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
