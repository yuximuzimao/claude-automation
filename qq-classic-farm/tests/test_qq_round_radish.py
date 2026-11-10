from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_qq_round import workflow
from farm_radish_restock import DEFAULT_PURCHASES
from farm_radish_xp import DEFAULT_ROUNDS, RADISH_BATCH, radish_plan


import json
import pytest


@pytest.fixture
def sample_catalog(tmp_path):
    seeds=[]
    for i in range(33):
        name = "森野白桃种子" if i == 27 else "白萝卜种子" if i == 32 else f"seed-{i}"
        seeds.append({"name": name, "observations": {"qq": {
            "quantity_latest_known": 120,
            "latest_warehouse_position": {"page": i//5+1, "slot": i%5+1},
        }}})
    path=tmp_path/'catalog.json'
    path.write_text(json.dumps({"seeds":seeds}))
    return path


@pytest.fixture
def sample_plan(tmp_path):
    empty={"planting":{"special":[],"ordinary":None},"daily":{"tasks":False,"fertilizer_reward":False,"share":False}}
    plan={"qq":{"planting":{
        "special":[{"plot":1,"page":1,"slot":4}],
        "ordinary":{"page":6,"slot":3,"quantity":12},
        "ordinary_after_exhaustion":[{"page":6,"slot":3,"page_items":5,"quantity":8}],
    },"daily":empty["daily"]},"wechat":empty}
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan));return path


def test_radish_default_is_five_full_fields():
    assert DEFAULT_ROUNDS == 5
    assert DEFAULT_ROUNDS * RADISH_BATCH == 120


def test_monthly_restock_is_thirty_seven_max_purchases():
    assert DEFAULT_PURCHASES == 37
    assert DEFAULT_PURCHASES * 99 == 3663
    assert DEFAULT_PURCHASES * 99 >= 30 * DEFAULT_ROUNDS * RADISH_BATCH


def test_radish_plan_is_qq_ordinary_page7_slot3_only(sample_catalog):
    plan = radish_plan(sample_catalog)
    assert plan["qq"]["planting"] == {
        "special": [],
        "ordinary": {"page": 7, "slot": 3, "page_items": 3},
    }
    assert plan["wechat"]["planting"] == {"special": [], "ordinary": None}


def test_qq_round_uses_original_daily_task_then_friend_sweep():
    steps = workflow(5, ROOT / "data/operation-plan.json")
    scripts = [Path(step[1]).name for step in steps if not isinstance(step, tuple)]
    assert scripts == [
        "farm_fertilize_once.py",
        "farm_harvest_once.py",
        "farm_radish_xp.py",
        "farm_plant_once.py",
        "farm_daily_task_once.py",
        "farm_friend_sweep.py",
        "farm_daily_fertilizer_reward.py",
    ]


import json
from types import SimpleNamespace
import numpy as np
import pytest
import farm_radish_restock as restock
import farm_fertilize_once as fertilizer


@pytest.mark.parametrize('hit_at', [1, 4, 10, None])
def test_restock_purchase_requires_local_match(monkeypatch, capsys, hit_at):
    events = []
    scans = []
    monkeypatch.setattr(sys, 'argv', ['restock', '--execute', '--purchases', '1'])
    monkeypatch.setattr(restock, 'farm_target', lambda *a: (None, {
        'window_id': 1, 'pid': 2, 'owner': 'QQ小程序', 'title': 'QQ经典农场', 'frame': {},
    }))
    monkeypatch.setattr(restock, 'click_batch', lambda *a: events.append(('click', len(a[3]))))
    def drag(*a, **kw):
        events.append(('drag',))
        return SimpleNamespace(returncode=0, stdout='{"status":"drag_sent_unverified"}')
    monkeypatch.setattr(restock.subprocess, 'run', drag)
    monkeypatch.setattr(restock, 'capture_region', lambda frame, roi: scans.append(roi))
    monkeypatch.setattr(restock, 'template_center', lambda *a: (100, 360) if len(scans) == hit_at else None)
    original_seek = restock.seek_radish
    monkeypatch.setattr(restock, 'seek_radish', lambda scroll, match: original_seek(scroll, match, lambda seconds: events.append(('wait', seconds))))
    assert restock.main() == (0 if hit_at else 2)
    assert scans == [restock.RADISH_ROI] * (hit_at or 10)
    assert events.count(('wait', 1.5)) == (hit_at or 10)
    assert events.count(('click', 3)) == (1 if hit_at else 0)
    if hit_at:
        assert events.index(('click', 3)) > max(i for i,e in enumerate(events) if e == ('drag',))
    else:
        assert events.count(('click', 1)) == 1  # Only opening shop, never buying.
        assert 'AGENT_REQUIRED' in capsys.readouterr().out


def test_seek_does_not_retry_input_or_capture_error():
    for failing_stage in ['scroll', 'capture']:
        calls = []
        def scroll():
            calls.append('scroll')
            if failing_stage == 'scroll':
                raise RuntimeError('input failed')
        def match():
            raise RuntimeError('capture failed')
        with pytest.raises(RuntimeError):
            restock.seek_radish(scroll, match, lambda _: None)
        assert calls == ['scroll']


def test_real_radish_template_matches_only_when_inside_roi():
    from anchor_locator import load_gray
    template = load_gray(restock.RADISH_TEMPLATE)
    frame = np.full((1111, 603), 220, dtype=np.float32)
    height, width = template.shape
    frame[327:327+height, 200:200+width] = template  # Neighbouring card must not unlock.
    x0,y0,x1,y1 = restock.RADISH_ROI
    assert restock.template_center(frame[y0:y1,x0:x1], template, (x0,y0), .90) is None
    frame[327:327+height, 68:68+width] = template
    assert restock.template_center(frame[y0:y1,x0:x1], template, (x0,y0), .90) is not None


@pytest.mark.parametrize('requested,reported,returncode,ok', [(1,1,0,True),(3,3,0,True),(3,1,0,False),(3,1,2,False)])
def test_click_batch_counts_and_partial_failure(monkeypatch, requested, reported, returncode, ok):
    monkeypatch.setattr(fertilizer.subprocess, 'run', lambda *a,**k: SimpleNamespace(
        returncode=returncode, stdout=json.dumps({'status':'clicks_sent_unverified','click_count':reported,'code':'PARTIAL'})))
    call = lambda: fertilizer.click_batch('helper','--execute',{'owner':'QQ小程序'},[{}]*requested)
    if ok:
        call()
    else:
        with pytest.raises(fertilizer.FertilizerStop):
            call()


@pytest.mark.parametrize('count,positions', [(1,[3]),(2,[2.5,3.5]),(3,[2,3,4]),(4,[1.5,2.5,3.5,4.5]),(5,[1,2,3,4,5])])
def test_centered_picker_positions(count, positions):
    from farm_plant_once import seed_slot_offset
    picker={'seed_slot_offsets':[[100*i,50] for i in range(1,6)]}
    assert [seed_slot_offset(picker,i,count) for i in range(1,count+1)] == [(100*p,50) for p in positions]


def test_radish_uses_both_fertilizers_before_harvest(monkeypatch, sample_catalog):
    import farm_radish_xp as xp
    calls=[]
    original_plan=xp.radish_plan
    monkeypatch.setattr(xp,'radish_plan',lambda:original_plan(sample_catalog))
    monkeypatch.setattr(sys,'argv',['xp','--rounds','1','--execute'])
    monkeypatch.setattr(xp,'run_script',lambda *args:calls.append(args))
    monkeypatch.setattr(xp,'sleep',lambda _:None)
    assert xp.main()==0
    assert [c[0] for c in calls]==['farm_plant_once.py','farm_fertilize_once.py','farm_fertilize_once.py','farm_harvest_once.py']
    assert calls[2][3:5]==('--kind','organic')


def test_same_day_mature_skips_fertilizer_and_daily():
    steps=workflow(0,ROOT/'data/operation-plan.json',field_state='mature',tasks=False,friends=False,reward=False)
    assert [Path(s[1]).name for s in steps]==['farm_harvest_once.py','farm_plant_once.py']


def test_empty_field_daily_round_does_not_harvest_or_fertilize_initially():
    steps=workflow(5,ROOT/'data/operation-plan.json',field_state='empty')
    assert Path(steps[0][1]).name=='farm_radish_xp.py'


def test_radish_position_compacts_after_peach_exhaustion(tmp_path, sample_catalog):
    import farm_radish_xp as xp
    data=json.loads(sample_catalog.read_text())
    for seed in data['seeds']:
        if seed['name']=='森野白桃种子':seed['observations']['qq']['quantity_latest_known']=0
    path=tmp_path/'catalog.json';path.write_text(json.dumps(data))
    assert xp.radish_plan(path)['qq']['planting']['ordinary']=={'page':7,'slot':2,'page_items':2}


def test_exhaustion_plan_contains_complete_sequence(sample_plan):
    from farm_plant_once import read_plan, plan_page_sizes
    policy=json.loads((ROOT/'data/ui-layout.json').read_text())['plot_policy']
    steps,_=read_plan(sample_plan,'qq',policy)
    assert [s[:3] for s in steps]==[(1,1,4),(24,6,3),(23,6,3)]
    assert plan_page_sizes(sample_plan,'qq')==[5,5,5]


def test_check_plan_needs_no_window_or_agent_entry(monkeypatch,capsys,sample_plan):
    import farm_plant_once as planting
    monkeypatch.setattr(sys,'argv',['plant','--platform','qq','--plan',str(sample_plan),'--check-plan'])
    monkeypatch.setattr(planting.subprocess,'run',lambda *a,**k: pytest.fail('must not open or inspect windows'))
    assert planting.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['steps']==[[1,1,4],[24,6,3],[23,6,3]]


def test_three_ordinary_selections_descend_without_counting_special():
    from farm_plant_once import planting_steps
    policy=json.loads((ROOT/'data/ui-layout.json').read_text())['plot_policy']
    assert [s[0] for s in planting_steps([(1,1,4)],(6,3),policy,[(6,3),(6,3)])]==[1,24,23,22]
    assert [s[0] for s in planting_steps([], (6,3),policy,[(6,3),(6,3)])]==[24,23,22]
    assert [s[0] for s in planting_steps([], (7,2),policy)]==[1]


def test_descending_entry_rejects_forbidden_or_covered_plot():
    from farm_plant_once import planting_steps
    policy=json.loads((ROOT/'data/ui-layout.json').read_text())['plot_policy']
    with pytest.raises(ValueError,match='INVALID_ORDINARY_ENTRY_21'):
        planting_steps([(1,1,4)],(6,3),policy,[(6,3)]*3)
    with pytest.raises(ValueError,match='INVALID_ORDINARY_ENTRY_24'):
        planting_steps([(23,1,4)],(6,3),policy)


@pytest.mark.parametrize('quantities',[(20,8),(12,7),(None,8)])
def test_exhaustion_rejects_invalid_capacity(sample_plan,quantities):
    from farm_plant_once import read_plan
    data=json.loads(sample_plan.read_text());p=data['qq']['planting']
    p['ordinary']['quantity'],p['ordinary_after_exhaustion'][0]['quantity']=quantities
    sample_plan.write_text(json.dumps(data))
    policy=json.loads((ROOT/'data/ui-layout.json').read_text())['plot_policy']
    with pytest.raises(ValueError): read_plan(sample_plan,'qq',policy)


def test_ordinary_sequence_waits_and_stops_without_retry(monkeypatch):
    import farm_plant_once as p
    clicks=[];waits=[]
    monkeypatch.setattr(p,'picker_anchor',lambda *a:(0,0))
    monkeypatch.setattr(p,'checkbox_state',lambda *a:'on')
    monkeypatch.setattr(p,'match',lambda *a:((0,0),0))
    monkeypatch.setattr(p,'sleep',lambda seconds:waits.append(seconds))
    picker={'checkbox_offset':(0,0),'next_page_offset':(8,8),'seed_slot_offsets':[(i,100) for i in range(5)]}
    args=([(24,1,1,None),(23,1,1,None),(22,1,1,None)],{i:(i,0) for i in (24,23,22)},picker,
          {'prompt_search_rect':[]},{},{'page-prefix':None,'enable-prompt':None})
    p.plant(lambda point,delay:clicks.append(point),lambda:None,*args)
    assert clicks==[(24,0),(0,100),(23,0),(0,100),(22,0),(0,100)]
    assert waits==[2.8]*3
    clicks.clear()
    def fail_on_second(point,delay):
        clicks.append(point)
        if point==(23,0): raise ValueError('input failed')
    with pytest.raises(ValueError,match='input failed'):
        p.plant(fail_on_second,lambda:None,*args)
    assert clicks==[(24,0),(0,100),(23,0)]
