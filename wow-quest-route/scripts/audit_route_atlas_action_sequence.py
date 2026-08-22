from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / ".ai-bridge/route-atlas-action-sequence-audit.md"

TASK_RE = re.compile(r"《([^》]+)》")
AUTHOR_WORDS = ("第一轮", "第二轮", "第三轮", "回访", "回收", "收尾", "终局", "开场", "机会插点", "本轮")


def ordered_task_events(action: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    for line in action.splitlines():
        # Split an action line into verb-led segments so `交A → 接B` is interpreted
        # in the actual written order instead of letting the first verb capture B.
        matches = list(re.finditer(r"(?:自动)?(接|做|交)", line))
        for idx, match in enumerate(matches):
            verb = match.group(1)
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
            body = line[start:end]
            for task in TASK_RE.findall(body):
                events.append((verb, task))
    return events


def audit_route(key: str, route: dict) -> list[str]:
    lines = [f"# {route['title']} ({key})", ""]
    active = defaultdict(int)
    suspicious: list[str] = []

    for step_no, group in enumerate(route["stepGroups"], 1):
        lines.append(f"## 步骤 {step_no}｜{group['title']}")
        for point_idx in range(group["start"], group["end"] + 1):
            point = route["points"][point_idx]
            label = point[2]
            action = point[3]
            rendered = action.replace("\n", "\n    ")
            lines.append(f"- {label}：{rendered}")

            for word in AUTHOR_WORDS:
                if word in label or word in action:
                    suspicious.append(f"步骤{step_no} {label}: 仍含作者过程词“{word}”")

            for verb, task in ordered_task_events(action):
                if verb == "接":
                    active[task] += 1
                elif verb == "交":
                    if active[task] > 0:
                        active[task] -= 1
                    elif not any(token in action for token in ("若携带", "若已", "若途中", "若死亡泥潭", "若五号")):
                        suspicious.append(f"步骤{step_no} {label}: 《{task}》出现交付，但此前动作序列未见对应接取（可能是跨图携带/解析误报，需人工确认）")
                elif verb == "做" and active[task] <= 0:
                    suspicious.append(f"步骤{step_no} {label}: 《{task}》出现执行，但此前动作序列未见对应接取（可能是同名后续/解析误报，需人工确认）")
        lines.append("")

    lines.append("### 自动异常信号")
    if suspicious:
        lines.extend(f"- {row}" for row in suspicious)
    else:
        lines.append("- 无")
    lines.append("")
    return lines


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    keys = sys.argv[1:] or ["zang", "nagrand"]
    out: list[str] = []
    for key in keys:
        if key not in routes:
            raise SystemExit(f"unknown route: {key}")
        out.extend(audit_route(key, routes[key]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
