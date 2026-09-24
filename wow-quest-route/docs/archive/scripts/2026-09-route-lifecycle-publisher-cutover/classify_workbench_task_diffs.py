from __future__ import annotations
import json,re
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"data/routes/workbench-compare/workbench-diff.json").read_text(encoding="utf-8"))

def clean_title(s):
    return re.sub(r"^步骤\s+\d+/\d+\s*·\s*","",str(s or "")).strip()

rows=[]
for key,row in data["routes"].items():
    if key=="icecrown":
        continue
    for i,d in enumerate(row["steps"],1):
        if clean_title(d["title_old"])!=clean_title(d["title_new"]) or d["task_role_sequence_same"]:
            continue
        old_text=" ".join(d["old_action_lines"])
        new_text=" ".join(d["new_action_lines"])
        old_true=[name for name in d["old_task_only"] if name not in new_text]
        new_true=[name for name in d["new_task_only"] if name not in old_text]
        old_false=[name for name in d["old_task_only"] if name in new_text]
        new_false=[name for name in d["new_task_only"] if name in old_text]
        old_seq=[tuple(x) for x in d["old_task_role_sequence"]]
        new_seq=[tuple(x) for x in d["new_task_role_sequence"]]
        rows.append({
            "route":key,"step":i,"title":clean_title(d["title_old"]),
            "true_missing_from_new":old_true,
            "true_added_in_new":new_true,
            "span_only_old":old_false,
            "span_only_new":new_false,
            "same_task_multiset":Counter(name for _,name in old_seq)==Counter(name for _,name in new_seq),
            "role_or_order_changed":old_seq!=new_seq,
        })
print(json.dumps(rows,ensure_ascii=False,indent=2))
