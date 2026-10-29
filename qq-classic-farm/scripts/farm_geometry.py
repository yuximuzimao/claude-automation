"""M1 pure window-local geometry. All input/output points are logical, never screenshot pixels."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


class GeometryStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WindowFrame:
    owner: str
    title: str
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        if (not self.owner or not self.title
            or not all(isfinite(v) for v in (self.x, self.y, self.width, self.height))
            or self.width <= 0 or self.height <= 0):
            raise GeometryStop("INVALID_WINDOW", "Invalid window metadata/bounds")

    def screen_point(self, local_x: float, local_y: float) -> tuple[float, float]:
        if (not all(isfinite(v) for v in (local_x, local_y))
            or not 0 <= local_x < self.width
            or not 0 <= local_y < self.height):
            raise GeometryStop("CLICK_OUTSIDE_WINDOW", "Window-local point is outside target")
        return self.x + local_x, self.y + local_y

    def pixel_to_local(
        self, pixel_x: float, pixel_y: float, image_width: int, image_height: int
    ) -> tuple[float, float]:
        """Screenshot must be an exact crop of this game canvas; reject mismatched geometry."""
        if (type(image_width) is not int or type(image_height) is not int
            or image_width <= 0 or image_height <= 0):
            raise GeometryStop("INVALID_SCREENSHOT", "Invalid image dimensions")
        scale_x = image_width / self.width
        scale_y = image_height / self.height
        if (not 0.95 <= scale_x / scale_y <= 1.05
            or not 0.95 <= scale_x <= 4.0):
            raise GeometryStop("SCREENSHOT_FRAME_MISMATCH", "Image/frame scale mismatch")
        if (not all(isfinite(v) for v in (pixel_x, pixel_y))
            or not 0 <= pixel_x < image_width
            or not 0 <= pixel_y < image_height):
            raise GeometryStop("PIXEL_OUTSIDE_SCREENSHOT", "Image point outside screenshot")
        return pixel_x / scale_x, pixel_y / scale_y

    def pixel_to_screen(
        self, pixel_x: float, pixel_y: float, image_width: int, image_height: int
    ) -> tuple[float, float]:
        return self.screen_point(*self.pixel_to_local(
            pixel_x, pixel_y, image_width, image_height
        ))


def validate_farm_window(
    frame: WindowFrame, platform: str, layout: dict, max_size_deviation: float = 0.06
) -> None:
    if platform not in ("qq", "wechat"):
        raise GeometryStop("UNKNOWN_PLATFORM", f"Unknown platform: {platform}")
    expected_title = "QQ经典农场"
    if frame.title != expected_title:
        raise GeometryStop("WINDOW_NOT_FOUND", f"Unexpected window title: {frame.title}")
    allowed_owners = {"qq": ("QQ小程序",), "wechat": ("微信", "WeChat")}
    if frame.owner not in allowed_owners[platform]:
        raise GeometryStop("WRONG_FRONTMOST_APP", f"Unexpected owner: {frame.owner}")
    baseline_w, baseline_h = layout["platforms"][platform]["baseline_window_size"]
    if (abs(frame.width / baseline_w - 1) > max_size_deviation
        or abs(frame.height / baseline_h - 1) > max_size_deviation):
        raise GeometryStop("WINDOW_SIZE_CHANGED", "Farm canvas differs from calibrated baseline")


def plot_local_point(
    platform: str, u: int, v: int, frame: WindowFrame, layout: dict
) -> tuple[float, float]:
    validate_farm_window(frame, platform, layout)
    if type(u) is not int or type(v) is not int or not 0 <= u <= 5 or not 0 <= v <= 3:
        raise GeometryStop("INVALID_PLOT", f"Plot outside 4x6 grid: {(u, v)}")
    config = layout["platforms"][platform]
    ox, oy = config["normalized_origin"]
    ux, uy = config["normalized_u_step"]
    vx, vy = config["normalized_v_step"]
    x = (ox + u * ux + v * vx) * frame.width
    y = (oy + u * uy + v * vy) * frame.height
    frame.screen_point(x, y)
    return x, y
