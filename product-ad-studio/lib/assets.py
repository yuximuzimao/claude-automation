from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


CATALOG_VERSION = 1
ROLE_DIRECTORIES = {
    "product_source": "products",
    "product_set": "products",
    "brand_logo": "logos",
    "demo_layout": "demos",
    "style_reference": "references",
    "designer_output": "cases",
    "edit_target": "working",
    "generated_draft": "working",
}


@dataclass(frozen=True)
class ImageFingerprint:
    sha256: str
    dhash: str
    width: int
    height: int
    mode: str
    has_alpha: bool
    alpha_bbox: tuple[int, int, int, int] | None
    byte_size: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "dhash": self.dhash,
            "width": self.width,
            "height": self.height,
            "mode": self.mode,
            "has_alpha": self.has_alpha,
            "alpha_bbox": list(self.alpha_bbox) if self.alpha_bbox else None,
            "byte_size": self.byte_size,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dhash(image: Image.Image, hash_size: int = 16) -> str:
    rgba = image.convert("RGBA")
    backdrop = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    backdrop.alpha_composite(rgba)
    gray = backdrop.convert("L").resize((hash_size + 1, hash_size))
    pixels = list(gray.get_flattened_data())
    value = 0
    for y in range(hash_size):
        offset = y * (hash_size + 1)
        for x in range(hash_size):
            value = (value << 1) | int(pixels[offset + x] > pixels[offset + x + 1])
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("dHash lengths do not match")
    return (int(left, 16) ^ int(right, 16)).bit_count()


def fingerprint_image(path: Path) -> ImageFingerprint:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    with Image.open(path) as image:
        has_alpha = "A" in image.getbands()
        alpha_bbox = image.getchannel("A").getbbox() if has_alpha else None
        return ImageFingerprint(
            sha256=hashlib.sha256(raw).hexdigest(),
            dhash=_dhash(image),
            width=image.width,
            height=image.height,
            mode=image.mode,
            has_alpha=has_alpha,
            alpha_bbox=alpha_bbox,
            byte_size=len(raw),
        )


def read_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": CATALOG_VERSION, "brand": path.parent.name, "assets": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("assets"), list):
        raise ValueError(f"Invalid catalog: {path}")
    return data


def save_catalog(path: Path, catalog: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_exact(catalog: dict[str, Any], sha256: str) -> dict[str, Any] | None:
    return next((item for item in catalog["assets"] if item["fingerprint"]["sha256"] == sha256), None)


def _find_asset_id(catalog: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    return next((item for item in catalog["assets"] if item["asset_id"] == asset_id), None)


def _possible_duplicates(catalog: dict[str, Any], fp: ImageFingerprint, threshold: int = 10) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    ratio = fp.width / fp.height
    for item in catalog["assets"]:
        other = item["fingerprint"]
        other_ratio = other["width"] / other["height"]
        if abs(ratio - other_ratio) > 0.03:
            continue
        distance = hamming_distance(fp.dhash, other["dhash"])
        if distance <= threshold:
            matches.append({"asset_id": item["asset_id"], "dhash_distance": distance})
    return sorted(matches, key=lambda item: item["dhash_distance"])


def import_asset(
    *,
    source: Path,
    brand_dir: Path,
    asset_id: str,
    role: str,
    description: str,
    tags: Iterable[str] = (),
    aliases: Iterable[str] = (),
    protection: dict[str, Any] | None = None,
    move: bool = False,
) -> tuple[dict[str, Any], bool]:
    if role not in ROLE_DIRECTORIES:
        raise ValueError(f"Unsupported role: {role}")
    source = source.expanduser().resolve()
    catalog_path = brand_dir / "asset-catalog.json"
    catalog = read_catalog(catalog_path)
    fingerprint = fingerprint_image(source)

    duplicate = _find_exact(catalog, fingerprint.sha256)
    source_alias = {
        "original_name": source.name,
        "source_path": str(source),
        "seen_at": utc_now(),
    }
    if duplicate:
        duplicate.setdefault("source_aliases", [])
        if source_alias not in duplicate["source_aliases"]:
            duplicate["source_aliases"].append(source_alias)
        duplicate["aliases"] = sorted(set(duplicate.get("aliases", [])) | set(aliases))
        duplicate["tags"] = sorted(set(duplicate.get("tags", [])) | set(tags))
        duplicate["updated_at"] = utc_now()
        save_catalog(catalog_path, catalog)
        if move:
            source.unlink()
        return duplicate, False

    conflict = _find_asset_id(catalog, asset_id)
    if conflict:
        raise ValueError(f"asset_id already exists with different content: {asset_id}")

    extension = source.suffix.lower() or ".png"
    destination_dir = brand_dir / "assets" / ROLE_DIRECTORIES[role]
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{asset_id}{extension}"
    if destination.exists():
        raise FileExistsError(destination)

    if move:
        shutil.move(str(source), destination)
    else:
        shutil.copy2(source, destination)

    entry = {
        "asset_id": asset_id,
        "role": role,
        "brand": brand_dir.name,
        "path": destination.relative_to(brand_dir.parent.parent.parent).as_posix(),
        "description": description,
        "tags": sorted(set(tags)),
        "aliases": sorted(set(aliases)),
        "protection": protection or {},
        "fingerprint": fingerprint.as_dict(),
        "possible_duplicates": _possible_duplicates(catalog, fingerprint),
        "source_aliases": [source_alias],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    catalog["brand"] = brand_dir.name
    catalog["assets"].append(entry)
    catalog["assets"].sort(key=lambda item: item["asset_id"])
    save_catalog(catalog_path, catalog)
    return entry, True


def verify_catalog(brand_dir: Path) -> list[str]:
    catalog = read_catalog(brand_dir / "asset-catalog.json")
    project_root = brand_dir.parent.parent.parent
    errors: list[str] = []
    seen_sha: dict[str, str] = {}
    for item in catalog["assets"]:
        path = project_root / item["path"]
        if not path.exists():
            errors.append(f"missing file: {item['asset_id']} -> {path}")
            continue
        actual = fingerprint_image(path)
        expected = item["fingerprint"]
        if actual.sha256 != expected["sha256"]:
            errors.append(f"checksum mismatch: {item['asset_id']}")
        previous = seen_sha.get(actual.sha256)
        if previous:
            errors.append(f"duplicate binary in catalog: {previous}, {item['asset_id']}")
        else:
            seen_sha[actual.sha256] = item["asset_id"]
    return errors
