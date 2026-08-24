from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data/route-atlas/grizzly-hills-handoff-audit.json"
OUT = ROOT / ".ai-bridge/grizzly-handoff-summary.md"

def names(rows):
    return ", ".join(str(x.get("name") or x.get("entity_id") or "?") for x in rows) or "—"

payload = json.loads(IN.read_text(encoding="utf-8"))
lines = ["# 灰熊丘陵任务接交摘要", ""]
for row in payload["tasks"]:
    lines.append(
        f"- {row['quest_id']}《{row['name']}》｜接：{names(row['start_entities'])}｜交：{names(row['finish_entities'])}｜pre_any={row['pre_any']}｜pre_all={row['pre_all']}"
    )
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(OUT)
