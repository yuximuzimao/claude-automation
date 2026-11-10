"""Pure control flow and guarded-drag validation; never touches the farm."""
import json
from pathlib import Path
import sys
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from farm_mischief_once import sweep,land_route


def menu(*actions,state=None):
    return {'state':state or 'actionable','actions':{k:[10 if k=='grass' else 20,30] for k in actions}}


def run(menus,limit=4,drag_error=False):
    reads=iter(menus);events=[];progress={'grass_gestures':0,'bug_gestures':0}
    def drag(point):
        events.append(('drag',point))
        if drag_error:raise ValueError('partial drag')
    reason=sweep(lambda p,d:events.append(('click',p)),lambda:next(reads),drag,
                 lambda:events.append(('home',)),[1,1],[2,2],[[3,3],[4,4],[5,5]],[24,24],progress,limit)
    return reason,events,progress


def test_mature_skipped_then_grass_bugs_and_shared_zero():
    reason,e,p=run([menu(state='mature'),menu('grass','bug'),menu('bug'),menu(state='exhausted')])
    assert reason=='shared_quota_exhausted'
    assert [x for x in e if x[0]=='drag']==[('drag',[10,30]),('drag',[20,30])]
    assert ('click',[3,3]) in e
    assert e[-1]==('home',)
    assert p['grass_gestures']==p['bug_gestures']==1


def test_zero_after_grass_does_not_spend_a_separate_bug_quota():
    reason,e,p=run([menu('grass','bug'),menu(state='exhausted')])
    assert reason=='shared_quota_exhausted'
    assert p['bug_gestures']==0
    assert len([x for x in e if x[0]=='drag'])==1


def test_no_bug_after_grass_moves_to_next_friend():
    reason,e,p=run([menu('grass'),menu(state='no_actions'),menu('grass','bug'),menu(state='exhausted')])
    assert reason=='shared_quota_exhausted'
    assert ('click',[3,3]) in e
    assert p['grass_gestures']==2 and p['bug_gestures']==0


def test_limit_returns_home_without_claiming_quota_completed():
    reason,e,p=run([menu(state='mature')]*4)
    assert reason=='visit_limit_without_zero_confirmation'
    assert [p for event,*rest in e if event=='drag' for p in rest]==[]
    assert all(('click',p) in e for p in ([3,3],[4,4],[5,5]))
    assert e[-1]==('home',)


def test_unknown_or_failed_drag_never_retries():
    with pytest.raises(ValueError,match='AMBIGUOUS'):
        run([menu(state='unknown')])
    with pytest.raises(ValueError,match='partial drag'):
        run([menu('grass','bug')],drag_error=True)


def test_route_visits_each_verified_land_once_starting_at_24():
    layout=json.loads((ROOT/'data/ui-layout.json').read_text())
    route=land_route(layout)
    points=layout['platforms']['qq']['confirmed_land_centers']['points']
    assert route[:4]==list(reversed(points[5]))
    assert len(route)==len({tuple(p) for p in route})==24
    assert set(map(tuple,route))=={tuple(p) for row in points for p in row}


@pytest.fixture(scope='module')
def helper(tmp_path_factory):
    binary=tmp_path_factory.mktemp('path-drag')/'helper'
    subprocess.run(['swiftc',str(ROOT/'scripts/farm_path_drag.swift'),'-o',str(binary)],check=True,capture_output=True,text=True,timeout=40)
    return binary


@pytest.mark.parametrize('mutation,expected',[(None,0),('outside',2),('count',2),('owner',2)])
def test_compiled_path_validation_never_inputs(helper,mutation,expected):
    layout=json.loads((ROOT/'data/ui-layout.json').read_text())
    payload={'window_id':1,'pid':2,'owner':'QQ小程序','title':'QQ经典农场',
             'frame':{'x':100,'y':100,'width':603,'height':1111},
             'points':[[180,800],*land_route(layout)]}
    if mutation=='outside':payload['points'][1]=[900,900]
    if mutation=='count':payload['points'].pop()
    if mutation=='owner':payload['owner']='QQ'
    r=subprocess.run([str(helper),'--validate'],input=json.dumps(payload),capture_output=True,text=True,timeout=5)
    assert r.returncode==expected
    assert json.loads(r.stdout)['events_sent']==0


def test_full_run_continues_past_first_friend_until_shared_zero():
    menus = [menu('grass','bug'), menu('bug'), menu('grass','bug')] * 3
    menus += [menu('grass','bug'), menu(state='exhausted')]
    reason, events, progress = run(menus, limit=100)
    assert reason == 'shared_quota_exhausted'
    assert progress['friend_visit'] == 4
    assert progress['grass_gestures'] == 4 and progress['bug_gestures'] == 3
    assert events[-1] == ('home',)
