#!/usr/bin/env python3
"""QQ: share with the configured contact, claim the reward, then return to the field."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from farm_daily_clicks import farm_target, find_point
from farm_fertilize_once import FertilizerStop, click_batch

ROOT = Path(__file__).resolve().parents[1]


def share_steps(anchors):
    share = anchors['scenes']['share']
    views = share['views']
    point = lambda view, name: find_point(views[view]['points'], 'qq', name)
    return [
        ('open_share', 'farm', find_point(anchors['home']['points'], 'qq', 'share'), 650),
        ('open_selector', 'farm', point('share-page', 'open-selector'), 1000),
        ('type_nickname', 'text', point('contact-list', 'search'), 1000),
        ('select_result', 'selector', point('search-result', 'result'), 350),
        ('send', 'selector', point('selected', 'send'), 1000),
        ('return_farm', 'activate', None, 0),
        ('claim', 'farm', point('share-page', 'open-selector'), 950),
        ('dismiss_reward', 'farm', find_point(anchors['scenes']['mall-welfare']['views']['reward']['points'], 'qq', 'dismiss-blank'), 350),
        ('close_share', 'farm', point('share-page', 'close'), 350),
    ]


def selector_target(windows, previous_ids):
    matches = [w for w in windows if w['owner'] == 'QQ'
               and (w['width'], w['height']) == (600, 600)
               and w['window_id'] not in previous_ids]
    if len(matches) != 1:
        raise ValueError('NEW_QQ_SHARE_SELECTOR_NOT_UNIQUE')
    window = matches[0]
    target = {key: window[key] for key in ('window_id', 'pid', 'owner', 'title')}
    target['frame'] = {key: window[key] for key in ('x', 'y', 'width', 'height')}
    return target


def send_text(helper, target, point, text, delay):
    result = subprocess.run([str(helper), '--execute', '--qq-share-text'],
                            input=json.dumps({**target, 'text': text, 'actions': [
                                {'x': point[0], 'y': point[1], 'delay_ms': delay}]}),
                            text=True, capture_output=True, timeout=5)
    reply = json.loads(result.stdout)
    if result.returncode or reply.get('status') != 'text_sent_unverified' or reply.get('click_count') != 0:
        raise FertilizerStop(reply.get('code', 'SHARE_TEXT_INPUT_FAILED'))


def run_share(steps, nickname, farm, windows, click, type_text, return_farm, progress):
    # Bind the newly opened selector, never a pre-existing QQ chat window.
    previous_ids = {w['window_id'] for w in windows()}
    selector = None
    for name, kind, point, delay in steps:
        progress['stage'] = name
        if kind == 'activate':
            if any(w['window_id'] == selector['window_id'] for w in windows()):
                raise ValueError('SHARE_SELECTOR_STILL_OPEN_AFTER_SEND')
            farm = return_farm(farm)
        elif kind == 'text':
            selector = selector_target(windows(), previous_ids)
            type_text(selector, point, nickname, delay)
        else:
            if name == 'send':
                # A tool failure can occur after posting the click: never auto-resend.
                progress['send_attempted'] = True
            click(farm if kind == 'farm' else selector, point, delay, kind == 'selector')
        progress['completed_steps'].append(name)



def restore_farm(original, registry, layout):
    # Activate only the original farm process; Stage Manager may have reduced its window.
    code = r"""
import AppKit
import CoreGraphics
let pid = Int32(CommandLine.arguments[1])!
let wid = Int(CommandLine.arguments[2])!
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
guard list.contains(where: {
    ($0[kCGWindowNumber as String] as? Int) == wid &&
    ($0[kCGWindowOwnerPID as String] as? Int32) == pid &&
    ($0[kCGWindowOwnerName as String] as? String) == "QQ小程序" &&
    ($0[kCGWindowName as String] as? String) == "QQ经典农场"
}), let app = NSRunningApplication(processIdentifier: pid), app.localizedName == "QQ小程序" else { exit(2) }
guard app.activate(options: [.activateAllWindows]) else { exit(3) }
Thread.sleep(forTimeInterval: 0.8)
guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else { exit(4) }
"""
    subprocess.run(['/usr/bin/swift', '-e', code, str(original['pid']), str(original['window_id'])],
                   capture_output=True, text=True, check=True, timeout=15)
    _, current = farm_target(registry, 'qq', layout)
    if any(current[key] != original[key] for key in ('window_id', 'pid', 'owner', 'title')):
        raise ValueError('FARM_IDENTITY_CHANGED_AFTER_SHARE')
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Send one share. Default prints the plan without input or window access.')
    parser.add_argument('--registry', type=Path, default=ROOT / '_sandbox/farm_window_registry')
    parser.add_argument('--click-helper', type=Path, default=ROOT / '_sandbox/farm_click_batch')
    args = parser.parse_args()
    progress = {'stage': 'prepare', 'completed_steps': [], 'send_attempted': False}
    try:
        anchors = json.loads((ROOT / 'data/ui-anchors.json').read_text())['fixed_points']
        nickname = anchors['scenes']['share']['qq_recipient']
        steps = share_steps(anchors)
        if not args.execute:
            print(json.dumps({'status': 'plan_ok_no_input', 'recipient': nickname, 'steps': steps,
                              'return_focus': 'activate_original_farm_process_and_refresh_window'}, ensure_ascii=False))
            return 0
        layout = json.loads((ROOT / 'data/ui-layout.json').read_text())
        _, farm = farm_target(args.registry, 'qq', layout)

        def windows():
            result = subprocess.run([str(args.registry), '--platform', 'qq'],
                                    capture_output=True, text=True, check=True, timeout=5)
            payload = json.loads(result.stdout)
            if payload['platform'] != 'qq':
                raise ValueError('REGISTRY_PLATFORM_MISMATCH')
            return payload['windows']

        def click(target, point, delay, selector):
            click_batch(args.click_helper, '--execute', target,
                        [{'x': point[0], 'y': point[1], 'delay_ms': delay}], qq_share=selector)

        run_share(steps, nickname, farm, windows, click,
                  lambda *a: send_text(args.click_helper, *a),
                  lambda target: restore_farm(target, args.registry, layout), progress)
        print(json.dumps({'status': 'share_actions_sent_unverified', **progress}, ensure_ascii=False))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'stopped', 'reason': str(exc), **progress}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
