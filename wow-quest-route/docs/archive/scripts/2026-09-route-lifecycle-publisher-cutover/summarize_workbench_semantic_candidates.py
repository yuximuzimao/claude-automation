from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
src=ROOT/"data/routes/workbench-compare/workbench-diff.json"
data=json.loads(src.read_text(encoding="utf-8"))

def strip_title(text):
    return re.sub(r"^步骤\s+\d+/\d+\s*·\s*","",str(text or "")).strip()

lines=["# 同步骤真实任务序列差异候选","","以下只列步骤标题可直接对齐、且任务接/做/交span序列发生变化的步骤。冰冠另行按标题重排对齐。",""]
for key,row in data["routes"].items():
    if key=="icecrown":
        continue
    hits=[]
    for i,d in enumerate(row["steps"],1):
        if strip_title(d["title_old"])!=strip_title(d["title_new"]):
            continue
        if d["task_role_sequence_same"]:
            continue
        hits.append((i,d))
    if not hits:
        continue
    lines += [f"## {key}",""]
    for i,d in hits:
        lines += [
            f"### Step {i}｜{strip_title(d['title_old'])}",
            f"- 旧任务序列：{d['old_task_role_sequence']}",
            f"- 新任务序列：{d['new_task_role_sequence']}",
            f"- 旧独有：{d['old_task_only']}",
            f"- 新独有：{d['new_task_only']}",
            "- 旧HUD：",
            "  " + " / ".join(d["old_action_lines"]),
            "- 新HUD：",
            "  " + " / ".join(d["new_action_lines"]),
            "- 旧备注： " + (" | ".join((n.get("task","")+"："+n.get("text","")).strip("：") for n in d["old_notes"]) or "（无）"),
            "- 新Presentation： " + (" | ".join(f"{p.get('name')}[{p.get('badge')} pending={p.get('pending')}] {p.get('note')}" for p in d["new_presentations"]) or "（无）"),
            "",
        ]
out=ROOT/"data/routes/workbench-compare/semantic-candidates.md"
out.write_text("\n".join(lines),encoding="utf-8")
print(out)
