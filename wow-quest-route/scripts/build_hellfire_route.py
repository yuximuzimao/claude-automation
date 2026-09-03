from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# The renderer is generic despite its historical module name: it converts the
# route's action truth into semantic-hud-v45 HTML without maintaining a second
# task order.
from howling_semantic_steps import apply_howling_semantic_hud

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data/routes/world-candidate/3483-hellfire-peninsula/route.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
SCOPE_OUT = ROOT / "data/route-atlas/hellfire-speed-route-scope.json"
GROUPS_OUT = ROOT / "data/route-atlas/hellfire-player-step-groups.json"
REPORT = ROOT / "docs/analysis/2026-08-27-hellfire-speed-route.md"

CANDIDATE_DATA = json.loads(CANDIDATE.read_text(encoding="utf-8"))
TASKS = {int(row["quest_id"]): row for row in CANDIDATE_DATA["quest_catalog"]}
TASKS[9912] = {
    "quest_id": 9912,
    "name": "塞纳里奥远征队",
    "required_level": 61,
    "quest_level": 62,
}
# 9400 is present in the current server Journey/chain data but absent from the
# older world-candidate catalog. Keep the live-proven card local to this route
# builder instead of rebuilding the old candidate universe.
TASKS[9400] = {
    "quest_id": 9400,
    "name": "刺客",
    "required_level": 58,
    "quest_level": 62,
}

# 58—64 reuse route. Journey is empirical evidence, not route order.
# This pool deliberately omits high-interaction/long-tail collection packages.
MAIN_IDS = {
    9407, 10120, 10289, 10291,
    10121, 10123, 10124, 10208, 10129, 10162, 10388,
    10086, 10087, 10450, 10449, 10242,
    10220, 10809, 10792, 10813, 10834,
    10236, 10238, 10629, 10630,
    10390, 10391, 10392, 10136, 10389,
    9400, 9401, 9405, 9410, 9406,
    9499, 9340, 9391, 9466, 9366, 9370, 9374, 10286, 10287, 9472,
    9387, 9376, 10442, 10103,
    10367, 10368, 10369,
    10132, 10134, 10349, 10351, 10159, 9372, 10255, 9912,
}

# Natural-drop/low marginal-cost branches. Never farm merely to open them.
CONDITIONAL_IDS = {
    10229, 10230, 10250, 10258,  # Mysterious Tome chain, only if the tome drops during 10220.
    10393,  # Burning Legion Missive from Razorsaw while doing 10390.
    9373,   # Eroded Leather Case from tunnellers/crust bursters; do not farm.
}

# Kept in scope documentation for gear-pressure recovery, but absent from the
# default speed route because the five-box interaction wallclock is too large.
OPTIONAL_EQUIPMENT_PACKS = {
    "crash_debris": {
        "ids": [10161, 9351],
        "reason": "30份飞艇碎片需要五号大量固定拾取；虽有直接装备并解锁后续装备，但首跑同块墙钟明显偏高。",
    },
    "spineleaf_crash": {
        "ids": [9345, 10213],
        "reason": "12片地狱火刺叶本身无装备；只有自然沿路已够时才值得顺手，不作为速度版必做。",
    },
}

SKIP_REASONS = {
    9349: "12枚掠食者卵；无关键装备，额外个人拾取。",
    9361: "掉肉+净化双随机，五开长尾高且无关键装备。",
    9356: "12只秃鹫翅膀随机掉落，长尾高。",
    9381: "8片尾羽随机掉落，无关键装备后续。",
    9396: "4个哈尔什卷轴，低收益个人收集。",
    9397: "鸟巢会随机出现公/母鸟，可能反复开巢，不适合稳定五开速度路线。",
    9418: "独立支线，不为它额外绕路。",
    10278: "迁跃裂隙链会进入40碎片阶段，整包墙钟过高。",
    10294: "需要40块虚空山脉灵魂碎片，强跳。",
    10295: "虽为链尾装备任务，但不值得为40碎片前置打开整包。",
    10538: "12份血样且每号需逐次锅交互；从此截断药剂师后半长链。",
    10835: "依赖被截断的10538后半长链。",
    10864: "依赖被截断的药剂师后半长链。",
    10838: "依赖被截断的药剂师后半长链，且包含脚本等待。",
    10875: "依赖被截断的药剂师后半长链。",
    10876: "链尾有装备，但不足以抵消前置整包五开墙钟。",
    9438: "跨大陆通知萨尔；主速度路线在地狱火结束后直接进赞加。",
    9441: "依赖跨大陆通知萨尔，不进入地狱火→赞加连续路线。",
    9442: "跨大陆后续；首组最终放弃。",
    9447: "依赖9442，不进入主路线。",
    9375: "当前服务器首组可直接接9376，无需该breadcrumb。",
    10403: "当前服务器首组可直接接10367，无需该breadcrumb。",
}

ENTRY_TURN_ONLY = {9407}
CROSSMAP_HANDOFF = {10103}


def n(qid: int) -> str:
    return f"《{TASKS[qid]['name']}》"


points: list[list[Any]] = []
covered: set[int] = set()
groups: list[dict[str, Any]] = []


def P(
    x: float,
    y: float,
    title: str,
    action: str,
    phase: str,
    note: str = "",
    movement: str = "ride",
    qids: tuple[int, ...] = (),
    optional: bool = False,
    fivebox: str = "",
) -> None:
    points.append([x, y, title, action, phase, note, movement, optional, fivebox])
    covered.update(qids)


def G(title: str, summary: str, fn) -> None:
    start = len(points)
    fn()
    groups.append({"start": start, "end": len(points) - 1, "title": title, "summary": summary})


def g1_portal_east_front() -> None:
    P(87.35, 49.78, "黑暗之门", f"沃雷恩中将 → 交{n(9407)} → 接{n(10120)}", "entry", qids=(9407, 10120))
    P(87.35, 48.14, "黑暗之门·部落营地", f"维拉加·乱羽 → 交{n(10120)} → 接{n(10289)}\n任务传送：黑暗之门 → 萨尔玛", "entry", "《萨尔玛之旅》使用任务提供的双足飞龙进入萨尔玛。", "script", (10120, 10289))
    P(55.88, 36.65, "萨尔玛", f"克拉库克将军 → 交{n(10289)} → 接{n(10291)}\n纳兹格雷尔 → 交{n(10291)} → 接{n(10121)}\n玛提克·托塞多雷 → 接{n(9499)}\n泽格·纳克布斯 → 接{n(10086)}\n乌托克·断斧 → 接{n(10450)}\n开飞行点：萨尔玛\n绑定炉石：萨尔玛", "thrallmar", "炉石先绑定萨尔玛；后面断背南线结束后直接炉石回中部。", "ride", (10289, 10291, 10121, 9499, 10086, 10450))
    P(58.14, 41.27, "萨尔玛东侧补给车队", f"斯古尔·碎颅者中士 → 交{n(10121)} → 接{n(10123)}", "east", qids=(10121, 10123))
    P(66.25, 47.26, "魔火峡谷", f"↳ 做{n(10123)}", "east", qids=(10123,))
    P(58.14, 41.27, "补给车队", f"斯古尔·碎颅者中士 → 交{n(10123)} → 接{n(10124)}", "east", qids=(10123, 10124))
    P(65.89, 43.59, "机甲残骸", f"前线指挥官托尔克 → 交{n(10124)} → 接{n(10208)}", "wreck", qids=(10124, 10208))
    P(72.41, 42.11, "希鲁斯 / 科卢尔传送门", f"↳ 做{n(10208)}", "wreck", "击杀传送门附近燃烧军团取得恶魔符文石，再在两座传送门使用任务炸药。", "ride", (10208,), fivebox="确认恶魔符文石是否个人拾取，以及一号炸门后其余四号是否同步获得两座传送门进度。")
    P(65.89, 43.59, "机甲残骸", f"前线指挥官托尔克 → 交{n(10208)} → 接{n(10129)}", "wreck", qids=(10208, 10129))
    P(77.87, 49.55, "军团传送器", f"空军指挥官布拉克 → 乘任务飞行\n↳ 做{n(10129)}", "wreck", "轰炸穆尔凯斯和沙德拉兹两座传送器；这是任务脚本飞行。", "script", (10129,), fivebox="确认是否五号都要分别乘任务飞行完成轰炸。")
    P(65.89, 43.59, "机甲残骸", f"前线指挥官托尔克 → 交{n(10129)} → 接{n(10162)}", "wreck", qids=(10129, 10162))


def g2_thrallmar_gear_to_spinebreaker() -> None:
    P(57.4, 49.3, "噬骨者营地 / 回收物资区", f"↳ 做{n(10086)}、{n(10450)}", "gear", "两项同片完成；《我为部落工作！》需要8份木材和8份金属。", "ride", (10086, 10450), fivebox="确认回收木材/金属是否必须五号分别拾取，以及《噬骨之血》同一尸体能否连续供五号拾取。")
    P(55.13, 36.21, "萨尔玛", f"泽格·纳克布斯 → 交{n(10086)} → 接{n(10087)}\n乌托克·断斧 → 交{n(10450)} → 接{n(10449)}", "thrallmar", qids=(10086, 10087, 10450, 10449))
    P(54.1, 52.5, "联盟火炮阵地", f"↳ 做{n(10087)}", "gear", "烧毁东西两门联盟火炮。", "ride", (10087,))
    P(65.89, 43.59, "机甲残骸", f"药剂师塞兰娜 → 交{n(10449)} → 接{n(10242)}\n任务传送：机甲残骸 → 断背岗哨", "wreck", qids=(10449, 10242))
    P(61.7, 81.7, "断背岗哨", f"药剂师阿尔布雷克 → 交{n(10242)}\n开飞行点：断背岗哨\n莫迪巴大使 → 接{n(10220)}\n通缉布告 → 接{n(10809)}", "spinebreaker", "", "script", (10242, 10220, 10809))


def g3_spinebreaker_armory_zethgor() -> None:
    P(54.8, 80.5, "远征军械库", f"↳ 做{n(10220)}", "south", "击杀12步兵阴魂、8骑士阴魂、6巫师阴魂。若期间自然掉落神秘典籍，可接《解读书卷》；26只任务怪杀完仍未掉就不补刷。", "ride", (10220,), fivebox="确认同一次击杀是否稳定同步三类阴魂数量。")
    P(67.8, 73.0, "塞斯高·第一趟", f"↳ 做{n(10809)}", "zethgor", "击杀座狼主宰卡鲁什。", "ride", (10809,))
    P(61.7, 81.7, "断背岗哨", f"莫迪巴大使 → 交{n(10220)}\n达克霍尔上尉 → 交{n(10809)} → 接{n(10792)}、{n(10813)}", "spinebreaker", "若自然获得《解读书卷》，在史学家奥尔森处顺手交并接《战斗的号角》；否则跳过整条书卷支线。", "ride", (10220, 10809, 10792, 10813))
    P(69.0, 74.9, "塞斯高·第二趟", f"↳ 做{n(10792)}、{n(10813)}", "zethgor", "烧建筑与捕获格里洛克之眼同一次进区。", "ride", (10792, 10813), fivebox="分别确认建筑纵火与捕获格里洛克之眼是否共享；未知前不要按任务类型推断。")
    P(61.7, 81.7, "断背岗哨", f"达克霍尔上尉 → 交{n(10792)}\n塞萨克 → 交{n(10813)} → 接{n(10834)}", "spinebreaker", qids=(10792, 10813, 10834))
    P(66.66, 71.5, "塞斯高·第三趟", f"↳ 做{n(10834)}", "zethgor", qids=(10834,))
    P(61.7, 81.7, "断背岗哨", f"塞萨克 → 交{n(10834)}\n使用炉石：萨尔玛", "spinebreaker", qids=(10834,))


def g4_thrallmar_north_and_forge() -> None:
    P(55.13, 36.2, "萨尔玛", f"泽格·纳克布斯 → 交{n(10087)}", "thrallmar", qids=(10087,))
    P(72.76, 17.47, "地狱岩床", f"↳ 做{n(10162)}", "north", "20甘尔葛苦工、5莫尔葛监工、5门邪能火炮。", "ride", (10162,))
    P(65.89, 43.59, "机甲残骸", f"前线指挥官托尔克 → 交{n(10162)} → 接{n(10388)}", "wreck", qids=(10162, 10388))
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(10388)} → 接{n(9400)}、{n(10390)}", "thrallmar", qids=(10388, 9400, 10390))
    P(51.37, 30.52, "萨尔玛西北矿洞", f"工头拉泽克拉兹 → 接{n(10236)}", "mine", qids=(10236,))
    P(47.9, 41.3, "矿洞外回收区", f"↳ 做{n(10236)}", "mine", "拾取6个固定伐木机备用零件。", "ride", (10236,), fivebox="确认备用零件是否必须五号分别拾取。")
    P(51.37, 30.52, "矿洞", f"工头拉泽克拉兹 → 交{n(10236)} → 接{n(10238)}", "mine", qids=(10236, 10238))
    P(46.4, 45.2, "邪兽人营地", f"↳ 做{n(10238)}", "mine", "释放曼尼、莫恩、雅克三名地精。", "ride", (10238,), fivebox="确认一号开三只牢笼时其余四号是否同步完成营救。")
    P(51.37, 30.52, "矿洞", f"工头拉泽克拉兹 → 交{n(10238)} → 接{n(10629)}\n↳ 做{n(10629)}\n工头拉泽克拉兹 → 交{n(10629)} → 接{n(10630)}", "mine", "《肮脏的工作》用哨子召地狱犬，击杀野猪喂食后从地狱犬残渣取得钥匙。", "ride", (10238, 10629, 10630), fivebox="确认恶魔警卫犬喂食/残渣取得是否需要五号分别执行。")
    P(54.39, 31.57, "萨尔玛地下", f"↳ 做{n(10630)}\n工头拉泽克拉兹 → 交{n(10630)}", "mine", qids=(10630,))
    P(61.8, 31.65, "铸魔营地：暴虐", f"↳ 做{n(10390)}", "forge", "击杀10甘尔葛仆从并击杀剃刀电锯。若剃刀电锯自然掉落燃烧军团信件，则接《邪恶的计划》并顺手回萨尔玛交；不额外等刷新。", "ride", (10390,), fivebox="确认剃刀电锯的任务起始信件是否同一尸体能让五号分别拾取。")
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(10390)} → 接{n(10391)}", "thrallmar", qids=(10390, 10391))
    P(59.33, 32.53, "铸魔营地：狂乱", f"↳ 做{n(10391)}", "forge", qids=(10391,))
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(10391)} → 接{n(10392)}", "thrallmar", qids=(10391, 10392))
    P(53.09, 26.47, "深渊之门", f"↳ 做{n(10392)}", "forge", "击杀战争使者阿利萨玛尔取得钥匙，再摧毁怨恨符文。", "ride", (10392,), fivebox="确认钥匙/怨恨符文操作是否需要五号分别执行。")
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(10392)} → 接{n(10136)}\n魔导师文森特·血鹰 → 接{n(10389)}", "thrallmar", "", "ride", (10392, 10136, 10389))


def g5_assassin_maghar_package() -> None:
    P(33.61, 43.52, "邪兽人尸体", f"邪兽人尸体 → 交{n(9400)} → 接{n(9401)}\n使用炉石：萨尔玛", "maghar", "这是链条要求的第一次到尸体；交《刺客》后从尸体取得重型石斧。", "hearth", (9400, 9401))
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(9401)} → 接{n(9405)}\n先知雷古库特 → 交{n(9405)} → 接{n(9410)}", "maghar", qids=(9401, 9405, 9410))
    P(33.61, 43.52, "邪兽人尸体·第二趟", f"↳ 做{n(9410)}", "maghar", "在尸体处使用先祖狼魂图腾，跟随狼魂前往玛格汉岗哨。", "script", (9410,), fivebox="确认五号是否都要分别使用先祖狼魂图腾并各自完成跟随。")
    P(31.99, 27.79, "玛格汉岗哨", f"格尔坎·血拳 → 交{n(9410)} → 接{n(9406)}", "maghar", qids=(9410, 9406))
    P(55.02, 35.96, "萨尔玛", f"纳兹格雷尔 → 交{n(9406)}", "maghar", "", "ride", (9406,))


def g6_falcon_first_west_loop() -> None:
    P(27.05, 60.24, "猎鹰岗哨", f"游侠队长维恩雷 → 交{n(9499)} → 接{n(9340)}、{n(10103)}\n通缉布告 → 接{n(9466)}\n阴沉的利亚森 → 接{n(9366)}\n魔导师卡尔琳达 → 接{n(9374)}\n药剂师艾瑟森 → 接{n(9387)}\n塔雷里斯·晨光 → 接{n(9376)}\n驯鹰者德蕾娜·河风 → 接{n(10442)}\n开飞行点：猎鹰岗哨", "falcon", "", "ride", (9499, 9340, 10103, 9466, 9366, 9374, 9387, 9376, 10442))
    P(40.0, 33.0, "阿苟纳之池", f"↳ 做{n(10136)}、{n(10389)}、{n(9366)}、{n(9374)}", "pools", "同片处理阿拉修斯、10只恐惧魔、6份邪血样本和埃雷利恩的日记。", "ride", (10136, 10389, 9366, 9374), fivebox="确认邪血样本和埃雷利恩日记是否需要五号分别取得；击杀信用按实测记录。")
    P(33.37, 65.08, "大裂隙", f"↳ 做{n(9340)}、{n(9466)}", "fissure", "击杀石镰幼崽/突击者与黑色利爪。同区潜伏怪若自然掉被腐蚀的皮箱，可顺手接《遗失的信件》；不为皮箱补刷。", "ride", (9340, 9466))
    P(22.11, 68.30, "尘羽峡谷营地", f"↳ 做{n(9376)}", "fissure", "寻找丢失的朝圣者背包。", "ride", (9376,), fivebox="确认同一只背包是否能让五号连续互动完成。")
    P(16.27, 65.09, "沙纳尔废墟·纳拉杜", f"↳ 做{n(9387)}\n纳拉杜 → 接{n(10367)}", "shanaar", "《堕落之源》需要5个恶魔精华。", "ride", (9387, 10367))
    P(14.34, 63.50, "沙纳尔废墟·金属箱", f"↳ 做{n(10367)}", "shanaar", "固定金属箱取得沙纳尔钥匙。", "ride", (10367,), fivebox="确认同一金属箱取得钥匙是否需要五号分别互动/等待刷新。")
    P(16.27, 65.09, "纳拉杜", f"纳拉杜 → 交{n(10367)} → 接{n(10368)}", "shanaar", qids=(10367, 10368))
    P(13.13, 58.75, "沙纳尔废墟·三长者", f"↳ 做{n(10368)}", "shanaar", qids=(10368,), fivebox="确认释放三名长者是否一号互动即可同步给队伍。")
    P(16.27, 65.09, "纳拉杜", f"纳拉杜 → 交{n(10368)} → 接{n(10369)}\n↳ 做{n(10369)}\n纳拉杜 → 交{n(10369)}", "shanaar", "对无情的阿尔泽斯使用长者法杖后击杀；本地闭环后再回猎鹰。", "ride", (10368, 10369))
    P(27.05, 60.24, "猎鹰岗哨", f"游侠队长维恩雷 → 交{n(9340)}、{n(9466)}、{n(9376)} → 接{n(9391)}\n阴沉的利亚森 → 交{n(9366)} → 接{n(9370)}\n魔导师卡尔琳达 → 交{n(9374)} → 接{n(10286)}\n药剂师艾瑟森 → 交{n(9387)}", "falcon", qids=(9340, 9466, 9376, 9391, 9366, 9370, 9374, 10286, 9387))
    P(55.02, 35.96, "系统飞行：猎鹰岗哨 → 萨尔玛 → 猎鹰岗哨", f"系统飞行：猎鹰岗哨 → 萨尔玛\n纳兹格雷尔 → 交{n(10136)}\n魔导师文森特·血鹰 → 交{n(10389)}\n系统飞行：萨尔玛 → 猎鹰岗哨", "falcon", "两项阿苟纳任务已在第一次西侧大环完成；利用已开的飞行点领取奖励后立即返回，不重跑陆路。", "taxi", (10136, 10389))


def g7_falcon_gated_second_loop() -> None:
    P(26.56, 63.04, "猎鹰岗哨外·魔导师阿利迪斯", f"魔导师阿利迪斯 → 交{n(10286)} → 接{n(10287)}", "falcon", "阿利迪斯在猎鹰岗哨外道路附近巡逻；找到并对话后原地接后续。", "ride", (10286, 10287))
    P(26.38, 60.32, "猎鹰岗哨", f"魔导师卡尔琳达 → 交{n(10287)} → 接{n(9472)}\n↳ 做{n(9472)}\n魔导师卡尔琳达 → 交{n(9472)}", "falcon", "诱使薇拉离岗后使用惩戒卷轴。", "ride", (10287, 9472), fivebox="确认惩戒薇拉的事件是否需要五号分别触发。")
    P(40.0, 32.9, "阿苟纳之池·第二趟", f"↳ 做{n(9370)}", "pools", "该趟是《邪恶之血》交回后才解锁的真实第二次进入；放置信号宝石后击杀召出的德莱尼学者。", "ride", (9370,), fivebox="确认一号放置信号宝石并击杀召唤目标后其余四号是否同步完成。")
    P(34.07, 60.58, "大裂隙·三座灯塔", f"↳ 做{n(9391)}", "fissure", "点燃南部、西部、中部三座灯塔；这是《大裂隙》交回后才解锁的第二次进入。", "ride", (9391,), fivebox="确认三座灯塔是否需要五号分别使用任务火炬。")
    P(27.05, 60.24, "猎鹰岗哨", f"阴沉的利亚森 → 交{n(9370)}\n游侠队长维恩雷 → 交{n(9391)}", "falcon", qids=(9370, 9391))


def g8_cenarion_post_exit() -> None:
    P(15.70, 52.09, "塞纳里奥哨站", f"塞安·红鬃 → 交{n(10442)} → 接{n(9372)}\n图拉希恩 → 接{n(10132)}\n玛霍拉姆·硬蹄 → 接{n(10159)}\n阿米希尔·迷雾行者 → 接{n(9912)}", "cenarion", "若前面自然获得被腐蚀的皮箱并接到《遗失的信件》，到这里顺手交；不为皮箱补刷。", "ride", (10442, 9372, 10132, 10159, 9912))
    P(15.23, 42.25, "塞纳里奥哨站北侧巨人", f"↳ 做{n(10132)}\n↳ 接{n(10134)}", "cenarion", "击杀5个暴怒巨人；火红水晶碎片由同片巨人掉落并触发《火红水晶中的线索》，与必做击杀绑定处理。", "ride", (10132, 10134), fivebox="确认火红水晶碎片同一尸体能否供五号分别拾取；若不能，记录实际补杀量。")
    P(10.02, 51.60, "棘牙岭", f"↳ 做{n(10159)}、{n(9372)}", "cenarion", "棘牙掠食者/喷毒者与地狱野猪同属塞纳里奥西侧扇区；《恶魔的玷污》需要6份血样。", "ride", (10159, 9372), fivebox="确认地狱野猪血样是否个人掉落；共享未知保留待实测。")
    P(15.70, 52.09, "塞纳里奥哨站", f"图拉希恩 → 交{n(10132)}、{n(10134)} → 接{n(10349)}\n玛霍拉姆·硬蹄 → 交{n(10159)}\n塞安·红鬃 → 交{n(9372)} → 接{n(10255)}", "cenarion", qids=(10132, 10134, 10349, 10159, 9372, 10255))
    P(15.83, 51.83, "缚地者加兰蒂娅·夜风", f"缚地者加兰蒂娅·夜风 → 交{n(10349)} → 接{n(10351)}\n↳ 做{n(10351)}\n缚地者加兰蒂娅·夜风 → 交{n(10351)}", "cenarion", "在缚地者法阵使用新生之种，完成本地短脚本。", "script", (10349, 10351), fivebox="确认新生之种事件是否需要五号分别使用任务物品。")
    P(15.70, 52.09, "塞纳里奥哨站·野猪测试", f"↳ 做{n(10255)}\n塞安·红鬃 → 交{n(10255)}", "cenarion", "对一只笨拙的地狱野猪使用塞纳里奥解毒剂并观察结果。", "ride", (10255,), fivebox="确认一号使用解毒剂并击杀后其余四号是否同步完成。")
    P(15.95, 52.15, "塞纳里奥哨站 → 赞加沼泽", f"阿米希尔·迷雾行者 → 确认已接{n(9912)}\n陆路越境进入赞加沼泽 → 塞纳里奥庇护所 → 交{n(9912)}", "exit", "《向祖莱报到》继续携带；进入赞加后在正式赞加第1步自然到沼泽鼠岗哨时交给祖莱。", "crossmap", (9912,))


GROUPS = [
    ("黑暗之门 → 萨尔玛 → 东部前线", "完成外域入场、萨尔玛开点与东部燃烧军团主链，机甲残骸开到地狱岩床。", g1_portal_east_front),
    ("萨尔玛装备包 → 机甲残骸 → 断背岗哨", "把《我为部落工作！》与《噬骨之血》同片完成；随后利用任务双足飞龙进入断背岗哨。", g2_thrallmar_gear_to_spinebreaker),
    ("断背岗哨 → 军械库 → 塞斯高", "只做共享击杀与塞斯高主链；神秘典籍仅自然掉落时进入条件支线，不补刷。", g3_spinebreaker_armory_zethgor),
    ("地狱岩床 → 矿洞 → 铸魔营地", "炉石回萨尔玛后完成北部共享击杀、矿洞短链和燃烧军团连续链。", g4_thrallmar_north_and_forge),
    ("刺客 → 玛格汉岗哨", "闭合《刺客》到《玛格汉》的低随机任务包；到萨尔玛交《玛格汉》后停止跨大陆后续。", g5_assassin_maghar_package),
    ("猎鹰岗哨 → 阿苟纳 → 大裂隙 → 沙纳尔", "第一次西侧大环同步装备任务与沙纳尔短链，明确跳过低收益随机收集和随机鸟巢。", g6_falcon_first_west_loop),
    ("猎鹰岗哨后续 → 阿苟纳 / 大裂隙第二趟", "只回访任务链真正解锁的《阻止净化》和《点燃灯塔》，同时闭合埃雷利恩本地后续。", g7_falcon_gated_second_loop),
    ("塞纳里奥哨站 → 赞加沼泽", "完成塞纳里奥本地高密度短链，接《塞纳里奥远征队》后直接越境进入赞加。", g8_cenarion_post_exit),
]

for title, summary, fn in GROUPS:
    G(title, summary, fn)

# Pre-live timing is deliberately broad. The first group was a learning run with
# large pauses, so do not treat its raw wall clock as a clean route baseline.
# These values only satisfy the shared Route Atlas timing contract until the
# next fresh group provides a real speed-route sample.
STEP_TIMINGS = [
    (45.0, 32.0, 60.0),
    (35.0, 25.0, 48.0),
    (45.0, 32.0, 60.0),
    (65.0, 48.0, 82.0),
    (35.0, 25.0, 48.0),
    (65.0, 48.0, 82.0),
    (40.0, 30.0, 52.0),
    (30.0, 22.0, 40.0),
]
for group, (center, low, high) in zip(groups, STEP_TIMINGS, strict=True):
    group["timing"] = {"centerMinutes": center, "rangeMinutes": [low, high]}

apply_howling_semantic_hud(points, groups)

missing = sorted(MAIN_IDS - covered)
unexpected = sorted((covered - MAIN_IDS) - CONDITIONAL_IDS)

# Minimal lifecycle gate: checks only the route's current contract, not an old
# route snapshot. 9407 is an inbound turn-in; 10103 is handed off to Zangarmarsh.
action_text = "\n".join(str(point[3]) for point in points)
accept_missing: list[int] = []
turn_missing: list[int] = []
for qid in sorted(MAIN_IDS):
    name = re.escape(TASKS[qid]["name"])
    # A single NPC line often says `接《A》、《B》` or `交《A》、《B》`.
    # Check only within that action line so the gate follows current grammar
    # without requiring the verb to be repeated before every task name.
    if qid not in ENTRY_TURN_ONLY and not re.search(rf"接[^\n]*《{name}》", action_text):
        accept_missing.append(qid)
    if qid not in CROSSMAP_HANDOFF and not re.search(rf"交[^\n]*《{name}》", action_text):
        turn_missing.append(qid)

route = {
    "order": 1,
    "title": "地狱火半岛 · 58—64五开速度路线",
    "sub": "黑暗之门起步，依次完成东部前线、断背/塞斯高、萨尔玛北线、猎鹰/塞纳里奥任务簇，最后直接进入赞加。",
    "badge": "炉石：萨尔玛\n预计总时间：360分钟",
    "hearthChain": ["萨尔玛"],
    "timing": {"centerMinutes": 360.0, "rangeMinutes": [270.0, 450.0]},
    "uiStandard": "semantic-hud-v45",
    "image": "maps/3483-hellfire-peninsula-hd.jpg",
    "legend": "",
    "footer": "塞纳里奥哨站接《塞纳里奥远征队》后直接越境赞加；《向祖莱报到》继续携带到沼泽鼠岗哨。",
    "labels": [
        [87.35, 49.78, "黑暗之门"],
        [55.1, 36.3, "萨尔玛"],
        [65.9, 43.6, "机甲残骸"],
        [61.7, 81.7, "断背岗哨"],
        [68.0, 73.0, "塞斯高"],
        [51.4, 30.5, "萨尔玛西北矿洞"],
        [31.99, 27.79, "玛格汉岗哨"],
        [27.05, 60.24, "猎鹰岗哨"],
        [40.0, 33.0, "阿苟纳之池"],
        [16.27, 65.09, "沙纳尔废墟"],
        [15.70, 52.09, "塞纳里奥哨站"],
    ],
    "points": points,
    "defaultIndex": 0,
    "phaseColors": {},
    "displayName": "地狱火半岛",
    "stepGroups": groups,
    "defaultGroupIndex": 0,
}

routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
# Idempotent insertion: failed/repeated builds must not keep shifting every map.
routes.pop("hellfire", None)
ordered_existing = sorted(
    routes.items(),
    key=lambda item: int(item[1].get("order", 9999)) if isinstance(item[1], dict) else 9999,
)
for order, (_, existing) in enumerate(ordered_existing, start=2):
    if isinstance(existing, dict):
        existing["order"] = order
routes["hellfire"] = route
WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

journey = json.loads((ROOT / "data/journey/current-paladin.json").read_text(encoding="utf-8"))
completed = {
    int(event["quest_id"])
    for event in journey.get("events", [])
    if event.get("event") == "Complete" and isinstance(event.get("quest_id"), int)
}

scope = {
    "status": "formal_speed_route_first_version",
    "zone": "地狱火半岛",
    "design_rule": "Journey只作首跑事实/耗时证据；正式顺序按任务簇重排。外域优先避开多件个人拾取、随机长尾、高交互低收益任务包，但保留直接装备和短链装备包。",
    "main_task_count": len(MAIN_IDS),
    "main_task_ids": sorted(MAIN_IDS),
    "main_journey_completed_count": len(MAIN_IDS & completed),
    "main_not_seen_complete_in_first_run": sorted(MAIN_IDS - completed),
    "conditional_natural_drop_ids": sorted(CONDITIONAL_IDS),
    "optional_equipment_packs": OPTIONAL_EQUIPMENT_PACKS,
    "skipped": [
        {"quest_id": qid, "name": TASKS.get(qid, {}).get("name"), "reason": reason}
        for qid, reason in sorted(SKIP_REASONS.items())
    ],
    "crossmap": {
        "9912": "在地狱火塞纳里奥哨站由阿米希尔·迷雾行者自然接取；越境后在赞加塞纳里奥庇护所交。",
        "10103": "猎鹰岗哨接取；带入赞加，在沼泽鼠岗哨交给祖莱。",
    },
    "coverage": {
        "covered_main_count": len(MAIN_IDS & covered),
        "missing": missing,
        "unexpected": unexpected,
        "accept_missing": accept_missing,
        "turn_missing": turn_missing,
        "point_count": len(points),
        "step_group_count": len(groups),
    },
}
SCOPE_OUT.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
GROUPS_OUT.write_text(json.dumps({
    "zone": "地狱火半岛",
    "pointCount": len(points),
    "groupCount": len(groups),
    "groups": [
        {"title": group["title"], "summary": group["summary"], "pointCount": group["end"] - group["start"] + 1}
        for group in groups
    ],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

REPORT.write_text(
    "# 地狱火半岛58—64五开速度路线\n\n"
    f"- 主路线任务：{len(MAIN_IDS)}；首组Journey已完成其中{len(MAIN_IDS & completed)}项。\n"
    f"- 路线点：{len(points)}；玩家步骤：{len(groups)}。\n"
    "- Journey只用于证明当前服务器任务存在/可达与识别首跑高墙钟；正式路线按任务簇重排。\n"
    "- 明确从默认路线移出：飞艇30碎片包、虚空40碎片包、沸腾之血后半长链、随机鸟巢和无关键装备的多件收集。\n"
    "- 神秘典籍、燃烧军团信件、被腐蚀的皮箱均按自然掉落机会支线处理，不为触发物补刷。\n"
    "- 9912《塞纳里奥远征队》来源已由首组Journey闭合：地狱火塞纳里奥哨站接，赞加塞纳里奥庇护所交；10103《向祖莱报到》带到沼泽鼠岗哨交。\n",
    encoding="utf-8",
)

result = scope["coverage"]
print(json.dumps(result, ensure_ascii=False, indent=2))
if missing or unexpected or accept_missing or turn_missing:
    raise SystemExit(2)
