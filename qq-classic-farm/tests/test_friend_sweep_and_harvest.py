import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from anchor_locator import load_gray
from farm_friend_sweep import interaction_state, sweep
from farm_harvest_once import special_points


def test_friend_sweep_visits_second_third_and_reuses_later_slot():
    events = []
    states = iter(["action"] * 5 + ["no_action"])
    result = sweep(
        lambda point, _: events.append(point), lambda: next(states), lambda: events.append("home"),
        "friends", "first", "interact", ("second", "third", "later"),
    )
    assert result == ("no_action", 5)
    assert events == [
        "friends", "first", "interact", "second", "interact", "third",
        "interact", "later", "interact", "later", "interact", "later", "home",
    ]


@pytest.mark.parametrize("state", ["no_action", "shared_point_outside_button"])
def test_friend_sweep_returns_home_without_clicking_unavailable_action(state):
    events = []
    result = sweep(
        lambda point, _: events.append(point), lambda: state, lambda: events.append("home"),
        "friends", "first", "interact", ("second", "third", "later"),
    )
    assert result == (state, 0)
    assert events == ["friends", "first", "home"]


def test_dual_buttons_use_only_the_shared_click_target():
    anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
    strip = anchors["fixed_points"]["scenes"]["friend-farm-navigation"]["action_strip_xyxy"]["wechat"]
    templates = [load_gray(ROOT / "assets/ui/friends" / f"wechat-{name}.png") for name in ("steal", "work")]
    image = np.zeros((strip[3] - strip[1], strip[2] - strip[0]), dtype=np.float32)
    for center_x, template in zip((258, 358), templates):
        h, w = template.shape
        x0 = center_x - strip[0] - w // 2
        y0 = 852 - strip[1] - h // 2
        image[y0:y0+h, x0:x0+w] = template
    assert interaction_state(image, templates, strip[:2], (283, 852)) == "action"
    assert interaction_state(image, templates, strip[:2], (309, 852)) == "shared_point_outside_button"


def test_special_stars_are_located_in_one_capture_and_missing_star_stops():
    anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
    rects = anchors["anchors"]["onekey_harvest"]["platforms"]["wechat"]["special_rects"]
    x0, y0 = rects["01"][:2]
    x1, y1 = rects["07"][2:]
    image = np.zeros((y1 - y0, x1 - x0), dtype=np.float32)
    centers = [(353, 558), (438, 601)]
    for plot, (cx, cy) in zip((1, 7), centers):
        template = load_gray(ROOT / "assets/ui/harvest" / f"wechat-special-{plot:02}.png")
        h, w = template.shape
        x, y = cx - x0 - w // 2, cy - y0 - h // 2
        image[y:y+h, x:x+w] = template

    reads = []

    def capture(rect):
        reads.append(rect)
        return image

    assert special_points(capture, "wechat", [1, 7], rects) == [(353, 558.5), (438, 601.5)]
    assert reads == [(x0, y0, x1, y1)]
    image[:, rects["07"][0] - x0:] = 0
    with pytest.raises(ValueError, match="SPECIAL_PICKABLE_NOT_FOUND_AT_PLOT_07"):
        special_points(capture, "wechat", [1, 7], rects)
    with pytest.raises(ValueError, match="SPECIAL_HARVEST_GROUP_NOT_VALIDATED"):
        special_points(capture, "wechat", [13], rects)
