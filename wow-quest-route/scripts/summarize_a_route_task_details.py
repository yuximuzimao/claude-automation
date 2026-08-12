from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/routes/horde/blood-elf/39-55-a-route-task-details.json"
OUTPUT = ROOT / "docs/analysis/2026-08-06-a-route-task-coordinate-summary.md"


def fmt_points(points: list[dict[str, Any]]) -> str:
    rendered = []
    for point in points[:3]:
        x = point.get("x")
        y = point.get("y")
        zone_id = point.get("zone_id")
        if x is None or y is None:
            continue
        rendered.append(f"{zone_id}:{x:.1f},{y:.1f}")
    return "; ".join(rendered) or "—"


def fmt_entities(entities: list[dict[str, Any]]) -> str:
    values = []
    for entity in entities[:4]:
        values.append(f"{entity.get('name')}@{fmt_points(entity.get('points') or [])}")
    return "；".join(values) or "—"


def main() -> None:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    lines = [
        "# A路线任务坐标与前置压缩摘要",
        "",
        "来源：Questie v11.32.3与当前A路线候选。坐标只用于定位任务簇，不替代道路与实跑路径。",
        "",
    ]
    for block in payload["blocks"]:
        lines.extend([f"## {block['block']}", ""])
        for task in block["tasks"]:
            starts = fmt_entities(task.get("start_entities") or [])
            finishes = fmt_entities(task.get("finish_entities") or [])
            objective_bits = []
            for objective in task.get("objectives") or []:
                sources = objective.get("sources") or []
                source_text = "；".join(
                    f"{source.get('name')}@{fmt_points(source.get('points') or [])}"
                    for source in sources[:4]
                )
                objective_bits.append(
                    f"{objective.get('required_count') or 1}×{source_text or objective.get('mechanic') or objective.get('objective_type')}"
                )
            objectives = " / ".join(objective_bits) or (task.get("objective_text_zh") or task.get("objective_text_en") or "—")
            pre = task.get("pre_group") or task.get("pre_single") or []
            lines.append(
                f"- {task['quest_id']}《{task.get('name')}》[{task.get('category')}] "
                f"req{task.get('required_level')} q{task.get('quest_level')} xp{task.get('xp')}；"
                f"前置{pre or '—'}；接：{starts}；交：{finishes}；目标：{objectives}"
            )
        lines.append("")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
