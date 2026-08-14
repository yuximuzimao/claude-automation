from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MapBounds:
    """Pixel rectangle corresponding to Questie's zone-local 0..100 coordinate space."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def validate(self) -> None:
        if self.width <= 0:
            raise ValueError("map bounds must have right > left")
        if self.height <= 0:
            raise ValueError("map bounds must have bottom > top")


@dataclass(frozen=True)
class PixelPoint:
    x: float
    y: float


def project_questie_point(x: float, y: float, bounds: MapBounds) -> PixelPoint:
    """Project one Questie zone coordinate (0..100) into a base-map pixel rectangle.

    Questie NPC/object spawn coordinates are local percentages of the zone map. The
    function deliberately does not clamp out-of-range values: bad or sentinel data
    should remain visible to callers instead of being silently moved onto the map edge.
    """

    bounds.validate()
    return PixelPoint(
        x=bounds.left + (x / 100.0) * bounds.width,
        y=bounds.top + (y / 100.0) * bounds.height,
    )


def full_image_bounds(width: float, height: float) -> MapBounds:
    """Return bounds for an uncropped image whose full frame is the zone coordinate space."""

    if width <= 0 or height <= 0:
        raise ValueError("image width and height must be positive")
    return MapBounds(left=0.0, top=0.0, right=width, bottom=height)
