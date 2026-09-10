from __future__ import annotations

import html
import re
from typing import Any

from dragonblight_semantic_steps import (
    arrow,
    danger,
    do_at,
    do_line,
    loc,
    note_block,
    notes_html,
    npc,
    npc_actions,
    point_anchor,
    status_span,
    system_line,
    task,
    verb,
)


def raw_line(text: str) -> str:
    return f'<div class="ra-line">{html.escape(text)}</div>'


def task_text_line(prefix: str, quest_name: str, suffix: str = "") -> str:
    return '<div class="ra-line">' + html.escape(prefix) + task(quest_name, "do") + html.escape(suffix) + '</div>'


def npc_do_line(npc_name: str, quest_name: str) -> str:
    return '<div class="ra-line">' + npc(npc_name) + arrow() + verb("做") + ' ' + task(quest_name, "do") + '</div>'


def accept_from_item_line(prefix: str, quest_name: str) -> str:
    return '<div class="ra-line">' + html.escape(prefix) + arrow() + verb("接") + ' ' + task(quest_name, "accept") + '</div>'


def drop_accept_line(quest_name: str) -> str:
    return '<div class="ra-line">' + '<span class="ra-branch">↳</span>' + verb("接") + ' ' + task(quest_name, "accept") + '</div>'


def apply_step(points: list[list[Any]], groups: list[dict[str, Any]], step_number: int, spec: dict[str, Any]) -> None:
    group = groups[step_number - 1]
    indices = list(range(int(group["start"]), int(group["end"]) + 1))
    if len(indices) != len(spec["points"]):
        raise RuntimeError(f"Grizzly semantic step {step_number} point count drift: actual={len(indices)} expected={len(spec['points'])}")
    group["title"] = spec["title"]
    group["summary"] = spec["summary"]
    group["actionHtml"] = "\n".join(spec["action_html"])
    group["noteHtml"] = spec.get("note_html", "")
    group["timingTaskNames"] = list(spec.get("timingTaskNames", []))
    if "timingExtraMinutes" in spec:
        group["timingExtraMinutes"] = float(spec["timingExtraMinutes"])
    for point_index, point_spec in zip(indices, spec["points"], strict=True):
        point = points[point_index]
        while len(point) <= 9:
            point.append("")
        point[2] = point_spec["title"]
        point[3] = point_spec["action"]
        point[5] = point_spec.get("note", "")
        if "fivebox" in point_spec:
            point[8] = point_spec["fivebox"]


ACTION_ROW_RE = re.compile(r'<div class="ra-line[^\"]*">.*?</div>', re.S)
NOTE_BLOCK_RE = re.compile(r'<div class="ra-note-block">.*?</div></div>', re.S)


DISPLAY_SPLITS: dict[int, list[tuple[int, int, str]]] = {
    1: [(4, 12, "征服堡 → 沃德伦任务"), (3, 8, "风险湾 → 沃德伦领主 → 征服堡")],
    3: [(3, 13, "花岗岩之泉：达库鲁 / 天灾"), (7, 11, "达库鲁火盆 → 古树之心 → Drak'atal")],
    4: [(1, 5, "征服堡：斗兽场准备"), (1, 14, "征服斗兽场五连"), (3, 10, "花岗岩之泉 → 沃达希尔 → 盲眼卢娜")],
    5: [(3, 11, "欧尼瓦 → 索尔莫丹"), (3, 7, "炉石征服堡 → 欧尼瓦交接")],
    8: [(5, 9, "萨莎 → 灰喉堡 → 乌索克"), (6, 7, "乌索克交付 → 安娅 / 萨莎")],
    9: [(6, 13, "符文监督者 → Drakil'jin墓穴"), (6, 9, "金亚拉克 → 血月岛 → 加弗洛克")],
    10: [(6, 11, "欧尼瓦 ↔ Dun Argol：制服 / 能源"), (5, 9, "Dun Argol：能源 → 铁领主 → 欧尼瓦")],
}


def _plain_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _note_html_for_action(parent_note_html: str, action_html: str) -> str:
    if not parent_note_html.strip():
        return ""
    # Split display groups must not repeat an execution note merely because a later handoff row
    # mentions the same task name. Attach the note only to the split that actually does the task.
    execution_rows = []
    for row in ACTION_ROW_RE.findall(action_html):
        row_text = _plain_html(row)
        if "做" in row_text:
            execution_rows.append(row_text)
    execution_text = "\n".join(execution_rows)
    blocks: list[str] = []
    for block in NOTE_BLOCK_RE.findall(parent_note_html):
        match = re.search(r'<div class="ra-note-task[^\"]*">(.*?)</div>', block, re.S)
        if not match:
            continue
        label = _plain_html(match.group(1)).strip().strip("《》")
        names = [part.strip() for part in label.split(" / ") if part.strip()]
        if any(name in execution_text for name in names) or (label and label in execution_text):
            blocks.append(block)
    return notes_html(*blocks)


def _rebuild_display_groups(groups: list[dict[str, Any]]) -> None:
    coarse = [dict(group) for group in groups]
    rebuilt: list[dict[str, Any]] = []
    for step_number, parent in enumerate(coarse, 1):
        splits = DISPLAY_SPLITS.get(step_number)
        if not splits:
            rebuilt.append(parent)
            continue
        action_rows = ACTION_ROW_RE.findall(str(parent.get("actionHtml", "")))
        expected_points = int(parent["end"]) - int(parent["start"]) + 1
        if sum(item[0] for item in splits) != expected_points:
            raise RuntimeError(f"Grizzly display split {step_number} point drift")
        if sum(item[1] for item in splits) != len(action_rows):
            raise RuntimeError(f"Grizzly display split {step_number} action drift")
        point_cursor = int(parent["start"])
        action_cursor = 0
        for split_index, (point_count, action_count, title) in enumerate(splits):
            start = point_cursor
            end = point_cursor + point_count - 1
            split_action = "\n".join(action_rows[action_cursor : action_cursor + action_count])
            timing_names = [
                name for name in parent.get("timingTaskNames", []) if str(name) in _plain_html(split_action)
            ]
            rebuilt.append({
                "start": start,
                "end": end,
                "title": title,
                "summary": "",
                "actionHtml": split_action,
                "noteHtml": _note_html_for_action(str(parent.get("noteHtml", "")), split_action),
                "timingTaskNames": timing_names,
                "timingLogicalOverheadMinutes": 0.5 if split_index == 0 else 0.0,
            })
            point_cursor = end + 1
            action_cursor += action_count
    groups[:] = rebuilt


def apply_grizzly_semantic_overrides(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    specs: dict[int, dict[str, Any]] = {
        1: {
            "title": "征服堡 → 沃德伦 → 风险湾 → 沃德伦领主",
            "summary": "进入征服堡接齐南侧任务并开点/绑炉石；沃德伦完成野兽与缚焰者任务，风险湾做短时限溶解剂，再骑任务龙击杀沃德伦领主。",
            "points": [
                {"title": "征服堡", "action": "征服者克雷娜 → 交《前往征服堡，自求多福吧！》 → 接《征服者的指派》"},
                {"title": "征服堡", "action": "纳兹格利姆中士 → 交《征服者的指派》 → 接《缚焰者的秘密》《显示力量》\n皮货商人休尼克 → 接《灰狼的毛皮》\n粮食商人洛克兰 → 接《赚外快》\n开飞行点：征服堡\n绑定炉石：征服堡"},
                {"title": "征服堡南侧 / 沃德伦", "action": "↳ 做《赚外快》《灰狼的毛皮》《缚焰者的秘密》《显示力量》", "note": "《赚外快》《灰狼的毛皮》《缚焰者的秘密》：不共享：任务物为个人掉落，五号分别拾取。\n《显示力量》：共享：击杀进度五号同步。"},
                {"title": "征服堡", "action": "粮食商人洛克兰 → 交《赚外快》\n皮货商人休尼克 → 交《灰狼的毛皮》 → 接《替代品》\n纳兹格利姆中士 → 交《缚焰者的秘密》《显示力量》 → 接《沃德伦的领主》"},
                {"title": "风险湾", "action": "古图尔 → 接《寻找溶解剂》\n↳ 做《寻找溶解剂》\n古图尔 → 交《寻找溶解剂》", "note": "不共享：按单个场景物交互/拾取处理，五号依次获取 Element 115；拾取后开始短时限返程，立即原路返回古图尔并尽量不进战斗。", "fivebox": ""},
                {"title": "沃德伦", "action": "↳ 做《沃德伦的领主》", "note": "《沃德伦的领主》：共享。西侧约(26.6,78.0)骑烈焰使者，领主在塔顶约(27.1,72.9)；贴到近身后优先卡CD用翼击眩晕，眩晕间隙补两种火焰技能，别在远距离吃弓箭/齐射。"},
                {"title": "征服堡", "action": "纳兹格利姆中士 → 交《沃德伦的领主》 → 接《前往欧尼瓦营地》\n征服者克雷娜 → 接《我的敌人的朋友》"},
            ],
            "action_html": [point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("前往征服堡，自求多福吧！",), accepts=("征服者的指派",)), npc_actions("纳兹格利姆中士", turns=("征服者的指派",), accepts=("缚焰者的秘密", "显示力量")), npc_actions("皮货商人休尼克", accepts=("灰狼的毛皮",)), npc_actions("粮食商人洛克兰", accepts=("赚外快",)), system_line("开飞行点：征服堡", "ra-flightpoint"), system_line("绑定炉石：征服堡", "ra-hearth"), do_at("征服堡南侧 / 沃德伦", "赚外快", "灰狼的毛皮", "缚焰者的秘密", "显示力量"), point_anchor("征服堡"), npc_actions("粮食商人洛克兰", turns=("赚外快",)), npc_actions("皮货商人休尼克", turns=("灰狼的毛皮",), accepts=("替代品",)), npc_actions("纳兹格利姆中士", turns=("缚焰者的秘密", "显示力量"), accepts=("沃德伦的领主",)), point_anchor("风险湾"), npc_actions("古图尔", accepts=("寻找溶解剂",)), do_line("寻找溶解剂"), npc_actions("古图尔", turns=("寻找溶解剂",)), do_at("沃德伦", "沃德伦的领主"), point_anchor("征服堡"), npc_actions("纳兹格利姆中士", turns=("沃德伦的领主",), accepts=("前往欧尼瓦营地",)), npc_actions("征服者克雷娜", accepts=("我的敌人的朋友",))],
            "note_html": notes_html(note_block("赚外快 / 灰狼的毛皮 / 缚焰者的秘密", status_span("不共享") + "任务物为个人掉落，五号分别拾取。"), note_block("显示力量", status_span("共享") + "击杀进度五号同步。"), note_block("寻找溶解剂", status_span("不共享") + "按单个场景物交互/拾取处理，五号依次获取 Element 115。拾取后立即原路返回古图尔，尽量避免战斗。"), note_block("沃德伦的领主", status_span("共享") + "西侧约(26.6,78.0)骑烈焰使者，领主在塔顶约(27.1,72.9)。贴到近身后优先卡CD用翼击眩晕，眩晕间隙补两种火焰技能；远距离会持续吃弓箭/齐射，反而更危险。")),
            "timingTaskNames": ["赚外快", "灰狼的毛皮", "缚焰者的秘密", "显示力量", "寻找溶解剂", "沃德伦的领主"],
        },
        2: {
            "title": "银溪镇 → 征服堡：克雷娜 / 高戈娜 / 休尼克",
            "summary": "银溪镇完成《我的敌人的朋友》并取得米克哈尔日记，北侧补灰熊皮；回征服堡按真实NPC推进克雷娜、高戈娜和休尼克三条线。",
            "points": [
                {"title": "银溪镇南侧", "action": "↳ 做《我的敌人的朋友》\n↳ 接《米克哈尔的日记》", "note": "《米克哈尔的日记》：来源怪为银溪猎人；击杀后拾取掉落的任务起始物“米克哈尔的日记”，五号分别右键接任务。离开前确认五号日志里都有任务。"},
                {"title": "银溪镇北侧", "action": "↳ 做《替代品》"},
                {"title": "征服堡", "action": "征服者克雷娜 → 交《我的敌人的朋友》《米克哈尔的日记》 → 接《攻击银溪镇》《高戈娜》\n高戈娜 → 交《高戈娜》 → 接《顺藤摸瓜》\n皮货商人休尼克 → 交《替代品》 → 接《休尼克的掩饰》"},
                {"title": "征服堡", "action": "皮货商人休尼克 → 交《休尼克的掩饰》 → 接《给克雷娜送货》\n征服者克雷娜 → 交《给克雷娜送货》\n风之先知希尔·灰角 → 接《白肩鹰的眼睛》\n苏尔肯中士 → 接《狩猎巨魔》", "note": "《休尼克的掩饰》：交任务前在征服堡商人购买5份面粉和1份煤块。"},
            ],
            "action_html": [do_at("银溪镇南侧", "我的敌人的朋友"), drop_accept_line("米克哈尔的日记"), do_at("银溪镇北侧", "替代品"), point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("我的敌人的朋友", "米克哈尔的日记"), accepts=("攻击银溪镇", "高戈娜")), npc_actions("高戈娜", turns=("高戈娜",), accepts=("顺藤摸瓜",)), npc_actions("皮货商人休尼克", turns=("替代品",), accepts=("休尼克的掩饰",)), npc_actions("皮货商人休尼克", turns=("休尼克的掩饰",), accepts=("给克雷娜送货",)), npc_actions("征服者克雷娜", turns=("给克雷娜送货",)), npc_actions("风之先知希尔·灰角", accepts=("白肩鹰的眼睛",)), npc_actions("苏尔肯中士", accepts=("狩猎巨魔",))],
            "note_html": notes_html(note_block("米克哈尔的日记", "来源怪为银溪猎人；击杀后拾取掉落的任务起始物“米克哈尔的日记”，五号分别右键接任务。离开前确认五号日志里都有任务。"), note_block("休尼克的掩饰", "交任务前在征服堡商人购买5份面粉和1份煤块。")),
            "timingTaskNames": ["我的敌人的朋友", "米克哈尔的日记", "替代品"],
        },
        3: {
            "title": "花岗岩之泉 → 达库鲁火盆 → 古树之心 → Drak'atal",
            "summary": "萨米尔/达库鲁/普雷蒙/马克分别推进巨魔链；两处达库鲁火盆完成象形文字与牺牲，古树之心交宝石，Drak'atal由达库鲁影像接出《灰尘之声》。",
            "points": [
                {"title": "花岗岩之泉", "action": "萨米尔 → 交《狩猎巨魔》 → 接《抓巨魔》\n↳ 做《抓巨魔》\n萨米尔 → 交《抓巨魔》\n达库鲁 → 接《停战？》\n↳ 做《停战？》\n达库鲁 → 交《停战？》 → 接《幻象之瓶》", "fivebox": ""},
                {"title": "花岗岩之泉北侧", "action": "↳ 做《幻象之瓶》\n达库鲁 → 交《幻象之瓶》 → 接《解读象形文字》", "note": "《幻象之瓶》：不共享：水草叶、3片朦胧叶和水晶瓶都齐再离开；水晶瓶在花岗岩之泉商人购买，一次购买直接得到5个，只需买一次。"},
                {"title": "花岗岩之泉", "action": "普雷蒙 → 接《清理天灾》《蘑菇汤！》\n↳ 做《清理天灾》\n马克·菲尔森 → 交《清理天灾》 → 接《净化天灾巨魔》"},
                {"title": "达库鲁火盆·南侧", "action": "↳ 做《解读象形文字》\n达库鲁的影像 → 交《解读象形文字》 → 接《必要的牺牲》", "note": "《解读象形文字》：不共享：冰冻魔精可交易；每号都要自己在火盆使用药剂召唤达库鲁影像，召唤NPC不共享。当前号背包里若还有超过任务所需的多余冰冻魔精会无法正常交任务，交前先把多余魔精移走。"},
                {"title": "Zeb'Halak", "action": "↳ 做《必要的牺牲》《蘑菇汤！》", "note": "《必要的牺牲》：不共享：所需魔精由五号依次拾取，预言者之眼也需要五号依次交互取得，再分别到火盆完成交付。"},
                {"title": "达库鲁火盆·北侧", "action": "达库鲁的影像 → 交《必要的牺牲》 → 接《古树精华宝石》"},
                {"title": "达克萨隆外", "action": "↳ 做《净化天灾巨魔》\n被囚禁的猎户 → 交《顺藤摸瓜》"},
                {"title": "银溪北侧 / 古树之心", "action": "↳ 做《攻击银溪镇》\nHeart of the Ancients → 交《古树精华宝石》 → 接《尽在掌控》"},
                {"title": "Drak'atal Passage", "action": "达库鲁的影像 → 交《尽在掌控》 → 接《灰尘之声》", "note": "《灰尘之声》先携带，进入Drakil'jin遗迹再完成。"},
                {"title": "征服堡", "action": "使用炉石：征服堡"},
            ],
            "action_html": [point_anchor("花岗岩之泉"), npc_actions("萨米尔", turns=("狩猎巨魔",), accepts=("抓巨魔",)), do_line("抓巨魔"), npc_actions("萨米尔", turns=("抓巨魔",)), npc_actions("达库鲁", accepts=("停战？",)), do_line("停战？"), npc_actions("达库鲁", turns=("停战？",), accepts=("幻象之瓶",)), do_at("花岗岩之泉北侧", "幻象之瓶"), npc_actions("达库鲁", turns=("幻象之瓶",), accepts=("解读象形文字",)), point_anchor("花岗岩之泉"), npc_actions("普雷蒙", accepts=("清理天灾", "蘑菇汤！")), do_line("清理天灾"), npc_actions("马克·菲尔森", turns=("清理天灾",), accepts=("净化天灾巨魔",)), do_at("达库鲁火盆·南侧", "解读象形文字"), npc_actions("达库鲁的影像", turns=("解读象形文字",), accepts=("必要的牺牲",)), do_at("Zeb'Halak", "必要的牺牲", "蘑菇汤！"), npc_actions("达库鲁的影像", turns=("必要的牺牲",), accepts=("古树精华宝石",)), do_at("达克萨隆外", "净化天灾巨魔"), npc_actions("被囚禁的猎户", turns=("顺藤摸瓜",)), do_at("银溪北侧", "攻击银溪镇"), npc_actions("Heart of the Ancients", turns=("古树精华宝石",), accepts=("尽在掌控",)), point_anchor("Drak'atal Passage"), npc_actions("达库鲁的影像", turns=("尽在掌控",), accepts=("灰尘之声",)), system_line("使用炉石：征服堡", "ra-hearth")],
            "note_html": notes_html(note_block("抓巨魔", status_span("共享") + "先在花岗岩之泉帐篷里与Budd对话让他跟随；到西南巨魔营地后先找一只落单目标，不要由玩家先攻击。用Budd宠物栏的Tag Troll把目标打晕，立刻靠近对昏迷巨魔使用赏金猎人的笼子；施放笼子时被其他怪打会中断，失败通常要回营地重新带Budd。"), note_block("停战？", status_span("共享") + "任务刀就在达库鲁笼子旁的树桩；拾取/使用钝刻刀完成割手动作后，再与达库鲁对话完成血契。"), note_block("幻象之瓶", status_span("不共享") + "水草叶、3片朦胧叶和水晶瓶都齐再离开；水晶瓶在花岗岩之泉商人购买，一次购买直接得到5个，只需买一次。"), note_block("清理天灾", status_span("共享") + "木乃伊就在花岗岩之泉营地附近。"), note_block("净化天灾巨魔", "对达克萨隆外成群的饥饿天灾巨魔使用马克的黑暗烈酒；任务道具为远程投掷，站台阶/高处往怪群里扔比冲进怪堆更稳。"), note_block("蘑菇汤！", status_span("不共享") + "蛇眼、雪帽和甜根在北侧区域采集。"), note_block("解读象形文字", status_span("不共享") + "冰冻魔精可交易；每号都要自己在火盆使用药剂召唤达库鲁影像，召唤NPC不共享。当前号背包若还有超过任务所需的多余冰冻魔精会无法正常交任务，交前先移走多余魔精。"), note_block("必要的牺牲", status_span("不共享") + "所需魔精由五号依次拾取，预言者之眼也要五号依次交互取得，再分别到火盆完成交付。")),
            "timingTaskNames": ["抓巨魔", "停战？", "幻象之瓶", "清理天灾", "净化天灾巨魔", "解读象形文字", "必要的牺牲", "蘑菇汤！", "古树精华宝石", "攻击银溪镇"],
        },
        4: {
            "title": "征服斗兽场 → 沃达希尔三洞 → 盲眼卢娜",
            "summary": "征服堡按克雷娜、高戈娜、灰角和格里尼克斯分别交接；斗兽场五连按真实交付NPC推进，再清沃达希尔三洞和盲眼卢娜链。",
            "points": [
                {"title": "征服堡", "action": "征服者克雷娜 → 交《攻击银溪镇》\n高戈娜 → 接《盲眼卢娜》\n风之先知希尔·灰角 → 接《沃达希尔的陨落》《地下的黑暗》\n格里尼克斯·西维格 → 接《征服斗兽场：斗熊！》"},
                {"title": "征服斗兽场", "action": "↳ 做《征服斗兽场：斗熊！》\n赌徒维尔金 → 交《征服斗兽场：斗熊！》\n格里尼克斯·西维格 → 接《征服斗兽场：疯狂的熊怪》\n↳ 做《征服斗兽场：疯狂的熊怪》\n赌徒维尔金 → 交《征服斗兽场：疯狂的熊怪》\n格里尼克斯·西维格 → 接《征服斗兽场：鲜血与金属》\n↳ 做《征服斗兽场：鲜血与金属》\n赌徒维尔金 → 交《征服斗兽场：鲜血与金属》\n格里尼克斯·西维格 → 接《征服斗兽场：九死一生》\n↳ 做《征服斗兽场：九死一生》\n赌徒维尔金 → 交《征服斗兽场：九死一生》\n格里尼克斯·西维格 → 接《征服斗兽场：摊牌》\n↳ 做《征服斗兽场：摊牌》\n高戈娜 → 交《征服斗兽场：摊牌》", "note": "五连均共享；前四轮交赌徒维尔金并回格里尼克斯接下一轮，最后《摊牌》交高戈娜。《疯狂的熊怪》由防骑单挑最稳，关键是全程持续跑动拉开，不要停下来和图腾硬耗；打断闪电链即可。", "fivebox": ""},
                {"title": "花岗岩之泉", "action": "马克·菲尔森 → 交《净化天灾巨魔》\n普雷蒙 → 交《蘑菇汤！》 → 接《跟我的小朋友打招呼》"},
                {"title": "沃达希尔三洞", "action": "↳ 做《沃达希尔的陨落》《地下的黑暗》《白肩鹰的眼睛》", "note": "《沃达希尔的陨落》不共享：五号分别收集6份软泥样本；《地下的黑暗》共享：三处洞穴到尽头黑烟前使用任务宝珠，主号完成即可同步；《白肩鹰的眼睛》共享，可沿三洞路线顺手完成。"},
                {"title": "盲眼卢娜", "action": "盲眼卢娜 → 交《盲眼卢娜》 → 接《卢娜的要求》\n↳ 做《卢娜的要求》\n盲眼卢娜 → 交《卢娜的要求》 → 接《梦游体验》\n↳ 做《梦游体验》\n盲眼卢娜 → 交《梦游体验》 → 接《命运与巧合》", "note": "《卢娜的要求》不共享，五号分别收集4份薄纱之尘。《梦游体验》不共享，五号分别在卢娜水晶球旁喝药并看完整视觉事件；若效果不自动结束，再取消buff。"},
            ],
            "action_html": [point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("攻击银溪镇",)), npc_actions("高戈娜", accepts=("盲眼卢娜",)), npc_actions("风之先知希尔·灰角", accepts=("沃达希尔的陨落", "地下的黑暗")), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：斗熊！",)), do_at("征服斗兽场", "征服斗兽场：斗熊！"), npc_actions("赌徒维尔金", turns=("征服斗兽场：斗熊！",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：疯狂的熊怪",)), do_line("征服斗兽场：疯狂的熊怪"), npc_actions("赌徒维尔金", turns=("征服斗兽场：疯狂的熊怪",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：鲜血与金属",)), do_line("征服斗兽场：鲜血与金属"), npc_actions("赌徒维尔金", turns=("征服斗兽场：鲜血与金属",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：九死一生",)), do_line("征服斗兽场：九死一生"), npc_actions("赌徒维尔金", turns=("征服斗兽场：九死一生",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：摊牌",)), do_line("征服斗兽场：摊牌"), npc_actions("高戈娜", turns=("征服斗兽场：摊牌",)), point_anchor("花岗岩之泉"), npc_actions("马克·菲尔森", turns=("净化天灾巨魔",)), npc_actions("普雷蒙", turns=("蘑菇汤！",), accepts=("跟我的小朋友打招呼",)), do_at("沃达希尔三洞", "沃达希尔的陨落", "地下的黑暗", "白肩鹰的眼睛"), point_anchor("盲眼卢娜"), npc_actions("盲眼卢娜", turns=("盲眼卢娜",), accepts=("卢娜的要求",)), do_line("卢娜的要求"), npc_actions("盲眼卢娜", turns=("卢娜的要求",), accepts=("梦游体验",)), do_line("梦游体验"), npc_actions("盲眼卢娜", turns=("梦游体验",), accepts=("命运与巧合",))],
            "note_html": notes_html(note_block("征服斗兽场：斗熊！", status_span("共享") + "五连第一场。前四场由开启任务事件的人先吃初始仇恨，防骑/主控号优先启动最省事；铁皮按普通单体Boss处理。"), note_block("征服斗兽场：疯狂的熊怪", status_span("共享") + "首组实跑最稳打法：防骑单挑，全程持续绕场跑动拉开；不要停下来和图腾硬耗，打断闪电链即可。"), note_block("征服斗兽场：鲜血与金属", status_span("共享") + "锈血会频繁击退，击退后可能转向第二仇恨；五号不要贴斗兽场边缘，主控被击退后立即回身重新接怪。"), note_block("征服斗兽场：九死一生", status_span("共享") + "霍格伦·地狱劈砍是五连高压点：会旋风斩、冲锋并伴随仇恨切换。全队平时靠近Boss，看到旋风斩再退；防骑随时准备嘲讽/重新接怪并提前开减伤。"), note_block("征服斗兽场：摊牌", status_span("共享") + "克雷娜带两名护卫，高戈娜会协助。克雷娜有顺劈、短晕和锁定加速；优先控/清两名护卫，主控让Boss背对跟随号。打完立即向高戈娜交任务，避免下一场斗兽场事件波及NPC。"), note_block("沃达希尔的陨落", status_span("不共享") + "实际目标是熵能软泥：三处洞穴区域任选/顺路击杀，五号分别收集6份软泥样本。"), note_block("地下的黑暗", status_span("共享") + "三洞黑烟分别在沃达希尔之泪约(28,44)、枝干约(33,48)、心脏约(40,52)；每处进洞到尽头黑烟前由主号使用宝珠即可同步五号。"), note_block("白肩鹰的眼睛", status_span("共享") + "与沃达希尔三洞同片完成；沿三洞路线对白肩鹰使用银色羽毛，主号完成6只即可同步五号。"), note_block("卢娜的要求", status_span("不共享") + "五号分别从东北的蕨叶蛾收集4份薄纱之尘。"), note_block("梦游体验", status_span("不共享") + "五号分别在卢娜水晶球旁使用薄纱药剂并等待视觉事件完成；若事件结束后效果仍不退出，再取消buff。")),
            "timingTaskNames": ["征服斗兽场：斗熊！", "征服斗兽场：疯狂的熊怪", "征服斗兽场：鲜血与金属", "征服斗兽场：九死一生", "征服斗兽场：摊牌", "沃达希尔的陨落", "地下的黑暗", "白肩鹰的眼睛", "卢娜的要求", "梦游体验"],
        },
        5: {
            "title": "欧尼瓦 → 索尔莫丹 → 征服堡 → 欧尼瓦",
            "summary": "欧尼瓦首次按沃塔肯、索鲁克、托尔玛克分别交接并开点；东北做驯鹿/野马/鱼群，索尔莫丹收日记书页，炉石征服堡后再系统飞回欧尼瓦交任务。",
            "points": [
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《前往欧尼瓦营地》 → 接《新的盟友》\n索鲁克·雷怒 → 接《惊吓野马》\n托尔玛克 → 接《不速之“客”》\n开飞行点：欧尼瓦营地"},
                {"title": "欧尼瓦东北", "action": "↳ 做《不速之“客”》《惊吓野马》\n休·格兰斯 → 接《熊的美食》\n↳ 做《熊的美食》", "note": "《熊的美食》不共享：五号分别对鱼群使用任务渔网，不需要钓鱼专业。", "fivebox": ""},
                {"title": "索尔莫丹外", "action": "↳ 接《破损的日记》\n↳ 做《破损的日记》", "note": "《破损的日记》：不共享。索尔莫丹外约(64.3,19.8)五号分别拾取地面的破损日记并接任务；书页就在周围战场地面，每号分别收集8张，最后各自在背包把书页与不完整日记合成完整日记再下山。", "fivebox": ""},
                {"title": "征服堡", "action": "使用炉石：征服堡\n风之先知希尔·灰角 → 交《白肩鹰的眼睛》《沃达希尔的陨落》《地下的黑暗》 → 接《可能的关联》《熊神的后代》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地\n托尔玛克 → 交《不速之“客”》 → 接《有趣的计划》\n索鲁克·雷怒 → 交《惊吓野马》\n休·格兰斯 → 交《熊的美食》"},
                {"title": "欧尼瓦营地", "action": "先知帕鲁纳 → 交《破损的日记》 → 接《翻译日记》"},
            ],
            "action_html": [point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("前往欧尼瓦营地",), accepts=("新的盟友",)), npc_actions("索鲁克·雷怒", accepts=("惊吓野马",)), npc_actions("托尔玛克", accepts=("不速之“客”",)), system_line("开飞行点：欧尼瓦营地", "ra-flightpoint"), do_at("欧尼瓦东北", "不速之“客”", "惊吓野马"), npc_actions("休·格兰斯", accepts=("熊的美食",)), do_line("熊的美食"), point_anchor("索尔莫丹外"), drop_accept_line("破损的日记"), do_line("破损的日记"), system_line("使用炉石：征服堡", "ra-hearth"), npc_actions("风之先知希尔·灰角", turns=("白肩鹰的眼睛", "沃达希尔的陨落", "地下的黑暗"), accepts=("可能的关联", "熊神的后代")), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("托尔玛克", turns=("不速之“客”",), accepts=("有趣的计划",)), npc_actions("索鲁克·雷怒", turns=("惊吓野马",)), npc_actions("休·格兰斯", turns=("熊的美食",)), npc_actions("先知帕鲁纳", turns=("破损的日记",), accepts=("翻译日记",))],
            "note_html": notes_html(note_block("熊的美食", status_span("不共享") + "五号分别对东风海岸发光鱼群使用任务渔网，不需要钓鱼专业。"), note_block("破损的日记", status_span("不共享") + "索尔莫丹外约(64.3,19.8)五号分别拾取破损日记并接任务；缺失书页就在周围战场地面，每号分别收集8张，最后各自在背包合成完整日记再离开。")),
            "timingTaskNames": ["不速之“客”", "惊吓野马", "熊的美食", "破损的日记"],
        },
        6: {
            "title": "欧尼瓦南侧 → 征服堡灰角 → 欧尼瓦",
            "summary": "欧尼瓦南侧完成翻译日记、熊怪血液和熊神子嗣；回征服堡只找灰角交接，再系统飞欧尼瓦分别找帕鲁纳和沃塔肯接索尔莫丹任务。",
            "points": [
                {"title": "欧尼瓦南侧", "action": "↳ 做《翻译日记》《可能的关联》《熊神的后代》", "note": "《翻译日记》目标只需击杀一次，五号依次拾取；《可能的关联》推荐在约(54.2,41.9)灰喉堡上山入口右侧水域附近刷；《熊神的后代》共享。"},
                {"title": "征服堡", "action": "风之先知希尔·灰角 → 交《可能的关联》《熊神的后代》 → 接《摧毁树苗》《沃达希尔的种子》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地\n先知帕鲁纳 → 交《翻译日记》 → 接《符文中的预言》\n斥候沃塔肯 → 接《“钢铁之子”》"},
            ],
            "action_html": [do_at("欧尼瓦南侧", "翻译日记", "可能的关联", "熊神的后代"), point_anchor("征服堡"), npc_actions("风之先知希尔·灰角", turns=("可能的关联", "熊神的后代"), accepts=("摧毁树苗", "沃达希尔的种子")), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("先知帕鲁纳", turns=("翻译日记",), accepts=("符文中的预言",)), npc_actions("斥候沃塔肯", accepts=("“钢铁之子”",))],
            "note_html": notes_html(note_block("翻译日记", "目标不是采草：到鲜血之心祭坛找独眼格鲁巴德；只需击杀一次，同一尸体可由五号依次拾取灵息草。"), note_block("可能的关联", "推荐刷点约(54.2,41.9)，在灰喉堡上山入口右侧水域附近。"), note_block("熊神的后代", status_span("共享") + "与《可能的关联》同片处理；奥尔松洞口约(48.5,58.2)，科迪安洞口约(66.7,61.5)。")),
            "timingTaskNames": ["翻译日记", "可能的关联", "熊神的后代"],
        },
        7: {
            "title": "库伦 / 索尔莫丹 → 哈考尔 / 加弗洛克 → 欧尼瓦",
            "summary": "库伦三连后在索尔莫丹同时完成铁矮人和符文板；再去哈考尔/克拉斯、加弗洛克接任务，最后回欧尼瓦分别向沃塔肯和帕鲁纳交接。",
            "points": [
                {"title": "库伦", "action": "库伦 → 交《新的盟友》 → 接《巨石横飞》\n↳ 做《巨石横飞》\n库伦 → 交《巨石横飞》 → 接《鼓舞士气》\n↳ 做《鼓舞士气》\n库伦 → 交《鼓舞士气》 → 接《攻破防线》", "note": "《巨石横飞》《鼓舞士气》均共享；主号完成即可同步五号。"},
                {"title": "索尔莫丹", "action": "↳ 做《攻破防线》《“钢铁之子”》《符文中的预言》", "note": "《符文中的预言》共享：三块符文板由主号读取即可同步五号。", "fivebox": ""},
                {"title": "库伦", "action": "库伦 → 交《攻破防线》 → 接《加弗洛克》"},
                {"title": "哈考尔 / 克拉斯", "action": "哈考尔 → 交《跟我的小朋友打招呼》 → 接《等肉下锅》《心灵的创伤》\n克拉斯 → 接《孤胆英雄……》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《加弗洛克》 → 接《压制符文》"},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《“钢铁之子”》 → 接《以洛肯之名》\n先知帕鲁纳 → 交《符文中的预言》", "note": "《以洛肯之名》先找休·格兰斯对话，再去加弗洛克完成剩余对话。"},
            ],
            "action_html": [point_anchor("库伦"), npc_actions("库伦", turns=("新的盟友",), accepts=("巨石横飞",)), do_line("巨石横飞"), npc_actions("库伦", turns=("巨石横飞",), accepts=("鼓舞士气",)), do_line("鼓舞士气"), npc_actions("库伦", turns=("鼓舞士气",), accepts=("攻破防线",)), do_at("索尔莫丹", "攻破防线", "“钢铁之子”", "符文中的预言"), npc_actions("库伦", turns=("攻破防线",), accepts=("加弗洛克",)), point_anchor("哈考尔 / 克拉斯"), npc_actions("哈考尔", turns=("跟我的小朋友打招呼",), accepts=("等肉下锅", "心灵的创伤")), npc_actions("克拉斯", accepts=("孤胆英雄……",)), npc_actions("加弗洛克", turns=("加弗洛克",), accepts=("压制符文",)), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("“钢铁之子”",), accepts=("以洛肯之名",)), npc_actions("先知帕鲁纳", turns=("符文中的预言",))],
            "note_html": notes_html(note_block("巨石横飞", status_span("共享") + "先在库伦附近/山脊边捡巨石；站在索尔莫丹北缘高处直接向沟内铁矮人投掷，不要为了命中目标跳进沟里，主号完成即可同步五号。"), note_block("鼓舞士气", status_span("共享") + "只对正在与符文巨人交战的友方灰熊丘陵巨人使用大地碎片；成功后会出现铁符文复仇者，立刻击杀。尽量选血量健康的友方巨人，避免它先死后符文巨人转火。"), note_block("攻破防线", "铁领主阿格鲁姆在索尔莫丹沟槽东北端约(70.4,12.8)，沟槽入口约(65,20)。狭窄隧道里别让五号同时挤着吃怪：先让防骑/主控接住，再把跟随号带进来。"), note_block("符文中的预言", status_span("共享") + "三块符文板都在索尔莫丹水道/隧道约68—70,15—16；站到每块符文板前由主号使用符文钥石读取即可同步五号。")),
            "timingTaskNames": ["巨石横飞", "鼓舞士气", "攻破防线", "“钢铁之子”", "符文中的预言"],
        },
        8: {
            "title": "萨莎 → 灰喉堡 → 乌索克 → 安娅 / 萨莎",
            "summary": "萨莎村推进猎杀与阿纳托雷；灰喉堡做树苗/种子后炉石征服堡接乌索克，系统飞欧尼瓦再去乌索克；完成后回欧尼瓦乘系统鸟交付，再找安娅、萨莎和休·格兰斯。",
            "points": [
                {"title": "萨莎", "action": "萨莎 → 交《命运与巧合》 → 接《萨莎的狩猎》《阿纳托雷》\n↳ 做《萨莎的狩猎》《阿纳托雷》\n萨莎 → 交《萨莎的狩猎》《阿纳托雷》 → 接《姐姐的誓言》", "note": "《阿纳托雷》不共享：去至日村找塔季娅娜，对她使用镇静飞镖触发坐骑/带回脚本；一个号完成后其余号留在原地等塔季娅娜刷新，再依次完成。"},
                {"title": "灰喉堡", "action": "↳ 做《摧毁树苗》《沃达希尔的种子》", "note": "两项都不共享；五号分别烧树苗、分别拾取种子。做完直接炉石回征服堡。", "fivebox": ""},
                {"title": "征服堡", "action": "使用炉石：征服堡\n风之先知希尔·灰角 → 交《摧毁树苗》《沃达希尔的种子》 → 接《乌索克，巨熊之神》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地"},
                {"title": "乌索克", "action": "↳ 做《乌索克，巨熊之神》", "note": "共享。击败乌索克后对尸体使用净化灰烬；1防骑+4惩戒可让NPC助手负责治疗。", "fivebox": ""},
                {"title": "欧尼瓦营地", "action": "系统飞行：欧尼瓦营地 → 征服堡"},
                {"title": "征服堡", "action": "风之先知希尔·灰角 → 交《乌索克，巨熊之神》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地"},
                {"title": "安娅", "action": "安娅 → 交《姐姐的誓言》"},
                {"title": "萨莎", "action": "萨莎 → 接《狼人的末日》"},
                {"title": "休·格兰斯", "action": "与休·格兰斯对话，推进《以洛肯之名》"},
            ],
            "action_html": [point_anchor("萨莎"), npc_actions("萨莎", turns=("命运与巧合",), accepts=("萨莎的狩猎", "阿纳托雷")), do_line("萨莎的狩猎", "阿纳托雷"), npc_actions("萨莎", turns=("萨莎的狩猎", "阿纳托雷"), accepts=("姐姐的誓言",)), do_at("灰喉堡", "摧毁树苗", "沃达希尔的种子"), system_line("使用炉石：征服堡", "ra-hearth"), npc_actions("风之先知希尔·灰角", turns=("摧毁树苗", "沃达希尔的种子"), accepts=("乌索克，巨熊之神",)), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), do_at("乌索克", "乌索克，巨熊之神"), point_anchor("欧尼瓦营地"), system_line("系统飞行：欧尼瓦营地 → 征服堡", "ra-flightpath"), npc_actions("风之先知希尔·灰角", turns=("乌索克，巨熊之神",)), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("安娅", turns=("姐姐的誓言",)), npc_actions("萨莎", accepts=("狼人的末日",)), task_text_line("与休·格兰斯对话，推进 ", "以洛肯之名")],
            "note_html": notes_html(note_block("阿纳托雷", status_span("不共享") + "目标其实是至日村的塔季娅娜，不是对阿纳托雷本人使用道具。对塔季娅娜使用镇静飞镖后会触发坐骑/带回脚本；一个号完成后其它号留在原地等她刷新，再依次完成。"), note_block("摧毁树苗", status_span("不共享") + "沃达希尔树苗在灰喉堡内部底层约(51,43)；五号分别到树苗前使用青翠火炬。两项灰喉堡任务做完后直接炉石回征服堡。"), note_block("沃达希尔的种子", status_span("不共享") + "种子在灰喉堡大树周围的熊怪营地地面拾取，五号分别拾取。"), note_block("乌索克，巨熊之神", status_span("共享") + "开打前与NPC助手图尔对话选择职责；1防骑+4惩戒适合让图尔负责治疗、主控自己坦Boss。图尔会被控/眩晕，治疗断档时提前开减伤；击杀后对尸体使用净化灰烬。")),
            "timingTaskNames": ["萨莎的狩猎", "阿纳托雷", "摧毁树苗", "沃达希尔的种子", "乌索克，巨熊之神", "以洛肯之名"],
        },
        9: {
            "title": "符文监督者 → Drakil'jin墓穴多次往返 → 血月岛 → 加弗洛克",
            "summary": "监督者后进入Drakil'jin；先完成罐子/石板，再由哈里森接护送。墓穴链按克拉斯↔墓穴真实往返执行，随后血月岛完成狼人并回萨莎交，最后到加弗洛克。",
            "points": [
                {"title": "符文监督者", "action": "↳ 做《压制符文》《心灵的创伤》", "note": "每名监督者都要先击杀正在引导的铁符文织法者才会出现；《等肉下锅》这里只沿路累计，最后在符文巨人平原补齐。"},
                {"title": "Drakil'jin遗迹", "action": "↳ 做《孤胆英雄……》《灰尘之声》\n达库鲁的影像 → 交《灰尘之声》\n哈里森·琼斯 → 接《喔——哒！！》\n↳ 做《喔——哒！！》", "note": "启动护送前先确认《孤胆英雄……》《灰尘之声》的遗迹内目标已完成。"},
                {"title": "哈考尔 / 克拉斯", "action": "哈考尔 → 交《心灵的创伤》《喔——哒！！》\n克拉斯 → 交《孤胆英雄……》 → 接《达卡古尔之槌》"},
                {"title": "达卡古尔", "action": "↳ 做《达卡古尔之槌》"},
                {"title": "克拉斯", "action": "克拉斯 → 交《达卡古尔之槌》 → 接《死后相见》"},
                {"title": "Drakil'jin墓穴", "action": "↳ 做《死后相见》\n甘休 → 交《死后相见》 → 接《冷静一下，伙计》\n↳ 做《冷静一下，伙计》", "note": "《死后相见》敲锣时完成进度共享，但五号仍必须分别敲锣进入脚本，否则未亲自触发的号无法交任务；《冷静一下，伙计》不共享，五号分别完成。", "fivebox": ""},
                {"title": "克拉斯", "action": "克拉斯 → 交《冷静一下，伙计》 → 接《金亚拉克的末日》"},
                {"title": "Drakil'jin墓穴", "action": "↳ 做《金亚拉克的末日》", "note": "共享；按任务流程灌注供品并在墓穴外锣旁完成最终事件即可。", "fivebox": ""},
                {"title": "克拉斯", "action": "克拉斯 → 交《金亚拉克的末日》"},
                {"title": "血月岛", "action": "↳ 做《狼人的末日》", "note": "共享；按三前置Boss → 阿鲁高之影的脚本顺序完成即可。", "fivebox": ""},
                {"title": "萨莎", "action": "萨莎 → 交《狼人的末日》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《压制符文》 → 接《潜在的能量》\n加弗洛克 → 做《以洛肯之名》\n↳ 做《潜在的能量》", "note": "《以洛肯之名》《潜在的能量》均共享。"},
            ],
            "action_html": [do_at("符文监督者", "压制符文", "心灵的创伤"), do_at("Drakil'jin遗迹", "孤胆英雄……", "灰尘之声"), npc_actions("达库鲁的影像", turns=("灰尘之声",)), npc_actions("哈里森·琼斯", accepts=("喔——哒！！",)), do_line("喔——哒！！"), point_anchor("哈考尔 / 克拉斯"), npc_actions("哈考尔", turns=("心灵的创伤", "喔——哒！！")), npc_actions("克拉斯", turns=("孤胆英雄……",), accepts=("达卡古尔之槌",)), do_at("达卡古尔", "达卡古尔之槌"), npc_actions("克拉斯", turns=("达卡古尔之槌",), accepts=("死后相见",)), do_at("Drakil'jin墓穴", "死后相见"), npc_actions("甘休", turns=("死后相见",), accepts=("冷静一下，伙计",)), do_line("冷静一下，伙计"), npc_actions("克拉斯", turns=("冷静一下，伙计",), accepts=("金亚拉克的末日",)), do_at("Drakil'jin墓穴", "金亚拉克的末日"), npc_actions("克拉斯", turns=("金亚拉克的末日",)), do_at("血月岛", "狼人的末日"), npc_actions("萨莎", turns=("狼人的末日",)), point_anchor("加弗洛克"), npc_actions("加弗洛克", turns=("压制符文",), accepts=("潜在的能量",)), npc_do_line("加弗洛克", "以洛肯之名"), do_line("潜在的能量")],
            "note_html": notes_html(note_block("压制符文", "四名符文监督者从西到东南依次约在(67.7,29.3)/(71.9,34.0)/(75.1,37.2)/(78.7,43.8)。到每个符文点先杀围着符文引导的4名铁符文织法者，监督者才会刷新；不要只杀一只就等Boss。"), note_block("孤胆英雄……", status_span("不共享") + "Drakil'jin墓穴入口区约(71,23)有达卡莱罐子；五号分别完成，拾取罐子会引到附近古代达卡莱亡灵，进门前先让主控接住周围怪。"), note_block("喔——哒！！", "启动哈里森·琼斯护送前，先确认《孤胆英雄……》《灰尘之声》的遗迹内目标已经做完；护送按五开通则一次即可共同完成。"), note_block("达卡古尔之槌", "达卡古尔会沿Drakil'jin遗迹道路巡逻，不必守一个固定点；沿主路找即可。"), note_block("死后相见", status_span("共享") + "敲锣触发时任务完成进度会同步，但五个角色仍必须分别敲锣进入死亡脚本，否则未亲自触发的角色无法交任务。"), note_block("冷静一下，伙计", status_span("不共享") + "从甘休旁箱子取永恒沉睡之雪，恢复活人后对古代达卡莱之魂使用；目标跑开并燃烧后跟过去拾取灵魂微粒，五号分别完成。"), note_block("金亚拉克的末日", status_span("共享") + "神圣达卡莱供品在墓穴第一个大房间约(71,19)；用达卡莱灵魂之尘灌注后带到墓穴外锣旁完成事件。"), note_block("狼人的末日", status_span("共享") + "先杀塞拉斯、瓦拉姆、污血之喉，再上塔打阿鲁高之影；三个前置Boss缺一不可。阿鲁高约75%血开盾并出3只小怪，约50%心控队友，约25%再出一波小怪；全程留在塔顶平台，跑下平台容易重置。"), note_block("以洛肯之名", status_span("共享") + "先与休·格兰斯对话，再到加弗洛克完成剩余对话；首组确认进度共享。"), note_block("潜在的能量", status_span("共享") + "三块潜能石在加弗洛克西侧一圈，常用顺序约(78,39)→(74,44)→(71,39)；到石头旁使用加弗洛克碎片即可。")),
            "timingTaskNames": ["压制符文", "心灵的创伤", "孤胆英雄……", "灰尘之声", "喔——哒！！", "达卡古尔之槌", "死后相见", "冷静一下，伙计", "金亚拉克的末日", "狼人的末日", "潜在的能量"],
        },
        10: {
            "title": "欧尼瓦 ↔ Dun Argol：沃塔肯 / 罗卡尔 / 托尔玛克",
            "summary": "《以洛肯之名》交沃塔肯并接制服线；《有趣的计划》交罗卡尔并接零件/能源线。Dun Argol多次往返按真实NPC推进，最终铁领主交托尔玛克、洛肯命令交沃塔肯。",
            "points": [
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《以洛肯之名》 → 接《监工的制服》"},
                {"title": "Dun Argol", "action": "↳ 做《监工的制服》《有趣的计划》", "note": "《监工的制服》目标打一次后五号依次拾取；《有趣的计划》不共享，三张蓝图为个人掉落，五号分别收集并在背包合成；最下方建筑内任务怪最密。", "fivebox": ""},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《监工的制服》 → 接《活灵活现》\n勘探员罗卡尔 → 交《有趣的计划》 → 接《收集零件》"},
                {"title": "Dun Argol", "action": "↳ 做《活灵活现》《收集零件》", "note": "《活灵活现》共享；《收集零件》不共享，五号分别拾取零件。"},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《活灵活现》 → 接《洛肯的命令》\n勘探员罗卡尔 → 交《收集零件》 → 接《我们有能源》"},
                {"title": "Dun Argol上层", "action": "↳ 做《我们有能源》《洛肯的命令》", "note": "《我们有能源》两名目标各打一次，同一尸体能量核心由五号依次拾取；《洛肯的命令》共享。读取基座后保持已完成未交，伪装留到铁领主结束。", "fivebox": ""},
                {"title": "欧尼瓦营地", "action": "勘探员罗卡尔 → 交《我们有能源》 → 接《……我们没有能源》"},
                {"title": "Dun Argol外围", "action": "↳ 做《……我们没有能源》", "note": "共享。五个角色分别召出的战争魔像都能对同一只闪电斥候各记1次充能；一只怪可直接记5次，两只怪即可完成全队。"},
                {"title": "欧尼瓦营地", "action": "勘探员罗卡尔 → 交《……我们没有能源》 → 接《击败铁领主》"},
                {"title": "Dun Argol上层", "action": "↳ 做《击败铁领主》", "note": "共享。穿伪装上楼/乘电梯，使用魔像控制器；铁领主死亡后继续利用魔像/载具离开。", "fivebox": ""},
                {"title": "欧尼瓦营地", "action": "托尔玛克 → 交《击败铁领主》\n斥候沃塔肯 → 交《洛肯的命令》"},
            ],
            "action_html": [point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("以洛肯之名",), accepts=("监工的制服",)), do_at("Dun Argol", "监工的制服", "有趣的计划"), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("监工的制服",), accepts=("活灵活现",)), npc_actions("勘探员罗卡尔", turns=("有趣的计划",), accepts=("收集零件",)), do_at("Dun Argol", "活灵活现", "收集零件"), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("活灵活现",), accepts=("洛肯的命令",)), npc_actions("勘探员罗卡尔", turns=("收集零件",), accepts=("我们有能源",)), do_at("Dun Argol上层", "我们有能源", "洛肯的命令"), point_anchor("欧尼瓦营地"), npc_actions("勘探员罗卡尔", turns=("我们有能源",), accepts=("……我们没有能源",)), do_at("Dun Argol外围", "……我们没有能源"), point_anchor("欧尼瓦营地"), npc_actions("勘探员罗卡尔", turns=("……我们没有能源",), accepts=("击败铁领主",)), do_at("Dun Argol上层", "击败铁领主"), point_anchor("欧尼瓦营地"), npc_actions("托尔玛克", turns=("击败铁领主",)), npc_actions("斥候沃塔肯", turns=("洛肯的命令",))],
            "note_html": notes_html(note_block("有趣的计划", status_span("不共享") + "三张蓝图为个人掉落；五号分别从铁符文铸造师收集第1/2/3部分并在背包合成完整蓝图。首组确认最下方建筑里面任务怪最多，优先在该建筑刷。"), note_block("监工的制服", "首组确认目标只需击杀一次，同一尸体可由五号依次拾取任务物。"), note_block("活灵活现", status_span("共享") + "罗卡尔的相机只能对已经死亡的铁矮人尸体使用；主号对尸体使用相机即可同步五号，不要在活怪身上反复试。"), note_block("收集零件", status_span("不共享") + "五号分别拾取任务零件，以最低号进度为离开条件。"), note_block("洛肯的命令", status_span("共享") + "先使用监工伪装进入Dun Argol；洛肯基座在最东侧主建筑的中层区域。伪装状态不能骑乘，受到伤害（包括摔落伤害）会破伪装；点击基座后等完整段对话结束。当前路线这里完成后先不交任务，保留伪装继续做铁领主链。"), note_block("我们有能源", "符文铸造师杜拉尔约(74.8,57)、卡索恩约(76.8,59.3)，分别在相对建筑里；两名目标各击杀一次即可，同一尸体上的能量核心可由五号依次拾取。"), note_block("……我们没有能源", status_span("共享") + "五号分别召出战争魔像后，同一只闪电斥候可让五只魔像各记1次充能，因此一只怪可直接记5次、两只怪即可完成全队。让魔像靠近目标后击杀；若带非战斗小宠物先收起。"), note_block("击败铁领主", status_span("共享") + "从Dun Argol最高建筑进入，电梯在进门左侧并向下到铁领主区域。战争魔像战斗时先选中旁边的铁砧，用2号EMP技能打掉弗雷哈默尔的护盾，再用1号技能输出Boss；护盾恢复就再次EMP铁砧。")),
            "timingTaskNames": ["监工的制服", "有趣的计划", "活灵活现", "收集零件", "我们有能源", "洛肯的命令", "……我们没有能源", "击败铁领主"],
        },
        11: {
            "title": "加弗洛克 → 符文巨人平原 → 哈考尔 → 加弗洛克",
            "summary": "加弗洛克交潜能石并接《终获解救》，符文巨人平原完成释放并补肉类；向哈考尔交《等肉下锅》，最后回加弗洛克交《终获解救》，灰熊丘陵本图结束。",
            "points": [
                {"title": "加弗洛克", "action": "加弗洛克 → 交《潜在的能量》 → 接《终获解救》"},
                {"title": "符文巨人平原", "action": "↳ 做《终获解救》《等肉下锅》", "note": "《终获解救》共享；符文破坏者失败时目标会被削弱，可等冷却后再次使用。《等肉下锅》先在约(72,37)同片顺手打；狼肉缺口优先去65—66,43，66,43洞内狼刷新快；想少跑动可在68,39营地/墓地附近循环，两种目标都有。", "fivebox": ""},
                {"title": "哈考尔", "action": "哈考尔 → 交《等肉下锅》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《终获解救》"},
            ],
            "action_html": [npc_actions("加弗洛克", turns=("潜在的能量",), accepts=("终获解救",)), do_at("符文巨人平原", "终获解救", "等肉下锅"), npc_actions("哈考尔", turns=("等肉下锅",)), npc_actions("加弗洛克", turns=("终获解救",))],
            "note_html": notes_html(note_block("终获解救", status_span("共享") + "对符文巨人使用加弗洛克的符文破坏者；一次不一定成功，失败会把目标变成削弱状态，这时不要把巨人杀掉，等道具冷却后对同一只再用，可能要重复数次。优先选正在与友方巨人交战的目标。"), note_block("等肉下锅", "优先与《终获解救》在约(72,37)同片顺手补。狼肉缺口可去65—66,43，66,43洞内狼刷新快；若想原地少跑，可在68,39营地/墓地附近循环，狼与长蹄鹿都有；鹿还可沿70—78,38—39一线补。")),
            "timingTaskNames": ["终获解救", "等肉下锅"],
        },
    }

    for step_number, spec in specs.items():
        apply_step(points, groups, step_number, spec)
    _rebuild_display_groups(groups)
