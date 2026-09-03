from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
DEPENDENCY = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
OUT = ROOT / "data/route-atlas/icecrown-route-structured-candidate.json"
COVERAGE = ROOT / "data/route-atlas/icecrown-route-structured-coverage.json"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}

# Stable Icecrown anchors only. Cross-map portions intentionally stay on their Icecrown
# departure/return anchor so the Icecrown map does not draw fake lines to another continent.
ANCHORS: dict[str, tuple[float, float]] = {
    "银色比武场": (69.65, 22.86),
    "银色前线基地": (87.1, 75.8),
    "回音谷": (83.0, 73.0),
    "天灾城": (78.5, 64.5),
    "北伐军之峰": (79.8, 71.8),
    "奥格瑞姆之锤": (64.0, 50.0),  # moving hub: representative map marker only
    "暗影拱顶": (44.1, 24.7),
    "Savage Ledge": (37.0, 23.7),
    "Jotunheim": (28.0, 40.0),
    "约尔达村": (27.0, 39.0),
    "白骨女巫": (32.5, 43.0),
    "地下大厅": (33.1, 37.8),
    "乌弗朗之厅": (40.1, 23.9),
    "巫妖王之眼": (26.2, 62.3),
    "先祖大厅": (28.0, 47.0),
    "战痕尖塔": (28.7, 51.9),
    "巴拉加德堡垒": (18.0, 56.0),
    "瓦哈拉斯西南鱼叉平台": (32.0, 24.0),
    "瓦哈拉斯": (30.7, 29.0),
    "死亡高地": (19.5, 48.1),
    "先锋军港口": (8.0, 43.0),
    "赤色大教堂": (10.0, 46.0),
    "黑色观察站": (35.4, 66.3),
    "缝合场": (34.0, 68.0),
    "复生密室": (34.0, 68.0),
    "伊米海姆": (52.0, 58.0),
    "萨隆邪铁矿洞": (55.0, 59.0),
    "玛雷卡里斯": (58.0, 72.0),
    "破碎前线": (68.0, 68.0),
    "冰冠堡垒": (54.0, 86.0),
    "遗忘深渊": (54.0, 87.0),
    "莫德雷萨": (60.8, 63.4),
    "失落希望之谷": (68.0, 51.8),
    "第一军团": (64.5, 44.0),
    "辛达苟萨之墓": (71.0, 37.0),
    "白骨之庭": (49.2, 73.2),
    "黑暗大教堂": (44.5, 77.6),
    "沉默墓地": (79.8, 30.8),
    "荒凉之门": (50.4, 40.3),
    "奥尔杜萨": (51.0, 33.0),
    "哭泣采掘场": (39.0, 35.0),
    "恐惧之门": (44.0, 62.0),
    "科雷萨": (48.0, 68.5),
    "苦难高地": (53.9, 71.5),
}

# When a step starts with dialogue/transport text that has no coordinate, keep a deterministic
# player-facing map anchor instead of guessing from the previous step.
PRIMARY_STEP_ANCHOR: dict[int, tuple[float, float]] = {
    1: ANCHORS["银色比武场"],
    2: ANCHORS["银色前线基地"],
    3: ANCHORS["银色前线基地"],
    4: ANCHORS["回音谷"],
    5: ANCHORS["银色前线基地"],
    6: ANCHORS["北伐军之峰"],
    7: ANCHORS["奥格瑞姆之锤"],
    8: ANCHORS["暗影拱顶"],
    9: ANCHORS["暗影拱顶"],
    10: ANCHORS["乌弗朗之厅"],
    11: ANCHORS["白骨女巫"],
    12: ANCHORS["Jotunheim"],
    13: ANCHORS["Jotunheim"],
    14: ANCHORS["白骨女巫"],
    15: ANCHORS["瓦哈拉斯"],
    16: ANCHORS["死亡高地"],
    17: ANCHORS["先锋军港口"],
    18: ANCHORS["先锋军港口"],
    19: ANCHORS["黑色观察站"],
    20: ANCHORS["伊米海姆"],
    21: ANCHORS["奥格瑞姆之锤"],
    22: ANCHORS["冰冠堡垒"],
    23: ANCHORS["莫德雷萨"],
    24: ANCHORS["莫德雷萨"],
    25: ANCHORS["辛达苟萨之墓"],
    26: ANCHORS["黑色观察站"],
    27: ANCHORS["北伐军之峰"],
    28: ANCHORS["北伐军之峰"],
    29: ANCHORS["银色前线基地"],
    30: ANCHORS["银色前线基地"],
    31: ANCHORS["银色前线基地"],
    32: ANCHORS["荒凉之门"],
    33: ANCHORS["奥尔杜萨"],
    34: ANCHORS["奥尔杜萨"],
    35: ANCHORS["奥尔杜萨"],
    36: ANCHORS["暗影拱顶"],
    37: ANCHORS["哭泣采掘场"],
    38: ANCHORS["恐惧之门"],
    39: ANCHORS["科雷萨"],
    40: ANCHORS["玛雷卡里斯"],
    41: ANCHORS["苦难高地"],
}

EXPLICIT_COORD = re.compile(r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*[,，]\s*(\d{1,2}(?:\.\d+)?)")
DISPLAY_COORD = re.compile(r"(?:约)?\d{1,2}(?:\.\d+)?(?:[—–-]\d{1,2}(?:\.\d+)?)?\s*[,，]\s*\d{1,2}(?:\.\d+)?(?:[—–-]\d{1,2}(?:\.\d+)?)?")
TASK_NAME = re.compile(r"《([^》]+)》")
TASK_ACTION_GROUP = re.compile(r"(接|做|交)\s*((?:《[^》]+》[、，, ]*)+)")
LOCATION_HINT = re.compile(r"(基地|林地|废墟|墓地|神殿|港口|大教堂|堡垒|营地|村|高地|前线|大厅|矿洞|之峰|之墓|之庭|之门|拱顶|观察站|海姆|雷卡里斯|杜萨|采掘场|约|附近|外围|顶部|底层|上层|下层|水域|城墙)")

SPECIAL_DISPLAY_ACTIONS = (
    ("三名首领全部完成后使用最后出现的死亡之门", "任务传送：天灾城 → 回音谷 → 交《凝固的空气》"),
    ("大德鲁伊莉琳德拉 → 对话开启月光林地传送门", "任务传送：银色前线基地 → 月光林地"),
    ("返程传送门返回冰冠冰川", "任务传送：月光林地 → 冰冠冰川"),
    ("现场开启的沙塔斯传送门", "任务传送：北伐军之峰 → 沙塔斯"),
    ("接受《阿达尔的恩赐》后按任务脚本返回达拉然", "任务传送：沙塔斯 → 达拉然"),
    ("逃生传送门", "任务传送：黑暗大教堂 → 北伐军之峰"),
    ("北伐军之峰骷髅堆", "北伐军之峰骷髅堆 → 做《北伐军之峰的战斗》"),
    ("其余五项先带走", ""),
    ("暗影拱顶顶部·眼球", "暗影拱顶顶部·眼球 → 做《乐趣十足》"),
    ("暗影拱顶周边三名目标", "暗影拱顶周边三名目标 → 做《解放你的思想》"),
    ("暗影拱顶内部北侧锻炉/武器架", "暗影拱顶内部 → 做《顽固的敌人》"),
    ("强大的乌弗朗领主", "强大的乌弗朗领主 → 做《暗影拱顶裁决令》"),
    ("教官霍加尔", "教官霍加尔 → 做《夺取钥匙》"),
    ("接《瓦古的复仇》并完成受难之环挑战", "地下大厅·贝索德·菲格 → 接《瓦古的复仇》 → 做《瓦古的复仇》"),
    ("先祖大厅入口约28,47", "先祖大厅 → 做《找到古代英雄》"),
    ("战痕尖塔附近约28.7,51.9", "战痕尖塔 → 做《不那么光彩的战斗》"),
    ("巴拉加德堡垒顶部约18,56", "巴拉加德堡垒顶部 → 做《女妖的复仇》"),
    ("连续推进《瓦哈拉斯之战：堕落的英雄》", "瓦哈拉斯 → 接《瓦哈拉斯之战：堕落的英雄》 → 做《瓦哈拉斯之战：堕落的英雄》 → 交《瓦哈拉斯之战：堕落的英雄》 → 接《瓦哈拉斯之战：黑暗主宰西塔利克斯》 → 做《瓦哈拉斯之战：黑暗主宰西塔利克斯》 → 交《瓦哈拉斯之战：黑暗主宰西塔利克斯》 → 接《瓦哈拉斯之战：齐格莉德归来》 → 做《瓦哈拉斯之战：齐格莉德归来》 → 交《瓦哈拉斯之战：齐格莉德归来》 → 接《瓦哈拉斯之战：血肉巨人卡纳基！》 → 做《瓦哈拉斯之战：血肉巨人卡纳基！》 → 交《瓦哈拉斯之战：血肉巨人卡纳基！》 → 接《瓦哈拉斯之战：“死亡一击”领主》 → 做《瓦哈拉斯之战：“死亡一击”领主》 → 交《瓦哈拉斯之战：“死亡一击”领主》 → 接《瓦哈拉斯之战：终极挑战》 → 做《瓦哈拉斯之战：终极挑战》 → 交《瓦哈拉斯之战：终极挑战》"),
    ("五号分别与高级指挥官埃雷特互动", "高级指挥官埃雷特 → 做《迄今为止的故事……》 → 交《迄今为止的故事……》"),
    ("等待埃雷特审讯灵魂脚本结束", "赤色大教堂 → 做《第二次机会》 → 交《第二次机会》 → 接《元帅的下落》"),
    ("岛屿南侧隐蔽洞穴", "岛屿南侧隐蔽洞穴 → 做《元帅的下落》"),
    ("缝合场东侧约37.1,71.2", "缝合场东侧 → 做《它们从哪儿来的？》\n黑色观察站 → 交《它们从哪儿来的？》 → 接《摧毁祭坛》《死亡的凝视》"),
    ("击杀召唤大师扎洛德", "缝合场 → 做《摧毁祭坛》《死亡的凝视》"),
    ("缝合场本地 → 主控摧毁", "缝合场 → 做《抛洒它们的血》 → 接《粗糙的碎片》 → 做《粗糙的碎片》"),
    ("交《前往伊米海姆！》→ 接《占山为王》；用跳跃机器人", "伊米海姆·布拉斯·炸雷 → 交《前往伊米海姆！》 → 接《占山为王》 → 做《占山为王》 → 交《占山为王》"),
    ("接《思维诡计》；击杀工头", "矿洞内黑暗低语者阿克希姆 → 接《思维诡计》 → 做《思维诡计》 → 交《思维诡计》"),
    ("做已携带《破碎前线》", "破碎前线 → 做《破碎前线》 → 接《为我复仇！》 → 做《为我复仇！》"),
    ("地下入口附近击杀10只笨重的恐尸", "冰冠堡垒地下入口 → 做《确立优势》 → 交《确立优势》 → 接《引爆！》"),
    ("遗忘深渊杀无面潜伏者", "遗忘深渊 → 做《藏匿行踪》 → 交《藏匿行踪》 → 接《返回地面》"),
    ("使用整修过的攻城车", "失落希望之谷 → 做《竭尽全力》"),
    ("第一军团前线营地约64.5,44.0", "第一军团前线营地 → 交《竭尽全力》 → 接《召唤大军》 → 做《召唤大军》 → 交《召唤大军》 → 接《徒劳》"),
    ("附近约48,72寻找染血的石头", "白骨之庭 → 做《猎人与王子》"),
    ("洞外/下层拾取发绿光的燃烧骷髅手臂", "复生密室洞外/下层 → 做《一举两得》"),
    ("回黑色观察站交《一举两得》", "黑色观察站 → 交《一举两得》 → 接《支离破碎》\nFleshwerks下层 → 做《支离破碎》"),
    ("交《支离破碎》→ 接《重新组合欧尔拉金》；再次进复生密室", "黑色观察站 → 交《支离破碎》 → 接《重新组合欧尔拉金》\n复生密室 → 做《重新组合欧尔拉金》"),
    ("交《重新组合欧尔拉金》→ 接《最强大的血肉巨人》；Fleshwerks西端", "黑色观察站 → 交《重新组合欧尔拉金》 → 接《最强大的血肉巨人》\nFleshwerks西端 → 做《最强大的血肉巨人》"),
    ("黑暗大教堂入口约44.5,77.6", "黑暗大教堂入口 → 做《提里奥的尝试》"),
    ("奥尔杜萨北部建筑入口约51,33", "奥尔杜萨北部建筑入口 → 做《需要更多情报》"),
    ("奥尔杜萨北部奥鲁麦斯仪式房间", "奥尔杜萨北部奥鲁麦斯仪式房间 → 做《片刻不得安宁》"),
    ("《不择手段》共享：", "做《不择手段》"),
    ("其余两项再控制幻象观察者", "哭泣采掘场 → 做《亡灵的好朋友》《来去无踪》"),
    ("80/80后不要坐狮鹫回暗影拱顶", "哭泣采掘场 → 做《一片狼藉》"),
    ("苦难高地东侧高处/桥面", "苦难高地东侧 → 做《新兵》"),
    ("五号交《新兵》→ 接《邪恶城堡》", "苦难高地 → 交《新兵》 → 接《邪恶城堡》 → 做《邪恶城堡》"),
    ("科雷萨北侧/大火场", "科雷萨北侧/大火场 → 做《在恐惧之门前》"),
    ("五号一起从南到北/顺路击杀三名骑士", "洛基尔·邪恶骑士 → 做《邪恶骑士》\n贝洛克·鲜血骑士 → 做《鲜血骑士》\n萨芙·冰霜骑士 → 做《冰霜骑士》"),
    ("冰冠堡垒地下深渊边缘", "冰冠堡垒地下深渊边缘 → 做《血毒的命运》"),
)


def extract_coord(text: str) -> tuple[float, float] | None:
    match = EXPLICIT_COORD.search(text)
    if not match:
        return None
    x, y = float(match.group(1)), float(match.group(2))
    if 0 <= x <= 100 and 0 <= y <= 100:
        return x, y
    return None


def infer_anchor(text: str) -> tuple[float, float] | None:
    # Coordinates are trusted wherever explicitly written. Named locations, however, are only
    # trusted in the action's leading location/NPC segment. Later prose often says things like
    # 'do not return to X yet', which must not move the map point to X.
    explicit = extract_coord(text)
    if explicit:
        return explicit
    prefix = text.split("→", 1)[0].split("↳", 1)[0].strip()
    # System/fixed transport names its destination explicitly; anchor the point at that destination.
    if text.startswith(("系统飞行：", "固定交通：")):
        for name in sorted(ANCHORS, key=len, reverse=True):
            if name in text.split("→")[-1]:
                return ANCHORS[name]
    if prefix.startswith(("使用炉石：", "炉石绑定：", "开飞行点：")):
        for name in sorted(ANCHORS, key=len, reverse=True):
            if name in prefix:
                return ANCHORS[name]
    # If an action has no explicit location segment and begins as an instruction, place names
    # mentioned later in that prose describe the objective/destination, not the current anchor.
    if "→" not in text and prefix.startswith(("做《", "先做《", "先由", "五号", "每", "使用", "继续", "同一片", "第一", "三项", "两项", "个人")):
        return None
    for name in sorted(ANCHORS, key=len, reverse=True):
        if name in prefix:
            return ANCHORS[name]
    return None


def movement_kind(text: str, step: int) -> str:
    if any(term in text for term in ("传送门", "任务脚本返回", "传送回")):
        return "script"
    if "炉石" in text:
        return "hearth"
    if step in {5, 29, 30, 31} and any(term in text for term in ("晶歌", "月光", "龙眠", "红玉", "沙塔斯", "达拉然")):
        return "crossmap"
    if text.startswith(("系统飞行：", "固定交通：")):
        return "crossmap"
    return "fly"


def action_location(text: str) -> str:
    head = text.split("→", 1)[0].strip()
    head = head.split("↳", 1)[0].strip()
    return head[:48] if head else "本段"


def clean_display_location(text: str) -> str:
    if "→" in text:
        head = text.split("→", 1)[0].strip()
    elif "↳" in text:
        head = text.split("↳", 1)[0].strip()
    else:
        return ""
    if "《" in head or "》" in head:
        return ""
    if any(token in head for token in ("；", ";", "五号", "主控", "技能", "完成", "击杀", "收集", "共享", "不共享", "任务物", "等待")):
        return ""
    head = DISPLAY_COORD.sub("", head)
    head = re.sub(r"[（(]\s*(?:约)?\d[^）)]*[）)]", "", head)
    head = re.sub(r"[（(]\s*[）)]", "", head)
    head = re.sub(r"^(?:(?:再|最后)?(?:重新找到|寻找)|五号一起|五号全部|五号分别|再|最后|返回|继续|开始由北向南|一路向北推进|向东北进入|离开)\s*", "", head)
    head = re.sub(r"^回(?=(?:苦难高地|黑色观察站|死亡高地|银色前线基地|北伐军之峰|暗影拱顶|奥格瑞姆之锤))", "", head)
    head = re.sub(r"^先(?=做|到|由|在|找|去|用|从|不要|不|把|让)", "", head)
    if "：" in head or ":" in head:
        head = re.split(r"[：:]", head)[-1]
    head = re.sub(r"\s*(?:约|附近|一带)$", "", head)
    head = re.sub(r"\s+", "", head).strip("·：:；;，, ")
    if not head:
        return ""
    if any(token in head for token in ("完成", "击杀", "使用", "收集", "共享", "等待", "不要", "直到", "任务", "顺路", "沿路", "带走", "先做")):
        return ""
    return head[:48]


def compact_player_action(text: str) -> str | None:
    raw = str(text).strip()
    if not raw:
        return None
    for needle, replacement in SPECIAL_DISPLAY_ACTIONS:
        if needle in raw:
            return replacement or None
    if raw.startswith(("开飞行点：", "炉石绑定：", "使用炉石：", "系统飞行：", "固定交通：", "任务传送：")):
        return re.sub(r"[（(][^）)]*[）)]$", "", raw).strip()

    groups = [(verb, names.strip("、，, ")) for verb, names in TASK_ACTION_GROUP.findall(raw)]
    names = TASK_NAME.findall(raw)

    if "接并护送" in raw and names:
        groups = [("接", f"《{names[0]}》"), ("做", f"《{names[0]}》")]
    elif not groups and names:
        do_signal = any(token in raw for token in (
            "完成《", "做《", "为《", "连续推进《", "推进《", "按任务载具机制", "取得《", "整个", "同圈做《",
        ))
        if do_signal:
            groups = [("做", "".join(f"《{name}》" for name in names))]

    location = clean_display_location(raw)
    if groups:
        action_chain = " → ".join(f"{verb}{task_group}" for verb, task_group in groups)
        return f"{location} → {action_chain}" if location else action_chain

    # A task can span several geographic stops. Keep a clean location-only waypoint so the map
    # still preserves the route geometry, while all mechanics/counts stay in the task note.
    return location or None


EXTERNAL_DISPLAY_PLACES = ("月光林地", "雷姆洛斯神殿", "龙眠神殿", "红玉巨龙圣地", "沙塔斯", "达拉然")


def player_point_title(raw_action: str, display_action: str, coord: tuple[float, float], step_no: int) -> str:
    for source in (display_action, raw_action):
        location = clean_display_location(source)
        if location:
            return location
    for place in EXTERNAL_DISPLAY_PLACES:
        if place in display_action or place in raw_action:
            return place
    if step_no == 29:
        return "月光林地"
    if step_no == 30:
        return "龙眠神殿"
    if step_no == 31:
        return "达拉然" if "达拉然" in display_action or "达拉然" in raw_action else "沙塔斯"
    return min(
        ANCHORS.items(),
        key=lambda item: (coord[0] - item[1][0]) ** 2 + (coord[1] - item[1][1]) ** 2,
    )[0]


def decorate_task_tokens(text: str) -> str:
    safe = html.escape(text)
    safe = re.sub(r"(开飞行点：[^；<]+)", r'<span class="ra-system-action ra-flightpoint">\1</span>', safe)
    safe = re.sub(r"(系统飞行：[^；<]+)", r'<span class="ra-system-action ra-flightpath">\1</span>', safe)
    safe = re.sub(r"(固定交通：[^；<]+)", r'<span class="ra-system-action ra-flightpath">\1</span>', safe)
    safe = re.sub(r"(炉石绑定：[^；<]+)", r'<span class="ra-system-action ra-hearthstone">\1</span>', safe)
    safe = re.sub(r"(使用炉石：[^；<]+)", r'<span class="ra-system-action ra-hearthstone">\1</span>', safe)

    def render_task_group(match: re.Match[str]) -> str:
        verb = match.group(1)
        names = re.findall(r"《([^》]+)》", match.group(2))
        cls = {"接": "ra-accept", "交": "ra-turnin", "做": "ra-do-task"}[verb]
        rendered = "、".join(f'<span class="ra-task {cls}">{name}</span>' for name in names)
        if verb == "做":
            return f'<span class="ra-branch">↳</span> <span class="ra-verb">做</span> {rendered}'
        return f'<span class="ra-verb">{verb}</span> {rendered}'

    # One verb governs the full adjacent task list: 接《A》《B》 / 交《A》、《B》 / 做《A》《B》.
    # Every task inherits the same semantic color and can therefore be audited from the final HUD.
    safe = re.sub(r"(接|交|做)((?:《[^》]+》[、，, ]*)+)", render_task_group, safe)
    # Task names used only as references/explanations still receive generic task styling.
    safe = re.sub(r"《([^》]+)》", r'<span class="ra-task">\1</span>', safe)
    return safe


def semantic_action_html(text: str) -> str:
    if "→" not in text:
        return f'<div class="ra-line">{decorate_task_tokens(text)}</div>'
    prefix, rest = text.split("→", 1)
    prefix = prefix.strip()
    rest = rest.strip()
    if prefix and "《" not in prefix and not prefix.startswith(("做《", "交《", "接《", "五号", "先", "每", "离开条件", "使用", "接受", "单号", "三项", "两项", "连续推进")):
        cls = "ra-location" if LOCATION_HINT.search(prefix) or infer_anchor(prefix) else "ra-npc"
        rendered_prefix = f'<span class="{cls}">{html.escape(prefix)}</span>'
        return f'<div class="ra-line">{rendered_prefix}<span class="ra-arrow">→</span>{decorate_task_tokens(rest)}</div>'
    return f'<div class="ra-line">{decorate_task_tokens(text)}</div>'


def note_html(step: dict) -> str:
    blocks: list[str] = []
    for card in (step.get("task_cards") or {}).values():
        name = str(card.get("name") or "任务")
        note = str(card.get("route_note") or "").strip()
        fivebox = str(card.get("fivebox") or "").strip()
        if not note and not fivebox:
            continue

        body = ""
        confirmed_prefix = ""
        confirmed_class = ""
        confirmed_detail = ""
        pending_detail = ""
        if fivebox.startswith("共享："):
            confirmed_prefix = "共享："
            confirmed_class = "ra-shared"
            confirmed_detail = fivebox[len("共享："):].strip()
        elif fivebox.startswith("不共享："):
            confirmed_prefix = "不共享："
            confirmed_class = "ra-not-shared"
            confirmed_detail = fivebox[len("不共享："):].strip()
        elif fivebox:
            pending_detail = re.sub(r"^(?:重点)?待实测[：:]\s*", "", fivebox).strip() or fivebox

        if confirmed_prefix:
            text = f'<span class="{confirmed_class}">{confirmed_prefix}</span>'
            if confirmed_detail:
                text += html.escape(confirmed_detail)
            if note:
                text += (" " if confirmed_detail else "") + html.escape(note)
            body += f'<div class="ra-note-text">{text}</div>'
        elif note:
            body += f'<div class="ra-note-text">{html.escape(note)}</div>'

        if pending_detail:
            body += (
                '<div class="ra-fivebox-line">'
                '<span class="ra-pending">五开待实测：</span>'
                f'{html.escape(pending_detail)}</div>'
            )
        blocks.append(f'<div class="ra-note-block"><div class="ra-note-task">《{html.escape(name)}》</div>{body}</div>')
    return ('<div class="ra-note-heading">备注</div>' + ''.join(blocks)) if blocks else ""


def main() -> None:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    dependency = json.loads(DEPENDENCY.read_text(encoding="utf-8"))
    first_step = {int(qid): int(step) for qid, step in (dependency.get("first_step_by_quest_id") or {}).items()}
    formal = {
        int(task["quest_id"])
        for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    }

    points: list[list] = []
    groups: list[dict] = []
    geometry_fallbacks: list[dict] = []
    previous = ANCHORS["银色比武场"]

    for step in draft.get("steps", []):
        step_no = int(step["step"])
        start = len(points)
        raw_actions = step.get("actions") or []
        # Step numbers are presentation order and change whenever Journey reorders/splits a phase.
        # Derive the starting anchor from the current step's own title/actions instead of coupling
        # geometry to the historical 41-step numbering table.
        title_text = str(step.get("title") or "")
        title_anchor = next(
            (ANCHORS[name] for name in sorted(ANCHORS, key=len, reverse=True) if name in title_text),
            None,
        )
        action_anchor = next((coord for action in raw_actions if (coord := infer_anchor(str(action))) is not None), None)
        current = title_anchor or action_anchor or previous
        display_rows: list[tuple[str, str]] = []
        for raw_action in raw_actions:
            compacted = compact_player_action(str(raw_action))
            if compacted is None:
                continue
            for display_action in (line.strip() for line in compacted.splitlines() if line.strip()):
                display_rows.append((str(raw_action), display_action))
        outside_icecrown_map = False
        for action_idx, (raw_action, display_action) in enumerate(display_rows, start=1):
            # Geometry is derived from the rich internal planning line; only the compact closed-set
            # action is published to the player. This keeps coordinates/mechanics out of HUD text
            # without throwing away the map position they were originally used to establish.
            coord = infer_anchor(display_action) or infer_anchor(raw_action)
            if coord is None:
                coord = current
                geometry_fallbacks.append({
                    "step": step_no,
                    "action": action_idx,
                    "text": raw_action,
                    "fallback": [round(coord[0], 2), round(coord[1], 2)],
                })
            else:
                current = coord
            move = movement_kind(raw_action, step_no)
            prefix = raw_action.split("→", 1)[0].strip()
            if move == "crossmap":
                outside_icecrown_map = True
            elif outside_icecrown_map and any(name in prefix for name in ANCHORS):
                move = "crossmap"
                outside_icecrown_map = False
            if "返程传送门返回冰冠冰川" in raw_action:
                coord = ANCHORS["银色前线基地"]
                current = coord
                move = "script"
                outside_icecrown_map = False
            title = player_point_title(raw_action, display_action, coord, step_no)
            points.append([
                round(coord[0], 2), round(coord[1], 2), title, display_action, f"ice{step_no:02d}", "", move, False, ""
            ])
        previous = current
        end = len(points) - 1
        if end < start:
            raise RuntimeError(f"Icecrown step {step_no} has no player actions after closed-set compaction")
        timing = step.get("timing") or {}
        display_actions = [display_action for _, display_action in display_rows]
        groups.append({
            "start": start,
            "end": end,
            "title": str(step["title"]),
            "summary": "",
            "actionHtml": "\n".join(semantic_action_html(display_action) for display_action in display_actions),
            "noteHtml": note_html(step),
            "timing": {
                "centerMinutes": float(timing["centerMinutes"]),
                "rangeMinutes": [float(x) for x in timing["rangeMinutes"]],
                "includeInTotal": str(timing.get("status") or "") != "pending_recalc",
                "status": str(timing.get("status") or "pending_recalc"),
            },
            "questIds": sorted(qid for qid, first in first_step.items() if first == step_no and qid in formal),
        })

    covered = {qid for group in groups for qid in group["questIds"]}
    missing = sorted(formal - covered)
    unexpected = sorted(covered - formal)
    policy = draft.get("timing_policy") or {}
    route = {
        "order": 7,
        "uiStandard": "semantic-hud-v45",
        "status": "icecrown_first_group_journey_closed_route",
        "title": "冰冠冰川 · 五开首组历程校准路线",
        "sub": "以首组Journey确认的大阶段顺序为主轴；局部任务簇仍按可复用的顺路顺序执行，高难未完成支线单列为可选收尾。",
        "badge": "炉石：暗影拱顶（解锁后）\\n预计总时间：待首组按重排路线实跑后重算",
        "image": "maps/210-icecrown-hd.jpg",
        "legend": "",
        "footer": "",
        "labels": [[x, y, name] for name, (x, y) in ANCHORS.items() if name not in {"奥格瑞姆之锤"}],
        "points": points,
        "defaultIndex": groups[24]["start"] if len(groups) > 24 else 0,
        "phaseColors": {f"ice{i:02d}": "#94a3b8" for i in range(1, len(groups) + 1)},
        "displayName": "冰冠冰川",
        "stepGroups": groups,
        "defaultGroupIndex": 24 if len(groups) > 24 else 0,
        "hearthChain": ["暗影拱顶"],
        "timing": {
            "centerMinutes": float(policy.get("route_total_center_minutes") or 0),
            "rangeMinutes": [float(x) for x in (policy.get("route_total_pre_live_band_minutes") or [])],
            "actualRuns": [],
            "model": "icecrown_54_step_journey_closure_player_bookmarks_pending_recalc",
        },
        "geometryAudit": {
            "fallbackActionCount": len(geometry_fallbacks),
            "fallbackActions": geometry_fallbacks,
            "movingHubRepresentative": {"name": "奥格瑞姆之锤", "point": list(ANCHORS["奥格瑞姆之锤"])},
        },
    }
    OUT.write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COVERAGE.write_text(json.dumps({
        "status": "icecrown_structured_candidate_coverage",
        "formalTaskCount": len(formal),
        "coveredTaskCount": len(covered & formal),
        "missing": missing,
        "unexpected": unexpected,
        "pointCount": len(points),
        "stepGroupCount": len(groups),
        "geometryFallbackActionCount": len(geometry_fallbacks),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "formal": len(formal), "covered": len(covered & formal), "missing": len(missing),
        "points": len(points), "groups": len(groups), "geometry_fallbacks": len(geometry_fallbacks),
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    if missing or unexpected:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
