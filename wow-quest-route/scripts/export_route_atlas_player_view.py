from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OUT_DIR = ROOT / ".ai-bridge"


def render_route(key: str, route: dict) -> str:
    points = route["points"]
    groups = route["stepGroups"]
    lines = [
        f"# {route['title']}",
        "",
        f"说明：{route.get('sub', '')}",
        f"提示：{route.get('badge', '')}",
        f"图例：{route.get('legend', '')}",
        f"页尾：{route.get('footer', '')}",
        "",
    ]
    for idx, group in enumerate(groups, 1):
        lines.extend([
            f"## 步骤 {idx}｜{group['title']}",
            f"摘要：{group.get('summary', '')}",
        ])
        for point_idx in range(group["start"], group["end"] + 1):
            point = points[point_idx]
            lines.append(f"- {point[2]}：{point[3]}")
            if len(point) > 5 and point[5]:
                lines.append(f"  - 备注：{point[5]}")
            if len(point) > 8 and point[8]:
                lines.append(f"  - 五开待实测：{point[8]}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("route", nargs="?", default="dragonblight", help="route key or 'all'")
    args = parser.parse_args()
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    keys = list(routes) if args.route == "all" else [args.route]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key in keys:
        if key not in routes:
            raise SystemExit(f"unknown route: {key}")
        out = OUT_DIR / f"{key}-player-view.md"
        out.write_text(render_route(key, routes[key]), encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main()
