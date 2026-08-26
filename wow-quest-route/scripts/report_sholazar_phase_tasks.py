from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
SKELETON = ROOT / "data/route-atlas/sholazar-route-skeleton.json"
OUT = ROOT / "docs/analysis/2026-08-26-sholazar-phase-task-windows.md"
ZONE_ID = "3711"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def anchors(rows: list[dict[str, Any]]) -> str:
    out = []
    for row in rows or []:
        rep = (row.get("representative_by_zone") or {}).get(ZONE_ID) or {}
        xy = "?,?"
        if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            xy = f"{float(rep['x']):.1f},{float(rep['y']):.1f}"
        out.append(f"{row.get('name') or '?'}@{xy}")
    return ", ".join(out) or "-"


def main() -> None:
    foundation = load(FOUNDATION)
    skeleton = load(SKELETON)
    tasks = {int(t["quest_id"]): t for t in foundation.get("tasks", [])}

    lines = [
        "# 索拉查盆地逐任务簇插入窗口",
        "",
        "用途：只服务当前正式路线插入。每项同时看前置、接取Hub、目标和交付Hub；不把坐标最近邻当执行顺序。",
        "",
    ]
    for phase in skeleton.get("phases") or []:
        lines.append(f"## {phase['id']}｜{phase['title']}")
        lines.append("")
        for qid in phase.get("task_ids") or []:
            t = tasks[int(qid)]
            deps = sorted(set(int(x) for x in ((t.get("pre_all") or []) + (t.get("parent_active") or []))))
            pre_any = [int(x) for x in (t.get("pre_any") or [])]
            lines.append(
                f"- {qid}《{t.get('name')}》｜pre_all={deps or '-'} pre_any={pre_any or '-'}｜"
                f"接:{anchors(t.get('start_entities') or [])}｜交:{anchors(t.get('finish_entities') or [])}｜"
                f"obj:{(t.get('objective_text_zh') or '').replace(chr(10), ' ')[:180]}"
            )
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
