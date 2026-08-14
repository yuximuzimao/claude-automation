from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_atlas_exact import ExactSolver, build_compressed_model

INPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-opt-v0.json"
REPORT = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-global-opt-v0-result.md"

# East-side non-toy prototype: three chains plus standalone/background tasks.
QUEST_IDS = [
    9747, 9788,  # 暗泽部族 -> 阴冷之地
    9895,        # 崩溃的平衡
    9773, 9899,  # 别再提蘑菇了！ -> 未完的职责
    9769,        # 时尚无罪（广域掉落）
    9770, 9898,  # 沼牙的威胁 -> 对方的尊重
]

# Start at the Cenarion Refuge anchor already validated against in-game Questie.
START_XY = (78.40, 62.02)
START_NAME = "塞纳里奥庇护所（伊谢尔·风歌锚点）"
SERVICE_WEIGHTS = [0.0, 0.25, 1.0]


def round_obj(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [round_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: round_obj(v) for k, v in value.items()}
    return value


def route_signature(route: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for a in route:
        if a["type"] == "MOVE":
            out.append(f"M:{a['to']}")
        elif a["type"] == "SERVICE":
            out.append(f"S:{a['entity_id']}")
        elif a["type"] in ("ACCEPT", "TURNIN"):
            out.append(f"{a['type'][0]}:{a['quest_id']}")
    return out


def summarize_route(route: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    step = 0
    for action in route:
        kind = action["type"]
        if kind == "MOVE":
            if action["distance"] <= 1e-9:
                continue
            step += 1
            rows.append(
                f"{step}. 移动：{action['from_name']} → {action['to_name']} "
                f"（代理距离 {action['distance']:.2f}）"
            )
        elif kind == "ACCEPT":
            rows.append(f"   - 接：{action['quest_id']}《{action['quest']}》")
        elif kind == "SERVICE":
            quest_ids = "/".join(str(q) for q in action["quests"])
            rows.append(
                f"   - 做：{action['entity']}（实体 {action['entity_id']}；推进任务 {quest_ids}）"
            )
        elif kind == "COMPLETE":
            rows.append(f"   - 完成：{action['quest_id']}《{action['quest']}》")
        elif kind == "TURNIN":
            rows.append(f"   - 交：{action['quest_id']}《{action['quest']}》")
    return rows


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    signatures: list[list[str]] = []
    base_model = None

    for weight in SERVICE_WEIGHTS:
        model = build_compressed_model(
            data,
            QUEST_IDS,
            start_xy=START_XY,
            start_name=START_NAME,
            service_weight=weight,
            accept_turnin_cost=0.0,
        )
        base_model = model
        result = ExactSolver(model).solve()
        signature = route_signature(result.route)
        signatures.append(signature)
        runs.append(
            {
                "service_weight": weight,
                "status": result.status,
                "total_proxy_cost": result.total_cost,
                "travel_proxy_cost": result.travel_cost,
                "service_proxy_cost": result.service_cost,
                "expanded_states": result.expanded_states,
                "route": result.route,
                "signature": signature,
            }
        )
        print(
            f"weight={weight:.2f} status={result.status} total={result.total_cost:.3f} "
            f"travel={result.travel_cost:.3f} service={result.service_cost:.3f} "
            f"states={result.expanded_states} actions={len(result.route)}"
        )

    assert base_model is not None
    stable = all(sig == signatures[0] for sig in signatures[1:])
    payload = {
        "meta": {
            "model": "RA-SPCSSP compressed deterministic exact v0",
            "mother_model": "Precedence-Constrained Shortest Path (PC-SP)",
            "zone_id": data["meta"]["zone_id"],
            "zone_name": data["meta"]["zone_name"],
            "questie_version": data["meta"]["questie_version"],
            "questie_sha256": data["meta"]["questie_sha256"],
            "quest_ids": QUEST_IDS,
            "start_xy": list(START_XY),
            "start_name": START_NAME,
            "proof_scope": (
                "PROVEN_OPTIMAL applies only to this compressed v0 proxy-cost model: one representative point per service entity; "
                "each objective requirement is completed in one service action; direct-line map-percent movement; deterministic service cost."
            ),
            "not_real_minutes": True,
            "sensitivity_route_signature_stable": stable,
        },
        "model": {
            "locations": {k: vars(v) for k, v in base_model.locations.items()},
            "quests": {str(k): vars(v) for k, v in base_model.quests.items()},
            "requirements": {k: vars(v) for k, v in base_model.requirements.items()},
        },
        "runs": runs,
    }
    OUTPUT.write_text(json.dumps(round_obj(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    best = runs[0]
    report: list[str] = [
        "# 赞加沼泽全局优化 v0：首个精确求解结果",
        "",
        "## 结论",
        "",
        f"- 求解状态：`{best['status']}`，但只对当前压缩代理成本模型成立；不是实际分钟最优证明。",
        f"- 任务数：{len(QUEST_IDS)}；逻辑 Objective requirement：{len(base_model.requirements)}；物理候选位置：{len(base_model.locations)}。",
        f"- 服务权重敏感性：`{SERVICE_WEIGHTS}`；完整动作签名是否完全一致：`{stable}`。",
        f"- weight=0 的最优旅行代理成本：`{best['travel_proxy_cost']:.3f}` Questie 地图百分点距离单位。",
        f"- Dijkstra 展开状态数：`{best['expanded_states']}`。",
        "",
        "## 当前精确模型包含",
        "",
        "- A/C/T 链式解锁；",
        "- Questie `preQuestSingle` OR 与 `preQuestGroup` AND 字段分离；",
        "- direct objective 与 item→NPC/Object 来源；",
        "- 同实体 shared-service：一次服务可以同时完成多个已接任务 requirement；",
        "- item objective 的多个掉落来源作为可选 service location；",
        "- 重复访问 Hub；不预先规定圈数。",
        "",
        "## 当前仍是压缩代理模型",
        "",
        "- 每个怪/Object实体用其点云中靠近中心的一个真实 Questie 点代表；",
        "- 一个 requirement 视为在一个候选实体处一次性完成；数量只进入 service proxy cost；",
        "- 移动成本使用 Questie 坐标直线距离，不是道路/地形/秒级骑乘时间；",
        "- 掉率仍未进入真实期望击杀数；",
        "- Titan effective corrections 尚未完整解析。",
        "",
        "因此 `PROVEN_OPTIMAL` 的准确含义是：**在上述 v0 压缩模型中，已经证明没有代理成本更低的路线。**",
        "",
        "## weight=0 最优动作路线",
        "",
    ]
    report.extend(summarize_route(best["route"]))
    report.extend([
        "",
        "## 下一步",
        "",
        "先不增加人工路线规则。把移动代理成本替换为可校准的 travel-time network，并把 requirement 一次性完成压缩逐步替换为真实数量/掉率/共享击杀成本；每扩一层后重新 exact solve，比较最优路线是否改变。",
        "",
    ])
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"stable_signature={stable}")
    print(f"output={OUTPUT}")
    print(f"report={REPORT}")


if __name__ == "__main__":
    main()
