from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"data/routes/workbench-compare/workbench-diff.json").read_text(encoding="utf-8"))
print("GLOBAL")
print(json.dumps(data["controls"],ensure_ascii=False,indent=2))
print("\nROUTES")
for key,row in data["routes"].items():
    s=row["summary"]
    print(json.dumps({
      "key":key,
      "steps":[s["step_count_old"],s["step_count_new"]],
      "titles_same":s["step_title_sequence_same"],
      "old_status":s["route_status_old"],
      "new_status":s["route_status_new"],
      "old_map":s["map_old"],
      "new_map":s["map_new"],
      "task_seq_changed":s["steps_task_sequence_changed"],
      "old_task_only":s["steps_old_task_only_total"],
      "new_task_only":s["steps_new_task_only_total"],
    },ensure_ascii=False))
