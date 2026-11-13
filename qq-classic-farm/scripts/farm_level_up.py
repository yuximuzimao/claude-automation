"""Recognize and dismiss the QQ level-up overlay without reading the level."""
from pathlib import Path

from anchor_locator import load_gray, normalized_cross_correlation


ASSETS = Path(__file__).resolve().parents[1] / 'assets/ui/level-up'
TITLE_REGION = (173, 334, 431, 411)
DISMISS_REGION = (210, 910, 390, 962)
# The existing user-confirmed dismiss point, with a small blank-area check.
BLANK_REGION = (293, 973, 308, 988)
DISMISS_POINT = (300, 980)
THRESHOLD = 0.90


def matches(capture, region, template):
    scores = normalized_cross_correlation(capture(region), load_gray(ASSETS / template))
    return scores is not None and scores.max() >= THRESHOLD


def dismiss_level_up(capture, click):
    """Use one click only after two local matches, then verify disappearance."""
    if not matches(capture, TITLE_REGION, 'qq-title.png'):
        return False
    if not matches(capture, DISMISS_REGION, 'qq-dismiss.png'):
        raise ValueError('QQ_LEVEL_UP_DISMISS_HINT_NOT_CONFIRMED')
    blank = capture(BLANK_REGION)
    if blank.max() - blank.min() > 28:
        raise ValueError('QQ_LEVEL_UP_DISMISS_POINT_NOT_BLANK')
    click(DISMISS_POINT, 650)
    if (matches(capture, TITLE_REGION, 'qq-title.png')
            or matches(capture, DISMISS_REGION, 'qq-dismiss.png')):
        raise ValueError('QQ_LEVEL_UP_DISMISS_NOT_CONFIRMED')
    return True
