"""Frozen pre-Stage-12 candidate publisher compatibility probe.

It may still render in-memory legacy candidates for migration comparison, but write mode is disabled
until Stage 12 is rebuilt on fresh Stage-5+ lifecycle outputs. It is not a current lifecycle consumer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_profiles import load_route_profile, validate_route_profile
from lib.route_publisher import build_route_payload
from lib.task_cards import load_all_task_cards

TEMPLATE = ROOT / "data/routes/route-atlas-workbench.html"
CANDIDATE_JSON_DIR = ROOT / "data/route-atlas/candidates"
CANDIDATE_HTML_DIR = ROOT / "data/routes"
START = "/* ROUTE_DATA_START */"
END = "/* ROUTE_DATA_END */"
DEFERRED_NOTE_MARKER = "【需要单独修正优化】"


def render_candidate_html(routes: dict[str, dict]) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(routes, ensure_ascii=False, separators=(",", ":"))
    prefix = f"const ROUTES={START}"
    start = html.find(prefix)
    if start < 0:
        raise RuntimeError("candidate template route data start marker not found")
    data_start = start + len(prefix)
    data_end = html.find(END, data_start)
    if data_end < 0:
        raise RuntimeError("candidate template route data end marker not found")
    return html[:data_start] + payload + html[data_end:]


def validate_candidate(profile: dict, route: dict) -> None:
    publish_key = profile["display"]["publish_key"]
    if not route.get("points"):
        raise RuntimeError(f"candidate route has no points: {publish_key}")
    if not route.get("stepGroups"):
        raise RuntimeError(f"candidate route has no stepGroups: {publish_key}")
    if len(route["stepGroups"]) != len(profile["step_groups"]):
        raise RuntimeError(f"candidate step count mismatch: {publish_key}")
    image = ROOT / "data/routes" / route["image"]
    if not image.exists():
        raise RuntimeError(f"candidate map image missing: {image}")
    for index, group in enumerate(route["stepGroups"], 1):
        if not str(group.get("actionHtml") or "").strip():
            raise RuntimeError(f"candidate actionHtml missing: {publish_key} step {index}")
    visible = json.dumps(route, ensure_ascii=False)
    if DEFERRED_NOTE_MARKER in visible:
        raise RuntimeError("deferred note optimization marker leaked into candidate player output")


def _profile_ids_from_disk() -> list[str]:
    rows: list[tuple[int, str]] = []
    for path in (ROOT / "data/route-profiles").glob("*.json"):
        if path.name == "schema.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        profile_id = str(payload.get("profile_id") or path.stem)
        rows.append((int((payload.get("display") or {}).get("order", 0)), profile_id))
    return [profile_id for _, profile_id in sorted(rows, key=lambda row: (row[0], row[1]))]


def publish_many(profile_ids: list[str], *, write: bool) -> dict[str, object]:
    if write:
        raise RuntimeError(
            "FROZEN LEGACY-COMPAT: candidate writes stay disabled until Stage 12 consumes fresh lifecycle outputs"
        )
    if not profile_ids:
        raise RuntimeError("no Route Profiles requested for candidate publication")
    cards = load_all_task_cards()
    combined_routes: dict[str, dict] = {}
    results: list[dict[str, object]] = []

    for profile_id in profile_ids:
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        validate_route_profile(profile, expected_profile_id=profile_id, known_task_cards=cards)
        publish_key = str(profile["display"]["publish_key"])
        if publish_key in combined_routes:
            raise RuntimeError(f"duplicate candidate publish_key: {publish_key}")
        route = build_route_payload(profile_id, profile=profile, cards=cards)
        validate_candidate(profile, route)
        combined_routes[publish_key] = route

        json_path = CANDIDATE_JSON_DIR / f"{publish_key}.json"
        html_path = CANDIDATE_HTML_DIR / f"route-atlas-workbench-candidate-{publish_key}.html"
        if write:
            CANDIDATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps({publish_key: route}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            html_path.write_text(render_candidate_html({publish_key: route}), encoding="utf-8")
        results.append({
            "profile_id": profile_id,
            "publish_key": publish_key,
            "point_count": len(route["points"]),
            "step_count": len(route["stepGroups"]),
            "map_label_count": len(route["labels"]),
            "task_count": len(profile["task_ids"]),
            "json_path": str(json_path.relative_to(ROOT)),
            "html_path": str(html_path.relative_to(ROOT)),
        })

    combined_json_path = CANDIDATE_JSON_DIR / "all-routes.json"
    combined_html_path = CANDIDATE_HTML_DIR / "route-atlas-workbench-candidate-all.html"
    if write:
        CANDIDATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
        combined_json_path.write_text(json.dumps(combined_routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        combined_html_path.write_text(render_candidate_html(combined_routes), encoding="utf-8")

    return {
        "profile_count": len(profile_ids),
        "route_count": len(combined_routes),
        "routes": results,
        "combined_json_path": str(combined_json_path.relative_to(ROOT)),
        "combined_html_path": str(combined_html_path.relative_to(ROOT)),
        "write": write,
    }


def publish(profile_id: str, *, write: bool) -> dict[str, object]:
    result = publish_many([profile_id], write=write)
    row = dict(result["routes"][0])
    row["write"] = write
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Route Profiles into isolated candidate workbench JSON/HTML.")
    parser.add_argument("profile_ids", nargs="*")
    parser.add_argument("--all", action="store_true", help="Publish every Route Profile found under data/route-profiles.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.all and args.profile_ids:
        raise SystemExit("use either explicit profile_ids or --all, not both")
    profile_ids = _profile_ids_from_disk() if args.all else args.profile_ids
    print(json.dumps(publish_many(profile_ids, write=args.write), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
