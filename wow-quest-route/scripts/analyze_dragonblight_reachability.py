from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT_JSON = ROOT / "data/route-atlas/dragonblight-route-reachability.json"
OUT_MD = ROOT / "docs/archive/analysis/2026-08-16-dragonblight-reachability-audit.md"

# Entry state inherited from the completed Borean from-zero route.
# 11930 is completed at the Dragonblight border; 12117 is carried active until Moa'ki Harbor.
ENTRY_COMPLETED = {11930}
ENTRY_ACTIVE = {12117}


def included_world(task: dict[str, Any]) -> bool:
    return (
        task.get("is_primary_candidate")
        and str(task.get("scope_status", "")).startswith("include_")
        and not task.get("is_dungeon")
    )


def all_start_coords(task: dict[str, Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for entity in task.get("start_entities") or []:
        rep = (entity.get("representative_by_zone") or {}).get("65")
        if rep and isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            out.append((round(float(rep["x"]), 2), round(float(rep["y"]), 2)))
    return out


def all_finish_coords(task: dict[str, Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for entity in task.get("finish_entities") or []:
        rep = (entity.get("representative_by_zone") or {}).get("65")
        if rep and isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            out.append((round(float(rep["x"]), 2), round(float(rep["y"]), 2)))
    return out


def objective_coords(task: dict[str, Any]) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    seen: set[tuple[float, float, str]] = set()
    for objective in task.get("objectives") or []:
        for source in objective.get("sources") or []:
            rep = (source.get("representative_by_zone") or {}).get("65")
            if not rep:
                continue
            x, y = rep.get("x"), rep.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue
            row = (round(float(x), 2), round(float(y), 2), str(source.get("name") or source.get("entity_id") or "目标"))
            if row not in seen:
                seen.add(row)
                out.append(row)
    for extra in task.get("extra_objectives") or []:
        rep = (extra.get("coordinates_by_zone") or {}).get("65")
        if isinstance(rep, dict):
            x, y = rep.get("x"), rep.get("y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                row = (round(float(x), 2), round(float(y), 2), str(extra.get("name") or "脚本目标"))
                if row not in seen:
                    seen.add(row)
                    out.append(row)
    return out


def prereq_state(task: dict[str, Any], reachable: set[int], available_ids: set[int]) -> tuple[bool, list[int]]:
    satisfied = reachable | ENTRY_COMPLETED | ENTRY_ACTIVE
    blockers: list[int] = []
    for qid in task.get("pre_all") or []:
        if qid not in satisfied:
            blockers.append(int(qid))
    pre_any = [int(qid) for qid in (task.get("pre_any") or [])]
    if pre_any and not any(qid in satisfied for qid in pre_any):
        blockers.extend(pre_any)
    # parent_active encodes an active-parent relationship. For route reachability, the parent
    # must at least be reachable; actual accept-before-complete ordering is handled later.
    for qid in task.get("parent_active") or []:
        if qid not in satisfied:
            blockers.append(int(qid))
    return not blockers, sorted(set(blockers))


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    by_id = {int(task["quest_id"]): task for task in tasks}
    candidate_ids = {qid for qid, task in by_id.items() if included_world(task)}

    # 12117 is already active on entry even though its accept point is in Borean.
    reachable: set[int] = set(ENTRY_ACTIVE & candidate_ids)
    changed = True
    while changed:
        changed = False
        for qid in sorted(candidate_ids - reachable):
            task = by_id[qid]
            ok, _ = prereq_state(task, reachable, candidate_ids)
            if not ok:
                continue
            # A normal quest needs a Dragonblight start entity. Item-start quests are allowed
            # to be reachable because their trigger can be produced in-zone by combat/objectives.
            has_local_start = bool(all_start_coords(task))
            item_start = bool(task.get("item_start_ids"))
            structural = task.get("scope_status") == "include_structural_zero_xp_prerequisite"
            if has_local_start or item_start or structural:
                reachable.add(qid)
                changed = True

    rows = []
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        ok, blockers = prereq_state(task, reachable, candidate_ids)
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "reachable_from_borean_axis": qid in reachable,
            "blocking_prereq_ids": [] if qid in reachable else blockers,
            "blocking_prereq_names": [by_id.get(dep, {}).get("name", str(dep)) for dep in blockers],
            "scope_status": task.get("scope_status"),
            "entry_axis_relevance": task.get("entry_axis_relevance"),
            "pre_all": task.get("pre_all") or [],
            "pre_any": task.get("pre_any") or [],
            "parent_active": task.get("parent_active") or [],
            "start_coords": all_start_coords(task),
            "finish_coords": all_finish_coords(task),
            "objective_coords": objective_coords(task),
            "note_decision": (task.get("final_note_review") or {}).get("decision"),
        })

    unreachable = [row for row in rows if not row["reachable_from_borean_axis"]]
    result = {
        "status": "pre_insertion_reachability_filter",
        "entry_completed": sorted(ENTRY_COMPLETED),
        "entry_active": sorted(ENTRY_ACTIVE),
        "candidate_world_count": len(candidate_ids),
        "reachable_count": len(reachable),
        "unreachable_count": len(unreachable),
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 龙骨荒野 · 北风入口前置可达性审计",
        "",
        "- 目的：在真正插任务前，排除只能由另一张地图入图链解锁、或被废弃/替代前置卡死的后续任务。",
        "- 入口状态：11930《横贯冰原》已在边界完成；12117《前往莫亚基港口》作为北风携带任务处于活动状态。",
        f"- 当前世界候选：{len(candidate_ids)}；从北风轴可达：{len(reachable)}；不可达：{len(unreachable)}。",
        "- 本文件只判定“是否可能接到”，不决定任务先后、炉石或路线几何。",
        "",
        "## 不可达任务",
        "",
    ]
    if unreachable:
        for row in unreachable:
            blockers = ", ".join(f"{qid}《{name}》" for qid, name in zip(row["blocking_prereq_ids"], row["blocking_prereq_names"])) or "无本地可用起点"
            lines.append(f"- {row['quest_id']}《{row['name']}》：阻塞={blockers}")
    else:
        lines.append("- 无")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "world_candidates": len(candidate_ids),
        "reachable": len(reachable),
        "unreachable": len(unreachable),
        "out_json": str(OUT_JSON.relative_to(ROOT)),
        "out_md": str(OUT_MD.relative_to(ROOT)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
