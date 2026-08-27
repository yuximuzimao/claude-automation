from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
AUTO = ROOT / "data/routes/world-candidate/66-zul-drak/route.json"
OUT = ROOT / "data/route-atlas/zuldrak-scope-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-19-zuldrak-scope-audit.md"
ZONE_ID = 66

# Structural only: current Horde outdoor axis, no speed/economic pruning.
STRUCTURAL_EXCLUDE = {
    12633: "alternate_branch_requires_dungeon_prerequisite_12238",
    12638: "alternate_branch_requires_dungeon_prerequisite_12238",
    12643: "alternate_branch_requires_dungeon_prerequisite_12238",
    12649: "alternate_branch_requires_dungeon_prerequisite_12238",
    12792: "mutually_exclusive_entry_breadcrumb_current_axis_carries_12789",
    12793: "mutually_exclusive_entry_breadcrumb_current_axis_carries_12789",
    12954: "alternate_amphitheater_starter_current_axis_uses_12932",
    12780: "deprecated_quest_typo_in_source_no_start_or_finish_entity",
}

# Zero-XP scripted child quests can still be mandatory to complete an included parent quest.
# 12664 is the non-dungeon branch opened while 12661 is active after the current route's 12648 path;
# completing its Gorebag flight tour is required before 12661 can be turned in to Stefan.
STRUCTURAL_INCLUDE = {
    12664: "mandatory_scripted_child_for_12661_current_non_dungeon_branch",
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
    zones = entity.get("zones") or []
    if not coord and zones:
        coord = f"@[zone {zones[0]}]"
    return f"{entity.get('name') or entity.get('entity_id')}{coord}"


def reason(task: dict[str, Any]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if qid in STRUCTURAL_EXCLUDE:
        return "exclude_structural", [STRUCTURAL_EXCLUDE[qid]]
    if qid in STRUCTURAL_INCLUDE:
        return "include_structural_zero_xp_scripted_child", [STRUCTURAL_INCLUDE[qid]]
    if not task.get("race_allowed") or not task.get("npc_faction_allowed"):
        return "exclude_faction", list(task.get("faction_reasons") or ["not_current_horde_axis"])
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
    if not (task.get("xp") or {}).get("has_xp"):
        return "exclude_no_xp_pending_dependency", ["no_xp"]
    return "include_candidate", ["one_time_outdoor_horde_paladin_xp"]


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    auto = json.loads(AUTO.read_text(encoding="utf-8"))
    auto_ids = {int(q["quest_id"]) for q in auto.get("quest_catalog", [])}
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
            "exclusive_to": task.get("exclusive_to") or [],
            "start": entity_label(task, "start_entities"),
            "finish": entity_label(task, "finish_entities"),
            "task_class": task.get("task_class"),
        })

    include_ids = {row["quest_id"] for row in rows if row["status"] == "include_candidate"}
    by_row = {row["quest_id"]: row for row in rows}
    by_task = {int(task["quest_id"]): task for task in tasks}
    changed = True
    while changed:
        changed = False
        for qid in sorted(include_ids):
            task = by_task[qid]
            mandatory = set(task.get("pre_all") or []) | set(task.get("parent_active") or [])
            pre_any = list(task.get("pre_any") or [])
            if len(pre_any) == 1:
                mandatory.add(pre_any[0])
            for dep in mandatory:
                row = by_row.get(int(dep))
                if row and row["status"] == "exclude_no_xp_pending_dependency":
                    row["status"] = "include_structural_zero_xp_prerequisite"
                    row["reasons"] = [f"mandatory_for_{qid}"]
                    include_ids.add(int(dep))
                    changed = True
    for row in rows:
        if row["status"] == "exclude_no_xp_pending_dependency":
            row["status"] = "exclude_no_xp"
            row["reasons"] = ["no_xp_not_mandatory_for_included_task"]

    formal_ids = {row["quest_id"] for row in rows if row["status"].startswith("include_")}
    old_auto_missing = sorted(formal_ids - auto_ids)
    old_auto_extra = sorted(auto_ids - formal_ids)
    counts = Counter(row["status"] for row in rows)
    level_counts = Counter(row["required_level"] for row in rows if row["status"].startswith("include_"))

    payload = {
        "zone_id": ZONE_ID,
        "zone_name": "祖达克",
        "strategy": "first-run continuous outdoor full-clear baseline; structural exclusions only",
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
        "# 祖达克正式 scope 审计（全清基线）", "",
        "- 目标：只建立首组户外一次性全清任务池；不做速度/金币裁剪。",
        f"- Questie assigned 到祖达克：{len(rows)}；正式候选：{len(formal_ids)}。",
        f"- requiredLevel：`{dict(sorted(level_counts.items(), key=lambda x: (x[0] is None, x[0] or 0)))}`。",
        f"- 旧自动路线：{len(auto_ids)}；漏召回{len(old_auto_missing)}；多出{len(old_auto_extra)}。", "",
        "## 旧自动路线漏掉的正式候选", "",
    ]
    for qid in old_auto_missing:
        row = by_row[qid]
        lines.append(f"- {qid}《{row['name']}》｜接：{row['start']}｜交：{row['finish']}｜pre={row['pre_any'] or row['pre_all']}｜parent={row['parent_active']}")
    lines += ["", "## 旧自动路线中应结构性排除", ""]
    for qid in old_auto_extra:
        row = by_row.get(qid)
        if row:
            lines.append(f"- {qid}《{row['name']}》：{row['status']} / {', '.join(row['reasons'])}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"assigned": len(rows), "formal": len(formal_ids), "missing_from_old_auto": len(old_auto_missing), "old_auto_extra": len(old_auto_extra), "status_counts": dict(sorted(counts.items()))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
