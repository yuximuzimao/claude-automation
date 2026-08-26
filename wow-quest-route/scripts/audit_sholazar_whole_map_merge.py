from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "data/route-atlas/sholazar-inserted-route.json"
OUT = ROOT / "data/route-atlas/sholazar-whole-map-merge-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-26-sholazar-whole-map-merge-audit.md"

DECISIONS = {
    "nesingwary_camp": ("forced_hub_chain", "多条奈辛瓦里任务链必须回营地交前一环再解锁下一环；W13还承担已优化的延迟交12569/12645并接12595。"),
    "frenzyheart_hill": ("forced_hub_chain", "12528→12529/30→12533/34→12532→12531/35→12536逐层解锁，不能一次进场预做。"),
    "rivers_heart": ("optimized_delayed_turn", "W08首次开Hub并做维克/塔玛拉；12654故意延后到W16做12573时顺交，避免从匹奇区域专门折返。"),
    "mistwhisper_village": ("forced_phase_and_objective_return", "W12是狂心阶段脚本到村；W16切神谕后才解锁12575/76；W19必须做完北部目标后回来交。"),
    "rainspeaker_canopy": ("forced_hub_chain", "12570后分层解锁12571/72→12573→12574，之后12577和12695又分别从北部/阿图里斯链回交。"),
    "dorian_camp": ("forced_internal_returns_merge_player_step", "12603完成后才开12607/58/81；12607送猛犸回营后才开12614。三次回营都是真前置，但最终前端合并为一个连续多里安任务块。"),
}

ALIAS_DECISIONS = [
    {
        "family": "swindlegrins_dig",
        "windows": ["W03", "W04"],
        "verdict": "forced_prerequisite_repeat",
        "reason": "12525《工头斯温迪格林》只有12524回营交付后才能接，所以挖掘场必须二次进入；第一次已把零件、15杀、戒指、护送全部合并。",
    },
    {
        "family": "final_east_campaign",
        "windows": ["W20", "W21"],
        "verdict": "merge_player_step_continuous_campaign",
        "reason": "苔行东部服务完必须回莫乌德交12579才能接12581；随后立即去阿图里斯，不离开东部任务区。最终玩家步骤合并展示，不能表现成两次独立远征。",
    },
]


def main() -> None:
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    windows = route.get("windows") or []
    seen: dict[str, list[str]] = defaultdict(list)
    for w in windows:
        for instance in w.get("spatial_instances") or []:
            seen[str(instance)].append(str(w["id"]))
    repeated = {k:v for k,v in seen.items() if len(v)>1}
    unresolved = sorted(k for k in repeated if k not in DECISIONS)
    reviews=[]
    for instance, ids in sorted(repeated.items()):
        verdict, reason = DECISIONS.get(instance, ("UNRESOLVED", ""))
        reviews.append({"spatial_instance":instance,"windows":ids,"verdict":verdict,"reason":reason})
    reviews.extend(ALIAS_DECISIONS)
    harmful = [r for r in reviews if r.get("verdict") in {"harmful_split","UNRESOLVED"}]
    merge_player = [r for r in reviews if "merge_player_step" in str(r.get("verdict"))]
    payload={
        "status":"pass" if not unresolved and not harmful else "fail",
        "repeated_exact_instance_count":len(repeated),
        "unresolved_exact_instances":unresolved,
        "harmful_split_count":len(harmful),
        "player_step_merge_count":len(merge_player),
        "reviews":reviews,
        "post_insertion_changes":[
            "12683《燃烧的唾液》已从错误的猛犸合并回路回插到W17始祖龙第一外圈。",
            "12607《驯服猛犸象》改为抓最近中立猛犸后立即送回，不携带慢速载具绕路。",
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "# 索拉查盆地整图任务簇合并审查","",
        f"- exact重复Spatial Instance：{len(repeated)}；未解释={unresolved}；harmful split={len(harmful)}。",
        f"- 最终玩家步骤需要主动合并的连续任务块：{len(merge_player)}。","",
    ]
    for r in reviews:
        lines.append(f"- {r.get('spatial_instance') or r.get('family')}｜{r['windows']}｜{r['verdict']}｜{r['reason']}")
    lines += ["","## 本轮实际回插修正","","- 多里安原候选把12607猛犸和12683多头蛇硬合并，机制核验后否决。","- 12683改入W17始祖龙/幼崽外圈；12607单独就近抓猛犸立即送回，再开12614母龙。"]
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"status":payload["status"],"repeated_exact_instances":len(repeated),"unresolved":unresolved,"harmful_split_count":len(harmful),"player_step_merges":len(merge_player)},ensure_ascii=False,indent=2))
    if payload["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
