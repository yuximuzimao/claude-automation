#!/usr/bin/env python3
"""Guarded QQ inventory capture; Agent reads images, then applies explicit observations."""
from __future__ import annotations
import argparse, copy, fcntl, hashlib, json, re, subprocess, tempfile
from datetime import datetime
from pathlib import Path
from time import sleep
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image
from farm_capture import capture_window
from farm_daily_clicks import farm_target, find_point
from farm_fertilize_once import click_batch, FertilizerStop
from farm_home_check import HomeRecognizer, live_check
ROOT=Path(__file__).resolve().parents[1]
GRID=(24,294,580,738)
REGIONS={'qq-title.png':(230,100,375,155),'qq-seed-tab.png':(310,175,430,226)}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,suffix='.tmp',delete=False) as f:
        temp=Path(f.name);json.dump(value,f,ensure_ascii=False,indent=2)
    try:temp.replace(path)
    finally:temp.unlink(missing_ok=True)
    if json.loads(path.read_text())!=value:raise ValueError('JSON_READBACK_FAILED')

def same_grid(a,b):
    delta=np.abs(np.asarray(a.crop(GRID),dtype=np.int16)-np.asarray(b.crop(GRID),dtype=np.int16))
    return float(delta.mean())<2 and float((delta.max(axis=2)>18).mean())<.02

def checked_image(layout):
    def probe():
        p=subprocess.run([str(ROOT/'_sandbox/farm_home_window'),'--check'],capture_output=True,text=True,timeout=10,check=True)
        return json.loads(p.stdout)
    before=probe();frame,target=farm_target(ROOT/'_sandbox/farm_window_registry','qq',layout)
    shot=capture_window(frame,'qq',layout)
    if probe()!=before:raise ValueError('WINDOW_CHANGED_DURING_CAPTURE')
    image=Image.fromarray(shot.rgb).resize((603,1111))
    for name,rect in REGIONS.items():
        expected=np.asarray(Image.open(ROOT/'assets/ui/warehouse'/name).convert('RGB'),dtype=np.int16)
        actual=np.asarray(image.crop(rect),dtype=np.int16)
        if actual.shape!=expected.shape or np.abs(actual-expected).mean()>8:
            raise ValueError('WAREHOUSE_SEED_PAGE_NOT_CONFIRMED: '+name)
    return image,target

def click_point(target,point):
    click_batch(ROOT/'_sandbox/farm_click_batch','--execute',target,[{'x':point[0],'y':point[1],'delay_ms':650}])

def scroll(target,direction):
    payload={k:target[k] for k in ('window_id','pid','owner','title','frame')}
    payload.update(from_x=302,from_y=330 if direction=='top' else 680,to_x=302,to_y=680 if direction=='top' else 330,steps=20)
    p=subprocess.run([str(ROOT/'_sandbox/farm_drag'),'--execute'],input=json.dumps(payload),capture_output=True,text=True,timeout=8)
    if p.returncode or json.loads(p.stdout).get('status')!='drag_sent_unverified':
        raise ValueError('WAREHOUSE_SCROLL_FAILED: '+(p.stdout or p.stderr))
    sleep(.8)

def capture_inventory(folder,already_open=False):
    folder.mkdir(parents=True,exist_ok=False)
    layout=json.loads((ROOT/'data/ui-layout.json').read_text())
    fixed=json.loads((ROOT/'data/ui-anchors.json').read_text())['fixed_points']
    before_hash=digest(ROOT/'data/seed-catalog.json')
    if not already_open:
        if not live_check(HomeRecognizer(),ROOT/'_sandbox/farm_home_window',prepare=True)['ready_for_input']:
            raise ValueError('HOME_NOT_READY')
        _,target=farm_target(ROOT/'_sandbox/farm_window_registry','qq',layout)
        click_point(target,find_point(fixed['home']['points'],'qq','warehouse'))
        click_point(target,find_point(fixed['scenes']['warehouse']['points'],'qq','seed'))
    image,target=checked_image(layout)
    # Only successful bounded scrolling is repeated; a failed input stops immediately.
    for _ in range(12):
        scroll(target,'top');next_image,target=checked_image(layout)
        if same_grid(image,next_image):image=next_image;break
        image=next_image
    else:raise ValueError('WAREHOUSE_TOP_NOT_REACHED')
    views=[]
    for index in range(20):
        path=folder/f'view-{index:02d}.png';image.save(path)
        views.append({'index':index,'path':str(path.resolve()),'sha256':digest(path)})
        scroll(target,'bottom');next_image,target=checked_image(layout)
        if same_grid(image,next_image):
            end=folder/'bottom-confirm.png';next_image.save(end);break
        image=next_image
    else:raise ValueError('WAREHOUSE_BOTTOM_NOT_REACHED')
    click_point(target,find_point(fixed['scenes']['warehouse']['points'],'qq','close'))
    if not live_check(HomeRecognizer(),ROOT/'_sandbox/farm_home_window')['ready_for_input']:
        raise ValueError('WAREHOUSE_CLOSE_NOT_HOME')
    manifest={'version':1,'platform':'qq','captured_at':now(),'top_confirmed':True,'bottom_confirmed':True,
              'warehouse_closed':True,'catalog_sha256_before':before_hash,'views':views,
              'bottom_confirmation':{'path':str(end.resolve()),'sha256':digest(end)}}
    path=folder/'manifest.json';write_json(path,manifest)
    return {'status':'inventory_capture_complete','manifest':str(path.resolve()),'views':views,'warehouse_closed':True,
            'next':'Read every image with view_image, deduplicate overlap, write observations JSON, then apply.'}

def update_catalog(catalog,observations,stamp):
    if observations.get('complete') is not True:raise ValueError('COMPLETE_OBSERVATIONS_REQUIRED')
    entries=observations.get('entries')
    if not isinstance(entries,list) or not entries:raise ValueError('NONEMPTY_ENTRIES_REQUIRED')
    names=[]
    for row in entries:
        if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip():raise ValueError('INVALID_SEED_NAME')
        if type(row.get('quantity')) is not int or row['quantity']<=0:raise ValueError('INVALID_SEED_QUANTITY')
        names.append(row['name'])
    if len(names)!=len(set(names)):raise ValueError('DUPLICATE_SEED_NAME_DEDUPLICATE_OVERLAP')
    result=copy.deepcopy(catalog);by_name={s['name']:s for s in result['seeds']}
    unknown=set(names)-set(by_name)
    if unknown:raise ValueError('UNKNOWN_SEED_NEEDS_CATALOG_ENTRY: '+', '.join(sorted(unknown)))
    previous={s['name']:s['observations']['qq']['quantity_latest_known'] for s in catalog['seeds'] if s.get('observations',{}).get('qq',{}).get('quantity_latest_known',0)>0}
    missing=set(previous)-set(names)
    if set(observations.get('confirmed_absent_names',[]))!=missing:raise ValueError('MISSING_KNOWN_SEEDS_REQUIRE_EXPLICIT_ABSENCE_CONFIRMATION')
    changes=[]
    for name in missing:
        item=by_name[name]['observations']['qq'];changes.append({'name':name,'before':previous[name],'after':0})
        item.update(quantity_latest_known=0,quantity_latest_known_at=stamp,quantity_confidence='verified',quantity_latest_known_basis='Absent from complete live warehouse capture')
    for i,row in enumerate(entries):
        item=by_name[row['name']].setdefault('observations',{}).setdefault('qq',{'platform':'qq','name':row['name']})
        old=item.get('quantity_latest_known',0)
        if old!=row['quantity']:changes.append({'name':row['name'],'before':old,'after':row['quantity']})
        item.update(quantity_latest_known=row['quantity'],quantity_latest_known_at=stamp,quantity_confidence='verified',
                    quantity_latest_known_basis='Complete live warehouse capture and Agent image reading',latest_warehouse_position={'page':i//5+1,'slot':i%5+1})
    result.setdefault('latest_warehouse_scan',{})['qq']={'completed_at':stamp,'in_stock_entries':len(entries),'total_quantity':sum(e['quantity'] for e in entries),'source':'farm_inventory capture with Agent verified observations'}
    result['platform_entry_counts']['qq']=sum('qq' in s.get('observations',{}) for s in result['seeds'])
    return result,changes

def update_markdown(text,entries,stamp):
    text=re.sub(r'QQ：最近一次完整仓库读取为 [^。]+。', f'QQ：最近一次完整仓库读取为 {stamp}。', text, count=1)
    a=text.index('### QQ');b=text.index('### 微信',a)
    lines=[f"### QQ · {len(entries)} 种，{sum(e['quantity'] for e in entries):,} 颗",'',
           f'{stamp} 完整仓库种子页现场读取并核对数量与顺序；盘点不执行收种动作。','',
           '| 页码 | 槽 1 | 槽 2 | 槽 3 | 槽 4 | 槽 5 |','| --- | --- | --- | --- | --- | --- |']
    for i in range(0,len(entries),5):
        row=[f"{e['name'].removesuffix('种子')} {e['quantity']}" for e in entries[i:i+5]];row+=['—']*(5-len(row))
        lines.append('| '+str(i//5+1)+' | '+' | '.join(row)+' |')
    return text[:a]+'\n'.join(lines)+'\n\n'+text[b:]

def apply_inventory(manifest_path,observations_path,after_reopen=False):
    # Local file commit lock only; not a desktop scheduler or a retry loop.
    lock_path=ROOT/'data/.inventory-apply.lock'
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('INVENTORY_APPLY_BUSY')
        return _apply_inventory(manifest_path,observations_path,after_reopen)


def _apply_inventory(manifest_path,observations_path,after_reopen=False):
    manifest=json.loads(manifest_path.read_text());observations=json.loads(observations_path.read_text())
    if manifest.get('platform')!='qq' or not all(manifest.get(k) is True for k in ('top_confirmed','bottom_confirmed','warehouse_closed')):raise ValueError('INCOMPLETE_CAPTURE_MANIFEST')
    age=datetime.now(ZoneInfo('Asia/Shanghai'))-datetime.fromisoformat(manifest['captured_at'])
    if not 0<=age.total_seconds()<=3600:raise ValueError('CAPTURE_TOO_OLD_RECAPTURE_REQUIRED')
    for view in [*manifest['views'],manifest['bottom_confirmation']]:
        if digest(Path(view['path']))!=view['sha256']:raise ValueError('CAPTURE_IMAGE_CHANGED')
    if sorted(observations.get('reviewed_views',[]))!=list(range(len(manifest['views']))):raise ValueError('EVERY_VIEW_MUST_BE_REVIEWED')
    catalog_path=ROOT/'data/seed-catalog.json';doc_path=ROOT/'docs/seed-catalog.md';pending=ROOT/'data/hamster-inventory-pending.json'
    if manifest.get('applied_catalog_sha256'):
        if digest(catalog_path)==manifest['applied_catalog_sha256'] and digest(observations_path)==manifest.get('applied_observations_sha256'):return {'status':'inventory_already_applied','manifest':str(manifest_path)}
        raise ValueError('CATALOG_CHANGED_AFTER_APPLY')
    if digest(catalog_path)!=manifest['catalog_sha256_before']:raise ValueError('CATALOG_CHANGED_SINCE_CAPTURE')
    state=json.loads(pending.read_text()) if pending.exists() else None
    if state and state.get('platform')!='qq':raise ValueError('PENDING_PLATFORM_MISMATCH')
    if state and state.get('status')=='recheck_order_after_reopen' and not after_reopen:raise ValueError('REOPEN_ORDER_CONFIRMATION_REQUIRED')
    catalog=json.loads(catalog_path.read_text());updated,changes=update_catalog(catalog,observations,manifest['captured_at'])
    document=update_markdown(doc_path.read_text(),observations['entries'],manifest['captured_at'])
    added=[c['name'] for c in changes if c['before']==0 and c['after']>0]
    # Persist the re-open obligation BEFORE quantities become positive. If a
    # later write fails, recapturing must not erase the fact that a new seed arrived.
    if added and not after_reopen:
        write_json(pending,{'platform':'qq','status':'recheck_order_after_reopen','new_seed_names':added,'at':now()})
    write_json(catalog_path,updated);doc_path.write_text(document)
    if doc_path.read_text()!=document:raise ValueError('MARKDOWN_READBACK_FAILED')
    if (not added or after_reopen) and pending.exists():pending.unlink()
    manifest.update(applied_at=now(),applied_catalog_sha256=digest(catalog_path),applied_observations_sha256=digest(observations_path),changes=changes);write_json(manifest_path,manifest)
    return {'status':'inventory_applied','changes':changes,'entries':len(observations['entries']),
            'total_quantity':sum(e['quantity'] for e in observations['entries']),'pending_remaining':pending.exists()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('capture','apply'))
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--already-open',action='store_true',help='Explicitly start from the verified seed warehouse.')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--observations',type=Path)
    parser.add_argument('--after-reopen',action='store_true',help='Caller confirms capture followed a fresh mini-program open.')
    args=parser.parse_args()
    if not args.execute:print(json.dumps({'status':'plan_ok_no_input','action':args.action}));return 0
    try:
        if args.action=='capture':
            folder=args.output_dir or ROOT.parent/'_sandbox'/('qq-inventory-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            result=capture_inventory(folder,args.already_open)
        else:
            if args.manifest is None or args.observations is None:raise ValueError('MANIFEST_AND_OBSERVATIONS_REQUIRED')
            result=apply_inventory(args.manifest,args.observations,args.after_reopen)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,FertilizerStop) as exc:
        print(json.dumps({'status':'stopped','action':args.action,'reason':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
