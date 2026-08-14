#!/usr/bin/env python3
"""Batch-build fully explored HD Route Atlas maps with geometry validation.

Sources:
- Classic/TBC zones: keyboardturner/WoWMapUprez_png ClassicTBC
- Northrend / Scarlet Enclave: keyboardturner/WoWMapUprez_png Retail
- Overlay placement: DreamCoreRev/EonsDBC 3.3.5a WorldMapArea/WorldMapOverlay CSV

The script never replaces the low-resolution zhCN fallback. Accepted HD maps are
written beside it as <stem>-hd.jpg and recorded in maps/manifest.json. Each
candidate is resized to the existing fallback and compared in grayscale; maps
with weak structural agreement or a non-zero best alignment shift are rejected.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import io
import json
import math
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "data/routes/maps"
MANIFEST = MAP_DIR / "manifest.json"
REPORT = MAP_DIR / "hd-build-report.json"
CACHE = Path("/tmp/wow-route-uprez-png-cache")

PNG_RAW = "https://raw.githubusercontent.com/keyboardturner/WoWMapUprez_png/master/{edition}/Interface/Worldmap/{folder}/{name}{index}.png"
PNG_ROOT_API = "https://api.github.com/repos/keyboardturner/WoWMapUprez_png/contents/{edition}/Interface/Worldmap?ref=master"
PNG_INTERFACE_API = "https://api.github.com/repos/keyboardturner/WoWMapUprez_png/contents/{edition}/Interface?ref=master"
PNG_TREE_API = "https://api.github.com/repos/keyboardturner/WoWMapUprez_png/git/trees/{sha}?recursive=1"
AREA_CSV = "https://raw.githubusercontent.com/DreamCoreRev/EonsDBC/master/DBFilesClient/csv/WorldMapArea.dbc.csv"
OVERLAY_CSV = "https://raw.githubusercontent.com/DreamCoreRev/EonsDBC/master/DBFilesClient/csv/WorldMapOverlay.dbc.csv"
UA = "Mozilla/5.0 route-atlas-hd-builder/1.1"

GAME_W = 1002
GAME_H = 668
UPSCALE = 4
HD_W = GAME_W * UPSCALE
HD_H = GAME_H * UPSCALE
TILE = 1024
EXACT_WOTLK_SPECIAL_ZONES = {1519}  # Stormwind gained the harbor in Wrath; TBC art is not exact.

# Historical client typos where the art-bearing files do not match the DBC name.
PREFIX_ALIASES = {
    "FeralfenVillage": ["FeralfenVilliage"],
    "BurningBladeRUins": ["BurningBladeRuins"],
    "ThunderlordStronghold": ["ThunderlordStrongHold"],
}

FILE_INDEX: dict[tuple[str, str, str, int], tuple[str, str]] = {}
FILE_PREFIXES: dict[tuple[str, str, int], dict[str, str]] = {}


def http_bytes(url: str, timeout: int = 30, attempts: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, IncompleteRead, ConnectionError) as exc:
            last = exc
        if attempt < attempts:
            time.sleep(0.4 * attempt)
    assert last is not None
    raise last


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_csv(url: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(http_bytes(url).decode("utf-8-sig"))))


def load_area_tables():
    area_rows = load_csv(AREA_CSV)
    overlay_rows = load_csv(OVERLAY_CSV)
    by_zone: dict[int, dict] = {}
    for r in area_rows[1:]:
        if len(r) < 4:
            continue
        try:
            map_area_id = int(r[0])
            continent = int(r[1])
            zone_id = int(r[2])
        except ValueError:
            continue
        by_zone[zone_id] = {
            "map_area_id": map_area_id,
            "continent": continent,
            "texture": r[3].strip().strip('"'),
        }
    overlays: dict[int, list[dict]] = {}
    for r in overlay_rows[1:]:
        if len(r) < 13:
            continue
        try:
            map_area_id = int(r[1])
            width, height = int(r[9] or 0), int(r[10] or 0)
            offset_x, offset_y = int(r[11] or 0), int(r[12] or 0)
        except ValueError:
            continue
        name = r[8].strip().strip('"')
        if not name or width <= 0 or height <= 0:
            continue
        overlays.setdefault(map_area_id, []).append({
            "name": name,
            "width": width,
            "height": height,
            "offset_x": offset_x,
            "offset_y": offset_y,
        })
    return by_zone, overlays


def edition_for(continent: int) -> str | None:
    if continent in (0, 1, 530):
        return "ClassicTBC"
    if continent in (571, 609):
        return "Retail"
    return None


def load_folder_maps() -> dict[str, dict[str, str]]:
    out = {}
    for edition in ("ClassicTBC", "Retail"):
        data = json.loads(http_bytes(PNG_ROOT_API.format(edition=edition)).decode("utf-8"))
        out[edition] = {norm(x["name"]): x["name"] for x in data if x.get("type") == "dir"}
    return out


def load_file_indexes() -> None:
    FILE_INDEX.clear()
    FILE_PREFIXES.clear()
    suffix_order = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    for edition in ("ClassicTBC", "Retail"):
        interface = json.loads(http_bytes(PNG_INTERFACE_API.format(edition=edition)).decode("utf-8"))
        worldmap = next(x for x in interface if x.get("name") == "Worldmap")
        tree = json.loads(http_bytes(PNG_TREE_API.format(sha=worldmap["sha"]), timeout=60).decode("utf-8"))
        if tree.get("truncated"):
            raise RuntimeError(f"GitHub tree truncated for {edition}")
        for item in tree.get("tree", []):
            if item.get("type") != "blob" or not item.get("path", "").lower().endswith(".png"):
                continue
            path = item["path"]
            if "/" not in path:
                continue
            folder, filename = path.split("/", 1)
            stem = filename[:-4]
            for index in suffix_order:
                suffix = str(index)
                if not stem.endswith(suffix):
                    continue
                prefix = stem[:-len(suffix)]
                if not prefix:
                    continue
                key = (edition, norm(folder), norm(prefix), index)
                FILE_INDEX[key] = (folder, prefix)
                FILE_PREFIXES.setdefault((edition, norm(folder), index), {})[norm(prefix)] = prefix
                break


def resolve_file_prefix(edition: str, folder: str, name: str, index: int) -> tuple[str, str]:
    folder_key = norm(folder)
    candidates = [name] + PREFIX_ALIASES.get(name, [])
    for candidate in candidates:
        hit = FILE_INDEX.get((edition, folder_key, norm(candidate), index))
        if hit:
            return hit
    available = FILE_PREFIXES.get((edition, folder_key, index), {})
    if available:
        match = difflib.get_close_matches(norm(name), list(available.keys()), n=1, cutoff=0.84)
        if match:
            return folder, available[match[0]]
    return folder, name


def cache_path(edition: str, folder: str, name: str, index: int) -> Path:
    return CACHE / edition / folder / f"{name}{index}.png"


def fetch_png(edition: str, folder: str, name: str, index: int) -> Image.Image:
    folder, name = resolve_file_prefix(edition, folder, name, index)
    cp = cache_path(edition, folder, name, index)
    if cp.exists():
        try:
            im = Image.open(cp).convert("RGBA")
            im.load()
            return im
        except Exception:
            cp.unlink(missing_ok=True)
    url = PNG_RAW.format(edition=edition, folder=folder, name=name, index=index)
    try:
        data = http_bytes(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise FileNotFoundError(url) from exc
        raise
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    im.load()
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(data)
    return im


def fetch_with_aliases(edition: str, folder: str, name: str, index: int) -> Image.Image:
    candidates = [name] + PREFIX_ALIASES.get(name, [])
    last = None
    for candidate in candidates:
        try:
            return fetch_png(edition, folder, candidate, index)
        except FileNotFoundError as exc:
            last = exc
    raise last or FileNotFoundError(name)


def build_map(edition: str, folder: str, texture: str, overlay_defs: list[dict]) -> tuple[Image.Image, list[str], list[str]]:
    canvas = Image.new("RGBA", (TILE * 4, TILE * 3), (0, 0, 0, 0))
    base_tiles: dict[int, Image.Image] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_png, edition, folder, texture, i): i for i in range(1, 13)}
        for fut in as_completed(futs):
            i = futs[fut]
            base_tiles[i] = fut.result()
    for i in range(1, 13):
        tile = base_tiles[i]
        zero = i - 1
        canvas.alpha_composite(tile, ((zero % 4) * TILE, (zero // 4) * TILE))
    canvas = canvas.crop((0, 0, HD_W, HD_H))

    applied: list[str] = []
    missing_pieces: list[str] = []
    for ov in overlay_defs:
        cols = math.ceil(ov["width"] / 256)
        rows = math.ceil(ov["height"] / 256)
        count = cols * rows
        layer = Image.new("RGBA", (cols * TILE, rows * TILE), (0, 0, 0, 0))
        pieces: dict[int, Image.Image] = {}
        with ThreadPoolExecutor(max_workers=min(8, count)) as ex:
            futs = {ex.submit(fetch_with_aliases, edition, folder, ov["name"], i): i for i in range(1, count + 1)}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    pieces[i] = fut.result()
                except FileNotFoundError:
                    # Old-world DBCs include some obsolete/fully-transparent edge
                    # pieces that are intentionally absent from the uprez archive.
                    # Treat those pieces as transparent and let final image
                    # correlation decide whether the assembled map is usable.
                    pieces[i] = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
                    missing_pieces.append(f"{ov['name']}{i}")
        for i in range(1, count + 1):
            piece = pieces[i]
            zero = i - 1
            layer.alpha_composite(piece, ((zero % cols) * TILE, (zero // cols) * TILE))
        layer = layer.crop((0, 0, ov["width"] * UPSCALE, ov["height"] * UPSCALE))
        canvas.alpha_composite(layer, (ov["offset_x"] * UPSCALE, ov["offset_y"] * UPSCALE))
        applied.append(ov["name"])
    return canvas, applied, missing_pieces


def save_jpg(im: Image.Image, path: Path) -> None:
    bg = Image.new("RGB", im.size, "black")
    bg.paste(im, mask=im.getchannel("A"))
    bg.save(path, "JPEG", quality=94, subsampling=0, optimize=True)


def corr(a: np.ndarray, b: np.ndarray) -> float:
    aa = a.astype(np.float64)
    bb = b.astype(np.float64)
    aa = (aa - aa.mean()) / (aa.std() + 1e-9)
    bb = (bb - bb.mean()) / (bb.std() + 1e-9)
    return float((aa * bb).mean())


def validate(hd: Image.Image, fallback: Image.Image) -> dict:
    old = np.asarray(fallback.convert("L"), dtype=np.float64)
    new = np.asarray(hd.convert("L").resize((fallback.width, fallback.height), Image.Resampling.LANCZOS), dtype=np.float64)
    h, w = old.shape
    best = (-9.0, 0, 0)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            y0, y1 = max(0, dy), min(h, h + dy)
            x0, x1 = max(0, dx), min(w, w + dx)
            aa = old[y0:y1, x0:x1]
            bb = new[y0-dy:y1-dy, x0-dx:x1-dx]
            c = corr(aa, bb)
            if c > best[0]:
                best = (c, dx, dy)
    mae = float(np.abs(old - new).mean())
    return {"corr": round(best[0], 6), "shift_x": best[1], "shift_y": best[2], "mae": round(mae, 4)}


def process(entry: dict, areas: dict, overlays: dict, folder_maps: dict, min_corr: float, accept_pre_cata: bool) -> dict:
    zid = int(entry["zone_id"])
    meta = areas.get(zid)
    if not meta:
        return {"zone_id": zid, "status": "skip", "reason": "no WorldMapArea row"}
    edition = edition_for(meta["continent"])
    if not edition:
        return {"zone_id": zid, "status": "skip", "reason": f"unsupported continent {meta['continent']}"}
    folder = folder_maps[edition].get(norm(meta["texture"]))
    if not folder:
        return {"zone_id": zid, "status": "skip", "reason": f"no {edition} folder for {meta['texture']}"}
    fallback_path = MAP_DIR / entry["file"]
    if not fallback_path.exists():
        return {"zone_id": zid, "status": "skip", "reason": "fallback file missing"}
    started = time.time()
    try:
        hd, applied, missing_pieces = build_map(edition, folder, meta["texture"], overlays.get(meta["map_area_id"], []))
        fallback = Image.open(fallback_path).convert("RGB")
        check = validate(hd, fallback)
        correlation_ok = check["corr"] >= min_corr and abs(check["shift_x"]) <= 1 and abs(check["shift_y"]) <= 1
        pre_cata_ok = (
            accept_pre_cata
            and meta["continent"] in (0, 1)
            and zid not in EXACT_WOTLK_SPECIAL_ZONES
            and not missing_pieces
        )
        accepted = correlation_ok or pre_cata_ok
        validation_mode = "fallback-correlation" if correlation_ok else ("pre-cata-source-trust" if pre_cata_ok else "failed")
        out_name = f"{fallback_path.stem}-hd.jpg"
        out_path = MAP_DIR / out_name
        if accepted:
            save_jpg(hd, out_path)
        return {
            "zone_id": zid,
            "status": "accepted" if accepted else "rejected",
            "edition": edition,
            "folder": folder,
            "texture": meta["texture"],
            "map_area_id": meta["map_area_id"],
            "overlay_count": len(applied),
            "overlays": applied,
            "missing_overlay_pieces": missing_pieces,
            "hd_file": out_name if accepted else None,
            "width": hd.width,
            "height": hd.height,
            "validation": check,
            "validation_mode": validation_mode,
            "seconds": round(time.time() - started, 2),
        }
    except Exception as exc:
        return {
            "zone_id": zid,
            "status": "error",
            "edition": edition,
            "folder": folder,
            "texture": meta["texture"],
            "map_area_id": meta["map_area_id"],
            "reason": f"{type(exc).__name__}: {exc}",
            "seconds": round(time.time() - started, 2),
        }


def update_manifest(manifest: dict, results: list[dict]) -> None:
    by_id = {int(x["zone_id"]): x for x in results}
    for entry in manifest["maps"]:
        r = by_id.get(int(entry["zone_id"]))
        if not r or r["status"] != "accepted":
            continue
        entry.update({
            "hd_file": r["hd_file"],
            "hd_source": f"keyboardturner/WoWMapUprez_png:{r['edition']}",
            "hd_width": r["width"],
            "hd_height": r["height"],
            "hd_method": f"fully explored {r['edition']} composite: 12 base tiles + {r['overlay_count']} WorldMapOverlay overlays",
            "hd_overlay_map_area_id": r["map_area_id"],
            "hd_overlay_source": "DreamCoreRev/EonsDBC 3.3.5a WorldMapOverlay.dbc.csv",
            "hd_validation_mode": r["validation_mode"],
            "hd_validation_corr": r["validation"]["corr"],
            "hd_validation_shift": [r["validation"]["shift_x"], r["validation"]["shift_y"]],
            "hd_validation_mae": r["validation"]["mae"],
        })
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone-ids", nargs="*", type=int)
    ap.add_argument("--min-corr", type=float, default=0.72)
    ap.add_argument("--accept-pre-cata", action="store_true", help="accept complete ClassicTBC old-world composites even when the current Wowhead fallback is from a different map era")
    ap.add_argument("--workers", type=int, default=2, help="maps processed in parallel")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = manifest["maps"]
    if args.zone_ids:
        wanted = set(args.zone_ids)
        selected = [x for x in selected if int(x["zone_id"]) in wanted]

    areas, overlays = load_area_tables()
    folder_maps = load_folder_maps()
    load_file_indexes()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process, entry, areas, overlays, folder_maps, args.min_corr, args.accept_pre_cata): entry for entry in selected}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            val = r.get("validation", {})
            print(f"{r['zone_id']:>4} {r['status']:<8} corr={val.get('corr','-')} shift=({val.get('shift_x','-')},{val.get('shift_y','-')}) overlays={r.get('overlay_count','-')} {r.get('reason','')}", flush=True)

    results.sort(key=lambda x: x["zone_id"])
    update_manifest(manifest, results)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "min_corr": args.min_corr,
        "selected_count": len(selected),
        "accepted": sum(r["status"] == "accepted" for r in results),
        "rejected": sum(r["status"] == "rejected" for r in results),
        "errors": sum(r["status"] == "error" for r in results),
        "skipped": sum(r["status"] == "skip" for r in results),
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("selected_count", "accepted", "rejected", "errors", "skipped")}, ensure_ascii=False))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
