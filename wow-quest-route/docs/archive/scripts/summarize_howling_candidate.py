from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "data/routes/world-candidate/495-howling-fjord/route.json"
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OUT_JSON = ROOT / "data/route-atlas/howling-fjord-candidate-summary.json"
OUT_MD = ROOT / "docs/analysis/2026-08-26-howling-fjord-candidate-summary.md"
ZONE_ID = 495


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


def objective_labels(task: dict[str, Any]) -> str:
    labels: list[str] = []
    for obj in task.get("objectives") or []:
        source = next((s for s in (obj.get("sources") or []) if ZONE_ID in (s.get("zones") or [])), None)
        if not source:
            continue
        rep = (source.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
        coord = ""
        if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            coord = f"@({rep['x']:.1f},{rep['y']:.1f})"
        label = f"{source.get('name') or source.get('entity_id')}{coord}"
        if label not in labels:
            labels.append(label)
    return " / ".join(labels[:4]) or "脚本/对话/无普通目标点"


def main() -> None:
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    tasks = {int(t["quest_id"]): t for t in universe.get("tasks", [])}

    steps: list[dict[str, Any]] = []
    seen_qids: set[int] = set()
    action_counts: Counter[str] = Counter()
    for index, step in enumerate(route.get("steps", []), start=1):
        qids = sorted({int(q) for q in step.get("quest_ids", []) if isinstance(q, int) or str(q).isdigit()})
        seen_qids.update(qids)
        action = str(step.get("action") or "")
        action_counts[action] += 1
        anchor = (step.get("anchor_details") or {}).get("representative") or {}
        names = [str(tasks.get(qid, {}).get("name") or f"Q{qid}") for qid in qids]
        steps.append({
            "index": index,
            "action": action,
            "quest_ids": qids,
            "quest_names": names,
            "anchor": {
                "x": anchor.get("x"),
                "y": anchor.get("y"),
                "zone_id": anchor.get("zone_id") or anchor.get("zoneId"),
                "label": anchor.get("label") or anchor.get("name"),
            },
        })

    selected = sorted(seen_qids)
    selected_task_facts = []
    for qid in selected:
        task = tasks.get(qid, {})
        selected_task_facts.append({
            "quest_id": qid,
            "name": task.get("name"),
            "required_level": task.get("required_level"),
            "quest_level": task.get("quest_level"),
            "task_class": task.get("task_class"),
            "is_dungeon": task.get("is_dungeon"),
            "is_raid_flagged": task.get("is_raid_flagged"),
            "is_repeatable": task.get("is_repeatable"),
            "is_daily": task.get("is_daily"),
            "pre_any": task.get("pre_any"),
            "pre_all": task.get("pre_all"),
            "parent_active": task.get("parent_active"),
            "next_quest": task.get("next_quest"),
            "start_zones": task.get("start_zones"),
            "turnin_zones": task.get("turnin_zones"),
        })

    sample_task = tasks.get(selected[0], {}) if selected else {}
    payload = {
        "zone_id": ZONE_ID,
        "zone_name": "嚎风峡湾",
        "source": str(ROUTE.relative_to(ROOT)),
        "strategy": "old auto candidate compressed for manual rebuilding; not a formal route",
        "step_count": len(steps),
        "candidate_quest_count": len(seen_qids),
        "action_counts": dict(action_counts),
        "selected_quest_ids": selected,
        "selected_task_facts": selected_task_facts,
        "task_schema_keys": sorted(sample_task.keys()),
        "steps": steps,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hub_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for qid in selected:
        task = tasks.get(qid, {})
        hub_groups[entity_label(task, "start_entities")].append(task)

    lines = [
        "# 嚎风峡湾旧自动候选压缩摘要",
        "",
        "> 只作为正式Route Atlas重建的任务/地理材料，不继承旧自动步骤结构。",
        "",
        f"- 自动步骤：{len(steps)}",
        f"- 自动候选任务：{len(seen_qids)}",
        f"- 动作类型：{dict(action_counts)}",
        "",
        "## 接取Hub分组",
        "",
    ]
    for hub, rows in sorted(hub_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        names_text = "、".join(f"{row['quest_id']}《{row['name']}》" for row in rows)
        lines.append(f"- **{hub}**（{len(rows)}）：{names_text}")

    lines.extend(["", "## 任务链与地理事实", ""])
    for qid in selected:
        task = tasks.get(qid, {})
        deps = []
        if task.get("pre_any"):
            deps.append(f"pre_any={task['pre_any']}")
        if task.get("pre_all"):
            deps.append(f"pre_all={task['pre_all']}")
        if task.get("parent_active"):
            deps.append(f"parent={task['parent_active']}")
        if task.get("next_quest"):
            deps.append(f"next={task['next_quest']}")
        dep_text = "; ".join(deps) or "独立/起始"
        lines.append(
            f"- {qid}《{task.get('name')}》｜接：{entity_label(task, 'start_entities')}｜目标：{objective_labels(task)}｜交：{entity_label(task, 'finish_entities')}｜{dep_text}｜{task.get('task_class')}"
        )

    lines.extend(["", "## 旧自动顺序（仅供识别材料）", ""])
    for item in steps:
        quest_text = "、".join(f"{qid}《{name}》" for qid, name in zip(item["quest_ids"], item["quest_names"])) or "—"
        anchor = item["anchor"]
        coord = ""
        if isinstance(anchor.get("x"), (int, float)) and isinstance(anchor.get("y"), (int, float)):
            coord = f" @ ({anchor['x']:.2f}, {anchor['y']:.2f})"
        lines.append(f"{item['index']}. **{item['action'] or '未标动作'}**{coord}：{quest_text}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "steps": len(steps),
        "candidate_quests": len(seen_qids),
        "out_json": str(OUT_JSON.relative_to(ROOT)),
        "out_md": str(OUT_MD.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
