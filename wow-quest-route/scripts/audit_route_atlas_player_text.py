from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"

# These phrases are not automatically wrong in prose, but in point actions they usually
# hide the exact accept/turn-in/task operation the player needs while actively playing.
VAGUE_ACTION_PATTERNS = (
    r"处理一次性任务",
    r"一次性任务",
    r"本地任务",
    r"本地接交",
    r"当前已完成任务",
    r"已完成的.*任务",
    r"北部已完成任务",
    r"批量交",
    r"集中交(?!《)",
    r"接齐(?!《)",
    r"交并接",
    r"接并做",
    r"交并",
    r"共享目标簇",
    r"古树/冰莓/织法者",
    r"显示锚点",
)

# Compact same-verb handoffs are intentionally allowed in the player HUD, for example
# `交《A》《B》《C》` or `接《D》《E》`. The verb applies to the contiguous task-name run;
# this keeps dense hub handoffs readable without repeating `交/接` before every quest.
IMPLICIT_HANDOFF_PATTERNS: tuple[str, ...] = ()

# Explicit cross-map carry tasks are allowed to remain open at the end of the current map.
# Anything else accepted without a visible `交《任务名》` is a route integrity failure.
LIFECYCLE_ALLOWLIST = {
    "zang": {"通知塞纳里奥议会"},
    "borean": {"前往莫亚基港口"},
    "dragonblight": {"前往征服堡，自求多福吧！", "前往圣光据点！", "黑暗的骚动", "魔法王国达拉然"},
    "dalaran": {"赫米特·奈辛瓦里哪去了？", "勇士的召唤！", "作战准备"},
}


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    bad = []
    for route_key, route in routes.items():
        for point_index, point in enumerate(route.get("points", []), 1):
            title = str(point[2]) if len(point) > 2 else ""
            action = str(point[3]) if len(point) > 3 else ""
            if not title or not action:
                bad.append((route_key, point_index, title, action, "empty title/action"))
                continue
            for pattern in (*VAGUE_ACTION_PATTERNS, *IMPLICIT_HANDOFF_PATTERNS):
                if re.search(pattern, action):
                    bad.append((route_key, point_index, title, action, pattern))
        for step_index, group in enumerate(route.get("stepGroups", []), 1):
            summary = str(group.get("summary", ""))
            if not summary:
                bad.append((route_key, step_index, group.get("title", ""), summary, "empty summary"))

    lifecycle = []
    handoff_re = re.compile(r"(?<!暂不)(自动接|右键接|接|交)((?:《[^》]+》(?:[、，\s]*))+)" )
    for route_key, route in routes.items():
        accepted: list[tuple[str, int]] = []
        turned_in: list[tuple[str, int]] = []
        for point_index, point in enumerate(route.get("points", []), 1):
            action = str(point[3]) if len(point) > 3 else ""
            for verb, block in handoff_re.findall(action):
                names = re.findall(r"《([^》]+)》", block)
                target = turned_in if verb == "交" else accepted
                target.extend((name, point_index) for name in names)
        turned_names = {name for name, _ in turned_in}
        allowed_open = LIFECYCLE_ALLOWLIST.get(route_key, set())
        for name, point_index in accepted:
            if name not in turned_names and name not in allowed_open:
                lifecycle.append((route_key, point_index, name))

    if lifecycle:
        print("UNEXPLAINED_ACCEPT_WITHOUT_VISIBLE_TURNIN")
        for route_key, index, name in lifecycle:
            print(f"{route_key}\t{index}\t{name}")

    if bad:
        print("VAGUE_OR_INVALID_PLAYER_TEXT")
        for route_key, index, title, text, reason in bad:
            print(f"{route_key}\t{index}\t{title}\t{reason}\t{text}")
    if bad or lifecycle:
        raise SystemExit(1)
    print("player-text audit PASS")


if __name__ == "__main__":
    main()
