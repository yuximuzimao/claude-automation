from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/routes/route-atlas-workbench.html"
START = "/* ROUTE_DATA_START */"
END = "/* ROUTE_DATA_END */"
HUD_ACTIONS_START = "/* HUD_GROUP_ACTIONS_START */"
HUD_ACTIONS_END = "/* HUD_GROUP_ACTIONS_END */"
HUD_ACTIONS_PATCH = f"""
{HUD_ACTIONS_START}
const routeAtlasInfoWithFullActions=info;
info=function(){{
  routeAtlasInfoWithFullActions();
  const gr=G[cur],el=document.getElementById('hudAction');
  if(!gr||!el)return;
  const lines=S.slice(gr.start,gr.end+1).map(point=>`${{point.label}}：${{point.action}}`).filter(Boolean);
  el.style.whiteSpace='pre-line';
  el.textContent=lines.join('\\n');
}};
if(Array.isArray(G)&&G.length)info();
{HUD_ACTIONS_END}
"""


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    if not routes:
        raise SystemExit("workbench route set is empty")

    for key, route in routes.items():
        image = ROOT / "data/routes" / route["image"]
        if not image.exists():
            raise SystemExit(f"missing map asset for {key}: {route['image']}")
        if not route.get("points"):
            raise SystemExit(f"route has no points: {key}")
        hearth = route.get("hearthChain")
        if not isinstance(hearth, list) or not hearth or not all(isinstance(value, str) and value for value in hearth):
            raise SystemExit(f"route hearthChain missing/invalid: {key}")
        timing = route.get("timing")
        if not isinstance(timing, dict) or not isinstance(timing.get("centerMinutes"), (int, float)):
            raise SystemExit(f"route timing missing: {key}")
        timing_range = timing.get("rangeMinutes")
        if not isinstance(timing_range, list) or len(timing_range) != 2:
            raise SystemExit(f"route timing range missing: {key}")
        groups = route.get("stepGroups")
        if not isinstance(groups, list) or not groups:
            raise SystemExit(f"route stepGroups missing: {key}")
        for index, group in enumerate(groups, 1):
            step_timing = group.get("timing")
            if not isinstance(step_timing, dict) or not isinstance(step_timing.get("centerMinutes"), (int, float)):
                raise SystemExit(f"step timing missing: {key} step {index}")
            step_range = step_timing.get("rangeMinutes")
            if not isinstance(step_range, list) or len(step_range) != 2:
                raise SystemExit(f"step timing range missing: {key} step {index}")
        if route.get("badgeTitle"):
            raise SystemExit(f"route top-right card must not have a title: {key}")
        if "炉石：" not in str(route.get("badge", "")) or "预计总时间：" not in str(route.get("badge", "")):
            raise SystemExit(f"route top-right hearth/timing card contract broken: {key}")

    html = OUT.read_text(encoding="utf-8")
    payload = json.dumps(routes, ensure_ascii=False, separators=(",", ":"))
    prefix = f"const ROUTES={START}"
    start = html.find(prefix)
    if start < 0:
        raise SystemExit("route data start marker not found")
    data_start = start + len(prefix)
    data_end = html.find(END, data_start)
    if data_end < 0:
        raise SystemExit("route data end marker not found")
    html = html[:data_start] + payload + html[data_end:]

    existing_patch_start = html.find(HUD_ACTIONS_START)
    if existing_patch_start >= 0:
        existing_patch_end = html.find(HUD_ACTIONS_END, existing_patch_start)
        if existing_patch_end < 0:
            raise SystemExit("HUD group-actions end marker not found")
        existing_patch_end += len(HUD_ACTIONS_END)
        html = html[:existing_patch_start] + html[existing_patch_end:]
    script_close = html.rfind("</script>")
    if script_close < 0:
        raise SystemExit("workbench closing script tag not found")
    html = html[:script_close] + HUD_ACTIONS_PATCH + html[script_close:]

    # User-visible route text must not expose internal A/C/T quest-id notation.
    visible = "\n".join(
        str(value)
        for route in routes.values()
        for point in route.get("points", [])
        for value in point[2:6]
    )
    if re.search(r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}", visible):
        raise SystemExit("internal quest action token leaked into workbench text")
    if "function fmtRouteMinutes" not in html or "本段预计：约" not in html:
        raise SystemExit("Route Atlas timing HUD contract missing from HTML")

    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
