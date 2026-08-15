from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/routes/route-atlas-workbench.html"
START = "/* ROUTE_DATA_START */"
END = "/* ROUTE_DATA_END */"


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

    # User-visible route text must not expose internal A/C/T quest-id notation.
    visible = "\n".join(
        str(value)
        for route in routes.values()
        for point in route.get("points", [])
        for value in point[2:6]
    )
    if re.search(r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}", visible):
        raise SystemExit("internal quest action token leaked into workbench text")

    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
