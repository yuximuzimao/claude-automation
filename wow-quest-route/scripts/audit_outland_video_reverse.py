from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie

ROUTES = ROOT / "data" / "route-atlas" / "workbench-routes.json"
VIDEO_MAPS = ROOT / "data" / "video-route" / "map-reference-blocks.json"
QUESTIE = ROOT / "_sandbox" / "sources" / "Questie-v11.32.3.zip"
OUT = ROOT / "data" / "video-route" / "outland-route-reverse-audit.json"
REPORT = ROOT / "docs" / "archive" / "analysis" / "video-route-outland-reverse-audit.md"

MAPS = {
    "zang": {"zone_id": 3521, "name": "赞加沼泽", "size": (5027.0835, 3352.0833)},
    "nagrand": {"zone_id": 3518, "name": "纳格兰", "size": (5525.0, 3683.3333)},
}

# These are not inferred from video. They are project decisions/validated historical facts.
MANUAL_CLASS = {
    "zang": {
        9912: ("conditional_inbound_restore", "旧R61明确要求：从地狱火携带时在塞纳里奥开场自然交付。"),
        9752: ("confirmed_route_omission_restored", "旧R45明确要求最终从零版补回；2026-08-20用户确认所有护送一次可五号共同完成。"),
        9802: ("confirmed_background_omission_restored", "旧R52明确要求开场接取、自然累计、够10株才顺手交，不专门刷。"),
        9782: ("video_alliance_only", "起止NPC守备官伊达尔为Alliance。"),
        9781: ("video_alliance_only", "起止NPC海尔伦为Alliance。"),
        9901: ("video_alliance_only", "Quest race mask excludes Blood Elf。"),
    },
    "nagrand": {
        9928: ("not_available_from_current_sprint_state", "部落需先沿泰罗卡/加拉达尔前置推进到10107《外交手段》后才自然进入兰特瑞索任务块；当前赞加→纳格兰冲刺状态不具备该前置。"),
        9927: ("not_available_from_current_sprint_state", "同兰特瑞索任务块；当前路线没有9889→9890→9891→9906→9907→10107前置。"),
        9931: ("not_available_from_current_sprint_state", "9928后续；当前路线没有兰特瑞索前置链。"),
        9932: ("not_available_from_current_sprint_state", "9927后续；当前路线没有兰特瑞索前置链。"),
        9818: ("intentional_sprint_exclusion_off_axis_chain", "元素王座任务中心位于当前冲刺主轴外，且此任务本身只是开启戈达乌连续链；当前实跑已在第二轮狩猎后到68。"),
        9861: ("intentional_sprint_exclusion_off_axis_chain", "元素王座支线入口；需要专门进入元素王座任务块，不属于当前67→68共享狩猎主轴。"),
        9800: ("intentional_sprint_exclusion_off_axis_chain", "元素王座连续任务入口，后续9804→9805→9810；整块需要额外Hub往返，当前冲刺不展开。"),
        9815: ("intentional_sprint_exclusion_off_axis_chain", "元素王座独立收集任务；任务中心约631码偏离当前停靠点，当前共享狩猎已足够到68。"),
        9819: ("intentional_sprint_exclusion_off_axis_chain", "元素王座戈达乌链，前置9818；当前冲刺不进入该链。"),
        9804: ("intentional_sprint_exclusion_off_axis_chain", "元素王座鲁艾普链，前置9800；当前冲刺不进入该链。"),
        9805: ("intentional_sprint_exclusion_off_axis_chain", "元素王座鲁艾普链，前置9804；当前冲刺不进入该链。"),
        9862: ("intentional_sprint_exclusion_off_axis_chain", "元素王座莫格链，前置9861；当前冲刺不进入该链。"),
        9821: ("intentional_sprint_exclusion_off_axis_chain", "元素王座戈达乌链，前置9819；当前冲刺不进入该链。"),
        9849: ("intentional_sprint_exclusion_off_axis_chain", "元素王座戈达乌后段，前置9821且需击杀30个目标；即使经验较高，也不是当前到68的低边际成本补充。"),
        9810: ("intentional_sprint_exclusion_off_axis_chain", "元素王座鲁艾普后段，前置9805；当前冲刺不进入该链。"),
        9853: ("intentional_sprint_exclusion_off_axis_chain", "元素王座戈达乌终段，必须先完成9818→9819→9821→9849；不能按单个34900经验任务看待。"),
        9991: ("not_available_or_off_axis_prechain", "奥图里斯位于当前主轴西侧约1033码，且任务需要9982/9983前置；当前状态不具备。"),
        9999: ("not_available_or_off_axis_prechain", "前置9991，而9991又依赖9982/9983；同时奥图里斯任务块远离当前冲刺主轴。"),
        10001: ("not_available_or_off_axis_prechain", "前置9999；属于奥图里斯西部连续任务块，不是当前冲刺可独立拿取的24000经验。"),
        9914: ("intentional_sprint_exclusion_fivebox_loot_detour", "象牙虽为野生雷象100%掉落，但每号需要3对，五开实际尸体拾取/分配成本尚未证明可压到共享击杀任务以下；任务Hub还在当前路线外约560码。当前不替换已实跑稳定的第二轮狩猎。"),
        10109: ("defer_speed_optimization_candidate", "瓦萨特只增加约0.43分钟路线偏移，任务经验22600；但每号3个气元素实体、80%掉率的五开拾取成本尚未实测。与10111合计50900经验，保留为未来压缩41分钟冲刺的专项替代候选，不直接改当前基线。"),
        10111: ("defer_speed_optimization_candidate", "10109后续，单号视频目标阶段约40秒，但五号弹射/鸟蛋交互成本不能从单号外推。与10109成包评估，当前证据不足以证明优于第二轮共享狩猎。"),
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_ids(table: Any) -> list[int]:
    out: list[int] = []
    if isinstance(table, int):
        return [table]
    if isinstance(table, dict):
        for value in table.values():
            out.extend(flatten_ids(value))
    elif isinstance(table, list):
        for value in table:
            out.extend(flatten_ids(value))
    return out


def map_points_for_npc(questie: Any, npc_id: int, zone_id: int) -> list[tuple[float, float]]:
    npc = questie.npcs.get(npc_id) or {}
    coords = (npc.get(7) or {}).get(zone_id)
    result: list[tuple[float, float]] = []
    if isinstance(coords, dict):
        for row in coords.values():
            if not isinstance(row, dict):
                continue
            x, y = row.get(1), row.get(2)
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                result.append((float(x), float(y)))
    return result


def npc_ids_from_side(side: Any) -> list[int]:
    if not isinstance(side, dict):
        return []
    npc_table = side.get(1)
    return [x for x in flatten_ids(npc_table) if isinstance(x, int)]


def faction_allowed(questie: Any, q: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    race_mask = q.get(6) or 0
    race_allowed = race_mask == 0 or bool(int(race_mask) & 512)
    start_npcs = npc_ids_from_side(q.get(2))
    end_npcs = npc_ids_from_side(q.get(3))

    def side_allowed(ids: list[int]) -> tuple[bool, list[dict[str, Any]]]:
        rows = []
        if not ids:
            return True, rows
        allowed = False
        for npc_id in ids:
            npc = questie.npcs.get(npc_id) or {}
            faction = npc.get(13)
            rows.append({"npc_id": npc_id, "faction": faction})
            if faction != "A":
                allowed = True
        return allowed, rows

    start_ok, start_rows = side_allowed(start_npcs)
    end_ok, end_rows = side_allowed(end_npcs)
    return race_allowed and start_ok and end_ok, {
        "race_mask": race_mask,
        "race_allowed": race_allowed,
        "start_npcs": start_rows,
        "end_npcs": end_rows,
    }


def route_action_names(route: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for point in route.get("points", []):
        text = str(point[3])
        for clause in re.split(r"[；。]", text):
            if "不接《" in clause or "放弃《" in clause:
                continue
            for name in re.findall(r"《([^》]+)》", clause):
                names.add(name)
    return names


def distance_yards(a: tuple[float, float], b: tuple[float, float], size: tuple[float, float]) -> float:
    dx = (b[0] - a[0]) / 100 * size[0]
    dy = (b[1] - a[1]) / 100 * size[1]
    return math.hypot(dx, dy)


def min_route_distance(points: list[tuple[float, float]], route_points: list[tuple[float, float]], size: tuple[float, float]) -> float | None:
    if not points:
        return None
    return min(distance_yards(p, r, size) for p in points for r in route_points)


def quest_xp_proxy(questie: Any, qid: int) -> int | None:
    row = questie.quest_xp.get(qid)
    if isinstance(row, dict):
        base = row.get(2)
        if isinstance(base, (int, float)):
            return int(round(float(base) * 2))
    return None


def audit_map(key: str, spec: dict[str, Any], routes: dict[str, Any], video_by_zone: dict[int, dict[str, Any]], questie: Any) -> dict[str, Any]:
    route = routes[key]
    route_names = route_action_names(route)
    route_points = [(float(p[0]), float(p[1])) for p in route.get("points", [])]
    video = video_by_zone[spec["zone_id"]]
    candidates: list[dict[str, Any]] = []
    common: list[dict[str, Any]] = []

    for order, event in enumerate(video["completion_sequence_first_by_quest_id"], 1):
        qid = int(event["quest_id"])
        name = str(event.get("quest_name") or qid)
        if name in route_names:
            common.append({"quest_id": qid, "quest_name": name, "video_order": order})
            continue
        q = questie.quests.get(qid) or {}
        allowed, faction_detail = faction_allowed(questie, q)
        repeatable = bool(int(q.get(24) or 0) & 1)
        start_npcs = npc_ids_from_side(q.get(2))
        end_npcs = npc_ids_from_side(q.get(3))
        start_points = [pt for npc_id in start_npcs for pt in map_points_for_npc(questie, npc_id, spec["zone_id"])]
        end_points = [pt for npc_id in end_npcs for pt in map_points_for_npc(questie, npc_id, spec["zone_id"])]
        start_distance = min_route_distance(start_points, route_points, spec["size"])
        end_distance = min_route_distance(end_points, route_points, spec["size"])
        video_xp = event.get("experience") if isinstance(event.get("experience"), (int, float)) else None
        manual = MANUAL_CLASS.get(key, {}).get(qid)
        row = {
            "quest_id": qid,
            "quest_name": name,
            "video_order": order,
            "video_episode": event["episode"],
            "video_xp": video_xp,
            "questie_2x_xp_proxy": quest_xp_proxy(questie, qid),
            "blood_elf_and_npc_faction_allowed": allowed,
            "faction_detail": faction_detail,
            "repeatable": repeatable,
            "required_level": q.get(4),
            "quest_level": q.get(5),
            "pre_quest": q.get(13),
            "next_quest": q.get(22),
            "start_distance_to_route_yards": round(start_distance, 1) if start_distance is not None else None,
            "end_distance_to_route_yards": round(end_distance, 1) if end_distance is not None else None,
            "manual_class": manual[0] if manual else None,
            "manual_reason": manual[1] if manual else None,
        }
        if manual:
            row["class"] = manual[0]
        elif not allowed:
            row["class"] = "video_faction_only"
        elif repeatable:
            row["class"] = "repeatable_not_automatic_omission"
        elif (start_distance is not None and start_distance <= 350) or (end_distance is not None and end_distance <= 350):
            row["class"] = "route_overlap_review"
        else:
            row["class"] = "off_route_or_chain_review"
        candidates.append(row)

    class_counts: dict[str, int] = {}
    for row in candidates:
        class_counts[row["class"]] = class_counts.get(row["class"], 0) + 1
    return {
        "map": spec["name"],
        "zone_id": spec["zone_id"],
        "route_task_action_name_count": len(route_names),
        "video_first_completion_count": len(video["completion_sequence_first_by_quest_id"]),
        "common_count": len(common),
        "candidate_count": len(candidates),
        "candidate_class_counts": class_counts,
        "common": common,
        "video_only_candidates": candidates,
    }


def main() -> None:
    routes = load_json(ROUTES)
    video_maps = load_json(VIDEO_MAPS)
    video_by_zone = {int(m["zone_id"]): m for m in video_maps["maps"]}
    questie = load_questie(QUESTIE)
    result = {
        "schema": "outland-video-reverse-audit-v1",
        "purpose": "route_reference_and_correction_only",
        "maps": {key: audit_map(key, spec, routes, video_by_zone, questie) for key, spec in MAPS.items()},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    z = result["maps"]["zang"]
    n = result["maps"]["nagrand"]
    n_overlap = [x for x in n["video_only_candidates"] if x["class"] == "route_overlap_review"]
    n_overlap.sort(key=lambda x: (x["start_distance_to_route_yards"] if x["start_distance_to_route_yards"] is not None else 10**9, -(x["video_xp"] or x["questie_2x_xp_proxy"] or 0)))
    lines = [
        "# 外域当前正式路线视频反向审计",
        "",
        "用途仅限本项目路线参考/纠错；视频不是上位真值。",
        "",
        "## 赞加沼泽",
        "",
        f"- 视频首次完成任务：{z['video_first_completion_count']}；与当前玩家动作共同任务：{z['common_count']}。",
        "- 视频独有项复查后，9912入口交付、9752护送、9802背景库存三项确认是当前工作台迁移遗漏，已恢复；9782、9781、9901属于联盟限定，不进入部落路线。",
        "- 9752保留依据：一次五号共同护送；视频护送约230秒，而本来必需的暗泽村→塞纳里奥回程约59秒，新增约171秒换20800经验，边际效率成立。",
        "",
        "## 纳格兰",
        "",
        f"- 视频首次完成任务：{n['video_first_completion_count']}；与当前67→68冲刺路线共同任务：{n['common_count']}；视频独有候选：{n['candidate_count']}。",
        "- 纳格兰当前路线的目标不是全清，而是从赞加结束状态最快补到68；因此视频独有任务不能按‘漏项’直接补回，只把与现有停靠点高度重叠的任务送入下一层边际成本复查。",
        "",
        "### 与当前路线Hub/停靠点距离较近、需要人工复查的候选",
        "",
    ]
    for row in n_overlap:
        xp = row["video_xp"] or row["questie_2x_xp_proxy"]
        lines.append(
            f"- `{row['quest_id']}`《{row['quest_name']}》：起点距当前路线约{row['start_distance_to_route_yards']}码，"
            f"终点约{row['end_distance_to_route_yards']}码，视频/2×代理经验{xp}；前置{row['pre_quest']}，后续{row['next_quest']}。"
        )
    lines += [
        "",
        "这些候选仍不是自动纳入项；下一步只对它们检查目标区与当前三轮狩猎/吉塞尔达/佐尔布的真实重叠，以及接取后是否会拖慢到68。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "zang": {"common": z["common_count"], "classes": z["candidate_class_counts"]},
        "nagrand": {"common": n["common_count"], "classes": n["candidate_class_counts"], "route_overlap_review": [
            {"quest_id": x["quest_id"], "name": x["quest_name"], "start_yards": x["start_distance_to_route_yards"], "end_yards": x["end_distance_to_route_yards"], "xp": x["video_xp"] or x["questie_2x_xp_proxy"]}
            for x in n_overlap
        ]},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
