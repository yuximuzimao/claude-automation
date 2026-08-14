#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "data/routes/maps"
MANIFEST = MAP_DIR / "manifest.json"
OUT = MAP_DIR / "hd-audit-summary.json"

FALLBACK_REASONS = {
    139: "WotLK Eastern Plaguelands requires ScarletEnclave1-4 overlay pieces not present in the ClassicTBC HD source; unsafe to substitute later-era RuinsOfTheScarletEnclave art.",
    1519: "Stormwind changed in WotLK with the harbor; ClassicTBC HD art is not an exact Wrath-era replacement.",
    4395: "Dalaran uses a non-standard map-tile layout in the available HD source; the generic 4x3/12-tile compositor is not safe for this city map.",
}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    modes: dict[str, int] = {}
    bad_dimensions = []
    total_bytes = 0

    for entry in manifest["maps"]:
        zone_id = int(entry["zone_id"])
        hd_file = entry.get("hd_file")
        hd_path = MAP_DIR / hd_file if hd_file else None
        hd_exists = bool(hd_path and hd_path.exists())
        row = {
            "zone_id": zone_id,
            "zone_dir": entry["zone_dir"],
            "fallback_file": entry["file"],
            "status": "hd" if hd_exists else "fallback",
        }
        if hd_exists:
            with Image.open(hd_path) as image:
                dims = [image.width, image.height]
            total_bytes += hd_path.stat().st_size
            mode = entry.get("hd_validation_mode", "unknown")
            modes[mode] = modes.get(mode, 0) + 1
            row.update({
                "hd_file": hd_file,
                "dimensions": dims,
                "validation_mode": mode,
                "validation_corr": entry.get("hd_validation_corr"),
                "validation_shift": entry.get("hd_validation_shift"),
                "overlay_map_area_id": entry.get("hd_overlay_map_area_id"),
            })
            if dims != [4008, 2672]:
                bad_dimensions.append({"zone_id": zone_id, "file": hd_file, "dimensions": dims})
        else:
            row["reason"] = FALLBACK_REASONS.get(zone_id, "No accepted HD asset recorded in manifest.")
        rows.append(row)

    summary = {
        "schema": "route-atlas-hd-audit/v1",
        "map_count": len(rows),
        "hd_count": sum(row["status"] == "hd" for row in rows),
        "fallback_count": sum(row["status"] == "fallback" for row in rows),
        "validation_modes": modes,
        "hd_total_bytes": total_bytes,
        "hd_total_mib": round(total_bytes / 1024 / 1024, 2),
        "bad_dimensions": bad_dimensions,
        "fallbacks": [row for row in rows if row["status"] == "fallback"],
        "maps": rows,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("map_count", "hd_count", "fallback_count", "validation_modes", "hd_total_mib", "bad_dimensions")}, ensure_ascii=False, indent=2))
    print("fallbacks", [(x["zone_id"], x["zone_dir"], x["reason"]) for x in summary["fallbacks"]])
    return 0 if not bad_dimensions else 1


if __name__ == "__main__":
    raise SystemExit(main())
