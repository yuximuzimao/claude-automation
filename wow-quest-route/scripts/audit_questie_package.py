from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path


def find_member(names: list[str], suffix: str) -> str | None:
    suffix = suffix.replace('\\', '/')
    for name in names:
        if name.endswith(suffix):
            return name
    return None


def read_text(zf: zipfile.ZipFile, member: str | None) -> str:
    if not member:
        return ''
    return zf.read(member).decode('utf-8', errors='replace')


def extract_toc_version(text: str) -> str:
    match = re.search(r'^## Version:\s*(.+?)\s*$', text, flags=re.MULTILINE)
    return match.group(1) if match else 'unknown'


def print_matches(title: str, text: str, patterns: list[str], context: int = 3) -> None:
    lines = text.splitlines()
    hits: list[int] = []
    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    for idx, line in enumerate(lines):
        if any(rx.search(line) for rx in regexes):
            hits.append(idx)
    print(f'\n## {title} ({len(hits)} hits)')
    shown: set[int] = set()
    for idx in hits[:80]:
        start = max(0, idx - context)
        end = min(len(lines), idx + context + 1)
        if any(i in shown for i in range(start, end)):
            continue
        for i in range(start, end):
            print(f'{i+1:5d} | {lines[i]}')
            shown.add(i)
        print('-----')


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit a Questie ZIP without modifying it.')
    parser.add_argument('zip_path')
    parser.add_argument('--mode', choices=('all', 'map', 'titan'), default='all')
    args = parser.parse_args()

    path = Path(args.zip_path).expanduser().resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f'path={path}')
    print(f'sha256={digest}')
    print(f'size={path.stat().st_size}')

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        print(f'entries={len(names)}')

        toc_candidates = [n for n in names if n.lower().endswith('.toc') and 'questie' in n.lower()]
        print('\n## TOC candidates')
        for member in toc_candidates[:20]:
            text = read_text(zf, member)
            print(f'{member}: version={extract_toc_version(text)}')
            for line in text.splitlines():
                if line.startswith('## Interface') or line.startswith('## Title') or line.startswith('## Version'):
                    print(f'  {line}')

        correction_members = [n for n in names if '/Database/Corrections/' in n.replace('\\', '/')]
        print(f'\ncorrection_files={len(correction_members)}')
        for member in correction_members[:80]:
            print(member)

        map_candidates = [
            n for n in names
            if n.endswith('.lua') and (
                '/Modules/Map/' in n.replace('\\', '/')
                or 'QuestieMap' in n
                or 'MapUtils' in n
            )
        ]
        print(f'\nmap_files={len(map_candidates)}')
        for member in map_candidates[:80]:
            print(member)

        if args.mode in ('all', 'titan'):
            titan_candidates: list[tuple[str, str]] = []
            for member in names:
                if not member.endswith(('.lua', '.toc', '.xml')):
                    continue
                try:
                    text = read_text(zf, member)
                except Exception:
                    continue
                if re.search(r'IsTitanReforged|TitanReforged|IsChinaRegion|ChinaRegion|38002|3\.80\.2|夜月', text, flags=re.IGNORECASE):
                    titan_candidates.append((member, text))
            print(f'\ntitan_related_files={len(titan_candidates)}')
            for member, _ in titan_candidates[:120]:
                print(member)

            for member, text in titan_candidates[:30]:
                print_matches(
                    f'Titan references: {member}',
                    text,
                    [r'IsTitanReforged', r'TitanReforged', r'IsChinaRegion', r'ChinaRegion', r'38002', r'3\.80\.2', r'夜月'],
                    context=4,
                )

        if args.mode in ('all', 'map'):
            for member in map_candidates[:20]:
                text = read_text(zf, member)
                if re.search(r'spawns|waypoints|SetPoint|WorldMap|UiMap|mapID|zone', text, re.IGNORECASE):
                    print_matches(
                        f'Map coordinate logic: {member}',
                        text,
                        [
                            r'spawns', r'waypoints', r'SetPoint', r'WorldMap', r'UiMap',
                            r'mapID', r'zone', r'coord', r'icon', r'note', r'pin',
                            r'HereBeDragons', r'HBD', r'AddWorldMapIcon', r'AddMinimapIcon',
                        ],
                        context=4,
                    )

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
