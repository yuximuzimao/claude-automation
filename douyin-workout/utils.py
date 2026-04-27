"""共享工具函数：转录解析、视频切片辅助"""
import re
import base64
from pathlib import Path
from config import NOISE_RE, ACTION_START_RE, MAX_REPEAT, SLICES_DIR


def is_noise(text: str) -> bool:
    return any(p.search(text) for p in NOISE_RE)


def is_action_start(text: str) -> bool:
    return any(p.match(text) for p in ACTION_START_RE)


def time_to_seconds(t: str) -> float:
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_segments(transcription: str) -> list[dict]:
    pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(.+)')
    raw, text_count = [], {}
    for match in pattern.finditer(transcription):
        start, end, text = match.groups()
        text = text.strip()
        if is_noise(text):
            continue
        text_count[text] = text_count.get(text, 0) + 1
        if text_count[text] > MAX_REPEAT:
            continue
        raw.append({'start': start, 'end': end, 'text': text})
    return raw


def group_into_actions(segments: list[dict]) -> list[dict]:
    """将连续句子按动作段落合并（新动作关键词或停顿 >5 秒触发分段）"""
    if not segments:
        return []
    groups, current = [], None
    for seg in segments:
        gap = time_to_seconds(seg['start']) - time_to_seconds(current['end']) if current else 0
        if current is None or is_action_start(seg['text']) or gap > 5:
            if current:
                groups.append(current)
            current = {'start': seg['start'], 'end': seg['end'], 'texts': [seg['text']]}
        else:
            current['end'] = seg['end']
            current['texts'].append(seg['text'])
    if current:
        groups.append(current)
    return groups


def sanitize(text: str, max_len: int = 30) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff]', '_', text)[:max_len]


_gif_cache: dict[str, str] = {}


def gif_to_b64(gif_dir: str, gif_name: str) -> str:
    """读取 GIF 并转为 base64，结果在进程内缓存避免重复读取。"""
    key = f"{gif_dir}/{gif_name}"
    if key not in _gif_cache:
        gif_path = SLICES_DIR / gif_dir / f"{gif_name}.gif"
        if gif_path.exists():
            _gif_cache[key] = base64.b64encode(gif_path.read_bytes()).decode()
        else:
            _gif_cache[key] = ""
    return _gif_cache[key]
