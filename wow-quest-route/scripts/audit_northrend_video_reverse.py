from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ROOT = ROOT.parent / ".ai-bridge" / "wow-video-extraction"
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OUT = ROOT / "data/route-atlas/northrend-video-reverse-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-19-northrend-video-reverse-audit.md"

SPECS = {
    "borean": {
        "name": "北风苔原",
        "zone_id": 3537,
        "episodes": list(range(34, 40)),
        "foundation": "data/route-atlas/borean-tundra-task-foundation.json",
    },
    "dragonblight": {
        "name": "龙骨荒野",
        "zone_id": 65,
        "episodes": list(range(40, 43)),
        "foundation": "data/route-atlas/dragonblight-task-foundation.json",
    },
    "grizzly": {
        "name": "灰熊丘陵",
        "zone_id": 394,
        "episodes": list(range(47, 52)),
        "foundation": "data/route-atlas/grizzly-hills-task-foundation.json",
    },
    "zuldrak": {
        "name": "祖达克",
        "zone_id": 66,
        "episodes": [52, 53],
        "foundation": "data/route-atlas/zuldrak-task-foundation.json",
    },
}

QUOTE_RE = re.compile(r"《([^》]+)》")
COMPLETE_ACTIONS = {"complete", "complete_and_accept_next", "object_trigger_active_then_complete"}

# Whole-map manual resolutions for current adjacent-order alarms. These are deliberately keyed by
# task names so any newly introduced reversal remains unresolved and blocks freeze until reviewed.
MANUAL_RESOLUTIONS = {
    "borean": {
        ("情势扭转", "决战奈辛瓦里"): "keep_current: video crosses a different Alliance map progression; current Horde route closes Nessingwary before the later Kaskala chain and does not create a shared local detour.",
        ("先祖的回归", "别让他们逃了！"): "keep_current: both Coldrock chains are active in the same local loop; their turn-in order differs but current route completes both without an extra revisit.",
        ("敌人的耳环", "帮助弱小"): "keep_current: Help the Weak is shared/fast and is turned in immediately; Earrings remains a background personal-drop task to avoid dedicated five-box farming.",
        ("调查", "监视裂谷：悬崖异常"): "keep_current: the rift task is already available on Amber Ledge arrival while Investigation unlocks after the jailbreak return; the current order follows availability and the same hub cycle.",
        ("重铸钥匙", "监视裂谷：峭壁断层"): "keep_current: the cliff-fault objective is completed on the outbound local pass; Reforging the Key unlocks later through the interrogation/time-race chain at the same hub.",
        ("监视裂谷：冬鳞洞穴", "侦查虫孔"): "keep_current: these belong to separate Taunka/Winterfin phases; video episode order is not a local adjacency claim. Current route carries the rift quest through the north loop and uses the opened flight network for its final turn-in.",
    },
    "dragonblight": {
        ("搜索因度雷村", "不要浪费"): "keep_current: video begins this section already on the Indu'le line. The Horde route from Agmar first reaches Moa'ki to unlock Don't Waste and the Kalu'ak chain, then threads back through Indu'le while those tasks are active; no duplicate standalone Indu'le revisit is introduced.",
        ("图尔凯的螃蟹陷阱", "长者玛纳洛"): "keep_current: both are accepted from the same Moa'ki visit; current route advances Mana'loa/Indu'le before sweeping the southern coast so crab traps are collected along the coast loop instead of forcing an early shoreline return.",
        ("魔网能量线的终端", "海洋女神"): "keep_current: the ley-line quest stays active while the coastal Ocean Goddess chain is closed, then is turned after the Moa'ki-to-Agmar flight; this batches the return transport rather than adding a separate Agmar trip.",
        ("向德弗雷斯塔兹领主报到", "红玉巨龙圣地的命运"): "keep_current: both resolve inside Wyrmrest/Ruby chain state; the video Alliance unlock order differs, while the current route turns the Ruby Brooch as soon as it is obtained and immediately continues the same tower/hub chain.",
    },
    "grizzly": {
        ("解读象形文字", "清理天灾"): "keep_current: both lie on the same westward Drakuru/Forgotten-depths sweep; current route takes the nearby mummified-crusader branch before the first brazier with no later revisit.",
        ("蘑菇汤！", "古树精华宝石"): "keep_current: Mushroom Soup is collected as a background task while the route continues east with the Drakuru gem chain; its delayed turn-in avoids returning to Granite Springs solely for the soup.",
        ("灰尘之声", "跟我的小朋友打招呼"): "keep_current: both are long-carried tasks whose turn-in order reflects different endpoints; the route hands Little Friend at Harkor when first entering the northeast, while Dust Voice waits for the later Drakil'jin spatial instance.",
        ("等肉下锅", "心灵的创伤"): "keep_current: Meat for the Pot is intentionally background-collected through later northeast/giant terrain; Healing with Herbs closes earlier when its local targets finish, avoiding dedicated meat farming.",
        ("金亚拉克的末日", "破损的日记"): "keep_current: the diary is collected/turned during the earlier Thor Modan pass; Jin'arrak is a later Harkor/Drakil'jin chain. Video's Alliance macro traversal reaches these chains in the opposite order.",
        ("攻破防线", "卢娜的要求"): "keep_current: Luna is closed before the northern giant chain because it is already available on the route into Onu'va; Break Through is a later strict giant-chain continuation, so swapping them would delay an already-open local loop.",
        ("……我们没有能源", "可能的关联"): "keep_current: Possible Link is an earlier Vordrassil/Conquest Hold chain and is intentionally closed before the late Dun Argol golem chain. Video Alliance hub progression unlocks the counterpart later.",
        ("终获解救", "沃达希尔的种子"): "keep_current: Vordrassil Seeds is completed in the mid-map Vordrassil pass and immediately unlocks the bear-god continuation; Free at Last is the terminal northern giant-chain task and cannot justify delaying the earlier tree pass.",
    },
    "zuldrak": {
        ("风暴将至", "圣光不能为我复仇"): "keep_current: Vargul Revenge is completed beside Gork during the same missing-crusader sweep, so turning it in immediately costs no revisit. Reproducing the video completion order would require carrying it away from its local turn-in and returning later.",
        ("希姆埃巴的祝福", "银色北伐军的降落伞"): "keep_current: Zim'Abwa requires personal Drakkari Offerings. The five-box route keeps this as background accumulation through the southern Drakkari loops and closes it on the final south return instead of forcing a dedicated early personal-drop farm.",
        ("银色北伐军的降落伞", "潜入沃尔塔鲁斯"): "keep_current: after the Gymer material loop the route is already back at Ebon Watch with Infiltrating Voltarus unlocked. Closing the phased Ebon chain before the one-way east transition avoids the video's later Ebon revisit after Argent Stand.",
        ("给斯塔哈默中士的新命令", "实验室的学徒"): "keep_current: both orders are dependency-legal, but the current Argent→Heb'Valok→spirits→Heb'Valok→Sseratus→bat→Heb'Valok→Argent loop is about 76.3 map-percent versus about 84.3 for the video-shaped Sseratus-first alternative using the same route anchors.",
        ("温暖的篝火", "扔手雷"): "keep_current: Throwing Down is turned in early specifically to unlock Cocooned, allowing Cocooned and One of a Kind? rescue targets to share one rescue pass. Creature Comforts remains a background wood collection and is turned later near the mushroom/basilisk return, avoiding a dedicated Drak'Jin wood loop.",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def formal_rows(spec: dict[str, Any]) -> tuple[set[int], dict[int, dict[str, Any]]]:
    data = load_json(ROOT / spec["foundation"])
    tasks = {int(t["quest_id"]): t for t in data.get("tasks", [])}
    if data.get("formal_task_ids"):
        ids = {int(x) for x in data["formal_task_ids"]}
        return ids, tasks
    ids: set[int] = set()
    for qid, task in tasks.items():
        status = str(task.get("scope_status") or "")
        if not status.startswith("include_"):
            continue
        if task.get("is_dungeon") or task.get("is_raid_flagged"):
            continue
        ids.add(qid)
    return ids, tasks


def route_positions(route: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], set[str]]:
    first: dict[str, int] = {}
    explicit_turnin: dict[str, int] = {}
    names: set[str] = set()
    for index, point in enumerate(route.get("points", []), 1):
        text = str(point[3]) if len(point) > 3 else ""
        for name in QUOTE_RE.findall(text):
            names.add(name)
            first.setdefault(name, index)
            if any(token in text for token in (f"交《{name}》", f"交付《{name}》", f"完成《{name}》", f"回交《{name}》")):
                explicit_turnin[name] = index
    return first, explicit_turnin, names


def video_events(episodes: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seq = 0
    for episode in episodes:
        data = load_json(VIDEO_ROOT / f"episode-{episode}-events.json")
        for event in data.get("events", []):
            row = dict(event)
            row["episode"] = episode
            row["sequence"] = seq
            rows.append(row)
            seq += 1
    return rows


def classify_video_only(
    qid: int | None,
    name: str,
    zone_id: int,
    formal_ids: set[int],
    foundation_tasks: dict[int, dict[str, Any]],
    universe_by_id: dict[int, dict[str, Any]],
    universe_by_name: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(qid, int) and qid in formal_ids:
        return {"class": "formal_candidate_missing_from_route", "matched_quest_id": qid}
    same_name_formal = [t for t in universe_by_name.get(name, []) if int(t["quest_id"]) in formal_ids]
    if same_name_formal:
        return {
            "class": "formal_counterpart_missing_from_route",
            "matched_quest_ids": [int(t["quest_id"]) for t in same_name_formal],
        }
    if isinstance(qid, int) and qid in foundation_tasks:
        task = foundation_tasks[qid]
        return {
            "class": "expected_not_in_current_route_scope",
            "scope_status": task.get("scope_status"),
            "scope_reasons": task.get("scope_reasons") or [],
        }
    if isinstance(qid, int) and qid in universe_by_id:
        task = universe_by_id[qid]
        return {
            "class": "video_faction_or_other_zone_only",
            "assigned_zone_id": task.get("assigned_zone_id"),
            "race_allowed": task.get("race_allowed"),
            "npc_faction_allowed": task.get("npc_faction_allowed"),
            "is_dungeon": task.get("is_dungeon"),
            "is_repeatable": task.get("is_repeatable"),
        }
    same_zone = [t for t in universe_by_name.get(name, []) if t.get("assigned_zone_id") == zone_id]
    if same_zone:
        return {
            "class": "same_name_zone_variant_not_formal",
            "matched_quest_ids": [int(t["quest_id"]) for t in same_zone],
        }
    return {"class": "video_only_unmapped"}


def audit_map(
    key: str,
    spec: dict[str, Any],
    routes: dict[str, Any],
    universe_by_id: dict[int, dict[str, Any]],
    universe_by_name: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    formal_ids, foundation_tasks = formal_rows(spec)
    formal_names = {foundation_tasks[qid].get("name") for qid in formal_ids if qid in foundation_tasks}
    events = video_events(spec["episodes"])
    video_task_rows: dict[tuple[int | None, str], dict[str, Any]] = {}
    video_complete_pos: dict[str, int] = {}
    video_first_pos: dict[str, int] = {}
    for event in events:
        name = event.get("quest_name")
        if not name:
            continue
        qid = event.get("quest_id")
        key2 = (int(qid) if isinstance(qid, int) else None, str(name))
        video_task_rows.setdefault(key2, {"quest_id": key2[0], "name": str(name), "episodes": []})
        if event["episode"] not in video_task_rows[key2]["episodes"]:
            video_task_rows[key2]["episodes"].append(event["episode"])
        video_first_pos.setdefault(str(name), int(event["sequence"]))
        if str(event.get("action")) in COMPLETE_ACTIONS:
            video_complete_pos[str(name)] = int(event["sequence"])

    route = routes.get(key)
    if route is None or spec.get("pre_route_only"):
        route_first: dict[str, int] = {}
        route_turnin: dict[str, int] = {}
        route_names: set[str] = set()
    else:
        route_first, route_turnin, route_names = route_positions(route)

    video_only: list[dict[str, Any]] = []
    for (qid, name), row in video_task_rows.items():
        if name in route_names:
            continue
        classified = classify_video_only(qid, name, spec["zone_id"], formal_ids, foundation_tasks, universe_by_id, universe_by_name)
        if spec.get("pre_route_only") and classified["class"] in {"formal_candidate_missing_from_route", "formal_counterpart_missing_from_route"}:
            classified = {**classified, "class": "formal_candidate_seen_in_video_pre_route"}
        video_only.append({**row, **classified})

    common_completion = sorted(
        set(video_complete_pos) & set(route_turnin),
        key=lambda n: video_complete_pos[n],
    )
    inversions = 0
    compared_pairs = 0
    for i, a in enumerate(common_completion):
        for b in common_completion[i + 1 :]:
            if route_turnin[a] == route_turnin[b]:
                continue
            compared_pairs += 1
            if route_turnin[a] > route_turnin[b]:
                inversions += 1
    reversed_video_adjacencies = []
    manual_resolutions = MANUAL_RESOLUTIONS.get(key, {})
    for a, b in zip(common_completion, common_completion[1:]):
        if route_turnin[a] > route_turnin[b]:
            resolution = manual_resolutions.get((a, b))
            reversed_video_adjacencies.append({
                "video_first": a,
                "video_second": b,
                "route_turnin_point_first": route_turnin[a],
                "route_turnin_point_second": route_turnin[b],
                "manual_resolution": resolution,
                "manual_review_status": "resolved" if resolution else "unresolved",
            })

    critical_omissions = [
        row for row in video_only
        if row["class"] in {"formal_candidate_missing_from_route", "formal_counterpart_missing_from_route"}
    ]
    unresolved_reversals = [row for row in reversed_video_adjacencies if row["manual_review_status"] == "unresolved"]
    if spec.get("pre_route_only"):
        order_status = "not_applicable_pre_route"
    elif critical_omissions or unresolved_reversals:
        order_status = "manual_review_required"
    else:
        order_status = "pass_whole_map_video_reverse_review"

    result = {
        "map": spec["name"],
        "episodes": spec["episodes"],
        "formal_task_count": len(formal_ids),
        "formal_name_count": len({x for x in formal_names if x}),
        "video_distinct_task_count": len(video_task_rows),
        "route_distinct_task_name_count": len(route_names),
        "common_route_video_name_count": len(set(video_first_pos) & route_names),
        "common_explicit_completion_count": len(common_completion),
        "critical_video_omission_count": len(critical_omissions),
        "critical_video_omissions": critical_omissions,
        "video_only_class_counts": {},
        "video_only": sorted(video_only, key=lambda row: (min(row.get("episodes") or [999]), row.get("quest_id") or 999999)),
        "completion_pair_count": compared_pairs,
        "completion_order_inversion_count": inversions,
        "completion_order_inversion_ratio": round(inversions / compared_pairs, 4) if compared_pairs else None,
        "reversed_video_adjacencies": reversed_video_adjacencies,
        "unresolved_adjacent_reversal_count": len(unresolved_reversals),
        "route_order_review_status": order_status,
    }
    counts: dict[str, int] = {}
    for row in video_only:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    result["video_only_class_counts"] = dict(sorted(counts.items()))
    return result


def main() -> None:
    routes = load_json(ROUTES)
    universe = load_json(UNIVERSE)
    universe_by_id = {int(t["quest_id"]): t for t in universe.get("tasks", [])}
    universe_by_name: dict[str, list[dict[str, Any]]] = {}
    for task in universe.get("tasks", []):
        universe_by_name.setdefault(str(task.get("name") or ""), []).append(task)

    results = {key: audit_map(key, spec, routes, universe_by_id, universe_by_name) for key, spec in SPECS.items()}
    OUT.write_text(json.dumps({
        "status": "video_reverse_audit_generated_manual_order_review_required",
        "policy": "video is reference evidence only; filter faction/dungeon/mutual-exclusion before omission/order review; route freeze requires explicit whole-map review when video exists",
        "maps": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 诺森德视频反向路线审查（北风 / 龙骨 / 灰熊 / 祖达克）",
        "",
        "- 视频只做共同任务顺序对照和遗漏审计，不覆盖部落五开任务事实、互斥、副本边界或实跑结果。",
        "- 自动顺序比较只把视频明确完成与路线显式交付做对照；出现逆序是人工复查信号，不等于路线错误。",
        "- 祖达克52—53集已同时用于基础任务池预审和正式路线整图反向审查；任何未解释的新逆序都会重新阻塞冻结。",
        "",
    ]
    for key in SPECS:
        row = results[key]
        lines += [
            f"## {row['map']}", "",
            f"- 视频：{row['episodes']}；视频不同任务{row['video_distinct_task_count']}；当前路线任务名{row['route_distinct_task_name_count']}；共同任务名{row['common_route_video_name_count']}。",
            f"- 视频独有项分类：`{row['video_only_class_counts']}`。",
            f"- 可能属于正式池但路线缺失：{row['critical_video_omission_count']}。",
        ]
        if row["route_order_review_status"] != "not_applicable_pre_route":
            lines += [
                f"- 明确完成共同任务：{row['common_explicit_completion_count']}；可比较成对顺序{row['completion_pair_count']}；逆序{row['completion_order_inversion_count']}（仅报警）。",
                f"- 视频相邻共同任务在路线中反向：{len(row['reversed_video_adjacencies'])}组；未完成人工归因：{row['unresolved_adjacent_reversal_count']}组。",
                f"- 整图视频反向审查状态：`{row['route_order_review_status']}`。",
            ]
        if row["critical_video_omissions"]:
            lines.append("- **需立即核对的遗漏：**")
            for item in row["critical_video_omissions"]:
                lines.append(f"  - {item.get('quest_id')}《{item['name']}》：{item['class']}")
        if row["reversed_video_adjacencies"]:
            lines.append("- **相邻逆序候选：**")
            for item in row["reversed_video_adjacencies"]:
                resolution = item.get("manual_resolution") or "UNRESOLVED"
                lines.append(f"  - 视频 `{item['video_first']} → {item['video_second']}`；路线交付点 `{item['route_turnin_point_first']} → {item['route_turnin_point_second']}`；人工结论：{resolution}")
        lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: {
        "critical_omissions": value["critical_video_omission_count"],
        "common_completion": value["common_explicit_completion_count"],
        "adjacent_reversals": len(value["reversed_video_adjacencies"]),
        "status": value["route_order_review_status"],
    } for key, value in results.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
