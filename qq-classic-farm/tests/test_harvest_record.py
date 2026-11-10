"""Offline contracts: reject before fertilizer, and fixed clicks need no star image."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import farm_harvest_once as harvest
import farm_qq_round as round_script


@pytest.fixture
def record(tmp_path):
    # A completed batch, independent of the next planting plan/picker changes.
    j = json.loads((ROOT / 'data/operation-plan.json').read_text())
    path = tmp_path / 'planted.json'
    path.write_text(json.dumps(j))
    return path


def validate(path, **kwargs):
    return harvest.validate_planted_plan(path, 'qq',
        json.loads((ROOT/'data/ui-layout.json').read_text()),
        json.loads((ROOT/'data/ui-anchors.json').read_text()), **kwargs)


@pytest.mark.parametrize('change', [
    lambda j: j.pop('wechat'),
    lambda j: j['qq']['planting']['special'][0].pop('plot'),
    lambda j: j['qq']['planting']['special'][0].pop('seed_name'),
    lambda j: j['qq']['planting']['special'][0].update(seed_name=' '),
    lambda j: j['qq']['planting']['special'][0].update(quantity=2),
    lambda j: j['qq']['planting']['ordinary'].update(quantity=True),
    lambda j: j['qq']['planting']['ordinary'].update(quantity=19),
    lambda j: j['qq']['planting']['special'].append(copy.deepcopy(j['qq']['planting']['special'][0])),
    lambda j: j['qq']['planting']['special'][0].update(plot=7),
    lambda j: j['qq']['daily'].update(tasks=1),
    lambda j: j.update(unexpected=True),
])
def test_bad_record_stops_round_before_any_subprocess(record, change, monkeypatch, capsys):
    j=json.loads(record.read_text());change(j);record.write_text(json.dumps(j))
    monkeypatch.setattr(sys, 'argv', ['round', '--field-state', 'tail', '--harvest-plan', str(record), '--execute'])
    def forbidden(*a, **kw):
        pytest.fail('invalid record reached a window/side-effect process')
    monkeypatch.setattr(round_script.subprocess, 'run', forbidden)
    assert round_script.main() == 2
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='rejected_rewrite_required'
    assert result['completed_stages']==[]


@pytest.mark.parametrize('path', [None, ROOT/'data/operation-plan.json'])
def test_missing_or_next_plan_rejected(path):
    with pytest.raises(ValueError): validate(path)


def test_malformed_json_rejected(record):
    record.write_text('{')
    with pytest.raises(ValueError): validate(record)


def test_valid_record_offline_without_window(record, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['harvest', '--platform', 'qq', '--planted-plan', str(record), '--check-plan'])
    monkeypatch.setattr(harvest, 'farm_target', lambda *a: pytest.fail('offline check opened window'))
    assert harvest.main()==0
    assert json.loads(capsys.readouterr().out)['special_points']==[[338,535]]


def test_fixed_star_click_only_after_maturity_then_hand(record, monkeypatch):
    argv=['harvest','--platform','qq','--planted-plan',str(record),'--execute']
    monkeypatch.setattr(sys,'argv',argv)
    monkeypatch.setattr(harvest,'farm_target',lambda *a: pytest.fail('missing maturity accessed window'))
    assert harvest.main()==2
    argv.append('--mature-confirmed')
    monkeypatch.setattr(harvest,'farm_target',lambda *a:(None,{'frame':{}}))
    monkeypatch.setattr(harvest,'capture_region',lambda *a: pytest.fail('star image captured'))
    monkeypatch.setattr(harvest,'hand_point',lambda *a:((297,825),.95))
    clicks=[]
    monkeypatch.setattr(harvest,'click_batch',lambda helper,mode,target,actions:clicks.extend(actions))
    monkeypatch.setattr(harvest,'sleep',lambda _:None)
    assert harvest.main()==0
    assert [(a['x'],a['y']) for a in clicks]==[(338,535),(297,825)]


def test_failed_fertilizer_never_reaches_fixed_harvest(record, monkeypatch):
    monkeypatch.setattr(sys,'argv',['round','--field-state','tail','--harvest-plan',str(record),'--execute'])
    calls=[]
    def fail(command, **kw):
        calls.append(command)
        return SimpleNamespace(returncode=2,stdout='stopped',stderr='')
    monkeypatch.setattr(round_script.subprocess,'run',fail)
    assert round_script.main()==2
    assert len(calls)==1 and 'farm_fertilize_once.py' in calls[0][1]


def test_successful_tail_waits_then_harvests(record,monkeypatch):
    monkeypatch.setattr(sys,'argv',['round','--field-state','tail','--harvest-plan',str(record),'--execute'])
    events=[]
    def success(command, **kw):
        events.append(Path(command[1]).name)
        if 'farm_harvest_once.py' in command[1]: assert '--mature-confirmed' in command
        return SimpleNamespace(returncode=0,stdout='ok',stderr='')
    monkeypatch.setattr(round_script.subprocess,'run',success)
    monkeypatch.setattr(round_script,'sleep',lambda seconds:events.append(seconds))
    assert round_script.main()==0
    assert events==['farm_fertilize_once.py',2.2,'farm_harvest_once.py','farm_plant_once.py']


def test_write_time_check_rejects_incomplete_full_field(record, monkeypatch, capsys):
    j=json.loads(record.read_text())
    j['qq']['planting']['ordinary']['quantity']=19
    record.write_text(json.dumps(j))
    monkeypatch.setattr(sys,'argv',['harvest','--platform','qq','--planted-plan',str(record),'--check-plan'])
    monkeypatch.setattr(harvest,'farm_target',lambda *a:pytest.fail('write-time validation accessed window'))
    assert harvest.main()==2
    assert json.loads(capsys.readouterr().out)['status']=='rejected_rewrite_required'
