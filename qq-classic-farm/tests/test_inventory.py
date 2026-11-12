from pathlib import Path
import json,sys,copy
import numpy as np
from PIL import Image
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import farm_inventory as inv

@pytest.fixture
def catalog():
    return {'seeds':[{'name':'A','observations':{'qq':{'quantity_latest_known':5},'wechat':{'quantity_latest_known':9}}},
                     {'name':'B','observations':{'qq':{'quantity_latest_known':0}}}],
            'platform_entry_counts':{'qq':2,'wechat':1},'latest_warehouse_scan':{'wechat':{'source':'unchanged'}}}

def obs(entries=None):
    return {'complete':True,'entries':entries or [{'name':'A','quantity':13}],'confirmed_absent_names':[],'reviewed_views':[0]}

def test_increase_overwrites_actual_and_preserves_wechat(catalog):
    out,changes=inv.update_catalog(catalog,obs(),'now')
    assert out['seeds'][0]['observations']['qq']['quantity_latest_known']==13
    assert out['seeds'][0]['observations']['wechat']==catalog['seeds'][0]['observations']['wechat']
    assert changes==[{'name':'A','before':5,'after':13}]
    assert catalog['seeds'][0]['observations']['qq']['quantity_latest_known']==5

def test_known_new_inventory_entry_gets_position(catalog):
    out,changes=inv.update_catalog(catalog,obs([{'name':'A','quantity':5},{'name':'B','quantity':2}]),'now')
    assert out['seeds'][1]['observations']['qq']['latest_warehouse_position']=={'page':1,'slot':2}
    assert changes==[{'name':'B','before':0,'after':2}]

@pytest.mark.parametrize('change,match',[
    (lambda x:x.update(complete=False),'COMPLETE'),
    (lambda x:x['entries'].append({'name':'A','quantity':1}),'DUPLICATE'),
    (lambda x:x['entries'][0].update(quantity=True),'QUANTITY'),
    (lambda x:x['entries'][0].update(quantity=-1),'QUANTITY'),
    (lambda x:x['entries'][0].update(name='unknown'),'UNKNOWN'),
    (lambda x:x.update(entries=[{'name':'B','quantity':1}]),'MISSING'),
])
def test_bad_observations_rejected(catalog,change,match):
    data=obs();change(data)
    with pytest.raises(ValueError,match=match):inv.update_catalog(catalog,data,'now')

def test_scroll_endpoint_ignores_detail_panel_but_not_grid():
    a=Image.fromarray(np.zeros((1111,603,3),dtype=np.uint8))
    b=a.copy();b.paste((255,255,255),(20,770,580,1080))
    assert inv.same_grid(a,b)
    b.paste((255,255,255),(30,300,550,700))
    assert not inv.same_grid(a,b)

@pytest.fixture
def files(tmp_path,catalog,monkeypatch):
    monkeypatch.setattr(inv,'ROOT',tmp_path)
    (tmp_path/'data').mkdir();(tmp_path/'docs').mkdir()
    cp=tmp_path/'data/seed-catalog.json';cp.write_text(json.dumps(catalog))
    (tmp_path/'docs/seed-catalog.md').write_text('header\n### QQ old\nold\n### 微信 keep\nunchanged')
    pending=tmp_path/'data/hamster-inventory-pending.json';pending.write_text(json.dumps({'platform':'qq','status':'legacy_purchase_pending_verification'}))
    image=tmp_path/'view.png';Image.new('RGB',(603,1111)).save(image)
    view={'index':0,'path':str(image),'sha256':inv.digest(image)}
    m=tmp_path/'manifest.json';inv.write_json(m,{'platform':'qq','captured_at':inv.now(),'top_confirmed':True,'bottom_confirmed':True,'warehouse_closed':True,'catalog_sha256_before':inv.digest(cp),'views':[view],'bottom_confirmation':view})
    o=tmp_path/'observations.json';inv.write_json(o,obs())
    return m,o,pending,cp

def test_apply_readback_clear_pending_and_no_double_apply(files):
    m,o,pending,cp=files
    assert inv.apply_inventory(m,o,after_reopen=True)['status']=='inventory_applied'
    assert not pending.exists()
    assert inv.apply_inventory(m,o,after_reopen=True)['status']=='inventory_already_applied'
    assert json.loads(cp.read_text())['seeds'][0]['observations']['qq']['quantity_latest_known']==13

@pytest.mark.parametrize('case',['catalog_changed','image_changed','view_unread','capture_incomplete','reopen_required'])
def test_failed_preconditions_do_not_write(files,case):
    m,o,pending,cp=files
    if case=='catalog_changed':cp.write_text(cp.read_text()+' ')
    elif case=='image_changed':Path(json.loads(m.read_text())['views'][0]['path']).write_bytes(b'changed')
    elif case=='view_unread':data=obs();data['reviewed_views']=[];inv.write_json(o,data)
    elif case=='capture_incomplete':data=json.loads(m.read_text());data['bottom_confirmed']=False;inv.write_json(m,data)
    elif case=='reopen_required':inv.write_json(pending,{'platform':'qq','status':'recheck_order_after_reopen'})
    original=cp.read_bytes()
    with pytest.raises(ValueError):inv.apply_inventory(m,o)
    assert cp.read_bytes()==original and pending.exists()

def test_newly_owned_seed_keeps_reopen_marker(files):
    m,o,pending,cp=files
    inv.write_json(o,obs([{'name':'A','quantity':5},{'name':'B','quantity':2}]))
    assert inv.apply_inventory(m,o)['pending_remaining']
    assert json.loads(pending.read_text())['status']=='recheck_order_after_reopen'


def test_new_seed_obligation_survives_document_write_failure(files,monkeypatch):
    m,o,pending,cp=files
    inv.write_json(o,obs([{'name':'A','quantity':5},{'name':'B','quantity':2}]))
    original=Path.write_text
    def fail_document(self,*args,**kwargs):
        if self.name=='seed-catalog.md':raise OSError('simulated disk failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail_document)
    with pytest.raises(OSError):inv.apply_inventory(m,o)
    assert json.loads(pending.read_text())['status']=='recheck_order_after_reopen'
    assert json.loads(cp.read_text())['seeds'][1]['observations']['qq']['quantity_latest_known']==2
    # A fresh capture can match the partly updated catalog, but cannot clear
    # the obligation without an explicit fresh-mini-program-open confirmation.
    data=json.loads(m.read_text());data['catalog_sha256_before']=inv.digest(cp);inv.write_json(m,data)
    with pytest.raises(ValueError,match='REOPEN_ORDER'):inv.apply_inventory(m,o)
    assert pending.exists()


def test_apply_refuses_another_commit_lock(files):
    import fcntl
    m,o,pending,cp=files
    original=cp.read_bytes()
    with (cp.parent/'.inventory-apply.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='INVENTORY_APPLY_BUSY'):inv.apply_inventory(m,o)
    assert cp.read_bytes()==original and pending.exists()
