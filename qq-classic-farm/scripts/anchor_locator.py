#!/usr/bin/env python3
"""Locate a stable UI image anchor inside a screenshot.

This tool never clicks. It only returns the best match coordinates and confidence.
The caller must decide whether the confidence is high enough before any CGEvent action.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
from PIL import Image
from scipy import ndimage, signal


def load_gray(path: str) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L"), dtype=np.float32)


def scaled(image: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 1e-9:
        return image
    return ndimage.zoom(image, scale, order=1)


def normalized_cross_correlation(
    image: np.ndarray, template: np.ndarray
) -> np.ndarray | None:
    h, w = template.shape
    if h >= image.shape[0] or w >= image.shape[1]:
        return None

    centered = template - template.mean()
    template_norm = np.sqrt(np.sum(centered * centered))
    if template_norm < 1e-6:
        return None

    numerator = signal.fftconvolve(image, centered[::-1, ::-1], mode="valid")

    kernel = np.ones((h, w), dtype=np.float32)
    sum_1 = signal.fftconvolve(image, kernel, mode="valid")
    sum_2 = signal.fftconvolve(image * image, kernel, mode="valid")
    n = float(h * w)
    variance = np.maximum(sum_2 - (sum_1 * sum_1) / n, 0.0)
    denominator = np.sqrt(variance) * template_norm

    return np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, -1.0),
        where=denominator > 1e-6,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("screenshot")
    parser.add_argument("template")
    parser.add_argument("--roi", help="x,y,w,h in screenshot pixel coordinates")
    parser.add_argument(
        "--logical-frame",
        help="logical x,y,w,h corresponding exactly to --roi; emits logical click coordinates",
    )
    parser.add_argument("--scales", default="0.90,0.95,1.00,1.05,1.10")
    parser.add_argument("--threshold", type=float, default=0.82)
    args = parser.parse_args()

    screenshot = load_gray(args.screenshot)
    origin_x = origin_y = 0
    if args.roi:
        x, y, w, h = map(int, args.roi.split(","))
        origin_x, origin_y = x, y
        screenshot = screenshot[y : y + h, x : x + w]

    template_base = load_gray(args.template)
    best = None

    for scale in (float(v) for v in args.scales.split(",")):
        template = scaled(template_base, scale)
        scores = normalized_cross_correlation(screenshot, template)
        if scores is None:
            continue

        local_y, local_x = np.unravel_index(np.argmax(scores), scores.shape)
        score = float(scores[local_y, local_x])
        candidate = {
            "score": score,
            "x": int(origin_x + local_x),
            "y": int(origin_y + local_y),
            "w": int(template.shape[1]),
            "h": int(template.shape[0]),
            "center_x": int(origin_x + local_x + template.shape[1] / 2),
            "center_y": int(origin_y + local_y + template.shape[0] / 2),
            "scale": scale,
        }
        if best is None or score > best["score"]:
            best = candidate

    if best is None:
        raise SystemExit("no valid match scale")

    if args.logical_frame:
        if not args.roi:
            raise SystemExit("--logical-frame requires --roi")
        rx, ry, rw, rh = map(float, args.roi.split(","))
        lx, ly, lw, lh = map(float, args.logical_frame.split(","))
        rel_x = (best["center_x"] - rx) / rw
        rel_y = (best["center_y"] - ry) / rh
        best["logical_center_x"] = lx + rel_x * lw
        best["logical_center_y"] = ly + rel_y * lh

    best["matched"] = best["score"] >= args.threshold
    print(json.dumps(best, ensure_ascii=False))
    return 0 if best["matched"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
