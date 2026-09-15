from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OLD_PREFIX = "奥格瑞玛 → 精神谷传送门区 → 黑暗之门 → 外域；"
PREFIX = "奥格瑞玛 → 精神谷传送门区 → 诅咒之地黑暗之门前；督军达图恩 → 接《跨越黑暗之门》 → 穿过黑暗之门进入外域；"


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    changed = []
    for key in ("hellfire", "hellfire_dk"):
        route = routes[key]
        action = str(route["points"][0][3])
        if action.startswith(OLD_PREFIX):
            route["points"][0][3] = PREFIX + action[len(OLD_PREFIX):]
            changed.append(key)
        elif not action.startswith(PREFIX):
            route["points"][0][3] = PREFIX + action
            changed.append(key)
        # Keep the semantic HUD action copy aligned with the point action.
        groups = route.get("stepGroups", [])
        if groups:
            html = str(groups[0].get("actionHtml", ""))
            old_line = '<div class="ra-line"><span class="ra-location">奥格瑞玛 → 精神谷传送门区 → 黑暗之门 → 外域</span></div>'
            bad_line = '<div class="ra-line"><span class="ra-location">奥格瑞玛 → 精神谷传送门区 → 诅咒之地黑暗之门前；督军达图恩 → 接《跨越黑暗之门》 → 穿过黑暗之门进入外域</span></div>'
            new_line = '<div class="ra-line"><span class="ra-location">奥格瑞玛 → 精神谷传送门区 → 诅咒之地黑暗之门前；督军达图恩 → 接跨越黑暗之门 → 穿过黑暗之门进入外域</span></div>'
            if bad_line in html:
                groups[0]["actionHtml"] = html.replace(bad_line, new_line, 1)
            elif old_line in html:
                groups[0]["actionHtml"] = html.replace(old_line, new_line, 1)
            elif new_line not in html:
                groups[0]["actionHtml"] = new_line + "\n" + html
    DATA.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("updated:", ", ".join(changed) if changed else "already current")


if __name__ == "__main__":
    main()
