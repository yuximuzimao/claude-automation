"""Home gate boundary tests: no native helper or desktop capture is executed."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from PIL import Image
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import farm_home_check as home
import farm_capture


@pytest.mark.parametrize('size',[(43,132),(603,1100),(625,1155),(2560,1440)])
def test_rejects_thumbnail_wrong_platform_and_clipped_image(size):
    result=home.HomeRecognizer().classify(Image.new('RGB',size,'white'))
    assert result['state']=='invalid_image_size'
    assert result['visual_ready'] is False


def test_blank_cannot_pass_as_home():
    r=home.HomeRecognizer().classify(Image.new('RGB',(603,1111),'white'))
    assert r['state']=='loading_or_blank'
    assert r['visual_ready'] is False


def window(x=100):
    return {'state':'window_ready','window_id':20,'pid':30,'owner':'QQ小程序',
            'title':'QQ经典农场','frame':{'x':x,'y':200,'width':603,'height':1111}}


def install_probe(monkeypatch,replies):
    calls=[];replies=iter(replies)
    def run(command,**kwargs):
        calls.append(command)
        payload=next(replies)
        return SimpleNamespace(returncode=0 if payload['state']=='window_ready' else 2,stdout=json.dumps(payload))
    monkeypatch.setattr(home.subprocess,'run',run)
    return calls


@pytest.mark.parametrize('state',['farm_not_found','farm_not_unique','farm_not_frontmost','window_occluded','nonstandard_window','activation_failed'])
def test_bad_window_never_captures_or_classifies(monkeypatch,state):
    install_probe(monkeypatch,[{'state':state}])
    monkeypatch.setattr(farm_capture,'capture_window',lambda *a:pytest.fail('capture must not run'))
    recognizer=Mock()
    with pytest.raises(ValueError,match=state): home.live_check(recognizer,'helper')
    recognizer.classify.assert_not_called()


def test_rejects_window_change_between_capture_and_decision(monkeypatch):
    install_probe(monkeypatch,[window(),window(101)])
    monkeypatch.setattr(farm_capture,'capture_window',lambda *a:SimpleNamespace(rgb=np.zeros((1111,603,3),dtype=np.uint8)))
    recognizer=Mock()
    with pytest.raises(ValueError,match='window_changed'):home.live_check(recognizer,'helper')
    recognizer.classify.assert_not_called()


@pytest.mark.parametrize('visual_ready',[True,False])
def test_prepare_is_explicit_and_requires_visual_acceptance(monkeypatch,visual_ready):
    calls=install_probe(monkeypatch,[window(),window()])
    monkeypatch.setattr(farm_capture,'capture_window',lambda *a:SimpleNamespace(rgb=np.zeros((1111,603,3),dtype=np.uint8)))
    recognizer=Mock();recognizer.classify.return_value={'visual_ready':visual_ready,'state':'home' if visual_ready else 'overlay'}
    r=home.live_check(recognizer,'helper',prepare=True)
    assert calls==[['helper','--prepare'],['helper','--check']]
    assert r['ready_for_input'] is visual_ready


def test_offline_never_sets_live_permission(monkeypatch,tmp_path,capsys):
    image=tmp_path/'image.png';Image.new('RGB',(603,1111)).save(image)
    monkeypatch.setattr(sys,'argv',['home','--image',str(image)])
    monkeypatch.setattr(home.HomeRecognizer,'classify',lambda *a:{'visual_ready':True,'state':'home'})
    monkeypatch.setattr(home.subprocess,'run',lambda *a,**k:pytest.fail('offline must not touch native tools'))
    assert home.main()==0
    assert json.loads(capsys.readouterr().out)['ready_for_input'] is False
