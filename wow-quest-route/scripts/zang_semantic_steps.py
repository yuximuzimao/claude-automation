from __future__ import annotations

import html
from typing import Any

from dragonblight_semantic_steps import (
    arrow,
    branch,
    do_at,
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


def object_actions(name: str, *, turns: tuple[str, ...] = (), accepts: tuple[str, ...] = ()) -> str:
    parts = [loc(name)]
    if turns:
        parts.extend([arrow(), verb("交"), " ", "、".join(task(x, "turn") for x in turns)])
    if accepts:
        parts.extend([arrow(), verb("接"), " ", "、".join(task(x, "accept") for x in accepts)])
    return '<div class="ra-line">' + "".join(parts) + "</div>"


def conditional_npc_turn_line(name: str, condition: str, quest_name: str) -> str:
    return (
        '<div class="ra-line">'
        + npc(name)
        + html.escape(condition)
        + arrow()
        + verb("交")
        + " "
        + task(quest_name, "turn")
        + "</div>"
    )


def npc_do_line(name: str, quest_name: str) -> str:
    return '<div class="ra-line ra-do-inline">' + npc(name) + ' ' + branch() + verb("做") + ' ' + task(quest_name, "do") + '</div>'


def drop_accept_line(quest_name: str) -> str:
    return '<div class="ra-line">' + branch() + verb("接") + ' ' + task(quest_name, "accept") + '</div>'


def task_text_line(prefix: str, quest_name: str, suffix: str = "") -> str:
    return '<div class="ra-line">' + html.escape(prefix) + task(quest_name, "do") + html.escape(suffix) + '</div>'


def accept_at(place: str, *tasks: str) -> str:
    return (
        '<div class="ra-line">'
        + loc(place)
        + '<span class="ra-inline-sep"> </span>'
        + branch()
        + verb("接")
        + " "
        + "、".join(task(x, "accept") for x in tasks)
        + "</div>"
    )


def P(
    x: float,
    y: float,
    title: str,
    action: str,
    phase: str,
    note: str = "",
    movement: str = "ride",
    optional: bool = False,
    fivebox: str = "",
) -> list[Any]:
    return [x, y, title, action, phase, note, movement, optional, fivebox]


def _replace_group_points(route: dict[str, Any], step_index: int, new_points: list[list[Any]]) -> None:
    groups = route["stepGroups"]
    points = route["points"]
    group = groups[step_index]
    start = int(group["start"])
    end = int(group["end"])
    old_count = end - start + 1
    points[start : end + 1] = new_points
    delta = len(new_points) - old_count
    group["end"] = start + len(new_points) - 1
    if delta:
        for later in groups[step_index + 1 :]:
            later["start"] = int(later["start"]) + delta
            later["end"] = int(later["end"]) + delta


def _patch_later_handoffs(route: dict[str, Any]) -> None:
    """Keep the route executable while step 1 is migrated ahead of later legacy steps."""
    marshlight_marker = "玛加沙 → 交《时尚无罪》《别再提蘑菇了！》 → 接《未完的职责》"
    ancient_turn = "唤风者塔鲁·黑蹄 → 交《古树的祝福》《保护观察者》"
    patched_marshlight = False
    patched_cenarion = False

    for point in route["points"]:
        action = str(point[3])
        if marshlight_marker in action:
            if "里维伊 → 交《沼牙的威胁》 → 接《对方的尊重》" not in action:
                action += "\n里维伊 → 交《沼牙的威胁》 → 接《对方的尊重》"
            point[3] = action
            patched_marshlight = True
        if ancient_turn in action:
            point[3] = action.replace(ancient_turn, "唤风者塔鲁·黑蹄 → 交《保护观察者》")
            patched_cenarion = True

    if not patched_marshlight:
        raise RuntimeError("Zang step 1 migration could not locate the later Marshlight handoff")
    if not patched_cenarion:
        # Idempotent reruns after this correction are allowed.
        patched_cenarion = any(
            "唤风者塔鲁·黑蹄 → 交《保护观察者》" in str(point[3])
            for point in route["points"]
        )
        if not patched_cenarion:
            raise RuntimeError("Zang step 1 migration could not locate the later Cenarion handoff")


def apply_zang_step1(route: dict[str, Any]) -> None:
    groups = route["stepGroups"]
    group = groups[0]
    current_count = int(group["end"]) - int(group["start"]) + 1
    if current_count not in {6, 11}:
        raise RuntimeError(f"Zang step 1 point-count drift: {current_count}")

    points = [
        P(
            78.40,
            62.02,
            "塞纳里奥庇护所",
            "伊谢尔·风歌 → 若携带《塞纳里奥远征队》则交；接《暗泽湖的异常》《失踪的先遣队》《监护者哈穆特》\n"
            "莱森·月火 → 接《观察者莉萨奥》《崩溃的平衡》\n"
            "通缉布告 → 接《暗潮纳迦的首领》《血鳞纳迦的领袖》\n"
            "唤风者塔鲁·黑蹄 → 接《古树的祝福》\n"
            "伊卡因 → 接《暗泽部族》\n"
            "劳兰娜·萨维尔 → 接《赞加沼泽的植物》\n"
            "监护者哈穆特 → 交《监护者哈穆特》 → 接《热情的欢迎》",
            "opening",
            "《赞加沼泽的植物》：沿后续路线自然累计未鉴定过的植物，不为它单独刷；到后续塞纳里奥回访时五号都够10株再交。",
        ),
        P(81.10, 63.87, "埃西恩", "↳ 做《古树的祝福》", "opening"),
        P(78.97, 67.44, "克勒斯", "↳ 做《古树的祝福》", "opening"),
        P(79.09, 65.27, "塞纳里奥庇护所", "唤风者塔鲁·黑蹄 → 交《古树的祝福》", "opening"),
        P(70.75, 80.15, "暗泽湖", "↳ 做《暗泽湖的异常》", "opening"),
        P(
            83.38,
            85.54,
            "暗泽村",
            "↳ 做《暗泽部族》\n凯拉·长鬃 → 接《逃离暗泽村》\n↳ 做《逃离暗泽村》",
            "opening",
            "《逃离暗泽村》：共享：五号都接好任务后一起护送凯拉返回塞纳里奥庇护所；保持队伍跟随。",
            "script",
        ),
        P(
            78.40,
            62.02,
            "塞纳里奥庇护所",
            "伊谢尔·风歌 → 交《逃离暗泽村》《暗泽湖的异常》 → 接《乌鸦的飞翔》\n"
            "↳ 做《乌鸦的飞翔》\n"
            "伊谢尔·风歌 → 交《乌鸦的飞翔》 → 接《恢复平衡》\n"
            "伊卡因 → 交《暗泽部族》 → 接《阴冷之地》\n"
            "劳兰娜·萨维尔 → 接《拯救孢子人》\n"
            "唤风者塔鲁·黑蹄 → 接《保护观察者》",
            "opening",
            "《乌鸦的飞翔》：在伊谢尔·风歌处使用风暴乌鸦护符，任务脚本会自动飞行完成；不要自己跑去调查点。",
            "script",
        ),
        P(
            85.28,
            54.75,
            "沼泽鼠岗哨",
            "开飞行点：沼泽鼠岗哨\n"
            "玛加沙 → 接《时尚无罪》《别再提蘑菇了！》\n"
            "里维伊 → 接《沼牙的威胁》\n"
            "祖莱 → 若携带《向祖莱报到》则交；接《厚重多头蛇鳞片》《向暗影猎手德恩加报到》",
            "east",
        ),
        P(
            77.50,
            70.50,
            "东部湖区",
            "↳ 做《沼牙的威胁》《崩溃的平衡》《别再提蘑菇了！》《时尚无罪》《厚重多头蛇鳞片》《热情的欢迎》",
            "east",
            "《热情的欢迎》：本段只沿路累计纳迦爪子，不要求在第一处抽水泵前完成；第二、第三泵区域继续补。",
        ),
        P(
            72.50,
            94.80,
            "暗泽南缘",
            "↳ 做《阴冷之地》《拯救孢子人》《保护观察者》",
            "east",
        ),
        P(
            70.60,
            80.29,
            "暗泽湖抽水泵",
            "↳ 做《恢复平衡》",
            "east",
            "《恢复平衡》：第一处抽水泵在暗泽湖；到抽水泵控制台旁使用任务给的铁藤种子。",
        ),
    ]

    if current_count == 6:
        _replace_group_points(route, 0, points)
    else:
        start = int(group["start"])
        route["points"][start : start + 11] = points

    group["title"] = "塞纳里奥庇护所 → 暗泽村 → 沼泽鼠岗哨 → 暗泽湖"
    group["summary"] = "塞纳里奥庇护所先完成本地古树祝福，再做暗泽湖、暗泽村护送与东南任务；沼泽鼠接齐任务后收第一处抽水泵。"
    group["actionHtml"] = "\n".join(
        [
            point_anchor("塞纳里奥庇护所"),
            conditional_npc_turn_line("伊谢尔·风歌", "：若携带塞纳里奥远征队 ", "塞纳里奥远征队"),
            npc_actions("伊谢尔·风歌", accepts=("暗泽湖的异常", "失踪的先遣队", "监护者哈穆特")),
            npc_actions("莱森·月火", accepts=("观察者莉萨奥", "崩溃的平衡")),
            object_actions("通缉布告", accepts=("暗潮纳迦的首领", "血鳞纳迦的领袖")),
            npc_actions("唤风者塔鲁·黑蹄", accepts=("古树的祝福",)),
            npc_actions("伊卡因", accepts=("暗泽部族",)),
            npc_actions("劳兰娜·萨维尔", accepts=("赞加沼泽的植物",)),
            npc_actions("监护者哈穆特", turns=("监护者哈穆特",), accepts=("热情的欢迎",)),
            npc_do_line("埃西恩", "古树的祝福"),
            npc_do_line("克勒斯", "古树的祝福"),
            npc_actions("唤风者塔鲁·黑蹄", turns=("古树的祝福",)),
            do_at("暗泽湖", "暗泽湖的异常"),
            point_anchor("暗泽村"),
            do_at("暗泽村", "暗泽部族"),
            npc_actions("凯拉·长鬃", accepts=("逃离暗泽村",)),
            npc_do_line("凯拉·长鬃", "逃离暗泽村"),
            point_anchor("塞纳里奥庇护所"),
            npc_actions("伊谢尔·风歌", turns=("逃离暗泽村", "暗泽湖的异常"), accepts=("乌鸦的飞翔",)),
            npc_do_line("伊谢尔·风歌", "乌鸦的飞翔"),
            npc_actions("伊谢尔·风歌", turns=("乌鸦的飞翔",), accepts=("恢复平衡",)),
            npc_actions("伊卡因", turns=("暗泽部族",), accepts=("阴冷之地",)),
            npc_actions("劳兰娜·萨维尔", accepts=("拯救孢子人",)),
            npc_actions("唤风者塔鲁·黑蹄", accepts=("保护观察者",)),
            point_anchor("沼泽鼠岗哨"),
            system_line("开飞行点：沼泽鼠岗哨", "ra-flightpoint"),
            npc_actions("玛加沙", accepts=("时尚无罪", "别再提蘑菇了！")),
            npc_actions("里维伊", accepts=("沼牙的威胁",)),
            conditional_npc_turn_line("祖莱", "：若携带向祖莱报到 ", "向祖莱报到"),
            npc_actions("祖莱", accepts=("厚重多头蛇鳞片", "向暗影猎手德恩加报到")),
            do_at("东部湖区", "沼牙的威胁", "崩溃的平衡", "别再提蘑菇了！", "时尚无罪", "厚重多头蛇鳞片", "热情的欢迎"),
            do_at("暗泽南缘", "阴冷之地", "拯救孢子人", "保护观察者"),
            do_at("暗泽湖抽水泵", "恢复平衡"),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("赞加沼泽的植物", "沿后续路线自然累计未鉴定过的植物，不单独刷；后续回塞纳里奥时五号都够10株再交。"),
        note_block("逃离暗泽村", status_span("共享") + "五号都接好任务后一起护送凯拉返回塞纳里奥庇护所；保持队伍跟随。"),
        note_block("乌鸦的飞翔", "在伊谢尔·风歌处使用风暴乌鸦护符，任务脚本会自动飞行完成；不要自己跑去调查点。"),
        note_block("热情的欢迎", "本段只沿路累计纳迦爪子，不要求在第一处抽水泵前完成；第二、第三泵区域继续补。"),
        note_block("恢复平衡", "第一处抽水泵在暗泽湖；到抽水泵控制台旁使用任务给的铁藤种子。"),
    )
    group["timingTaskNames"] = [
        "暗泽湖的异常",
        "暗泽部族",
        "逃离暗泽村",
        "乌鸦的飞翔",
        "古树的祝福",
        "沼牙的威胁",
        "崩溃的平衡",
        "别再提蘑菇了！",
        "时尚无罪",
        "厚重多头蛇鳞片",
        "热情的欢迎",
        "阴冷之地",
        "拯救孢子人",
        "保护观察者",
        "恢复平衡",
    ]

    _patch_later_handoffs(route)


def apply_zang_step2(route: dict[str, Any]) -> None:
    group = route["stepGroups"][1]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 3:
        raise RuntimeError(f"Zang step 2 point-count drift: {end - start + 1}")

    points = [
        P(
            65.10,
            68.67,
            "环礁湖",
            "↳ 做《恢复平衡》《暗潮纳迦的首领》《热情的欢迎》\n↳ 接《抽水泵结构图》",
            "east",
            "《恢复平衡》：第二处抽水泵在环礁湖；到控制台旁使用铁藤种子。\n"
            "《抽水泵结构图》：环礁湖的蒸汽泵监工会掉落“抽水泵结构图”，拾取后右键接同名任务；这里只顺手打，不额外强刷。",
        ),
        P(
            65.15,
            40.91,
            "毒蛇湖",
            "↳ 做《恢复平衡》《血鳞纳迦的领袖》《热情的欢迎》\n离开前确认已接《抽水泵结构图》",
            "east",
            "《恢复平衡》：第三处抽水泵在毒蛇湖；到控制台旁使用铁藤种子。\n"
            "《抽水泵结构图》：若此前还没拿到，毒蛇湖优先击杀血鳞监工、血鳞唤潮者和蒸汽泵监工，取得“抽水泵结构图”后右键接任务；离开毒蛇湖前必须拿到。先进入《恢复平衡》四泵阶段再补刷，泵旁使用铁藤种子可让蒸汽泵监工再次出现。\n"
            "《热情的欢迎》：图纸来源怪与纳迦爪子目标重叠，离开毒蛇湖前一并补齐。",
        ),
        P(80.75, 36.27, "观察者杰哈恩", "观察者杰哈恩 → 交《失踪的先遣队》", "east"),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "环礁湖 → 毒蛇湖 → 观察者杰哈恩"
    group["summary"] = "环礁湖完成第二处抽水泵与哈格哈兹；毒蛇湖完成第三泵、弗亚希并补齐纳迦爪子，离开前确保取得《抽水泵结构图》，最后去观察者杰哈恩交任务。"
    group["actionHtml"] = "\n".join(
        [
            do_at("环礁湖", "恢复平衡", "暗潮纳迦的首领", "热情的欢迎"),
            drop_accept_line("抽水泵结构图"),
            do_at("毒蛇湖", "恢复平衡", "血鳞纳迦的领袖", "热情的欢迎"),
            '<div class="ra-line">离开前确认已接 ' + task("抽水泵结构图", "accept") + '</div>',
            npc_actions("观察者杰哈恩", turns=("失踪的先遣队",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("恢复平衡", "第二处抽水泵在环礁湖，第三处在毒蛇湖；两处都在控制台旁使用铁藤种子。"),
        note_block("抽水泵结构图", "环礁湖的蒸汽泵监工会掉落“抽水泵结构图”，自然掉落就拾取并右键接任务，这里不强刷。若到毒蛇湖仍未取得，优先击杀血鳞监工、血鳞唤潮者和蒸汽泵监工，拿到图纸并接任务后再离开；先进入《恢复平衡》四泵阶段再补刷，泵旁使用铁藤种子可让蒸汽泵监工再次出现。"),
        note_block("热情的欢迎", "毒蛇湖的图纸来源怪与纳迦爪子目标重叠，离开前一并补齐。"),
    )
    group["timingTaskNames"] = ["恢复平衡", "暗潮纳迦的首领", "血鳞纳迦的领袖", "热情的欢迎"]


def apply_zang_step3(route: dict[str, Any]) -> None:
    group = route["stepGroups"][2]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 3:
        raise RuntimeError(f"Zang step 3 point-count drift: {end - start + 1}")

    points = [
        P(
            32.38,
            51.96,
            "萨布拉金",
            "开飞行点：萨布拉金\n炉石绑定：萨布拉金\n"
            "暗影猎手德恩加 → 交《向暗影猎手德恩加报到》\n"
            "巫医托尔加什 → 接《爆顶蘑菇》\n苏尔加亚 → 接《下钩钓鱼》\n"
            "通缉布告 → 接《通缉：穆玛基酋长》《通缉：格罗阿克》\n"
            "加巴林卡 → 接《清除沼光抽血者》",
            "west",
        ),
        P(
            50.34,
            40.87,
            "水域排水口",
            "↳ 做《下钩钓鱼》《抽水泵结构图》",
            "water",
            "《下钩钓鱼》：在泥爪水域完成任务目标。\n《抽水泵结构图》：到水下排水口完成调查。两条完成后不要游回岸边，直接在水中使用炉石。",
            "swim",
        ),
        P(
            32.38,
            51.96,
            "萨布拉金",
            "使用炉石：萨布拉金\n苏尔加亚 → 交《下钩钓鱼》 → 接《多头蛇之王》《猎杀恐爪》",
            "west",
            movement="hearth",
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "萨布拉金 → 水域排水口 → 炉石萨布拉金"
    group["summary"] = "首次到萨布拉金开启飞行点并绑定炉石；进入水域一次完成《下钩钓鱼》和《抽水泵结构图》调查，做完直接在水中炉石回萨布拉金交接。"
    group["actionHtml"] = "\n".join(
        [
            point_anchor("萨布拉金"),
            system_line("开飞行点：萨布拉金", "ra-flightpoint"),
            system_line("炉石绑定：萨布拉金", "ra-hearth"),
            npc_actions("暗影猎手德恩加", turns=("向暗影猎手德恩加报到",)),
            npc_actions("巫医托尔加什", accepts=("爆顶蘑菇",)),
            npc_actions("苏尔加亚", accepts=("下钩钓鱼",)),
            object_actions("通缉布告", accepts=("通缉：穆玛基酋长", "通缉：格罗阿克")),
            npc_actions("加巴林卡", accepts=("清除沼光抽血者",)),
            do_at("水域排水口", "下钩钓鱼", "抽水泵结构图"),
            system_line("使用炉石：萨布拉金", "ra-hearth"),
            npc_actions("苏尔加亚", turns=("下钩钓鱼",), accepts=("多头蛇之王", "猎杀恐爪")),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("下钩钓鱼", "在泥爪水域完成任务目标。"),
        note_block("抽水泵结构图", "到水下排水口完成调查；与《下钩钓鱼》一起完成后不要游回岸边，直接在水中炉石萨布拉金。"),
    )
    group["timingTaskNames"] = ["下钩钓鱼", "抽水泵结构图"]


def apply_zang_step4(route: dict[str, Any]) -> None:
    group = route["stepGroups"][3]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 3:
        raise RuntimeError(f"Zang step 4 point-count drift: {end - start + 1}")

    points = [
        P(
            25.40,
            42.86,
            "沼光湖抽水泵",
            "↳ 做《恢复平衡》",
            "east",
            "《恢复平衡》：第四处抽水泵在陆地；到控制台旁使用铁藤种子。",
        ),
        P(
            78.40,
            62.02,
            "塞纳里奥庇护所",
            "系统飞行：萨布拉金 → 塞纳里奥庇护所\n"
            "伊谢尔·风歌 → 交《恢复平衡》《抽水泵结构图》 → 接《通知塞纳里奥议会》\n"
            "监护者哈穆特 → 交《血鳞纳迦的领袖》《暗潮纳迦的首领》《热情的欢迎》\n"
            "唤风者塔鲁·黑蹄 → 交《保护观察者》\n莱森·月火 → 交《崩溃的平衡》\n"
            "伊卡因 → 交《阴冷之地》\n劳兰娜·萨维尔 → 交《拯救孢子人》《赞加沼泽的植物》",
            "east",
            "《赞加沼泽的植物》：只有五号都已自然累计10株未鉴定过的植物时才交；不足就继续保留，不专门补刷。\n"
            "《通知塞纳里奥议会》：作为跨图任务继续携带，不为它专程返回地狱火半岛。",
            movement="taxi",
        ),
        P(
            85.28,
            54.75,
            "沼泽鼠岗哨",
            "系统飞行：塞纳里奥庇护所 → 沼泽鼠岗哨\n"
            "玛加沙 → 交《时尚无罪》《别再提蘑菇了！》 → 接《未完的职责》\n"
            "祖莱 → 交《厚重多头蛇鳞片》 → 接《寻找斥候尤尔巴》\n"
            "里维伊 → 交《沼牙的威胁》 → 接《对方的尊重》",
            "east",
            movement="taxi",
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "沼光湖 → 塞纳里奥庇护所 → 沼泽鼠岗哨"
    group["summary"] = "完成陆地第四泵后乘系统鸟回塞纳里奥集中交付，再乘系统鸟到沼泽鼠；《沼牙的威胁》在这次自然回访时交并接出《对方的尊重》。"
    group["actionHtml"] = "\n".join(
        [
            do_at("沼光湖抽水泵", "恢复平衡"),
            system_line("系统飞行：萨布拉金 → 塞纳里奥庇护所", "ra-flightpath"),
            point_anchor("塞纳里奥庇护所"),
            npc_actions("伊谢尔·风歌", turns=("恢复平衡", "抽水泵结构图"), accepts=("通知塞纳里奥议会",)),
            npc_actions("监护者哈穆特", turns=("血鳞纳迦的领袖", "暗潮纳迦的首领", "热情的欢迎")),
            npc_actions("唤风者塔鲁·黑蹄", turns=("保护观察者",)),
            npc_actions("莱森·月火", turns=("崩溃的平衡",)),
            npc_actions("伊卡因", turns=("阴冷之地",)),
            npc_actions("劳兰娜·萨维尔", turns=("拯救孢子人", "赞加沼泽的植物")),
            system_line("系统飞行：塞纳里奥庇护所 → 沼泽鼠岗哨", "ra-flightpath"),
            point_anchor("沼泽鼠岗哨"),
            npc_actions("玛加沙", turns=("时尚无罪", "别再提蘑菇了！"), accepts=("未完的职责",)),
            npc_actions("祖莱", turns=("厚重多头蛇鳞片",), accepts=("寻找斥候尤尔巴",)),
            npc_actions("里维伊", turns=("沼牙的威胁",), accepts=("对方的尊重",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("恢复平衡", "第四处抽水泵在陆地；到控制台旁使用铁藤种子。"),
        note_block("赞加沼泽的植物", "只有五号都已自然累计10株未鉴定过的植物时才交；不足就继续保留，不专门补刷。"),
        note_block("通知塞纳里奥议会", "作为跨图任务继续携带，不为它专程返回地狱火半岛。"),
    )
    group["timingTaskNames"] = ["恢复平衡"]


def apply_zang_step5(route: dict[str, Any]) -> None:
    group = route["stepGroups"][4]
    current_count = int(group["end"]) - int(group["start"]) + 1
    if current_count not in {5, 7}:
        raise RuntimeError(f"Zang step 5 point-count drift: {current_count}")

    points = [
        P(
            80.75,
            36.27,
            "死亡泥潭",
            "斥候尤尔巴 → 交《寻找斥候尤尔巴》 → 接《尤尔巴的报告》",
            "east",
        ),
        P(
            82.50,
            45.00,
            "死亡泥潭·枯萎的巨人",
            "↳ 做《尤尔巴的报告》\n↳ 接《枯萎的孢芽》",
            "east",
            "《尤尔巴的报告》：不共享：五号都要分别拾取斥候尤尔巴的报告；同一具枯萎的巨人尸体可五号依次拾取，全部拿到后再离开。\n"
            "《枯萎的孢芽》：死亡泥潭约(81—85,43—48)的枯萎的巨人会随机掉落“枯萎的孢芽”，拾取后右键接同名任务；掉了就接，不为它额外补刷。",
        ),
        P(78.01, 45.41, "孢子之翼", "↳ 做《未完的职责》", "east"),
        P(
            84.36,
            54.33,
            "沼泽鼠岗哨",
            "玛加沙 → 交《未完的职责》\n祖莱 → 交《尤尔巴的报告》\n里维伊 → 交《枯萎的孢芽》",
            "east",
            "《枯萎的孢芽》：没掉就忽略，不回头补刷。",
        ),
        P(49.75, 60.06, "黑钉", "↳ 做《对方的尊重》", "east"),
        P(84.96, 54.03, "沼泽鼠岗哨", "里维伊 → 交《对方的尊重》", "east"),
        P(32.38, 51.96, "萨布拉金", "使用炉石：萨布拉金", "west", movement="hearth"),
    ]

    if current_count == 5:
        _replace_group_points(route, 4, points)
    else:
        start = int(group["start"])
        route["points"][start : start + 7] = points

    group["title"] = "死亡泥潭 → 孢子之翼 → 沼泽鼠岗哨 → 黑钉 → 炉石萨布拉金"
    group["summary"] = "尤尔巴先接出报告，再在死亡泥潭处理枯萎巨人和条件触发物；完成孢子之翼后回沼泽鼠交付，去黑钉完成《对方的尊重》，再回沼泽鼠交任务后炉石萨布拉金。"
    group["actionHtml"] = "\n".join(
        [
            point_anchor("死亡泥潭"),
            npc_actions("斥候尤尔巴", turns=("寻找斥候尤尔巴",), accepts=("尤尔巴的报告",)),
            do_at("枯萎的巨人", "尤尔巴的报告"),
            drop_accept_line("枯萎的孢芽"),
            do_at("孢子之翼", "未完的职责"),
            point_anchor("沼泽鼠岗哨"),
            npc_actions("玛加沙", turns=("未完的职责",)),
            npc_actions("祖莱", turns=("尤尔巴的报告",)),
            npc_actions("里维伊", turns=("枯萎的孢芽",)),
            do_at("黑钉", "对方的尊重"),
            point_anchor("沼泽鼠岗哨"),
            npc_actions("里维伊", turns=("对方的尊重",)),
            system_line("使用炉石：萨布拉金", "ra-hearth"),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("尤尔巴的报告", status_span("不共享") + "五号都要分别拾取斥候尤尔巴的报告；同一具枯萎的巨人尸体可五号依次拾取，全部拿到后再离开。"),
        note_block("枯萎的孢芽", "死亡泥潭约(81—85,43—48)的枯萎的巨人会随机掉落“枯萎的孢芽”，拾取后右键接同名任务；掉了就接，后续自然回沼泽鼠时交，没掉就忽略，不为它额外补刷。"),
    )
    group["timingTaskNames"] = ["尤尔巴的报告", "未完的职责", "对方的尊重"]


def apply_zang_step6(route: dict[str, Any]) -> None:
    group = route["stepGroups"][5]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 4:
        raise RuntimeError(f"Zang step 6 point-count drift: {end - start + 1}")

    points = [
        P(
            32.38,
            51.96,
            "萨布拉金",
            "↳ 做《爆顶蘑菇》《清除沼光抽血者》\n"
            "巫医托尔加什 → 交《爆顶蘑菇》 → 接《你见过鱼人吗？》\n"
            "加巴林卡 → 交《清除沼光抽血者》 → 接《最锋利的刀刃》\n"
            "先知亚尼迪 → 接《蛮沼之灵》",
            "west",
            "《爆顶蘑菇》：围绕萨布拉金本地专门转一圈拾取，不要只沿主路等顺手收齐。",
        ),
        P(46.40, 61.30, "蛮沼区", "↳ 做《蛮沼之灵》", "west"),
        P(32.38, 51.96, "萨布拉金", "先知亚尼迪 → 交《蛮沼之灵》 → 接《灵魂之盟？》", "west"),
        P(
            22.31,
            45.78,
            "恐爪刷新点",
            "↳ 做《猎杀恐爪》",
            "west",
            "《猎杀恐爪》：经过刷新点时目标在场就做；不等刷新，未完成继续保留。",
            optional=True,
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "萨布拉金 → 蛮沼区 → 恐爪刷新点"
    group["summary"] = "先完成萨布拉金本地采集并接出后续，再往返蛮沼区完成《蛮沼之灵》；经过恐爪刷新点时只在目标现身的情况下顺手完成。"
    group["actionHtml"] = "\n".join(
        [
            point_anchor("萨布拉金"),
            do_at("萨布拉金周边", "爆顶蘑菇", "清除沼光抽血者"),
            npc_actions("巫医托尔加什", turns=("爆顶蘑菇",), accepts=("你见过鱼人吗？",)),
            npc_actions("加巴林卡", turns=("清除沼光抽血者",), accepts=("最锋利的刀刃",)),
            npc_actions("先知亚尼迪", accepts=("蛮沼之灵",)),
            do_at("蛮沼区", "蛮沼之灵"),
            point_anchor("萨布拉金"),
            npc_actions("先知亚尼迪", turns=("蛮沼之灵",), accepts=("灵魂之盟？",)),
            do_at("恐爪刷新点", "猎杀恐爪"),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("爆顶蘑菇", "围绕萨布拉金本地专门转一圈拾取，不要只沿主路等顺手收齐。"),
        note_block("猎杀恐爪", "经过刷新点时目标在场就做；不等刷新，未完成继续保留。"),
    )
    group["timingTaskNames"] = ["爆顶蘑菇", "清除沼光抽血者", "蛮沼之灵"]


def apply_zang_step7(route: dict[str, Any]) -> None:
    group = route["stepGroups"][6]
    current_count = int(group["end"]) - int(group["start"]) + 1
    if current_count not in {4, 7}:
        raise RuntimeError(f"Zang step 7 point-count drift: {current_count}")

    points = [
        P(19.54, 50.04, "孢子村", "格沙弗 → 接《成熟的孢子》\n姆希菲 → 接《亮顶蘑菇》", "west"),
        P(23.32, 66.21, "莉萨奥营地", "观察者莉萨奥 → 交《观察者莉萨奥》 → 接《观察孢子人》", "west"),
        P(19.02, 62.43, "法恩森", "法恩森 → 接《孢子人的困境》《天敌》《孢子村》", "west"),
        P(14.39, 61.05, "孢殖林", "↳ 做《孢子人的困境》《观察孢子人》《天敌》", "west"),
        P(19.02, 62.43, "法恩森", "法恩森 → 交《孢子人的困境》《天敌》", "west"),
        P(23.32, 66.21, "莉萨奥营地", "观察者莉萨奥 → 交《观察孢子人》 → 接《狼吞虎咽》", "west"),
        P(19.54, 50.04, "孢子村", "舒特 → 接《既然我们是朋友......》", "west"),
    ]
    if current_count == 4:
        _replace_group_points(route, 6, points)
    else:
        start = int(group["start"])
        route["points"][start : start + 7] = points

    group["title"] = "孢子村 → 莉萨奥 → 法恩森 → 孢殖林 → 孢子村"
    group["summary"] = "孢子村先接背景采集；莉萨奥和法恩森接出三项孢殖林任务，完成后分别回原NPC交接，最后自然回孢子村接《既然我们是朋友......》。"
    group["actionHtml"] = "\n".join(
        [
            point_anchor("孢子村"),
            npc_actions("格沙弗", accepts=("成熟的孢子",)),
            npc_actions("姆希菲", accepts=("亮顶蘑菇",)),
            point_anchor("莉萨奥营地"),
            npc_actions("观察者莉萨奥", turns=("观察者莉萨奥",), accepts=("观察孢子人",)),
            npc_actions("法恩森", accepts=("孢子人的困境", "天敌", "孢子村")),
            do_at("孢殖林", "孢子人的困境", "观察孢子人", "天敌"),
            npc_actions("法恩森", turns=("孢子人的困境", "天敌")),
            point_anchor("莉萨奥营地"),
            npc_actions("观察者莉萨奥", turns=("观察孢子人",), accepts=("狼吞虎咽",)),
            point_anchor("孢子村"),
            npc_actions("舒特", accepts=("既然我们是朋友......",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("成熟的孢子", "作为北部路线背景采集；沿后续主体路线自然累计，不在孢子村附近单独绕圈补。"),
        note_block("孢子村", "继续携带到后续自然回孢子村时交给姆希菲。"),
    )
    group["timingTaskNames"] = ["孢子人的困境", "观察孢子人", "天敌"]


def apply_zang_step8(route: dict[str, Any]) -> None:
    group = route["stepGroups"][7]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 3:
        raise RuntimeError(f"Zang step 8 point-count drift: {end - start + 1}")

    points = [
        P(30.11, 63.94, "丢弃的食物", "↳ 做《狼吞虎咽》", "west"),
        P(
            32.81,
            59.53,
            "昂古拉刷新点",
            "↳ 接《沼泽中的伯爵》",
            "west",
            "《沼泽中的伯爵》：来源怪为“伯爵”昂古拉，主要位置约(32.8,59.5)；击杀后拾取必掉的任务起始物“昂古拉的下颚”，右键该物品接取任务。",
        ),
        P(23.32, 66.21, "莉萨奥营地", "观察者莉萨奥 → 交《狼吞虎咽》《沼泽中的伯爵》 → 接《熟悉的蘑菇》", "west"),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "丢弃的食物 → 昂古拉 → 莉萨奥"
    group["summary"] = "完成《狼吞虎咽》后顺路在昂古拉刷新点接《沼泽中的伯爵》，再回莉萨奥一次性交两项并接《熟悉的蘑菇》。"
    group["actionHtml"] = "\n".join(
        [
            do_at("丢弃的食物", "狼吞虎咽"),
            accept_at("昂古拉刷新点", "沼泽中的伯爵"),
            point_anchor("莉萨奥营地"),
            npc_actions("观察者莉萨奥", turns=("狼吞虎咽", "沼泽中的伯爵"), accepts=("熟悉的蘑菇",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("沼泽中的伯爵", "来源怪：“伯爵”昂古拉；主要位置约(32.8,59.5)；任务起始物：“昂古拉的下颚”（必掉）。击杀昂古拉后拾取该掉落物，右键物品接《沼泽中的伯爵》。"),
    )
    group["timingTaskNames"] = ["狼吞虎咽", "沼泽中的伯爵"]


def apply_zang_step9(route: dict[str, Any]) -> None:
    group = route["stepGroups"][8]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 5:
        raise RuntimeError(f"Zang step 9 point-count drift: {end - start + 1}")

    points = [
        P(26.21, 40.63, "血鳞区", "↳ 做《既然我们是朋友......》", "west"),
        P(
            23.78,
            26.75,
            "穆玛基",
            "↳ 做《通缉：穆玛基酋长》",
            "west",
            "《成熟的孢子》：可交易；沿北部主体路线顺手击杀大型孢子蝠自然累计，五号之间可调配库存，不在穆玛基附近单独绕圈补。",
        ),
        P(
            26.81,
            22.60,
            "匕潭鱼人笼点",
            "↳ 做《你见过鱼人吗？》",
            "west",
            "《你见过鱼人吗？》：到匕潭村约(26.8,22.6)的任务点使用任务提供的鱼人笼完成目标。",
        ),
        P(34.82, 34.83, "格罗阿克", "↳ 做《通缉：格罗阿克》《熟悉的蘑菇》", "west"),
        P(
            42.23,
            41.42,
            "多头蛇之王刷新点",
            "↳ 做《多头蛇之王》",
            "west",
            "《多头蛇之王》：经过固定刷新点时目标在场就做；不等刷新，未完成继续保留。",
            optional=True,
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "血鳞区 → 穆玛基 → 匕潭鱼人笼 → 格罗阿克"
    group["summary"] = "沿北部连续完成血鳞、穆玛基、鱼人笼和格罗阿克；成熟孢子只做背景累计，多头蛇之王只在经过时目标已刷新才顺手做。"
    group["actionHtml"] = "\n".join(
        [
            do_at("血鳞区", "既然我们是朋友......"),
            do_at("穆玛基", "通缉：穆玛基酋长"),

            do_at("匕潭鱼人笼点", "你见过鱼人吗？"),
            do_at("格罗阿克", "通缉：格罗阿克", "熟悉的蘑菇"),
            do_at("多头蛇之王刷新点", "多头蛇之王"),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("成熟的孢子", "可交易；沿北部主体路线顺手击杀大型孢子蝠自然累计，五号之间可调配库存，不在穆玛基附近单独绕圈补。"),
        note_block("你见过鱼人吗？", "到匕潭村约(26.8,22.6)的任务点使用任务提供的鱼人笼完成目标。"),
        note_block("多头蛇之王", "经过固定刷新点时目标在场就做；不等刷新，未完成继续保留。"),
    )
    group["timingTaskNames"] = ["既然我们是朋友......", "通缉：穆玛基酋长", "成熟的孢子", "你见过鱼人吗？", "通缉：格罗阿克", "熟悉的蘑菇"]


def apply_zang_step10(route: dict[str, Any]) -> None:
    group = route["stepGroups"][9]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 4:
        raise RuntimeError(f"Zang step 10 point-count drift: {end - start + 1}")

    points = [
        P(
            32.38,
            51.96,
            "萨布拉金",
            "使用炉石：萨布拉金\n"
            "暗影猎手德恩加 → 交《通缉：穆玛基酋长》《通缉：格罗阿克》 → 接《战斗迫近》\n"
            "巫医托尔加什 → 交《你见过鱼人吗？》\n"
            "苏尔加亚 → 交《多头蛇之王》《猎杀恐爪》",
            "final",
            movement="hearth",
        ),
        P(
            19.88,
            27.09,
            "战斗迫近",
            "↳ 做《战斗迫近》",
            "final",
            "《成熟的孢子》：仍按背景采集处理；只有离自然回孢子村已经很近且数量不足时才顺手补，不单独开刷怪圈。",
        ),
        P(
            19.54,
            50.04,
            "孢子村",
            "舒特 → 交《既然我们是朋友......》\n格沙弗 → 交《成熟的孢子》\n姆希菲 → 交《亮顶蘑菇》《孢子村》",
            "final",
        ),
        P(23.32, 66.21, "莉萨奥营地", "观察者莉萨奥 → 交《熟悉的蘑菇》 → 接《偷回蘑菇》", "final"),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "炉石萨布拉金 → 战斗迫近 → 孢子村 → 莉萨奥"
    group["summary"] = "炉石回萨布拉金交北部任务并接《战斗迫近》；完成后自然回孢子村集中交付，再到莉萨奥接《偷回蘑菇》。"
    group["actionHtml"] = "\n".join(
        [
            system_line("使用炉石：萨布拉金", "ra-hearth"),
            point_anchor("萨布拉金"),
            npc_actions("暗影猎手德恩加", turns=("通缉：穆玛基酋长", "通缉：格罗阿克"), accepts=("战斗迫近",)),
            npc_actions("巫医托尔加什", turns=("你见过鱼人吗？",)),
            npc_actions("苏尔加亚", turns=("多头蛇之王", "猎杀恐爪")),
            do_at("战斗迫近", "战斗迫近"),
            point_anchor("孢子村"),
            npc_actions("舒特", turns=("既然我们是朋友......",)),
            npc_actions("格沙弗", turns=("成熟的孢子",)),
            npc_actions("姆希菲", turns=("亮顶蘑菇", "孢子村")),
            point_anchor("莉萨奥营地"),
            npc_actions("观察者莉萨奥", turns=("熟悉的蘑菇",), accepts=("偷回蘑菇",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("成熟的孢子", "仍按背景采集处理；只有离自然回孢子村已经很近且数量不足时才顺手补，不单独开刷怪圈。"),
        note_block("多头蛇之王 / 猎杀恐爪", "只交已经完成的任务；仍未完成就继续保留，不为了交任务等待刷新。"),
    )
    group["timingTaskNames"] = ["战斗迫近"]


def apply_zang_step11(route: dict[str, Any]) -> None:
    group = route["stepGroups"][10]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 2:
        raise RuntimeError(f"Zang step 11 point-count drift: {end - start + 1}")

    points = [
        P(
            44.36,
            66.01,
            "博哈姆废墟",
            "↳ 做《灵魂之盟？》",
            "final",
            "《灵魂之盟？》：在博哈姆废墟台阶底部放置蛮沼图腾，击杀召唤出的蛮沼毒蛇之魂。",
        ),
        P(
            32.38,
            51.96,
            "萨布拉金",
            "使用炉石：萨布拉金\n"
            "暗影猎手德恩加 → 交《战斗迫近》 → 接《你死我活》《警告匕潭失落者》\n"
            "先知亚尼迪 → 交《灵魂之盟？》",
            "final",
            movement="hearth",
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "博哈姆 → 炉石萨布拉金"
    group["summary"] = "在博哈姆完成《灵魂之盟？》后直接炉石萨布拉金，交《战斗迫近》和灵魂任务，并接最后北上两项。"
    group["actionHtml"] = "\n".join(
        [
            do_at("博哈姆废墟", "灵魂之盟？"),
            system_line("使用炉石：萨布拉金", "ra-hearth"),
            point_anchor("萨布拉金"),
            npc_actions("暗影猎手德恩加", turns=("战斗迫近",), accepts=("你死我活", "警告匕潭失落者")),
            npc_actions("先知亚尼迪", turns=("灵魂之盟？",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("灵魂之盟？", "在博哈姆废墟台阶底部放置蛮沼图腾，击杀召唤出的蛮沼毒蛇之魂。"),
    )
    group["timingTaskNames"] = ["灵魂之盟？"]


def apply_zang_step12(route: dict[str, Any]) -> None:
    group = route["stepGroups"][11]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 3:
        raise RuntimeError(f"Zang step 12 point-count drift: {end - start + 1}")

    points = [
        P(32.81, 59.53, "昂古拉走廊", "↳ 做《最锋利的刀刃》", "final"),
        P(25.13, 23.78, "匕潭失落者营地", "↳ 做《警告匕潭失落者》", "final"),
        P(
            18.60,
            7.00,
            "安葛洛什",
            "↳ 做《偷回蘑菇》《你死我活》",
            "final",
            "《偷回蘑菇》《你死我活》：都在安葛洛什区域完成，两条都完成后再离开。",
        ),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "昂古拉走廊 → 匕潭失落者 → 安葛洛什"
    group["summary"] = "从中部走廊一路北上，依次完成《最锋利的刀刃》《警告匕潭失落者》，最后在安葛洛什合并完成《偷回蘑菇》和《你死我活》。"
    group["actionHtml"] = "\n".join(
        [
            do_at("昂古拉走廊", "最锋利的刀刃"),
            do_at("匕潭失落者营地", "警告匕潭失落者"),
            do_at("安葛洛什", "偷回蘑菇", "你死我活"),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("偷回蘑菇", "与《你死我活》都在安葛洛什区域完成，两条都完成后再离开。"),
    )
    group["timingTaskNames"] = ["最锋利的刀刃", "警告匕潭失落者", "偷回蘑菇", "你死我活"]


def apply_zang_step13(route: dict[str, Any]) -> None:
    group = route["stepGroups"][12]
    start = int(group["start"])
    end = int(group["end"])
    if end - start + 1 != 2:
        raise RuntimeError(f"Zang step 13 point-count drift: {end - start + 1}")

    points = [
        P(
            32.38,
            51.96,
            "萨布拉金",
            "使用炉石：萨布拉金\n"
            "加巴林卡 → 交《最锋利的刀刃》\n"
            "暗影猎手德恩加 → 交《警告匕潭失落者》《你死我活》\n"
            "若已完成：苏尔加亚 → 交《多头蛇之王》《猎杀恐爪》",
            "cleanup",
            "《多头蛇之王》《猎杀恐爪》：只交已经完成的任务；仍未完成就跳过，不等待刷新。",
            movement="hearth",
        ),
        P(23.32, 66.21, "莉萨奥营地", "观察者莉萨奥 → 交《偷回蘑菇》", "cleanup"),
    ]
    route["points"][start : end + 1] = points

    group["title"] = "炉石萨布拉金 → 莉萨奥"
    group["summary"] = "炉石回萨布拉金交北部已完成任务；刷新目标只交已经完成的，随后到莉萨奥交《偷回蘑菇》。"
    group["actionHtml"] = "\n".join(
        [
            system_line("使用炉石：萨布拉金", "ra-hearth"),
            point_anchor("萨布拉金"),
            npc_actions("加巴林卡", turns=("最锋利的刀刃",)),
            npc_actions("暗影猎手德恩加", turns=("警告匕潭失落者", "你死我活")),
            conditional_npc_turn_line("苏尔加亚", "：若已完成 ", "多头蛇之王"),
            conditional_npc_turn_line("苏尔加亚", "：若已完成 ", "猎杀恐爪"),
            point_anchor("莉萨奥营地"),
            npc_actions("观察者莉萨奥", turns=("偷回蘑菇",)),
        ]
    )
    group["noteHtml"] = notes_html(
        note_block("多头蛇之王 / 猎杀恐爪", "只交已经完成的任务；仍未完成就跳过，不等待刷新。"),
    )
    group["timingTaskNames"] = []
