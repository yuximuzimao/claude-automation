#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "data/routes/maps"
MANIFEST = MAP_DIR / "manifest.json"

FALLBACK_REASONS = {
    139: "WotLK Eastern Plaguelands needs ScarletEnclave1-4 overlay pieces absent from the ClassicTBC HD source; later-era substitutes are not accepted.",
    1519: "Stormwind changed in WotLK with the harbor; ClassicTBC HD art is not an exact Wrath-era replacement.",
    4395: "Dalaran uses a non-standard map-tile layout in the available HD source; generic 4x3 composition is not accepted.",
}


def infer_validation_mode(entry: dict) -> str:
    corr = entry.get("hd_validation_corr")
    shift = entry.get("hd_validation_shift") or [99, 99]
    if isinstance(corr, (int, float)) and corr >= 0.72 and len(shift) >= 2 and abs(shift[0]) <= 1 and abs(shift[1]) <= 1:
        return "fallback-correlation"
    source = entry.get("hd_source", "")
    if "ClassicTBC" in source and int(entry["zone_id"]) != 1519:
        return "pre-cata-source-trust"
    return "source-trust"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    hd_count = 0
    fallback_count = 0
    for entry in manifest["maps"]:
        zone_id = int(entry["zone_id"])
        hd_file = entry.get("hd_file")
        hd_exists = bool(hd_file and (MAP_DIR / hd_file).exists())
        if hd_exists:
            hd_count += 1
            entry["hd_status"] = "hd"
            entry.pop("hd_fallback_reason", None)
            if not entry.get("hd_validation_mode"):
                entry["hd_validation_mode"] = infer_validation_mode(entry)
        else:
            fallback_count += 1
            entry["hd_status"] = "fallback"
            entry["hd_fallback_reason"] = FALLBACK_REASONS.get(zone_id, "No accepted HD asset.")
            # Never retain a stale HD filename for a fallback entry.
            entry.pop("hd_file", None)
    manifest["hd_summary"] = {
        "hd_count": hd_count,
        "fallback_count": fallback_count,
        "fallback_zone_ids": sorted(FALLBACK_REASONS),
        "policy": "HD first; exact fallback retained for maps whose available HD source is not safe for the WotLK-era route atlas.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["hd_summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
