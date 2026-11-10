"""No live windows or inputs: exercise the share sequence and failure boundaries."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import farm_share_once as share


def anchors():
    return json.loads((ROOT / 'data/ui-anchors.json').read_text())['fixed_points']


def selector(window_id=2):
    return dict(window_id=window_id, pid=10, owner='QQ', title='分享',
                x=400, y=200, width=600, height=600)


def test_share_types_without_search_click_or_enter_then_claims_same_point():
    steps = share.share_steps(anchors())
    events = []
    reads = iter([[], [selector()], []])
    progress = {'completed_steps': [], 'send_attempted': False}
    share.run_share(steps, '灬🐈‍⬛、御汐。', {'owner': 'QQ小程序'}, lambda: next(reads),
                    lambda target,point,delay,is_selector: events.append(('click', target['owner'], point)),
                    lambda target,point,text,delay: events.append(('type', text, point)), lambda farm: farm, progress)
    assert [e[0] for e in events] == ['click','click','type','click','click','click','click','click']
    assert events[2] == ('type','灬🐈‍⬛、御汐。',[162,64])
    assert events[3] == ('click','QQ',[59,145])
    assert events[4] == ('click','QQ',[511,534])
    assert events[1][2] == events[5][2] == [421,913]
    assert events[-1] == ('click','QQ小程序',[565,182])
    assert progress['send_attempted'] is True
    assert progress['completed_steps'] == [step[0] for step in steps]


def test_focus_not_returned_stops_after_one_send():
    steps = share.share_steps(anchors())
    reads = iter([[], [selector()], []])
    progress = {'completed_steps': [], 'send_attempted': False}
    calls = []
    def click(target, point, delay, is_selector):
        calls.append(point)
        if progress['stage'] == 'claim':
            raise share.FertilizerStop('WRONG_FRONTMOST_APP')
    with pytest.raises(share.FertilizerStop, match='WRONG_FRONTMOST_APP'):
        share.run_share(steps, 'name', {}, lambda: next(reads), click, lambda *a: None, lambda farm: farm, progress)
    assert calls.count([511,534]) == 1
    assert progress['stage'] == 'claim'
    assert progress['completed_steps'][-1] == 'return_farm'
    assert [300,980] not in calls
    assert [565,182] not in calls


@pytest.mark.parametrize('windows,previous', [([],set()),([selector()],{2}),([selector(),selector(3)],set())])
def test_missing_preexisting_or_ambiguous_selector_is_rejected(windows, previous):
    with pytest.raises(ValueError, match='NOT_UNIQUE'):
        share.selector_target(windows, previous)


def test_plan_mode_does_not_access_windows_or_send(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['share'])
    monkeypatch.setattr(share.subprocess,'run',lambda *a,**k: pytest.fail('no subprocess in plan mode'))
    assert share.main() == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'plan_ok_no_input'


def test_return_waits_for_selector_to_close_and_never_resends():
    progress={'completed_steps':[],'send_attempted':False}
    reads=iter([[],[selector()],[selector()]])
    clicks=[]
    with pytest.raises(ValueError,match='SELECTOR_STILL_OPEN'):
        share.run_share(share.share_steps(anchors()),'name',{},lambda:next(reads),
                        lambda target,point,*a:clicks.append(point),lambda *a:None,
                        lambda farm:pytest.fail('must not hide an open selector'),progress)
    assert clicks.count([511,534])==1
    assert progress['completed_steps'][-1]=='send'


def test_restore_rebinds_geometry_but_rejects_different_farm(monkeypatch):
    original={'pid':123,'window_id':456,'owner':'QQ小程序','title':'QQ经典农场','frame':{'x':1}}
    moved={**original,'frame':{'x':200}}
    calls=[]
    monkeypatch.setattr(share.subprocess,'run',lambda *a,**k:calls.append(a))
    monkeypatch.setattr(share,'farm_target',lambda *a:(None,moved))
    assert share.restore_farm(original,'registry',{})==moved
    assert calls[0][0][-2:]==['123','456']
    monkeypatch.setattr(share,'farm_target',lambda *a:(None,{**moved,'pid':999}))
    with pytest.raises(ValueError,match='IDENTITY_CHANGED'):
        share.restore_farm(original,'registry',{})
