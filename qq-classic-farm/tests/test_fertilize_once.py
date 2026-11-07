from pathlib import Path
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_checked_tick_allows_exactly_one_fertilizer_click():
    from farm_fertilize_once import fertilize_once

    tick = np.full((19, 21), 95, dtype=np.float32)
    tick[8:13, 2:9] = 179
    tick[3:10, 9:18] = 180
    checkbox = np.full((34, 36), 95, dtype=np.float32)
    checkbox[8:27, 7:28] = tick
    land, checkbox_center, fertilizer = (341.6, 583.9), (425, 754), (297, 676)
    events = []

    def capture():
        events.append("capture-checkbox")
        return checkbox

    fertilize_once(
        lambda point, delay: events.append(point),
        capture, land, checkbox_center, fertilizer, tick,
    )
    assert events == [land, "capture-checkbox", fertilizer]


def test_missing_tick_toggles_once_and_then_applies_fertilizer():
    from farm_fertilize_once import fertilize_once

    tick = np.full((19, 21), 95, dtype=np.float32)
    tick[8:13, 2:9] = 179
    tick[3:10, 9:18] = 180
    unchecked = np.full((34, 36), 95, dtype=np.float32)
    checked = unchecked.copy()
    checked[8:27, 7:28] = tick
    frames = iter([unchecked, checked])
    land, checkbox_center, fertilizer = (355.8, 607), (441, 786), (306, 705)
    events = []

    def capture():
        events.append("capture-checkbox")
        return next(frames)

    fertilize_once(
        lambda point, delay: events.append(point),
        capture, land, checkbox_center, fertilizer, tick,
    )
    assert events == [land, "capture-checkbox", checkbox_center, "capture-checkbox", fertilizer]


def test_still_unchecked_after_toggle_does_not_apply_fertilizer():
    from farm_fertilize_once import FertilizerStop, fertilize_once

    tick = np.arange(399, dtype=np.float32).reshape(19, 21)
    land, checkbox_center = (355.8, 607), (441, 786)
    events = []
    with pytest.raises(FertilizerStop, match="CHECKBOX_NOT_CONFIRMED"):
        fertilize_once(
            lambda point, delay: events.append(point),
            lambda: np.full((34, 36), 95, dtype=np.float32),
            land, checkbox_center, (306, 705), tick,
        )
    assert events == [land, checkbox_center]


def test_capture_error_does_not_toggle_checkbox():
    from farm_fertilize_once import fertilize_once

    def capture():
        raise OSError("screenshot unavailable")

    events = []
    land = (341.6, 583.9)
    with pytest.raises(OSError, match="screenshot unavailable"):
        fertilize_once(
            lambda point, delay: events.append(point),
            capture, land, (425, 754), (297, 676), np.empty((19, 21)),
        )
    assert events == [land]


def test_embedded_wechat_clicks_use_right_farm_canvas():
    from farm_fertilize_once import farm_canvas

    window = {"x": 835, "y": 149, "width": 1039, "height": 1155}
    assert farm_canvas(window, (625, 1155), 414) == {
        "x": 1249, "y": 149, "width": 625, "height": 1155,
    }
