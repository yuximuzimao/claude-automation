from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from lib.questie_source import load_questie

ROOT = Path(__file__).resolve().parents[1]
QUESTIE_ZIP = ROOT / "_sandbox/sources/Questie-v11.32.3.zip"

ZONE_SPECS = [
    ("地狱火半岛", "3483-hellfire-peninsula"),
    ("赞加沼泽", "3521-zangarmarsh"),
    ("泰罗卡森林", "3519-terokkar-forest"),
    ("沙塔斯城", "3703-shattrath-city"),
    ("纳格兰", "3518-nagrand"),
    ("刀锋山", "3522-blade-s-edge-mountains"),
    ("虚空风暴", "3523-netherstorm"),
    ("影月谷", "3520-shadowmoon-valley"),
]

ZONE_ID_TO_NAME = {
    3483: "地狱火半岛",
    3521: "赞加沼泽",
    3519: "泰罗卡森林",
    3703: "沙塔斯城",
    3518: "纳格兰",
    3522: "刀锋山",
    3523: "虚空风暴",
    3520: "影月谷",
    1637: "奥格瑞玛",
    3679: "泰罗卡森林·斯克提斯",
    3688: "泰罗卡森林·奥金顿",
    3790: "奥金顿·奥金尼地穴（副本）",
    3840: "影月谷·黑暗神殿",
    3905: "赞加沼泽·盘牙水库",
}

DUNGEON_ZONE_IDS = {3790}
DUNGEON_HUB_ZONE_IDS = {3905}

# Blood Elf + Paladin masks in Classic/WotLK DB conventions.
BLOOD_ELF_RACE_MASK = 512
PALADIN_CLASS_MASK = 2
THRALLMAR_REP = 947
HONOR_HOLD_REP = 946

MANUAL_FLAGS: dict[int, list[str]] = {
    13409: ["PvP特殊任务"],
}


def lua_seq(value: Any) -> list[Any]:
    if not isinstance(value, dict):
        return []
    return [value[k] for k in sorted(k for k in value if isinstance(k, int))]


def eligible(raw: dict[Any, Any] | None) -> bool:
    if not isinstance(raw, dict):
        return False
    races = raw.get(6)
    classes = raw.get(7)
    race_ok = races in (None, 0) or (isinstance(races, int) and bool(races & BLOOD_ELF_RACE_MASK))
    class_ok = classes in (None, 0) or (isinstance(classes, int) and bool(classes & PALADIN_CLASS_MASK))
    rep_factions = {
        row.get(1)
        for row in lua_seq(raw.get(26))
        if isinstance(row, dict) and isinstance(row.get(1), int)
    }
    faction_ok = not (HONOR_HOLD_REP in rep_factions and THRALLMAR_REP not in rep_factions)
    return bool(race_ok and class_ok and faction_ok)


def relatives(raw: dict[Any, Any]) -> set[int]:
    rel: set[int] = set()
    for key in (12, 13, 14):  # preGroup, preSingle, childQuests
        for value in lua_seq(raw.get(key)):
            if isinstance(value, int):
                rel.add(value)
    for key in (22, 25, 27, 28, 33, 34, 36):
        value = raw.get(key)
        if isinstance(value, int):
            rel.add(value)
        elif isinstance(value, dict):
            for item in lua_seq(value):
                if isinstance(item, int):
                    rel.add(item)
    return rel


def name_of(data: Any, quest_id: int) -> str:
    row = data.quest_names.get(quest_id)
    if isinstance(row, dict) and isinstance(row.get(1), str):
        return row[1]
    raw = data.quests.get(quest_id)
    if isinstance(raw, dict) and isinstance(raw.get(1), str):
        return raw[1]
    return f"Quest {quest_id}"


def zone_name_of(raw: dict[Any, Any]) -> str:
    value = raw.get(17)
    if isinstance(value, int):
        return ZONE_ID_TO_NAME.get(value, f"区域{value}")
    return "未知区域"


def task_flags(data: Any, quest_id: int) -> list[str]:
    raw = data.quests.get(quest_id, {})
    flags: list[str] = []
    name = name_of(data, quest_id)
    raw_name = raw.get(1) if isinstance(raw, dict) else None
    special = raw.get(24) if isinstance(raw, dict) else None
    required_skill = raw.get(18) if isinstance(raw, dict) else None
    required_class = raw.get(7) if isinstance(raw, dict) else None
    qlevel = raw.get(5) if isinstance(raw, dict) else None
    required_level = raw.get(4) if isinstance(raw, dict) else None
    raw_zone = raw.get(17) if isinstance(raw, dict) else None
    if isinstance(special, int) and special & 1:
        flags.append("可重复")
    if raw_zone in DUNGEON_ZONE_IDS:
        flags.append("副本任务")
    if raw_zone in DUNGEON_HUB_ZONE_IDS:
        flags.append("副本枢纽相关")
    if required_skill:
        flags.append("专业限定")
    if isinstance(required_class, int):
        flags.append("职业限定")
    if name == "DEPRECATED" or (isinstance(raw_name, str) and "UNUSED" in raw_name.upper()):
        flags.append("废弃/未使用")
    if isinstance(required_level, int) and required_level >= 100:
        flags.append("不可用/数据库占位")
    if isinstance(qlevel, int) and qlevel >= 69:
        flags.append("69+/70残局")
    flags.extend(MANUAL_FLAGS.get(quest_id, []))
    return sorted(set(flags))


def priority_for(min_quest_level: int | None) -> tuple[str, str, int | None]:
    if min_quest_level is None:
        return ("PX", "需人工核验", None)
    deadline = min_quest_level + 5
    if min_quest_level <= 60:
        return ("P0", "最高号65前处理低级环", deadline)
    if min_quest_level == 61:
        return ("P1", "最高号66前处理低级环", deadline)
    if min_quest_level == 62:
        return ("P2", "最高号67前处理低级环", deadline)
    if min_quest_level == 63:
        return ("P3", "最高号68前结清，或整块留80", deadline)
    return ("P4", "58→68无衰减硬压力，可按升级效率或80回收决定", deadline)


def main() -> None:
    data = load_questie(QUESTIE_ZIP)

    seed_ids: set[int] = set()
    candidate_zones: dict[int, set[str]] = defaultdict(set)
    for zone_name, slug in ZONE_SPECS:
        path = ROOT / f"data/routes/world-candidate/{slug}/route.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for quest in payload.get("quest_catalog", []):
            quest_id = int(quest["quest_id"])
            if not eligible(data.quests.get(quest_id)):
                continue
            seed_ids.add(quest_id)
            candidate_zones[quest_id].add(zone_name)

    # Close direct prerequisite / successor relations so omissions like 9400 are surfaced.
    all_ids = set(seed_ids)
    frontier = list(seed_ids)
    while frontier:
        quest_id = frontier.pop()
        raw = data.quests.get(quest_id)
        if not isinstance(raw, dict):
            continue
        for related in relatives(raw):
            if related in all_ids:
                continue
            related_raw = data.quests.get(related)
            if eligible(related_raw):
                all_ids.add(related)
                frontier.append(related)

    adjacency: dict[int, set[int]] = defaultdict(set)
    for quest_id in all_ids:
        raw = data.quests.get(quest_id)
        if not isinstance(raw, dict):
            continue
        for related in relatives(raw):
            if related in all_ids:
                adjacency[quest_id].add(related)
                adjacency[related].add(quest_id)

    seen: set[int] = set()
    components: list[list[int]] = []
    for quest_id in sorted(all_ids):
        if quest_id in seen:
            continue
        stack = [quest_id]
        seen.add(quest_id)
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(component)

    rows: list[dict[str, Any]] = []
    quest_rows: list[dict[str, Any]] = []

    for index, component in enumerate(components, start=1):
        tasks: list[dict[str, Any]] = []
        for quest_id in component:
            raw = data.quests.get(quest_id, {})
            qlevel = raw.get(5) if isinstance(raw, dict) and isinstance(raw.get(5), int) else None
            required = raw.get(4) if isinstance(raw, dict) and isinstance(raw.get(4), int) else None
            flags = task_flags(data, quest_id)
            task = {
                "quest_id": quest_id,
                "name": name_of(data, quest_id),
                "quest_level": qlevel,
                "required_level": required,
                "full_xp_last_level": qlevel + 5 if isinstance(qlevel, int) else None,
                "raw_zone": zone_name_of(raw) if isinstance(raw, dict) else "未知区域",
                "candidate_zones": sorted(candidate_zones.get(quest_id, set())),
                "seed_candidate": quest_id in seed_ids,
                "closure_only": quest_id not in seed_ids,
                "flags": flags,
                "pre_group": [x for x in lua_seq(raw.get(12)) if isinstance(x, int)] if isinstance(raw, dict) else [],
                "pre_single": [x for x in lua_seq(raw.get(13)) if isinstance(x, int)] if isinstance(raw, dict) else [],
                "exclusive_to": [x for x in lua_seq(raw.get(16)) if isinstance(x, int)] if isinstance(raw, dict) else [],
                "next_quest": raw.get(22) if isinstance(raw, dict) and isinstance(raw.get(22), int) else None,
            }
            tasks.append(task)

        tasks.sort(key=lambda x: (
            x["quest_level"] if isinstance(x["quest_level"], int) else 999,
            x["required_level"] if isinstance(x["required_level"], int) else 999,
            x["quest_id"],
        ))
        quest_levels = [x["quest_level"] for x in tasks if isinstance(x["quest_level"], int)]
        min_ql = min(quest_levels) if quest_levels else None
        max_ql = max(quest_levels) if quest_levels else None
        priority, recommendation, deadline = priority_for(min_ql)
        zones = sorted({zone for task in tasks for zone in task["candidate_zones"]} | {task["raw_zone"] for task in tasks})
        meaningful_zones = [z for z in zones if z != "未知区域"]
        cross_zone = len(set(meaningful_zones)) > 1
        flags = sorted({flag for task in tasks for flag in task["flags"]})
        actionable_tasks = [
            t for t in tasks
            if "废弃/未使用" not in t["flags"] and "不可用/数据库占位" not in t["flags"]
        ]
        actionable_ids = {t["quest_id"] for t in actionable_tasks}
        exclusive_adj: dict[int, set[int]] = defaultdict(set)
        for task in actionable_tasks:
            for other in task["exclusive_to"]:
                if other in actionable_ids:
                    exclusive_adj[task["quest_id"]].add(other)
                    exclusive_adj[other].add(task["quest_id"])
        exclusive_groups: list[list[int]] = []
        exclusive_seen: set[int] = set()
        for task_id in sorted(exclusive_adj):
            if task_id in exclusive_seen:
                continue
            stack = [task_id]
            exclusive_seen.add(task_id)
            group: list[int] = []
            while stack:
                current = stack.pop()
                group.append(current)
                for neighbor in exclusive_adj[current]:
                    if neighbor not in exclusive_seen:
                        exclusive_seen.add(neighbor)
                        stack.append(neighbor)
            if len(group) > 1:
                exclusive_groups.append(sorted(group))
        max_completable_task_count = len(actionable_tasks) - sum(len(group) - 1 for group in exclusive_groups)
        contains_maghar = any(t["quest_id"] in {9400, 9401, 9405, 9410, 9406, 9438, 9441, 9442, 9447} for t in tasks)
        structural_notes: list[str] = []
        if cross_zone:
            structural_notes.append("跨地图链")
        if contains_maghar:
            structural_notes.append("玛格汉/纳格兰结构前置")
        if exclusive_groups:
            structural_notes.append(f"含{len(exclusive_groups)}组互斥任务，经验预算只能选其一")
        if any(t["closure_only"] for t in tasks):
            structural_notes.append("自动候选存在漏链，已由闭包补齐")
        if "PvP特殊任务" in flags:
            structural_notes.append("特殊PvP，单独池")
        if "可重复" in flags:
            structural_notes.append("含可重复任务，单独池")
        if "专业限定" in flags:
            structural_notes.append("含专业任务，单独池")
        if "副本任务" in flags:
            structural_notes.append("含副本任务，副本池单独处理")
        if "副本枢纽相关" in flags:
            structural_notes.append("盘牙水库/副本枢纽相关，需单独核验")

        display_tasks = actionable_tasks[:8]
        # This is deliberately NOT rendered as an arrow chain. Complex components can branch,
        # and the level-sorted list below is only a membership/urgency summary, not execution order.
        summary = "；".join(f"《{t['name']}》（{t['quest_id']}）[{t['quest_level'] or '?'}]" for t in display_tasks)
        if len(actionable_tasks) > len(display_tasks):
            summary += f"；…（共{len(actionable_tasks)}项）"

        if min_ql is not None and min_ql <= 62:
            defer80 = "不建议整链后置；会主动放弃低级任务满经验"
        elif min_ql == 63:
            defer80 = "可选：68前整块结清，或未启动时整块留80"
        else:
            defer80 = "较适合整块后置；避免只剩零散末环"
        if contains_maghar:
            defer80 = "不建议后置：会影响后续纳格兰任务中心"
        if "副本任务" in flags or "副本枢纽相关" in flags:
            defer80 = "副本/副本枢纽池单独判断，不直接并入开放世界循环"

        row = {
            "chain_id": f"OC{index:03d}",
            "task_count": len(tasks),
            "actionable_task_count": len(actionable_tasks),
            "max_completable_task_count": max_completable_task_count,
            "exclusive_groups": exclusive_groups,
            "min_quest_level": min_ql,
            "max_quest_level": max_ql,
            "full_xp_deadline": deadline,
            "priority": priority,
            "recommendation_58_68": recommendation,
            "defer_to_80": defer80,
            "zones": zones,
            "cross_zone": cross_zone,
            "flags": flags,
            "structural_notes": structural_notes,
            "chain_summary": summary,
            "tasks": tasks,
        }
        rows.append(row)
        for task in tasks:
            quest_rows.append({"chain_id": row["chain_id"], **task})

    rows.sort(key=lambda row: (
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "PX": 5}[row["priority"]],
        row["min_quest_level"] if isinstance(row["min_quest_level"], int) else 999,
        ",".join(row["zones"]),
        row["chain_id"],
    ))

    # Renumber after sorting for stable human reading.
    id_map = {row["chain_id"]: f"OC{index:03d}" for index, row in enumerate(rows, start=1)}
    for row in rows:
        old = row["chain_id"]
        row["chain_id"] = id_map[old]
        for task in row["tasks"]:
            task["chain_id"] = row["chain_id"]
    for quest in quest_rows:
        quest["chain_id"] = id_map[quest["chain_id"]]

    counts: dict[str, int] = defaultdict(int)
    actionable_counts: dict[str, int] = defaultdict(int)
    tasks_by_priority: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["priority"]] += 1
        if row["actionable_task_count"] > 0:
            actionable_counts[row["priority"]] += 1
        tasks_by_priority[row["priority"]] += row["actionable_task_count"]

    output = {
        "source": {
            "questie_version": data.version,
            "questie_sha256": data.source_sha256,
            "candidate_zone_slugs": [slug for _, slug in ZONE_SPECS],
            "seed_candidate_count": len(seed_ids),
            "closure_task_count": len(all_ids),
            "component_count": len(rows),
        },
        "priority_counts": dict(counts),
        "actionable_chain_counts": dict(actionable_counts),
        "actionable_task_counts": dict(tasks_by_priority),
        "chains": rows,
        "quests": quest_rows,
    }

    out_json = ROOT / "data/routes/horde/blood-elf/outland-58-68-chain-audit.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# 外域58—68任务链总表（链级底表）")
    lines.append("")
    lines.append("状态：机器闭包＋人工规则初筛，不是具体执行攻略。自动候选只作召回；任务机制、互斥、PvP/副本/特殊任务仍需在写具体地图攻略前逐链复核。")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 原始8区域候选：{len(seed_ids)}条。")
    lines.append(f"- 任务链闭包后：{len(all_ids)}条（补回{len(all_ids)-len(seed_ids)}条直接前置/后续）。")
    lines.append(f"- 合并为：{len(rows)}个任务链/独立任务块。")
    lines.append(f"- P0/P1/P2/P3/P4有效链块：{actionable_counts.get('P0',0)}/{actionable_counts.get('P1',0)}/{actionable_counts.get('P2',0)}/{actionable_counts.get('P3',0)}/{actionable_counts.get('P4',0)}；纯废弃/未使用组件保留在JSON底表但不展示。")
    lines.append("")
    lines.append("优先级含义：P0=链内最低≤60（最高号65前处理低级环）；P1=最低61（66前）；P2=最低62（67前）；P3=最低63（68前结清或整块留80）；P4=最低64+（58→68没有衰减硬压力）。")
    lines.append("")

    for priority, title in [
        ("P0", "P0：65前必须关注"),
        ("P1", "P1：66前必须关注"),
        ("P2", "P2：67前必须关注"),
        ("P3", "P3：68前做出‘现在结清/整块留80’决策"),
        ("P4", "P4：无当前衰减硬压力"),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| 链ID | 地图 | 最低→最高任务等级 | 最多可完成/有效候选 | 结构备注 | 68前处理 | 80后置 | 链内任务样本（按等级列示，非执行顺序） |")
        lines.append("|---|---|---:|---:|---|---|---|---|")
        for row in rows:
            if row["priority"] != priority or row["actionable_task_count"] <= 0:
                continue
            zone_text = " / ".join(row["zones"])
            lvl_text = f"{row['min_quest_level'] if row['min_quest_level'] is not None else '?'}→{row['max_quest_level'] if row['max_quest_level'] is not None else '?'}"
            notes = "；".join(row["structural_notes"]) or "—"
            summary = row["chain_summary"].replace("|", "／")
            lines.append(
                f"| {row['chain_id']} | {zone_text} | {lvl_text} | {row['max_completable_task_count']}/{row['actionable_task_count']} | {notes} | {row['recommendation_58_68']} | {row['defer_to_80']} | {summary} |"
            )
        lines.append("")

    lines.append("## 使用方式")
    lines.append("")
    lines.append("- 具体路线设计时先看最高经验号：到65前消灭P0低级环，到66前消灭P1，到67前消灭P2。")
    lines.append("- P3不能留下69—79级零散回头任务：要么最高号68前整块交完，要么未启动时整块封存到80。")
    lines.append("- P4不因等级窗口抢做；按任务中心密度、后续解锁、68升级效率和80回收成本决定。")
    lines.append("- 任务链若跨地图或属于结构前置，不能只依据最低任务等级机械拆开。")
    lines.append("- 完整逐任务字段见`data/routes/horde/blood-elf/outland-58-68-chain-audit.json`。")

    out_md = ROOT / "docs/archive/analysis/2026-08-11-outland-58-68-chain-master-table.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "json": str(out_json.relative_to(ROOT)),
        "markdown": str(out_md.relative_to(ROOT)),
        "seed": len(seed_ids),
        "closure": len(all_ids),
        "components": len(rows),
        "priority_counts": dict(counts),
        "actionable_chain_counts": dict(actionable_counts),
        "actionable_task_counts": dict(tasks_by_priority),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
