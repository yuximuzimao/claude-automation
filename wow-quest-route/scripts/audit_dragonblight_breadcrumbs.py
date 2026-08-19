from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT = ROOT / "docs/archive/analysis/2026-08-16-dragonblight-breadcrumb-audit.md"


def main():
    p = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    by_id = {int(t["quest_id"]): t for t in p["tasks"]}
    rows = []
    for qid, t in sorted(by_id.items()):
        if not t.get("is_primary_candidate") or not str(t.get("scope_status", "")).startswith("include_") or t.get("is_dungeon"):
            continue
        breadcrumb_for = t.get("breadcrumb_for")
        breadcrumbs = t.get("breadcrumbs") or []
        exclusive = [int(x) for x in (t.get("exclusive_to") or []) if int(x) in by_id]
        if breadcrumb_for or breadcrumbs or exclusive:
            rows.append((qid, t, breadcrumb_for, breadcrumbs, exclusive))
    lines = ["# 龙骨荒野 breadcrumb / exclusiveTo 审计", ""]
    for qid, t, target, crumbs, exclusive in rows:
        target_name = by_id.get(int(target), {}).get("name") if isinstance(target, int) else None
        ex = [f"{x}《{by_id.get(x, {}).get('name', '?')}》" for x in exclusive]
        cr = [f"{x}《{by_id.get(x, {}).get('name', '?')}》" for x in crumbs]
        lines.append(f"- {qid}《{t['name']}》 breadcrumb_for={target}{'《'+target_name+'》' if target_name else ''} breadcrumbs={cr or '-'} exclusive={ex or '-'}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
