from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REACH = ROOT / "data/route-atlas/dragonblight-route-reachability.json"
OUT = ROOT / "docs/archive/analysis/2026-08-16-dragonblight-hub-summary.md"

MANUAL_COORDS = {
    # Questie 11.34.0 has no spawn coordinates for Narf (26647).
    # Warcraft Wiki places Nozzlerust Post around 54.8,23.47; use the post center as a route anchor.
    12043: (54.8, 23.47),
    12052: (54.8, 23.47),
    12112: (54.8, 23.47),
}


def main():
    p = json.loads(REACH.read_text(encoding="utf-8"))
    rows = [r for r in p["rows"] if r["reachable_from_borean_axis"]]
    # Restore three Narf quests whose NPC is real but missing coordinates in Questie.
    for r in p["rows"]:
        if r["quest_id"] in MANUAL_COORDS and not r["reachable_from_borean_axis"]:
            r = dict(r)
            r["reachable_from_borean_axis"] = True
            r["start_coords"] = [list(MANUAL_COORDS[r["quest_id"]])]
            rows.append(r)

    hubs = defaultdict(list)
    item_starts = []
    for r in rows:
        starts = r.get("start_coords") or []
        if not starts:
            item_starts.append(r)
            continue
        x, y = starts[0]
        key = (round(float(x), 1), round(float(y), 1))
        hubs[key].append(r)

    lines = ["# 龙骨荒野可达任务 · 接取Hub摘要", "", f"任务行={len(rows)}；Hub={len(hubs)}。", ""]
    for (x, y), tasks in sorted(hubs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        lines.append(f"## ({x:.1f},{y:.1f})")
        for r in sorted(tasks, key=lambda r: r["quest_id"]):
            deps = sorted(set((r.get("pre_all") or []) + (r.get("pre_any") or []) + (r.get("parent_active") or [])))
            finish = r.get("finish_coords") or []
            obj = r.get("objective_coords") or []
            lines.append(f"- {r['quest_id']}《{r['name']}》 deps={deps or '-'} finish={finish[:1] or '-'} obj={obj[:3] or '-'} note={r['note_decision']}")
        lines.append("")
    lines.append("## 无NPC接取坐标 / 物品触发")
    for r in sorted(item_starts, key=lambda r: r["quest_id"]):
        lines.append(f"- {r['quest_id']}《{r['name']}》 finish={r.get('finish_coords') or '-'} obj={r.get('objective_coords') or '-'}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
