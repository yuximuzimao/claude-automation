from __future__ import annotations

import html
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


def apply_grizzly_semantic_overrides(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    specs: dict[int, dict[str, Any]] = {
        1: {
            "title": "征服堡 → 沃德伦 → 风险湾 → 沃德伦领主",
            "summary": "进入征服堡接齐南侧任务并开点/绑炉石；沃德伦完成野兽与缚焰者任务，风险湾做短时限溶解剂，再骑任务龙击杀沃德伦领主。",
            "points": [
                {"title": "征服堡", "action": "征服者克雷娜 → 交《前往征服堡，自求多福吧！》 → 接《征服者的指派》"},
                {"title": "征服堡", "action": "纳兹格利姆中士 → 交《征服者的指派》 → 接《缚焰者的秘密》《显示力量》\n皮货商人休尼克 → 接《灰狼的毛皮》\n粮食商人洛克兰 → 接《赚外快》\n开飞行点：征服堡（五号分别）\n绑定炉石：征服堡"},
                {"title": "征服堡南侧 / 沃德伦", "action": "↳ 做《赚外快》《灰狼的毛皮》《缚焰者的秘密》《显示力量》", "note": "《赚外快》《灰狼的毛皮》《缚焰者的秘密》：不共享：任务物为个人掉落，五号分别拾取。\n《显示力量》：共享：击杀进度五号同步。"},
                {"title": "征服堡", "action": "粮食商人洛克兰 → 交《赚外快》\n皮货商人休尼克 → 交《灰狼的毛皮》 → 接《替代品》\n纳兹格利姆中士 → 交《缚焰者的秘密》《显示力量》 → 接《沃德伦的领主》"},
                {"title": "风险湾", "action": "古图尔 → 接《寻找溶解剂》\n↳ 做《寻找溶解剂》\n古图尔 → 交《寻找溶解剂》", "note": "拾取 Element 115 后开始短时限返程；立即原路返回古图尔，尽量不进战斗。", "fivebox": "请确认 Element 115 是否能同一刷新点连续五号拾取，以及返程窗口是否分别计时。"},
                {"title": "沃德伦", "action": "↳ 做《沃德伦的领主》", "note": "骑任务龙完成载具战；贴近目标，高伤技能冷却好就用。"},
                {"title": "征服堡", "action": "纳兹格利姆中士 → 交《沃德伦的领主》 → 接《前往欧尼瓦营地》\n征服者克雷娜 → 接《我的敌人的朋友》"},
            ],
            "action_html": [point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("前往征服堡，自求多福吧！",), accepts=("征服者的指派",)), npc_actions("纳兹格利姆中士", turns=("征服者的指派",), accepts=("缚焰者的秘密", "显示力量")), npc_actions("皮货商人休尼克", accepts=("灰狼的毛皮",)), npc_actions("粮食商人洛克兰", accepts=("赚外快",)), system_line("开飞行点：征服堡（五号分别）", "ra-flightpoint"), system_line("绑定炉石：征服堡", "ra-hearth"), do_at("征服堡南侧 / 沃德伦", "赚外快", "灰狼的毛皮", "缚焰者的秘密", "显示力量"), point_anchor("征服堡"), npc_actions("粮食商人洛克兰", turns=("赚外快",)), npc_actions("皮货商人休尼克", turns=("灰狼的毛皮",), accepts=("替代品",)), npc_actions("纳兹格利姆中士", turns=("缚焰者的秘密", "显示力量"), accepts=("沃德伦的领主",)), point_anchor("风险湾"), npc_actions("古图尔", accepts=("寻找溶解剂",)), do_line("寻找溶解剂"), npc_actions("古图尔", turns=("寻找溶解剂",)), do_at("沃德伦", "沃德伦的领主"), point_anchor("征服堡"), npc_actions("纳兹格利姆中士", turns=("沃德伦的领主",), accepts=("前往欧尼瓦营地",)), npc_actions("征服者克雷娜", accepts=("我的敌人的朋友",))],
            "note_html": notes_html(note_block("赚外快 / 灰狼的毛皮 / 缚焰者的秘密", status_span("不共享") + "任务物为个人掉落，五号分别拾取。"), note_block("显示力量", status_span("共享") + "击杀进度五号同步。"), note_block("寻找溶解剂", status_span("五开待实测") + "Element 115 是否能同一刷新点连续五号拾取、返程窗口是否分别计时。拾取后立即原路返回古图尔。"), note_block("沃德伦的领主", "骑任务龙完成载具战；贴近目标，高伤技能冷却好就用。")),
            "timingTaskNames": ["赚外快", "灰狼的毛皮", "缚焰者的秘密", "显示力量", "寻找溶解剂", "沃德伦的领主"],
        },
        2: {
            "title": "银溪镇 → 征服堡：克雷娜 / 高戈娜 / 休尼克",
            "summary": "银溪镇完成《我的敌人的朋友》并取得米克哈尔日记，北侧补灰熊皮；回征服堡按真实NPC推进克雷娜、高戈娜和休尼克三条线。",
            "points": [
                {"title": "银溪镇南侧", "action": "↳ 做《我的敌人的朋友》\n↳ 接《米克哈尔的日记》", "note": "《米克哈尔的日记》：来源怪为银溪猎人；击杀后拾取掉落的任务起始物“米克哈尔的日记”，五号分别右键接任务。离开前确认五号日志里都有任务。"},
                {"title": "银溪镇北侧", "action": "↳ 做《替代品》"},
                {"title": "征服堡", "action": "征服者克雷娜 → 交《我的敌人的朋友》《米克哈尔的日记》 → 接《攻击银溪镇》《高戈娜》\n高戈娜 → 交《高戈娜》 → 接《顺藤摸瓜》\n皮货商人休尼克 → 交《替代品》 → 接《休尼克的掩饰》"},
                {"title": "征服堡", "action": "购买5份面粉和1份煤块\n皮货商人休尼克 → 交《休尼克的掩饰》 → 接《给克雷娜送货》\n征服者克雷娜 → 交《给克雷娜送货》\n风之先知希尔·灰角 → 接《白肩鹰的眼睛》\n苏尔肯中士 → 接《狩猎巨魔》", "note": "《休尼克的掩饰》：面粉和煤块都在征服堡商人处购买。"},
            ],
            "action_html": [do_at("银溪镇南侧", "我的敌人的朋友"), drop_accept_line("米克哈尔的日记"), do_at("银溪镇北侧", "替代品"), point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("我的敌人的朋友", "米克哈尔的日记"), accepts=("攻击银溪镇", "高戈娜")), npc_actions("高戈娜", turns=("高戈娜",), accepts=("顺藤摸瓜",)), npc_actions("皮货商人休尼克", turns=("替代品",), accepts=("休尼克的掩饰",)), raw_line("购买5份面粉和1份煤块"), npc_actions("皮货商人休尼克", turns=("休尼克的掩饰",), accepts=("给克雷娜送货",)), npc_actions("征服者克雷娜", turns=("给克雷娜送货",)), npc_actions("风之先知希尔·灰角", accepts=("白肩鹰的眼睛",)), npc_actions("苏尔肯中士", accepts=("狩猎巨魔",))],
            "note_html": notes_html(note_block("米克哈尔的日记", "来源怪为银溪猎人；击杀后拾取掉落的任务起始物“米克哈尔的日记”，五号分别右键接任务。离开前确认五号日志里都有任务。"), note_block("休尼克的掩饰", "面粉和煤块都在征服堡商人处购买。")),
            "timingTaskNames": ["我的敌人的朋友", "米克哈尔的日记", "替代品"],
        },
        3: {
            "title": "花岗岩之泉 → 达库鲁火盆 → 古树之心 → Drak'atal",
            "summary": "萨米尔/达库鲁/普雷蒙/马克分别推进巨魔链；两处达库鲁火盆完成象形文字与牺牲，古树之心交宝石，Drak'atal由达库鲁影像接出《灰尘之声》。",
            "points": [
                {"title": "花岗岩之泉", "action": "萨米尔 → 交《狩猎巨魔》 → 接《抓巨魔》\n↳ 做《抓巨魔》\n萨米尔 → 交《抓巨魔》\n达库鲁 → 接《停战？》\n↳ 做《停战？》\n达库鲁 → 交《停战？》 → 接《幻象之瓶》", "fivebox": "请确认《抓巨魔》一名角色成功抓捕是否共享任务进度；若不共享则五号依次执行。"},
                {"title": "花岗岩之泉北侧", "action": "↳ 做《幻象之瓶》\n达库鲁 → 交《幻象之瓶》 → 接《解读象形文字》", "note": "水草叶、3片朦胧叶和水晶瓶都齐再离开；水晶瓶在花岗岩之泉商人购买。"},
                {"title": "花岗岩之泉", "action": "普雷蒙 → 接《清理天灾》《蘑菇汤！》\n↳ 做《清理天灾》\n马克·菲尔森 → 交《清理天灾》 → 接《净化天灾巨魔》"},
                {"title": "达库鲁火盆·南侧", "action": "↳ 做《解读象形文字》\n达库鲁的影像 → 交《解读象形文字》 → 接《必要的牺牲》", "note": "必须在火盆旁使用任务药剂；单纯杀怪不会完成交付。"},
                {"title": "Zeb'Halak", "action": "↳ 做《必要的牺牲》《蘑菇汤！》"},
                {"title": "达库鲁火盆·北侧", "action": "达库鲁的影像 → 交《必要的牺牲》 → 接《古树精华宝石》"},
                {"title": "达克萨隆外", "action": "↳ 做《净化天灾巨魔》\n被囚禁的猎户 → 交《顺藤摸瓜》"},
                {"title": "银溪北侧 / 古树之心", "action": "↳ 做《攻击银溪镇》\nHeart of the Ancients → 交《古树精华宝石》 → 接《尽在掌控》"},
                {"title": "Drak'atal Passage", "action": "达库鲁的影像 → 交《尽在掌控》 → 接《灰尘之声》\n↳ 做《白肩鹰的眼睛》", "note": "《灰尘之声》先携带，进入Drakil'jin遗迹再完成。"},
                {"title": "征服堡", "action": "使用炉石：征服堡"},
            ],
            "action_html": [point_anchor("花岗岩之泉"), npc_actions("萨米尔", turns=("狩猎巨魔",), accepts=("抓巨魔",)), do_line("抓巨魔"), npc_actions("萨米尔", turns=("抓巨魔",)), npc_actions("达库鲁", accepts=("停战？",)), do_line("停战？"), npc_actions("达库鲁", turns=("停战？",), accepts=("幻象之瓶",)), do_at("花岗岩之泉北侧", "幻象之瓶"), npc_actions("达库鲁", turns=("幻象之瓶",), accepts=("解读象形文字",)), point_anchor("花岗岩之泉"), npc_actions("普雷蒙", accepts=("清理天灾", "蘑菇汤！")), do_line("清理天灾"), npc_actions("马克·菲尔森", turns=("清理天灾",), accepts=("净化天灾巨魔",)), do_at("达库鲁火盆·南侧", "解读象形文字"), npc_actions("达库鲁的影像", turns=("解读象形文字",), accepts=("必要的牺牲",)), do_at("Zeb'Halak", "必要的牺牲", "蘑菇汤！"), npc_actions("达库鲁的影像", turns=("必要的牺牲",), accepts=("古树精华宝石",)), do_at("达克萨隆外", "净化天灾巨魔"), npc_actions("被囚禁的猎户", turns=("顺藤摸瓜",)), do_at("银溪北侧", "攻击银溪镇"), npc_actions("Heart of the Ancients", turns=("古树精华宝石",), accepts=("尽在掌控",)), point_anchor("Drak'atal Passage"), npc_actions("达库鲁的影像", turns=("尽在掌控",), accepts=("灰尘之声",)), do_line("白肩鹰的眼睛"), system_line("使用炉石：征服堡", "ra-hearth")],
            "note_html": notes_html(note_block("抓巨魔", status_span("五开待实测") + "确认一名角色成功抓捕是否共享任务进度。"), note_block("停战？", "任务刀就在花岗岩之泉附近树桩；使用任务刀完成动作后再离开。"), note_block("幻象之瓶", "水草叶、3片朦胧叶和水晶瓶都齐再离开；水晶瓶在花岗岩之泉商人购买。"), note_block("清理天灾 / 蘑菇汤！", "木乃伊就在花岗岩之泉营地附近；《蘑菇汤！》的蛇眼、雪帽和甜根在北侧区域采集。"), note_block("解读象形文字", "必须在达库鲁火盆旁使用任务药剂。")),
            "timingTaskNames": ["抓巨魔", "停战？", "幻象之瓶", "清理天灾", "净化天灾巨魔", "解读象形文字", "必要的牺牲", "蘑菇汤！", "古树精华宝石", "攻击银溪镇", "白肩鹰的眼睛"],
        },
        4: {
            "title": "征服斗兽场 → 沃达希尔三洞 → 盲眼卢娜",
            "summary": "征服堡按克雷娜、高戈娜、灰角和格里尼克斯分别交接；斗兽场五连按真实交付NPC推进，再清沃达希尔三洞和盲眼卢娜链。",
            "points": [
                {"title": "征服堡", "action": "征服者克雷娜 → 交《攻击银溪镇》\n高戈娜 → 接《盲眼卢娜》\n风之先知希尔·灰角 → 接《沃达希尔的陨落》《地下的黑暗》\n格里尼克斯·西维格 → 接《征服斗兽场：斗熊！》"},
                {"title": "征服斗兽场", "action": "↳ 做《征服斗兽场：斗熊！》\n赌徒维尔金 → 交《征服斗兽场：斗熊！》\n格里尼克斯·西维格 → 接《征服斗兽场：疯狂的熊怪》\n↳ 做《征服斗兽场：疯狂的熊怪》\n赌徒维尔金 → 交《征服斗兽场：疯狂的熊怪》\n格里尼克斯·西维格 → 接《征服斗兽场：鲜血与金属》\n↳ 做《征服斗兽场：鲜血与金属》\n赌徒维尔金 → 交《征服斗兽场：鲜血与金属》\n格里尼克斯·西维格 → 接《征服斗兽场：九死一生》\n↳ 做《征服斗兽场：九死一生》\n赌徒维尔金 → 交《征服斗兽场：九死一生》\n格里尼克斯·西维格 → 接《征服斗兽场：摊牌》\n↳ 做《征服斗兽场：摊牌》\n高戈娜 → 交《征服斗兽场：摊牌》", "note": "前四轮交赌徒维尔金并回格里尼克斯接下一轮；最后《摊牌》交高戈娜。", "fivebox": "请确认五号同时处于任务状态时是否一次战斗全部记进度。"},
                {"title": "花岗岩之泉", "action": "马克·菲尔森 → 交《净化天灾巨魔》\n普雷蒙 → 交《蘑菇汤！》 → 接《跟我的小朋友打招呼》"},
                {"title": "沃达希尔三洞", "action": "↳ 做《沃达希尔的陨落》《地下的黑暗》《白肩鹰的眼睛》", "note": "《沃达希尔的陨落》三个洞都要下到底层黑烟处使用任务球；《地下的黑暗》软泥样本在洞内怪物区收集。"},
                {"title": "盲眼卢娜", "action": "盲眼卢娜 → 交《盲眼卢娜》 → 接《卢娜的要求》\n↳ 做《卢娜的要求》\n盲眼卢娜 → 交《卢娜的要求》 → 接《梦游体验》\n↳ 做《梦游体验》\n盲眼卢娜 → 交《梦游体验》 → 接《命运与巧合》", "note": "《梦游体验》喝药后看完整视觉事件；若效果不自动结束，再取消buff。"},
            ],
            "action_html": [point_anchor("征服堡"), npc_actions("征服者克雷娜", turns=("攻击银溪镇",)), npc_actions("高戈娜", accepts=("盲眼卢娜",)), npc_actions("风之先知希尔·灰角", accepts=("沃达希尔的陨落", "地下的黑暗")), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：斗熊！",)), do_at("征服斗兽场", "征服斗兽场：斗熊！"), npc_actions("赌徒维尔金", turns=("征服斗兽场：斗熊！",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：疯狂的熊怪",)), do_line("征服斗兽场：疯狂的熊怪"), npc_actions("赌徒维尔金", turns=("征服斗兽场：疯狂的熊怪",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：鲜血与金属",)), do_line("征服斗兽场：鲜血与金属"), npc_actions("赌徒维尔金", turns=("征服斗兽场：鲜血与金属",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：九死一生",)), do_line("征服斗兽场：九死一生"), npc_actions("赌徒维尔金", turns=("征服斗兽场：九死一生",)), npc_actions("格里尼克斯·西维格", accepts=("征服斗兽场：摊牌",)), do_line("征服斗兽场：摊牌"), npc_actions("高戈娜", turns=("征服斗兽场：摊牌",)), point_anchor("花岗岩之泉"), npc_actions("马克·菲尔森", turns=("净化天灾巨魔",)), npc_actions("普雷蒙", turns=("蘑菇汤！",), accepts=("跟我的小朋友打招呼",)), do_at("沃达希尔三洞", "沃达希尔的陨落", "地下的黑暗", "白肩鹰的眼睛"), point_anchor("盲眼卢娜"), npc_actions("盲眼卢娜", turns=("盲眼卢娜",), accepts=("卢娜的要求",)), do_line("卢娜的要求"), npc_actions("盲眼卢娜", turns=("卢娜的要求",), accepts=("梦游体验",)), do_line("梦游体验"), npc_actions("盲眼卢娜", turns=("梦游体验",), accepts=("命运与巧合",))],
            "note_html": notes_html(note_block("征服斗兽场", status_span("五开待实测") + "确认五号同时有任务时是否一场战斗同步完成。前四轮交赌徒维尔金，下一轮由格里尼克斯接；最终《摊牌》交高戈娜。")),
            "timingTaskNames": ["征服斗兽场：斗熊！", "征服斗兽场：疯狂的熊怪", "征服斗兽场：鲜血与金属", "征服斗兽场：九死一生", "征服斗兽场：摊牌", "沃达希尔的陨落", "地下的黑暗", "白肩鹰的眼睛", "卢娜的要求", "梦游体验"],
        },
        5: {
            "title": "欧尼瓦 → 索尔莫丹 → 征服堡 → 欧尼瓦",
            "summary": "欧尼瓦首次按沃塔肯、索鲁克、托尔玛克分别交接并开点；东北做驯鹿/野马/鱼群，索尔莫丹收日记书页，炉石征服堡后再系统飞回欧尼瓦交任务。",
            "points": [
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《前往欧尼瓦营地》 → 接《新的盟友》\n索鲁克·雷怒 → 接《惊吓野马》\n托尔玛克 → 接《不速之“客”》\n开飞行点：欧尼瓦营地（五号分别）"},
                {"title": "欧尼瓦东北", "action": "↳ 做《不速之“客”》《惊吓野马》\n休·格兰斯 → 接《熊的美食》\n↳ 做《熊的美食》", "note": "《熊的美食》直接对鱼群使用任务渔网，不需要钓鱼专业。", "fivebox": "请确认鲑鱼任务物为个人获取还是共享。"},
                {"title": "索尔莫丹外", "action": "↳ 接《破损的日记》\n↳ 做《破损的日记》", "note": "《破损的日记》：索尔莫丹外约(64.3,19.8)拾取地面的破损日记并右键接任务；随后收集8张缺失书页并合成完整日记后再下山。", "fivebox": "请确认8张书页是否逐号收集，及同一刷新点能否多号连续拾取。"},
                {"title": "征服堡", "action": "使用炉石：征服堡\n风之先知希尔·灰角 → 交《白肩鹰的眼睛》《沃达希尔的陨落》《地下的黑暗》 → 接《可能的关联》《熊神的后代》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地\n托尔玛克 → 交《不速之“客”》 → 接《有趣的计划》\n索鲁克·雷怒 → 交《惊吓野马》\n休·格兰斯 → 交《熊的美食》"},
                {"title": "欧尼瓦营地", "action": "先知帕鲁纳 → 交《破损的日记》 → 接《翻译日记》"},
            ],
            "action_html": [point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("前往欧尼瓦营地",), accepts=("新的盟友",)), npc_actions("索鲁克·雷怒", accepts=("惊吓野马",)), npc_actions("托尔玛克", accepts=("不速之“客”",)), system_line("开飞行点：欧尼瓦营地（五号分别）", "ra-flightpoint"), do_at("欧尼瓦东北", "不速之“客”", "惊吓野马"), npc_actions("休·格兰斯", accepts=("熊的美食",)), do_line("熊的美食"), point_anchor("索尔莫丹外"), drop_accept_line("破损的日记"), do_line("破损的日记"), system_line("使用炉石：征服堡", "ra-hearth"), npc_actions("风之先知希尔·灰角", turns=("白肩鹰的眼睛", "沃达希尔的陨落", "地下的黑暗"), accepts=("可能的关联", "熊神的后代")), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("托尔玛克", turns=("不速之“客”",), accepts=("有趣的计划",)), npc_actions("索鲁克·雷怒", turns=("惊吓野马",)), npc_actions("休·格兰斯", turns=("熊的美食",)), npc_actions("先知帕鲁纳", turns=("破损的日记",), accepts=("翻译日记",))],
            "note_html": notes_html(note_block("熊的美食", status_span("五开待实测") + "确认鲑鱼任务物是否共享；鱼群直接用任务渔网。"), note_block("破损的日记", "索尔莫丹外约(64.3,19.8)拾取地面的破损日记并右键接任务；随后收集8张缺失书页并合成完整日记后再下山。" + status_span("五开待实测") + "确认8张书页是否逐号收集、同一刷新点能否多号连续拾取。")),
            "timingTaskNames": ["不速之“客”", "惊吓野马", "熊的美食", "破损的日记"],
        },
        6: {
            "title": "欧尼瓦南侧 → 征服堡灰角 → 欧尼瓦",
            "summary": "欧尼瓦南侧完成翻译日记、熊怪血液和熊神子嗣；回征服堡只找灰角交接，再系统飞欧尼瓦分别找帕鲁纳和沃塔肯接索尔莫丹任务。",
            "points": [
                {"title": "欧尼瓦南侧", "action": "↳ 做《翻译日记》《可能的关联》《熊神的后代》"},
                {"title": "征服堡", "action": "风之先知希尔·灰角 → 交《可能的关联》《熊神的后代》 → 接《摧毁树苗》《沃达希尔的种子》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地\n先知帕鲁纳 → 交《翻译日记》 → 接《符文中的预言》\n斥候沃塔肯 → 接《“钢铁之子”》"},
            ],
            "action_html": [do_at("欧尼瓦南侧", "翻译日记", "可能的关联", "熊神的后代"), point_anchor("征服堡"), npc_actions("风之先知希尔·灰角", turns=("可能的关联", "熊神的后代"), accepts=("摧毁树苗", "沃达希尔的种子")), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("先知帕鲁纳", turns=("翻译日记",), accepts=("符文中的预言",)), npc_actions("斥候沃塔肯", accepts=("“钢铁之子”",))],
            "timingTaskNames": ["翻译日记", "可能的关联", "熊神的后代"],
        },
        7: {
            "title": "库伦 / 索尔莫丹 → 哈考尔 / 加弗洛克 → 欧尼瓦",
            "summary": "库伦三连后在索尔莫丹同时完成铁矮人和符文板；再去哈考尔/克拉斯、加弗洛克接任务，最后回欧尼瓦分别向沃塔肯和帕鲁纳交接。",
            "points": [
                {"title": "库伦", "action": "库伦 → 交《新的盟友》 → 接《巨石横飞》\n↳ 做《巨石横飞》\n库伦 → 交《巨石横飞》 → 接《鼓舞士气》\n↳ 做《鼓舞士气》\n库伦 → 交《鼓舞士气》 → 接《攻破防线》"},
                {"title": "索尔莫丹", "action": "↳ 做《攻破防线》《“钢铁之子”》《符文中的预言》", "fivebox": "请确认《符文中的预言》三块符文板互动是否共享。"},
                {"title": "库伦", "action": "库伦 → 交《攻破防线》 → 接《加弗洛克》"},
                {"title": "哈考尔 / 克拉斯", "action": "哈考尔 → 交《跟我的小朋友打招呼》 → 接《等肉下锅》《心灵的创伤》\n克拉斯 → 接《孤胆英雄……》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《加弗洛克》 → 接《压制符文》"},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《“钢铁之子”》 → 接《以洛肯之名》\n先知帕鲁纳 → 交《符文中的预言》", "note": "《以洛肯之名》先找休·格兰斯对话，再去加弗洛克完成剩余对话。"},
            ],
            "action_html": [point_anchor("库伦"), npc_actions("库伦", turns=("新的盟友",), accepts=("巨石横飞",)), do_line("巨石横飞"), npc_actions("库伦", turns=("巨石横飞",), accepts=("鼓舞士气",)), do_line("鼓舞士气"), npc_actions("库伦", turns=("鼓舞士气",), accepts=("攻破防线",)), do_at("索尔莫丹", "攻破防线", "“钢铁之子”", "符文中的预言"), npc_actions("库伦", turns=("攻破防线",), accepts=("加弗洛克",)), point_anchor("哈考尔 / 克拉斯"), npc_actions("哈考尔", turns=("跟我的小朋友打招呼",), accepts=("等肉下锅", "心灵的创伤")), npc_actions("克拉斯", accepts=("孤胆英雄……",)), npc_actions("加弗洛克", turns=("加弗洛克",), accepts=("压制符文",)), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("“钢铁之子”",), accepts=("以洛肯之名",)), npc_actions("先知帕鲁纳", turns=("符文中的预言",))],
            "note_html": notes_html(note_block("符文中的预言", status_span("五开待实测") + "确认三块符文板互动进度是否共享。")),
            "timingTaskNames": ["巨石横飞", "鼓舞士气", "攻破防线", "“钢铁之子”", "符文中的预言"],
        },
        8: {
            "title": "萨莎 → 灰喉堡 → 乌索克 → 安娅 / 萨莎",
            "summary": "萨莎村推进猎杀与阿纳托雷；灰喉堡做树苗/种子后炉石征服堡接乌索克，系统飞欧尼瓦再去乌索克；完成后回欧尼瓦乘系统鸟交付，再找安娅、萨莎和休·格兰斯。",
            "points": [
                {"title": "萨莎", "action": "萨莎 → 交《命运与巧合》 → 接《萨莎的狩猎》《阿纳托雷》\n↳ 做《萨莎的狩猎》《阿纳托雷》\n萨莎 → 交《萨莎的狩猎》《阿纳托雷》 → 接《姐姐的誓言》", "note": "《阿纳托雷》对阿纳托雷本人使用任务道具，再跟随坐骑/脚本完成事件。"},
                {"title": "灰喉堡", "action": "↳ 做《摧毁树苗》《沃达希尔的种子》", "fivebox": "请确认《摧毁树苗》火炬互动是否共享。"},
                {"title": "征服堡", "action": "使用炉石：征服堡\n风之先知希尔·灰角 → 交《摧毁树苗》《沃达希尔的种子》 → 接《乌索克，巨熊之神》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地"},
                {"title": "乌索克", "action": "↳ 做《乌索克，巨熊之神》", "note": "击败乌索克后必须对尸体使用净化灰烬；NPC助手可选坦克/输出/治疗。", "fivebox": "请确认击杀共享后，尸体使用净化灰烬是否每号都需操作。"},
                {"title": "欧尼瓦营地", "action": "系统飞行：欧尼瓦营地 → 征服堡"},
                {"title": "征服堡", "action": "风之先知希尔·灰角 → 交《乌索克，巨熊之神》"},
                {"title": "欧尼瓦营地", "action": "系统飞行：征服堡 → 欧尼瓦营地"},
                {"title": "安娅", "action": "安娅 → 交《姐姐的誓言》"},
                {"title": "萨莎", "action": "萨莎 → 接《狼人的末日》"},
                {"title": "休·格兰斯", "action": "与休·格兰斯对话，推进《以洛肯之名》"},
            ],
            "action_html": [point_anchor("萨莎"), npc_actions("萨莎", turns=("命运与巧合",), accepts=("萨莎的狩猎", "阿纳托雷")), do_line("萨莎的狩猎", "阿纳托雷"), npc_actions("萨莎", turns=("萨莎的狩猎", "阿纳托雷"), accepts=("姐姐的誓言",)), do_at("灰喉堡", "摧毁树苗", "沃达希尔的种子"), system_line("使用炉石：征服堡", "ra-hearth"), npc_actions("风之先知希尔·灰角", turns=("摧毁树苗", "沃达希尔的种子"), accepts=("乌索克，巨熊之神",)), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), do_at("乌索克", "乌索克，巨熊之神"), point_anchor("欧尼瓦营地"), system_line("系统飞行：欧尼瓦营地 → 征服堡", "ra-flightpath"), npc_actions("风之先知希尔·灰角", turns=("乌索克，巨熊之神",)), system_line("系统飞行：征服堡 → 欧尼瓦营地", "ra-flightpath"), npc_actions("安娅", turns=("姐姐的誓言",)), npc_actions("萨莎", accepts=("狼人的末日",)), task_text_line("与休·格兰斯对话，推进 ", "以洛肯之名")],
            "note_html": notes_html(note_block("摧毁树苗", status_span("五开待实测") + "确认火炬互动是否共享。树苗在灰喉堡底层。"), note_block("沃达希尔的种子", "种子在灰喉堡大树周围的熊怪营地地面拾取。"), note_block("乌索克，巨熊之神", status_span("五开待实测") + "击杀后必须对尸体使用净化灰烬；确认是否每号都需操作。")),
            "timingTaskNames": ["萨莎的狩猎", "阿纳托雷", "摧毁树苗", "沃达希尔的种子", "乌索克，巨熊之神", "以洛肯之名"],
        },
        9: {
            "title": "符文监督者 → Drakil'jin墓穴多次往返 → 血月岛 → 加弗洛克",
            "summary": "监督者后进入Drakil'jin；先完成罐子/石板，再由哈里森接护送。墓穴链按克拉斯↔墓穴真实往返执行，随后血月岛完成狼人并回萨莎交，最后到加弗洛克。",
            "points": [
                {"title": "符文监督者", "action": "↳ 做《压制符文》《心灵的创伤》\n沿路推进《等肉下锅》", "note": "每名监督者都要先击杀正在引导的铁符文织法者才会出现；《等肉下锅》这里只沿路累计，最后在符文巨人平原补齐。"},
                {"title": "Drakil'jin遗迹", "action": "↳ 做《孤胆英雄……》《灰尘之声》\n达库鲁的影像 → 交《灰尘之声》\n哈里森·琼斯 → 接《喔——哒！！》\n↳ 做《喔——哒！！》", "note": "启动护送前先确认《孤胆英雄……》《灰尘之声》的遗迹内目标已完成。"},
                {"title": "哈考尔 / 克拉斯", "action": "哈考尔 → 交《心灵的创伤》《喔——哒！！》\n克拉斯 → 交《孤胆英雄……》 → 接《达卡古尔之槌》"},
                {"title": "达卡古尔", "action": "↳ 做《达卡古尔之槌》"},
                {"title": "克拉斯", "action": "克拉斯 → 交《达卡古尔之槌》 → 接《死后相见》"},
                {"title": "Drakil'jin墓穴", "action": "↳ 做《死后相见》\n甘休 → 交《死后相见》 → 接《冷静一下，伙计》\n↳ 做《冷静一下，伙计》", "fivebox": "请确认灵魂/死亡阶段是否必须五号分别触发，以及任务道具/微粒是否逐号完成。"},
                {"title": "克拉斯", "action": "克拉斯 → 交《冷静一下，伙计》 → 接《金亚拉克的末日》"},
                {"title": "Drakil'jin墓穴", "action": "↳ 做《金亚拉克的末日》", "fivebox": "请确认供品拾取和最终锣互动是否逐号完成。"},
                {"title": "克拉斯", "action": "克拉斯 → 交《金亚拉克的末日》"},
                {"title": "血月岛", "action": "↳ 做《狼人的末日》", "fivebox": "请确认最终阿鲁高脚本阶段五号均完成。"},
                {"title": "萨莎", "action": "萨莎 → 交《狼人的末日》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《压制符文》 → 接《潜在的能量》\n与加弗洛克对话，完成《以洛肯之名》剩余目标\n↳ 做《潜在的能量》"},
            ],
            "action_html": [do_at("符文监督者", "压制符文", "心灵的创伤"), task_text_line("沿路推进 ", "等肉下锅"), do_at("Drakil'jin遗迹", "孤胆英雄……", "灰尘之声"), npc_actions("达库鲁的影像", turns=("灰尘之声",)), npc_actions("哈里森·琼斯", accepts=("喔——哒！！",)), do_line("喔——哒！！"), point_anchor("哈考尔 / 克拉斯"), npc_actions("哈考尔", turns=("心灵的创伤", "喔——哒！！")), npc_actions("克拉斯", turns=("孤胆英雄……",), accepts=("达卡古尔之槌",)), do_at("达卡古尔", "达卡古尔之槌"), npc_actions("克拉斯", turns=("达卡古尔之槌",), accepts=("死后相见",)), do_at("Drakil'jin墓穴", "死后相见"), npc_actions("甘休", turns=("死后相见",), accepts=("冷静一下，伙计",)), do_line("冷静一下，伙计"), npc_actions("克拉斯", turns=("冷静一下，伙计",), accepts=("金亚拉克的末日",)), do_at("Drakil'jin墓穴", "金亚拉克的末日"), npc_actions("克拉斯", turns=("金亚拉克的末日",)), do_at("血月岛", "狼人的末日"), npc_actions("萨莎", turns=("狼人的末日",)), point_anchor("加弗洛克"), npc_actions("加弗洛克", turns=("压制符文",), accepts=("潜在的能量",)), task_text_line("与加弗洛克对话，完成 ", "以洛肯之名", " 剩余目标"), do_line("潜在的能量")],
            "note_html": notes_html(note_block("压制符文", "四名符文监督者在Drakil'jin方向；每名监督者都要先击杀正在引导的铁符文织法者才会出现。"), note_block("喔——哒！！", "启动护送前先确认《孤胆英雄……》《灰尘之声》的遗迹内目标已完成。"), note_block("达卡古尔之槌", "达卡古尔会沿Drakil'jin遗迹道路巡逻。"), note_block("死后相见 / 冷静一下，伙计", status_span("五开待实测") + "确认灵魂/死亡阶段是否必须五号分别触发，以及任务道具/微粒是否逐号完成。墓穴链会多次进入：按当前任务依次敲锣、灵魂状态找甘休、取雪恢复；每次完成当前目标后再离开。"), note_block("金亚拉克的末日", status_span("五开待实测") + "确认供品拾取和最终锣互动是否逐号完成。取得供品后按任务要求合成，再进行最终敲锣。"), note_block("狼人的末日", status_span("五开待实测") + "确认最终阿鲁高脚本阶段五号均完成。")),
            "timingTaskNames": ["压制符文", "心灵的创伤", "孤胆英雄……", "灰尘之声", "喔——哒！！", "达卡古尔之槌", "死后相见", "冷静一下，伙计", "金亚拉克的末日", "狼人的末日", "潜在的能量"],
        },
        10: {
            "title": "欧尼瓦 ↔ Dun Argol：沃塔肯 / 罗卡尔 / 托尔玛克",
            "summary": "《以洛肯之名》交沃塔肯并接制服线；《有趣的计划》交罗卡尔并接零件/能源线。Dun Argol多次往返按真实NPC推进，最终铁领主交托尔玛克、洛肯命令交沃塔肯。",
            "points": [
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《以洛肯之名》 → 接《监工的制服》\n确认日志已有《有趣的计划》"},
                {"title": "Dun Argol", "action": "↳ 做《监工的制服》《有趣的计划》", "note": "《有趣的计划》三张蓝图集齐后在背包合成。", "fivebox": "请确认三张蓝图是否个人掉落。"},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《监工的制服》 → 接《活灵活现》\n勘探员罗卡尔 → 交《有趣的计划》 → 接《收集零件》"},
                {"title": "Dun Argol", "action": "↳ 做《活灵活现》《收集零件》"},
                {"title": "欧尼瓦营地", "action": "斥候沃塔肯 → 交《活灵活现》 → 接《洛肯的命令》\n勘探员罗卡尔 → 交《收集零件》 → 接《我们有能源》"},
                {"title": "Dun Argol上层", "action": "↳ 做《我们有能源》《洛肯的命令》", "note": "读取基座后《洛肯的命令》保持已完成未交；伪装留到铁领主结束。", "fivebox": "请确认两颗能量核心是否个人掉落/同尸多号可拾取。"},
                {"title": "欧尼瓦营地", "action": "勘探员罗卡尔 → 交《我们有能源》 → 接《……我们没有能源》\n《洛肯的命令》暂不交"},
                {"title": "Dun Argol外围", "action": "↳ 做《……我们没有能源》"},
                {"title": "欧尼瓦营地", "action": "勘探员罗卡尔 → 交《……我们没有能源》 → 接《击败铁领主》"},
                {"title": "Dun Argol上层", "action": "↳ 做《击败铁领主》", "note": "穿伪装上楼/乘电梯，使用魔像控制器；铁领主死亡后继续利用魔像/载具离开。", "fivebox": "请确认载具/控制器击杀进度是否共享。"},
                {"title": "欧尼瓦营地", "action": "托尔玛克 → 交《击败铁领主》\n斥候沃塔肯 → 交《洛肯的命令》"},
            ],
            "action_html": [point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("以洛肯之名",), accepts=("监工的制服",)), task_text_line("确认日志已有 ", "有趣的计划"), do_at("Dun Argol", "监工的制服", "有趣的计划"), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("监工的制服",), accepts=("活灵活现",)), npc_actions("勘探员罗卡尔", turns=("有趣的计划",), accepts=("收集零件",)), do_at("Dun Argol", "活灵活现", "收集零件"), point_anchor("欧尼瓦营地"), npc_actions("斥候沃塔肯", turns=("活灵活现",), accepts=("洛肯的命令",)), npc_actions("勘探员罗卡尔", turns=("收集零件",), accepts=("我们有能源",)), do_at("Dun Argol上层", "我们有能源", "洛肯的命令"), point_anchor("欧尼瓦营地"), npc_actions("勘探员罗卡尔", turns=("我们有能源",), accepts=("……我们没有能源",)), task_text_line("保持已完成未交：", "洛肯的命令"), do_at("Dun Argol外围", "……我们没有能源"), point_anchor("欧尼瓦营地"), npc_actions("勘探员罗卡尔", turns=("……我们没有能源",), accepts=("击败铁领主",)), do_at("Dun Argol上层", "击败铁领主"), point_anchor("欧尼瓦营地"), npc_actions("托尔玛克", turns=("击败铁领主",)), npc_actions("斥候沃塔肯", turns=("洛肯的命令",))],
            "note_html": notes_html(note_block("有趣的计划", status_span("五开待实测") + "确认三张蓝图是否个人掉落；集齐后在背包合成。"), note_block("我们有能源", status_span("五开待实测") + "确认两颗能量核心是否个人掉落/同尸多号可拾取。"), note_block("击败铁领主", status_span("五开待实测") + "确认载具/控制器击杀进度是否共享。")),
            "timingTaskNames": ["监工的制服", "有趣的计划", "活灵活现", "收集零件", "我们有能源", "洛肯的命令", "……我们没有能源", "击败铁领主"],
        },
        11: {
            "title": "加弗洛克 → 符文巨人平原 → 哈考尔 → 祖达克",
            "summary": "加弗洛克交潜能石并接《终获解救》，符文巨人平原完成释放并补肉类；向哈考尔交《等肉下锅》，回加弗洛克交任务后直接进入祖达克。",
            "points": [
                {"title": "加弗洛克", "action": "加弗洛克 → 交《潜在的能量》 → 接《终获解救》"},
                {"title": "符文巨人平原", "action": "↳ 做《终获解救》《等肉下锅》", "note": "符文破坏者失败时目标会被削弱，可等冷却后再次使用。", "fivebox": "请确认一次释放是否共享进度；若必须逐号使用则记录切号成本。"},
                {"title": "哈考尔", "action": "哈考尔 → 交《等肉下锅》"},
                {"title": "加弗洛克", "action": "加弗洛克 → 交《终获解救》\n继续进入祖达克"},
            ],
            "action_html": [npc_actions("加弗洛克", turns=("潜在的能量",), accepts=("终获解救",)), do_at("符文巨人平原", "终获解救", "等肉下锅"), npc_actions("哈考尔", turns=("等肉下锅",)), npc_actions("加弗洛克", turns=("终获解救",)), raw_line("继续进入祖达克")],
            "note_html": notes_html(note_block("终获解救", status_span("五开待实测") + "确认一次释放是否共享进度；失败时目标会被削弱，可等冷却后再次使用。")),
            "timingTaskNames": ["终获解救", "等肉下锅"],
        },
    }

    for step_number, spec in specs.items():
        apply_step(points, groups, step_number, spec)
