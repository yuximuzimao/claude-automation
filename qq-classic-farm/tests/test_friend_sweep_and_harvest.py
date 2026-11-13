import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from anchor_locator import load_gray
from farm_friend_sweep import interaction_target, sweep
from farm_harvest_once import special_points


def test_friend_sweep_visits_second_third_and_reuses_later_slot():
    events = []
    actions = iter(["action-1", "action-2", "action-3", "action-4", "action-5", None])
    result = sweep(
        lambda point, _: events.append(point), lambda: next(actions), lambda: events.append("home"),
        "friends", "first", ("second", "third", "later"),
    )
    assert result == ("no_action", 5)
    assert events == [
        "friends", "first", "action-1", "second", "action-2", "third",
        "action-3", "later", "action-4", "later", "action-5", "later", "home",
    ]


def test_friend_sweep_returns_home_without_clicking_when_no_action():
    events = []
    result = sweep(
        lambda point, _: events.append(point), lambda: None, lambda: events.append("home"),
        "friends", "first", ("second", "third", "later"),
    )
    assert result == ("no_action", 0)
    assert events == ["friends", "first", "home"]


def test_dual_buttons_clicks_recognized_button_center_without_fixed_shared_point():
    anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
    strip = anchors["fixed_points"]["scenes"]["friend-farm-navigation"]["action_strip_xyxy"]["wechat"]
    templates = [load_gray(ROOT / "assets/ui/friends" / f"wechat-{name}.png") for name in ("steal", "work")]
    image = np.zeros((strip[3] - strip[1], strip[2] - strip[0]), dtype=np.float32)
    expected = []
    for center_x, template in zip((258, 358), templates):
        h, w = template.shape
        x0 = center_x - strip[0] - w // 2
        y0 = 852 - strip[1] - h // 2
        image[y0:y0+h, x0:x0+w] = template
        expected.append((center_x + (w % 2) / 2, 852 + (h % 2) / 2))

    assert interaction_target(image, templates, strip[:2]) == pytest.approx(expected[0])


def test_special_harvest_uses_confirmed_point_without_images():
    anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
    config = anchors["anchors"]["onekey_harvest"]["platforms"]["qq"]
    assert special_points([1], config) == [(338, 535)]
    assert special_points([], config) == []
    with pytest.raises(ValueError, match="SPECIAL_HARVEST_POINT_NOT_VALIDATED_07"):
        special_points([1, 7], config)


def test_daily_task_resolves_same_dual_button_target(monkeypatch, capsys):
    import farm_daily_clicks as daily
    import farm_friend_sweep as friends
    from farm_daily_task_once import task_steps
    events = []
    target = {'frame': {}}
    monkeypatch.setattr(sys, 'argv', ['daily', '--platform', 'qq', '--execute'])
    monkeypatch.setattr(daily, 'farm_target', lambda *a: (None, target))
    monkeypatch.setattr(friends, 'read_interaction_target', lambda *a: [257, 820])
    monkeypatch.setattr(daily, 'return_home_point', lambda *a: [550, 840])
    monkeypatch.setattr(daily, 'click_batch', lambda *a: events.extend(a[-1]))
    level_checks = []
    monkeypatch.setattr(daily, 'dismiss_level_up', lambda *a: level_checks.append(len(events)))
    assert daily.run_daily('test', task_steps) == 0
    assert [events[2]['x'], events[2]['y']] == [257, 820]
    assert level_checks == [3]
    assert not any(e['x'] == 297 and e['y'] == 820 for e in events)
    events.clear()
    monkeypatch.setattr(friends, 'read_interaction_target', lambda *a: None)
    assert daily.run_daily('test', task_steps) == 2
    assert len(events) == 2  # No blind interaction or subsequent task claim.
