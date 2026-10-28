#!/usr/bin/env python3
"""Read-only locator for known seed icons in the in-field seed picker.

It never clicks. Targets are matched by their catalog icon, so picker slots may
shift when inventory reaches zero without breaking the lookup.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from anchor_locator import load_gray, normalized_cross_correlation, scaled

ROOT = Path(__file__).resolve().parents[1]


def best_match(image, template_base, roi, scales):
    x0, y0, w, h = roi
    search = image[y0:y0+h, x0:x0+w]
    best = None
    for scale in scales:
        template = scaled(template_base, scale)
        scores = normalized_cross_correlation(search, template)
        if scores is None:
            continue
        local_y, local_x = np.unravel_index(np.argmax(scores), scores.shape)
        score = float(scores[local_y, local_x])
        candidate = {
            "score": score,
            "x": int(x0 + local_x),
            "y": int(y0 + local_y),
            "w": int(template.shape[1]),
            "h": int(template.shape[0]),
            "center_x": int(x0 + local_x + template.shape[1] / 2),
            "center_y": int(y0 + local_y + template.shape[0] / 2),
            "scale": scale,
        }
        if best is None or score > best["score"]:
            best = candidate
    return best


def normalized_roi(width, height, spec=(0.02, 0.52, 0.96, 0.34)):
    x, y, w, h = spec
    return (
        int(round(x * width)),
        int(round(y * height)),
        int(round(w * width)),
        int(round(h * height)),
    )


def load_catalog():
    data = json.loads((ROOT / "data/seed-catalog.json").read_text())
    return {seed["name"]: seed for seed in data["seeds"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot", help="cropped farm-window screenshot with picker open")
    ap.add_argument("--platform", choices=["qq", "wechat"], required=True)
    ap.add_argument("--target", action="append", required=True,
                    help="seed name; repeat to provide a priority list")
    ap.add_argument("--threshold", type=float, default=0.58)
    args = ap.parse_args()

    image = load_gray(args.screenshot)
    height, width = image.shape
    roi = normalized_roi(width, height)
    catalog = load_catalog()
    scales = [0.9, 0.95, 1.0, 1.05, 1.1]

    results = []
    for priority, name in enumerate(args.target):
        seed = catalog.get(name)
        if seed is None:
            results.append({
                "name": name,
                "priority": priority,
                "error": "unknown_seed",
                "matched": False,
            })
            continue
        template = load_gray(str(ROOT / seed["image"]))
        match = best_match(image, template, roi, scales)
        if match is None:
            results.append({
                "name": name,
                "priority": priority,
                "matched": False,
                "score": -1.0,
            })
            continue
        match.update({
            "name": name,
            "priority": priority,
            "matched": match["score"] >= args.threshold,
            "threshold": args.threshold,
            "catalog_image": seed["image"],
            "latest_known_quantity": (
                seed.get("observations", {})
                    .get(args.platform, {})
                    .get("quantity_latest_known")
            ),
        })
        results.append(match)

    chosen = next((x for x in results if x.get("matched")), None)
    print(json.dumps({
        "platform": args.platform,
        "image_size": [width, height],
        "roi": roi,
        "chosen": chosen,
        "results": results,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
