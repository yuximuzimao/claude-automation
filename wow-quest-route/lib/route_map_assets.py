from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = PROJECT_ROOT / "data/routes/maps"
MANIFEST_PATH = MAP_DIR / "manifest.json"
LABELS_PATH = MAP_DIR / "labels-zhcn.json"


@lru_cache(maxsize=1)
def load_map_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def map_entries_by_zone() -> dict[int, dict[str, Any]]:
    manifest = load_map_manifest()
    return {int(entry["zone_id"]): entry for entry in manifest.get("maps", [])}


def route_map_entry(zone_id: int) -> dict[str, Any]:
    try:
        return map_entries_by_zone()[int(zone_id)]
    except KeyError as exc:
        raise KeyError(f"Route Atlas map manifest has no zone_id={zone_id}") from exc


def route_map_filename(zone_id: int, *, prefer_hd: bool = True) -> str:
    entry = route_map_entry(zone_id)
    if prefer_hd and entry.get("hd_status") == "hd" and entry.get("hd_file"):
        hd_path = MAP_DIR / entry["hd_file"]
        if hd_path.exists():
            return str(entry["hd_file"])
    fallback = str(entry["file"])
    fallback_path = MAP_DIR / fallback
    if not fallback_path.exists():
        raise FileNotFoundError(f"Route Atlas map file missing for zone_id={zone_id}: {fallback_path}")
    return fallback


def route_map_href(zone_id: int, *, prefer_hd: bool = True) -> str:
    """Return the portable HTML href relative to data/routes/*.html."""
    return f"maps/{route_map_filename(zone_id, prefer_hd=prefer_hd)}"


def route_map_status(zone_id: int) -> dict[str, Any]:
    entry = route_map_entry(zone_id)
    filename = route_map_filename(zone_id, prefer_hd=True)
    return {
        "zone_id": int(zone_id),
        "status": "hd" if filename == entry.get("hd_file") else "fallback",
        "filename": filename,
        "validation_mode": entry.get("hd_validation_mode"),
        "fallback_reason": entry.get("hd_fallback_reason"),
    }


@lru_cache(maxsize=1)
def load_map_labels() -> dict[str, Any]:
    if not LABELS_PATH.exists():
        return {"maps": {}}
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def route_map_labels(zone_id: int) -> list[dict[str, Any]]:
    """Return optional zhCN hint labels in the shared 0-100 map coordinate frame."""
    zone = load_map_labels().get("maps", {}).get(str(int(zone_id)), {})
    labels = zone.get("labels", [])
    return [dict(label) for label in labels]


def clear_map_manifest_cache() -> None:
    load_map_manifest.cache_clear()
    map_entries_by_zone.cache_clear()
    load_map_labels.cache_clear()
