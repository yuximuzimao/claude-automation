from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
OUT = ROOT / "data/route-atlas/sholazar-inserted-route.json"
REPORT = ROOT / "docs/analysis/2026-08-26-sholazar-inserted-route.md"

# (id, title, completed quest ids in real completion order, Spatial Instances visited)
WINDOWS = [
    ("W01", "达拉然脚本入图→奈辛瓦里", [12521,12489], ["dalaran_krasus","wildgrowth_mangal","nesingwary_camp"]),
    ("W02", "飞行器引擎往返", [12522], ["nesingwary_camp","wildgrowth_engine"]),
    ("W03", "挖掘场第一次进场", [12523,12524,12624,12688], ["swindlegrins_dig","nesingwary_camp"]),
    ("W04", "挖掘场第二次进场→狩猎开锁", [12525,12589], ["swindlegrins_north_platform","nesingwary_camp"]),
    ("W05", "犀牛/恶刃豹初阶狩猎", [12520,12549], ["nesingwary_west_hunt","nesingwary_camp"]),
    ("W06", "诺兹隆→中央任务簇→足迹", [12526,12543,12544,12550,12551,12634,12804], ["nozzlerust_bones","central_wildgrowth","bittertide_tracks","nesingwary_camp"]),
    ("W07", "沙蕨→法鲁恩→杉苟→炉石", [12644,12560,12556,12558,12592], ["seabreach_sandfern","farunn_range","shango_range","nesingwary_camp"]),
    ("W08", "鳄鱼伏击→河流之心→匹奇→狂心岭", [12651,12696,12699,12671,12528], ["seabreach_fallen_log","rivers_heart","pitch_spawn","frenzyheart_hill"]),
    ("W09", "硬皮猩猩一次进场", [12529,12530], ["frenzyheart_hill","hardknuckle_thicket"]),
    ("W10", "蓝玉虫巢一次进场→抓鸡", [12533,12534,12532], ["sapphire_hive","frenzyheart_hill"]),
    ("W11", "狂心岭南部一次进场", [12531,12535], ["frenzyheart_south","frenzyheart_hill"]),
    ("W12", "鳄鱼脚本→雾语村一次进场", [12536,12537,12538], ["croc_transport","mistwhisper_village"]),
    ("W13", "炉石奈辛瓦里关闭旧线→狂心岭", [12569,12645,12539], ["nesingwary_camp","frenzyheart_hill"]),
    ("W14", "受伤神谕者→雨声树屋", [12540,12570], ["injured_oracle","rainspeaker_canopy"]),
    ("W15", "雨声树屋蛇/亮闪闪外圈", [12571,12572], ["rainspeaker_outer","rainspeaker_canopy"]),
    ("W16", "议和→河流之心→雾语村", [12573,12654,12574], ["vekjik_peace","rivers_heart","rainspeaker_canopy","mistwhisper_village"]),
    ("W17", "多里安第一层：始祖龙+苦潮多头蛇外圈", [12595,12603,12605,12683], ["dorian_camp","burning_nest","bittertide_hydra"]),
    ("W18", "猛犸就近驯服立即送回", [12607], ["mammoth_range","dorian_camp"]),
    ("W19", "矛生+母龙+大鹏北部大圈", [12614,12658,12681,12575,12576,12577], ["spearborn","slivina_nest","roc_range","dorian_camp","mistwhisper_village","rainspeaker_canopy"]),
    ("W20", "苔行村东部大圈", [12578,12579,12580,12691], ["mosswalker_village","mosswalker_east","makers_overlook"]),
    ("W21", "阿图里斯→神谕者→雨声树屋", [12581,12689,12695], ["artruis_cave","rainspeaker_canopy"]),
]


def deps(task: dict[str, Any]) -> set[int]:
    out = {int(x) for x in (task.get("pre_all") or [])}
    out.update(int(x) for x in (task.get("parent_active") or []))
    one = [int(x) for x in (task.get("pre_any") or [])]
    if len(one) == 1:
        out.add(one[0])
    return out


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = {int(t["quest_id"]): t for t in foundation.get("tasks", [])}
    formal = {int(x) for x in foundation.get("formal_task_ids", [])}
    flat = [q for _,_,ids,_ in WINDOWS for q in ids]
    missing = sorted(formal-set(flat)); extra = sorted(set(flat)-formal)
    dup = sorted({q for q in flat if flat.count(q)>1})
    pos = {q:(wi,ti) for wi,(_,_,ids,_) in enumerate(WINDOWS) for ti,q in enumerate(ids)}
    bad=[]
    for q in flat:
        for d in sorted(deps(tasks[q])):
            if d in pos and pos[d] > pos[q]:
                bad.append({"quest_id":q,"dependency_id":d,"quest_pos":pos[q],"dependency_pos":pos[d]})
    windows=[{"id":wid,"title":title,"complete_task_ids":ids,"spatial_instances":spatial} for wid,title,ids,spatial in WINDOWS]
    payload={
        "status":"task_cluster_insertion_complete_pending_whole_map_merge_audit",
        "formal_task_count":len(formal),"window_count":len(windows),
        "coverage_missing":missing,"coverage_extra":extra,"coverage_duplicates":dup,
        "dependency_order_violation_count":len(bad),"dependency_order_violations":bad,
        "windows":windows,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# 索拉查盆地任务簇插入完成稿（发布前）","",f"- 正式任务{len(formal)}；窗口{len(windows)}；missing={missing}；extra={extra}；duplicates={dup}；dependency violations={len(bad)}。","- 下一步固定做整图Spatial Instance合并审查，未审完不进入Route Atlas发布。",""]
    for w in windows:
        lines += [f"- {w['id']}｜{w['title']}｜Complete={w['complete_task_ids']}｜Spatial={w['spatial_instances']}"]
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"formal":len(formal),"windows":len(windows),"missing":missing,"extra":extra,"duplicates":dup,"dependency_order_violations":len(bad)},ensure_ascii=False,indent=2))
    if missing or extra or dup or bad:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
