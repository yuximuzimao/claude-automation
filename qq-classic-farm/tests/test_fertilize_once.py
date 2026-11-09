from pathlib import Path
import sys

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from farm_fertilize_once import FertilizerStop, farm_canvas, fertilize_once, template_center


LAND = (355.8, 607)
WORK = (309, 853)
CHECKBOX = (440, 799)
CONFIRM = (436, 677)
FERTILIZER = (307, 709)


def run_fertilize(states, events):
    states = iter(states)

    def locate(kind):
        events.append(kind)
        return next(states)

    return fertilize_once(lambda point, delay: events.append((point, delay)), locate, LAND)


def test_already_checked_without_work_uses_one_dose():
    events = []
    assert run_fertilize([None, (True, None, FERTILIZER)], events) is False
    assert events == ["work", (LAND, 350), "panel", (FERTILIZER, 0)]


def test_work_precedes_plot_and_waits_one_second():
    events = []
    assert run_fertilize([WORK, (True, None, FERTILIZER)], events) is True
    assert events == ["work", (WORK, 1000), (LAND, 350), "panel", (FERTILIZER, 0)]


def test_unchecked_toggles_confirms_and_reads_back_before_dosing():
    events = []
    moved_bucket = (307, 696)
    run_fertilize([None, (False, CHECKBOX, FERTILIZER), CONFIRM, (True, None, moved_bucket)], events)
    assert events == [
        "work", (LAND, 350), "panel", (CHECKBOX, 350),
        "enable_prompt", (CONFIRM, 350), "panel", (moved_bucket, 0),
    ]


@pytest.mark.parametrize(("tail", "reason"), [
    ([None], "ONE_KEY_FERTILIZER_PROMPT_NOT_FOUND"),
    ([CONFIRM, (False, CHECKBOX, FERTILIZER)], "CHECKBOX_NOT_CONFIRMED"),
])
def test_unconfirmed_checkbox_never_doses(tail, reason):
    events = []
    with pytest.raises(FertilizerStop, match=reason):
        run_fertilize([None, (False, CHECKBOX, FERTILIZER), *tail], events)
    assert (FERTILIZER, 0) not in events
    assert events.count((CHECKBOX, 350)) == 1


def test_capture_failure_stops_before_any_click():
    def capture_failed(kind):
        raise OSError("screenshot unavailable")

    events = []
    with pytest.raises(OSError, match="screenshot unavailable"):
        fertilize_once(lambda *args: events.append(args), capture_failed, LAND)
    assert events == []


def test_template_center_maps_shifted_control_back_to_canvas():
    rng = np.random.default_rng(35)
    template = rng.integers(50, 220, size=(6, 8)).astype(np.float32)
    region = np.full((30, 26), 95, dtype=np.float32)
    region[13:19, 9:17] = template
    assert template_center(region, template, (400, 754), 0.90) == (413, 770)


def test_embedded_wechat_clicks_use_right_farm_canvas():
    window = {"x": 835, "y": 149, "width": 1039, "height": 1155}
    assert farm_canvas(window, (625, 1155), 414) == {
        "x": 1249, "y": 149, "width": 625, "height": 1155,
    }


@pytest.mark.parametrize('kind', ['ordinary', 'organic'])
def test_panel_request_keeps_selected_fertilizer_kind(kind):
    import json
    from farm_fertilize_once import ROOT, UI, fertilizer_locator
    from anchor_locator import load_gray
    spec=json.loads((ROOT/'data/ui-anchors.json').read_text())['fixed_points']['scenes']['fertilizer-switch']['recognition']['qq']
    image=np.full((1111,603),230,dtype=np.float32)
    bucket_rect=spec['organic_bucket_rect' if kind=='organic' else 'bucket_rect']
    for path,(x,y) in [(UI/'fertilizer'/f'qq-{kind}.png',(bucket_rect[0]+3,650)),(UI/'qq-fertilizer-onekey-tick.png',(400,730))]:
        template=load_gray(path)
        h,w=template.shape
        image[y:y+h,x:x+w]=template
    locate=fertilizer_locator(lambda r:image[r[1]:r[3],r[0]:r[2]],'qq',spec,kind)
    checked,_,point=locate('panel')
    assert checked and bucket_rect[0] <= point[0] < bucket_rect[2]
