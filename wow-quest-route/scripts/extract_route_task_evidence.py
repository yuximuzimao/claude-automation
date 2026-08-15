from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


QUEST_ID_PATTERN = re.compile(r"(?<!\d)(\d{2,5})(?!\d)")
KNOWN_LOW_QUEST_IDS = {10, 32, 77, 82}


def parse_route_quest_ids(route_text: str) -> list[int]:
    """Extract quest IDs from route prose while excluding obvious dates/levels."""
    ids: set[int] = set()
    for line in route_text.splitlines():
        # Quest IDs in this project normally appear next to a Chinese quest title,
        # an arrow chain, or in explicit task lists. Ignore headings/date metadata.
        if line.startswith("#") or "2026-" in line:
            continue
        for match in QUEST_ID_PATTERN.finditer(line):
            value = int(match.group(1))
            # Route quest IDs in this project are below 20,000. Larger values in
            # prose are character XP snapshots, not quest identifiers.
            if (value < 100 and value not in KNOWN_LOW_QUEST_IDS) or value > 20_000:
                continue
            ids.add(value)
    return sorted(ids)


def compact_source(source: dict[str, Any]) -> dict[str, Any]:
    evidence = []
    for row in source.get("loot_evidence", []):
        evidence.append(
            {
                "source_type": row.get("source_type"),
                "probability_percent": row.get("probability_percent"),
                "quest_only": row.get("quest_only"),
                "mincount": row.get("mincount"),
                "maxcount": row.get("maxcount"),
            }
        )
    return {
        "entity_type": source.get("entity_type"),
        "entity_id": source.get("entity_id"),
        "name": source.get("name"),
        "level_min": source.get("level_min"),
        "level_max": source.get("level_max"),
        "spawn_count": len(source.get("spawns", [])),
        "loot_evidence": evidence,
    }


def compact_objective(objective: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective_type": objective.get("objective_type"),
        "mechanic": objective.get("mechanic"),
        "required_count": objective.get("required_count"),
        "item_id": objective.get("item_id"),
        "fivebox_mode": objective.get("fivebox_mode"),
        "difficulty_flags": objective.get("difficulty_flags", []),
        "sources": [compact_source(source) for source in objective.get("sources", [])],
        "reference_time": objective.get("azerothcore_time_at_earliest_level"),
    }


def compact_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "quest_id": task.get("quest_id"),
        "name": task.get("name"),
        "english_name": task.get("english_name"),
        "status": task.get("status"),
        "zone": task.get("primary_zone"),
        "required_level": task.get("required_level"),
        "quest_level": task.get("quest_level"),
        "xp_by_completion_level": task.get("xp_by_completion_level", {}),
        "objective_text_zh": task.get("objective_text_zh"),
        "task_class": task.get("task_class"),
        "objectives": [compact_objective(obj) for obj in task.get("objectives", [])],
        "pre_single": task.get("pre_single", []),
        "pre_group": task.get("pre_group", []),
        "next_quest": task.get("next_quest"),
        "route_flags": task.get("route_flags", []),
        "confidence": task.get("confidence"),
        "manual_review_reasons": task.get("manual_review_reasons", []),
        "standalone_time_at_earliest_level": task.get("standalone_time_at_earliest_level"),
        "azerothcore_adjusted_standalone_time": task.get("azerothcore_adjusted_standalone_time"),
        "loot_enrichment_status": task.get("loot_enrichment_status"),
    }


def probability_summary(task: dict[str, Any]) -> str:
    values: list[str] = []
    for objective in task.get("objectives", []):
        for source in objective.get("sources", []):
            for row in source.get("loot_evidence", []):
                probability = row.get("probability_percent")
                if probability is not None:
                    values.append(f"{source.get('name')}:{probability}%")
    return "; ".join(dict.fromkeys(values)) or "—"


def objective_summary(task: dict[str, Any]) -> str:
    values: list[str] = []
    for objective in task.get("objectives", []):
        sources = "/".join(
            str(source.get("name"))
            for source in objective.get("sources", [])[:3]
            if source.get("name")
        )
        values.append(
            f"{objective.get('mechanic')}×{objective.get('required_count') or '?'}"
            f"[{objective.get('fivebox_mode') or '?'}]"
            f"({sources or 'source?'})"
        )
    return "; ".join(values) or "无目标/跑腿"


def write_markdown_summary(
    tasks: list[dict[str, Any]], missing: list[int], output_path: Path, root: Path
) -> None:
    lines = [
        "# 当前39—55路线逐任务静态证据矩阵",
        "",
        "> 此表只压缩Questie与AzerothCore参考数据；公开玩家评论、本服实测和地点密度证据需在后续人工审计列补齐。",
        "",
        f"- 路线任务：{len(tasks) + len(missing)}个。",
        f"- 已定位基础记录：{len(tasks)}个。",
        f"- 基础表缺失：{', '.join(map(str, missing)) if missing else '无'}。",
        "",
        "| ID | 任务 | 地图 | 要求/任务等级 | 机制、数量、五开模式、来源 | 参考概率 | 前置→后续 | 静态风险 |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in sorted(tasks, key=lambda row: (str(row.get("zone")), int(row.get("quest_id") or 0))):
        pre = ",".join(map(str, task.get("pre_single", [])))
        group = ",".join(map(str, task.get("pre_group", [])))
        pre_text = pre or (f"组:{group}" if group else "—")
        chain = f"{pre_text}→{task.get('next_quest') or '—'}"
        risks = ",".join(task.get("manual_review_reasons", [])) or "—"
        values = [
            str(task.get("quest_id")),
            str(task.get("name") or ""),
            str(task.get("zone") or ""),
            f"{task.get('required_level')}/{task.get('quest_level')}",
            objective_summary(task).replace("|", "/"),
            probability_summary(task).replace("|", "/"),
            chain,
            risks.replace("|", "/"),
        ]
        lines.append("| " + " | ".join(values) + " |")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a compact evidence bundle for every quest ID mentioned in a route markdown file."
    )
    parser.add_argument("route", help="Workspace-relative route markdown path")
    parser.add_argument(
        "--foundation",
        default="data/routes/horde/blood-elf/35-55-task-foundation-enriched.json",
    )
    parser.add_argument(
        "--output",
        default="data/routes/horde/blood-elf/current-route-task-evidence.json",
    )
    parser.add_argument(
        "--summary",
        default="docs/archive/analysis/2026-08-06-current-route-static-evidence-matrix.md",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    route_path = (root / args.route).resolve()
    foundation_path = (root / args.foundation).resolve()
    output_path = (root / args.output).resolve()
    summary_path = (root / args.summary).resolve()

    route_ids = parse_route_quest_ids(route_path.read_text(encoding="utf-8"))
    payload = json.loads(foundation_path.read_text(encoding="utf-8"))
    task_by_id = {
        int(task["quest_id"]): task
        for task in payload.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("quest_id"), int)
    }

    found = [compact_task(task_by_id[quest_id]) for quest_id in route_ids if quest_id in task_by_id]
    missing = [quest_id for quest_id in route_ids if quest_id not in task_by_id]

    result = {
        "schema_version": 1,
        "source_route": str(route_path.relative_to(root)),
        "source_foundation": str(foundation_path.relative_to(root)),
        "questie_version": payload.get("questie_version"),
        "questie_sha256": payload.get("questie_sha256"),
        "route_id_count": len(route_ids),
        "found_task_count": len(found),
        "missing_ids": missing,
        "tasks": found,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_summary(found, missing, summary_path, root)
    print(
        json.dumps(
            {
                "route_id_count": len(route_ids),
                "found_task_count": len(found),
                "missing_ids": missing,
                "output": str(output_path.relative_to(root)),
                "summary": str(summary_path.relative_to(root)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
