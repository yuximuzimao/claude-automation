#!/usr/bin/env python3
"""Read-only multi-target locator for 4-plot "可摘" markers.

Uses multiple compact templates and non-maximum suppression. It never clicks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter

from anchor_locator import load_gray, normalized_cross_correlation, scaled

ROOT = Path(__file__).resolve().parents[1]


def candidates(image, template, roi, scales, threshold, template_name):
    x0, y0, w, h = roi
    search = image[y0:y0+h, x0:x0+w]
    out = []
    for scale in scales:
        t = scaled(template, scale)
        scores = normalized_cross_correlation(search, t)
        if scores is None:
            continue
        mx = maximum_filter(scores, size=max(21, int(min(t.shape) * 0.8)))
        ys, xs = np.where((scores == mx) & (scores >= threshold))
        for y, x in zip(ys, xs):
            out.append({
                "score": float(scores[y, x]),
                "center_x": float(x0 + x + t.shape[1] / 2),
                "center_y": float(y0 + y + t.shape[0] / 2),
                "scale": scale,
                "template": template_name,
            })
    return out


def dedupe(items, radius=30.0):
    kept = []
    for item in sorted(items, key=lambda z: z["score"], reverse=True):
        if all(
            (item["center_x"] - k["center_x"]) ** 2
            + (item["center_y"] - k["center_y"]) ** 2
            > radius ** 2
            for k in kept
        ):
            kept.append(item)
    return kept


def locate_pickables(image, roi_normalized=(0.12, 0.42, 0.76, 0.34), threshold=0.70, scales=None):
    if scales is None:
        scales = [0.9, 0.95, 1.0, 1.05, 1.1]
    h, w = image.shape
    rx, ry, rw, rh = roi_normalized
    roi = (
        int(round(rx*w)), int(round(ry*h)),
        int(round(rw*w)), int(round(rh*h)),
    )
    templates = [
        ("pickable-qq", ROOT / "assets/ui/pickable-qq.png"),
        ("pickable-wechat", ROOT / "assets/ui/pickable-wechat.png"),
        ("pickable-wechat2", ROOT / "assets/ui/pickable-wechat2.png"),
    ]
    items = []
    for name, path in templates:
        items.extend(candidates(
            image, load_gray(str(path)), roi, scales, threshold, name
        ))
    result = dedupe(items)
    return {"count": len(result), "items": result, "roi": roi}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot")
    ap.add_argument("--roi", default="0.12,0.42,0.76,0.34",
                    help="normalized x,y,w,h")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--scales", default="0.9,0.95,1,1.05,1.1")
    args = ap.parse_args()

    image = load_gray(args.screenshot)
    result = locate_pickables(
        image,
        tuple(map(float, args.roi.split(","))),
        args.threshold,
        [float(v) for v in args.scales.split(",")],
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
