from pathlib import Path
import json
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def opener(tmp_path_factory):
    binary=tmp_path_factory.mktemp('qq-open-guard')/'opener'
    subprocess.run(['swiftc',str(ROOT/'scripts/open_qq_farm.swift'),'-o',str(binary)],check=True,capture_output=True,timeout=60)
    return binary


def probe(opener, *, change=None, front=42, covering=False, system=False):
    target=dict(id=1,pid=42,owner='QQ',title='QQ',x=100,y=100,width=1200,height=900,layer=0,alpha=1)
    current=dict(target,**(change or {}));windows=[current]
    if covering:windows.insert(0,dict(target,id=9,pid=99,owner='Other'))
    if system:windows.insert(0,dict(target,id=10,pid=50,owner='Dock',layer=20,x=0,y=0,width=2560,height=1440))
    data=dict(target=target,windows=windows,frontPID=front,point=[200,200],display=[0,0,2560,1440])
    r=subprocess.run([str(opener),'--validate-target'],input=json.dumps(data),text=True,capture_output=True,timeout=5)
    return r.returncode,r.stdout.strip()


def test_valid_target_posts_no_input(opener):
    assert probe(opener)==(0,'validated_no_click')
    assert probe(opener,system=True)==(0,'validated_no_click')

@pytest.mark.parametrize('kwargs,reason', [({'front':99},'TARGET_NOT_FRONTMOST'),({'covering':True},'TARGET_OCCLUDED'),({'change':{'pid':99}},'TARGET_IDENTITY_CHANGED'),({'change':{'width':100}},'TARGET_FRAME_CHANGED'),({'change':{'title':'Other'}},'TARGET_IDENTITY_CHANGED')])
def test_target_changes_rejected(opener,kwargs,reason):
    assert probe(opener,**kwargs)==(2,reason)


def test_input_release_validation_posts_no_input(tmp_path):
    binary=tmp_path/'release'
    subprocess.run(['swiftc',str(ROOT/'scripts/farm_release_input.swift'),'-o',str(binary)],check=True,capture_output=True,timeout=60)
    result=subprocess.run([str(binary),'--validate'],capture_output=True,text=True,timeout=5)
    assert result.returncode==0 and result.stdout.strip()=='validated_no_input'



@pytest.mark.parametrize('child_error', ['TARGET_FRAME_CHANGED','TARGET_OCCLUDED','QQ_MAIN_WINDOW_NOT_AT_BASELINE'])
def test_open_failure_preserves_child_reason(monkeypatch,capsys,child_error):
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    import farm_window
    monkeypatch.setattr(sys,'argv',['window','open','--platform','qq','--execute'])
    def run(command,**kwargs):
        if command[0]=='/usr/bin/swift':
            raise subprocess.CalledProcessError(2,command,output='',stderr=child_error+'\n')
        return subprocess.CompletedProcess(command,0,json.dumps({'platform':'qq','windows':[]}),'')
    monkeypatch.setattr(farm_window.subprocess,'run',run)
    assert farm_window.main()==2
    result=json.loads(capsys.readouterr().out)
    assert result['reason']==child_error and result['child_returncode']==2
    assert result['child_stderr']==child_error
