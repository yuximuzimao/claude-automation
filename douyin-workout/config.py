"""共享配置：路径、常量"""
import os
import re
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
PLANS_DIR = PLUGIN_DIR
SLICES_DIR = PLUGIN_DIR / "slices"
DB_PATH = PLUGIN_DIR / "exercise_db.json"
WHISPER_MODEL = os.path.expanduser("~/.whisper-models/ggml-medium.bin")

EXERCISE_TYPES = ["腿部", "小腿", "腰腹", "拉伸", "体态", "有氧", "其他"]

_NOISE_PATTERNS = [
    r'字幕製作', r'我只想跟你', r'我就是想要你', r'这种动作.*强大',
    r'^好$', r'^\(.*\)$', r'我帮你解决了', r'帮我解决了',
    r'你以為我會', r'你和我之间', r'腿前侧拉伸.*一条腿向前倒.*再撑',
    r'^[十一二三四五六七八九]+\s*腿前侧拉伸',
]
_ACTION_STARTERS = [
    r'^第[一二三四五六七八九十\d]+[个动作]',
    r'^\d+[、.]',
    r'^[一二三四五六七八九十]\s*[、.]',
    r'^[一二三四五六七八九十]\s+\w',
]

NOISE_RE = [re.compile(p) for p in _NOISE_PATTERNS]
ACTION_START_RE = [re.compile(p) for p in _ACTION_STARTERS]
MAX_REPEAT = 3
