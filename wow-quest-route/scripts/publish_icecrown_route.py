from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data/route-atlas/icecrown-route-structured-candidate.json"
AUDIT = ROOT / "data/route-atlas/icecrown-structured-candidate-audit.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"


def main() -> None:
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS" or int(audit.get("hardIssueCount") or 0) != 0:
        raise RuntimeError("Icecrown structured candidate has not passed the hard geometry/coverage audit")

    candidate["status"] = "icecrown_reordered_v1_live_run"
    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    routes["icecrown"] = candidate

    # Preserve the intended Northrend spine even while Sholazar/Howling Fjord formal routes are not yet present.
    if "storm" in routes:
        routes["storm"]["order"] = 6
    routes["icecrown"]["order"] = 7
    if "zuldrak" in routes:
        routes["zuldrak"]["order"] = 9
    if "grizzly" in routes:
        routes["grizzly"]["order"] = 10

    routes = dict(sorted(routes.items(), key=lambda kv: (int(kv[1].get("order", 999)), kv[0])))
    WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "published": "icecrown",
        "order": routes["icecrown"]["order"],
        "steps": len(routes["icecrown"].get("stepGroups") or []),
        "points": len(routes["icecrown"].get("points") or []),
        "timing": routes["icecrown"].get("timing"),
        "orders": {key: value.get("order") for key, value in routes.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
