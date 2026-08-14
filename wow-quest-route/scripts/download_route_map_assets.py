#!/usr/bin/env python3
"""Download the localized zone-map image set used by portable route HTML files.

The portable layout is intentionally:

    data/routes/
      <route>.html
      maps/
        <zone-id>-<slug>.jpg
        manifest.json

Route HTML files should only reference ./maps/... so the whole data/routes
folder can be copied to another computer without additional project paths.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZONE_ROOT = ROOT / "data" / "routes" / "world-candidate"
OUT_DIR = ROOT / "data" / "routes" / "maps"
URL_TEMPLATE = "https://wow.zamimg.com/images/wow/maps/zhcn/normal/{zone_id}.jpg"
FALLBACK_URLS = {
    36: "https://olimg.3dmgame.com/uploads/images/xiaz/2019/1219/1576742397832.jpg",
    4395: "https://olimg.3dmgame.com/uploads/images/xiaz/2025/0508/1746687396697.png",
}
USER_AGENT = "Mozilla/5.0 route-atlas-map-cache/1.0"


def zone_dirs() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for path in sorted(ZONE_ROOT.iterdir()):
        if not path.is_dir():
            continue
        match = re.fullmatch(r"(\d+)-(.+)", path.name)
        if not match:
            continue
        out.append((int(match.group(1)), path.name))
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_DIR / "manifest.json"
    previous_manifest = {}
    previous_by_zone = {}
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            previous_by_zone = {int(entry["zone_id"]): entry for entry in previous_manifest.get("maps", [])}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            previous_manifest = {}
            previous_by_zone = {}
    entries = []
    failures = []

    for zone_id, dirname in zone_dirs():
        primary_url = URL_TEMPLATE.format(zone_id=zone_id)
        urls = [primary_url]
        if zone_id in FALLBACK_URLS:
            urls.append(FALLBACK_URLS[zone_id])

        last_error: Exception | None = None
        for url in urls:
            headers = {"User-Agent": USER_AGENT}
            if "3dmgame.com" in url:
                headers["Referer"] = "https://ol.3dmgame.com/"
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    content_type = response.headers.get("Content-Type", "")
                    data = response.read()
                if not content_type.startswith("image/") or len(data) < 1000:
                    raise RuntimeError(f"unexpected response: {content_type}, {len(data)} bytes")

                extension = ".png" if "png" in content_type.lower() else ".jpg"
                filename = f"{dirname}{extension}"
                target = OUT_DIR / filename
                target.write_bytes(data)
                entry = {
                    "zone_id": zone_id,
                    "zone_dir": dirname,
                    "file": filename,
                    "source": url,
                    "fallback": url != primary_url,
                    "bytes": len(data),
                }
                previous = previous_by_zone.get(zone_id, {})
                for key, value in previous.items():
                    if key.startswith("hd_"):
                        entry[key] = value
                entries.append(entry)
                print(f"OK   {zone_id:4d}  {filename}  {len(data):>7d} bytes")
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as exc:
                last_error = exc
        else:
            failures.append(
                {"zone_id": zone_id, "zone_dir": dirname, "source": urls, "error": str(last_error)}
            )
            print(f"FAIL {zone_id:4d}  {dirname}: {last_error}")

    manifest = {
        "schema": "route-atlas-map-cache/v1",
        "locale": "zhCN",
        "source_pattern": URL_TEMPLATE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "failure_count": len(failures),
        "maps": entries,
        "failures": failures,
    }
    if "hd_summary" in previous_manifest:
        manifest["hd_summary"] = previous_manifest["hd_summary"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nDownloaded {len(entries)} maps; failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
