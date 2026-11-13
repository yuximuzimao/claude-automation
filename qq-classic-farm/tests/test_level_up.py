"""Regression tests for a level-independent, guarded QQ overlay dismissal."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import farm_level_up as overlay


def sample(title=True, hint=True, blank=True):
    frame = np.zeros((1111, 603), dtype=np.float32)
    for present, name, x, y in ((title, 'title', 189, 343), (hint, 'dismiss', 227, 923)):
        if present:
            template = overlay.load_gray(overlay.ASSETS / f'qq-{name}.png')
            h, w = template.shape
            frame[y:y+h, x:x+w] = template
    frame[285:318, 270:334] = np.random.default_rng(7).integers(0, 255, size=(33, 64))
    if not blank:
        frame[979:982, 299:302] = 255
    return frame


def test_match_without_level_and_verify_disappearance():
    frame = sample()
    clicks = []

    def click(point, delay):
        clicks.append((point, delay))
        frame[:] = sample(False, False)

    assert overlay.dismiss_level_up(lambda r: frame[r[1]:r[3], r[0]:r[2]], click)
    assert clicks == [((300, 980), 650)]


@pytest.mark.parametrize(('title', 'hint', 'blank', 'reason', 'clicks_expected'), [
    (False, True, True, None, 0),
    (True, False, True, 'HINT_NOT_CONFIRMED', 0),
    (True, True, False, 'POINT_NOT_BLANK', 0),
    (True, True, True, 'DISMISS_NOT_CONFIRMED', 1),
])
def test_stops_safely(title, hint, blank, reason, clicks_expected):
    frame = sample(title, hint, blank)
    clicks = []
    capture = lambda r: frame[r[1]:r[3], r[0]:r[2]]
    click = lambda *a: clicks.append(a)
    if reason:
        with pytest.raises(ValueError, match=reason):
            overlay.dismiss_level_up(capture, click)
    else:
        assert not overlay.dismiss_level_up(capture, click)
    assert len(clicks) == clicks_expected
