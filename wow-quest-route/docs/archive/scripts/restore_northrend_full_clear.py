from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
BASELINE_COMMIT = "d4b6943"
BASELINE_PATH = "wow-quest-route/data/route-atlas/workbench-routes.json"


def split_groups(route: dict) -> list[dict]:
    out = []
    for group in route["stepGroups"]:
        start, end = int(group["start"]), int(group["end"])
        out.append(
            {
                "title": group["title"],
                "summary": group.get("summary", ""),
                "points": copy.deepcopy(route["points"][start : end + 1]),
            }
        )
    return out


def flatten(route: dict, groups: list[dict]) -> None:
    points = []
    step_groups = []
    for group in groups:
        start = len(points)
        points.extend(group["points"])
        step_groups.append(
            {
                "start": start,
                "end": len(points) - 1,
                "title": group["title"],
                "summary": group.get("summary", ""),
            }
        )
    route["points"] = points
    route["stepGroups"] = step_groups


def find_group(groups: list[dict], title: str) -> dict:
    matches = [g for g in groups if g["title"] == title]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group {title!r}, got {len(matches)}")
    return matches[0]


def find_point(group: dict, title: str) -> list:
    matches = [p for p in group["points"] if p[2] == title]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one point {title!r} in {group['title']!r}, got {len(matches)}")
    return matches[0]


def old_group(old_groups: list[dict], title: str) -> dict:
    return copy.deepcopy(find_group(old_groups, title))


def main() -> None:
    data = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    route = data["borean"]
    route_text = json.dumps(route, ensure_ascii=False)
    if "《超强度金属板！》" in route_text and "《地狱咆哮的勇士》" in route_text and "《美味炖鲸肉》" in route_text:
        print("Borean full-clear restoration already present; no changes.")
        return

    old_data = json.loads(
        subprocess.check_output(
            ["git", "show", f"{BASELINE_COMMIT}:{BASELINE_PATH}"],
            text=True,
            cwd=ROOT,
        )
    )
    groups = split_groups(route)
    old_groups = split_groups(old_data["borean"])

    # Echo Coast: restore the two drop quests, burn-ships chain, tank/Nasam and Find Karuk.
    g = find_group(groups, "码头接回音海岸保留任务")
    g["title"] = "码头接齐回音海岸任务"
    g["summary"] = "交《魔法飞毯》后把莫布、瓦托尔这组一次性任务全部接齐；慢掉落任务保留，但与同一克瓦迪尔怪区合并完成。"
    find_point(g, "回音海岸·莫布")[3] = "交《坦克可不会自己修好！》 → 接《莫布的坦克零件气动装配器》 + 接《超强度金属板！》"
    find_point(g, "回音海岸·瓦托尔")[3] = "接《深入迷雾》 + 接《古代水手的号角》"

    g = find_group(groups, "固定零件 + 号角 + 短护送")
    g["title"] = "固定零件 + 克瓦迪尔三任务 + 短护送"
    g["summary"] = "先拿固定零件，再在同一克瓦迪尔怪区同时推进《超强度金属板！》《深入迷雾》《古代水手的号角》，避免为低掉率任务单独折返；顺路完成小穆图短护送。"
    old = old_group(old_groups, "零件 + 克瓦迪尔共享刷怪 + 短护送")
    find_point(g, "南侧小屋·固定零件")[3] = find_point(old, "南侧小屋·固定零件")[3]
    find_point(g, "克瓦迪尔共享刷怪带")[3] = "在同一克瓦迪尔怪区同时做《超强度金属板！》《深入迷雾》《古代水手的号角》；三项都保留，优先利用同一批击杀一起推进，离开前确认五个角色均达到各自交付条件"

    g = find_group(groups, "护送交付并回收码头任务")
    g["title"] = "护送交付并批量换下一轮任务"
    g["summary"] = "护送结束后按穆图→莫布→瓦托尔→格雷克罗连续交接，解锁《坦克准备就绪！》《烧毁船只》《纳萨姆平原》。"
    old = old_group(old_groups, "护送交付并批量换下一轮任务")
    find_point(g, "莫布")[3] = find_point(old, "莫布")[3]
    find_point(g, "瓦托尔")[3] = find_point(old, "瓦托尔")[3]
    g["points"].append(copy.deepcopy(find_point(old, "格雷克罗")))

    idx = groups.index(find_group(groups, "舵手奥拉布斯事件"))
    groups[idx] = old_group(old_groups, "四艘船 + 奥拉布斯一次海岸闭环")
    idx = groups.index(find_group(groups, "海岸交付后直奔卡鲁克"))
    groups[idx] = old_group(old_groups, "海岸交付后直接上坦克做纳萨姆")

    g = find_group(groups, "卡鲁克第一段海岸链")
    g["summary"] = "先交《找到卡鲁克！》再接《卡鲁克的誓言》；随后接《残忍的科瓦迪尔》，两条同一海岸处理并继续贾梅尔链。"
    find_point(g, "裂鞭海岸·卡鲁克")[3] = "交《找到卡鲁克！》 → 接《卡鲁克的誓言》"

    g = find_group(groups, "炉石回战歌并检查机会任务")
    g["summary"] = "炉石回战歌先交《纳萨姆平原》，再接《危在旦夕》《立即前往博古洛克前哨站！》，顺路看一次伊斯里克斯事件。"
    find_point(g, "战歌要塞·加尔鲁什")[3] = "交《纳萨姆平原》；接《危在旦夕》 + 接《立即前往博古洛克前哨站！》"

    # Bloodspore/Gammoth: restore the entire chain but keep the improved moth-egg co-location.
    g = find_group(groups, "炉石回战歌 → 诺克 → 图古克")
    g["title"] = "炉石回战歌 → 诺克 → 图古克 / 劳莉丝"
    g["summary"] = "交《愚蠢的努力》接诺克链，送完逃兵后接《清除北地狗头人》，并在劳莉丝处接《奇妙的血孢》。"
    old20 = old_group(old_groups, "战歌 → 诺克 → 图古克/劳莉丝接血孢线")
    g["points"].append(copy.deepcopy(find_point(old20, "血法师劳莉丝")))

    idx = groups.index(find_group(groups, "清狗头人 + 巨蛾卵顺路交付"))
    groups[idx] = old_group(old_groups, "血孢平原一圈 + 巨蛾/蛾卵同点完成")
    groups.insert(idx + 1, old_group(old_groups, "迦莫斯洞穴收尾并回战歌"))

    # DEHTA: preserve the user's preferred Carin -> drop down to Leandra ordering, then restore tail chain.
    g = find_group(groups, "仁德会南线：卡琳 → 遗弃海岸补耳环")
    p_recover = copy.deepcopy(find_point(g, "仁德会第二次回收"))
    p_carin = copy.deepcopy(find_point(g, "驯鹿杀手卡琳"))
    p_leandra = copy.deepcopy(find_point(g, "圣职者莉安德拉"))
    p_coast = copy.deepcopy(find_point(g, "遗弃海岸佣兵带"))
    p_leandra[3] = "交《遗弃海岸》 → 接《不可容忍》"
    p_coast[3] = "做《不可容忍》动物组织；同时杀北海雇佣兵/北海暴徒，把《敌人的耳环》补到15"
    old28 = old_group(old_groups, "仁德会南线：莉安德拉与遗弃海岸")
    p_leandra2 = copy.deepcopy(find_point(old28, "莉安德拉"))
    g["title"] = "仁德会南线：卡琳 → 遗弃海岸 / 不可容忍"
    g["summary"] = "交卡奥后先做卡琳，再顺地形下到莉安德拉交《遗弃海岸》接《不可容忍》；在佣兵带同时补耳环和动物组织，回莉安德拉交付并接蛤蜊主宰。"
    g["points"] = [p_recover, p_carin, p_leandra, p_coast, p_leandra2]

    idx = groups.index(find_group(groups, "仁德会保留任务交付"))
    tail = old_group(old_groups, "蛤蜊主宰 + 哈罗德终局")
    tail["title"] = "蛤蜊主宰 + 哈罗德终局"
    tail["summary"] = "完成蛤蜊主宰，回仁德会同时交《驯鹿杀手之死》《敌人的耳环》和蛤蜊任务，接并完成《刺杀哈罗德·兰恩》，仁德会全清。"
    p = find_point(tail, "仁德会终局")
    p[3] = "交《驯鹿杀手之死》 + 交《敌人的耳环》 + 交《罪恶的蛤蜊主宰……》；全部前置齐全 → 接《刺杀哈罗德·兰恩》"
    groups[idx] = tail

    # Taunka'le: turn in the restored Warsong-wide chain breadcrumb while already at the hub.
    g = find_group(groups, "牦牛村第一轮：接任务 → 三处虫孔调查")
    g["summary"] = "开启牦牛村飞行点；交《前往牦牛村》和《地狱咆哮的勇士》，接齐虫孔/运货/先知任务并开始调查。"
    p = find_point(g, "牦牛村·第一次Hub扫描")
    p[3] = "开飞行点：牦牛村\n交《前往牦牛村》 → 接《他们想干什么？》\n交《地狱咆哮的勇士》\n接《侦查虫孔》《运货行动！》《先知赫米萨》"

    # Coldarra: restore Ancient Tree's Secret and Stay Hidden; dungeon/raid followups remain outside this outdoor route.
    g = find_group(groups, "永生之盾开场 → 南 / 西监测点")
    g["summary"] = "开启永生之盾飞行点并接齐户外任务；南/西监测点同圈推进《古树的秘密》《冰冷的草莓》《基本的训练》。"
    p = find_point(g, "考达拉·永生之盾")
    p[3] = "开启考达拉/永生之盾（Transitus Shield）飞行点；交《飞越裂谷》；接《监测数据》 + 接《古树的秘密》 + 接《冰冷的草莓》 + 接《基本的训练》"
    find_point(g, "考达拉南监测点")[3] = "做《监测数据》南点：到约(28.5,35.0)找到地上的地质监测仪并主动点击/读取数据；沿路做《古树的秘密》/《冰冷的草莓》/《基本的训练》"

    g = find_group(groups, "北部监测 → 中央监测 → 永生之盾回收")
    g["summary"] = "继续完成北/东北/中央监测点并补齐《古树的秘密》《冰冷的草莓》《基本的训练》；回永生之盾交付，接《保持隐蔽》和《蓝龙的卵》。"
    find_point(g, "考达拉北部")[3] = "推进《监测数据》；继续《古树的秘密》《冰冷的草莓》《基本的训练》"
    find_point(g, "考达拉中央监测点")[3] = "做《监测数据》；补齐《古树的秘密》/《冰冷的草莓》/《基本的训练》"
    find_point(g, "永生之盾第一次回收")[3] = "交《监测数据》；交《古树的秘密》；交《冰冷的草莓》→接《保持隐蔽》；交《基本的训练》→接《蓝龙的卵》"

    g = find_group(groups, "考达拉第二圈 → 触发《奇怪……》")
    g["summary"] = "第二圈同时做《保持隐蔽》和《蓝龙的卵》，刷缚法者触发《奇怪……》；回永生之盾交付并接《猎龙》《牢笼》。"
    find_point(g, "考达拉第二圈")[3] = "做《保持隐蔽》奥术浮蛇 + 做《蓝龙的卵》：先杀5只考达拉龙人拿5把100%掉落的冰霜战斧，再由主控用战斧打碎5枚蓝龙卵；碎卵进度五号共享。随后主动击杀考达拉缚法者，拾取其掉落的任务起始物“Scintillating Fragment（闪光碎片）”，自动接《奇怪……》"
    find_point(g, "莱洛拉斯 / 塞尔拉")[3] = "交《保持隐蔽》；交《蓝龙的卵》→接《猎龙》；交《奇怪……》→接《牢笼》"

    # Winterfin: restore whale stew while already doing the same bay kill loop.
    g = find_group(groups, "救救蝌蚪 → 鱼人服 → 接决不投降")
    g["summary"] = "同圈完成蝌蚪/装备线；到屠夫处同时接《美味炖鲸肉》，在幽光海湾与咕拉咕拉一起做，回Hub交完后再接《决不投降！》。"
    find_point(g, "姆姆咕咕 / 屠夫布咕布噜")[3] = "交《我被敲竹杠了！》→接《咕噜咕噜呜啦哇啦！》；接《美味炖鲸肉》"
    find_point(g, "幽光海湾")[3] = "做《咕噜咕噜呜啦哇啦！》：击杀咕拉咕拉并取得任务物；同时做《美味炖鲸肉》逆戟鲸脂肪"
    find_point(g, "冬鳞Hub")[3] = "交《咕噜咕噜呜啦哇啦！》→接《备用的鱼人服》；交《美味炖鲸肉》"

    flatten(route, groups)
    WORKBENCH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    restored_names = [
        "古树的秘密", "保持隐蔽", "美味炖鲸肉", "超强度金属板！", "坦克准备就绪！", "纳萨姆平原",
        "深入迷雾", "烧毁船只", "找到卡鲁克！", "奇妙的血孢", "授粉的巨蛾", "完美的测试对象",
        "攻打迦莫斯", "折磨者迦莫斯拉", "迦莫斯的战利品", "不可容忍", "罪恶的蛤蜊主宰……",
        "刺杀哈罗德·兰恩", "地狱咆哮的勇士",
    ]
    final_text = json.dumps(route, ensure_ascii=False)
    missing = [name for name in restored_names if f"《{name}》" not in final_text]
    if missing:
        raise RuntimeError(f"Restoration incomplete, still missing: {missing}")
    print(f"restored Borean full-clear route: points={len(route['points'])}, steps={len(route['stepGroups'])}")
    print("restored task names=19/19")


if __name__ == "__main__":
    main()
