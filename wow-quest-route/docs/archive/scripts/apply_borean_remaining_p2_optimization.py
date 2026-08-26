from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"


def remap_groups(groups, order, overrides):
    old_to_new = {old_idx: new_idx - 1 for new_idx, old_idx in enumerate(order, 1)}
    new_groups = []
    for old_group_index, group in enumerate(groups, 1):
        lo = int(group["start"]) + 1
        hi = int(group["end"]) + 1
        kept = [old_idx for old_idx in order if lo <= old_idx <= hi]
        if not kept:
            continue
        new_group = copy.deepcopy(group)
        positions = [old_to_new[old_idx] for old_idx in kept]
        new_group["start"] = min(positions)
        new_group["end"] = max(positions)
        if old_group_index in overrides:
            new_group.update(overrides[old_group_index])
        new_groups.append(new_group)
    return new_groups


def set_action(points, old_idx, action, *, label=None, note=None):
    point = points[old_idx - 1]
    if label is not None:
        point[2] = label
    point[3] = action
    if note is not None:
        point[5] = note


def patch_borean(route):
    points = copy.deepcopy(route["points"])
    if len(points) != 221:
        raise RuntimeError(f"Expected pre-patch Borean 221 points, got {len(points)}")

    set_action(points, 28, "交《坦克可不会自己修好！》 → 接《莫布的坦克零件气动装配器》")
    set_action(points, 29, "接《古代水手的号角》")
    set_action(points, 30, "做《莫布的坦克零件气动装配器》：到约(32.4,49.2)进入岸边小屋，固定任务零件就在屋内，点击拾取；随后沿克瓦迪尔带开始找《古代水手的号角》")
    set_action(points, 31, "在克瓦迪尔怪区做《古代水手的号角》；五号拿到各自号角后即可离开，不再为《超强度金属板！》或《深入迷雾》补刷")
    set_action(points, 34, "交《莫布的坦克零件气动装配器》")
    set_action(points, 35, "交《古代水手的号角》 → 接《舵手奥拉布斯》")
    set_action(points, 42, "交《舵手奥拉布斯》")
    set_action(points, 45, "接《卡鲁克的誓言》")
    set_action(points, 57, "接《危在旦夕》 + 接《立即前往博古洛克前哨站！》")

    set_action(points, 75, "做《清除北地狗头人》")
    set_action(points, 78, "顺路到巨大的发光蛾卵，点击地面的 Massive Glowing Egg（巨大的发光蛾卵），自动接《巨大的蛾卵》", label="巨大的发光蛾卵")
    set_action(points, 79, "交《巨大的蛾卵》", label="血法师劳莉丝")

    set_action(points, 102, "交《遗弃海岸》；随后去东南侧佣兵带补《敌人的耳环》")
    set_action(points, 103, "杀北海雇佣兵/北海暴徒，把《敌人的耳环》补到15；不再为《不可容忍》收集动物杂货箱")
    set_action(points, 105, "交《驯鹿杀手之死》 + 交《敌人的耳环》；仁德会当前保留任务回收完成", label="仁德会回收")
    set_action(points, 116, "开启牦牛村飞行点；交《前往牦牛村》→接《他们想干什么？》；接《侦查虫孔》 + 接《运货行动！》 + 接《先知赫米萨》")

    delete_indices = {36, 37, 38, 39, 41, 43, 44, 74, 77, 80, 81, 82, 104, 106, 107}
    order = [idx for idx in range(1, len(points) + 1) if idx not in delete_indices]
    # After removing the Bloodspore chain, pick the nearby independent moth egg before
    # returning to Scout Tungok/Laurith instead of riding out and back twice.
    order.remove(78)
    order.insert(order.index(76), 78)

    route["points"] = [points[idx - 1] for idx in order]
    route["stepGroups"] = remap_groups(
        route["stepGroups"],
        order,
        {
            8: {"title": "码头接回音海岸保留任务", "summary": "交《魔法飞毯》后接《莫布的坦克零件气动装配器》和《古代水手的号角》；不再接《超强度金属板！》《深入迷雾》。"},
            9: {"title": "固定零件 + 号角 + 短护送", "summary": "先拿固定零件，在克瓦迪尔带只做到五号各自拿到《古代水手的号角》，再顺手完成小穆图短护送；不为已删多掉落任务补刷。"},
            10: {"title": "护送交付并回收码头任务", "summary": "护送结束后交《莫布的坦克零件气动装配器》；交《古代水手的号角》接《舵手奥拉布斯》。"},
            11: {"title": "舵手奥拉布斯事件", "summary": "直接去战歌码头尽头吹响号角完成《舵手奥拉布斯》，跳过四艘烧船路线。"},
            12: {"title": "海岸交付后直奔卡鲁克", "summary": "回瓦托尔交《舵手奥拉布斯》后直接前往裂鞭海岸，不再上坦克做《纳萨姆平原》。"},
            13: {"title": "卡鲁克第一段海岸链", "summary": "到卡鲁克直接接《卡鲁克的誓言》；再接《残忍的科瓦迪尔》，与《卡鲁克的誓言》同一海岸处理并继续贾梅尔链。"},
            16: {"title": "炉石回战歌并检查机会任务", "summary": "炉石回战歌后接《危在旦夕》《立即前往博古洛克前哨站！》，再看一眼伊斯里克斯事件；不再交《纳萨姆平原》。"},
            21: {"title": "炉石回战歌 → 诺克 → 图古克", "summary": "回战歌交《愚蠢的努力》接诺克链，送完逃兵后在图古克接《清除北地狗头人》；不再开启血孢多掉落链。"},
            22: {"title": "清狗头人 + 巨蛾卵顺路交付", "summary": "完成《清除北地狗头人》后顺路点巨大的发光蛾卵接《巨大的蛾卵》，再回图古克交狗头人任务、到劳莉丝交蛾卵；不进入血孢/迦莫斯链。"},
            30: {"title": "仁德会南线：卡琳 → 遗弃海岸补耳环", "summary": "交《猛犸毁灭者卡奥》后先做《驯鹿杀手之死》，下到莉安德拉交《遗弃海岸》，随后只在佣兵带把《敌人的耳环》补到15；不接《不可容忍》。"},
            31: {"title": "仁德会保留任务交付", "summary": "回仁德会交《驯鹿杀手之死》和《敌人的耳环》；跳过蛤蜊主宰与哈罗德刺杀尾链。"},
            34: {"title": "牦牛村第一轮：接任务 → 三处虫孔调查", "summary": "开启牦牛村飞行点；交《前往牦牛村》接《他们想干什么？》，再接《侦查虫孔》《运货行动！》《先知赫米萨》并开始虫孔调查；不再交《地狱咆哮的勇士》。"},
        },
    )


def patch_dragonblight(route):
    points = copy.deepcopy(route["points"])
    if len(points) != 194:
        raise RuntimeError(f"Expected pre-patch Dragonblight 194 points, got {len(points)}")

    set_action(points, 7, "交《阿格玛之锤》 → 接《胜利将近……》；若此时已到73级，同营地接《高级执行官需要你》长期携带去怨毒镇；未到73级则先不接")
    set_action(points, 57, "炉石回阿格玛之锤；若此时已到73级且此前未接《高级执行官需要你》，现在补接；若仍为72级则继续月影花园主链")
    set_action(points, 62, "交《寻找线索》 → 接《阻碍协议》；同时交《通缉：魔导师凯尔多努斯》；若此前仍未接《高级执行官需要你》，按当前纯任务下界此时已保证达到73级，在阿格玛同营地补接；回伊瑟尼安前顺路交《阿坎尼姆斯的终结》")

    order = [idx for idx in range(1, len(points) + 1) if idx != 10]
    route["points"] = [points[idx - 1] for idx in order]
    route["stepGroups"] = remap_groups(
        route["stepGroups"],
        order,
        {
            3: {"title": "阿格玛主线开场 + 飞行点 / 炉石", "summary": "交《阿格玛之锤》接《胜利将近……》并设置交通；《高级执行官需要你》只在已到73级时接。因北风已删除《地狱咆哮的勇士》，不再做《萨鲁法尔的信》。"},
            15: {"title": "冰心洞穴 + 拉特尔博尔 → 炉石阿格玛", "summary": "完成水晶裂痕/冰心洞穴任务后炉石回阿格玛；若实际经验已到73则补接《高级执行官需要你》，否则继续月影花园。"},
            16: {"title": "眠月花园第一轮：计划书 + 伊瑟尼安 + 通缉", "summary": "完成眠月花园第一轮并回阿格玛交《寻找线索》；按当前纯任务下界此处保证到73，若此前未接则在同Hub补接《高级执行官需要你》。"},
        },
    )


def main():
    data = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    patch_borean(data["borean"])
    patch_dragonblight(data["dragonblight"])
    WORKBENCH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patched {WORKBENCH}")
    print(f"borean points={len(data['borean']['points'])} stepGroups={len(data['borean']['stepGroups'])}")
    print(f"dragonblight points={len(data['dragonblight']['points'])} stepGroups={len(data['dragonblight']['stepGroups'])}")


if __name__ == "__main__":
    main()
