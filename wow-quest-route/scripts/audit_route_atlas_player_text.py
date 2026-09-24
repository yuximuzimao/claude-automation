from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER_ROOT = ROOT / "data/generated/route-lifecycle/profiles"

VAGUE_ACTION_PATTERNS = (
    r"处理一次性任务", r"一次性任务", r"本地任务", r"本地接交",
    r"当前已完成任务", r"已完成的.*任务", r"北部已完成任务",
    r"批量交", r"集中交(?!《)", r"接齐(?!《)", r"交并接", r"接并做",
    r"交并", r"共享目标簇", r"古树/冰莓/织法者", r"显示锚点",
)
STEP_TITLE_PROCESS_PATTERNS = (
    r"第[一二三四五六七八九十0-9]+次回收",
    r"补漏",
    r"重新整理",
    r"保证不断链",
)
ACTION_GRAMMAR_FORBIDDEN_PATTERNS = (
    r"》[:：]", r"（五号分别）",
    r"(?:^|\n)\s*(?:否则|沿路推进|沿路补|推进《|确认《|暂不做|保持已完成未交|只携带|五号分别|立即检查)",
    r"(?:^|\n)\s*购买\d", r"(?:^|\n)\s*零经验重复任务",
    r"；\s*(?:若|否则|立即检查|只携带|不等待|不专程)",
    r"(?:^|\n).*不选择前往.*出发对话", r"(?:^|\n).*回地面.*",
    r"拾取[^\n]*→\s*接《", r"(?:^|\n)\s*(?:乘系统鸟：|乘龙：|任务脚本飞行：|启动任务飞行：)",
    r"(?:^|\n).*传送到达拉然",
)
CONDITIONAL_LINE_RE = re.compile(r"^\s*若")
EXPLICIT_TASK_OPERATION_RE = re.compile(r"(?:接|做|交)《[^》]+》")


def main() -> None:
    bad: list[dict[str, object]] = []
    checked = 0
    for path in sorted(PUBLISHER_ROOT.glob("*/publisher.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "blocked":
            continue
        checked += 1
        profile_id = str(data.get("profile_id") or path.parent.name)
        for step_index, step in enumerate(data.get("steps") or [], 1):
            title = str(step.get("title") or "")
            if not title:
                bad.append({"profile_id": profile_id, "step": step_index, "kind": "empty_step_title"})
            for pattern in STEP_TITLE_PROCESS_PATTERNS:
                if re.search(pattern, title):
                    bad.append({"profile_id": profile_id, "step": step_index, "kind": "process_step_title", "pattern": pattern, "text": title})
            for line_index, line in enumerate(step.get("lines") or [], 1):
                text = str(line.get("text") or "")
                line_type = str(line.get("type") or "")
                if not text:
                    bad.append({"profile_id": profile_id, "step": step_index, "line": line_index, "kind": "empty_line"})
                    continue
                if line_type == "location":
                    continue
                if CONDITIONAL_LINE_RE.search(text) and not EXPLICIT_TASK_OPERATION_RE.search(text):
                    bad.append({"profile_id": profile_id, "step": step_index, "line": line_index, "kind": "conditional_without_task_operation", "text": text})
                audit_text = re.sub(r"《[^》]+》", "《任务》", text)
                for pattern in (*VAGUE_ACTION_PATTERNS, *ACTION_GRAMMAR_FORBIDDEN_PATTERNS):
                    if re.search(pattern, audit_text):
                        bad.append({"profile_id": profile_id, "step": step_index, "line": line_index, "kind": "invalid_player_text", "pattern": pattern, "text": text})

    report = {"checked_profiles": checked, "issues": bad}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
