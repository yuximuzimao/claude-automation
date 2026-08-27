from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/howling-fjord-task-foundation.json"
OUT = ROOT / "docs/analysis/2026-08-26-howling-fjord-formal-task-windows.md"
ZONE_ID = 495


def entity_label(task: dict[str, Any], field: str) -> str:
    entities = task.get(field) or []
    if not entities:
        return "—"
    labels = []
    for entity in entities[:3]:
        rep = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
        coord = ""
        if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            coord = f"@({rep['x']:.1f},{rep['y']:.1f})"
        label = f"{entity.get('name') or entity.get('entity_id')}{coord}"
        if label not in labels:
            labels.append(label)
    return " / ".join(labels) or "—"


def objective_labels(task: dict[str, Any]) -> str:
    labels: list[str] = []
    for obj in task.get("objectives") or []:
        for source in obj.get("sources") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rep = (source.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
            coord = ""
            if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
                coord = f"@({rep['x']:.1f},{rep['y']:.1f})"
            label = f"{source.get('name') or source.get('entity_id')}{coord}"
            if label not in labels:
                labels.append(label)
    return " / ".join(labels[:8]) or "脚本/对话/任务物触发"


def main() -> None:
    data = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    lines = [
        "# 嚎风峡湾正式任务窗口压缩表",
        "",
        f"- 正式任务：{len(tasks)}。",
        "- 用途：逐簇插入时人工检查前置、同NPC、同目的地与回访，不作为玩家文案。",
        "",
    ]
    for task in tasks:
        qid = int(task["quest_id"])
        deps = []
        if task.get("pre_any"):
            deps.append(f"pre_any={task['pre_any']}")
        if task.get("pre_all"):
            deps.append(f"pre_all={task['pre_all']}")
        if task.get("parent_active"):
            deps.append(f"parent={task['parent_active']}")
        if task.get("next_quest"):
            deps.append(f"next={task['next_quest']}")
        lines.append(
            f"- {qid}《{task.get('name')}》｜接：{entity_label(task, 'start_entities')}｜目标：{objective_labels(task)}｜交：{entity_label(task, 'finish_entities')}｜{'；'.join(deps) or '独立/起始'}｜{task.get('task_class')}"
        )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"tasks": len(tasks), "out": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
