from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
routes_dir=ROOT/"data/routes"
html=(routes_dir/"route-atlas-workbench.html").read_text(encoding="utf-8")
m=re.search(r"/\* ROUTE_DATA_START \*/(.*?)/\* ROUTE_DATA_END \*/",html,re.S)
if not m: raise SystemExit("old ROUTES marker missing")
old=json.loads(m.group(1))
diff=json.loads((routes_dir/"workbench-compare/workbench-diff.json").read_text(encoding="utf-8"))
for key,row in diff["routes"].items():
    profile=row["profile_id"]
    pub=json.loads((ROOT/f"data/generated/route-lifecycle/profiles/{profile}/publisher.json").read_text(encoding="utf-8"))
    steps=row["steps"]
    old_chars=sum(sum(len(x) for x in d["old_action_lines"]) for d in steps)
    new_chars=sum(sum(len(x) for x in d["new_action_lines"]) for d in steps)
    pending=sum(sum(1 for p in d["new_presentations"] if p.get("pending")) for d in steps)
    pres=sum(len(d["new_presentations"]) for d in steps)
    old_t=(old[key].get("timing") or {})
    new_t=(pub.get("route_timing") or {})
    print(json.dumps({
      "key":key,
      "old_timing":{"status":old_t.get("status"),"center":old_t.get("centerMinutes"),"range":old_t.get("rangeMinutes")},
      "new_timing":{"status":new_t.get("status"),"center":new_t.get("center_minutes"),"range":new_t.get("range_minutes"),"complete":new_t.get("complete")},
      "old_badge":old[key].get("badge"),
      "old_action_chars":old_chars,
      "new_hud_chars":new_chars,
      "hud_ratio":round(new_chars/max(1,old_chars),2),
      "new_presentations":pres,
      "new_pending_presentations":pending,
    },ensure_ascii=False))
