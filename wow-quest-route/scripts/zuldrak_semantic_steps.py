from __future__ import annotations

import html
from typing import Any

from dragonblight_semantic_steps import (
    arrow,
    branch,
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


def item_accept_line(quest_name: str) -> str:
    return '<div class="ra-line">' + branch() + verb("接") + ' ' + task(quest_name, "accept") + '</div>'


def object_actions(name: str, *, turns: tuple[str, ...] = (), accepts: tuple[str, ...] = ()) -> str:
    parts = [loc(name)]
    if turns:
        parts.extend([arrow(), verb("交"), " ", "、".join(task(x, "turn") for x in turns)])
    if accepts:
        parts.extend([arrow(), verb("接"), " ", "、".join(task(x, "accept") for x in accepts)])
    return '<div class="ra-line">' + "".join(parts) + '</div>'


def npc_do_line(name: str, quest_name: str) -> str:
    return '<div class="ra-line ra-do-inline">' + npc(name) + ' ' + branch() + verb("做") + ' ' + task(quest_name, "do") + '</div>'


def apply_step(points: list[list[Any]], groups: list[dict[str, Any]], step_number: int, spec: dict[str, Any]) -> None:
    group = groups[step_number - 1]
    indices = list(range(int(group["start"]), int(group["end"]) + 1))
    if len(indices) != len(spec["points"]):
        raise RuntimeError(f"Zul'Drak semantic step {step_number} point count drift: actual={len(indices)} expected={len(spec['points'])}")
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
        point[8] = point_spec.get("fivebox", "")


def apply_zuldrak_semantic_overrides(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    specs: dict[int, dict[str, Any]] = {
        1: {
            "title": "圣光据点 → 怒爪巢穴 → 兰迪加",
            "summary": "向莉安娜交跨图引导并开飞行点；按通缉板、莫奇、怒爪酋长、兰迪加分别接任务，怒爪巢穴完成后回据点按原NPC交付并接黑锋/前线引导。",
            "points": [
                {"title": "圣光据点", "action": "莉安娜中士 → 交《前往圣光据点！》\n开飞行点：圣光据点"},
                {"title": "圣光据点", "action": "通缉板 → 接《悬赏：怒鬃的鳍肢》\n萨满长者莫奇 → 接《火仍在烧！》\n怒爪酋长 → 接《巨魔疯啦！》\n北伐军领主兰迪加 → 接《寻找答案》"},
                {"title": "怒爪巢穴", "action": "↳ 做《火仍在烧！》《巨魔疯啦！》《悬赏：怒鬃的鳍肢》\n悬浮的达库鲁命令卷轴 → 交《寻找答案》 → 接《达库鲁的命令》", "note": "《火仍在烧！》：需要使用灭火器。\n《巨魔疯啦！》：需要取得并使用开锁器。", "fivebox": "确认灭火器和开锁器进度是否共享；若不共享则五号分别操作。"},
                {"title": "圣光据点", "action": "怒爪酋长 → 交《悬赏：怒鬃的鳍肢》《巨魔疯啦！》\n萨满长者莫奇 → 交《火仍在烧！》\n北伐军领主兰迪加 → 交《达库鲁的命令》 → 接《黑锋哨站》《北伐军前线营地》"},
            ],
            "action_html": [point_anchor("圣光据点"), npc_actions("莉安娜中士", turns=("前往圣光据点！",)), system_line("开飞行点：圣光据点", "ra-flightpoint"), npc_actions("通缉板", accepts=("悬赏：怒鬃的鳍肢",)), npc_actions("萨满长者莫奇", accepts=("火仍在烧！",)), npc_actions("怒爪酋长", accepts=("巨魔疯啦！",)), npc_actions("北伐军领主兰迪加", accepts=("寻找答案",)), do_at("怒爪巢穴", "火仍在烧！", "巨魔疯啦！", "悬赏：怒鬃的鳍肢"), object_actions("悬浮的达库鲁命令卷轴", turns=("寻找答案",), accepts=("达库鲁的命令",)), point_anchor("圣光据点"), npc_actions("怒爪酋长", turns=("悬赏：怒鬃的鳍肢", "巨魔疯啦！")), npc_actions("萨满长者莫奇", turns=("火仍在烧！",)), npc_actions("北伐军领主兰迪加", turns=("达库鲁的命令",), accepts=("黑锋哨站", "北伐军前线营地"))],
            "note_html": notes_html(note_block("火仍在烧！", status_span("五开待实测") + "确认灭火器进度是否共享；若不共享则五号分别使用。"), note_block("巨魔疯啦！", status_span("五开待实测") + "确认开锁器救俘虏进度是否共享；若不共享则五号分别操作。")),
            "timingTaskNames": ["火仍在烧！", "巨魔疯啦！", "悬赏：怒鬃的鳍肢"],
        },
        2: {
            "title": "北伐军前线 → 三名失踪者 → 盖米尔材料",
            "summary": "马克拉尔与里德分别接失踪者/废料；按达加斯→戈尔克→布尔完成搜救，到盖米尔接《风暴将至》，回前线交接后先收女妖精华再向黑锋入口移动。",
            "points": [
                {"title": "北伐军前线营地", "action": "北伐军战士马克拉尔 → 交《北伐军前线营地》 → 接《朋友的意义……》\n工程师里德 → 接《从无到有》"},
                {"title": "北伐军战士达加斯", "action": "↳ 做《朋友的意义……》《从无到有》"},
                {"title": "戈尔克", "action": "↳ 做《朋友的意义……》\n戈尔克 → 接《圣光不能为我复仇》\n↳ 做《圣光不能为我复仇》\n戈尔克 → 交《圣光不能为我复仇》"},
                {"title": "布尔", "action": "↳ 做《朋友的意义……》"},
                {"title": "盖米尔囚笼", "action": "盖米尔 → 接《风暴将至》"},
                {"title": "北伐军前线营地", "action": "工程师里德 → 交《从无到有》《风暴将至》 → 接《拯救盖米尔》\n北伐军战士马克拉尔 → 交《朋友的意义……》"},
                {"title": "北伐军前线周边", "action": "↳ 做《拯救盖米尔》", "note": "《拯救盖米尔》：本段先收女妖精华；硅藻土在黑锋哨站入口约(13.3,74.8)补齐。", "fivebox": "确认女妖精华与硅藻土是否个人掉落。"},
            ],
            "action_html": [point_anchor("北伐军前线营地"), npc_actions("北伐军战士马克拉尔", turns=("北伐军前线营地",), accepts=("朋友的意义……",)), npc_actions("工程师里德", accepts=("从无到有",)), do_at("北伐军战士达加斯", "朋友的意义……", "从无到有"), do_at("戈尔克", "朋友的意义……"), npc_actions("戈尔克", accepts=("圣光不能为我复仇",)), do_line("圣光不能为我复仇"), npc_actions("戈尔克", turns=("圣光不能为我复仇",)), do_at("布尔", "朋友的意义……"), npc_actions("盖米尔", accepts=("风暴将至",)), point_anchor("北伐军前线营地"), npc_actions("工程师里德", turns=("从无到有", "风暴将至"), accepts=("拯救盖米尔",)), npc_actions("北伐军战士马克拉尔", turns=("朋友的意义……",)), do_at("北伐军前线周边", "拯救盖米尔")],
            "note_html": notes_html(note_block("拯救盖米尔", status_span("五开待实测") + "确认女妖精华与硅藻土是否个人掉落；硅藻土在黑锋哨站入口补齐。")),
            "timingTaskNames": ["朋友的意义……", "圣光不能为我复仇", "风暴将至", "拯救盖米尔"],
        },
        3: {
            "title": "黑锋哨站 → 骨肠伪装 → 盖米尔 → 沃尔塔鲁斯入口",
            "summary": "黑锋入口补硅藻土；斯特凡线完成纳斯/项圈/达图拉/乔装，骨肠完成食尸鬼；再回前线完成盖米尔材料与载具，最后回黑锋准备潜入沃尔塔鲁斯。",
            "points": [
                {"title": "黑锋哨站入口", "action": "↳ 做《拯救盖米尔》", "note": "《拯救盖米尔》：这里补齐硅藻土；离开入口前确认五号材料都齐。"},
                {"title": "黑锋哨站", "action": "斯特凡·瓦杜 → 交《黑锋哨站》 → 接《纳斯和巨魔的毛发》\n开飞行点：黑锋哨站"},
                {"title": "干瘪巨魔", "action": "↳ 做《纳斯和巨魔的毛发》\n↳ 接《某种邀请……》", "note": "《某种邀请……》：黑锋哨站附近的干瘪巨魔会掉落“尸灵项圈”；拾取后右键接任务，离开前检查五号任务日志。", "fivebox": "确认纳斯主动使用是否共享。"},
                {"title": "黑锋哨站", "action": "斯特凡·瓦杜 → 交《某种邀请……》 → 接《幸免于难》"},
                {"title": "血玫瑰达图拉", "action": "血玫瑰达图拉 ↳ 做《幸免于难》", "note": "《幸免于难》：与达图拉交互，把项圈交给她推进任务。"},
                {"title": "黑锋哨站", "action": "斯特凡·瓦杜 → 交《幸免于难》 → 接《无处可藏》"},
                {"title": "痛苦之匣下层", "action": "↳ 做《无处可藏》", "fivebox": "确认两种任务物是否个人掉落。"},
                {"title": "黑锋哨站", "action": "斯特凡·瓦杜 → 交《无处可藏》 → 接《乔装打扮》"},
                {"title": "骨肠", "action": "↳ 做《乔装打扮》\n骨肠 → 接《喂饱食尸鬼》\n↳ 做《喂饱食尸鬼》\n骨肠 → 交《喂饱食尸鬼》", "note": "《乔装打扮》：先用迷惑项圈进入天灾伪装，再向骨肠购买苦痛浆液。\n《喂饱食尸鬼》：在附近食尸鬼旁使用杂碎大餐。", "fivebox": "确认伪装/喂食是否需要五号分别操作。"},
                {"title": "黑锋哨站", "action": "斯特凡·瓦杜 → 交《乔装打扮》《纳斯和巨魔的毛发》 → 接《潜入沃尔塔鲁斯》\n血玫瑰达图拉 → 接《银色前沿》"},
                {"title": "北伐军前线营地", "action": "工程师里德 → 交《拯救盖米尔》 → 接《唯一的希望》"},
                {"title": "盖米尔囚笼", "action": "↳ 做《唯一的希望》\n盖米尔 → 交《唯一的希望》 → 接《风暴之王的复仇》", "note": "《唯一的希望》：使用巨型爆盐炸弹释放盖米尔。", "fivebox": "确认炸弹交互是否共享。"},
                {"title": "盖米尔载具", "action": "↳ 做《风暴之王的复仇》", "fivebox": "确认主控完成载具目标时五号是否同步。"},
                {"title": "北伐军前线营地", "action": "北伐军战士马克拉尔 → 交《风暴之王的复仇》"},
                {"title": "黑锋哨站", "action": "使用迷惑项圈：进入沃尔塔鲁斯"},
            ],
            "action_html": [do_at("黑锋哨站入口", "拯救盖米尔"), point_anchor("黑锋哨站"), npc_actions("斯特凡·瓦杜", turns=("黑锋哨站",), accepts=("纳斯和巨魔的毛发",)), system_line("开飞行点：黑锋哨站", "ra-flightpoint"), do_at("干瘪巨魔", "纳斯和巨魔的毛发"), item_accept_line("某种邀请……"), point_anchor("黑锋哨站"), npc_actions("斯特凡·瓦杜", turns=("某种邀请……",), accepts=("幸免于难",)), npc_do_line("血玫瑰达图拉", "幸免于难"), npc_actions("斯特凡·瓦杜", turns=("幸免于难",), accepts=("无处可藏",)), do_at("痛苦之匣下层", "无处可藏"), npc_actions("斯特凡·瓦杜", turns=("无处可藏",), accepts=("乔装打扮",)), do_at("骨肠", "乔装打扮"), npc_actions("骨肠", accepts=("喂饱食尸鬼",)), do_line("喂饱食尸鬼"), npc_actions("骨肠", turns=("喂饱食尸鬼",)), point_anchor("黑锋哨站"), npc_actions("斯特凡·瓦杜", turns=("乔装打扮", "纳斯和巨魔的毛发"), accepts=("潜入沃尔塔鲁斯",)), npc_actions("血玫瑰达图拉", accepts=("银色前沿",)), point_anchor("北伐军前线营地"), npc_actions("工程师里德", turns=("拯救盖米尔",), accepts=("唯一的希望",)), do_at("盖米尔囚笼", "唯一的希望"), npc_actions("盖米尔", turns=("唯一的希望",), accepts=("风暴之王的复仇",)), do_at("盖米尔载具", "风暴之王的复仇"), npc_actions("北伐军战士马克拉尔", turns=("风暴之王的复仇",)), point_anchor("黑锋哨站"), system_line("使用迷惑项圈：进入沃尔塔鲁斯")],
            "note_html": notes_html(note_block("拯救盖米尔", status_span("五开待实测") + "确认女妖精华与硅藻土是否个人掉落；硅藻土在黑锋哨站入口补齐。"), note_block("纳斯和巨魔的毛发", status_span("五开待实测") + "确认纳斯主动使用是否共享。"), note_block("某种邀请……", "黑锋哨站附近的干瘪巨魔会掉落“尸灵项圈”；拾取后右键接任务，离开前检查五号任务日志。"), note_block("幸免于难", "与血玫瑰达图拉交互，把项圈交给她推进任务。"), note_block("乔装打扮", status_span("五开待实测") + "确认迷惑项圈伪装是否需要五号分别操作；伪装后向骨肠购买苦痛浆液。"), note_block("喂饱食尸鬼", status_span("五开待实测") + "确认喂食是否需要五号分别操作；在附近食尸鬼旁使用杂碎大餐。"), note_block("唯一的希望", status_span("五开待实测") + "确认巨型爆盐炸弹交互是否共享。"), note_block("风暴之王的复仇", status_span("五开待实测") + "确认主控完成盖米尔载具目标时五号是否同步。")),
            "timingTaskNames": ["拯救盖米尔", "纳斯和巨魔的毛发", "乔装打扮", "无处可藏", "喂饱食尸鬼", "唯一的希望", "风暴之王的复仇", "潜入沃尔塔鲁斯"],
        },
        4: {
            "title": "沃尔塔鲁斯 ↔ 痛苦之匣：达库鲁 / 斯特凡完整链",
            "summary": "用迷惑项圈、传送器和斯特凡号角连续推进；达库鲁负责沃尔塔鲁斯任务，斯特凡负责痛苦之匣任务，最后击败达库鲁并立刻使用最后愿望。",
            "points": [
                {"title": "沃尔塔鲁斯", "action": "↳ 做《潜入沃尔塔鲁斯》\n传送回痛苦之匣", "note": "《潜入沃尔塔鲁斯》：保留斯特凡号角，回到痛苦之匣后直接使用。"},
                {"title": "痛苦之匣", "action": "使用斯特凡号角\n斯特凡·瓦杜 → 交《潜入沃尔塔鲁斯》 → 接《目前为止，一切很糟》"},
                {"title": "沃尔塔鲁斯 → 痛苦之匣", "action": "达库鲁大王 → 接《官大一级压死人》\n↳ 做《官大一级压死人》\n达库鲁大王 → 交《官大一级压死人》\n↳ 做《目前为止，一切很糟》", "note": "《官大一级压死人》控制荒芜恶鬼采集水晶，不是普通地面拾取。", "fivebox": "确认恶鬼采集和瘟疫锅使用是否共享。"},
                {"title": "痛苦之匣", "action": "使用斯特凡号角\n斯特凡·瓦杜 → 交《目前为止，一切很糟》 → 接《危险的材料》"},
                {"title": "沃尔塔鲁斯", "action": "达库鲁大王 → 接《无法容忍》\n↳ 做《无法容忍》《危险的材料》\n达库鲁大王 → 交《无法容忍》", "fivebox": "确认仆从控制和荒芜水晶是否需五号分别完成。"},
                {"title": "痛苦之匣", "action": "使用斯特凡号角\n斯特凡·瓦杜 → 交《危险的材料》 → 接《爆破活动》"},
                {"title": "沃尔塔鲁斯 → 上层密室 → 痛苦之匣", "action": "达库鲁大王 → 接《火上浇油》\n↳ 做《火上浇油》\n达库鲁大王 → 交《火上浇油》 → 接《真相大白》\n使用传送器：进入上层密室\n↳ 做《真相大白》\n达库鲁大王 → 交《真相大白》\n↳ 做《爆破活动》", "fivebox": "确认控制憎恶、密室脚本和炸药束进度是否共享。"},
                {"title": "痛苦之匣", "action": "使用斯特凡号角\n斯特凡·瓦杜 → 交《爆破活动》 → 接《背叛》"},
                {"title": "沃尔塔鲁斯", "action": "↳ 做《背叛》\n立刻使用达库鲁的最后愿望返回痛苦之匣", "note": "《背叛》：达库鲁的最后愿望只有短时间可用；击败后立刻使用。", "fivebox": "确认达库鲁战斗/最后愿望是否需要五号分别执行。"},
                {"title": "痛苦之匣", "action": "使用斯特凡号角\n斯特凡·瓦杜 → 交《背叛》"},
            ],
            "action_html": [do_at("沃尔塔鲁斯", "潜入沃尔塔鲁斯"), system_line("传送回痛苦之匣"), system_line("使用斯特凡号角"), npc_actions("斯特凡·瓦杜", turns=("潜入沃尔塔鲁斯",), accepts=("目前为止，一切很糟",)), npc_actions("达库鲁大王", accepts=("官大一级压死人",)), do_line("官大一级压死人"), npc_actions("达库鲁大王", turns=("官大一级压死人",)), do_line("目前为止，一切很糟"), system_line("使用斯特凡号角"), npc_actions("斯特凡·瓦杜", turns=("目前为止，一切很糟",), accepts=("危险的材料",)), npc_actions("达库鲁大王", accepts=("无法容忍",)), do_line("无法容忍", "危险的材料"), npc_actions("达库鲁大王", turns=("无法容忍",)), system_line("使用斯特凡号角"), npc_actions("斯特凡·瓦杜", turns=("危险的材料",), accepts=("爆破活动",)), npc_actions("达库鲁大王", accepts=("火上浇油",)), do_line("火上浇油"), npc_actions("达库鲁大王", turns=("火上浇油",), accepts=("真相大白",)), system_line("使用传送器：进入上层密室"), do_line("真相大白"), npc_actions("达库鲁大王", turns=("真相大白",)), do_line("爆破活动"), system_line("使用斯特凡号角"), npc_actions("斯特凡·瓦杜", turns=("爆破活动",), accepts=("背叛",)), do_at("沃尔塔鲁斯", "背叛"), system_line("立刻使用达库鲁的最后愿望返回痛苦之匣"), system_line("使用斯特凡号角"), npc_actions("斯特凡·瓦杜", turns=("背叛",))],
            "note_html": notes_html(note_block("潜入沃尔塔鲁斯", "保留斯特凡号角，传送回痛苦之匣后直接使用。"), note_block("官大一级压死人", "控制荒芜恶鬼采集荒芜水晶，不是普通地面拾取。" + status_span("五开待实测") + "确认恶鬼采集是否共享。"), note_block("目前为止，一切很糟", status_span("五开待实测") + "确认瘟疫锅使用是否共享。"), note_block("背叛", status_span("五开待实测") + "确认战斗和最后愿望是否需要五号分别执行；最后愿望只有短时间可用，击败达库鲁后立刻使用。")),
            "timingTaskNames": ["潜入沃尔塔鲁斯", "官大一级压死人", "目前为止，一切很糟", "无法容忍", "危险的材料", "真相大白", "爆破活动", "背叛"],
        },
        5: {
            "title": "银色前沿 → 赫布瓦罗 → 西莱图斯 → 银色前沿",
            "summary": "法斯塔夫开场；库恩斯/乌布戈分别接巡逻与祭坛任务。赫布瓦罗完成实验室与灵质，再到西莱图斯由斯塔哈默/玛加推进撤退和清怪，取得奇怪魔精后回银色前沿。",
            "points": [
                {"title": "银色前沿", "action": "指挥官法斯塔夫 → 交《银色前沿》 → 接《保卫银色前沿》《银色北伐军的降落伞》\n妖术师乌布戈 → 接《希姆埃巴的祝福》\n开飞行点：银色前沿"},
                {"title": "银色前沿庭院", "action": "↳ 做《保卫银色前沿》《银色北伐军的降落伞》", "fivebox": "确认击杀与降落伞使用是否共享。"},
                {"title": "银色前沿", "action": "指挥官法斯塔夫 → 交《保卫银色前沿》《银色北伐军的降落伞》\n指挥官库恩斯 → 接《给斯塔哈默中士的新命令》《巡逻任务》\n妖术师乌布戈 → 接《西莱图斯祭坛的麻烦》"},
                {"title": "赫布瓦罗岗哨", "action": "炼金师菲肯斯坦 → 接《实验室的学徒》\n阿纳斯上尉 → 接《吸取灵魂》\n↳ 做《实验室的学徒》\n炼金师菲肯斯坦 → 交《实验室的学徒》", "note": "《实验室的学徒》：4种材料都在实验室内固定位置。", "fivebox": "确认实验室固定材料是否逐号拾取。"},
                {"title": "扎尔金之池", "action": "↳ 做《吸取灵魂》"},
                {"title": "赫布瓦罗岗哨", "action": "阿纳斯上尉 → 交《吸取灵魂》 → 接《收集腐液》《蝙蝠翅膀》"},
                {"title": "暗门爬行者", "action": "↳ 做《收集腐液》"},
                {"title": "西莱图斯祭坛", "action": "斯塔哈默中士 → 交《给斯塔哈默中士的新命令》 → 接《银色北伐军，撤退！》\n玛加下士 → 接《扫清巨魔》\n↳ 做《西莱图斯祭坛的麻烦》《银色北伐军，撤退！》《扫清巨魔》\n↳ 接《奇怪的魔精》\n斯塔哈默中士 → 交《银色北伐军，撤退！》\n玛加下士 → 交《扫清巨魔》", "note": "《奇怪的魔精》：西莱图斯祭坛周围的达卡莱巨魔会掉落“奇怪的魔精”；拾取后右键接任务。", "fivebox": "确认撤退交谈和奇怪魔精掉落是否逐号完成。"},
                {"title": "西莱图斯东北", "action": "↳ 做《蝙蝠翅膀》"},
                {"title": "赫布瓦罗岗哨", "action": "阿纳斯上尉 → 交《收集腐液》《蝙蝠翅膀》"},
                {"title": "银色前沿", "action": "妖术师乌布戈 → 交《西莱图斯祭坛的麻烦》《奇怪的魔精》 → 接《珍贵的元素液体》\n亚克斯中尉 → 接《达卡莱巨魔不需要水元素！》"},
            ],
            "action_html": [point_anchor("银色前沿"), npc_actions("指挥官法斯塔夫", turns=("银色前沿",), accepts=("保卫银色前沿", "银色北伐军的降落伞")), npc_actions("妖术师乌布戈", accepts=("希姆埃巴的祝福",)), system_line("开飞行点：银色前沿", "ra-flightpoint"), do_at("银色前沿庭院", "保卫银色前沿", "银色北伐军的降落伞"), point_anchor("银色前沿"), npc_actions("指挥官法斯塔夫", turns=("保卫银色前沿", "银色北伐军的降落伞")), npc_actions("指挥官库恩斯", accepts=("给斯塔哈默中士的新命令", "巡逻任务")), npc_actions("妖术师乌布戈", accepts=("西莱图斯祭坛的麻烦",)), point_anchor("赫布瓦罗岗哨"), npc_actions("炼金师菲肯斯坦", accepts=("实验室的学徒",)), npc_actions("阿纳斯上尉", accepts=("吸取灵魂",)), do_line("实验室的学徒"), npc_actions("炼金师菲肯斯坦", turns=("实验室的学徒",)), do_at("扎尔金之池", "吸取灵魂"), npc_actions("阿纳斯上尉", turns=("吸取灵魂",), accepts=("收集腐液", "蝙蝠翅膀")), do_at("暗门爬行者", "收集腐液"), point_anchor("西莱图斯祭坛"), npc_actions("斯塔哈默中士", turns=("给斯塔哈默中士的新命令",), accepts=("银色北伐军，撤退！",)), npc_actions("玛加下士", accepts=("扫清巨魔",)), do_line("西莱图斯祭坛的麻烦", "银色北伐军，撤退！", "扫清巨魔"), item_accept_line("奇怪的魔精"), npc_actions("斯塔哈默中士", turns=("银色北伐军，撤退！",)), npc_actions("玛加下士", turns=("扫清巨魔",)), do_at("西莱图斯东北", "蝙蝠翅膀"), npc_actions("阿纳斯上尉", turns=("收集腐液", "蝙蝠翅膀")), point_anchor("银色前沿"), npc_actions("妖术师乌布戈", turns=("西莱图斯祭坛的麻烦", "奇怪的魔精"), accepts=("珍贵的元素液体",)), npc_actions("亚克斯中尉", accepts=("达卡莱巨魔不需要水元素！",))],
            "note_html": notes_html(note_block("实验室的学徒", status_span("五开待实测") + "确认4种固定材料是否逐号拾取。"), note_block("奇怪的魔精", "西莱图斯祭坛周围的达卡莱巨魔会掉落“奇怪的魔精”；拾取后右键接任务。")),
            "timingTaskNames": ["保卫银色前沿", "银色北伐军的降落伞", "吸取灵魂", "收集腐液", "西莱图斯祭坛的麻烦", "银色北伐军，撤退！", "扫清巨魔", "奇怪的魔精", "蝙蝠翅膀"],
        },
        6: {
            "title": "达克迦尔 / 达克索塔巡逻环 → 银色前沿 → 达拉然短往返",
            "summary": "按格隆迪尔、布兰顿、鲁伯特、罗杰斯、穆尔沙、考格维尔真实NPC推进南部岗哨；银色前沿交水元素/邪铁并做蘑菇蜥蜴，结束巡逻后立即去达拉然接《勇士的召唤！》并系统飞回。",
            "points": [
                {"title": "达克迦尔岗哨", "action": "格隆迪尔上尉 → 接《温暖的篝火》", "note": "《温暖的篝火》：接取后沿后续路线自然拾取枯死荆木；若不够，返回达克迦尔前再补。"},
                {"title": "达克索塔", "action": "布兰顿上尉 → 接《止痛药》\n鲁伯特上尉 → 接《扔手雷》\n罗杰斯博士 → 接《一个也不能少》"},
                {"title": "水罂粟 / 水元素走廊", "action": "↳ 做《止痛药》《达卡莱巨魔不需要水元素！》《珍贵的元素液体》"},
                {"title": "蛛魔弹坑", "action": "↳ 做《扔手雷》", "note": "《一个也不能少》：这里先不救人；先回达克索塔交《扔手雷》并接出《茧中人》，再把两个救援任务合并完成。"},
                {"title": "达克索塔", "action": "布兰顿上尉 → 交《止痛药》\n鲁伯特上尉 → 交《扔手雷》 → 接《茧中人》\n穆尔沙·月影中士 → 接《通灵师之死》\n专家考格维尔 → 接《撒网者的喷丝头》"},
                {"title": "蛛魔救援区", "action": "↳ 做《一个也不能少》《茧中人》"},
                {"title": "哈沙尔", "action": "↳ 做《通灵师之死》《撒网者的喷丝头》"},
                {"title": "达克索塔", "action": "罗杰斯博士 → 交《一个也不能少》\n鲁伯特上尉 → 交《茧中人》\n穆尔沙·月影中士 → 交《通灵师之死》 → 接《腐蚀者玛拉斯》\n专家考格维尔 → 交《撒网者的喷丝头》 → 接《坠毁的喷射器》\n鲁伯特上尉 → 接《纯粹的邪恶》"},
                {"title": "达克索塔北侧", "action": "↳ 做《腐蚀者玛拉斯》《坠毁的喷射器》《纯粹的邪恶》"},
                {"title": "达克索塔", "action": "穆尔沙·月影中士 → 交《腐蚀者玛拉斯》\n专家考格维尔 → 交《坠毁的喷射器》 → 接《缠绕投网器》"},
                {"title": "药剂喷射器", "action": "↳ 做《缠绕投网器》\n专家考格维尔 → 交《缠绕投网器》"},
                {"title": "希姆埃巴雕像", "action": "希姆埃巴雕像 → 交《希姆埃巴的祝福》", "note": "《希姆埃巴的祝福》：每号确认10份达卡莱供品后再奉上。"},
                {"title": "银色前沿", "action": "亚克斯中尉 → 交《达卡莱巨魔不需要水元素！》\n妖术师乌布戈 → 交《珍贵的元素液体》 → 接《蘑菇混合剂》\n伊崔格 → 交《纯粹的邪恶》\n学徒匹斯波特 → 接《贪吃的蜥蜴》"},
                {"title": "银色前沿东北", "action": "↳ 做《蘑菇混合剂》《贪吃的蜥蜴》"},
                {"title": "达克迦尔岗哨", "action": "格隆迪尔上尉 → 交《温暖的篝火》"},
                {"title": "银色前沿", "action": "妖术师乌布戈 → 交《蘑菇混合剂》 → 接《过犹不及》"},
                {"title": "赫布瓦罗岗哨", "action": "炼金师菲肯斯坦 → 交《贪吃的蜥蜴》"},
                {"title": "西莱图斯先知", "action": "↳ 做《过犹不及》", "note": "《过犹不及》：先对西莱图斯先知使用混乱魔精，再击杀。"},
                {"title": "银色前沿", "action": "妖术师乌布戈 → 交《过犹不及》\n指挥官库恩斯 → 交《巡逻任务》 → 接《巫医库弗》"},
                {"title": "达拉然短往返", "action": "博学者泰罗努斯三世 → 传送到达拉然\n狡猾的维克斯 → 接《勇士的召唤！》\n系统飞行：达拉然 → 银色前沿", "note": "《魔法王国达拉然》：继续保持未交；这里利用博学者泰罗努斯三世的任务传送进入达拉然。\n《勇士的召唤！》：必须在开始痛苦斗兽场前接；五号分别完成传送、接取和返程。"},
            ],
            "action_html": [point_anchor("达克迦尔岗哨"), npc_actions("格隆迪尔上尉", accepts=("温暖的篝火",)), point_anchor("达克索塔"), npc_actions("布兰顿上尉", accepts=("止痛药",)), npc_actions("鲁伯特上尉", accepts=("扔手雷",)), npc_actions("罗杰斯博士", accepts=("一个也不能少",)), do_at("水罂粟 / 水元素走廊", "止痛药", "达卡莱巨魔不需要水元素！", "珍贵的元素液体"), do_at("蛛魔弹坑", "扔手雷"), point_anchor("达克索塔"), npc_actions("布兰顿上尉", turns=("止痛药",)), npc_actions("鲁伯特上尉", turns=("扔手雷",), accepts=("茧中人",)), npc_actions("穆尔沙·月影中士", accepts=("通灵师之死",)), npc_actions("专家考格维尔", accepts=("撒网者的喷丝头",)), do_at("蛛魔救援区", "一个也不能少", "茧中人"), do_at("哈沙尔", "通灵师之死", "撒网者的喷丝头"), point_anchor("达克索塔"), npc_actions("罗杰斯博士", turns=("一个也不能少",)), npc_actions("鲁伯特上尉", turns=("茧中人",), accepts=("纯粹的邪恶",)), npc_actions("穆尔沙·月影中士", turns=("通灵师之死",), accepts=("腐蚀者玛拉斯",)), npc_actions("专家考格维尔", turns=("撒网者的喷丝头",), accepts=("坠毁的喷射器",)), do_at("达克索塔北侧", "腐蚀者玛拉斯", "坠毁的喷射器", "纯粹的邪恶"), point_anchor("达克索塔"), npc_actions("穆尔沙·月影中士", turns=("腐蚀者玛拉斯",)), npc_actions("专家考格维尔", turns=("坠毁的喷射器",), accepts=("缠绕投网器",)), do_at("药剂喷射器", "缠绕投网器"), npc_actions("专家考格维尔", turns=("缠绕投网器",)), object_actions("希姆埃巴雕像", turns=("希姆埃巴的祝福",)), point_anchor("银色前沿"), npc_actions("亚克斯中尉", turns=("达卡莱巨魔不需要水元素！",)), npc_actions("妖术师乌布戈", turns=("珍贵的元素液体",), accepts=("蘑菇混合剂",)), npc_actions("伊崔格", turns=("纯粹的邪恶",)), npc_actions("学徒匹斯波特", accepts=("贪吃的蜥蜴",)), do_at("银色前沿东北", "蘑菇混合剂", "贪吃的蜥蜴"), npc_actions("格隆迪尔上尉", turns=("温暖的篝火",)), point_anchor("银色前沿"), npc_actions("妖术师乌布戈", turns=("蘑菇混合剂",), accepts=("过犹不及",)), npc_actions("炼金师菲肯斯坦", turns=("贪吃的蜥蜴",)), do_at("西莱图斯先知", "过犹不及"), point_anchor("银色前沿"), npc_actions("妖术师乌布戈", turns=("过犹不及",)), npc_actions("指挥官库恩斯", turns=("巡逻任务",), accepts=("巫医库弗",)), point_anchor("达拉然短往返"), system_line("博学者泰罗努斯三世 → 传送到达拉然"), npc_actions("狡猾的维克斯", accepts=("勇士的召唤！",)), system_line("系统飞行：达拉然 → 银色前沿", "ra-flightpath")],
            "note_html": notes_html(note_block("魔法王国达拉然", "继续保持未交；这里利用博学者泰罗努斯三世的任务传送进入达拉然。"), note_block("勇士的召唤！", "必须在开始痛苦斗兽场前接取；五号分别完成达拉然传送、接取和返程。")),
            "timingTaskNames": ["止痛药", "达卡莱巨魔不需要水元素！", "珍贵的元素液体", "扔手雷", "一个也不能少", "茧中人", "通灵师之死", "撒网者的喷丝头", "腐蚀者玛拉斯", "坠毁的喷射器", "纯粹的邪恶", "缠绕投网器", "蘑菇混合剂", "贪吃的蜥蜴", "过犹不及"],
            "timingExtraMinutes": 6.0,
        },
        7: {
            "title": "痛苦斗兽场六连 → 希姆托加 → 金亚莱",
            "summary": "先用伊戈达斯验证当前五开战斗压力；可接受则六场均由古尔戈索克接、巨魔仆从伍迪交。随后到希姆托加开点绑炉石，按库弗/埃霍奈/图基尼/德苟达分线进入金亚莱。",
            "points": [
                {"title": "痛苦斗兽场", "action": "古尔戈索克 → 交《勇士的召唤！》 → 接《痛苦斗兽场：伊戈达斯！》\n↳ 做《痛苦斗兽场：伊戈达斯！》\n巨魔仆从伍迪 → 交《痛苦斗兽场：伊戈达斯！》\n古尔戈索克 → 接《痛苦斗兽场：猛犸人！》\n↳ 做《痛苦斗兽场：猛犸人！》\n巨魔仆从伍迪 → 交《痛苦斗兽场：猛犸人！》\n古尔戈索克 → 接《痛苦斗兽场：异界的对手！》\n↳ 做《痛苦斗兽场：异界的对手！》\n巨魔仆从伍迪 → 交《痛苦斗兽场：异界的对手！》\n古尔戈索克 → 接《痛苦斗兽场：海象人的末日！》\n↳ 做《痛苦斗兽场：海象人的末日！》\n巨魔仆从伍迪 → 交《痛苦斗兽场：海象人的末日！》\n古尔戈索克 → 接《痛苦斗兽场：血怒者科尔拉克！》\n↳ 做《痛苦斗兽场：血怒者科尔拉克！》\n巨魔仆从伍迪 → 交《痛苦斗兽场：血怒者科尔拉克！》\n古尔戈索克 → 接《痛苦斗兽场的冠军》\n↳ 做《痛苦斗兽场的冠军》\n巨魔仆从伍迪 → 交《痛苦斗兽场的冠军》", "note": "《痛苦斗兽场：伊戈达斯！》：第一场同时作为战斗压力门槛；若主控明显打不过或失败重跑成本高，就停止后五场，整条以后补。", "fivebox": "先确认伊戈达斯是否五号同步完成；后续各场继续观察。"},
                {"title": "希姆托加", "action": "巫医库弗 → 交《巫医库弗》 → 接《希姆托加的祝福》《横扫金亚莱》\n剥皮师埃霍奈 → 接《金亚莱的领袖》\n记载者图基尼 → 接《核实情况》\n开飞行点：希姆托加\n绑定炉石：希姆托加"},
                {"title": "金亚莱", "action": "↳ 做《横扫金亚莱》《金亚莱的领袖》", "note": "《金亚莱的领袖》：三个首领分别在对应图腾附近触发，不要只按一个平均坐标找。"},
                {"title": "希姆托加", "action": "巫医库弗 → 交《横扫金亚莱》 → 接《与哈克娅交谈》\n剥皮师埃霍奈 → 交《金亚莱的领袖》 → 接《封印裂隙》\n记载者图基尼 → 接《雪豹之神的圣物》\n元素驯服者德苟达 → 接《冻土精华》\n希姆托加雕像 → 交《希姆托加的祝福》", "note": "《希姆托加的祝福》：每号确认有10份达卡莱供品后再在雕像前交付。\n《核实情况》继续携带到杜布拉金。"},
            ],
            "action_html": [point_anchor("痛苦斗兽场"), npc_actions("古尔戈索克", turns=("勇士的召唤！",), accepts=("痛苦斗兽场：伊戈达斯！",)), do_line("痛苦斗兽场：伊戈达斯！"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场：伊戈达斯！",)), npc_actions("古尔戈索克", accepts=("痛苦斗兽场：猛犸人！",)), do_line("痛苦斗兽场：猛犸人！"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场：猛犸人！",)), npc_actions("古尔戈索克", accepts=("痛苦斗兽场：异界的对手！",)), do_line("痛苦斗兽场：异界的对手！"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场：异界的对手！",)), npc_actions("古尔戈索克", accepts=("痛苦斗兽场：海象人的末日！",)), do_line("痛苦斗兽场：海象人的末日！"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场：海象人的末日！",)), npc_actions("古尔戈索克", accepts=("痛苦斗兽场：血怒者科尔拉克！",)), do_line("痛苦斗兽场：血怒者科尔拉克！"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场：血怒者科尔拉克！",)), npc_actions("古尔戈索克", accepts=("痛苦斗兽场的冠军",)), do_line("痛苦斗兽场的冠军"), npc_actions("巨魔仆从伍迪", turns=("痛苦斗兽场的冠军",)), point_anchor("希姆托加"), npc_actions("巫医库弗", turns=("巫医库弗",), accepts=("希姆托加的祝福", "横扫金亚莱")), npc_actions("剥皮师埃霍奈", accepts=("金亚莱的领袖",)), npc_actions("记载者图基尼", accepts=("核实情况",)), system_line("开飞行点：希姆托加", "ra-flightpoint"), system_line("绑定炉石：希姆托加", "ra-hearth"), do_at("金亚莱", "横扫金亚莱", "金亚莱的领袖"), point_anchor("希姆托加"), npc_actions("巫医库弗", turns=("横扫金亚莱",), accepts=("与哈克娅交谈",)), npc_actions("剥皮师埃霍奈", turns=("金亚莱的领袖",), accepts=("封印裂隙",)), npc_actions("记载者图基尼", accepts=("雪豹之神的圣物",)), npc_actions("元素驯服者德苟达", accepts=("冻土精华",)), object_actions("希姆托加雕像", turns=("希姆托加的祝福",))],
            "note_html": notes_html(note_block("痛苦斗兽场：伊戈达斯！", status_span("五开待实测") + "第一场同时验证战斗压力和五号同步；明显难打则停止整条后续。"), note_block("希姆托加的祝福", "每号确认有10份达卡莱供品后再在希姆托加雕像前交付。")),
            "timingTaskNames": ["痛苦斗兽场：伊戈达斯！", "痛苦斗兽场：猛犸人！", "痛苦斗兽场：异界的对手！", "痛苦斗兽场：海象人的末日！", "痛苦斗兽场：血怒者科尔拉克！", "痛苦斗兽场的冠军", "横扫金亚莱", "金亚莱的领袖"],
        },
        8: {
            "title": "哈克娅 → 伦诺克 → 赫布达卡 → 奎丝鲁恩侦察",
            "summary": "哈克娅子嗣与圣物后回希姆托加分配图基尼/库弗任务；伦诺克链与冻土裂隙同圈完成，再做赫布达卡，最后返回哈克娅完成脚本侦察和灵界准备。",
            "points": [
                {"title": "哈克娅祭坛", "action": "哈克娅 → 交《与哈克娅交谈》 → 接《我的后裔》"},
                {"title": "哈克娅之爪", "action": "↳ 做《雪豹之神的圣物》《我的后裔》", "note": "《我的后裔》目标死亡后对尸体使用哈克娅的胡须。", "fivebox": "确认圣物拾取与尸体使用是否逐号完成。"},
                {"title": "哈克娅祭坛", "action": "哈克娅 → 交《我的后裔》 → 接《伦诺克之魂》"},
                {"title": "希姆托加", "action": "记载者图基尼 → 交《雪豹之神的圣物》 → 接《自毁家园》《拎尾巴》\n巫医库弗 → 接《希姆鲁克的祝福》"},
                {"title": "伦诺克祭坛 / 希姆鲁克雕像", "action": "↳ 做《冻土精华》《封印裂隙》\n伦诺克之魂 → 交《伦诺克之魂》 → 接《我的先知，我的敌人》\n↳ 做《我的先知，我的敌人》\n伦诺克之魂 → 交《我的先知，我的敌人》 → 接《结束痛苦》\n↳ 做《结束痛苦》\n伦诺克之魂 → 交《结束痛苦》 → 接《返回哈克娅身边》\n↳ 做《自毁家园》\n希姆鲁克雕像 → 交《希姆鲁克的祝福》", "note": "《结束痛苦》：在伦诺克祭坛使用薰香并按脚本完成。\n《希姆鲁克的祝福》：每号准备10份达卡莱供品后在雕像前交付。"},
                {"title": "希姆托加", "action": "元素驯服者德苟达 → 交《冻土精华》 → 接《击落赫布金》\n剥皮师埃霍奈 → 交《封印裂隙》 → 接《巫毒头饰！》\n记载者图基尼 → 交《自毁家园》"},
                {"title": "赫布达卡", "action": "↳ 做《巫毒头饰！》《击落赫布金》", "fivebox": "确认取头饰与赫布金触发击杀是否共享。"},
                {"title": "希姆托加", "action": "剥皮师埃霍奈 → 交《巫毒头饰！》\n元素驯服者德苟达 → 交《击落赫布金》"},
                {"title": "哈克娅祭坛", "action": "哈克娅 → 交《返回哈克娅身边》 → 接《不祥的扰动》\n↳ 做《不祥的扰动》\n哈克娅 → 交《不祥的扰动》 → 接《进入灵界的准备》", "note": "《不祥的扰动》与哈克娅交谈后乘她的子嗣自动侦察。", "fivebox": "确认脚本飞行是否五号分别执行。"},
                {"title": "哈克娅之爪", "action": "↳ 做《进入灵界的准备》\n哈克娅 → 交《进入灵界的准备》 → 接《寻找风蛇女神》"},
            ],
            "action_html": [point_anchor("哈克娅祭坛"), npc_actions("哈克娅", turns=("与哈克娅交谈",), accepts=("我的后裔",)), do_at("哈克娅之爪", "雪豹之神的圣物", "我的后裔"), npc_actions("哈克娅", turns=("我的后裔",), accepts=("伦诺克之魂",)), point_anchor("希姆托加"), npc_actions("记载者图基尼", turns=("雪豹之神的圣物",), accepts=("自毁家园", "拎尾巴")), npc_actions("巫医库弗", accepts=("希姆鲁克的祝福",)), do_at("伦诺克祭坛 / 希姆鲁克雕像", "冻土精华", "封印裂隙"), npc_actions("伦诺克之魂", turns=("伦诺克之魂",), accepts=("我的先知，我的敌人",)), do_line("我的先知，我的敌人"), npc_actions("伦诺克之魂", turns=("我的先知，我的敌人",), accepts=("结束痛苦",)), do_line("结束痛苦"), npc_actions("伦诺克之魂", turns=("结束痛苦",), accepts=("返回哈克娅身边",)), do_line("自毁家园"), object_actions("希姆鲁克雕像", turns=("希姆鲁克的祝福",)), point_anchor("希姆托加"), npc_actions("元素驯服者德苟达", turns=("冻土精华",), accepts=("击落赫布金",)), npc_actions("剥皮师埃霍奈", turns=("封印裂隙",), accepts=("巫毒头饰！",)), npc_actions("记载者图基尼", turns=("自毁家园",)), do_at("赫布达卡", "巫毒头饰！", "击落赫布金"), point_anchor("希姆托加"), npc_actions("剥皮师埃霍奈", turns=("巫毒头饰！",)), npc_actions("元素驯服者德苟达", turns=("击落赫布金",)), point_anchor("哈克娅祭坛"), npc_actions("哈克娅", turns=("返回哈克娅身边",), accepts=("不祥的扰动",)), do_line("不祥的扰动"), npc_actions("哈克娅", turns=("不祥的扰动",), accepts=("进入灵界的准备",)), do_at("哈克娅之爪", "进入灵界的准备"), npc_actions("哈克娅", turns=("进入灵界的准备",), accepts=("寻找风蛇女神",))],
            "note_html": notes_html(note_block("我的后裔", status_span("五开待实测") + "确认尸体使用哈克娅胡须是否逐号完成。"), note_block("不祥的扰动", status_span("五开待实测") + "确认哈克娅脚本侦察是否五号分别执行。")),
            "timingTaskNames": ["雪豹之神的圣物", "我的后裔", "冻土精华", "封印裂隙", "结束痛苦", "返回哈克娅身边", "自毁家园", "巫毒头饰！", "击落赫布金", "不祥的扰动", "进入灵界的准备"],
        },
        9: {
            "title": "奎丝鲁恩灵界链 → 哈克娅 → 犸托斯之血",
            "summary": "奎丝鲁恩之魂连续推进创造条件、复仇基础、三祭司；《最后一步》回哈克娅交后取犸托斯之血，再回哈克娅接《种瓜得瓜种豆得豆》，杀虚弱先知后炉石希姆托加。",
            "points": [
                {"title": "奎丝鲁恩之魂", "action": "奎丝鲁恩之魂 → 交《寻找风蛇女神》 → 接《创造条件》"},
                {"title": "奎丝鲁恩", "action": "↳ 做《创造条件》\n奎丝鲁恩之魂 → 交《创造条件》 → 接《复仇的基础》"},
                {"title": "奎丝鲁恩", "action": "↳ 做《复仇的基础》\n奎丝鲁恩之魂 → 交《复仇的基础》 → 接《地狱的复仇》"},
                {"title": "奎丝鲁恩三名高阶祭司", "action": "↳ 做《地狱的复仇》《拎尾巴》\n奎丝鲁恩之魂 → 交《地狱的复仇》 → 接《最后一步》", "note": "《地狱的复仇》：三名高阶祭司都要先使用奎丝鲁恩妖术棒，再击杀。", "fivebox": "确认妖术棒与拖带目标是否逐号操作。"},
                {"title": "哈克娅祭坛", "action": "哈克娅 → 交《最后一步》 → 接《死去神灵的血液》"},
                {"title": "犸托斯祭坛", "action": "↳ 做《死去神灵的血液》"},
                {"title": "哈克娅祭坛", "action": "哈克娅 → 交《死去神灵的血液》 → 接《种瓜得瓜种豆得豆》"},
                {"title": "虚弱的奎丝鲁恩先知", "action": "↳ 做《种瓜得瓜种豆得豆》\n使用炉石：希姆托加"},
            ],
            "action_html": [npc_actions("奎丝鲁恩之魂", turns=("寻找风蛇女神",), accepts=("创造条件",)), do_at("奎丝鲁恩", "创造条件"), npc_actions("奎丝鲁恩之魂", turns=("创造条件",), accepts=("复仇的基础",)), do_at("奎丝鲁恩", "复仇的基础"), npc_actions("奎丝鲁恩之魂", turns=("复仇的基础",), accepts=("地狱的复仇",)), do_at("奎丝鲁恩三名高阶祭司", "地狱的复仇", "拎尾巴"), npc_actions("奎丝鲁恩之魂", turns=("地狱的复仇",), accepts=("最后一步",)), point_anchor("哈克娅祭坛"), npc_actions("哈克娅", turns=("最后一步",), accepts=("死去神灵的血液",)), do_at("犸托斯祭坛", "死去神灵的血液"), point_anchor("哈克娅祭坛"), npc_actions("哈克娅", turns=("死去神灵的血液",), accepts=("种瓜得瓜种豆得豆",)), do_at("虚弱的奎丝鲁恩先知", "种瓜得瓜种豆得豆"), system_line("使用炉石：希姆托加", "ra-hearth")],
            "note_html": notes_html(note_block("地狱的复仇", status_span("五开待实测") + "确认奎丝鲁恩妖术棒是否需要五号分别操作；三名高阶祭司均先用妖术棒再击杀。"), note_block("拎尾巴", status_span("五开待实测") + "确认麻醉拖带目标是否需要五号分别操作。")),
            "timingTaskNames": ["创造条件", "复仇的基础", "地狱的复仇", "拎尾巴", "死去神灵的血液", "种瓜得瓜种豆得豆"],
        },
        10: {
            "title": "希姆托加四NPC交接 → 犸托斯 → 佐尔玛兹 → 阿卡里",
            "summary": "库弗收神灵链、图基尼收拖带；埃霍奈/德苟达/图基尼/哈克娅分别接四条北部任务。完成猛犸和佐尔玛兹后回各NPC交付，再开古达克飞行点释放阿卡里并系统飞回希姆托加。",
            "points": [
                {"title": "希姆托加", "action": "巫医库弗 → 交《种瓜得瓜种豆得豆》\n记载者图基尼 → 交《拎尾巴》\n剥皮师埃霍奈 → 接《猛犸的复仇》\n元素驯服者德苟达 → 接《魔化蒂基面具战士》\n记载者图基尼 → 接《妖术宝箱》\n哈克娅 → 接《督军佐尔玛兹的钥匙》"},
                {"title": "犸托斯", "action": "↳ 做《猛犸的复仇》", "fivebox": "确认猛犸载具击杀是否共享。"},
                {"title": "佐尔玛兹要塞", "action": "↳ 做《魔化蒂基面具战士》《妖术宝箱》《督军佐尔玛兹的钥匙》"},
                {"title": "希姆托加", "action": "剥皮师埃霍奈 → 交《猛犸的复仇》\n元素驯服者德苟达 → 交《魔化蒂基面具战士》\n记载者图基尼 → 交《妖术宝箱》\n哈克娅 → 交《督军佐尔玛兹的钥匙》 → 接《狂暴》"},
                {"title": "古达克飞行点", "action": "开飞行点：古达克"},
                {"title": "阿卡里", "action": "↳ 做《狂暴》", "fivebox": "确认释放阿卡里脚本是否共享。"},
                {"title": "古达克飞行点", "action": "系统飞行：古达克 → 希姆托加"},
                {"title": "希姆托加", "action": "巫医库弗 → 交《狂暴》 → 接《诸神的指引》"},
            ],
            "action_html": [point_anchor("希姆托加"), npc_actions("巫医库弗", turns=("种瓜得瓜种豆得豆",)), npc_actions("记载者图基尼", turns=("拎尾巴",), accepts=("妖术宝箱",)), npc_actions("剥皮师埃霍奈", accepts=("猛犸的复仇",)), npc_actions("元素驯服者德苟达", accepts=("魔化蒂基面具战士",)), npc_actions("哈克娅", accepts=("督军佐尔玛兹的钥匙",)), do_at("犸托斯", "猛犸的复仇"), do_at("佐尔玛兹要塞", "魔化蒂基面具战士", "妖术宝箱", "督军佐尔玛兹的钥匙"), point_anchor("希姆托加"), npc_actions("剥皮师埃霍奈", turns=("猛犸的复仇",)), npc_actions("元素驯服者德苟达", turns=("魔化蒂基面具战士",)), npc_actions("记载者图基尼", turns=("妖术宝箱",)), npc_actions("哈克娅", turns=("督军佐尔玛兹的钥匙",), accepts=("狂暴",)), system_line("开飞行点：古达克", "ra-flightpoint"), do_at("阿卡里", "狂暴"), point_anchor("古达克飞行点"), system_line("系统飞行：古达克 → 希姆托加", "ra-flightpath"), npc_actions("巫医库弗", turns=("狂暴",), accepts=("诸神的指引",))],
            "note_html": notes_html(note_block("猛犸的复仇 / 狂暴", status_span("五开待实测") + "确认载具击杀与阿卡里释放脚本是否共享。")),
            "timingTaskNames": ["猛犸的复仇", "魔化蒂基面具战士", "妖术宝箱", "督军佐尔玛兹的钥匙", "狂暴"],
        },
        11: {
            "title": "诸神的指引两精华 → 佐尔赫布 → 希姆托加",
            "summary": "先取希姆鲁克守卫者与奎丝鲁恩典狱官两份精华，向哈克娅交《诸神的指引》接佐尔赫布；击杀阿卡里先知后回古达克乘系统鸟，希姆托加附近向哈克娅交接《未完的事情》。",
            "points": [
                {"title": "希姆鲁克守卫者", "action": "↳ 做《诸神的指引》", "note": "《诸神的指引》：先从希姆鲁克守卫者取得守卫者精华；两份精华均按个人掉落处理，以五号最慢角色为准。"},
                {"title": "奎丝鲁恩祭坛典狱官", "action": "↳ 做《诸神的指引》", "note": "《诸神的指引》：这里取得典狱官精华，确认五号都已拿到后再去找哈克娅。"},
                {"title": "哈克娅", "action": "哈克娅 → 交《诸神的指引》 → 接《在佐尔赫布相会》"},
                {"title": "佐尔赫布召唤圈", "action": "↳ 做《在佐尔赫布相会》"},
                {"title": "古达克飞行点", "action": "系统飞行：古达克 → 希姆托加"},
                {"title": "希姆托加", "action": "哈克娅 → 交《在佐尔赫布相会》 → 接《未完的事情》"},
            ],
            "action_html": [do_at("希姆鲁克守卫者", "诸神的指引"), do_at("奎丝鲁恩祭坛典狱官", "诸神的指引"), npc_actions("哈克娅", turns=("诸神的指引",), accepts=("在佐尔赫布相会",)), do_at("佐尔赫布召唤圈", "在佐尔赫布相会"), point_anchor("古达克飞行点"), system_line("系统飞行：古达克 → 希姆托加", "ra-flightpath"), npc_actions("哈克娅", turns=("在佐尔赫布相会",), accepts=("未完的事情",))],
            "note_html": notes_html(note_block("诸神的指引", status_span("不共享") + "两份精华按个人掉落处理，以五号最慢角色为准。")),
            "timingTaskNames": ["诸神的指引", "在佐尔赫布相会"],
        },
        12: {
            "title": "希姆托加 → 古达克 → 杜布拉金迅猛龙卵",
            "summary": "系统飞到古达克；杜布拉金分别向托玛尔、拜基妮交两条携带任务，哈瓦纳接迅猛龙卵；五号完成后回哈瓦纳交付。",
            "points": [
                {"title": "古达克飞行点", "action": "系统飞行：希姆托加 → 古达克"},
                {"title": "杜布拉金", "action": "托玛尔 → 交《未完的事情》\n记载者拜基妮 → 交《核实情况》\n哈瓦纳 → 接《杜布拉金需要迅猛龙卵》"},
                {"title": "古达克迅猛龙卵", "action": "↳ 做《杜布拉金需要迅猛龙卵》", "fivebox": "确认迅猛龙卵是否个人拾取、同一刷新点能否多号连续取得。"},
                {"title": "杜布拉金", "action": "哈瓦纳 → 交《杜布拉金需要迅猛龙卵》"},
            ],
            "action_html": [system_line("系统飞行：希姆托加 → 古达克", "ra-flightpath"), point_anchor("杜布拉金"), npc_actions("托玛尔", turns=("未完的事情",)), npc_actions("记载者拜基妮", turns=("核实情况",)), npc_actions("哈瓦纳", accepts=("杜布拉金需要迅猛龙卵",)), do_at("古达克迅猛龙卵", "杜布拉金需要迅猛龙卵"), npc_actions("哈瓦纳", turns=("杜布拉金需要迅猛龙卵",))],
            "note_html": notes_html(note_block("杜布拉金需要迅猛龙卵", status_span("五开待实测") + "确认迅猛龙卵是否个人拾取、同一刷新点能否多号连续取得。")),
            "timingTaskNames": ["杜布拉金需要迅猛龙卵"],
        },
    }

    for step_number, spec in specs.items():
        apply_step(points, groups, step_number, spec)
