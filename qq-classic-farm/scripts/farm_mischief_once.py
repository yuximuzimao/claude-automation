#!/usr/bin/env python3
"""QQ friend grass/bugs, using the user's shared-quota workflow; no automatic retries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

import cv2
import numpy as np
from PIL import Image

from farm_daily_clicks import farm_target, find_point, return_home_point
from farm_fertilize_once import FertilizerStop, capture_region, click_batch
from farm_capture import capture_window
from farm_level_up import dismiss_level_up
from farm_process import run_action, ActionCancelled, ActionCleanupError

ROOT=Path(__file__).resolve().parents[1]


class MenuReader:
    def __init__(self):
        self.templates={n:np.asarray(Image.open(ROOT/f'assets/ui/mischief/qq-{n}.png').convert('RGB'))
                        for n in ('mature','grass','bug','grass-gray','bug-gray','zero-badge')}

    def locate(self,rgb,name):
        template=self.templates[name];best=None
        gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        for scale in (0.9,1.0,1.1):
            t=cv2.resize(template,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
            h,w=t.shape[:2]
            if h>rgb.shape[0] or w>rgb.shape[1]:continue
            _,score,_,(x,y)=cv2.minMaxLoc(cv2.matchTemplate(gray,cv2.cvtColor(t,cv2.COLOR_RGB2GRAY),cv2.TM_CCOEFF_NORMED))
            patch=rgb[y:y+h,x:x+w]
            error=float(np.abs(patch.astype(float)-t).mean())
            # Contours alone cannot distinguish disabled and enabled buttons.
            # Compare their differing pixels, excluding the common background.
            base=name.removesuffix('-gray')
            if base in ('grass','bug'):
                other_name=base if name.endswith('-gray') else base+'-gray'
                other=cv2.resize(self.templates[other_name],(w,h))
                mask=np.max(np.abs(t.astype(float)-other.astype(float)),axis=2)>25
                if not mask.any():continue
                own=float(np.abs(patch.astype(float)-t)[mask].mean())
                alternate=float(np.abs(patch.astype(float)-other)[mask].mean())
                if own+5>=alternate:continue
            # Gray and green icons have almost identical contours; color is mandatory.
            if score>=.86 and error<=22 and (best is None or score>best['score']):
                best={'center':[x+w/2,y+h/2],'box':[x,y,w,h],'score':score,'scale':scale}
        return best

    def read(self,image):
        rgb=np.asarray(image.convert('RGB'))
        if self.locate(rgb,'mature'):
            return {'state':'mature','actions':{}}
        active={name:self.locate(rgb,name) for name in ('grass','bug')}
        gray={name:self.locate(rgb,name+'-gray') for name in ('grass','bug')}
        zeros={}
        for name,icon in gray.items():
            if icon:
                x,y,w,h=icon['box'];scale=icon['scale']
                badge=rgb[max(0,y-round(36*scale)):y+round(2*scale),max(0,x-round(8*scale)):x+w]
                zeros[name]=badge.size>0 and self.locate(badge,'zero-badge') is not None
        if any(gray.values()) and all(zeros.get(k) for k,icon in gray.items() if icon):
            if any(active.values()):return {'state':'unknown','actions':{}}
            return {'state':'exhausted','actions':{},'shared_remaining':0}
        if any(gray.values()):return {'state':'unknown','actions':{}}
        actions={name:hit['center'] for name,hit in active.items() if hit}
        if len(actions)==2:
            g,b=actions['grass'],actions['bug']
            if not (65<=b[0]-g[0]<=130 and abs(g[1]-b[1])<=12):
                return {'state':'unknown','actions':{}}
        return {'state':'actionable' if actions else 'no_actions','actions':actions}


def land_route(layout):
    points=layout['platforms']['qq']['confirmed_land_centers']['points']
    # Serpentine: 24,23,22,21,17,18,19,20,...; every land exactly once.
    return [points[u][v] for row,u in enumerate(range(5,-1,-1))
            for v in (range(3,-1,-1) if row%2==0 else range(4))]


def sweep(click,inspect,drag,go_home,entry,first_visit,next_points,plot24,progress,limit=100,after_gesture=lambda: None):
    click(entry,650);click(first_visit,850)
    last_menu=None
    for index in range(limit):
        progress['friend_visit']=index+1
        progress['stage']='inspect_plot24'
        click(plot24,650);menu=inspect();last_menu=menu
        if menu['state']=='exhausted':
            go_home();return 'shared_quota_exhausted'
        if menu['state']=='unknown':raise ValueError('AMBIGUOUS_ACTION_MENU')
        if menu['state']=='actionable':
            # Prefer grass. If it is absent but bugs are available, use bugs once.
            if 'grass' in menu['actions']:
                progress['stage']='drag_grass';drag(menu['actions']['grass']);progress['grass_gestures']+=1
                after_gesture()
                progress['stage']='inspect_after_grass';click(plot24,650);menu=inspect();last_menu=menu
                if menu['state']=='exhausted':go_home();return 'shared_quota_exhausted'
                if menu['state']=='unknown':raise ValueError('AMBIGUOUS_ACTION_MENU')
            if menu['state']=='actionable' and 'bug' in menu['actions']:
                progress['stage']='drag_bugs';drag(menu['actions']['bug']);progress['bug_gestures']+=1
                after_gesture()
                progress['stage']='inspect_after_bugs';click(plot24,650);last_menu=inspect()
                if last_menu['state']=='exhausted':go_home();return 'shared_quota_exhausted'
                if last_menu['state']=='unknown':raise ValueError('AMBIGUOUS_ACTION_MENU')
        # A mature crop, missing operation bar, or a completed friend's gestures moves on.
        if index+1<limit:
            progress['stage']='next_friend';click(next_points[min(index,2)],850)
    go_home();return 'visit_limit_without_zero_confirmation'


def drag_once(helper, payload):
    # run_action reaps the process group before verified release on every
    # abnormal exit, timeout or SIGINT/SIGTERM; never replay a partial gesture.
    r = run_action([str(helper), '--execute'], input=json.dumps(payload), timeout=20)
    reply = json.loads(r.stdout)
    if r.returncode or reply.get('status') != 'path_drag_sent_unverified':
        raise ValueError(reply.get('reason', 'DRAG_FAILED_PARTIAL_UNCERTAIN'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--execute',action='store_true')
    modes.add_argument('--image',type=Path,help='Recognize a saved crop or window; never input.')
    parser.add_argument('--max-visits',type=int,default=100, help='Safety bound on friends, not action quota; normal runs continue until visible disabled counters show zero.')
    args=parser.parse_args()
    progress={'stage':'prepare','friend_visit':0,'grass_gestures':0,'bug_gestures':0}
    try:
        if not 1<=args.max_visits<=100:raise ValueError('INVALID_VISIT_LIMIT')
        reader=MenuReader()
        if args.image:
            with Image.open(args.image) as image:result=reader.read(image)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['state']!='unknown' else 2
        layout=json.loads((ROOT/'data/ui-layout.json').read_text());path=land_route(layout)
        if not args.execute:
            print(json.dumps({'status':'plan_ok_no_input','shared_quota':100,'land_route':path,
                              'flow':'friends → first visit → plot24 → skip mature → grass drag → inspect → bug drag if available → next friend; single or double gray zero → home',
                              'max_visits':args.max_visits},ensure_ascii=False));return 0
        from farm_home_check import HomeRecognizer,live_check
        if not live_check(HomeRecognizer(),ROOT/'_sandbox/farm_home_window')['ready_for_input']:
            raise ValueError('HOME_NOT_READY')
        fixed=json.loads((ROOT/'data/ui-anchors.json').read_text())['fixed_points'];scenes=fixed['scenes']
        nav=scenes['friend-farm-navigation']['views']
        next_points=[find_point(nav['first']['points'],'qq',n) for n in ('second-friend','third-friend')]
        next_points.append(find_point(nav['next']['points'],'qq','fourth-onward'))
        frame,target=farm_target(ROOT/'_sandbox/farm_window_registry','qq',layout)
        def click(point,delay):
            click_batch(ROOT/'_sandbox/farm_click_batch','--execute',target,[{'x':point[0],'y':point[1],'delay_ms':delay}], managed=True)
        def inspect():
            image=Image.fromarray(capture_window(frame,'qq',layout).rgb).resize((603,1111))
            # All supplied panels are below the upper fixed UI and above the friend strip.
            result=reader.read(image.crop((0,350,603,940)))
            for point in result['actions'].values():point[1]+=350
            return result
        def drag(point):
            payload={**target,'points':[point,*path]};payload.pop('window_frame',None)
            helper=ROOT/'_sandbox/farm_path_drag'
            drag_once(helper, payload)
            sleep(.7)
        def home():click(return_home_point(frame,'qq',layout),800)
        reason=sweep(click,inspect,drag,home,find_point(fixed['home']['points'],'qq','friends'),
                     find_point(scenes['friend-list']['views']['first-visit']['points'],'qq','first-visit'),
                     next_points,path[0],progress,args.max_visits,
                     after_gesture=lambda: dismiss_level_up(lambda rect: capture_region(target['frame'], rect), click))
        print(json.dumps({'status':'completed' if reason=='shared_quota_exhausted' else 'stopped_returned_home','reason':reason,'shared_remaining':0 if reason=='shared_quota_exhausted' else None,**progress},ensure_ascii=False))
        return 0 if reason=='shared_quota_exhausted' else 2
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,FertilizerStop,ActionCancelled,ActionCleanupError) as exc:
        print(json.dumps({'status':'stopped','reason':str(exc),**progress},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
