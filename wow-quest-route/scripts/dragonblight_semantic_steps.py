from __future__ import annotations

import html
from typing import Any


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
    return '<div class="ra-line ra-do">' + branch() + verb("做") + " " + "、".join(task(x, "do") for x in tasks) + "</div>"


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


def accept_at(place: str, *tasks: str) -> str:
    return (
        '<div class="ra-line ra-do-inline">'
        + loc(place)
        + '<span class="ra-inline-sep"> </span>'
        + branch()
        + verb("接")
        + " "
        + "、".join(task(x, "accept") for x in tasks)
        + "</div>"
    )


def system_line(text: str, cls: str = "ra-transport") -> str:
    return f'<div class="ra-line"><span class="ra-system-action {cls}">{html.escape(text)}</span></div>'


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
    cls = {"共享": "ra-shared", "不共享": "ra-not-shared", "五开待实测": "ra-fivebox-check"}[status]
    return f'<span class="{cls}">{status}：</span>'


def danger(text: str) -> str:
    return f'<span class="ra-danger">{html.escape(text)}</span>'


def set_point(point: list[Any], *, title: str, action: str, note: str = "", fivebox: str | None = None) -> None:
    while len(point) <= 9:
        point.append("")
    point[2] = title
    point[3] = action
    point[5] = note
    if fivebox is not None:
        point[8] = fivebox


def apply_step(points: list[list[Any]], groups: list[dict[str, Any]], step_number: int, spec: dict[str, Any]) -> None:
    group = groups[step_number - 1]
    indices = list(range(int(group["start"]), int(group["end"]) + 1))
    if len(indices) != len(spec["points"]):
        raise RuntimeError(
            f"Dragonblight semantic step {step_number} point count drift: actual={len(indices)} expected={len(spec['points'])}"
        )
    group["title"] = spec["title"]
    group["summary"] = spec["summary"]
    group["actionHtml"] = "\n".join(spec["action_html"])
    group["noteHtml"] = spec.get("note_html", "")
    if "timingTaskNames" in spec:
        group["timingTaskNames"] = list(spec["timingTaskNames"])
    if "timingExtraMinutes" in spec:
        group["timingExtraMinutes"] = float(spec["timingExtraMinutes"])
    for point_index, point_spec in zip(indices, spec["points"], strict=True):
        set_point(points[point_index], **point_spec)


def apply_dragonblight_semantic_overrides(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    specs: dict[int, dict[str, Any]] = {
        1: {
            "title": "龙骨边界 → 西风避难营 → 东侧林地",
            "summary": "沃图克交接后进入西风避难营，接齐《深入密林》《部落的荣耀》，到东侧林地同区完成。",
            "points": [
                {"title": "龙骨边界", "action": "沃图克 → 交《横贯冰原》 → 接《牦牛人中的牛头人》"},
                {"title": "西风避难营", "action": "特使艾米萨·闪蹄 → 交《牦牛人中的牛头人》 → 接《深入密林》\n血卫士洛恩基尔 → 接《部落的荣耀》"},
                {"title": "西风避难营东侧林地", "action": "↳ 做《深入密林》《部落的荣耀》", "note": "离开前确认五号任务都完成。"},
            ],
            "action_html": [
                point_anchor("龙骨边界"), npc_actions("沃图克", turns=("横贯冰原",), accepts=("牦牛人中的牛头人",)),
                point_anchor("西风避难营"), npc_actions("特使艾米萨·闪蹄", turns=("牦牛人中的牛头人",), accepts=("深入密林",)), npc_actions("血卫士洛恩基尔", accepts=("部落的荣耀",)),
                do_at("西风避难营东侧林地", "深入密林", "部落的荣耀"),
            ],
        },
        2: {
            "title": "西风避难营 → 部落的血誓 → 阿格玛之锤",
            "summary": "回西风避难营交当前任务，完成共享的《部落的血誓》，再由艾米萨接出《阿格玛之锤》。",
            "points": [
                {"title": "西风避难营", "action": "特使艾米萨·闪蹄 → 交《深入密林》 → 接《部落的血誓》\n血卫士洛恩基尔 → 交《部落的荣耀》"},
                {"title": "牦牛难民帐篷区", "action": "↳ 做《部落的血誓》", "note": "《部落的血誓》：共享：主控逐个与牦牛难民对话即可同步全队。"},
                {"title": "西风避难营", "action": "特使艾米萨·闪蹄 → 交《部落的血誓》 → 接《阿格玛之锤》"},
            ],
            "action_html": [
                point_anchor("西风避难营"), npc_actions("特使艾米萨·闪蹄", turns=("深入密林",), accepts=("部落的血誓",)), npc_actions("血卫士洛恩基尔", turns=("部落的荣耀",)),
                do_at("牦牛难民帐篷区", "部落的血誓"),
                point_anchor("西风避难营"), npc_actions("特使艾米萨·闪蹄", turns=("部落的血誓",), accepts=("阿格玛之锤",)),
            ],
            "note_html": notes_html(note_block("部落的血誓", status_span("共享") + "主控逐个与牦牛难民对话即可同步全队。")),
        },
        3: {
            "title": "阿格玛之锤：主线 → 飞行点 / 炉石",
            "summary": "向阿格玛大王交入口任务；五号开启飞行点并绑定炉石，再由军士长祖托克接深渊与怨毒镇引导。《萨鲁法尔的信》因北风前置已删除，不进入执行稿。",
            "points": [
                {"title": "阿格玛之锤", "action": "阿格玛大王 → 交《阿格玛之锤》 → 接《胜利将近……》"},
                {"title": "阿格玛之锤·飞行点 / 旅店", "action": "开飞行点：阿格玛之锤（五号分别）\n炉石绑定：阿格玛之锤（五号分别）"},
                {"title": "阿格玛之锤", "action": "军士长祖托克 → 交《胜利将近……》 → 接《艾卓-尼鲁布的深渊》《高级执行官需要你》", "note": "《高级执行官需要你》长期携带，到怨毒镇自然交付。"},
            ],
            "action_html": [
                point_anchor("阿格玛之锤"), npc_actions("阿格玛大王", turns=("阿格玛之锤",), accepts=("胜利将近……",)),
                system_line("开飞行点：阿格玛之锤（五号分别）", "ra-flightpoint"), system_line("炉石绑定：阿格玛之锤（五号分别）", "ra-hearth"),
                npc_actions("军士长祖托克", turns=("胜利将近……",), accepts=("艾卓-尼鲁布的深渊", "高级执行官需要你")),
            ],
            "note_html": notes_html(note_block("高级执行官需要你", "长期携带，到怨毒镇自然交付。")),
        },
        4: {
            "title": "阿格玛之锤：黑血 / 通缉 / 腐烂器官 / 寻找线索",
            "summary": "在阿格玛之锤接齐纳尔苏深渊、通缉、感染野兽和眠月花园任务；吉加托尔精英支线继续留80后。",
            "points": [
                {"title": "阿格玛之锤", "action": "伯鲁斯·折铁 → 接《尤格-萨隆的黑血》"},
                {"title": "阿格玛之锤·高尔特 / 通缉板", "action": "高尔特上尉 → 接《死亡名单：高阶教徒扎古斯》\n通缉板 → 接《通缉：魔导师凯尔多努斯》《通缉：恐怖之爪》", "note": "吉加托尔→猎龙营地→萨拉斯塔整条精英支线留80后。"},
                {"title": "阿格玛之锤", "action": "索艾·鹰怒 → 接《腐烂的器官》"},
                {"title": "阿格玛之锤", "action": "夺日者影像 → 接《寻找线索》"},
            ],
            "action_html": [
                npc_actions("伯鲁斯·折铁", accepts=("尤格-萨隆的黑血",)),
                npc_actions("高尔特上尉", accepts=("死亡名单：高阶教徒扎古斯",)), npc_actions("通缉板", accepts=("通缉：魔导师凯尔多努斯", "通缉：恐怖之爪")),
                npc_actions("索艾·鹰怒", accepts=("腐烂的器官",)), npc_actions("夺日者影像", accepts=("寻找线索",)),
            ],
        },
        5: {
            "title": "纳尔苏深渊：扎古斯 → 黑血 → 基里克斯 → 感染野兽",
            "summary": "沿洞穴向下完成深渊探索、扎古斯、黑血和基里克斯链；出洞后补《腐烂的器官》。",
            "points": [
                {"title": "纳尔苏深渊·入口", "action": "↳ 做《艾卓-尼鲁布的深渊》", "note": "多层洞穴：沿通道向下，不要只追平面坐标。"},
                {"title": "高阶教徒扎古斯", "action": "↳ 做《死亡名单：高阶教徒扎古斯》", "note": "《血之魔典》此时还不能刷；必须先回阿格玛向高尔特上尉交《死亡名单：高阶教徒扎古斯》。魔典来源是后续冰雾村的阿努巴尔教徒，不是扎古斯。"},
                {"title": "纳尔苏深渊·黑血区", "action": "↳ 做《尤格-萨隆的黑血》", "note": "《尤格-萨隆的黑血》：不共享：五号分别采集，以最低进度角色完成为离开条件。"},
                {"title": "纳尔苏深渊·拆解者基里克斯", "action": "拆解者基里克斯 → 接《阿尔萨斯的死敌》\n↳ 做《阿尔萨斯的死敌》\n拆解者基里克斯 → 交《阿尔萨斯的死敌》 → 接《失落的帝国》", "note": "蛛魔领主在地下层，不要回地表找。"},
                {"title": "深渊外感染野兽带", "action": "↳ 做《腐烂的器官》", "note": "《腐烂的器官》：共享：感染野兽击杀同步；防腐内脏只需实际掉出一次，同一具尸体可供五号分别拾取。"},
            ],
            "action_html": [
                do_at("纳尔苏深渊·入口", "艾卓-尼鲁布的深渊"), do_at("高阶教徒扎古斯", "死亡名单：高阶教徒扎古斯"), do_at("纳尔苏深渊·黑血区", "尤格-萨隆的黑血"),
                point_anchor("纳尔苏深渊·拆解者基里克斯"), npc_actions("拆解者基里克斯", accepts=("阿尔萨斯的死敌",)), do_line("阿尔萨斯的死敌"), npc_actions("拆解者基里克斯", turns=("阿尔萨斯的死敌",), accepts=("失落的帝国",)),
                do_at("深渊外感染野兽带", "腐烂的器官"),
            ],
            "note_html": notes_html(
                note_block("艾卓-尼鲁布的深渊", "多层洞穴：沿通道向下，不要只追平面坐标。"),
                note_block("死亡名单：高阶教徒扎古斯", "《血之魔典》此时还不能刷；必须先回阿格玛交本任务。魔典来源是后续冰雾村的阿努巴尔教徒，不是扎古斯。"),
                note_block("尤格-萨隆的黑血", status_span("不共享") + "五号分别采集，以最低进度角色完成为离开条件。"),
                note_block("阿尔萨斯的死敌", "蛛魔领主在地下层，不要回地表找。"),
                note_block("腐烂的器官", status_span("共享") + "感染野兽击杀同步；防腐内脏只需实际掉出一次，同一具尸体可供五号分别拾取。"),
            ),
        },
        6: {
            "title": "阿格玛之锤：深渊交付 → 解锁血之魔典 → 红玉丁香",
            "summary": "回阿格玛按NPC交深渊任务；交扎古斯后血之魔典才进入可刷状态，同时把医生链推进到《红玉丁香》。",
            "points": [
                {"title": "阿格玛之锤", "action": "阿格玛大王 → 交《失落的帝国》\n军士长祖托克 → 交《艾卓-尼鲁布的深渊》 → 接《部落的力量》\n伯鲁斯·折铁 → 交《尤格-萨隆的黑血》 → 接《天灾的装备》\n高尔特上尉 → 交《死亡名单：高阶教徒扎古斯》", "note": "《血之魔典》从这里开始可在冰雾村阿努巴尔教徒身上获取。"},
                {"title": "阿格玛之锤", "action": "索艾·鹰怒 → 交《腐烂的器官》 → 接《好医生……》"},
                {"title": "阿格玛之锤", "action": "辛塔尔·玛菲奥斯博士 → 交《好医生……》 → 接《红玉丁香》", "note": "《红玉丁香》先携带，后面经过目标区再做。"},
            ],
            "action_html": [
                point_anchor("阿格玛之锤"), npc_actions("阿格玛大王", turns=("失落的帝国",)), npc_actions("军士长祖托克", turns=("艾卓-尼鲁布的深渊",), accepts=("部落的力量",)), npc_actions("伯鲁斯·折铁", turns=("尤格-萨隆的黑血",), accepts=("天灾的装备",)), npc_actions("高尔特上尉", turns=("死亡名单：高阶教徒扎古斯",)),
                npc_actions("索艾·鹰怒", turns=("腐烂的器官",), accepts=("好医生……",)), npc_actions("辛塔尔·玛菲奥斯博士", turns=("好医生……",), accepts=("红玉丁香",)),
            ],
            "note_html": notes_html(note_block("血之魔典", "交《死亡名单：高阶教徒扎古斯》后才进入冰雾村阿努巴尔教徒掉落池。"), note_block("红玉丁香", "先携带，后面经过目标区再做。")),
        },
        7: {
            "title": "冰雾祖母 → 班索克 → 三钥匙 / 魔典 / 军旗",
            "summary": "从冰雾祖母接引导进入冰雾村；完成三把钥匙、军备、血之魔典和《部落的力量》。",
            "points": [
                {"title": "阿格玛之锤·西侧", "action": "冰雾祖母 → 接《冰雾的力量》"},
                {"title": "冰雾村", "action": "班索克·冰雾 → 交《冰雾的力量》 → 接《阿努巴尔的束缚》"},
                {"title": "冰雾村·三钥匙 / 阿努巴尔教徒", "action": "↳ 做《阿努巴尔的束缚》《天灾的装备》\n↳ 接《血之魔典》", "note": "《阿努巴尔的束缚》：三名钥匙目标各杀一次；每具尸体可供五号分别拾取钥匙。西诺克在南侧高台连排大房子内约(25.7,44.2)。\n《血之魔典》：来源怪为冰雾村阿努巴尔教徒；击杀后拾取掉落的任务起始物并右键接任务。必须先交《死亡名单：高阶教徒扎古斯》后才会进入掉落池；五号都接到任务后再离开。"},
                {"title": "冰雾村·战歌军旗", "action": "↳ 做《部落的力量》", "note": "《部落的力量》：不共享：五号各自插1面旗；可在同一地点连续插旗并共同守完事件。"},
            ],
            "action_html": [
                npc_actions("冰雾祖母", accepts=("冰雾的力量",)), point_anchor("冰雾村"), npc_actions("班索克·冰雾", turns=("冰雾的力量",), accepts=("阿努巴尔的束缚",)),
                do_at("冰雾村·三钥匙 / 阿努巴尔教徒", "阿努巴尔的束缚", "天灾的装备"), accept_at("冰雾村·阿努巴尔教徒", "血之魔典"),
                do_at("冰雾村·战歌军旗", "部落的力量"),
            ],
            "note_html": notes_html(
                note_block("阿努巴尔的束缚", "三名钥匙目标各杀一次；每具尸体可供五号分别拾取钥匙。西诺克在南侧高台连排大房子内约(25.7,44.2)。"),
                note_block("血之魔典", "来源怪为冰雾村阿努巴尔教徒；击杀后拾取掉落的任务起始物并右键接任务。必须先交《死亡名单：高阶教徒扎古斯》后才会进入掉落池；五号都接到任务后再离开。"),
                note_block("部落的力量", status_span("不共享") + "五号各自插1面旗；可在同一地点连续插旗并共同守完事件。"),
            ),
        },
        8: {
            "title": "班索克 → 大酋长归来",
            "summary": "向班索克交三钥匙并接《大酋长归来》，救出大酋长并完成虫王事件。",
            "points": [
                {"title": "冰雾村", "action": "班索克·冰雾 → 交《阿努巴尔的束缚》 → 接《大酋长归来》"},
                {"title": "冰雾牢笼 / 虫王", "action": "↳ 做《大酋长归来》", "note": "《大酋长归来》：共享：救援与虫王击杀只需主控完成；虫王尸体上的外壳碎片由五号分别拾取。"},
            ],
            "action_html": [point_anchor("冰雾村"), npc_actions("班索克·冰雾", turns=("阿努巴尔的束缚",), accepts=("大酋长归来",)), do_at("冰雾牢笼 / 虫王", "大酋长归来")],
            "note_html": notes_html(note_block("大酋长归来", status_span("共享") + "救援与虫王击杀只需主控完成；虫王尸体上的外壳碎片由五号分别拾取。")),
        },
        9: {
            "title": "炉石阿格玛 → 三宝石 → 洛纳乌克 → 荒芜兽",
            "summary": "炉石回阿格玛完成冰雾任务交付，接三宝石；完成共享洛纳乌克事件后向阿格玛大王交付，再推进任务双足飞龙。",
            "points": [
                {"title": "阿格玛之锤", "action": "使用炉石：阿格玛之锤\n阿格玛大王 → 交《大酋长归来》 → 接《洛纳乌克万岁！》\n军士长祖托克 → 交《部落的力量》 → 接《空中打击！》\n伯鲁斯·折铁 → 交《天灾的装备》\n高尔特上尉 → 交《血之魔典》 → 接《库尔迪拉和亡者之语》"},
                {"title": "阿格玛之锤", "action": "库尔迪拉·织亡者 → 交《库尔迪拉和亡者之语》 → 接《邪能之约》《邪恶之约》《冰霜之约》", "note": "三颗宝石先携带，后续经过各自目标区再做。"},
                {"title": "洛纳乌克", "action": "↳ 做《洛纳乌克万岁！》", "note": "《洛纳乌克万岁！》：共享：主控触发并看完整个事件脚本即可同步全队。"},
                {"title": "阿格玛之锤", "action": "阿格玛大王 → 交《洛纳乌克万岁！》\n瓦诺克·风怒 → 交《空中打击！》 → 接《该死的荒芜兽！》"},
                {"title": "冰雾村·库卡隆双足飞龙", "action": "↳ 做《该死的荒芜兽！》", "fivebox": "请确认《该死的荒芜兽！》：主控使用任务双足飞龙击杀后，其他四个角色的25只目标是否同步计数，还是五号都必须分别跑载具？"},
                {"title": "阿格玛之锤", "action": "瓦诺克·风怒 → 交《该死的荒芜兽！》"},
            ],
            "action_html": [
                system_line("使用炉石：阿格玛之锤", "ra-hearth"), npc_actions("阿格玛大王", turns=("大酋长归来",), accepts=("洛纳乌克万岁！",)), npc_actions("军士长祖托克", turns=("部落的力量",), accepts=("空中打击！",)), npc_actions("伯鲁斯·折铁", turns=("天灾的装备",)), npc_actions("高尔特上尉", turns=("血之魔典",), accepts=("库尔迪拉和亡者之语",)),
                npc_actions("库尔迪拉·织亡者", turns=("库尔迪拉和亡者之语",), accepts=("邪能之约", "邪恶之约", "冰霜之约")),
                do_at("洛纳乌克", "洛纳乌克万岁！"), point_anchor("阿格玛之锤"), npc_actions("阿格玛大王", turns=("洛纳乌克万岁！",)), npc_actions("瓦诺克·风怒", turns=("空中打击！",), accepts=("该死的荒芜兽！",)),
                do_at("冰雾村·库卡隆双足飞龙", "该死的荒芜兽！"), point_anchor("阿格玛之锤"), npc_actions("瓦诺克·风怒", turns=("该死的荒芜兽！",)),
            ],
            "note_html": notes_html(note_block("洛纳乌克万岁！", status_span("共享") + "主控触发并看完整个事件脚本即可同步全队。"), note_block("该死的荒芜兽！", status_span("五开待实测") + "确认主控载具击杀是否同步其他四号；若不共享则五号分别跑载具。")),
        },
        10: {
            "title": "恐怖之爪 → 猎龙营地 → 诺兹拉斯挖掘场",
            "summary": "击杀恐怖之爪，猎龙营地接《害虫控制》，再由诺兹拉斯补给员接引导进入哨站并完成挖掘场第一组。",
            "points": [
                {"title": "恐怖之爪", "action": "↳ 做《通缉：恐怖之爪》", "note": "目标在雪坡/高台上空约(46.3,43.0)，不要在坡底找。冰拳留到《峡谷追击》。"},
                {"title": "猎龙营地", "action": "肯图卡尼斯 → 接《害虫控制》"},
                {"title": "诺兹拉斯西南坡", "action": "诺兹拉斯补给员 → 接《退回发件人》"},
                {"title": "诺兹拉斯哨站", "action": "辛克 → 交《退回发件人》 → 接《囤积矿石》\n希弗里克斯 → 接《刨冰》\n纳尔弗 → 接《诺兹拉斯的防御》", "note": "纳尔弗约(54.5,23.6)，在哨站西侧；Questie缺少其NPC坐标。"},
                {"title": "迦拉克隆挖掘场", "action": "↳ 做《诺兹拉斯的防御》《囤积矿石》", "note": "悬崖落差大，五开不要贴边抄近路或直接往下跳。"},
                {"title": "诺兹拉斯哨站", "action": "纳尔弗 → 交《诺兹拉斯的防御》\n辛克 → 交《囤积矿石》"},
            ],
            "action_html": [
                do_at("恐怖之爪", "通缉：恐怖之爪"), point_anchor("猎龙营地"), npc_actions("肯图卡尼斯", accepts=("害虫控制",)), npc_actions("诺兹拉斯补给员", accepts=("退回发件人",)),
                point_anchor("诺兹拉斯哨站"), npc_actions("辛克", turns=("退回发件人",), accepts=("囤积矿石",)), npc_actions("希弗里克斯", accepts=("刨冰",)), npc_actions("纳尔弗", accepts=("诺兹拉斯的防御",)),
                do_at("迦拉克隆挖掘场", "诺兹拉斯的防御", "囤积矿石"), point_anchor("诺兹拉斯哨站"), npc_actions("纳尔弗", turns=("诺兹拉斯的防御",)), npc_actions("辛克", turns=("囤积矿石",)),
            ],
        },
        11: {
            "title": "刨冰 → 柔软的包装 → 不会融化的东西",
            "summary": "完成《刨冰》后由希弗里克斯接《柔软的包装》，刷满薄兽皮再回哨站接《不会融化的东西》和《难以下咽》。",
            "points": [
                {"title": "水晶冰雪元素", "action": "↳ 做《刨冰》", "note": "不要从右上悬崖直接跳去水晶裂痕，按正常坡路返回。"},
                {"title": "诺兹拉斯哨站", "action": "希弗里克斯 → 交《刨冰》 → 接《柔软的包装》"},
                {"title": "掘洞冰虫 / 秃鹫带", "action": "↳ 做《柔软的包装》", "note": "以最低进度角色12/12为离开条件。"},
                {"title": "诺兹拉斯哨站", "action": "希弗里克斯 → 交《柔软的包装》 → 接《不会融化的东西》\n辛克 → 接《难以下咽》"},
            ],
            "action_html": [do_at("水晶冰雪元素", "刨冰"), point_anchor("诺兹拉斯哨站"), npc_actions("希弗里克斯", turns=("刨冰",), accepts=("柔软的包装",)), do_at("掘洞冰虫 / 秃鹫带", "柔软的包装"), point_anchor("诺兹拉斯哨站"), npc_actions("希弗里克斯", turns=("柔软的包装",), accepts=("不会融化的东西",)), npc_actions("辛克", accepts=("难以下咽",))],
        },
        12: {
            "title": "破碎骨片 → 巨大冰虫 → 诺兹拉斯",
            "summary": "完成《不会融化的东西》《难以下咽》，回诺兹拉斯分别向希弗里克斯、辛克和纳尔弗交接鹰身人/伐木机任务。",
            "points": [
                {"title": "巨龙骸骨堆", "action": "↳ 做《不会融化的东西》", "note": "《不会融化的东西》：破碎骨片为地面固定拾取物。", "fivebox": "请确认《不会融化的东西》：主控拾取一块破碎骨片后，其他四个角色是否同步计数，还是五号需要分别拾取？"},
                {"title": "巨大的冰虫", "action": "↳ 做《难以下咽》", "note": "把冰虫打到低血量，等张嘴时扔炸药；爆炸后拾取烧焦冰虫肉。不要直接打死。"},
                {"title": "诺兹拉斯哨站", "action": "希弗里克斯 → 交《不会融化的东西》\n辛克 → 交《难以下咽》 → 接《抢木材》\n纳尔弗 → 接《该死的鹰身人！》"},
            ],
            "action_html": [do_at("巨龙骸骨堆", "不会融化的东西"), do_at("巨大的冰虫", "难以下咽"), point_anchor("诺兹拉斯哨站"), npc_actions("希弗里克斯", turns=("不会融化的东西",)), npc_actions("辛克", turns=("难以下咽",), accepts=("抢木材",)), npc_actions("纳尔弗", accepts=("该死的鹰身人！",))],
            "note_html": notes_html(note_block("不会融化的东西", status_span("五开待实测") + "破碎骨片为地面固定拾取物；确认拾取进度是否共享。"), note_block("难以下咽", "把冰虫打到低血量，等张嘴时扔炸药；爆炸后拾取烧焦冰虫肉。")),
        },
        13: {
            "title": "鹰身人 / 伐木机 → 冷风女王 → 水晶裂痕",
            "summary": "同区推进共享鹰身人击杀与五号个人伐木机木材，补冷风女王后回诺兹拉斯交接，再到佐特接《采集样本》。",
            "points": [
                {"title": "鹰身人巢穴 / 伐木机", "action": "↳ 做《该死的鹰身人！》《抢木材》", "note": "《该死的鹰身人！》：共享：主控清鹰身人即可同步。\n《抢木材》：不共享：五号分别召伐木机并各自收集50捆木材，以最低角色50/50为离开条件。"},
                {"title": "冷风女王", "action": "↳ 做《该死的鹰身人！》", "note": "不要只刷普通鹰身人漏掉命名目标冷风女王。"},
                {"title": "诺兹拉斯哨站", "action": "辛克 → 交《抢木材》\n纳尔弗 → 交《该死的鹰身人！》 → 接《艰难的沟通》"},
                {"title": "水晶裂痕", "action": "佐特 → 交《艰难的沟通》 → 接《采集样本》"},
            ],
            "action_html": [do_at("鹰身人巢穴 / 伐木机", "该死的鹰身人！", "抢木材"), do_at("冷风女王", "该死的鹰身人！"), point_anchor("诺兹拉斯哨站"), npc_actions("辛克", turns=("抢木材",)), npc_actions("纳尔弗", turns=("该死的鹰身人！",), accepts=("艰难的沟通",)), point_anchor("水晶裂痕"), npc_actions("佐特", turns=("艰难的沟通",), accepts=("采集样本",))],
            "note_html": notes_html(note_block("该死的鹰身人！", status_span("共享") + "主控清普通鹰身人即可同步；冷风女王仍要单独补掉。"), note_block("抢木材", status_span("不共享") + "五号分别召伐木机并各自收集50捆木材，以最低角色50/50为离开条件。")),
        },
        14: {
            "title": "水晶裂痕：采集样本 → 恶心的生意 → 冰虫之母",
            "summary": "五号分别取样并完成腐蚀性唾液操作；佐特与科查尔交接后接到《冰虫之母》《抓虫子》。",
            "points": [
                {"title": "水晶裂痕·冰巨人尸体", "action": "↳ 做《采集样本》", "note": "《采集样本》：不共享：五号分别点击固定冰巨人尸体取样，不是杀活冰巨人。"},
                {"title": "水晶裂痕", "action": "佐特 → 交《采集样本》 → 接《恶心的生意》\n坚不可摧的科查尔 → 接《践踏大地》"},
                {"title": "水晶裂痕·冰虫酸液区", "action": "↳ 做《恶心的生意》", "note": "《恶心的生意》：不共享：每号自己吃到腐蚀性唾液，再对自己使用佐特的刮刀做到2/2。"},
                {"title": "水晶裂痕", "action": "佐特 → 交《恶心的生意》 → 接《主动示好》"},
                {"title": "水晶裂痕", "action": "坚不可摧的科查尔 → 交《主动示好》 → 接《冰虫之母》\n佐特 → 接《抓虫子》"},
            ],
            "action_html": [do_at("水晶裂痕·冰巨人尸体", "采集样本"), point_anchor("水晶裂痕"), npc_actions("佐特", turns=("采集样本",), accepts=("恶心的生意",)), npc_actions("坚不可摧的科查尔", accepts=("践踏大地",)), do_at("水晶裂痕·冰虫酸液区", "恶心的生意"), point_anchor("水晶裂痕"), npc_actions("佐特", turns=("恶心的生意",), accepts=("主动示好",)), npc_actions("坚不可摧的科查尔", turns=("主动示好",), accepts=("冰虫之母",)), npc_actions("佐特", accepts=("抓虫子",))],
            "note_html": notes_html(note_block("采集样本", status_span("不共享") + "五号分别点击固定冰巨人尸体取样，不是杀活冰巨人。"), note_block("恶心的生意", status_span("不共享") + "每号自己吃到腐蚀性唾液，再对自己使用佐特的刮刀做到2/2。")),
        },
        15: {
            "title": "冰心洞穴 → 拉特尔博尔 → 水晶裂痕 → 炉石阿格玛",
            "summary": "在冰心洞穴完成《抓虫子》《践踏大地》，击杀拉特尔博尔后回水晶裂痕交付，随后炉石回阿格玛。",
            "points": [
                {"title": "冰心洞穴", "action": "↳ 做《抓虫子》《践踏大地》", "note": "《抓虫子》：不共享：五号分别对幼虫使用坚固的箱子，并分别拾取自己的落地箱子。洞穴入口约(56,12)。"},
                {"title": "钻雪虫·拉特尔博尔", "action": "↳ 做《冰虫之母》", "note": "真正拉Boss前再用佐特防护药剂。药剂一次性，死亡后消失且不能重领；不要提前使用。"},
                {"title": "水晶裂痕", "action": "佐特 → 交《抓虫子》\n坚不可摧的科查尔 → 交《践踏大地》《冰虫之母》"},
                {"title": "阿格玛之锤", "action": "使用炉石：阿格玛之锤"},
            ],
            "action_html": [do_at("冰心洞穴", "抓虫子", "践踏大地"), do_at("钻雪虫·拉特尔博尔", "冰虫之母"), point_anchor("水晶裂痕"), npc_actions("佐特", turns=("抓虫子",)), npc_actions("坚不可摧的科查尔", turns=("践踏大地", "冰虫之母")), system_line("使用炉石：阿格玛之锤", "ra-hearth")],
            "note_html": notes_html(note_block("抓虫子", status_span("不共享") + "五号分别对幼虫使用坚固的箱子，并分别拾取自己的落地箱子。洞穴入口约(56,12)。"), note_block("冰虫之母", danger("真正拉Boss前") + "再用佐特防护药剂。药剂一次性，死亡后消失且不能重领；不要提前使用。")),
        },
    }

    timing_task_names = {
        1: ["深入密林", "部落的荣耀"],
        2: ["部落的血誓"],
        3: [],
        4: [],
        5: ["艾卓-尼鲁布的深渊", "死亡名单：高阶教徒扎古斯", "尤格-萨隆的黑血", "阿尔萨斯的死敌", "腐烂的器官"],
        6: [],
        7: ["阿努巴尔的束缚", "天灾的装备", "血之魔典", "部落的力量"],
        8: ["大酋长归来"],
        9: ["洛纳乌克万岁！", "该死的荒芜兽！"],
        10: ["通缉：恐怖之爪", "诺兹拉斯的防御", "囤积矿石"],
        11: ["刨冰", "柔软的包装"],
        12: ["不会融化的东西", "难以下咽"],
        13: ["该死的鹰身人！", "抢木材"],
        14: ["采集样本", "恶心的生意"],
        15: ["抓虫子", "践踏大地", "冰虫之母"],
    }
    for step_number, names in timing_task_names.items():
        specs[step_number]["timingTaskNames"] = names

    for step_number, spec in specs.items():
        apply_step(points, groups, step_number, spec)
