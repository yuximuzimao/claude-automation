from __future__ import annotations

import math
from typing import Iterable, Sequence

Point = Sequence[float]


def _xy(point: Point) -> tuple[float, float]:
    return float(point[0]), float(point[1])


def distance(a: Point, b: Point) -> float:
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return math.hypot(bx - ax, by - ay)


def centroid(points: Sequence[Point]) -> list[float] | None:
    if not points:
        return None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return [sum(xs) / len(xs), sum(ys) / len(ys)]


def bbox(points: Sequence[Point]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return {
        "left": min(xs),
        "top": min(ys),
        "right": max(xs),
        "bottom": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if not 0 <= q <= 1:
        raise ValueError("q must be within [0, 1]")
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def compass_direction(dx: float, dy: float) -> str:
    """Return an 8-way map direction. Questie map Y increases southward."""
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return "原地"
    # Convert screen/map vector into mathematical angle where north is +Y.
    angle = math.degrees(math.atan2(dx, -dy)) % 360
    labels = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    index = int((angle + 22.5) // 45) % 8
    return labels[index]


def axis_direction(dx: float, dy: float) -> str:
    """Return an undirected 4-axis label for a point-cloud principal axis."""
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return "无主轴"
    direction = compass_direction(dx, dy)
    opposites = {
        "北": "南",
        "东北": "西南",
        "东": "西",
        "东南": "西北",
        "南": "北",
        "西南": "东北",
        "西": "东",
        "西北": "东南",
    }
    canonical = {
        frozenset(("北", "南")): "南北",
        frozenset(("东", "西")): "东西",
        frozenset(("东北", "西南")): "东北—西南",
        frozenset(("东南", "西北")): "东南—西北",
    }
    return canonical[frozenset((direction, opposites[direction]))]


def principal_axis(points: Sequence[Point]) -> dict[str, float | str] | None:
    """Analytic PCA for a 2D point cloud, without requiring numpy."""
    if not points:
        return None
    c = centroid(points)
    assert c is not None
    cx, cy = c
    if len(points) == 1:
        return {
            "dx": 0.0,
            "dy": 0.0,
            "lambda_major": 0.0,
            "lambda_minor": 0.0,
            "axis_strength": 0.0,
            "direction": "无主轴",
        }

    xx = yy = xy = 0.0
    for p in points:
        x, y = _xy(p)
        rx = x - cx
        ry = y - cy
        xx += rx * rx
        yy += ry * ry
        xy += rx * ry
    n = float(len(points))
    xx /= n
    yy /= n
    xy /= n

    trace = xx + yy
    disc = math.sqrt(max(0.0, (xx - yy) ** 2 + 4 * xy * xy))
    major = (trace + disc) / 2
    minor = (trace - disc) / 2

    if major <= 1e-15:
        vx, vy = 0.0, 0.0
    elif abs(xy) > 1e-15:
        vx, vy = major - yy, xy
        norm = math.hypot(vx, vy)
        vx, vy = vx / norm, vy / norm
    elif xx >= yy:
        vx, vy = 1.0, 0.0
    else:
        vx, vy = 0.0, 1.0

    strength = 0.0 if major <= 1e-15 else max(0.0, min(1.0, 1.0 - minor / major))
    return {
        "dx": vx,
        "dy": vy,
        "lambda_major": major,
        "lambda_minor": minor,
        "axis_strength": strength,
        "direction": axis_direction(vx, vy),
    }


def nearest_point(origin_points: Sequence[Point], target_points: Sequence[Point]) -> dict[str, object] | None:
    if not origin_points or not target_points:
        return None
    best: tuple[float, Point, Point] | None = None
    for origin in origin_points:
        for target in target_points:
            d = distance(origin, target)
            if best is None or d < best[0]:
                best = (d, origin, target)
    assert best is not None
    d, origin, target = best
    ox, oy = _xy(origin)
    tx, ty = _xy(target)
    return {
        "distance": d,
        "origin": [ox, oy],
        "target": [tx, ty],
        "direction": compass_direction(tx - ox, ty - oy),
    }


def directed_nearest_distances(source: Sequence[Point], target: Sequence[Point]) -> list[float]:
    if not source or not target:
        return []
    return [min(distance(point, other) for other in target) for point in source]


def bbox_iou(a_points: Sequence[Point], b_points: Sequence[Point]) -> float | None:
    a = bbox(a_points)
    b = bbox(b_points)
    if a is None or b is None:
        return None
    left = max(a["left"], b["left"])
    top = max(a["top"], b["top"])
    right = min(a["right"], b["right"])
    bottom = min(a["bottom"], b["bottom"])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    a_area = a["width"] * a["height"]
    b_area = b["width"] * b["height"]
    union = a_area + b_area - intersection
    if union <= 1e-15:
        return 1.0 if a["left"] == b["left"] and a["top"] == b["top"] else 0.0
    return intersection / union


def cloud_summary(points: Sequence[Point]) -> dict[str, object] | None:
    if not points:
        return None
    c = centroid(points)
    assert c is not None
    radii = [distance(c, p) for p in points]
    return {
        "point_count": len(points),
        "centroid": c,
        "bbox": bbox(points),
        "radius_p50": percentile(radii, 0.50),
        "radius_p90": percentile(radii, 0.90),
        "principal_axis": principal_axis(points),
    }


def pair_metrics(a_points: Sequence[Point], b_points: Sequence[Point]) -> dict[str, object] | None:
    if not a_points or not b_points:
        return None
    a_center = centroid(a_points)
    b_center = centroid(b_points)
    assert a_center is not None and b_center is not None
    a_to_b = directed_nearest_distances(a_points, b_points)
    b_to_a = directed_nearest_distances(b_points, a_points)
    min_d = min(min(a_to_b), min(b_to_a))
    a50 = percentile(a_to_b, 0.50)
    b50 = percentile(b_to_a, 0.50)
    a90 = percentile(a_to_b, 0.90)
    b90 = percentile(b_to_a, 0.90)
    assert a50 is not None and b50 is not None and a90 is not None and b90 is not None
    return {
        "centroid_distance": distance(a_center, b_center),
        "minimum_point_distance": min_d,
        "a_to_b_nn_p50": a50,
        "b_to_a_nn_p50": b50,
        "symmetric_nn_p50": (a50 + b50) / 2,
        "a_to_b_nn_p90": a90,
        "b_to_a_nn_p90": b90,
        "symmetric_nn_p90": (a90 + b90) / 2,
        "bbox_iou": bbox_iou(a_points, b_points),
    }
