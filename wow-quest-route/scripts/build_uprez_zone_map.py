#!/usr/bin/env python3
"""Build a fully explored high-resolution WoW route-map base from WoWMapUprezTBC.

Old WoW world maps are not just twelve base tiles. The base `Zone1..12.blp`
textures represent the unexplored map; discovered subzones are separate overlay
textures positioned by WorldMapOverlay.dbc. A correct fully explored map must
composite both layers.

For Zangarmarsh, WoWMapUprezTBC provides 4x-upscaled BLP art and the 3.3.5a
WorldMapOverlay table supplies the original 1002x668 overlay dimensions and
pixel offsets. The resulting canvas is therefore 4008x2672 and stays on the
same 0-100 coordinate frame used by Route Atlas.

Example:
    python scripts/build_uprez_zone_map.py \
      --zone Zangarmarsh \
      --map-area-id 467 \
      --output data/routes/maps/3521-zangarmarsh-hd.jpg
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

REPO_RAW = (
    "https://raw.githubusercontent.com/keyboardturner/"
    "WoWMapUprezTBC/main/Interface/Worldmap/{zone}/{name}{index}.blp"
)
OVERLAY_CSV = (
    "https://raw.githubusercontent.com/DreamCoreRev/EonsDBC/master/"
    "DBFilesClient/csv/WorldMapOverlay.dbc.csv"
)
USER_AGENT = "Mozilla/5.0 route-atlas-uprez/2.0"
BASE_COLUMNS = 4
BASE_ROWS = 3
BASE_TILE_COUNT = BASE_COLUMNS * BASE_ROWS
GAME_MAP_WIDTH = 1002
GAME_MAP_HEIGHT = 668
UPSCALE = 4
SOURCE_TILE = 256
HD_TILE = SOURCE_TILE * UPSCALE

# The TBC source contains a historical misspelling for this overlay. The
# correctly spelled files 2-4 are transparent placeholders, while the typo
# variant contains the actual art matching WorldMapOverlay.dbc.
OVERLAY_ALIASES = {
    "FeralfenVillage": "FeralfenVilliage",
    # WorldMapOverlay.dbc uses an odd capital-U spelling; the TBC uprez
    # repository stores the Nagrand overlay with the normal Ruins casing.
    "BurningBladeRUins": "BurningBladeRuins",
}


class RemoteAssetError(RuntimeError):
    pass


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RemoteAssetError(f"failed to download {url}: {exc}") from exc


def fetch_blp(zone: str, name: str, index: int) -> Image.Image:
    url = REPO_RAW.format(zone=zone, name=name, index=index)
    data = _get(url)
    try:
        image = Image.open(io.BytesIO(data)).convert("RGBA")
        image.load()
    except Exception as exc:  # Pillow raises format-specific subclasses here.
        raise RuntimeError(f"failed to decode {name}{index}.blp: {exc}") from exc
    if image.width > HD_TILE or image.height > HD_TILE:
        raise RuntimeError(f"unexpected oversized tile for {name}{index}: {image.size}")
    return image


def build_base(zone: str) -> Image.Image:
    tiles = [fetch_blp(zone, zone, index) for index in range(1, BASE_TILE_COUNT + 1)]
    canvas = Image.new("RGBA", (HD_TILE * BASE_COLUMNS, HD_TILE * BASE_ROWS), (0, 0, 0, 0))
    for zero_index, tile in enumerate(tiles):
        x = (zero_index % BASE_COLUMNS) * HD_TILE
        y = (zero_index // BASE_COLUMNS) * HD_TILE
        canvas.alpha_composite(tile, (x, y))
    return canvas.crop((0, 0, GAME_MAP_WIDTH * UPSCALE, GAME_MAP_HEIGHT * UPSCALE))


def load_overlay_rows(map_area_id: int) -> list[dict[str, int | str]]:
    text = _get(OVERLAY_CSV).decode("utf-8-sig")
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 13 or row[1] != str(map_area_id):
            continue
        texture_name = row[8].strip().strip('"')
        width = int(row[9] or 0)
        height = int(row[10] or 0)
        if not texture_name or width <= 0 or height <= 0:
            continue
        rows.append(
            {
                "texture_name": texture_name,
                "width": width,
                "height": height,
                "offset_x": int(row[11] or 0),
                "offset_y": int(row[12] or 0),
            }
        )
    if not rows:
        raise RuntimeError(f"no WorldMapOverlay rows found for MapAreaID {map_area_id}")
    return rows


def build_overlay(zone: str, texture_name: str, width: int, height: int) -> Image.Image:
    source_name = OVERLAY_ALIASES.get(texture_name, texture_name)
    cols = math.ceil(width / SOURCE_TILE)
    rows = math.ceil(height / SOURCE_TILE)
    piece_count = cols * rows
    canvas = Image.new("RGBA", (cols * HD_TILE, rows * HD_TILE), (0, 0, 0, 0))
    for zero_index in range(piece_count):
        tile = fetch_blp(zone, source_name, zero_index + 1)
        x = (zero_index % cols) * HD_TILE
        y = (zero_index // cols) * HD_TILE
        canvas.alpha_composite(tile, (x, y))
    return canvas.crop((0, 0, width * UPSCALE, height * UPSCALE))


def composite_fully_explored(zone: str, map_area_id: int) -> tuple[Image.Image, list[str]]:
    canvas = build_base(zone)
    applied: list[str] = []
    for row in load_overlay_rows(map_area_id):
        name = str(row["texture_name"])
        width = int(row["width"])
        height = int(row["height"])
        overlay = build_overlay(zone, name, width, height)
        x = int(row["offset_x"]) * UPSCALE
        y = int(row["offset_y"]) * UPSCALE
        canvas.alpha_composite(overlay, (x, y))
        applied.append(name)
    return canvas, applied


def save(image: Image.Image, output: Path, quality: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        background = Image.new("RGB", image.size, "black")
        background.paste(image, mask=image.getchannel("A"))
        background.save(output, "JPEG", quality=quality, subsampling=0, optimize=True)
    elif suffix == ".png":
        image.save(output, "PNG", optimize=True)
    else:
        raise RuntimeError("output must end in .jpg, .jpeg, or .png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", required=True, help="WoWMapUprezTBC folder/tile prefix, e.g. Zangarmarsh")
    parser.add_argument("--map-area-id", required=True, type=int, help="3.3.5a WorldMapArea/WorldMapOverlay MapAreaID")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--quality", type=int, default=94)
    args = parser.parse_args()

    image, overlays = composite_fully_explored(args.zone, args.map_area_id)
    save(image, args.output, args.quality)
    print(
        f"built fully explored {args.zone}: {image.width}x{image.height}; "
        f"overlays={len(overlays)} ({', '.join(overlays)}) -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
