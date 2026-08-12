from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from lib.questie_source import load_questie

ROOT = Path(__file__).resolve().parents[1]
QUESTIE_ZIP = ROOT / "_sandbox/sources/Questie-v11.32.3.zip"
ROUTE_JSON = ROOT / "data/routes/world-candidate/3483-hellfire-peninsula/route.json"
OUT_JSON = ROOT / "data/routes/horde/blood-elf/hellfire-chain-round-overlap.json"
OUT_MD = ROOT / "docs/analysis/2026-08-11-hellfire-chain-round-overlap.md"

HELLFIRE = 3483
BLOOD_ELF = 512
PALADIN = 2
THRALLMAR_REP = 947
HONOR_HOLD_REP = 946

# Current 58->68 open-world pass: keep only normal outdoor leveling content.
MANUAL_EXCLUDE = {
    13409: "PvP任务《地狱火半岛的工事》",
    9588: "触发物来自地狱火城墙副本瓦兹德",
    10755: "68级后70级锻造/钥匙残局",
    10756: "68级后70级残局",
    10757: "68级后70级残局",
    10758: "68级后70级残局",
    11003: "70级玛瑟里顿团队副本",
    10046: "旧/特殊入口版本《跨越黑暗之门》；不进入时光服保证路线",
    10207: "REUSE占位版本《前线基地：劫夺者荒野》；不进入时光服保证路线",
    10150: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10151: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10153: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10154: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10155: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10059: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10060: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10156: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10157: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10061: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10062: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10152: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10158: "当前TBC主路线无可靠接取来源；时光服待现场验证",
    10214: "当前TBC主路线无可靠接取来源；时光服待现场验证",
}

CHAIN_NAME_OVERRIDES = {
    9407: "萨尔玛主线／燃烧军团／玛格汉",
    10450: "断背岗哨药剂师线",
    10154: "塞斯高渗透／刺杀线",
    9374: "埃雷利恩日记线",
    10229: "神秘典籍／血之复仇线",
    10236: "外域烂地方／矿洞地精线",
    10403: "纳拉杜／残冠长者线",
    10809: "座狼主宰／格里洛克线",
    9499: "猎鹰岗哨／大裂隙线",
    9349: "飞艇坠毁点食材线",
    10442: "塞纳里奥哨站解毒线",
    10134: "火红水晶线",
    10278: "迁跃裂隙线",
    9345: "准备药膏／坠毁点调查线",
    10161: "坠毁点虚空行者线",
    9366: "邪恶之血／阻止净化线",
    9375: "猎鹰岗哨朝圣线",
    10061: "远征军械库阴魂线",
    10086: "部落烧毁任务线",
    10131: "联盟版逃脱线（应被阵营过滤）",
}


def seq(value: Any) -> list[Any]:
    if not isinstance(value, dict):
        return []
    keys = sorted(k for k in value if isinstance(k, int))
    return [value[k] for k in keys]


def quest_name(data: Any, qid: int) -> str:
    row = data.quest_names.get(qid)
    if isinstance(row, dict) and isinstance(row.get(1), str):
        return row[1]
    raw = data.quests.get(qid, {})
    return raw.get(1) if isinstance(raw, dict) and isinstance(raw.get(1), str) else f"Quest {qid}"


def npc_name(data: Any, npc_id: int) -> str:
    row = data.npc_names.get(npc_id)
    if isinstance(row, dict) and isinstance(row.get(1), str):
        return row[1]
    raw = data.npcs.get(npc_id, {})
    return raw.get(1) if isinstance(raw, dict) and isinstance(raw.get(1), str) else f"NPC {npc_id}"


def object_name(data: Any, object_id: int) -> str:
    row = data.object_names.get(object_id)
    if isinstance(row, dict) and isinstance(row.get(1), str):
        return row[1]
    raw = data.objects.get(object_id, {})
    return raw.get(1) if isinstance(raw, dict) and isinstance(raw.get(1), str) else f"Object {object_id}"


def reputation_factions(raw: dict[Any, Any]) -> set[int]:
    out: set[int] = set()
    for row in seq(raw.get(26)):
        if isinstance(row, dict) and isinstance(row.get(1), int):
            out.add(row[1])
    return out


def eligible(data: Any, qid: int) -> tuple[bool, str | None]:
    raw = data.quests.get(qid)
    if not isinstance(raw, dict):
        return False, "数据库无任务"
    name = quest_name(data, qid)
    if qid in MANUAL_EXCLUDE:
        return False, MANUAL_EXCLUDE[qid]
    if name == "DEPRECATED" or "UNUSED" in name.upper():
        return False, "废弃/未使用"
    races = raw.get(6)
    classes = raw.get(7)
    if isinstance(races, int) and races not in (0,) and not (races & BLOOD_ELF):
        return False, "非血精灵阵营任务"
    if isinstance(classes, int) and classes not in (0,) and not (classes & PALADIN):
        return False, "非圣骑士职业任务"
    reps = reputation_factions(raw)
    if HONOR_HOLD_REP in reps and THRALLMAR_REP not in reps:
        return False, "荣耀堡/联盟版本"
    if isinstance(raw.get(24), int) and raw.get(24) & 1:
        return False, "可重复任务"
    if isinstance(raw.get(4), int) and raw.get(4) >= 68:
        return False, "68级前不可接"
    if isinstance(raw.get(5), int) and raw.get(5) >= 69:
        return False, "69+/70级残局"
    return True, None


def relation_ids(raw: dict[Any, Any]) -> set[int]:
    out: set[int] = set()
    for key in (12, 13, 14):
        for value in seq(raw.get(key)):
            if isinstance(value, int):
                out.add(value)
    if isinstance(raw.get(22), int):
        out.add(raw[22])
    return out


def item_sources(data: Any, item_id: int) -> tuple[set[int], set[int]]:
    raw = data.items.get(item_id, {})
    npcs: set[int] = set()
    objects: set[int] = set()
    # Questie item DB: 2=npcDrops, 3=objectDrops.
    for value in seq(raw.get(2) if isinstance(raw, dict) else None):
        if isinstance(value, int):
            npcs.add(value)
    for value in seq(raw.get(3) if isinstance(raw, dict) else None):
        if isinstance(value, int):
            objects.add(value)
    return npcs, objects


def entity_points(data: Any, entity_type: str, entity_id: int) -> list[tuple[float, float]]:
    raw = data.npcs.get(entity_id, {}) if entity_type == "npc" else data.objects.get(entity_id, {})
    if not isinstance(raw, dict):
        return []
    spawns = raw.get(7 if entity_type == "npc" else 2)
    if not isinstance(spawns, dict):
        return []
    zone_rows = spawns.get(HELLFIRE)
    if not isinstance(zone_rows, dict):
        return []
    out: list[tuple[float, float]] = []
    for point in seq(zone_rows):
        if isinstance(point, dict) and isinstance(point.get(1), (int, float)) and isinstance(point.get(2), (int, float)):
            x, y = float(point[1]), float(point[2])
            if 0 <= x <= 100 and 0 <= y <= 100:
                out.append((x, y))
    return out


def recursive_ints(value: Any) -> set[int]:
    out: set[int] = set()
    if isinstance(value, int):
        out.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            out |= recursive_ints(item)
    return out


def task_targets(data: Any, qid: int) -> dict[str, Any]:
    raw = data.quests.get(qid, {})
    mobs: set[int] = set()
    objects: set[int] = set()
    trigger_mobs: set[int] = set()
    trigger_objects: set[int] = set()
    points: list[tuple[float, float]] = []

    objectives = raw.get(10) if isinstance(raw, dict) else None
    if isinstance(objectives, dict):
        creature_rows = objectives.get(1)
        if isinstance(creature_rows, dict):
            for row in seq(creature_rows):
                if isinstance(row, dict) and isinstance(row.get(1), int):
                    mobs.add(row[1])
        object_rows = objectives.get(2)
        if isinstance(object_rows, dict):
            for row in seq(object_rows):
                if isinstance(row, dict) and isinstance(row.get(1), int):
                    objects.add(row[1])
        item_rows = objectives.get(3)
        if isinstance(item_rows, dict):
            for row in seq(item_rows):
                if isinstance(row, dict) and isinstance(row.get(1), int):
                    npc_sources, object_sources = item_sources(data, row[1])
                    mobs |= npc_sources
                    objects |= object_sources
        # killCreditObjective often contains creature IDs nested inside row structure.
        kill_credit = objectives.get(5)
        if isinstance(kill_credit, dict):
            for row in seq(kill_credit):
                ints = recursive_ints(row)
                for candidate in ints:
                    if candidate in data.npcs:
                        mobs.add(candidate)

    # Item-start quests: the dropped item acquisition itself is a practical target for overlap.
    started_by = raw.get(2) if isinstance(raw, dict) else None
    if isinstance(started_by, dict):
        item_starts = started_by.get(3)
        for item_id in seq(item_starts):
            if isinstance(item_id, int):
                npc_sources, object_sources = item_sources(data, item_id)
                trigger_mobs |= npc_sources
                trigger_objects |= object_sources

    for mob in sorted(mobs | trigger_mobs):
        points.extend(entity_points(data, "npc", mob))
    for obj in sorted(objects | trigger_objects):
        points.extend(entity_points(data, "object", obj))

    trigger_end = raw.get(9) if isinstance(raw, dict) else None
    if isinstance(trigger_end, dict):
        zone_map = trigger_end.get(2)
        if isinstance(zone_map, dict) and isinstance(zone_map.get(HELLFIRE), dict):
            for point in seq(zone_map[HELLFIRE]):
                if isinstance(point, dict) and isinstance(point.get(1), (int, float)) and isinstance(point.get(2), (int, float)):
                    points.append((float(point[1]), float(point[2])))

    # Deduplicate rounded points; hundreds of raw spawns are not useful downstream.
    unique_points = sorted({(round(x, 2), round(y, 2)) for x, y in points})
    return {
        "mobs": sorted(mobs),
        "objects": sorted(objects),
        "trigger_mobs": sorted(trigger_mobs),
        "trigger_objects": sorted(trigger_objects),
        "points": unique_points,
    }


def min_point_distance(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> tuple[float | None, tuple[float, float] | None]:
    if not a or not b:
        return None, None
    best = float("inf")
    best_mid = None
    # Spawn lists are small enough here; cap to protect against pathological DB entries.
    aa = a[:250]
    bb = b[:250]
    for ax, ay in aa:
        for bx, by in bb:
            d = math.hypot(ax - bx, ay - by)
            if d < best:
                best = d
                best_mid = ((ax + bx) / 2, (ay + by) / 2)
    return best, best_mid


def round_assignment(data: Any, component: set[int]) -> dict[int, int]:
    incoming_next: dict[int, set[int]] = defaultdict(set)
    for qid in component:
        nxt = data.quests.get(qid, {}).get(22)
        if isinstance(nxt, int) and nxt in component:
            incoming_next[nxt].add(qid)

    memo: dict[int, int] = {}
    visiting: set[int] = set()

    def solve(qid: int) -> int:
        if qid in memo:
            return memo[qid]
        if qid in visiting:
            return 1
        visiting.add(qid)
        raw = data.quests.get(qid, {})
        hard = set(incoming_next.get(qid, set()))
        hard |= {x for x in seq(raw.get(12)) if isinstance(x, int) and x in component}
        singles = [x for x in seq(raw.get(13)) if isinstance(x, int) and x in component]
        candidates: list[int] = []
        if hard:
            candidates.append(max(solve(p) for p in hard) + 1)
        if singles:
            candidates.append(min(solve(p) for p in singles) + 1)
        result = max(candidates) if candidates else 1
        visiting.remove(qid)
        memo[qid] = result
        return result

    for qid in component:
        solve(qid)
    return memo


def component_name(data: Any, component: set[int], rounds: dict[int, int]) -> str:
    for key, name in CHAIN_NAME_OVERRIDES.items():
        if key in component:
            return name
    roots = sorted([qid for qid in component if rounds[qid] == 1])
    if roots:
        names = [quest_name(data, qid) for qid in roots[:2]]
        return "／".join(names)
    first = min(component)
    return quest_name(data, first)


def target_summary(data: Any, targets: dict[str, Any]) -> str:
    mob_ids = targets["mobs"] + [x for x in targets["trigger_mobs"] if x not in targets["mobs"]]
    object_ids = targets["objects"] + [x for x in targets["trigger_objects"] if x not in targets["objects"]]
    parts: list[str] = []
    if mob_ids:
        names = [npc_name(data, x) for x in mob_ids[:4]]
        if len(mob_ids) > 4:
            names.append(f"等{len(mob_ids)}种怪")
        parts.append("怪：" + "、".join(names))
    if object_ids:
        names = [object_name(data, x) for x in object_ids[:3]]
        if len(object_ids) > 3:
            names.append(f"等{len(object_ids)}种物体")
        parts.append("物：" + "、".join(names))
    pts = targets["points"]
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if max(xs) - min(xs) <= 8 and max(ys) - min(ys) <= 8:
            parts.append(f"约({sum(xs)/len(xs):.1f},{sum(ys)/len(ys):.1f})")
        else:
            parts.append(f"范围({min(xs):.1f}–{max(xs):.1f},{min(ys):.1f}–{max(ys):.1f})")
    return "；".join(parts) if parts else "对话/送信/数据库无野外目标坐标"


def main() -> None:
    data = load_questie(QUESTIE_ZIP)
    payload = json.loads(ROUTE_JSON.read_text(encoding="utf-8"))
    raw_candidate_ids = {int(row["quest_id"]) for row in payload["quest_catalog"]}
    # Questie world-candidate misses the valid item-trigger quest 《亚维鲁的宝珠》(9418).
    raw_candidate_ids.add(9418)

    excluded: dict[int, str] = {}
    task_ids: set[int] = set()
    for qid in raw_candidate_ids:
        ok, reason = eligible(data, qid)
        if ok:
            task_ids.add(qid)
        else:
            excluded[qid] = reason or "excluded"

    # Add omitted in-zone direct relatives, preserving all normal Horde/Blood-Elf leveling tasks.
    changed = True
    while changed:
        changed = False
        for qid in list(task_ids):
            raw = data.quests.get(qid, {})
            for related in relation_ids(raw):
                rr = data.quests.get(related, {})
                if not isinstance(rr, dict) or rr.get(17) != HELLFIRE or related in task_ids:
                    continue
                ok, reason = eligible(data, related)
                if ok:
                    task_ids.add(related)
                    changed = True
                elif reason:
                    excluded.setdefault(related, reason)

    # Undirected components for logical chain blocks.
    adjacency: dict[int, set[int]] = defaultdict(set)
    for qid in task_ids:
        raw = data.quests.get(qid, {})
        for related in relation_ids(raw):
            if related in task_ids:
                adjacency[qid].add(related)
                adjacency[related].add(qid)

    components: list[set[int]] = []
    seen: set[int] = set()
    for qid in sorted(task_ids):
        if qid in seen:
            continue
        stack = [qid]
        seen.add(qid)
        comp: set[int] = set()
        while stack:
            current = stack.pop()
            comp.add(current)
            for nxt in adjacency[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(comp)

    component_rows: list[dict[str, Any]] = []
    all_task_targets = {qid: task_targets(data, qid) for qid in task_ids}

    # Sort large/structural chains first, then stable by minimum id.
    components.sort(key=lambda c: (-len(c), min(c)))
    for index, comp in enumerate(components, start=1):
        rounds = round_assignment(data, comp)
        name = component_name(data, comp, rounds)
        round_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for qid in sorted(comp, key=lambda x: (rounds[x], x)):
            raw = data.quests.get(qid, {})
            target = all_task_targets[qid]
            external_pre = sorted({
                x
                for key in (12, 13)
                for x in seq(raw.get(key))
                if isinstance(x, int) and x not in comp
            })
            round_rows[rounds[qid]].append({
                "quest_id": qid,
                "name": quest_name(data, qid),
                "quest_level": raw.get(5),
                "required_level": raw.get(4),
                "external_prerequisites": external_pre,
                "targets": target,
                "target_summary": target_summary(data, target),
            })
        component_rows.append({
            "chain_id": f"HF{index:02d}",
            "name": name,
            "task_count": len(comp),
            "round_count": max(rounds.values()),
            "rounds": {str(k): v for k, v in sorted(round_rows.items())},
        })

    # Round nodes for cross-chain overlap matrix.
    nodes: list[dict[str, Any]] = []
    for chain in component_rows:
        for round_no_str, tasks in chain["rounds"].items():
            mobs: set[int] = set()
            objects: set[int] = set()
            points: list[tuple[float, float]] = []
            for task in tasks:
                t = task["targets"]
                mobs |= set(t["mobs"]) | set(t["trigger_mobs"])
                objects |= set(t["objects"]) | set(t["trigger_objects"])
                points.extend(tuple(x) for x in t["points"])
            nodes.append({
                "chain_id": chain["chain_id"],
                "chain_name": chain["name"],
                "round": int(round_no_str),
                "tasks": [(t["quest_id"], t["name"]) for t in tasks],
                "mobs": sorted(mobs),
                "objects": sorted(objects),
                "points": sorted(set(points)),
            })

    overlaps: list[dict[str, Any]] = []
    for i in range(len(nodes)):
        a = nodes[i]
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            if a["chain_id"] == b["chain_id"]:
                continue
            shared_mobs = sorted(set(a["mobs"]) & set(b["mobs"]))
            shared_objects = sorted(set(a["objects"]) & set(b["objects"]))
            dist, midpoint = min_point_distance(a["points"], b["points"])
            # High confidence: exact same target, or very close outdoor target coordinates.
            overlap_type = None
            confidence = None
            if shared_mobs:
                overlap_type = "同怪"
                confidence = "高"
            elif shared_objects:
                overlap_type = "同物体"
                confidence = "高"
            elif dist is not None and dist <= 2.5:
                overlap_type = "同区域"
                confidence = "中"
            if not overlap_type:
                continue
            overlaps.append({
                "a_chain": a["chain_id"],
                "a_name": a["chain_name"],
                "a_round": a["round"],
                "a_tasks": a["tasks"],
                "b_chain": b["chain_id"],
                "b_name": b["chain_name"],
                "b_round": b["round"],
                "b_tasks": b["tasks"],
                "type": overlap_type,
                "confidence": confidence,
                "shared_mobs": [(mid, npc_name(data, mid)) for mid in shared_mobs],
                "shared_objects": [(oid, object_name(data, oid)) for oid in shared_objects],
                "min_distance": round(dist, 2) if dist is not None else None,
                "midpoint": [round(midpoint[0], 1), round(midpoint[1], 1)] if midpoint else None,
            })

    overlaps.sort(key=lambda row: (
        0 if row["type"] == "同怪" else 1 if row["type"] == "同物体" else 2,
        row["a_chain"], row["a_round"], row["b_chain"], row["b_round"],
    ))

    output = {
        "scope": "Hellfire Peninsula, Horde Blood Elf Paladin, normal outdoor 58-68 pass",
        "source_candidate_count": len(raw_candidate_ids),
        "included_task_count": len(task_ids),
        "chain_count": len(component_rows),
        "excluded": {str(k): v for k, v in sorted(excluded.items())},
        "chains": component_rows,
        "cross_chain_overlaps": overlaps,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# 地狱火半岛：任务链轮次与跨链目标重叠表")
    lines.append("")
    lines.append("状态：首跑辅助分析，不是固定执行路线。范围为部落血精灵圣骑士58→68期间的正常开放世界地狱火任务；剔除联盟荣耀堡版本、PvP、可重复、副本触发、68级后70级残局、DEPRECATED/UNUSED。")
    lines.append("")
    lines.append("“第N轮”定义：同一任务链内，必须完成并交付上一轮后才能解锁的下一层。一个轮次可同时出现多个分支任务。跨链重叠分两类：`同怪`为数据库目标怪ID完全一致；`同区域`为两个任务目标刷新点最近距离≤2.5个地图坐标单位，只作为高价值聚合候选，首跑仍以游戏地图实际标记为准。")
    lines.append("")
    lines.append(f"- 原始地狱火候选：{len(raw_candidate_ids)}条。")
    lines.append(f"- 当前首跑有效任务：{len(task_ids)}条。")
    lines.append(f"- 合并为：{len(component_rows)}条任务链/独立任务。")
    lines.append(f"- 检出的跨链高/中置信重叠：{len(overlaps)}组。")
    lines.append("")

    lines.append("## 一、完整任务链与轮次")
    lines.append("")
    for chain in component_rows:
        lines.append(f"### {chain['chain_id']} {chain['name']}（{chain['task_count']}任务 / {chain['round_count']}轮）")
        lines.append("")
        for round_no_str, tasks in chain["rounds"].items():
            lines.append(f"- **第{round_no_str}轮**")
            for task in tasks:
                ext = ""
                if task["external_prerequisites"]:
                    ext_names = "、".join(f"《{quest_name(data, x)}》（{x}）" for x in task["external_prerequisites"])
                    ext = f"；外部前置：{ext_names}"
                lines.append(
                    f"  - 《{task['name']}》（{task['quest_id']}，ql{task['quest_level']}）：{task['target_summary']}{ext}"
                )
        lines.append("")

    lines.append("## 二、跨任务链重叠矩阵")
    lines.append("")
    lines.append("优先看`同怪`，其次看`同物体`，最后看`同区域`。同区域只是告诉你‘这两轮值得等一等一起去’，并不表示任务目标完全相同。")
    lines.append("")
    for row in overlaps:
        a_tasks = "、".join(f"《{name}》（{qid}）" for qid, name in row["a_tasks"])
        b_tasks = "、".join(f"《{name}》（{qid}）" for qid, name in row["b_tasks"])
        detail_parts: list[str] = []
        if row["shared_mobs"]:
            detail_parts.append("共同怪：" + "、".join(f"{name}({mid})" for mid, name in row["shared_mobs"]))
        if row["shared_objects"]:
            detail_parts.append("共同物体：" + "、".join(f"{name}({oid})" for oid, name in row["shared_objects"]))
        if row["midpoint"]:
            detail_parts.append(f"重叠位置约({row['midpoint'][0]},{row['midpoint'][1]})")
        if row["min_distance"] is not None and row["type"] == "同区域":
            detail_parts.append(f"最近目标距离{row['min_distance']}")
        detail = "；".join(detail_parts)
        lines.append(
            f"- **{row['type']}**：{row['a_chain']}第{row['a_round']}轮（{a_tasks}） ↔ "
            f"{row['b_chain']}第{row['b_round']}轮（{b_tasks}）{('；' + detail) if detail else ''}"
        )
    lines.append("")

    lines.append("## 三、现场使用规则")
    lines.append("")
    lines.append("1. 每次交任务后先看自己刚解锁到哪条链的第几轮。")
    lines.append("2. 查重叠矩阵：若新轮次与尚未完成的另一条链当前轮为`同怪`或`同区域`，优先等两边都可接后一起出发。")
    lines.append("3. 如果另一条链还差两三轮才能解锁，不为等待而停止当前高密度任务；首跑记录第二次回区成本，第二版再判断是否值得调整交付顺序。")
    lines.append("4. 单任务链内部连续回同一区域属于链设计本身；本表重点解决的是‘两个不同任务链本可合并却分两趟跑’。")
    lines.append("")
    lines.append(f"完整机器数据：`{OUT_JSON.relative_to(ROOT)}`。")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "candidate_count": len(raw_candidate_ids),
        "included_task_count": len(task_ids),
        "chain_count": len(component_rows),
        "overlap_count": len(overlaps),
        "json": str(OUT_JSON.relative_to(ROOT)),
        "markdown": str(OUT_MD.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
