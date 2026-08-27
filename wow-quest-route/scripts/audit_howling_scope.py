from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
AUTO = ROOT / "data/route-atlas/howling-fjord-candidate-summary.json"
OUT = ROOT / "data/route-atlas/howling-fjord-scope-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-26-howling-fjord-scope-audit.md"
ZONE_ID = 495

# Only structural impossibilities belong here. Add explicit ids only after manual confirmation.
STRUCTURAL_EXCLUDE: dict[int, str] = {
    11189: "beta_removed_alliance_quest_not_present_in_live_wotlk",
}


def entity_label(task: dict[str, Any], field: str) -> str:
    entities = task.get(field) or []
    if not entities:
        return "—"
    entity = entities[0]
    rep = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
    coord = ""
    if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
        coord = f"@({rep['x']:.1f},{rep['y']:.1f})"
    return f"{entity.get('name') or entity.get('entity_id')}{coord}"


def reason(task: dict[str, Any]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if qid in STRUCTURAL_EXCLUDE:
        return "exclude_structural", [STRUCTURAL_EXCLUDE[qid]]
    if task.get("assigned_zone_id") != ZONE_ID:
        return "boundary_only", ["not_assigned_to_howling_fjord"]
    if not task.get("race_allowed") or not task.get("npc_faction_allowed"):
        return "exclude_faction", list(task.get("faction_reasons") or ["not_horde_blood_elf"])
    if not task.get("class_allowed"):
        return "exclude_class", ["not_paladin"]
    if task.get("required_skill"):
        return "exclude_profession", ["requires_profession_or_skill"]
    if task.get("is_deprecated_or_system"):
        return "exclude_deprecated", ["deprecated_or_system"]
    if task.get("is_dungeon") or task.get("is_raid_flagged"):
        return "exclude_dungeon_raid", ["outdoor_route_policy"]
    if task.get("pvp", {}).get("is_pvp") and not task.get("pvp", {}).get("allowed_by_policy"):
        return "exclude_pvp", ["non_mob_pvp"]
    if task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly"):
        return "exclude_repeatable_calendar", ["not_one_time_baseline"]
    xp = task.get("xp") or {}
    if not xp.get("has_xp"):
        return "exclude_no_xp_pending_dependency", ["no_xp"]
    required_level = task.get("required_level")
    if isinstance(required_level, int) and required_level > 80:
        return "exclude_above_80", [f"required_level_{required_level}"]
    return "include_candidate", ["one_time_outdoor_horde_paladin"]


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    auto = json.loads(AUTO.read_text(encoding="utf-8"))
    auto_ids = {int(qid) for qid in auto.get("selected_quest_ids", [])}
    tasks = [task for task in universe.get("tasks", []) if task.get("assigned_zone_id") == ZONE_ID]

    rows = []
    for task in tasks:
        status, reasons = reason(task)
        rows.append({
            "quest_id": int(task["quest_id"]),
            "name": task.get("name"),
            "required_level": task.get("required_level"),
            "quest_level": task.get("quest_level"),
            "status": status,
            "reasons": reasons,
            "in_old_auto_route": int(task["quest_id"]) in auto_ids,
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "next_quest": task.get("next_quest"),
            "start": entity_label(task, "start_entities"),
            "finish": entity_label(task, "finish_entities"),
            "task_class": task.get("task_class"),
        })

    include_ids = {row["quest_id"] for row in rows if row["status"] == "include_candidate"}
    by_id = {row["quest_id"]: row for row in rows}
    task_by_id = {int(task["quest_id"]): task for task in tasks}

    # Promote zero-XP tasks only when dependency data proves they are mandatory.
    changed = True
    while changed:
        changed = False
        for qid in sorted(include_ids):
            task = task_by_id.get(qid)
            if not task:
                continue
            mandatory = set(task.get("pre_all") or []) | set(task.get("parent_active") or [])
            pre_any = list(task.get("pre_any") or [])
            if len(pre_any) == 1:
                mandatory.add(pre_any[0])
            for dep in mandatory:
                row = by_id.get(int(dep))
                if row and row["status"] == "exclude_no_xp_pending_dependency":
                    row["status"] = "include_structural_zero_xp_prerequisite"
                    row["reasons"] = [f"mandatory_for_{qid}"]
                    include_ids.add(int(dep))
                    changed = True

    for row in rows:
        if row["status"] == "exclude_no_xp_pending_dependency":
            row["status"] = "exclude_no_xp"
            row["reasons"] = ["no_xp_not_mandatory_by_dependency_data"]

    formal_ids = {row["quest_id"] for row in rows if row["status"].startswith("include_")}
    old_auto_missing = sorted(formal_ids - auto_ids)
    old_auto_extra = sorted(auto_ids - formal_ids)
    counts = Counter(row["status"] for row in rows)
    level_counts = Counter(row["required_level"] for row in rows if row["status"].startswith("include_"))

    payload = {
        "zone_id": ZONE_ID,
        "zone_name": "嚎风峡湾",
        "strategy": "one-time outdoor Horde baseline from cleaned Northrend task universe; no economic pruning",
        "assigned_task_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "formal_candidate_count": len(formal_ids),
        "formal_candidate_ids": sorted(formal_ids),
        "required_level_counts": {str(k): v for k, v in sorted(level_counts.items(), key=lambda x: (x[0] is None, x[0] or 0))},
        "old_auto_selected_count": len(auto_ids),
        "formal_missing_from_old_auto": old_auto_missing,
        "old_auto_extra_vs_formal": old_auto_extra,
        "rows": sorted(rows, key=lambda row: row["quest_id"]),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 嚎风峡湾正式scope审计",
        "",
        "- 输入：已清洗的诺森德任务宇宙；这里是路线scope，不是重新清洗任务数据。",
        "- 基线：部落血精灵圣骑士、一次性户外任务；副本/团队/专业/不可用阵营/重复日常做结构性排除；不做经济性删减。",
        f"- assigned任务：{len(rows)}；正式候选：{len(formal_ids)}。",
        f"- 状态统计：`{dict(sorted(counts.items()))}`。",
        f"- 旧自动候选：{len(auto_ids)}；正式池新增{len(old_auto_missing)}，旧自动多出{len(old_auto_extra)}。",
        "",
        "## 旧自动候选漏召回的正式任务",
        "",
    ]
    for qid in old_auto_missing:
        row = by_id[qid]
        lines.append(f"- {qid}《{row['name']}》｜Lv{row['required_level']}｜接：{row['start']}｜交：{row['finish']}｜{row['task_class']}")
    lines.extend(["", "## 旧自动候选中不属于正式池", ""])
    for qid in old_auto_extra:
        row = by_id.get(qid)
        if row:
            lines.append(f"- {qid}《{row['name']}》：{row['status']} / {', '.join(row['reasons'])}")
        else:
            lines.append(f"- {qid}：不属于assigned嚎风任务")
    lines.extend(["", "## 正式候选", ""])
    for qid in sorted(formal_ids):
        row = by_id[qid]
        dep = []
        if row["pre_any"]:
            dep.append(f"pre_any={row['pre_any']}")
        if row["pre_all"]:
            dep.append(f"pre_all={row['pre_all']}")
        if row["parent_active"]:
            dep.append(f"parent={row['parent_active']}")
        if row["next_quest"]:
            dep.append(f"next={row['next_quest']}")
        lines.append(f"- {qid}《{row['name']}》｜接：{row['start']}｜交：{row['finish']}｜{'；'.join(dep) or '起始/独立'}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "assigned": len(rows),
        "formal": len(formal_ids),
        "status_counts": dict(sorted(counts.items())),
        "missing_from_old_auto": len(old_auto_missing),
        "old_auto_extra": len(old_auto_extra),
        "out": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
