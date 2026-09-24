from __future__ import annotations

import copy
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dragonblight_semantic_steps import loc, note_block, notes_html, status_span
from howling_semantic_steps import render_action_line
from lib.task_cards import load_task_card
from lib.task_presentation import project_task_presentation

WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
TASK_RE = re.compile(r"《([^》]+)》")

HELLFIRE_DELETE = {
    "恶魔的玷污",
    "测试解毒剂",
    "我为部落工作！",
    "为了部落，烧！",
    "噬骨之血",
    "药剂师塞兰娜",
    "断背岗哨",
}

ZANG_DELETE = {
    # 孢子村核心包
    "孢子人的困境",
    "天敌",
    "孢子村",
    "成熟的孢子",
    "亮顶蘑菇",
    "既然我们是朋友......",
    # 独立高操作任务 / 任务链
    "热情的欢迎",
    "时尚无罪",
    "最锋利的刀刃",
    "别再提蘑菇了！",
    "未完的职责",
    "厚重多头蛇鳞片",
    "寻找斥候尤尔巴",
    "尤尔巴的报告",
    "蛮沼之灵",
    "灵魂之盟？",
    # 莉萨奥任务链（保留面包屑《观察者莉萨奥》和独立《沼泽中的伯爵》）
    "观察孢子人",
    "狼吞虎咽",
    "熟悉的蘑菇",
    "偷回蘑菇",
    # 《尤尔巴的报告》删除后，不再专门进入死亡泥潭触发该机会任务。
    "枯萎的孢芽",
}


def _clean_action_line(line: str, deleted: set[str]) -> str:
    value = line.strip()
    if not value:
        return ""
    task_names = TASK_RE.findall(value)
    touched = [name for name in task_names if name in deleted]
    if not touched:
        return value
    kept = [name for name in task_names if name not in deleted]
    if not kept:
        return ""

    for name in touched:
        value = value.replace(f"《{name}》", "")

    # Adjacent task names in the legacy action grammar need an explicit separator after removal.
    value = re.sub(r"》\s*《", "》、《", value)
    value = re.sub(r"、{2,}", "、", value)
    value = re.sub(r"、\s*(?=→|；|;|$)", "", value)
    value = re.sub(r"(?<=[接交做])\s*、", "", value)

    # Remove now-empty action atoms such as `→ 接` or `；交` left by deleting the only task.
    value = re.sub(r"\s*→\s*(?:接|交|做)\s*(?=→|；|;|$)", "", value)
    value = re.sub(r"[；;]\s*(?:接|交|做)\s*(?=→|；|;|$)", "", value)
    value = re.sub(r"\s*→\s*(?:接|交|做)\s*$", "", value)
    value = re.sub(r"[；;]\s*(?:接|交|做)\s*$", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace(" 、", "、").replace("、 ", "、")
    return value


def _filter_text(text: str, deleted: set[str]) -> str:
    rows = []
    for line in str(text or "").splitlines():
        # Notes/fivebox text tied only to removed tasks must not survive into the DK page.
        if any(name in line for name in deleted):
            continue
        if line.strip():
            rows.append(line.strip())
    return "\n".join(rows)


def _filter_points(route: dict[str, Any], deleted: set[str]) -> tuple[list[list[Any]], dict[int, int]]:
    filtered: list[list[Any]] = []
    old_to_new: dict[int, int] = {}
    for old_index, raw in enumerate(route["points"]):
        point = copy.deepcopy(raw)
        new_lines = []
        for line in str(point[3]).splitlines():
            cleaned = _clean_action_line(line, deleted)
            if cleaned:
                new_lines.append(cleaned)
        point[3] = "\n".join(new_lines)
        if len(point) > 5:
            point[5] = _filter_text(point[5], deleted)
        if len(point) > 8:
            point[8] = _filter_text(point[8], deleted)
        if not point[3].strip():
            continue
        old_to_new[old_index] = len(filtered)
        filtered.append(point)
    return filtered, old_to_new


def _note_title(point: list[Any]) -> str:
    names = TASK_RE.findall(str(point[3]))
    if len(names) == 1:
        return names[0]
    return str(point[2])


def _semantic_groups(
    points: list[list[Any]],
    groups: list[dict[str, Any]],
    *,
    task_presentations: dict[str, dict[str, Any]] | None = None,
) -> None:
    presentations = task_presentations or {}
    for group in groups:
        action_rows: list[str] = []
        note_rows: list[str] = []
        presentation_rendered: set[str] = set()
        for point in points[int(group["start"]) : int(group["end"]) + 1]:
            title = str(point[2]).strip()
            if title:
                action_rows.append(f'<div class="ra-line ra-point-anchor">{loc(title)}</div>')
            for line in str(point[3]).splitlines():
                rendered = render_action_line(line)
                if rendered:
                    action_rows.append(rendered)

            note = str(point[5] if len(point) > 5 else "").strip()
            fivebox = str(point[8] if len(point) > 8 else "").strip()
            if note:
                note_rows.append(note_block(_note_title(point), html.escape(note)))
            if fivebox:
                # Compatibility path for tasks not migrated to Task Cards yet.
                fivebox_html = html.escape(fivebox)
                if not fivebox.startswith("已实测"):
                    fivebox_html = status_span("五开待实测") + fivebox_html
                note_rows.append(note_block(_note_title(point), fivebox_html))

            for task_name in TASK_RE.findall(str(point[3])):
                if task_name in presentation_rendered or task_name not in presentations:
                    continue
                projected = presentations[task_name]
                body: list[str] = []
                badge = projected.get("badge")
                if badge == "shared":
                    body.append(status_span("共享"))
                elif badge == "not_shared":
                    body.append(status_span("不共享"))
                elif badge == "sequential_loot":
                    body.append(status_span("依次拾取"))
                elif badge == "special":
                    body.append(status_span("特殊"))
                if projected.get("pending"):
                    body.append(status_span("五开待实测"))
                projected_note = projected.get("note")
                if projected_note:
                    body.append(html.escape(str(projected_note)))
                if body:
                    note_rows.append(note_block(task_name, "".join(body)))
                presentation_rendered.add(task_name)
        group["actionHtml"] = "\n".join(action_rows)
        group["noteHtml"] = notes_html(*note_rows)


def _make_groups(
    source_route: dict[str, Any],
    old_to_new: dict[int, int],
    specs: list[tuple[list[int], str, tuple[float, float, float]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    source_groups = source_route["stepGroups"]
    for old_group_indices, title, timing in specs:
        old_points: list[int] = []
        for group_index in old_group_indices:
            source = source_groups[group_index]
            old_points.extend(range(int(source["start"]), int(source["end"]) + 1))
        new_points = [old_to_new[index] for index in old_points if index in old_to_new]
        if not new_points:
            continue
        center, low, high = timing
        result.append(
            {
                "start": min(new_points),
                "end": max(new_points),
                "title": title,
                "summary": "",
                "timing": {
                    "centerMinutes": center,
                    "rangeMinutes": [low, high],
                    "includeInTotal": True,
                },
            }
        )
    return result


def _find_point(
    points: list[list[Any]],
    *,
    title: str | None = None,
    action_contains: str | None = None,
    start: int = 0,
) -> int:
    for index, point in enumerate(points[start:], start):
        if title is not None and str(point[2]) != title:
            continue
        if action_contains is not None and action_contains not in str(point[3]):
            continue
        return index
    raise RuntimeError(f"route point not found: title={title!r} action_contains={action_contains!r}")


def _contiguous_groups(
    ends: list[int],
    specs: list[tuple[str, tuple[float, float, float]]],
) -> list[dict[str, Any]]:
    if len(ends) != len(specs):
        raise RuntimeError("group end/spec count mismatch")
    result: list[dict[str, Any]] = []
    start = 0
    for end, (title, timing) in zip(ends, specs, strict=True):
        center, low, high = timing
        result.append(
            {
                "start": start,
                "end": end,
                "title": title,
                "summary": "",
                "timing": {
                    "centerMinutes": center,
                    "rangeMinutes": [low, high],
                    "includeInTotal": True,
                },
            }
        )
        start = end + 1
    return result


def build_hellfire(base: dict[str, Any]) -> dict[str, Any]:
    route = copy.deepcopy(base)

    # Migration pilot: task 10208 presentation is now projected from its Task Card.  The route
    # structure is still legacy workbench data in this phase; do not infer facts back from it.
    block_reinforcements_card = load_task_card(10208)
    block_reinforcements_presentation = project_task_presentation(
        block_reinforcements_card,
        profile_id="hellfire_dk",
    )
    migrated_presentations = {
        str(block_reinforcements_card["identity"]["name_zhcn"]): block_reinforcements_presentation
    }

    # This transport exists only inside the removed Apothecary Zelana -> Spinebreaker chain.
    # Remove the whole old transport point so the DK variant simply rides from the preserved
    # Mech Wreck area to Spinebreaker Post. Do not leave a stale task-transport waypoint behind.
    route["points"][14][3] = ""
    points, old_to_new = _filter_points(route, HELLFIRE_DELETE)

    # Current-run facts and player-note cleanup. Ordinary quest targets belong to the tracker/action
    # skeleton, not notes. Keep only mechanics that change how the five-box party actually executes.
    portal_arrival = _find_point(points, title="黑暗之门·部落营地")
    points[portal_arrival][5] = ""
    thrallmar_entry = _find_point(points, title="萨尔玛", action_contains="绑定炉石：萨尔玛")
    points[thrallmar_entry][5] = ""

    block_reinforcements = _find_point(points, action_contains="做《阻断援军》")
    points[block_reinforcements][5] = ""
    # The old free-text fivebox field is intentionally blank for migrated task 10208; its badge/note
    # now comes from the Task Card projection above.
    points[block_reinforcements][8] = ""

    portal_bombing = _find_point(points, action_contains="做《任务：穆尔凯斯和沙德拉兹之门》")
    points[portal_bombing][5] = ""
    points[portal_bombing][8] = (
        "已实测：距离足够近时轰炸进度共享；前后错开约两个号执行即可覆盖队伍。"
        "离开前核对五号均已完成。"
    )

    abyssal_shelf = _find_point(points, title="地狱岩床", action_contains="做《任务：地狱岩床》")
    points[abyssal_shelf][5] = ""

    spare_parts = _find_point(points, title="矿洞外回收区")
    points[spare_parts][5] = ""
    goblin_rescue = _find_point(points, title="邪兽人营地")
    points[goblin_rescue][5] = ""
    shizz_work = _find_point(points, title="矿洞", action_contains="做《肮脏的工作》")
    points[shizz_work][5] = "用哨子召地狱犬；击杀野猪后从地狱犬留下的残渣取得钥匙。"

    forge_tyranny = _find_point(points, title="铸魔营地：暴虐")
    points[forge_tyranny][5] = "剃刀电锯若掉落燃烧军团信件，拾取后接《邪恶的计划》；不等刷新。"

    assassin_corpse = _find_point(points, title="邪兽人尸体", action_contains="交《刺客》")
    points[assassin_corpse][5] = ""

    pools = _find_point(points, title="阿苟纳之池")
    points[pools][5] = ""
    points[pools][8] = "确认邪血样本和埃雷利恩日记是否需要五号分别取得。"
    fissure = _find_point(points, title="大裂隙")
    points[fissure][5] = "潜伏怪若掉落被腐蚀的皮箱，拾取后接《遗失的信件》；不补刷。"
    pilgrim = _find_point(points, title="尘羽峡谷营地")
    points[pilgrim][5] = ""
    corruption = _find_point(points, title="沙纳尔废墟·纳拉杜")
    points[corruption][5] = ""
    metal_box = _find_point(points, title="沙纳尔废墟·金属箱")
    points[metal_box][5] = ""
    alzeth = _find_point(points, title="纳拉杜", action_contains="做《阿尔泽斯之死》")
    points[alzeth][5] = "对无情的阿尔泽斯使用长者法杖后再击杀。"

    falcon_taxi_note = _find_point(points, action_contains="系统飞行：猎鹰岗哨 → 萨尔玛")
    points[falcon_taxi_note][5] = ""
    alidis = _find_point(points, title="猎鹰岗哨外·魔导师阿利迪斯")
    points[alidis][5] = "阿利迪斯沿猎鹰岗哨外道路巡逻。"
    pools_second = _find_point(points, title="阿苟纳之池·第二趟")
    points[pools_second][5] = "放置信号宝石后击杀召出的德莱尼学者。"
    beacons = _find_point(points, title="大裂隙·三座灯塔")
    points[beacons][5] = ""
    giants = _find_point(points, title="塞纳里奥哨站北侧巨人")
    points[giants][5] = "巨人若掉落火红水晶碎片，拾取后接《火红水晶中的线索》。"
    natural_healing = _find_point(points, title="缚地者加兰蒂娅·夜风", action_contains="做《自然的治愈》")
    points[natural_healing][5] = "在缚地者法阵使用新生之种。"

    # Without the removed Apothecary Zelana chain there is no free wyvern transport;
    # the preserved Spinebreaker hub is now reached directly by normal route movement.
    spinebreaker = _find_point(points, title="断背岗哨", action_contains="开飞行点：断背岗哨")
    points[spinebreaker][6] = "ride"

    # Optimization 1: the Abyssal Shelf is a task-flight round trip from Mech Wreck. Do it as soon
    # as it is accepted instead of carrying it through the whole Spinebreaker loop and returning later.
    shelf_do = _find_point(points, title="地狱岩床", action_contains="做《任务：地狱岩床》")
    shelf_turn = _find_point(points, title="机甲残骸", action_contains="交《任务：地狱岩床》")
    shelf_block = [points[shelf_do], points[shelf_turn]]
    del points[shelf_do : shelf_turn + 1]
    shelf_block[0][3] = "空军指挥官布拉克 → 乘任务飞行\n↳ 做《任务：地狱岩床》"
    shelf_block[0][6] = "script"
    shelf_accept = _find_point(points, title="机甲残骸", action_contains="接《任务：地狱岩床》")
    points[shelf_accept + 1 : shelf_accept + 1] = shelf_block

    # Optimization 2: after Deep Gate, go straight to the Assassin corpse and hearth back once.
    # Merge the two consecutive Thrallmar hand-ins into the same stop.
    deep_gate = _find_point(points, title="深渊之门", action_contains="做《深渊之门》")
    corpse = _find_point(points, title="邪兽人尸体", action_contains="交《刺客》")
    corpse_point = points.pop(corpse)
    deep_gate = _find_point(points, title="深渊之门", action_contains="做《深渊之门》")
    points.insert(deep_gate + 1, corpse_point)
    thrall_deep = _find_point(points, title="萨尔玛", action_contains="交《深渊之门》")
    thrall_weapon = _find_point(points, title="萨尔玛", action_contains="交《奇怪的武器》")
    points[thrall_deep][3] = str(points[thrall_deep][3]).rstrip() + "\n" + str(points[thrall_weapon][3]).strip()
    points.pop(thrall_weapon)

    # Optimization 3: after Mag'har Post, ride directly to Falcon Watch. Turn in 《玛格汉》 during
    # the later scheduled Falcon Watch -> Thrallmar -> Falcon Watch taxi stop.
    maghar_turn = _find_point(points, title="萨尔玛", action_contains="交《玛格汉》")
    points.pop(maghar_turn)
    falcon_taxi = _find_point(points, action_contains="系统飞行：猎鹰岗哨 → 萨尔玛")
    taxi_lines = str(points[falcon_taxi][3]).splitlines()
    taxi_lines.insert(1, "纳兹格雷尔 → 交《玛格汉》")
    points[falcon_taxi][3] = "\n".join(taxi_lines)

    group_ends = [
        _find_point(points, title="补给车队", action_contains="接《机甲残骸》"),
        _find_point(points, title="机甲残骸", action_contains="交《任务：地狱岩床》"),
        _find_point(points, title="塞斯高·第二趟", action_contains="做《燃烧吧，塞斯高！》"),
        _find_point(points, title="远征军械库·指挥官霍加斯", action_contains="使用炉石：萨尔玛"),
        _find_point(points, title="矿洞", action_contains="接《萨尔玛的地下》"),
        _find_point(points, title="深渊之门", action_contains="做《深渊之门》"),
        _find_point(points, title="玛格汉岗哨", action_contains="接《玛格汉》"),
        _find_point(points, title="沙纳尔废墟·金属箱", action_contains="做《叛徒》"),
        _find_point(points, action_contains="系统飞行：猎鹰岗哨 → 萨尔玛"),
        _find_point(points, title="猎鹰岗哨", action_contains="交《点燃灯塔》"),
        len(points) - 1,
    ]
    groups = _contiguous_groups(
        group_ends,
        [
            ("黑暗之门 → 萨尔玛 → 魔火峡谷", (25.0, 18.0, 34.0)),
            ("机甲残骸 → 阻断援军 → 两轮轰炸", (27.0, 20.0, 36.0)),
            ("断背岗哨 → 军械库 → 塞斯高", (30.0, 22.0, 40.0)),
            ("血之复仇 → 暗眼格里洛克 → 炉石萨尔玛", (25.0, 18.0, 34.0)),
            ("萨尔玛 → 矿洞短链", (25.0, 18.0, 34.0)),
            ("萨尔玛地下 → 铸魔营地 → 深渊之门", (25.0, 18.0, 34.0)),
            ("刺客 → 玛格汉岗哨", (29.0, 21.0, 40.0)),
            ("猎鹰岗哨 → 阿苟纳 → 大裂隙 → 沙纳尔", (35.0, 26.0, 44.0)),
            ("沙纳尔后半 → 猎鹰岗哨回交", (27.0, 20.0, 36.0)),
            ("猎鹰岗哨后续 → 阿苟纳 / 大裂隙第二趟", (40.0, 30.0, 52.0)),
            ("塞纳里奥哨站 → 赞加沼泽", (22.0, 16.0, 31.0)),
        ],
    )
    _semantic_groups(points, groups, task_presentations=migrated_presentations)

    route.update(
        {
            "order": 101,
            "title": "地狱火半岛 · DK专用加速路线",
            "displayName": "地狱火半岛（DK专用）",
            "sub": "黑暗之门起步，依次完成东部前线、断背/塞斯高、萨尔玛北线、猎鹰/塞纳里奥任务簇，最后直接进入赞加。",
            "badge": "炉石：萨尔玛\n预计总时间：330分钟（补回复仇链后的首跑前预算）",
            "timing": {"centerMinutes": 330.0, "rangeMinutes": [243.0, 436.0]},
            "footer": "塞纳里奥哨站接《塞纳里奥远征队》后直接越境赞加；下一张切换“赞加沼泽（DK专用）”。",
            "points": points,
            "stepGroups": groups,
            "defaultIndex": 0,
            "defaultGroupIndex": 0,
            "uiStandard": "semantic-hud-v45",
        }
    )
    return route


def build_zang(base: dict[str, Any]) -> dict[str, Any]:
    route = copy.deepcopy(base)

    # Deleting the Lisaao chain makes the early standalone visit unnecessary.
    # Keep the free breadcrumb turn-in and merge it into the later Count Ungula visit.
    route["points"][32][3] = ""
    route["points"][40][3] = (
        "观察者莉萨奥 → 交《观察者莉萨奥》、《沼泽中的伯爵》"
    )

    points, old_to_new = _filter_points(route, ZANG_DELETE)

    # Player-note cleanup: remove tracker-level repetition while keeping actual execution mechanics.
    darkcrest_escort = _find_point(points, title="暗泽村", action_contains="做《逃离暗泽村》")
    points[darkcrest_escort][5] = "《逃离暗泽村》：五号都接好任务后只跑一次护送即可。"
    water_outlet_note = _find_point(points, title="水域排水口")
    points[water_outlet_note][5] = "《抽水泵结构图》：到水下排水口完成调查；完成后直接在水中使用炉石，不游回岸边。"
    final_zabrajin = _find_point(points, title="萨布拉金", action_contains="若已完成：苏尔加亚")
    points[final_zabrajin][5] = ""

    # Optimization 1: do the fourth Restore Balance pump before the water outlet. This removes the
    # stale post-pump assumption that the party is still in Zabra'jin and makes the hearth useful.
    fourth_pump = _find_point(points, title="沼光湖抽水泵", action_contains="做《恢复平衡》")
    fourth_pump_point = points.pop(fourth_pump)
    water_outlet = _find_point(points, title="水域排水口")
    points.insert(water_outlet, fourth_pump_point)

    # Optimization 2: the deleted Feralfen/Sporegar package no longer justifies going north to
    # Terrorclaw, back south to Ungula/Lisaao, then north again. Put Terrorclaw on the natural
    # northbound line after Lisaao and before the northern boss loop.
    terrorclaw = _find_point(points, title="恐爪刷新点")
    terrorclaw_point = points.pop(terrorclaw)
    lisaao = _find_point(points, title="莉萨奥营地", action_contains="交《观察者莉萨奥》")
    points.insert(lisaao + 1, terrorclaw_point)

    g1a_end = _find_point(points, title="塞纳里奥庇护所", action_contains="接《恢复平衡》")
    g1b_end = _find_point(points, title="暗泽湖抽水泵", start=g1a_end + 1)
    g2_end = _find_point(points, title="观察者杰哈恩", start=g1b_end + 1)
    g3_end = _find_point(points, title="萨布拉金", action_contains="交《下钩钓鱼》", start=g2_end + 1)
    g4_end = _find_point(points, title="沼泽鼠岗哨", action_contains="接《对方的尊重》", start=g3_end + 1)
    g5_end = _find_point(points, title="萨布拉金", action_contains="使用炉石：萨布拉金", start=g4_end + 1)
    g6_end = _find_point(points, title="恐爪刷新点", start=g5_end + 1)
    g7_end = _find_point(points, title="多头蛇之王刷新点", start=g6_end + 1)
    g8_end = _find_point(points, title="萨布拉金", action_contains="接《你死我活》", start=g7_end + 1)
    group_ends = [g1a_end, g1b_end, g2_end, g3_end, g4_end, g5_end, g6_end, g7_end, g8_end, len(points) - 1]
    groups = _contiguous_groups(
        group_ends,
        [
            ("塞纳里奥庇护所 → 暗泽村 → 回庇护所", (8.0, 6.0, 11.0)),
            ("沼泽鼠岗哨 → 东部湖区 → 暗泽湖第一泵", (4.0, 3.0, 6.0)),
            ("环礁湖 → 毒蛇湖 → 观察者杰哈恩", (28.0, 22.0, 35.0)),
            ("萨布拉金 → 沼光湖第四泵 → 水域排水口 → 炉石萨布拉金", (22.0, 17.0, 29.0)),
            ("塞纳里奥庇护所 → 沼泽鼠岗哨", (12.0, 10.0, 16.0)),
            ("黑钉 → 沼泽鼠岗哨 → 炉石萨布拉金", (12.0, 9.0, 17.0)),
            ("萨布拉金 → 昂古拉 → 莉萨奥 → 恐爪", (20.0, 15.0, 28.0)),
            ("穆玛基 → 鱼人笼 → 格罗阿克 → 多头蛇之王", (28.0, 21.0, 37.0)),
            ("炉石萨布拉金 → 战斗迫近 → 回萨布拉金", (18.0, 13.0, 25.0)),
            ("匕潭失落者 → 安葛洛什 → 炉石萨布拉金", (22.0, 16.0, 30.0)),
        ],
    )
    _semantic_groups(points, groups)

    route.update(
        {
            "order": 102,
            "title": "赞加沼泽 · DK专用加速路线",
            "displayName": "赞加沼泽（DK专用）",
            "sub": "塞纳里奥东部任务簇 → 萨布拉金 → 西部高效率任务 → 安葛洛什收尾，之后直接进入纳格兰原路线。",
            "badge": "炉石：萨布拉金\n预计总时间：174分钟（重排后首跑前预算）",
            "timing": {"centerMinutes": 174.0, "rangeMinutes": [133.0, 232.0]},
            "footer": "若进入纳格兰前经验明显不足：优先补《蛮沼之灵》→《灵魂之盟？》，再补《亮顶蘑菇》；否则直接切换原“纳格兰”路线。",
            "points": points,
            "stepGroups": groups,
            "defaultIndex": 0,
            "defaultGroupIndex": 0,
            "uiStandard": "semantic-hud-v45",
        }
    )
    return route


def main() -> None:
    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    if "hellfire" not in routes or "zang" not in routes:
        raise SystemExit("base Hellfire/Zangarmarsh routes missing")

    # Always rebuild variants from the untouched base routes, never from a prior DK derivative.
    routes["hellfire_dk"] = build_hellfire(routes["hellfire"])
    routes["zang_dk"] = build_zang(routes["zang"])
    raise RuntimeError("RETIRED: direct workbench-routes.json writes are disabled; edit Route Profiles and publish through the Route Lifecycle pipeline")

    print(
        json.dumps(
            {
                "hellfire_dk": {
                    "points": len(routes["hellfire_dk"]["points"]),
                    "groups": len(routes["hellfire_dk"]["stepGroups"]),
                    "timing": routes["hellfire_dk"]["timing"],
                },
                "zang_dk": {
                    "points": len(routes["zang_dk"]["points"]),
                    "groups": len(routes["zang_dk"]["stepGroups"]),
                    "timing": routes["zang_dk"]["timing"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
