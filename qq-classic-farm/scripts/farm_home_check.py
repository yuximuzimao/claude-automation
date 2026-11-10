#!/usr/bin/env python3
"""Conservative QQ home recognition. Offline images never authorize live input."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'data/home-recognition.json'


class HomeRecognizer:
    def __init__(self):
        self.config = json.loads(CONFIG.read_text())
        self.templates = [(s, np.asarray(Image.open(ROOT / s['path']).convert('RGB'))) for s in self.config['templates']]

    def classify(self, image):
        if image.size not in ((603,1111), (1206,2222)):
            return {'visual_ready': False, 'state': 'invalid_image_size', 'size': list(image.size)}
        rgb = np.asarray(image.convert('RGB').resize((603,1111), Image.Resampling.LANCZOS))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        results = {}
        for spec, template in self.templates:
            x0,y0,x1,y1 = spec['roi']
            tgray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
            scores = cv2.matchTemplate(gray[y0:y1,x0:x1],tgray,cv2.TM_CCOEFF_NORMED)
            _,score,_,(x,y) = cv2.minMaxLoc(scores)
            h,w = tgray.shape
            patch = rgb[y0+y:y0+y+h,x0+x:x0+x+w]
            error = float(np.abs(patch.astype(float)-template).mean())
            # NCC alone accepts a darkened page behind a modal; raw color rejects it.
            results[spec['id']] = {'matched':score>=spec.get('threshold',0.90) and error<=24,
                                    'position':[x0+x,y0+y],
                                    'score':round(score,4),'color_error':round(error,2)}
        hits = lambda kind: [s['id'] for s,_ in self.templates if s['kind']==kind and results[s['id']]['matched']]
        misaligned = [s['id'] for s,_ in self.templates if 'alignment_tolerance' in s
                      and results[s['id']]['matched']
                      and max(abs(a-b) for a,b in zip(results[s['id']]['position'],s['source_rect'][:2]))>s['alignment_tolerance']]
        missing = [s['id'] for s,_ in self.templates if s['kind']=='home' and not results[s['id']]['matched']]
        blockers = hits('overlay')
        if blockers:
            state = 'overlay'
        elif hits('friend'):
            state = 'friend_farm'
        elif hits('non_home'):
            state = 'non_home'
        elif misaligned:
            state = 'scene_misaligned'
        elif not missing:
            state = 'home'
        elif float(np.mean(np.min(rgb[40:],axis=2)>240)) > .96:
            state = 'loading_or_blank'
        else:
            state = 'unknown_or_non_home'
        return {'visual_ready':state=='home','state':state,'missing_home_features':missing,
                'blockers':blockers,'misaligned':misaligned,'features':results}


def live_check(recognizer, helper, prepare=False):
    from farm_capture import capture_window
    from farm_geometry import WindowFrame
    def probe(mode):
        p = subprocess.run([str(helper),mode],capture_output=True,text=True,timeout=10)
        result = json.loads(p.stdout)
        if p.returncode or result.get('state') != 'window_ready':
            raise ValueError(result.get('state','window_probe_failed'))
        return result
    before = probe('--prepare' if prepare else '--check')
    frame = WindowFrame(before['owner'],before['title'],**before['frame'])
    layout = json.loads((ROOT/'data/ui-layout.json').read_text())
    capture = capture_window(frame,'qq',layout)
    after = probe('--check')
    if before != after:
        raise ValueError('window_changed_during_capture')
    result = recognizer.classify(Image.fromarray(capture.rgb))
    return {'mode':'live','ready_for_input':result['visual_ready'],**result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--image',type=Path)
    mode.add_argument('--live',action='store_true',help='Read current window and capture once; no game input.')
    parser.add_argument('--prepare',action='store_true',help='With --live, activate the existing farm and wait 5 seconds.')
    parser.add_argument('--window-helper',type=Path,default=ROOT/'_sandbox/farm_home_window')
    args=parser.parse_args()
    if args.prepare and not args.live:
        parser.error('--prepare requires --live')
    try:
        recognizer=HomeRecognizer()
        if args.live:
            result=live_check(recognizer,args.window_helper,args.prepare)
        else:
            with Image.open(args.image) as im:
                result={'mode':'offline','ready_for_input':False,**recognizer.classify(im)}
        print(json.dumps(result,ensure_ascii=False))
        return 0 if result['visual_ready'] else 2
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print(json.dumps({'mode':'live' if args.live else 'offline','ready_for_input':False,
                          'visual_ready':False,'state':'error','reason':str(exc)}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
