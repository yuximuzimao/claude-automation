from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER_VIEW = ROOT / ".ai-bridge/dragonblight-player-view.md"
CONFIG = ROOT / "data/route-atlas/dragonblight-player-step-groups.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE = ROOT / "data/route-atlas/dragonblight-route-coverage.json"


def parse_player_view() -> list[dict[str, object]]:
    lines = PLAYER_VIEW.read_text(encoding="utf-8").splitlines()
    groups: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        match = re.match(r"^## 步骤 \d+｜(.+)$", line)
        if match:
            if current is not None:
                groups.append(current)
            current = {"title": match.group(1), "summary": "", "pointTitles": []}
            continue
        if current is None:
            continue
        if line.startswith("摘要："):
            current["summary"] = line.removeprefix("摘要：")
        elif line.startswith("- "):
            title = line[2:].split("：", 1)[0]
            current["pointTitles"].append(title)
    if current is not None:
        groups.append(current)
    return groups


def main() -> None:
    groups = parse_player_view()
    if len(groups) != 51:
        raise SystemExit(f"expected 51 reviewed Dragonblight groups, got {len(groups)}")

    target = None
    for group in groups:
        titles = list(group.pop("pointTitles"))
        group["pointCount"] = len(titles)
        if "峡谷·冰拳" in titles:
            target = group
    if target is None:
        raise SystemExit("could not find reviewed group containing 峡谷·冰拳")

    # The all-map audit found a real missing return: after Icefist, the player must
    # go back to the hunter camp to turn in 《峡谷追击》 before continuing.
    target["pointCount"] = int(target["pointCount"]) + 1

    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    points = routes["dragonblight"]["points"]
    if sum(int(group["pointCount"]) for group in groups) != len(points):
        raise SystemExit(
            f"reviewed group point count mismatch: groups={sum(int(group['pointCount']) for group in groups)} points={len(points)}"
        )

    config = {
        "version": 1,
        "purpose": "Reviewed player-logical-step boundaries for the Dragonblight Route Atlas. Builder must fail rather than fall back to coarse geometry groups when counts drift.",
        "groups": groups,
    }
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rebuilt = []
    offset = 0
    for group in groups:
        count = int(group["pointCount"])
        rebuilt.append(
            {
                "start": offset,
                "end": offset + count - 1,
                "title": group["title"],
                "summary": group["summary"],
            }
        )
        offset += count
    routes["dragonblight"]["stepGroups"] = rebuilt
    WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if COVERAGE.exists():
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        coverage["step_group_count"] = len(rebuilt)
        coverage["point_count"] = len(points)
        COVERAGE.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"groups": len(rebuilt), "points": len(points)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
