from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"


def loc(name: str) -> str:
    return f'<span class="ra-location">{html.escape(name)}</span>'


def npc(name: str) -> str:
    return f'<span class="ra-npc">{html.escape(name)}</span>'


def task(name: str, kind: str) -> str:
    cls = {"turn": "ra-turnin", "accept": "ra-accept", "do": "ra-do-task"}[kind]
    return f'<span class="ra-task {cls}">{html.escape(name)}</span>'


def verb(name: str) -> str:
    return f'<span class="ra-verb">{html.escape(name)}</span>'


def arrow() -> str:
    return '<span class="ra-arrow">→</span>'


def branch() -> str:
    return '<span class="ra-branch">↳</span>'


def point_anchor(name: str) -> str:
    return f'<div class="ra-line ra-point-anchor">{loc(name)}</div>'


def npc_actions(name: str, *, turns: tuple[str, ...] = (), accepts: tuple[str, ...] = ()) -> str:
    parts = [npc(name)]
    if turns:
        parts.extend([arrow(), verb("交"), " ", "、".join(task(x, "turn") for x in turns)])
    if accepts:
        parts.extend([arrow(), verb("接"), " ", "、".join(task(x, "accept") for x in accepts)])
    return '<div class="ra-line">' + "".join(parts) + "</div>"


def do_line(*tasks: str) -> str:
    return (
        '<div class="ra-line ra-do">'
        + branch()
        + verb("做")
        + " "
        + "、".join(task(x, "do") for x in tasks)
        + "</div>"
    )


def do_at(place: str, *tasks: str) -> str:
    return (
        '<div class="ra-line ra-do-inline">'
        + loc(place)
        + '<span class="ra-inline-sep"> </span>'
        + branch()
        + verb("做")
        + " "
        + "、".join(task(x, "do") for x in tasks)
        + "</div>"
    )


def system_line(text: str, cls: str = "ra-transport") -> str:
    return f'<div class="ra-line"><span class="ra-system-action {cls}">{html.escape(text)}</span></div>'


def pickup_accept(item_name: str, quest_name: str) -> str:
    return (
        '<div class="ra-line">'
        + f'拾取{html.escape(item_name)}'
        + arrow()
        + verb("接")
        + " "
        + task(quest_name, "accept")
        + "</div>"
    )


def note_block(quest_name: str, body_html: str) -> str:
    return (
        '<div class="ra-note-block">'
        f'<div class="ra-note-task">《{html.escape(quest_name)}》</div>'
        f'<div class="ra-note-text">{body_html}</div>'
        '</div>'
    )


def notes_html(*blocks: str) -> str:
    if not blocks:
        return ""
    return '<div class="ra-note-heading">备注</div>' + "".join(blocks)


def status_span(status: str) -> str:
    cls = "ra-shared" if status == "共享" else "ra-not-shared"
    return f'<span class="{cls}">{status}：</span>'


def danger(text: str) -> str:
    return f'<span class="ra-danger">{html.escape(text)}</span>'


def key(text: str) -> str:
    return f'<span class="ra-key">{html.escape(text)}</span>'


def set_point(point: list, *, title: str, action: str, note: str = "", fivebox: str = "") -> None:
    while len(point) <= 8:
        point.append("")
    point[2] = title
    point[3] = action
    point[5] = note
    point[8] = fivebox


def apply_step(route: dict, step_number: int, spec: dict) -> None:
    group = route["stepGroups"][step_number - 1]
    expected = spec["expected_title"]
    if group["title"] not in {expected, spec["title"]}:
        raise RuntimeError(
            f"step {step_number} title drift: {group['title']!r} not in "
            f"{{{expected!r}, {spec['title']!r}}}"
        )
    indices = list(range(group["start"], group["end"] + 1))
    if len(indices) != len(spec["points"]):
        raise RuntimeError(
            f"step {step_number} point count drift: actual={len(indices)} expected={len(spec['points'])}"
        )
    group["title"] = spec["title"]
    group["summary"] = spec["summary"]
    group["actionHtml"] = "\n".join(spec["action_html"])
    group["noteHtml"] = spec.get("note_html", "")
    for point_index, point_spec in zip(indices, spec["points"], strict=True):
        set_point(route["points"][point_index], **point_spec)


def patch_steps_5_23_player_copy(route: dict) -> None:
    def update_point(step_number: int, title: str, expected_action: str, action: str, note: str | None = None) -> None:
        group = route["stepGroups"][step_number - 1]
        candidates = [
            route["points"][index]
            for index in range(int(group["start"]), int(group["end"]) + 1)
            if route["points"][index][2] == title
        ]
        old_matches = [point for point in candidates if point[3] == expected_action]
        new_matches = [point for point in candidates if point[3] == action]
        if len(old_matches) == 1 and not new_matches:
            point = old_matches[0]
            point[3] = action
        elif len(new_matches) == 1 and not old_matches:
            point = new_matches[0]
        else:
            raise RuntimeError(
                f"step {step_number} point drift for {title!r}: old={len(old_matches)} new={len(new_matches)}"
            )
        if note is not None:
            point[5] = note

    def replace_action_html(group: dict, old: str, new: str, label: str) -> None:
        text = group["actionHtml"]
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == 1 and new_count == 0:
            group["actionHtml"] = text.replace(old, new, 1)
            return
        if old_count == 0 and new_count == 1:
            return
        raise RuntimeError(f"{label} actionHtml drift: old={old_count} new={new_count}")

    # Step 5: point title already identifies the individual burrow; objective details stay in notes/map.
    for title, suffix in (("东虫孔", "东虫孔；同时做《切断虫源》蛛卵"), ("南虫孔", "南虫孔；同时做《切断虫源》蛛卵"), ("西虫孔", "西虫孔；同时做《切断虫源》蛛卵"), ("北虫孔", "北虫孔；同时补齐《切断虫源》蛛卵")):
        update_point(5, title, f"↳ 做《活埋了那些蟑螂！》：{suffix}", "↳ 做《活埋了那些蟑螂！》《切断虫源》")
    route["stepGroups"][4]["actionHtml"] = "\n".join([
        do_at("东虫孔", "活埋了那些蟑螂！", "切断虫源"),
        do_at("南虫孔", "活埋了那些蟑螂！", "切断虫源"),
        do_at("西虫孔", "活埋了那些蟑螂！", "切断虫源"),
        npc_actions("暗影密探卢瑟尔", turns=("隐藏的真相",), accepts=("尼鲁巴尔的秘密",)),
        do_at("北虫孔", "活埋了那些蟑螂！", "切断虫源"),
    ])

    # Step 7: task skeleton and scripted transport are separate player actions.
    update_point(7, "战歌要塞·亚尼", "亚尼 → 做《魔法飞毯》：使用任务脚本飞毯前往加尔鲁什码头", "亚尼 → 做《魔法飞毯》\n任务脚本飞行：战歌要塞 → 加尔鲁什码头")
    g = route["stepGroups"][6]
    old = '<div class="ra-line"><span class="ra-npc">亚尼</span><span class="ra-arrow">→</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">魔法飞毯</span>：<span class="ra-system-action ra-flightpath">任务脚本飞行前往加尔鲁什码头</span></div>'
    new = "\n".join([do_at("战歌要塞·亚尼", "魔法飞毯"), system_line("任务脚本飞行：战歌要塞 → 加尔鲁什码头", "ra-flightpath")])
    replace_action_html(g, old, new, "step 7 magic carpet")

    # Step 9: fixed item/overlap/escort mechanics belong in notes.
    update_point(9, "回音海岸南侧岸边小屋", "↳ 做《莫布的坦克零件气动装配器》：进入约(32.4,49.2)小屋，拾取屋内固定零件", "↳ 做《莫布的坦克零件气动装配器》", "《莫布的坦克零件气动装配器》：固定零件在约(32.4,49.2)岸边小屋内，不在屋外地面。")
    update_point(9, "回音海岸克瓦迪尔怪区", "↳ 做《超强度金属板！》《深入迷雾》《古代水手的号角》：同一怪区一起推进；离开前确认五号均达到交付条件", "↳ 做《超强度金属板！》《深入迷雾》《古代水手的号角》", "三条任务在同一克瓦迪尔怪区推进；离开前确认五号均达到交付条件，不为其中任何一条单独折返。")
    update_point(9, "回音海岸", "小穆图 → 接《逃离迷雾》\n↳ 做《逃离迷雾》：护送小穆图", "小穆图 → 接《逃离迷雾》\n↳ 做《逃离迷雾》")
    route["stepGroups"][8]["actionHtml"] = "\n".join([
        do_at("回音海岸南侧岸边小屋", "莫布的坦克零件气动装配器"),
        do_at("回音海岸克瓦迪尔怪区", "超强度金属板！", "深入迷雾", "古代水手的号角"),
        point_anchor("回音海岸"), npc_actions("小穆图", accepts=("逃离迷雾",)), do_line("逃离迷雾"),
    ])

    # Step 11: ship/horn use is special operation detail, not action-line prose.
    for title in ("伯尔之锤", "库尔达卡", "毒蛇之喉", "伯尔之砧"):
        update_point(11, title, f"↳ 做《烧毁船只》：对{title}使用海象人火炬", "↳ 做《烧毁船只》")
    update_point(11, "战歌码头尽头", "↳ 做《舵手奥拉布斯》：吹响号角，完成奥拉布斯事件", "↳ 做《舵手奥拉布斯》", "《舵手奥拉布斯》：在战歌码头最西端旗帜/塔附近约(26.8,54.8)使用古代水手的号角触发事件。")
    route["stepGroups"][10]["actionHtml"] = "\n".join([
        do_at("伯尔之锤", "烧毁船只"), do_at("库尔达卡", "烧毁船只"), do_at("毒蛇之喉", "烧毁船只"), do_at("战歌码头尽头", "舵手奥拉布斯"), do_at("伯尔之砧", "烧毁船只"),
    ])
    route["stepGroups"][10]["noteHtml"] = notes_html(
        note_block("烧毁船只", '不是清船上怪自动完成；四艘船都要站到船上/船体可用范围，主动使用海象人火炬。' + '<div class="ra-fivebox-line"><span class="ra-pending">五开待实测：</span>一号点燃船只是否可同步五号进度；若不共享，五号需分别使用火炬。</div>'),
        note_block("舵手奥拉布斯", "在战歌码头最西端旗帜/塔附近约(26.8,54.8)使用古代水手的号角触发事件。"),
    )

    # Step 12: vehicle mechanics go to the task note.
    update_point(12, "加尔鲁什码头", "部落攻城坦克 → ↳ 做《纳萨姆平原》：五号分别上坦克", "↳ 做《纳萨姆平原》", "《纳萨姆平原》：不共享：五号分别上部落攻城坦克执行。")
    update_point(12, "纳萨姆平原", "↳ 做《纳萨姆平原》：坦克清100天灾、完成救援并指认指挥官", "↳ 做《纳萨姆平原》", "《纳萨姆平原》：使用坦克完成100个天灾目标、救援并指认指挥官；五号分别完成，实跑单号最长约3分钟。")
    g = route["stepGroups"][11]
    g["actionHtml"] = "\n".join([
        npc_actions("瓦托尔", turns=("烧毁船只", "舵手奥拉布斯"), accepts=("找到卡鲁克！",)),
        do_at("加尔鲁什码头", "纳萨姆平原"), do_at("纳萨姆平原", "纳萨姆平原"),
    ])
    g["noteHtml"] = notes_html(note_block("纳萨姆平原", status_span("不共享") + "五号分别上部落攻城坦克，使用坦克完成100个天灾目标、救援并指认指挥官；实跑单号最长约3分钟。"))

    # Step 13: freeing the NPC is the prerequisite for accepting, not part of the accept action text.
    update_point(13, "裂鞭海岸·被俘虏的海象人", "清掉周围科瓦迪尔并击杀出现的娜迦，救出被俘虏的海象人 → 接《残忍的科瓦迪尔》", "被俘虏的海象人 → 接《残忍的科瓦迪尔》", "《残忍的科瓦迪尔》：先清掉周围科瓦迪尔并击杀出现的娜迦，救出海象人；等他变成可接任务NPC后再接任务。")
    update_point(13, "裂鞭海岸·斯卡迪尔营地", "↳ 做《卡鲁克的誓言》：击杀6名斯卡迪尔袭击者、5名斯卡迪尔船工", "↳ 做《卡鲁克的誓言》")
    g = route["stepGroups"][12]
    g["actionHtml"] = "\n".join([
        point_anchor("裂鞭海岸"), npc_actions("卡鲁克", turns=("找到卡鲁克！",), accepts=("卡鲁克的誓言",)),
        point_anchor("裂鞭海岸·被俘虏的海象人"), npc_actions("被俘虏的海象人", accepts=("残忍的科瓦迪尔",)),
        do_at("裂鞭海岸·斯卡迪尔营地", "卡鲁克的誓言"),
        npc_actions("卡鲁克", turns=("卡鲁克的誓言", "残忍的科瓦迪尔"), accepts=("残忍的贾梅尔",)),
    ])

    # Step 15: target/use/loot mechanics are notes; task action stays skeletal.
    update_point(15, "裂鞭废墟东北部", "↳ 做《纳兹亚的三叉戟》：击杀拉格纳·德拉卡伦并拾取纳兹亚的三叉戟", "↳ 做《纳兹亚的三叉戟》", "《纳兹亚的三叉戟》：击杀拉格纳·德拉卡伦并拾取纳兹亚的三叉戟。")
    update_point(15, "裂鞭废墟北部冰山下", "↳ 做《使者》：下潜找到利维洛斯，对它使用纳兹亚的三叉戟后击杀", "↳ 做《使者》", "《使者》：目标在水下冰山底部；下潜找到利维洛斯，对它使用纳兹亚的三叉戟后击杀。Questie约(52.1,88.2)只给平面坐标。")
    g = route["stepGroups"][14]
    g["actionHtml"] = "\n".join([do_at("裂鞭废墟东北部", "纳兹亚的三叉戟"), npc_actions("维赫亚", turns=("纳兹亚的三叉戟",), accepts=("使者",)), do_at("裂鞭废墟北部冰山下", "使者"), npc_actions("卡鲁克", turns=("使者",))])
    g["noteHtml"] = notes_html(
        note_block("纳兹亚的三叉戟", '击杀拉格纳·德拉卡伦并拾取纳兹亚的三叉戟。<div class="ra-fivebox-line"><span class="ra-pending">五开待实测：</span>同一具尸体上的三叉戟是否能让五个角色分别拾取。</div>'),
        note_block("使者", '<span class="ra-danger">目标在水下、冰山底部</span>；Questie约(52.1,88.2)只给平面坐标。下潜找到利维洛斯，对它使用纳兹亚的三叉戟后击杀。<div class="ra-fivebox-line"><span class="ra-pending">五开待实测：</span>是否只需一个角色使用三叉戟并参与击杀即可同步五号进度。</div>'),
    )

    # Step 16: opportunity item-start quest follows the same drop-trigger display rule.
    update_point(16, "战歌要塞南门·伊斯里克斯事件", "若事件正在进行 → 完成事件并击杀收割者伊斯里克斯 → 拾取伊斯里克斯的甲壳 → 接《寒风中的怪兽……》；若无事件/甲壳，直接继续，不等待", "若事件正在进行 → 接《寒风中的怪兽……》；否则继续，不等待")
    g = route["stepGroups"][15]
    verbose = '<div class="ra-line">若事件正在进行<span class="ra-arrow">→</span>完成事件并击杀<span class="ra-npc">收割者伊斯里克斯</span><span class="ra-arrow">→</span>拾取伊斯里克斯的甲壳<span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">寒风中的怪兽……</span></div>\n<div class="ra-line">若无事件/甲壳<span class="ra-arrow">→</span><span class="ra-danger">直接继续，不等待</span></div>'
    concise = '<div class="ra-line">若事件正在进行' + arrow() + verb("接") + ' ' + task("寒风中的怪兽……", "accept") + '；否则<span class="ra-danger">继续，不等待</span></div>'
    replace_action_html(g, verbose, concise, "step 16 Isrikk")

    # Step 18: reconnaissance/kill/count mechanics leave the action line.
    for title in ("托普的农场", "战歌粮仓", "战歌屠宰场"):
        update_point(18, title, f"↳ 做《战歌农场》：侦察{title}", "↳ 做《战歌农场》")
    update_point(18, "战歌农场西南怪区 / 囚笼", "↳ 做《慈悲为怀》：主控杀恩其拉通灵领主/战歌畸变体拿5把天灾牢笼钥匙，开5个囚笼\n↳ 做《该死的猪》：击杀10只亡灵猪", "↳ 做《慈悲为怀》《该死的猪》", "《慈悲为怀》：共享：主控击杀恩其拉通灵领主/战歌畸变体取得5把天灾牢笼钥匙，开5个囚笼即可同步全队。\n《该死的猪》：击杀10只亡灵猪。")
    g = route["stepGroups"][17]
    g["actionHtml"] = "\n".join([do_at("托普的农场", "战歌农场"), do_at("战歌粮仓", "战歌农场"), do_at("战歌农场西南怪区 / 囚笼", "慈悲为怀", "该死的猪"), do_at("战歌屠宰场", "战歌农场")])
    g["noteHtml"] = notes_html(note_block("慈悲为怀", status_span("共享") + "主控击杀恩其拉通灵领主/战歌畸变体取得5把天灾牢笼钥匙，开5个囚笼即可同步全队。"), note_block("该死的猪", "击杀10只亡灵猪。"))

    # Step 19: kodo operation is fully in the note.
    update_point(19, "感染科多兽区", "↳ 做《把它们活着带回去》：对感染的科多兽使用托普的科多兽缰绳 → 骑回农夫托普 → 按载具栏“交付/放下科多”；完成8只", "↳ 做《把它们活着带回去》", "《把它们活着带回去》：对感染的科多兽使用托普的科多兽缰绳，骑回农夫托普后必须按载具栏“交付/放下科多”才计数；每号完成8只，任务缰绳有效10分钟。")
    g = route["stepGroups"][18]
    old = '<div class="ra-line ra-do-inline"><span class="ra-location">感染科多兽区</span> <span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">把它们活着带回去</span>：对感染的科多兽使用托普的科多兽缰绳<span class="ra-arrow">→</span>骑回农夫托普<span class="ra-arrow">→</span>按载具栏“交付/放下科多”；完成8只</div>'
    new = do_at("感染科多兽区", "把它们活着带回去")
    replace_action_html(g, old, new, "step 19 kodo")
    g["noteHtml"] = notes_html(note_block("把它们活着带回去", '对感染的科多兽使用托普的科多兽缰绳，骑回农夫托普后<span class="ra-danger">必须按载具栏“交付/放下科多”</span>才计数；每号完成8只，任务缰绳有效10分钟。<div class="ra-fivebox-line"><span class="ra-pending">五开待实测：</span>科多救援计数是否共享。</div>'))

    # Steps 20-23: normal objective prose moves into existing/supplemented notes.
    update_point(20, "残忍的瓦雷杜斯", "↳ 做《愚蠢的努力》：击杀残忍的瓦雷杜斯", "↳ 做《愚蠢的努力》")
    g = route["stepGroups"][19]
    old = '<div class="ra-line ra-do-inline"><span class="ra-location">残忍的瓦雷杜斯</span> <span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">愚蠢的努力</span>：击杀残忍的瓦雷杜斯</div>'
    new = do_at("残忍的瓦雷杜斯", "愚蠢的努力")
    replace_action_html(g, old, new, "step 20 Valredus")

    update_point(21, "战歌要塞", "典狱官诺克·血怒 → 交《诺克·血怒》 → 接《逃兵快递，30分钟送到否则免费》\n↳ 做《逃兵快递，30分钟送到否则免费》：带联盟逃兵到东侧十字路口约(55.3,50.8)，使用战歌信号枪完成交付", "典狱官诺克·血怒 → 交《诺克·血怒》 → 接《逃兵快递，30分钟送到否则免费》\n↳ 做《逃兵快递，30分钟送到否则免费》")
    g = route["stepGroups"][20]
    old = '<div class="ra-line ra-do-inline"><span class="ra-location">战歌要塞东侧十字路口约(55.3,50.8)</span> <span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">逃兵快递，30分钟送到否则免费</span>：带联盟逃兵到点，使用战歌信号枪</div>'
    new = do_at("战歌要塞东侧十字路口约(55.3,50.8)", "逃兵快递，30分钟送到否则免费")
    replace_action_html(g, old, new, "step 21 deserter")

    update_point(22, "血孢平原", "↳ 做《清除北地狗头人》：击杀8名血孢收割者、5名血孢点火者、2名血孢烘烤者\n↳ 做《奇妙的血孢》：收集10片血孢心皮", "↳ 做《清除北地狗头人》《奇妙的血孢》")
    update_point(22, "迦莫斯洞穴上方高处·巨大的发光蛾卵", "↳ 做《授粉的巨蛾》：在巨蛋附近收集5份花粉\n巨大的发光蛾卵 → 接《巨大的蛾卵》", "↳ 做《授粉的巨蛾》\n巨大的发光蛾卵 → 接《巨大的蛾卵》")
    update_point(22, "血孢平原", "血法师劳莉丝 → 交《授粉的巨蛾》《巨大的蛾卵》 → 接《完美的测试对象》\n↳ 做《完美的测试对象》：在劳莉丝旁使用授过粉的血孢花 → 交《完美的测试对象》 → 接《攻打迦莫斯》\n普雷玛·巨角 → 交《攻打迦莫斯》 → 接《折磨者迦莫斯拉》", "血法师劳莉丝 → 交《授粉的巨蛾》《巨大的蛾卵》 → 接《完美的测试对象》\n↳ 做《完美的测试对象》\n血法师劳莉丝 → 交《完美的测试对象》 → 接《攻打迦莫斯》\n普雷玛·巨角 → 交《攻打迦莫斯》 → 接《折磨者迦莫斯拉》")
    g = route["stepGroups"][21]
    g["actionHtml"] = "\n".join([
        point_anchor("血孢平原"), do_line("清除北地狗头人", "奇妙的血孢"), npc_actions("斥候图古克", turns=("清除北地狗头人",)), npc_actions("血法师劳莉丝", turns=("奇妙的血孢",), accepts=("授粉的巨蛾",)),
        point_anchor("迦莫斯洞穴上方高处·巨大的发光蛾卵约(48.55,59.04)"), do_line("授粉的巨蛾"), '<div class="ra-line">巨大的发光蛾卵' + arrow() + verb("接") + ' ' + task("巨大的蛾卵", "accept") + '</div>',
        point_anchor("血孢平原"), npc_actions("血法师劳莉丝", turns=("授粉的巨蛾", "巨大的蛾卵"), accepts=("完美的测试对象",)), do_line("完美的测试对象"), npc_actions("血法师劳莉丝", turns=("完美的测试对象",), accepts=("攻打迦莫斯",)), npc_actions("普雷玛·巨角", turns=("攻打迦莫斯",), accepts=("折磨者迦莫斯拉",)),
    ])

    update_point(23, "迦莫斯洞穴底层", "↳ 做《折磨者迦莫斯拉》：对迦莫斯拉使用碾碎的血孢花粉袋削弱 → 击杀 → 拾取迦莫斯拉的头颅", "↳ 做《折磨者迦莫斯拉》")
    g = route["stepGroups"][22]
    old = '<div class="ra-line ra-do-inline"><span class="ra-location">迦莫斯洞穴底层</span> <span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">折磨者迦莫斯拉</span>：对<span class="ra-npc">迦莫斯拉</span>使用碾碎的血孢花粉袋削弱<span class="ra-arrow">→</span>击杀<span class="ra-arrow">→</span>拾取迦莫斯拉的头颅</div>'
    new = do_at("迦莫斯洞穴底层", "折磨者迦莫斯拉")
    replace_action_html(g, old, new, "step 23 Gammothra")


def patch_step46_transport(route: dict) -> None:
    group = route["stepGroups"][45]
    if group["title"] != "天崩地裂 / 过关斩将 → 牦牛村":
        raise RuntimeError(f"step 46 title drift: {group['title']!r}")
    matching = [
        index
        for index in range(int(group["start"]), int(group["end"]) + 1)
        if route["points"][index][2] == "纳克萨纳尔"
    ]
    if len(matching) != 1:
        raise RuntimeError(f"step 46 Naxxanar point drift: {matching}")
    point = route["points"][matching[0]]
    new_action = "使用外部传送器：进入纳克萨纳尔\n↳ 做《过关斩将》\n任务中途使用内部传送器：前往上层"
    old_html = '<div class="ra-line ra-do-inline"><span class="ra-location">纳克萨纳尔</span> <span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">过关斩将</span></div>'
    new_html = "\n".join(
        [
            system_line("使用外部传送器：进入纳克萨纳尔"),
            do_at("纳克萨纳尔", "过关斩将"),
            system_line("任务中途使用内部传送器：前往上层"),
        ]
    )
    if point[3] == new_action and new_html in group["actionHtml"]:
        return
    if point[3] != "↳ 做《过关斩将》" or group["actionHtml"].count(old_html) != 1:
        raise RuntimeError("step 46 Naxxanar actionHtml drift")
    point[3] = new_action
    group["actionHtml"] = group["actionHtml"].replace(old_html, new_html, 1)


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    route = routes["borean"]
    patch_steps_5_23_player_copy(route)
    patch_step46_transport(route)

    specs: dict[int, dict] = {
        50: {
            "expected_title": "审讯 → 与时间赛跑 → 准备飞翔",
            "title": "法师塔二楼 → 与时间赛跑 → 苏雷斯塔兹",
            "summary": "在法师塔二楼推进审讯链，下楼由多纳森接出《与时间赛跑》；完成后回琥珀崖经多纳森与苏雷斯塔兹接到《准备飞翔》。",
            "points": [
                {
                    "title": "琥珀崖·法师塔二楼",
                    "action": "图书管理员诺曼提斯 → 交《苔原上的审讯》 → 接《说服的艺术》\n↳ 做《说服的艺术》\n图书管理员诺曼提斯 → 交《说服的艺术》 → 接《分享情报》\n下楼：图书管理员多纳森 → 交《分享情报》 → 接《与时间赛跑》",
                    "note": "《说服的艺术》：目标就在诺曼提斯旁边的椅子上；对被封印的蓝玉巫师反复使用任务提供的催眠魔杖，直到任务完成。",
                },
                {
                    "title": "蓝玉营地·圆形平台",
                    "action": "↳ 做《与时间赛跑》",
                    "note": "《与时间赛跑》：到蓝玉营地最大的圆形平台，对审讯者莎尔兰德的护盾使用任务提供的护盾破坏道具；她落地后击杀。死亡后会出现锁箱，从锁箱拾取莎尔兰德的断裂钥匙，不是直接摸尸体。",
                },
                {
                    "title": "琥珀崖",
                    "action": "图书管理员多纳森 → 交《与时间赛跑》 → 接《重铸钥匙》\n苏雷斯塔兹 → 交《重铸钥匙》 → 接《准备飞翔》",
                },
            ],
            "action_html": [
                point_anchor("琥珀崖·法师塔二楼"),
                npc_actions("图书管理员诺曼提斯", turns=("苔原上的审讯",), accepts=("说服的艺术",)),
                do_line("说服的艺术"),
                npc_actions("图书管理员诺曼提斯", turns=("说服的艺术",), accepts=("分享情报",)),
                point_anchor("琥珀崖·法师塔一楼"),
                npc_actions("图书管理员多纳森", turns=("分享情报",), accepts=("与时间赛跑",)),
                do_at("蓝玉营地·圆形平台", "与时间赛跑"),
                point_anchor("琥珀崖"),
                npc_actions("图书管理员多纳森", turns=("与时间赛跑",), accepts=("重铸钥匙",)),
                npc_actions("苏雷斯塔兹", turns=("重铸钥匙",), accepts=("准备飞翔",)),
            ],
            "note_html": notes_html(
                note_block(
                    "说服的艺术",
                    f'目标就在诺曼提斯旁边的椅子上；对被封印的蓝玉巫师反复使用任务提供的催眠魔杖，直到任务完成。',
                ),
                note_block(
                    "与时间赛跑",
                    f'到蓝玉营地最大的圆形平台，对审讯者莎尔兰德的护盾使用任务提供的护盾破坏道具；她落地后击杀。死亡后会出现{key("锁箱")}，从锁箱拾取莎尔兰德的断裂钥匙，{danger("不是直接摸尸体")}。',
                ),
            ),
        },
        51: {
            "expected_title": "营救艾瓦诺尔 → 飞考达拉",
            "title": "营救艾瓦诺尔 → 苏雷斯塔兹 → 考达拉",
            "summary": "由战斗法师安斯姆启动任务飞行完成《营救艾瓦诺尔》；回琥珀崖交接到《飞越裂谷》，再乘任务飞行进入考达拉。",
            "points": [
                {
                    "title": "琥珀崖·战斗法师安斯姆",
                    "action": "战斗法师安斯姆 → 交《准备飞翔》 → 接《营救艾瓦诺尔》\n启动任务飞行：蓝玉营地上方平台\n↳ 做《营救艾瓦诺尔》",
                    "note": "《营救艾瓦诺尔》：启动前先下普通坐骑并停稳。落地后按任务脚本完成营救；完成后由艾瓦诺尔的脚本直接送回琥珀崖，不要自己跳崖离开。",
                },
                {
                    "title": "琥珀崖·法师塔",
                    "action": "大法师艾瓦诺尔 → 交《营救艾瓦诺尔》 → 接《苏雷斯塔兹》",
                },
                {
                    "title": "琥珀崖·苏雷斯塔兹",
                    "action": "苏雷斯塔兹 → 交《苏雷斯塔兹》 → 接《飞越裂谷》\n启动任务飞行：考达拉",
                },
            ],
            "action_html": [
                point_anchor("琥珀崖"),
                npc_actions("战斗法师安斯姆", turns=("准备飞翔",), accepts=("营救艾瓦诺尔",)),
                system_line("启动任务飞行：蓝玉营地上方平台"),
                do_line("营救艾瓦诺尔"),
                npc_actions("大法师艾瓦诺尔", turns=("营救艾瓦诺尔",), accepts=("苏雷斯塔兹",)),
                npc_actions("苏雷斯塔兹", turns=("苏雷斯塔兹",), accepts=("飞越裂谷",)),
                system_line("启动任务飞行：考达拉"),
            ],
            "note_html": notes_html(
                note_block(
                    "营救艾瓦诺尔",
                    f'启动前先下普通坐骑并停稳。落地后按任务脚本完成营救；完成后由艾瓦诺尔的脚本直接送回琥珀崖，{danger("不要自己跳崖离开")}。',
                )
            ),
        },
        52: {
            "expected_title": "永生之盾开场 → 南 / 西监测点",
            "title": "永生之盾 → 南部 / 西部监测点",
            "summary": "抵达永生之盾后开飞行点并接齐当前户外任务；先完成南部与西部监测点，同时推进同区域任务。",
            "points": [
                {
                    "title": "考达拉·永生之盾",
                    "action": "开飞行点：永生之盾（五号分别）\n大法师伯林纳德 → 交《飞越裂谷》 → 接《监测数据》《古树的秘密》\n图书馆员塞尔拉 → 接《冰冷的草莓》\n莱洛拉斯 → 接《基本的训练》",
                },
                {
                    "title": "考达拉南部监测点",
                    "action": "↳ 做《监测数据》《古树的秘密》《冰冷的草莓》《基本的训练》",
                    "note": "《监测数据》：四个点都是固定地质监测仪，必须主动点击读取数据；南(28.5,35.0)、西(22.5,23.8)、东北(31.5,20.4)、中央(28.3,28.5)。",
                },
                {
                    "title": "考达拉西部监测点",
                    "action": "↳ 做《监测数据》《古树的秘密》《冰冷的草莓》《基本的训练》",
                },
            ],
            "action_html": [
                point_anchor("考达拉·永生之盾"),
                system_line("开飞行点：永生之盾（五号分别）", "ra-flightpoint"),
                npc_actions("大法师伯林纳德", turns=("飞越裂谷",), accepts=("监测数据", "古树的秘密")),
                npc_actions("图书馆员塞尔拉", accepts=("冰冷的草莓",)),
                npc_actions("莱洛拉斯", accepts=("基本的训练",)),
                do_at("考达拉南部监测点", "监测数据", "古树的秘密", "冰冷的草莓", "基本的训练"),
                do_at("考达拉西部监测点", "监测数据", "古树的秘密", "冰冷的草莓", "基本的训练"),
            ],
            "note_html": notes_html(
                note_block(
                    "监测数据",
                    '四个点都是固定地质监测仪，必须主动点击读取数据；南(28.5,35.0)、西(22.5,23.8)、东北(31.5,20.4)、中央(28.3,28.5)。',
                )
            ),
        },
        53: {
            "expected_title": "北部监测 → 中央监测 → 永生之盾回收",
            "title": "北部 / 东北 / 中央监测点 → 永生之盾",
            "summary": "完成北部、东北和中央监测点并补齐同区域任务；回永生之盾交付，接《保持隐蔽》和《蓝龙的卵》。",
            "points": [
                {
                    "title": "考达拉北部",
                    "action": "↳ 做《监测数据》《古树的秘密》《冰冷的草莓》《基本的训练》",
                    "note": "《监测数据》：监测仪需要主动点击；本段依次处理东北(31.5,20.4)与中央(28.3,28.5)，不要只到坐标附近等待自动完成。",
                },
                {
                    "title": "考达拉东北监测点",
                    "action": "↳ 做《监测数据》",
                },
                {
                    "title": "考达拉中央监测点",
                    "action": "↳ 做《监测数据》《古树的秘密》《冰冷的草莓》《基本的训练》",
                },
                {
                    "title": "考达拉·永生之盾",
                    "action": "大法师伯林纳德 → 交《监测数据》《古树的秘密》\n图书馆员塞尔拉 → 交《冰冷的草莓》 → 接《保持隐蔽》\n莱洛拉斯 → 交《基本的训练》 → 接《蓝龙的卵》",
                },
            ],
            "action_html": [
                do_at("考达拉北部", "监测数据", "古树的秘密", "冰冷的草莓", "基本的训练"),
                do_at("考达拉东北监测点", "监测数据"),
                do_at("考达拉中央监测点", "监测数据", "古树的秘密", "冰冷的草莓", "基本的训练"),
                point_anchor("考达拉·永生之盾"),
                npc_actions("大法师伯林纳德", turns=("监测数据", "古树的秘密")),
                npc_actions("图书馆员塞尔拉", turns=("冰冷的草莓",), accepts=("保持隐蔽",)),
                npc_actions("莱洛拉斯", turns=("基本的训练",), accepts=("蓝龙的卵",)),
            ],
            "note_html": notes_html(
                note_block(
                    "监测数据",
                    '监测仪需要主动点击；本段依次处理东北(31.5,20.4)与中央(28.3,28.5)，不要只到坐标附近等待自动完成。',
                )
            ),
        },
        54: {
            "expected_title": "考达拉第二圈 → 触发《奇怪……》",
            "title": "考达拉外圈 → 奇怪…… → 永生之盾",
            "summary": "在考达拉外圈完成《保持隐蔽》《蓝龙的卵》，并从考达拉缚法者取得闪光碎片触发《奇怪……》；回永生之盾交接《猎龙》《牢笼》。",
            "points": [
                {
                    "title": "考达拉外圈",
                    "action": "↳ 做《保持隐蔽》《蓝龙的卵》\n拾取闪光碎片 → 接《奇怪……》",
                    "note": "《蓝龙的卵》：共享：先杀考达拉龙人取得冰霜战斧，再由主控用战斧打碎蓝龙卵。\n《奇怪……》：来源怪必须是人形的考达拉缚法者，常带一只蓝色猎犬；主要在考达拉西北/北部约(33—35,26—30)。击杀后拾取闪光碎片触发任务；不要误刷名称相近的考达拉织法者。",
                },
                {
                    "title": "考达拉·永生之盾",
                    "action": "图书馆员塞尔拉 → 交《保持隐蔽》\n莱洛拉斯 → 交《蓝龙的卵》 → 接《猎龙》\n莱洛拉斯 → 交《奇怪……》 → 接《牢笼》",
                },
            ],
            "action_html": [
                do_at("考达拉外圈", "保持隐蔽", "蓝龙的卵"),
                pickup_accept("闪光碎片", "奇怪……"),
                point_anchor("考达拉·永生之盾"),
                npc_actions("图书馆员塞尔拉", turns=("保持隐蔽",)),
                npc_actions("莱洛拉斯", turns=("蓝龙的卵",), accepts=("猎龙",)),
                npc_actions("莱洛拉斯", turns=("奇怪……",), accepts=("牢笼",)),
            ],
            "note_html": notes_html(
                note_block(
                    "蓝龙的卵",
                    status_span("共享") + '先杀考达拉龙人取得冰霜战斧，再由主控用战斧打碎蓝龙卵。',
                ),
                note_block(
                    "奇怪……",
                    f'来源怪必须是人形的考达拉缚法者，常带一只蓝色猎犬；主要在考达拉西北/北部约(33—35,26—30)。击杀后拾取闪光碎片触发任务；{danger("不要误刷名称相近的考达拉织法者")}。',
                ),
            ),
        },
        55: {
            "expected_title": "牢笼 + 猎龙 → 克莉斯塔萨 / 诱饵",
            "title": "戈德拉克 / 塞鲁利恩 → 猎龙 → 永生之盾",
            "summary": "完成《牢笼》和《猎龙》，把捕获的魔枢雏龙带回永生之盾；继续推进《克莉斯塔萨》并接《诱饵》。",
            "points": [
                {
                    "title": "战争使者戈德拉克",
                    "action": "↳ 做《牢笼》",
                    "note": "《牢笼》：共享：能量核心与牢笼外壳进度同步；主控完成两名目标即可。",
                },
                {
                    "title": "塞鲁利恩将军",
                    "action": "↳ 做《牢笼》",
                },
                {
                    "title": "魔枢雏龙",
                    "action": "↳ 做《猎龙》",
                    "note": "《猎龙》：共享：对空中的魔枢雏龙使用莱洛拉斯的长矛；这是捕获任务，不要把目标打死。命中后等待捕获生效，再带回莱洛拉斯。",
                },
                {
                    "title": "考达拉·永生之盾",
                    "action": "莱洛拉斯 → 交《猎龙》 → 接《破译密码》\n莱洛拉斯 → 交《牢笼》\n克莉斯塔萨 → 接《克莉斯塔萨》\n↳ 做《克莉斯塔萨》\n克莉斯塔萨 → 交《克莉斯塔萨》 → 接《诱饵》",
                },
            ],
            "action_html": [
                do_at("战争使者戈德拉克", "牢笼"),
                do_at("塞鲁利恩将军", "牢笼"),
                do_at("魔枢雏龙", "猎龙"),
                point_anchor("考达拉·永生之盾"),
                npc_actions("莱洛拉斯", turns=("猎龙",), accepts=("破译密码",)),
                npc_actions("莱洛拉斯", turns=("牢笼",)),
                npc_actions("克莉斯塔萨", accepts=("克莉斯塔萨",)),
                do_line("克莉斯塔萨"),
                npc_actions("克莉斯塔萨", turns=("克莉斯塔萨",), accepts=("诱饵",)),
            ],
            "note_html": notes_html(
                note_block("牢笼", status_span("共享") + '能量核心与牢笼外壳进度同步；主控完成两名目标即可。'),
                note_block(
                    "猎龙",
                    status_span("共享") + f'对空中的魔枢雏龙使用莱洛拉斯的长矛；这是捕获任务，{danger("不要把目标打死")}。命中后等待捕获生效，再带回莱洛拉斯。',
                ),
            ),
        },
        56: {
            "expected_title": "诱饵 → 莎拉苟萨",
            "title": "考达拉目标区 → 莎拉苟萨平台",
            "summary": "完成《诱饵》《破译密码》，回永生之盾接《莎拉苟萨的末日》；通过克莉斯塔萨脚本进入高处平台完成莎拉苟萨事件。",
            "points": [
                {
                    "title": "考达拉目标区",
                    "action": "↳ 做《诱饵》《破译密码》",
                },
                {
                    "title": "考达拉·永生之盾",
                    "action": "莱洛拉斯 → 交《破译密码》\n克莉斯塔萨 → 交《诱饵》 → 接《莎拉苟萨的末日》",
                },
                {
                    "title": "莎拉苟萨平台",
                    "action": "启动克莉斯塔萨任务脚本：前往高处平台\n↳ 做《莎拉苟萨的末日》\n通过克莉斯塔萨任务脚本返回\n克莉斯塔萨 → 交《莎拉苟萨的末日》 → 接《集结红龙》",
                    "note": "《莎拉苟萨的末日》：莎拉苟萨不在地面常驻。先使用任务给的强化奥术牢笼联系克莉斯塔萨并选择准备就绪，脚本会送到高处平台；到平台后使用奥术能量源召出莎拉苟萨。击杀后仍通过克莉斯塔萨脚本返回。",
                },
            ],
            "action_html": [
                do_at("考达拉目标区", "诱饵", "破译密码"),
                point_anchor("考达拉·永生之盾"),
                npc_actions("莱洛拉斯", turns=("破译密码",)),
                npc_actions("克莉斯塔萨", turns=("诱饵",), accepts=("莎拉苟萨的末日",)),
                system_line("启动克莉斯塔萨任务脚本：前往高处平台"),
                do_line("莎拉苟萨的末日"),
                system_line("通过克莉斯塔萨任务脚本返回"),
                npc_actions("克莉斯塔萨", turns=("莎拉苟萨的末日",), accepts=("集结红龙",)),
            ],
            "note_html": notes_html(
                note_block(
                    "莎拉苟萨的末日",
                    '莎拉苟萨不在地面常驻。先使用任务给的强化奥术牢笼联系克莉斯塔萨并选择准备就绪，脚本会送到高处平台；到平台后使用奥术能量源召出莎拉苟萨。击杀后仍通过克莉斯塔萨脚本返回。',
                )
            ),
        },
        57: {
            "expected_title": "集结红龙 → 触动陷阱 → 考达拉户外收尾",
            "title": "永生之盾 → 信号火焰 → 莱洛拉斯",
            "summary": "交《集结红龙》接《触动陷阱》，到信号火焰完成事件后回莱洛拉斯交付。",
            "points": [
                {
                    "title": "考达拉·永生之盾",
                    "action": "莱洛拉斯 → 交《集结红龙》 → 接《触动陷阱》",
                },
                {
                    "title": "考达拉·信号火焰",
                    "action": "↳ 做《触动陷阱》",
                    "note": "《触动陷阱》：到信号火焰约(25.4,21.8)，站在火焰旁使用任务物品莱洛拉斯的火花触发事件；到坐标不会自动完成。",
                },
                {
                    "title": "考达拉·永生之盾",
                    "action": "莱洛拉斯 → 交《触动陷阱》",
                },
            ],
            "action_html": [
                point_anchor("考达拉·永生之盾"),
                npc_actions("莱洛拉斯", turns=("集结红龙",), accepts=("触动陷阱",)),
                do_at("考达拉·信号火焰", "触动陷阱"),
                point_anchor("考达拉·永生之盾"),
                npc_actions("莱洛拉斯", turns=("触动陷阱",)),
            ],
            "note_html": notes_html(
                note_block(
                    "触动陷阱",
                    '到信号火焰约(25.4,21.8)，站在火焰旁使用任务物品莱洛拉斯的火花触发事件；到坐标不会自动完成。',
                )
            ),
        },
        58: {
            "expected_title": "永生之盾收尾 → 系统鸟回琥珀崖",
            "title": "永生之盾 → 系统鸟琥珀崖",
            "summary": "考达拉任务结束后回永生之盾飞行管理员，乘系统鸟返回琥珀崖。",
            "points": [
                {"title": "考达拉·永生之盾", "action": "到飞行管理员处"},
                {"title": "永生之盾飞行点", "action": "乘系统鸟：永生之盾 → 琥珀崖"},
                {"title": "琥珀崖", "action": "抵达琥珀崖"},
            ],
            "action_html": [
                point_anchor("考达拉·永生之盾"),
                system_line("乘系统鸟：永生之盾 → 琥珀崖", "ra-flightpath"),
                point_anchor("琥珀崖"),
            ],
        },
        59: {
            "expected_title": "钢腭战场顺路清 → 博古洛克开场",
            "title": "钢腭车队 → 博古洛克前哨站",
            "summary": "在钢腭车队接并完成三条战场任务；继续到博古洛克前哨站开飞行点并完成当前交接。",
            "points": [
                {
                    "title": "钢腭车队",
                    "action": "远行者达玛·傲蹄 → 接《攻击！》\n步兵沃塔·怒拳 → 接《亡者的尊严》《让他们安息》",
                },
                {
                    "title": "钢腭车队战场",
                    "action": "↳ 做《攻击！》《亡者的尊严》《让他们安息》",
                    "note": "《亡者的尊严》：共享：主控对地上的车队卫兵或工人尸体使用任务火把。",
                },
                {
                    "title": "钢腭车队",
                    "action": "步兵沃塔·怒拳 → 交《亡者的尊严》《让他们安息》",
                },
                {
                    "title": "博古洛克前哨站",
                    "action": "开飞行点：博古洛克前哨站（五号分别）\n博古洛克大王 → 交《攻击！》\n灵语者斯纳尔芬 → 交《立即前往博古洛克前哨站！》 → 接《睿智的气元素》\n补给官塔尼斯 → 接《国王姆嘎姆嘎》",
                },
            ],
            "action_html": [
                point_anchor("钢腭车队"),
                npc_actions("远行者达玛·傲蹄", accepts=("攻击！",)),
                npc_actions("步兵沃塔·怒拳", accepts=("亡者的尊严", "让他们安息")),
                do_at("钢腭车队战场", "攻击！", "亡者的尊严", "让他们安息"),
                npc_actions("步兵沃塔·怒拳", turns=("亡者的尊严", "让他们安息")),
                point_anchor("博古洛克前哨站"),
                system_line("开飞行点：博古洛克前哨站（五号分别）", "ra-flightpoint"),
                npc_actions("博古洛克大王", turns=("攻击！",)),
                npc_actions("灵语者斯纳尔芬", turns=("立即前往博古洛克前哨站！",), accepts=("睿智的气元素",)),
                npc_actions("补给官塔尼斯", accepts=("国王姆嘎姆嘎",)),
            ],
            "note_html": notes_html(
                note_block("亡者的尊严", status_span("共享") + '主控对地上的车队卫兵或工人尸体使用任务火把。')
            ),
        },
        60: {
            "expected_title": "沸点途中做学习沟通 → 先推进冬鳞Hub链",
            "title": "因波莉安 → 火水元素 → 冬鳞避难所",
            "summary": "由因波莉安接《沸点》，完成火、水元素后进入冬鳞避难所；推进《国王姆嘎姆嘎》《学习沟通》，接到《冬鳞鱼人的贸易》。",
            "points": [
                {
                    "title": "因波莉安",
                    "action": "因波莉安 → 交《睿智的气元素》 → 接《沸点》",
                },
                {"title": "火元素西米尔", "action": "↳ 做《沸点》"},
                {"title": "水元素卓恩", "action": "↳ 做《沸点》"},
                {
                    "title": "冬鳞避难所",
                    "action": "国王姆嘎姆嘎 → 交《国王姆嘎姆嘎》 → 接《学习沟通》",
                },
                {
                    "title": "斯卡德尔尸体",
                    "action": "↳ 做《学习沟通》",
                    "note": "《学习沟通》：不共享：只需击杀一次斯卡德尔；同一具尸体可供五个角色依次使用空贝壳，每号各操作一次。",
                },
                {
                    "title": "冬鳞避难所",
                    "action": "国王姆嘎姆嘎 → 交《学习沟通》 → 接《冬鳞鱼人的贸易》",
                },
            ],
            "action_html": [
                npc_actions("因波莉安", turns=("睿智的气元素",), accepts=("沸点",)),
                do_at("火元素西米尔", "沸点"),
                do_at("水元素卓恩", "沸点"),
                point_anchor("冬鳞避难所"),
                npc_actions("国王姆嘎姆嘎", turns=("国王姆嘎姆嘎",), accepts=("学习沟通",)),
                do_at("斯卡德尔尸体", "学习沟通"),
                npc_actions("国王姆嘎姆嘎", turns=("学习沟通",), accepts=("冬鳞鱼人的贸易",)),
            ],
            "note_html": notes_html(
                note_block(
                    "学习沟通",
                    status_span("不共享") + '只需击杀一次斯卡德尔；同一具尸体可供五个角色依次使用空贝壳，每号各操作一次。',
                )
            ),
        },
        61: {
            "expected_title": "冬鳞外圈连续推进 → 接决不投降",
            "title": "冬鳞外圈 → 幽光海湾 → 冬鳞避难所",
            "summary": "完成冬鳞外圈和幽光海湾任务，连续推进避难所交接，直到接到《决不投降！》。",
            "points": [
                {
                    "title": "冬鳞鱼人外圈",
                    "action": "↳ 做《冬鳞鱼人的贸易》",
                    "note": "《冬鳞鱼人的贸易》：优先拾取地面的冬鳞蚌壳；地面不够时再杀冬鳞巡滩者、智者或战士补缺。",
                },
                {
                    "title": "冬鳞避难所",
                    "action": "呀噜咕噜 → 交《冬鳞鱼人的贸易》\n国王姆嘎姆嘎 → 接《救救蝌蚪！》\n吧咕姆咕 → 接《就是他们！》",
                },
                {
                    "title": "冬鳞鱼人外圈",
                    "action": "↳ 做《救救蝌蚪！》《就是他们！》",
                    "note": "《救救蝌蚪！》：共享：",
                },
                {
                    "title": "冬鳞避难所",
                    "action": "国王姆嘎姆嘎 → 交《救救蝌蚪！》 → 接《我被敲竹杠了！》\n吧咕姆咕 → 交《就是他们！》",
                },
                {
                    "title": "冬鳞避难所·姆姆咕咕 / 屠夫布咕布噜",
                    "action": "姆姆咕咕 → 交《我被敲竹杠了！》 → 接《咕噜咕噜呜啦哇啦！》\n屠夫布咕布噜 → 接《美味炖鲸肉》",
                },
                {
                    "title": "幽光海湾",
                    "action": "↳ 做《咕噜咕噜呜啦哇啦！》《美味炖鲸肉》",
                },
                {
                    "title": "冬鳞避难所",
                    "action": "姆姆咕咕 → 交《咕噜咕噜呜啦哇啦！》 → 接《备用的鱼人服》\n屠夫布咕布噜 → 交《美味炖鲸肉》",
                },
                {
                    "title": "冬鳞避难所·国王姆嘎姆嘎",
                    "action": "国王姆嘎姆嘎 → 交《备用的鱼人服》 → 接《决不投降！》",
                },
            ],
            "action_html": [
                do_at("冬鳞鱼人外圈", "冬鳞鱼人的贸易"),
                point_anchor("冬鳞避难所"),
                npc_actions("呀噜咕噜", turns=("冬鳞鱼人的贸易",)),
                npc_actions("国王姆嘎姆嘎", accepts=("救救蝌蚪！",)),
                npc_actions("吧咕姆咕", accepts=("就是他们！",)),
                do_at("冬鳞鱼人外圈", "救救蝌蚪！", "就是他们！"),
                point_anchor("冬鳞避难所"),
                npc_actions("国王姆嘎姆嘎", turns=("救救蝌蚪！",), accepts=("我被敲竹杠了！",)),
                npc_actions("吧咕姆咕", turns=("就是他们！",)),
                npc_actions("姆姆咕咕", turns=("我被敲竹杠了！",), accepts=("咕噜咕噜呜啦哇啦！",)),
                npc_actions("屠夫布咕布噜", accepts=("美味炖鲸肉",)),
                do_at("幽光海湾", "咕噜咕噜呜啦哇啦！", "美味炖鲸肉"),
                point_anchor("冬鳞避难所"),
                npc_actions("姆姆咕咕", turns=("咕噜咕噜呜啦哇啦！",), accepts=("备用的鱼人服",)),
                npc_actions("屠夫布咕布噜", turns=("美味炖鲸肉",)),
                npc_actions("国王姆嘎姆嘎", turns=("备用的鱼人服",), accepts=("决不投降！",)),
            ],
            "note_html": notes_html(
                note_block("冬鳞鱼人的贸易", '优先拾取地面的冬鳞蚌壳；地面不够时再杀冬鳞巡滩者、智者或战士补缺。'),
                note_block("救救蝌蚪！", status_span("共享")),
            ),
        },
        62: {
            "expected_title": "冬鳞洞穴一次通行：裂谷 + 钥匙 + 护送 + 决不投降",
            "title": "冬鳞洞穴：裂谷 → 钥匙 → 护送",
            "summary": "进入冬鳞洞穴后完成裂谷监测，推进钥匙任务并接护送；沿同一洞穴路线完成《决不投降！》，随护送出洞后回避难所交付。",
            "points": [
                {
                    "title": "冬鳞洞穴·裂谷异常",
                    "action": "↳ 做《监视裂谷：冬鳞洞穴》",
                    "note": "《监视裂谷：冬鳞洞穴》：在异常点附近主动使用奥术测量器取得读数，不会自动完成。",
                },
                {"title": "冬鳞洞穴·咕啦咕啦", "action": "咕啦咕啦 → 接《钥匙管理者呜啦咕噜》"},
                {"title": "钥匙管理者呜啦咕噜", "action": "↳ 做《钥匙管理者呜啦咕噜》"},
                {
                    "title": "冬鳞洞穴·咕啦咕啦 / 噜呱吧呱",
                    "action": "咕啦咕啦 → 交《钥匙管理者呜啦咕噜》\n噜呱吧呱 → 接《逃离冬鳞洞穴》",
                    "note": "《逃离冬鳞洞穴》：共享：",
                },
                {
                    "title": "冬鳞洞穴·克拉西姆斯",
                    "action": "↳ 做《决不投降！》《逃离冬鳞洞穴》",
                },
                {
                    "title": "冬鳞避难所",
                    "action": "国王姆嘎姆嘎 → 交《决不投降！》《逃离冬鳞洞穴》",
                },
            ],
            "action_html": [
                do_at("冬鳞洞穴·裂谷异常", "监视裂谷：冬鳞洞穴"),
                point_anchor("冬鳞洞穴"),
                npc_actions("咕啦咕啦", accepts=("钥匙管理者呜啦咕噜",)),
                do_at("钥匙管理者呜啦咕噜", "钥匙管理者呜啦咕噜"),
                npc_actions("咕啦咕啦", turns=("钥匙管理者呜啦咕噜",)),
                npc_actions("噜呱吧呱", accepts=("逃离冬鳞洞穴",)),
                do_at("冬鳞洞穴·克拉西姆斯", "决不投降！", "逃离冬鳞洞穴"),
                point_anchor("冬鳞避难所"),
                npc_actions("国王姆嘎姆嘎", turns=("决不投降！", "逃离冬鳞洞穴")),
            ],
            "note_html": notes_html(
                note_block("监视裂谷：冬鳞洞穴", '在异常点附近主动使用奥术测量器取得读数，不会自动完成。'),
                note_block("逃离冬鳞洞穴", status_span("共享")),
            ),
        },
        63: {
            "expected_title": "沸点交付 → 风暴微粒 → 空气的幻象",
            "title": "因波莉安 → 风暴微粒 → 博古洛克",
            "summary": "回因波莉安交《沸点》并完成《风暴微粒》；回博古洛克完成《空气的幻象》，接《先知格雷姆沃克之魂》《向犸格莫斯复仇》。",
            "points": [
                {
                    "title": "因波莉安",
                    "action": "因波莉安 → 交《沸点》 → 接《风暴微粒》",
                },
                {"title": "狂怒的雷暴", "action": "↳ 做《风暴微粒》"},
                {
                    "title": "因波莉安",
                    "action": "因波莉安 → 交《风暴微粒》 → 接《返回灵语者身边》",
                },
                {
                    "title": "博古洛克",
                    "action": "灵语者斯纳尔芬 → 交《返回灵语者身边》 → 接《空气的幻象》\n↳ 做《空气的幻象》\n灵语者斯纳尔芬 → 交《空气的幻象》 → 接《先知格雷姆沃克之魂》\n奥尔托什 → 接《向犸格莫斯复仇》",
                    "note": "《空气的幻象》：就在斯纳尔芬旁的图腾使用因波莉安的原始精华完成，不需要去野外找幻象目标。",
                },
            ],
            "action_html": [
                npc_actions("因波莉安", turns=("沸点",), accepts=("风暴微粒",)),
                do_at("狂怒的雷暴", "风暴微粒"),
                npc_actions("因波莉安", turns=("风暴微粒",), accepts=("返回灵语者身边",)),
                point_anchor("博古洛克"),
                npc_actions("灵语者斯纳尔芬", turns=("返回灵语者身边",), accepts=("空气的幻象",)),
                do_line("空气的幻象"),
                npc_actions("灵语者斯纳尔芬", turns=("空气的幻象",), accepts=("先知格雷姆沃克之魂",)),
                npc_actions("奥尔托什", accepts=("向犸格莫斯复仇",)),
            ],
            "note_html": notes_html(
                note_block("空气的幻象", '就在斯纳尔芬旁的图腾使用因波莉安的原始精华完成，不需要去野外找幻象目标。')
            ),
        },
        64: {
            "expected_title": "犸格莫斯洞穴闭环",
            "title": "犸格莫斯洞穴 → 博古洛克",
            "summary": "在犸格莫斯洞穴推进《卡加尼舒》《向犸格莫斯复仇》《落叶归根》，取得先知遗骸后回博古洛克交付。",
            "points": [
                {
                    "title": "犸格莫斯·先知格雷姆沃克的灵魂",
                    "action": "先知格雷姆沃克的灵魂 → 交《先知格雷姆沃克之魂》 → 接《卡加尼舒》",
                },
                {
                    "title": "犸格莫斯洞穴",
                    "action": "↳ 做《卡加尼舒》《向犸格莫斯复仇》",
                    "note": "《卡加尼舒》：拿到神像后还要对洞内先知格雷姆沃克的残骸使用，不能只击杀卡加尼舒。",
                },
                {
                    "title": "先知格雷姆沃克遗骸",
                    "action": "先知格雷姆沃克的灵魂 → 交《卡加尼舒》 → 接《落叶归根》\n↳ 做《落叶归根》",
                    "note": "《落叶归根》：接任务后立即拾取先知格雷姆沃克灵魂脚下的遗骸，再离开洞穴。",
                },
                {
                    "title": "博古洛克前哨站",
                    "action": "灵语者斯纳尔芬 → 交《落叶归根》\n奥尔托什 → 交《向犸格莫斯复仇》",
                },
            ],
            "action_html": [
                npc_actions("先知格雷姆沃克的灵魂", turns=("先知格雷姆沃克之魂",), accepts=("卡加尼舒",)),
                do_at("犸格莫斯洞穴", "卡加尼舒", "向犸格莫斯复仇"),
                point_anchor("先知格雷姆沃克遗骸"),
                npc_actions("先知格雷姆沃克的灵魂", turns=("卡加尼舒",), accepts=("落叶归根",)),
                do_line("落叶归根"),
                point_anchor("博古洛克前哨站"),
                npc_actions("灵语者斯纳尔芬", turns=("落叶归根",)),
                npc_actions("奥尔托什", turns=("向犸格莫斯复仇",)),
            ],
            "note_html": notes_html(
                note_block("卡加尼舒", '拿到神像后还要对洞内先知格雷姆沃克的残骸使用，不能只击杀卡加尼舒。'),
                note_block("落叶归根", '接任务后立即拾取先知格雷姆沃克灵魂脚下的遗骸，再离开洞穴。'),
            ),
        },
        65: {
            "expected_title": "博古洛克飞琥珀崖 → 裂谷监测交付",
            "title": "博古洛克 → 系统鸟琥珀崖",
            "summary": "从博古洛克乘系统鸟回琥珀崖，向图书馆员盖伦交《监视裂谷：冬鳞洞穴》。",
            "points": [
                {"title": "博古洛克飞行点", "action": "乘系统鸟：博古洛克 → 琥珀崖"},
                {"title": "琥珀崖", "action": "图书馆员盖伦 → 交《监视裂谷：冬鳞洞穴》"},
            ],
            "action_html": [
                system_line("乘系统鸟：博古洛克 → 琥珀崖", "ra-flightpath"),
                point_anchor("琥珀崖"),
                npc_actions("图书馆员盖伦", turns=("监视裂谷：冬鳞洞穴",)),
            ],
        },
        66: {
            "expected_title": "琥珀崖直飞牦牛村 → 横贯冰原转场",
            "title": "系统鸟琥珀崖 → 牦牛村 → 横贯冰原",
            "summary": "从琥珀崖直接乘系统鸟到牦牛村，接《横贯冰原》并护送撤离者进入龙骨荒野。",
            "points": [
                {
                    "title": "琥珀崖飞行点",
                    "action": "乘系统鸟：琥珀崖 → 牦牛村",
                },
                {
                    "title": "牦牛村",
                    "action": "陶拉努克宗母 → 接《横贯冰原》",
                },
                {
                    "title": "陶拉努克撤离队",
                    "action": "↳ 做《横贯冰原》",
                    "note": "《横贯冰原》：共享：",
                },
                {
                    "title": "龙骨荒野边界",
                    "action": "沃图克 → 交《横贯冰原》",
                    "note": "《前往莫亚基港口》：继续携带，后续到莫亚基港口自然交付。",
                },
            ],
            "action_html": [
                system_line("乘系统鸟：琥珀崖 → 牦牛村", "ra-flightpath"),
                point_anchor("牦牛村"),
                npc_actions("陶拉努克宗母", accepts=("横贯冰原",)),
                do_at("陶拉努克撤离队", "横贯冰原"),
                point_anchor("龙骨荒野边界"),
                npc_actions("沃图克", turns=("横贯冰原",)),
            ],
            "note_html": notes_html(
                note_block("横贯冰原", status_span("共享")),
                note_block("前往莫亚基港口", '继续携带，后续到莫亚基港口自然交付。'),
            ),
        },
    }

    for step_number in range(50, 67):
        apply_step(route, step_number, specs[step_number])

    route["uiStandard"] = "semantic-hud-v45"
    route["legend"] = ""
    DATA.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"route": "borean", "steps_refactored": [50, 66], "uiStandard": route["uiStandard"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
