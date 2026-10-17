from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

from solver import Cell, CellKind

ROWS = 18
COLS = 18

# 16x20 normalized glyph masks sampled from the user's fixed-size game UI.
_DIGIT_PATTERNS = {
    1: [
        "........########","........########","....############","################",
        "########..######","####......######","####......######","..........######",
        "..........######","..........######","..........######","..........######",
        "..........######","..........######","..........######","..........######",
        "..........######","..........######","..........######","..........######",
    ],
    2: [
        ".......###......",".......###......","...#########....","..############..",
        "..####....#####.","..##.......####.","...........####.","...........####.",
        "...........####.","..........#####.","..........####..","........####....",
        ".......#####....","......#####.....","......#####.....","....######......",
        "...#####........","..#####.........","################","################",
    ],
    3: [
        "......####......","......####......","...#########....","..############..",
        "..####....#####.","..##.......####.","...........####.","..........#####.",
        ".......#######..","......######....","......########..","......########..",
        "..........#####.","...........####.","...........#####","..##.......####.",
        "######....#####.","..#############.","...###########..","......#####.....",
    ],
    4: [
        "........####....","........####....",".......#####....",".......###......",
        ".....#####......",".....####.......","....#####.......","....####........",
        "...#####.####...","...####..####...","..#####..####...","..#####..####...",
        "#####....####...","###############.","################","################",
        ".........####...",".........####...",".........####...","..........###...",
    ],
    5: [
        "...###########..","..#############.","..#############.",".##############.",
        ".#####..........",".#####..........","######..........","##########......",
        "#############...","##############..","###############.","######...#######",
        "...........#####","...........#####","...........#####",".###.......#####",
        "######...#######","###############.",".#############..","...#########....",
    ],
    6: [
        "........####....","........####....",".......#####....",".......####.....",
        "......#####.....","....######......","....####........","...#######......",
        "...###########..","..#############.","..##############","..##############",
        "######.....#####","######.....#####","######.....#####","######.....#####",
        "..#####...######","..#############.","...###########..","......######....",
    ],
}

_DIGIT_MASKS = {
    n: np.array([[ch == "#" for ch in row] for row in rows], dtype=np.uint8)
    for n, rows in _DIGIT_PATTERNS.items()
}


@dataclass(frozen=True)
class Recognition:
    board: list[list[Cell]]
    confidence: float
    unknown_cells: tuple[tuple[int, int], ...]


def _core(tile: np.ndarray) -> np.ndarray:
    h, w = tile.shape[:2]
    pad_y = max(2, h // 8)
    pad_x = max(2, w // 8)
    return tile[pad_y : h - pad_y, pad_x : w - pad_x]


def _colored_mask(tile_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2HSV)
    # Digits/markers are saturated and bright compared with opened brown cells.
    mask = (hsv[:, :, 1] > 95) & (hsv[:, :, 2] > 120)

    # Ignore the decorative/grid border. This is especially important for yellow
    # clues because the board border itself is also gold and otherwise becomes
    # part of the glyph mask.
    h, w = mask.shape
    pad_y = max(2, h // 8)
    pad_x = max(2, w // 8)
    mask[:pad_y, :] = False
    mask[h - pad_y :, :] = False
    mask[:, :pad_x] = False
    mask[:, w - pad_x :] = False
    return hsv, mask


def _normalize_glyph(mask: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(mask)
    if len(xs) < 20:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    crop = mask[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8)
    if crop.shape[0] < 5 or crop.shape[1] < 2:
        return None
    return cv2.resize(crop, (16, 20), interpolation=cv2.INTER_NEAREST)


def _digit_distance(a: np.ndarray, b: np.ndarray) -> float:
    # Symmetric binary disagreement; tolerant to slight anti-aliasing changes.
    return float(np.mean(a != b))


def _classify_digit(mask: np.ndarray) -> tuple[int | None, float]:
    norm = _normalize_glyph(mask)
    if norm is None:
        return None, 0.0
    scored = sorted((_digit_distance(norm, tmpl), n) for n, tmpl in _DIGIT_MASKS.items())
    dist, number = scored[0]
    confidence = max(0.0, 1.0 - dist / 0.45)
    return number, confidence


def _is_revealed_kbao(tile_bgr: np.ndarray) -> bool:
    core = _core(tile_bgr)
    hsv = cv2.cvtColor(core, cv2.COLOR_BGR2HSV)
    # Revealed K宝 cells have a pale bright background plus several saturated hues.
    bright_ratio = float(np.mean(hsv[:, :, 2] > 180))
    low_sat_bright = float(np.mean((hsv[:, :, 1] < 110) & (hsv[:, :, 2] > 180)))
    varied = hsv[(hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 150), 0]
    hue_span = float(np.ptp(varied)) if varied.size else 0.0
    return bright_ratio > 0.55 and low_sat_bright > 0.20 and hue_span > 35


def classify_tile(tile_bgr: np.ndarray) -> tuple[Cell, float]:
    core = _core(tile_bgr)
    hsv_core = cv2.cvtColor(core, cv2.COLOR_BGR2HSV)
    median_v = float(np.median(hsv_core[:, :, 2]))

    if _is_revealed_kbao(tile_bgr):
        return Cell(CellKind.REVEALED_KBAO), 0.96

    hsv, color_mask = _colored_mask(tile_bgr)
    h = hsv[:, :, 0]
    v = hsv[:, :, 2]

    red = color_mask & ((h <= 7) | (h >= 175))
    blue = color_mask & (h >= 88) & (h <= 115)
    yellow = color_mask & (h >= 14) & (h <= 25)

    red_count = int(red.sum())
    blue_count = int(blue.sum())
    yellow_count = int(yellow.sum())

    # Covered tiles are much brighter than opened brown tiles at this fixed size.
    covered_like = median_v > 135

    if covered_like:
        # A user/app right-click marker is a red glyph on a covered tile.
        # We intentionally only accept narrow exclamation-like marks. A wider '?'
        # is left unknown so the app never treats an uncertain marker as a bomb.
        if red_count >= 30:
            ys, xs = np.where(red)
            if len(xs):
                width = int(xs.max() - xs.min() + 1)
                height = int(ys.max() - ys.min() + 1)
                if height >= 12 and width <= max(10, int(height * 0.58)):
                    return Cell(CellKind.FLAG_BOMB), 0.95
                return Cell(CellKind.COVERED), 0.55
        return Cell(CellKind.COVERED), 0.98

    # Open cell: determine clue family from hue, then recognize digit shape.
    groups = [
        (red_count, CellKind.CLUE_BOMB, red),
        (blue_count, CellKind.CLUE_KBAO, blue),
        (yellow_count, CellKind.CLUE_TOTAL, yellow),
    ]
    groups.sort(key=lambda x: x[0], reverse=True)
    count, kind, mask = groups[0]
    if count < 24:
        return Cell(CellKind.OPEN_EMPTY), 0.98

    digit, digit_conf = _classify_digit(mask)
    if digit is None or digit_conf < 0.45:
        # Never guess a number. A single wrong clue can poison the whole board,
        # so force the caller into the low-confidence/stop path instead.
        return Cell(CellKind.OPEN_EMPTY), 0.20
    return Cell(kind, digit), min(0.98, 0.72 + 0.28 * digit_conf)


def split_board(board_bgr: np.ndarray) -> Iterable[tuple[int, int, np.ndarray]]:
    h, w = board_bgr.shape[:2]
    if h < ROWS or w < COLS:
        raise ValueError("board image is too small")
    for r in range(ROWS):
        y0 = round(r * h / ROWS)
        y1 = round((r + 1) * h / ROWS)
        for c in range(COLS):
            x0 = round(c * w / COLS)
            x1 = round((c + 1) * w / COLS)
            yield r, c, board_bgr[y0:y1, x0:x1]


def recognize_board(board_bgr: np.ndarray) -> Recognition:
    board = [[Cell(CellKind.COVERED) for _ in range(COLS)] for _ in range(ROWS)]
    confidences: list[float] = []
    unknown: list[tuple[int, int]] = []

    for r, c, tile in split_board(board_bgr):
        cell, conf = classify_tile(tile)
        board[r][c] = cell
        confidences.append(conf)
        if conf < 0.50:
            unknown.append((r, c))

    return Recognition(
        board=board,
        confidence=float(np.mean(confidences)) if confidences else 0.0,
        unknown_cells=tuple(unknown),
    )
