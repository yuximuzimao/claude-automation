from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"

AMBER_POINT_INDEX = 169
BOGOROK_POINT_INDEX = 170


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["borean"]
    points = route["points"]

    amber = points[AMBER_POINT_INDEX]
    bogorok = points[BOGOROK_POINT_INDEX]
    if amber[2] != "系统鸟点：考达拉 → 琥珀崖":
        raise RuntimeError(f"Unexpected Amber Ledge point {AMBER_POINT_INDEX}: {amber[2]!r}")
    if "博古洛克前哨站" not in str(bogorok[2]):
        raise RuntimeError(f"Unexpected Bogorok point {BOGOROK_POINT_INDEX}: {bogorok[2]!r}")

    if len(amber) <= 6 or amber[6] != "taxi":
        raise RuntimeError(f"Amber arrival must remain system taxi; got {amber[6] if len(amber) > 6 else None!r}")
    if len(bogorok) <= 6:
        bogorok.extend([None] * (7 - len(bogorok)))
    if bogorok[6] not in {"taxi", "ride"}:
        raise RuntimeError(f"Unexpected Bogorok inbound transport: {bogorok[6]!r}")

    old_action = "从Transitus Shield乘系统航线返回琥珀崖，落地后直接转乘博古洛克"
    new_action = "从Transitus Shield乘系统航线返回琥珀崖；博古洛克飞行点尚未开启，落地后沿道路骑马北上博古洛克"
    if amber[3] == old_action:
        amber[3] = new_action
    elif amber[3] != new_action:
        raise RuntimeError(f"Unexpected Amber action: {amber[3]!r}")

    bogorok[6] = "ride"

    group = next(
        (
            row for row in route["stepGroups"]
            if int(row["start"]) <= AMBER_POINT_INDEX <= int(row["end"])
        ),
        None,
    )
    if group is None:
        raise RuntimeError("Could not locate the logical step containing the Amber Ledge flight point")

    old_title = "永生之盾收尾 → 系统鸟转北部"
    new_title = "永生之盾收尾 → 系统鸟回琥珀崖 → 骑马北上"
    if group.get("title") == old_title:
        group["title"] = new_title
    elif group.get("title") != new_title:
        raise RuntimeError(f"Unexpected step title: {group.get('title')!r}")

    old_summary = "回永生之盾飞行点 → 从Transitus Shield乘系统航线返回琥珀崖，落地后直接转乘博古洛克。"
    new_summary = "回永生之盾飞行点 → 从Transitus Shield乘系统航线返回琥珀崖；博古洛克飞行点尚未开启，落地后沿道路骑马北上，抵达后再开点。"
    if group.get("summary") == old_summary:
        group["summary"] = new_summary
    elif group.get("summary") != new_summary:
        raise RuntimeError(f"Unexpected step summary: {group.get('summary')!r}")

    ROUTES.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "route": "borean",
        "amber_point": AMBER_POINT_INDEX,
        "amber_transport": amber[6],
        "bogorok_point": BOGOROK_POINT_INDEX,
        "bogorok_transport": bogorok[6],
        "step_title": group["title"],
        "step_summary": group["summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
