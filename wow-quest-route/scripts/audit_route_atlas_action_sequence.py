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
CONDITIONAL_TOKENS = ("若携带", "若已", "若途中", "若死亡泥潭", "若五号")


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
    seen: set[str] = set()
    suspicious: list[str] = []

    for step_no, group in enumerate(route["stepGroups"], 1):
        lines.append(f"## 步骤 {step_no}｜{group['title']}")
        for point_idx in range(group["start"], group["end"] + 1):
            point = route["points"][point_idx]
            label = point[2]
            action = point[3]
            rendered = action.replace("\n", "\n    ")
            lines.append(f"- {label}：{rendered}")

            conditional = any(token in action for token in CONDITIONAL_TOKENS)
            for verb, task in ordered_task_events(action):
                if verb == "接":
                    active[task] += 1
                    seen.add(task)
                    continue

                if verb == "交":
                    if active[task] > 0:
                        active[task] -= 1
                    elif conditional:
                        # Conditional/fallback turn-ins can legitimately appear at more than one
                        # natural hub visit. This diagnostic does not branch the task state.
                        pass
                    elif task in seen:
                        suspicious.append(
                            f"步骤{step_no} {label}: 《{task}》再次交付，但当前序列已无激活实例（优先检查重复/过期动作）"
                        )
                    else:
                        suspicious.append(
                            f"步骤{step_no} {label}: 《{task}》首次出现就是交付；当前审计未建模地图入口前已接/跨图携带状态，需人工确认入口状态"
                        )
                    seen.add(task)
                    continue

                if verb == "做" and active[task] <= 0:
                    if conditional:
                        pass
                    elif task in seen:
                        suspicious.append(
                            f"步骤{step_no} {label}: 《{task}》执行时当前序列无激活实例（优先检查重排后漏接/过期动作）"
                        )
                    else:
                        suspicious.append(
                            f"步骤{step_no} {label}: 《{task}》首次出现就是执行；当前审计未建模地图入口前已接/跨图携带状态，需人工确认入口状态"
                        )
                    seen.add(task)
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
    keys = sys.argv[1:]
    if not keys:
        raise SystemExit(
            "Specify one or more Route Atlas route keys explicitly, e.g. "
            "python3 scripts/audit_route_atlas_action_sequence.py zang nagrand. "
            "This is a diagnostic, not a default all-route publication gate, because route-entry carried task state is not modeled yet."
        )
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
