#!/usr/bin/env python3
"""Build Chinese map-label hints from 3.3.5 WorldMapOverlay geometry.

Classic/TBC zhCN names come from pfQuest's generated zhCN zone table, which is
built from localized AreaTable data. Label positions use the center of each
WorldMapOverlay hit rectangle; this tracks the visible English subzone labels
far better than using the center of the overlay texture itself.

Northrend/WotLK-only areas are intentionally left without generated labels
until a trustworthy WotLK zhCN AreaTable source is available. HD terrain is
independent from this optional hint layer.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "data/routes/maps"
MANIFEST = MAP_DIR / "manifest.json"
OUTPUT = MAP_DIR / "labels-zhcn.json"

AREA_CSV = "https://raw.githubusercontent.com/DreamCoreRev/EonsDBC/master/DBFilesClient/csv/WorldMapArea.dbc.csv"
OVERLAY_CSV = "https://raw.githubusercontent.com/DreamCoreRev/EonsDBC/master/DBFilesClient/csv/WorldMapOverlay.dbc.csv"
PFQUEST_ZONES_CLASSIC = "https://raw.githubusercontent.com/shagu/pfQuest/master/db/zhCN/zones.lua"
PFQUEST_ZONES_TBC = "https://raw.githubusercontent.com/shagu/pfQuest/master/db/zhCN/zones-tbc.lua"
UA = "Mozilla/5.0 route-atlas-label-builder/1.0"
MAP_W = 1002.0
MAP_H = 668.0


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def cjk_name(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value)) and not value.lower().startswith("reuse me")


def parse_pfquest_names(text: str) -> dict[int, str]:
    names = {}
    pattern = re.compile(r'^\s*\[(\d+)\]\s*=\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', re.MULTILINE)
    for match in pattern.finditer(text):
        area_id = int(match.group(1))
        name = bytes(match.group(2), "utf-8").decode("unicode_escape") if "\\" in match.group(2) else match.group(2)
        if cjk_name(name):
            names[area_id] = name
    return names


def load_area_meta() -> tuple[dict[int, dict], dict[int, list[list[str]]]]:
    area_rows = list(csv.reader(io.StringIO(get_text(AREA_CSV))))
    overlay_rows = list(csv.reader(io.StringIO(get_text(OVERLAY_CSV))))
    by_zone = {}
    for row in area_rows[1:]:
        if len(row) < 4:
            continue
        try:
            map_area_id = int(row[0])
            continent = int(row[1])
            zone_id = int(row[2])
        except ValueError:
            continue
        by_zone[zone_id] = {
            "map_area_id": map_area_id,
            "continent": continent,
            "texture": row[3].strip().strip('"'),
        }
    by_map_area: dict[int, list[list[str]]] = {}
    for row in overlay_rows[1:]:
        if len(row) < 17:
            continue
        try:
            map_area_id = int(row[1])
        except ValueError:
            continue
        by_map_area.setdefault(map_area_id, []).append(row)
    return by_zone, by_map_area


def first_localized_area_id(row: list[str], names: dict[int, str]) -> int | None:
    for raw in row[2:6]:
        try:
            area_id = int(raw or 0)
        except ValueError:
            continue
        if area_id and area_id in names:
            return area_id
    return None


def label_position(row: list[str]) -> tuple[float, float, str]:
    # WorldMapOverlay columns 13..16 are hit-rect top, left, bottom, right.
    try:
        top, left, bottom, right = (int(row[i] or 0) for i in range(13, 17))
    except (ValueError, IndexError):
        top = left = bottom = right = 0
    if right > left and bottom > top:
        x = ((left + right) / 2.0) / MAP_W * 100.0
        y = ((top + bottom) / 2.0) / MAP_H * 100.0
        return x, y, "hit-rect-center"

    # Rare rows lack a hit rectangle; fall back to the overlay texture center.
    width, height = int(row[9] or 0), int(row[10] or 0)
    offset_x, offset_y = int(row[11] or 0), int(row[12] or 0)
    x = (offset_x + width / 2.0) / MAP_W * 100.0
    y = (offset_y + height / 2.0) / MAP_H * 100.0
    return x, y, "overlay-center"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = parse_pfquest_names(get_text(PFQUEST_ZONES_CLASSIC))
    names.update(parse_pfquest_names(get_text(PFQUEST_ZONES_TBC)))
    zones, overlays = load_area_meta()
    output_maps = {}
    total_labels = 0

    for entry in manifest["maps"]:
        zone_id = int(entry["zone_id"])
        meta = zones.get(zone_id)
        if not meta or meta["continent"] not in (0, 1, 530):
            continue
        labels = []
        seen = set()
        for row in overlays.get(meta["map_area_id"], []):
            area_id = first_localized_area_id(row, names)
            if area_id is None:
                continue
            zh = names[area_id]
            texture = row[8].strip().strip('"')
            key = (zh, texture)
            if key in seen:
                continue
            seen.add(key)
            x, y, method = label_position(row)
            if not (0 <= x <= 100 and 0 <= y <= 100):
                continue
            labels.append({
                "area_id": area_id,
                "texture": texture,
                "zhCN": zh,
                "x": round(x, 2),
                "y": round(y, 2),
                "position_method": method,
            })
        if labels:
            labels.sort(key=lambda item: (item["y"], item["x"], item["zhCN"]))
            output_maps[str(zone_id)] = {
                "zone_dir": entry["zone_dir"],
                "label_count": len(labels),
                "labels": labels,
            }
            total_labels += len(labels)

    result = {
        "schema": "route-atlas-map-labels/v1",
        "locale": "zhCN",
        "source_names": "shagu/pfQuest db/zhCN/zones.lua + zones-tbc.lua",
        "source_geometry": "DreamCoreRev/EonsDBC WorldMapOverlay.dbc.csv",
        "scope": "Classic + TBC only; WotLK-only/Northrend labels intentionally not synthesized",
        "map_count": len(output_maps),
        "label_count": total_labels,
        "maps": output_maps,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"map_count": len(output_maps), "label_count": total_labels}, ensure_ascii=False))
    for zid in (3521, 3518, 3483):
        data = output_maps.get(str(zid))
        if data:
            print(zid, [(x["zhCN"], x["x"], x["y"]) for x in data["labels"][:25]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
