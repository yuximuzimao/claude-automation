from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_atlas_exact import ExactSolver, build_compressed_model

ATLAS = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-opt-v1.json"
REPORT = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-global-opt-v1-result.md"

# Same east-side validation set as v0 so route changes can be attributed to model changes.
QUEST_IDS = [9747, 9788, 9895, 9773, 9899, 9769, 9770, 9898]
START_XY = (78.40, 62.02)
START_NAME = "塞纳里奥庇护所（伊谢尔·风歌锚点）"


def round_obj(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [round_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: round_obj(v) for k, v in value.items()}
    return value


def fmt(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}分{total % 60:02d}秒"


def summarize_route(route: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    step = 0
    for action in route:
        kind = action["type"]
        if kind == "MOVE":
            if action["travel_cost"] <= 1e-9:
                continue
            step += 1
            rows.append(
                f"{step}. 移动：{action['from_name']} → {action['to_name']}（{fmt(action['travel_cost'])}）"
            )
        elif kind == "ACCEPT":
            rows.append(f"   - 接：{action['quest_id']}《{action['quest']}》")
        elif kind == "SERVICE":
            qids = "/".join(str(v) for v in action["quests"])
            rows.append(
                f"   - 做：{action['entity']}（实体 {action['entity_id']}；推进 {qids}；预计 {fmt(action['service_cost'])}）"
            )
        elif kind == "COMPLETE":
            rows.append(f"   - 完成：{action['quest_id']}《{action['quest']}》")
        elif kind == "TURNIN":
            rows.append(f"   - 交：{action['quest_id']}《{action['quest']}》")
    return rows


def main() -> None:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    meta = profiles["meta"]

    model = build_compressed_model(
        atlas,
        QUEST_IDS,
        start_xy=START_XY,
        start_name=START_NAME,
        service_weight=0.0,
        accept_turnin_cost=0.0,
        task_profiles=profiles,
        x_units_to_yards=float(meta["map_width_yards"]) / 100.0,
        y_units_to_yards=float(meta["map_height_yards"]) / 100.0,
        travel_speed_yards_per_sec=float(meta["travel_speed_yards_per_sec_assumption"]),
    )
    result = ExactSolver(model).solve()

    payload = {
        "meta": {
            "model": "Route Atlas exact v1 materialized-seconds validation",
            "mother_model": "Precedence-Constrained Shortest Path (PC-SP)",
            "zone_id": atlas["meta"]["zone_id"],
            "zone_name": atlas["meta"]["zone_name"],
            "questie_version": atlas["meta"]["questie_version"],
            "questie_sha256": atlas["meta"]["questie_sha256"],
            "quest_ids": QUEST_IDS,
            "start_xy": list(START_XY),
            "start_name": START_NAME,
            "time_unit": "seconds",
            "travel_model": meta["travel_model"],
            "kill_model": meta["kill_model"],
            "drop_model": meta["drop_model"],
            "respawn_proxy_available": meta.get("respawn_proxy_available"),
            "respawn_proxy_meta": meta.get("respawn_proxy_meta"),
            "proof_scope": (
                "PROVEN_OPTIMAL is only for this selected 8-quest compressed deterministic seconds model. "
                "Questie point-cloud entities are represented by one representative service point; terrain is ignored; "
                "service times are materialized task-profile estimates, not Titan observed ground truth."
            ),
        },
        "result": {
            "status": result.status,
            "total_seconds": result.total_cost,
            "travel_seconds": result.travel_cost,
            "service_seconds": result.service_cost,
            "expanded_states": result.expanded_states,
            "route": result.route,
        },
        "model": {
            "locations": {k: vars(v) for k, v in model.locations.items()},
            "quests": {str(k): vars(v) for k, v in model.quests.items()},
            "requirements": {k: vars(v) for k, v in model.requirements.items()},
        },
    }
    OUTPUT.write_text(json.dumps(round_obj(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# 赞加沼泽全局优化 v1：统一秒级成本精确验证",
        "",
        "## 结论",
        "",
        f"- 求解状态：`{result.status}`。",
        f"- 当前8任务压缩模型总预计时间：**{fmt(result.total_cost)}**（{result.total_cost:.2f}秒）。",
        f"- 其中移动：**{fmt(result.travel_cost)}**；目标执行/接交闭包：**{fmt(result.service_cost)}**。",
        f"- 搜索状态：{result.expanded_states}。",
        "- 与v0不同，本版统一使用秒：地图比例坐标→码→骑乘时间；打怪/掉落使用任务数据层已经物化的秒级成本。",
        "- Questie前置字段已按实际schema修正：12=preQuestGroup，13=preQuestSingle。",
        "",
        "## 证明边界",
        "",
        "这里的 `PROVEN_OPTIMAL` 只表示：在当前8任务、当前代表点、平面直线移动、当前物化耗时参数组成的数学模型中，没有总预计秒数更低的可行顺序。它不等于Titan现场真实8任务绝对最快时间。",
        "",
        "## 最优动作序列",
        "",
    ]
    report.extend(summarize_route(result.route))
    report.extend([
        "",
        "## 下一步",
        "",
        "全图70+任务不再用裸Dijkstra直接扩展。保留本v1作为秒级成本/前置/共享服务正确性的精确回归基线；下一层改用可分解的精确优化模型（CP-SAT/MIP/branch-and-bound with lower bounds），再把全部可用赞加任务放入同一个全局目标。",
        "",
    ])
    REPORT.write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({
        "status": result.status,
        "total_seconds": round(result.total_cost, 3),
        "travel_seconds": round(result.travel_cost, 3),
        "service_seconds": round(result.service_cost, 3),
        "expanded_states": result.expanded_states,
        "output": str(OUTPUT),
        "report": str(REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
