from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie
from lib.route_atlas_exact import representative_point
from lib.route_atlas_special_tasks import materialize_manual_special_time
from scripts.build_zangarmarsh_task_profiles import travel_seconds

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
PROFILE_PATH = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
ATLAS_PATH = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
AUDIT_PATH = ROOT / "data" / "route-atlas" / "zangarmarsh-task-classification-audit.json"
OVERRIDES_PATH = ROOT / "data" / "route-atlas" / "zangarmarsh-task-overrides.json"
REPORT_PATH = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-task-classification-adversarial-audit.md"

PALADIN_MASK = 2
BLOOD_ELF_MASK = 512

ACTION_RULES = [
    (re.compile(r"护送"), "escort", "文本包含护送动作"),
    (re.compile(r"使用.*(调查|侦察|观察)|调查.*使用"), "scripted_use_explore", "文本包含使用物品+调查"),
    (re.compile(r"(搜寻|搜索|寻找).*(下落|踪迹|位置|入口|营地|目标)?"), "search_or_trigger", "文本包含搜索/寻找地点"),
    (re.compile(r"(使用|唤醒|激活|释放|召唤|摧毁|关闭|开启)"), "scripted_action", "文本包含脚本/使用动作"),
]

GENERIC_CONTAINER_WORDS = ("宝箱", "箱", "Chest", "Cache", "Crate", "Strongbox")


def seq(table: Any) -> list[Any]:
    if not isinstance(table, dict):
        return []
    return [table[k] for k in sorted(k for k in table if isinstance(k, int))]


def eligibility(raw: dict[Any, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    race_mask = raw.get(6)
    class_mask = raw.get(7)
    skill = raw.get(18)
    required_spell = raw.get(30)
    class_ok = not class_mask or bool(int(class_mask) & PALADIN_MASK)
    race_ok = not race_mask or bool(int(race_mask) & BLOOD_ELF_MASK)
    reasons = []
    if not class_ok:
        reasons.append(f"职业限制掩码={class_mask}，不包含圣骑士")
    if not race_ok:
        reasons.append(f"种族限制掩码={race_mask}，不包含血精灵")
    if skill:
        reasons.append(f"另有技能条件={seq(skill)}")
    if required_spell:
        reasons.append(f"另有法术条件={required_spell}")
    return {
        "required_race_mask": race_mask,
        "required_class_mask": class_mask,
        "required_skill": seq(skill),
        "required_spell": required_spell,
        "blood_elf_paladin_class_race_ok": class_ok and race_ok,
        "has_additional_skill_or_spell_condition": bool(skill or required_spell),
        "reasons": reasons,
    }


def unique_item_object_points(atlas_q: dict[str, Any], source_item_id: int) -> tuple[int, int]:
    all_points = []
    total_rows = 0
    for target in atlas_q.get("objective_targets") or []:
        if target.get("kind") != "item_object" or int(target.get("source_item_id") or 0) != source_item_id:
            continue
        pts = target.get("spawns") or []
        total_rows += len(pts)
        all_points.extend((round(float(p[0]), 3), round(float(p[1]), 3)) for p in pts)
    return total_rows, len(set(all_points))


def audit_quest(qid: int, profile: dict[str, Any], atlas_q: dict[str, Any], raw: dict[Any, Any] | None, questie: Any) -> dict[str, Any]:
    text = str(atlas_q.get("objective") or "")
    primary = profile.get("classification", {}).get("primary") or "other"
    effective = primary
    flags: list[str] = []
    notes: list[str] = []
    severity = "high"

    elig = eligibility(raw)
    if not elig["blood_elf_paladin_class_race_ok"]:
        flags.append("not_eligible_for_blood_elf_paladin")
        severity = "low"
    if elig["has_additional_skill_or_spell_condition"]:
        flags.append("additional_skill_or_spell_condition")
        severity = "low"

    if primary == "handoff":
        for pattern, suggested, reason in ACTION_RULES:
            if pattern.search(text):
                flags.append("handoff_has_non_handoff_action")
                effective = suggested
                notes.append(reason)
                severity = "low"
                break

    raw_kinds = profile.get("classification", {}).get("raw_objective_kinds", {})
    unsupported = [k for k in ("kill_credit", "spell", "reputation") if raw_kinds.get(k)]
    if unsupported:
        flags.append("structured_objective_not_in_cost_model")
        notes.append("Questie原始Objective包含当前耗时模型尚未展开的结构：" + ",".join(unsupported))
        severity = "low"

    if raw_kinds.get("item") and not profile.get("components"):
        flags.append("item_objective_without_resolved_source")
        effective = "special_unresolved"
        severity = "low"

    for comp in profile.get("components") or []:
        family = comp.get("family")
        key = str(comp.get("requirement_key") or "")
        item_id = int(key.split(":", 1)[1]) if key.startswith("item:") else None
        if family == "object_collect_multi" and item_id:
            raw_item = questie.items.get(item_id) or {}
            item_class = raw_item.get(12)
            total_rows, unique_points = unique_item_object_points(atlas_q, item_id)
            comp["spawn_points"] = {
                "raw_rows": total_rows,
                "unique_points": unique_points,
                "deduplicated": total_rows != unique_points,
            }
            if total_rows != unique_points:
                flags.append("duplicate_object_source_spawn_rows")
                notes.append(f"物品{item_id}多个Object来源复用了同一批坐标；刷新点数必须去重：{total_rows}→{unique_points}")
            source_names = [str(s.get("name") or "") for s in comp.get("sources") or []]
            generic = any(any(word in name for word in GENERIC_CONTAINER_WORDS) for name in source_names)
            if item_class == 7 or generic:
                flags.append("object_drop_is_not_proven_primary_quest_method")
                notes.append("Item→Object仅证明可能从该物体获得，不能证明它是任务正常主完成方式；贸易品/通用宝箱尤其危险。")
                effective = "material_or_alternative_source"
                severity = "low"
            if unique_points == 0:
                flags.append("no_local_object_spawn_points")
                severity = "low"

        if family == "mob_drop":
            if any(s.get("drop_rate_percent") is None for s in comp.get("sources") or []):
                flags.append("missing_drop_rate")
                severity = "low"
            if any(s.get("low_density_shortcut") for s in comp.get("sources") or []):
                notes.append("存在单点/稀有来源，只作为快捷策略，不作为基础耗时来源。")

        if comp.get("needed_count") == 1:
            numbers = [int(v) for v in re.findall(r"\d+", text)]
            if any(v > 1 for v in numbers) and comp.get("label") and str(comp.get("label")) not in text:
                flags.append("count_inference_may_have_defaulted_to_one")
                severity = "low"

    # Known structural corrections surfaced by the adversarial audit itself.
    if qid == 9718:
        effective = "scripted_use_explore"
    elif qid in (9771, 9876):
        effective = "search_or_trigger"
    elif qid == 10964:
        effective = "scripted_action"
    elif qid == 10994:
        effective = "special_unresolved"

    confidence = "high" if not flags else ("medium" if severity == "high" else "low")
    if not flags:
        confidence = "high"

    time_model_valid = confidence != "low" and elig["blood_elf_paladin_class_race_ok"] and not elig["has_additional_skill_or_spell_condition"]
    if effective in ("search_or_trigger", "scripted_use_explore", "scripted_action", "special_unresolved", "material_or_alternative_source"):
        time_model_valid = False

    return {
        "primary_raw": primary,
        "primary_effective": effective,
        "confidence": confidence,
        "review_required": confidence == "low",
        "risk_flags": sorted(set(flags)),
        "notes": notes,
        "eligibility": elig,
        "time_model_valid_for_global_optimizer": time_model_valid,
    }


def apply_component_overrides(profile: dict[str, Any], override: dict[str, Any]) -> None:
    component_overrides = override.get("component_overrides")
    if not isinstance(component_overrides, dict):
        return
    for component in profile.get("components") or []:
        if not isinstance(component, dict):
            continue
        patch = component_overrides.get(component.get("requirement_key"))
        if not isinstance(patch, dict):
            continue
        if patch.get("effective_family"):
            component["raw_family"] = component.get("family")
            component["family"] = patch["effective_family"]
        manual_point = patch.get("manual_point")
        if isinstance(manual_point, list) and len(manual_point) >= 2:
            point = [float(manual_point[0]), float(manual_point[1])]
            component["baseline_point"] = point
            baseline = component.get("baseline_source")
            if isinstance(baseline, dict):
                baseline["representative_point"] = point
                if patch.get("manual_name"):
                    baseline["name"] = patch["manual_name"]
            for source in component.get("sources") or []:
                if isinstance(source, dict):
                    source["representative_point"] = point
                    if patch.get("manual_name"):
                        source["name"] = patch["manual_name"]
        seconds = patch.get("estimated_objective_seconds")
        if isinstance(seconds, (int, float)):
            seconds = float(seconds)
            component["estimated_objective_seconds"] = seconds
            component["estimated_objective_seconds_lower"] = seconds
            component["estimated_objective_seconds_upper"] = seconds
            component["calculation"] = {
                "formula": "manual_component_override",
                "inputs": {"requirement_key": component.get("requirement_key")},
                "result": seconds,
                "unit": "seconds",
                "source": "manual_task_override",
                "quality": "manual_verified_mechanic",
            }
            component["time_model"] = "manual_component_override"

    route = profile.get("solo_time_estimate")
    if not isinstance(route, dict):
        return
    values = [c.get("estimated_objective_seconds") for c in profile.get("components") or []]
    if any(v is None for v in values):
        objective_total = None
    else:
        objective_total = sum(float(v) for v in values)
    travel = route.get("total_travel_seconds")
    route["objective_seconds"] = objective_total
    route["objective_seconds_lower"] = objective_total
    route["objective_seconds_upper"] = objective_total
    total = float(travel) + objective_total if isinstance(travel, (int, float)) and objective_total is not None else None
    route["estimated_total_seconds"] = total
    route["estimated_total_seconds_lower"] = total
    route["estimated_total_seconds_upper"] = total
    if isinstance(route.get("calculations"), dict):
        route["calculations"]["objective_total"] = {
            "formula": "sum(effective component seconds)",
            "inputs": {"component_seconds": values},
            "result": objective_total,
            "unit": "seconds",
            "source": "manual_component_override_materialization",
            "quality": "manual_verified_mechanic",
        }
        route["calculations"]["quest_total"] = {
            "formula": "total_travel_seconds + effective_objective_seconds",
            "inputs": {"total_travel_seconds": travel, "objective_seconds": objective_total},
            "result": total,
            "unit": "seconds",
            "source": "manual_component_override_materialization",
            "quality": "manual_verified_mechanic",
        }


def main() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    atlas = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    override_payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8")) if OVERRIDES_PATH.exists() else {"quests": {}}
    overrides = override_payload.get("quests", {})
    questie = load_questie(QUESTIE_ZIP)
    npc_by_id = {int(n["id"]): n for n in atlas.get("npcs", [])}
    audit_rows: dict[str, Any] = {}
    low_rows = []
    manual_resolved = 0

    for qid_text, profile in payload["quests"].items():
        qid = int(qid_text)
        row = audit_quest(qid, profile, atlas["quests"][qid_text], questie.quests.get(qid), questie)
        override = overrides.get(qid_text)
        if override:
            manual_resolved += 1
            row["auto_primary_effective"] = row["primary_effective"]
            row["primary_effective"] = override["effective_type"]
            row["confidence"] = "manual"
            row["review_required"] = False
            row["manual_override"] = True
            row["manual_notes"] = override.get("notes", [])
            route_policy = override.get("route_policy", "include")
            row["route_policy"] = route_policy
            # Only route-policy=include can enter the current open-world optimizer.
            # Conditional/excluded tasks remain fully described in the task layer but are not silently optimized.
            row["time_model_valid_for_global_optimizer"] = route_policy == "include"
        else:
            row["manual_override"] = False
            row["route_policy"] = "include"

        profile["classification_audit"] = row
        profile["classification"]["effective_primary"] = row["primary_effective"]
        profile["classification"]["confidence"] = row["confidence"]
        profile["classification"]["risk_flags"] = row["risk_flags"]
        profile["eligibility"] = row["eligibility"]
        profile["route_policy"] = row["route_policy"]
        profile["time_model_valid_for_global_optimizer"] = row["time_model_valid_for_global_optimizer"]
        if override:
            profile["manual_override"] = override
            apply_component_overrides(profile, override)
            if override.get("time_override"):
                time_cell = override["time_override"]
                profile["effective_time_estimate"] = {
                    "mode": "manual_fixed_service",
                    "objective_seconds": time_cell.get("result"),
                    "estimated_total_seconds": time_cell.get("result"),
                    "calculation": time_cell,
                    "source": "manual_override",
                }
            elif override.get("objective_time_override") and profile.get("solo_time_estimate"):
                base = dict(profile["solo_time_estimate"])
                objective_seconds = override["objective_time_override"].get("result")
                base["objective_seconds"] = objective_seconds
                if base.get("total_travel_seconds") is not None and objective_seconds is not None:
                    base["estimated_total_seconds"] = float(base["total_travel_seconds"]) + float(objective_seconds)
                base["objective_calculation"] = override["objective_time_override"]
                base["source"] = "manual_override_plus_materialized_travel"
                profile["effective_time_estimate"] = base
            elif row["route_policy"] == "include":
                profile["effective_time_estimate"] = profile.get("solo_time_estimate")
            else:
                profile["effective_time_estimate"] = {
                    "mode": "not_in_open_world_baseline",
                    "estimated_total_seconds": None,
                    "reason": override.get("time_policy") or row["route_policy"],
                }
        else:
            profile["effective_time_estimate"] = profile.get("solo_time_estimate") if row["time_model_valid_for_global_optimizer"] else None

        if override and row["route_policy"] == "include":
            materialize_manual_special_time(
                profile,
                atlas["quests"][qid_text],
                override,
                npc_by_id,
            )

        audit_rows[qid_text] = {"quest_id": qid, "name": profile.get("name"), **row}
        if row["review_required"]:
            low_rows.append(audit_rows[qid_text])

    payload["summary"]["classification_low_confidence"] = len(low_rows)
    payload["summary"]["classification_manual_resolved"] = manual_resolved
    payload["summary"]["optimizer_time_model_valid"] = sum(
        1 for p in payload["quests"].values() if p.get("time_model_valid_for_global_optimizer")
    )
    payload["meta"]["classification_audit"] = "adversarial-v1+manual-overrides-v1"
    PROFILE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps({"summary": {"low_confidence": len(low_rows), "manual_resolved": manual_resolved}, "quests": audit_rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 赞加沼泽任务类型对抗性审查 v1",
        "",
        f"- 审查任务：{len(audit_rows)}",
        f"- 已用永久人工 override 解决：{manual_resolved}",
        f"- 仍低置信度/需额外数据审查：{len(low_rows)}",
        f"- 当前可直接进入开放世界全局耗时优化器：{payload['summary']['optimizer_time_model_valid']}",
        "",
        "## 审查原则",
        "",
        "自动分类不只寻找支持证据，也主动寻找反例：文本动作与Objective结构冲突、未解析Objective、Item来源并不等于主完成方式、重复Object别名坐标、职业/技能不可接等。低置信度任务仍保留事实，但不得直接用错误耗时进入全局优化。",
        "",
        "## 低置信度任务",
        "",
    ]
    for row in low_rows:
        lines.append(f"- {row['quest_id']}《{row['name']}》：`{row['primary_raw']} → {row['primary_effective']}`；风险：{', '.join(row['risk_flags']) or '—'}。")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"quests": len(audit_rows), "low_confidence": len(low_rows), "optimizer_valid": payload['summary']['optimizer_time_model_valid']}, ensure_ascii=False))
    print(AUDIT_PATH)
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
