from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT_JSON = ROOT / "data/route-atlas/icecrown-components.json"
OUT_MD = ROOT / "docs/analysis/2026-08-25-icecrown-components.md"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}


def entity_summary(entity: dict[str, Any]) -> dict[str, Any]:
    rep = (entity.get("representative_by_zone") or {}).get("210") or {}
    return {
        "entity_type": entity.get("entity_type"),
        "entity_id": entity.get("entity_id"),
        "name": entity.get("name"),
        "x": rep.get("x"),
        "y": rep.get("y"),
    }


def component_label(tasks: list[dict[str, Any]]) -> str:
    ids = {int(task["quest_id"]) for task in tasks}
    names = " ".join(str(task.get("name") or "") for task in tasks)
    if any(13600 <= qid <= 14199 for qid in ids) or "冠军" in names or "侍从" in names or "锦标赛" in names:
        return "argent_tournament_or_patch"
    if any(24500 <= qid <= 24699 for qid in ids):
        return "quel_delar_patch_chain"
    if any(qid in ids for qid in {12892, 12891, 12893, 12896, 12898}):
        return "shadow_vault_entry"
    if any(qid in ids for qid in {13036, 13039, 13040, 13044, 13045}):
        return "argent_vanguard"
    if any(13300 <= qid <= 13420 for qid in ids):
        return "late_icecrown_or_airship"
    return "core_or_misc_icecrown"


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = [
        task for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    ]
    by_id = {int(task["quest_id"]): task for task in tasks}
    ids = set(by_id)

    graph: dict[int, set[int]] = {qid: set() for qid in ids}
    for qid, task in by_id.items():
        related = set(int(x) for x in (task.get("pre_any") or []))
        related |= set(int(x) for x in (task.get("pre_all") or []))
        related |= set(int(x) for x in (task.get("parent_active") or []))
        related |= set(int(x) for x in (task.get("child_quests") or []))
        next_quest = task.get("next_quest")
        if isinstance(next_quest, int):
            related.add(next_quest)
        for other in related & ids:
            graph[qid].add(other)
            graph[other].add(qid)

    seen: set[int] = set()
    components: list[dict[str, Any]] = []
    for start in sorted(ids):
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        members: list[int] = []
        while queue:
            qid = queue.popleft()
            members.append(qid)
            for other in sorted(graph[qid]):
                if other not in seen:
                    seen.add(other)
                    queue.append(other)
        member_tasks = [by_id[qid] for qid in sorted(members)]
        roots = []
        start_entities: list[dict[str, Any]] = []
        finish_entities: list[dict[str, Any]] = []
        for task in member_tasks:
            local_deps = (
                set(int(x) for x in (task.get("pre_any") or []))
                | set(int(x) for x in (task.get("pre_all") or []))
                | set(int(x) for x in (task.get("parent_active") or []))
            ) & ids
            if not local_deps:
                roots.append({"quest_id": int(task["quest_id"]), "name": task.get("name")})
            start_entities.extend(entity_summary(entity) for entity in (task.get("start_entities") or []))
            finish_entities.extend(entity_summary(entity) for entity in (task.get("finish_entities") or []))

        geo_starts = [row for row in start_entities if row.get("x") is not None and row.get("y") is not None]
        geo_finishes = [row for row in finish_entities if row.get("x") is not None and row.get("y") is not None]
        all_geo = geo_starts + geo_finishes
        xs = [float(row["x"]) for row in all_geo]
        ys = [float(row["y"]) for row in all_geo]
        bonus_copper = sum(int((task.get("level_80_economy") or {}).get("xp_bonus_money_copper") or 0) for task in member_tasks)
        component = {
            "component_id": len(components) + 1,
            "label": component_label(member_tasks),
            "task_count": len(member_tasks),
            "quest_ids": sorted(members),
            "quest_names": [task.get("name") for task in member_tasks],
            "roots": roots,
            "repeatable_or_calendar_count": sum(
                1 for task in member_tasks
                if task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly")
            ),
            "conditional_count": sum(1 for task in member_tasks if task.get("scope_status") == "include_conditional_route_state"),
            "xp_bonus_gold_per_character": round(bonus_copper / 10000.0, 2),
            "geo_start_entities": geo_starts,
            "geo_finish_entities": geo_finishes,
            "bbox": [min(xs), min(ys), max(xs), max(ys)] if xs and ys else None,
        }
        components.append(component)

    components.sort(key=lambda row: (-int(row["task_count"]), int(row["quest_ids"][0])))
    for index, component in enumerate(components, start=1):
        component["component_id"] = index

    label_counts: dict[str, int] = defaultdict(int)
    label_tasks: dict[str, int] = defaultdict(int)
    for component in components:
        label_counts[component["label"]] += 1
        label_tasks[component["label"]] += int(component["task_count"])

    payload = {
        "status": "icecrown_candidate_component_analysis",
        "candidate_task_count": len(tasks),
        "component_count": len(components),
        "label_component_counts": dict(sorted(label_counts.items())),
        "label_task_counts": dict(sorted(label_tasks.items())),
        "components": components,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 冰冠冰川候选任务组件分解",
        "",
        f"- 当前路线候选：{len(tasks)}项；依赖图连通组件：{len(components)}个。",
        f"- 标签任务数：`{dict(sorted(label_tasks.items()))}`。标签只用于规划分层，不直接决定删留。",
        "",
        "## 大组件",
        "",
    ]
    for component in components:
        if int(component["task_count"]) < 3:
            continue
        roots_text = "、".join(f"{row['quest_id']}《{row['name']}》" for row in component["roots"][:6]) or "无显式根"
        lines.append(
            f"- C{component['component_id']}｜{component['label']}｜{component['task_count']}项｜首轮重复/日历={component['repeatable_or_calendar_count']}｜80级XP折金≈{component['xp_bonus_gold_per_character']}G/角色｜根：{roots_text}｜bbox={component['bbox']}"
        )
    lines.extend([
        "",
        "## 使用方式",
        "",
        "- 先按组件识别独立Hub和时间/声望门槛；再在组件内部按前置顺序拆Target Cluster。",
        "- Argent Tournament/补丁链不能仅因地理上属于冰冠就自动混入核心清图序列；必须先审真实首日可接性、日历/声望时间门槛和户外政策。",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "candidate_task_count": len(tasks),
        "component_count": len(components),
        "label_task_counts": dict(sorted(label_tasks.items())),
        "largest": [
            {
                "id": row["component_id"],
                "label": row["label"],
                "tasks": row["task_count"],
                "roots": row["roots"][:5],
                "bbox": row["bbox"],
            }
            for row in components[:12]
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
