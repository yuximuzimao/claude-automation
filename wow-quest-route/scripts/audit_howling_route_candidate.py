from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
FOUNDATION = ROOT / "data/route-atlas/howling-fjord-task-foundation.json"
OUT = ROOT / "data/route-atlas/howling-fjord-route-candidate-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-26-howling-fjord-route-candidate-audit.md"

VERB_RE = re.compile(r"接|交|做")
TASK_RE = re.compile(r"《([^》]+)》")


def parse_ops(route: dict[str, Any], name_to_qid: dict[str, int]) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    ordinal = 0
    for point_index, point in enumerate(route.get("points", [])):
        action = str(point[3] if len(point) > 3 else "")
        for line_index, line in enumerate(action.splitlines()):
            verbs = [(m.start(), m.group(0)) for m in VERB_RE.finditer(line)]
            for task_match in TASK_RE.finditer(line):
                name = task_match.group(1)
                qid = name_to_qid.get(name)
                if qid is None:
                    continue
                prior = [item for item in verbs if item[0] < task_match.start()]
                if not prior:
                    continue
                verb = prior[-1][1]
                ops.append({
                    "ordinal": ordinal,
                    "point": point_index,
                    "line": line_index,
                    "verb": verb,
                    "quest_id": qid,
                    "name": name,
                    "text": line,
                })
                ordinal += 1
    return ops


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["howling"]
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = {int(t["quest_id"]): t for t in foundation.get("tasks", [])}
    name_to_qid: dict[str, int] = {}
    duplicate_names: set[str] = set()
    for qid, task in tasks.items():
        name = str(task["name"])
        if name in name_to_qid and name_to_qid[name] != qid:
            duplicate_names.add(name)
        else:
            name_to_qid[name] = qid
    for name in duplicate_names:
        name_to_qid.pop(name, None)

    ops = parse_ops(route, name_to_qid)
    accepts: dict[int, list[dict[str, Any]]] = {qid: [] for qid in tasks}
    turns: dict[int, list[dict[str, Any]]] = {qid: [] for qid in tasks}
    dos: dict[int, list[dict[str, Any]]] = {qid: [] for qid in tasks}
    for op in ops:
        target = accepts if op["verb"] == "接" else turns if op["verb"] == "交" else dos
        target[op["quest_id"]].append(op)

    missing_accept = [qid for qid in tasks if not accepts[qid]]
    missing_turn = [qid for qid in tasks if not turns[qid]]
    duplicate_accept = [qid for qid in tasks if len(accepts[qid]) > 1]
    duplicate_turn = [qid for qid in tasks if len(turns[qid]) > 1]

    dependency_violations: list[dict[str, Any]] = []
    parent_violations: list[dict[str, Any]] = []
    for qid, task in tasks.items():
        if not accepts[qid]:
            continue
        accept_ord = accepts[qid][0]["ordinal"]
        pre_any = [int(x) for x in (task.get("pre_any") or []) if int(x) in tasks]
        pre_all = [int(x) for x in (task.get("pre_all") or []) if int(x) in tasks]
        parent = [int(x) for x in (task.get("parent_active") or []) if int(x) in tasks]

        if pre_any:
            valid = [dep for dep in pre_any if turns.get(dep) and turns[dep][0]["ordinal"] < accept_ord]
            if not valid:
                dependency_violations.append({"quest_id": qid, "name": task["name"], "kind": "pre_any", "required": pre_any, "accept": accepts[qid][0]})
        missing_all = [dep for dep in pre_all if not turns.get(dep) or turns[dep][0]["ordinal"] >= accept_ord]
        if missing_all:
            dependency_violations.append({"quest_id": qid, "name": task["name"], "kind": "pre_all", "required": missing_all, "accept": accepts[qid][0]})
        for dep in parent:
            if not accepts.get(dep) or accepts[dep][0]["ordinal"] >= accept_ord:
                parent_violations.append({"quest_id": qid, "name": task["name"], "parent": dep, "reason": "parent_not_active_before_accept"})
                continue
            if turns.get(dep) and turns[dep][0]["ordinal"] < accept_ord:
                parent_violations.append({"quest_id": qid, "name": task["name"], "parent": dep, "reason": "parent_already_turned_before_accept"})

    hard = []
    if duplicate_names:
        hard.append("duplicate_task_names_unparseable")
    if missing_accept:
        hard.append("missing_accept")
    if missing_turn:
        hard.append("missing_turnin")
    if duplicate_accept:
        hard.append("duplicate_accept")
    if duplicate_turn:
        hard.append("duplicate_turnin")
    if dependency_violations:
        hard.append("dependency_order")
    if parent_violations:
        hard.append("parent_active_order")

    result = {
        "status": "pass" if not hard else "fail",
        "formal_task_count": len(tasks),
        "parsed_operation_count": len(ops),
        "hard_failures": hard,
        "duplicate_task_names": sorted(duplicate_names),
        "missing_accept": [{"quest_id": qid, "name": tasks[qid]["name"]} for qid in missing_accept],
        "missing_turnin": [{"quest_id": qid, "name": tasks[qid]["name"]} for qid in missing_turn],
        "duplicate_accept": [{"quest_id": qid, "name": tasks[qid]["name"], "count": len(accepts[qid])} for qid in duplicate_accept],
        "duplicate_turnin": [{"quest_id": qid, "name": tasks[qid]["name"], "count": len(turns[qid])} for qid in duplicate_turn],
        "dependency_violations": dependency_violations,
        "parent_active_violations": parent_violations,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 嚎风峡湾候选路线局部状态审查",
        "",
        f"- 结论：**{result['status'].upper()}**。",
        f"- 正式任务：{len(tasks)}；解析接/做/交操作：{len(ops)}。",
        f"- missing accept：{len(missing_accept)}；missing turnin：{len(missing_turn)}。",
        f"- duplicate accept：{len(duplicate_accept)}；duplicate turnin：{len(duplicate_turn)}。",
        f"- 依赖顺序违规：{len(dependency_violations)}；parent-active违规：{len(parent_violations)}。",
        "",
        "## 硬失败",
        "",
    ]
    lines.extend(f"- {item}" for item in hard) if hard else lines.append("- 无。")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "formal": len(tasks),
        "ops": len(ops),
        "missing_accept": len(missing_accept),
        "missing_turnin": len(missing_turn),
        "duplicate_accept": len(duplicate_accept),
        "duplicate_turnin": len(duplicate_turn),
        "dependency_violations": len(dependency_violations),
        "parent_active_violations": len(parent_violations),
    }, ensure_ascii=False, indent=2))
    if hard:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
