#!/usr/bin/env python3
"""Replay saved local screenshots. Missing or changed evidence is an error, never a skip."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from farm_home_check import HomeRecognizer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    corpus=json.loads((ROOT/'tests/home-screenshot-corpus.json').read_text())
    recognizer=HomeRecognizer(); rows=[]; started=time.monotonic()
    for case in corpus['cases']:
        path=ROOT.parent/case['file']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=case['sha256']:
            raise ValueError(f'SCREENSHOT_MISSING_OR_CHANGED: {path}')
        with Image.open(path) as im:
            result=recognizer.classify(im)
        rows.append({**case,**result,'correct':case['expected_ready']==result['visual_ready']})
    errors=[r for r in rows if not r['correct']]
    summary={'cases':len(rows),'unique_file_hashes':len({r['sha256'] for r in rows}),
             'expected_ready':sum(r['expected_ready'] for r in rows),
             'false_ready':sum(r['visual_ready'] and not r['expected_ready'] for r in rows),
             'false_reject':sum(not r['visual_ready'] and r['expected_ready'] for r in rows),
             'states':dict(Counter(r['state'] for r in rows)),
             'splits':dict(Counter(r['split'] for r in rows)),
             'seconds':round(time.monotonic()-started,3)}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'summary':summary,'label_contract':corpus['label_contract'],'results':rows},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False));print('mismatches:',[(r['index'],r['state']) for r in errors])
    return 1 if errors else 0


if __name__=='__main__':raise SystemExit(main())
