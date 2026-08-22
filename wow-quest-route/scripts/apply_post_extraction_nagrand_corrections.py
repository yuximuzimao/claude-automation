from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data" / "route-atlas" / "workbench-routes.json"


def main() -> None:
    data = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = data["nagrand"]
    points = route["points"]
    groups = route["stepGroups"]

    idx = next((i for i, p in enumerate(points) if str(p[2]) == "【最后兜底】奈辛瓦里第三轮首领"), None)
    if idx is None:
        raise SystemExit("Nagrand final fallback point not found")
    point = list(points[idx])
    point[3] = (
        "若仍未68，再按经验缺口选择班塔尔、裂肠者、巴克洛尔；每完成一条就回奈辛瓦里交付并检查最低号经验。"
        "若三条高级狩猎全部完成并交付后仍未68，再接《终极挑战》，去塔丝克（44.24,65.16）击杀并取得塔丝克之心，"
        "回奈辛瓦里交《终极挑战》；任何一次检查到最低号已68就立刻结束纳格兰冲刺"
    )
    point[5] = (
        "塔丝克是68级任务目标；只在三条高级狩猎全部交完仍未68时启用这一步，击杀后确认每个仍需要任务物的角色都取得塔丝克之心再离开。"
    )
    while len(point) < 9:
        if len(point) == 6:
            point.append("ride")
        elif len(point) == 7:
            point.append(False)
        else:
            point.append("")
    point[8] = (
        "仅当真的走到《终极挑战》时检查：击杀塔丝克后，同一具尸体的塔丝克之心是否能让五个角色都分别拾取。"
        "若只能一个角色取得，不要原地等四次刷新，停止这条兜底并记录。"
    )
    points[idx] = point

    if len(groups) != 4 or groups[3]["start"] != 11 or groups[3]["end"] != 13:
        raise SystemExit("unexpected Nagrand fallback group structure")
    groups[3]["title"] = "条件兜底：顾问佐尔布 / 第三轮首领 / 终极挑战"
    groups[3]["summary"] = (
        "只在最低号未68时逐层补经验：先顾问佐尔布，再按缺口做奈辛瓦里第三轮首领；"
        "三条高级狩猎全交后仍未68才启用《终极挑战》，到68立即停止。"
    )
    groups[3]["timing"] = {
        "centerMinutes": 20.5,
        "rangeMinutes": [16.0, 25.0],
        "includeInTotal": False,
    }
    groups[3]["fivebox_check"] = (
        "若启用《终极挑战》，确认塔丝克之心是否同一尸体五号都可分别拾取；若只能单号拾取，不等待重复刷新。"
    )

    ROUTES.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "point_index": idx,
        "action": points[idx][3],
        "fivebox_check": points[idx][8],
        "fallback_group": groups[3],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
