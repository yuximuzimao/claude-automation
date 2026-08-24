from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
OUT = ROOT / "data/route-atlas/zuldrak-handoff-audit.json"
SUMMARY = ROOT / ".ai-bridge/zuldrak-handoff-summary.md"


def compact_entity(entity: dict) -> dict:
    return {
        "name": entity.get("name"),
        "entity_type": entity.get("entity_type"),
        "entity_id": entity.get("entity_id"),
        "representative_by_zone": entity.get("representative_by_zone"),
    }


def entity_names(rows: list[dict]) -> str:
    return ", ".join(str(x.get("name") or x.get("entity_id") or "?") for x in rows) or "—"


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in payload.get("tasks", []):
        row = {
            "quest_id": int(task.get("quest_id") or 0),
            "name": task.get("name"),
            "scope_status": task.get("scope_status"),
            "start_entities": [compact_entity(x) for x in task.get("start_entities", [])],
            "finish_entities": [compact_entity(x) for x in task.get("finish_entities", [])],
            "pre_any": task.get("pre_any", []),
            "pre_all": task.get("pre_all", []),
            "parent_active": task.get("parent_active", []),
            "next_quest": task.get("next_quest"),
        }
        rows.append(row)
    rows.sort(key=lambda x: x["quest_id"])
    OUT.write_text(json.dumps({"row_count": len(rows), "tasks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 祖达克任务接交摘要", ""]
    for row in rows:
        lines.append(
            f"- {row['quest_id']}《{row['name']}》｜接：{entity_names(row['start_entities'])}｜交：{entity_names(row['finish_entities'])}｜pre_any={row['pre_any']}｜pre_all={row['pre_all']}"
        )
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "audit": str(OUT.relative_to(ROOT)), "summary": str(SUMMARY.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
