"""Route formal Infinite-realm Silver units into the dynamic dossier.

The dossier is a current-state view, not a second knowledge base. A routed Silver
unit can be:
- baseline_absorb: historical calibration; remove from first-read and attach lineage.
- silent_support: same state/boundary, stronger evidence only; remove from first-read.
- visible_update: material state/scope/boundary change; update dossier but keep the
  Silver unit visible in first-read as an update.

Routing is fully reviewed. Similarity may propose targets but cannot apply them.
"""
from __future__ import annotations

import copy
from collections import Counter

ALLOWED_VISIBILITY = {"baseline_absorb", "silent_support", "visible_update"}


def _silver_map(silver: dict) -> dict[str, dict]:
    result = {}
    for unit in silver.get("units", []):
        kid = str(unit.get("knowledge_id") or "")
        if not kid:
            raise ValueError("Silver unit missing knowledge_id")
        if kid in result:
            raise ValueError(f"duplicate Silver knowledge_id: {kid}")
        result[kid] = unit
    return result


def _signal_index(dossier: dict) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    sections = {}
    signals = {}
    for section in dossier.get("sections", []):
        key = str(section.get("key") or "")
        if not key or key in sections:
            raise ValueError(f"invalid or duplicate dossier section key: {key}")
        sections[key] = section
        for signal in section.get("signals", []):
            field = str(signal.get("field") or "")
            pair = (key, field)
            if not field or pair in signals:
                raise ValueError(f"invalid or duplicate dossier signal: {pair}")
            signals[pair] = signal
    return sections, signals


def _card_ids(unit: dict) -> list[str]:
    return sorted({
        str(ref.get("card_id"))
        for ref in unit.get("evidence_refs", [])
        if ref.get("card_id")
    })


def apply_infinite_dossier_routing(
    dossier: dict,
    silver: dict,
    review: dict,
) -> tuple[dict, dict]:
    if review.get("status") != "reviewed_infinite_dossier_routing":
        raise ValueError("unexpected infinite dossier routing review status")

    result = copy.deepcopy(dossier)
    units = _silver_map(silver)
    sections, signals = _signal_index(result)

    expected = {
        kid
        for kid, unit in units.items()
        if unit.get("initial_state") == "queue"
        and "无限服" in (unit.get("topics") or [])
    }

    items = review.get("items", [])
    routed_ids = [str(item.get("knowledge_id") or "") for item in items]
    if any(not kid for kid in routed_ids):
        raise ValueError("dossier routing item missing knowledge_id")
    if len(routed_ids) != len(set(routed_ids)):
        raise ValueError("duplicate dossier routing knowledge_id")

    routed_set = set(routed_ids)
    missing = sorted(expected - routed_set)
    extra = sorted(routed_set - expected)
    if missing:
        raise ValueError(f"infinite Silver units missing reviewed routing: {missing}")
    if extra:
        raise ValueError(f"review routes non-current Infinite queue units: {extra}")

    visibility_counts: Counter[str] = Counter()
    declared_new_signal_count = sum(
        len(item.get("new_signals") or [])
        for item in items
    )
    created_new_signal_count = 0
    target_links = 0
    absorbed_ids: list[str] = []
    visible_update_ids: list[str] = []
    visible_changes: list[dict] = []

    for item in items:
        kid = str(item["knowledge_id"])
        unit = units[kid]
        visibility = str(item.get("visibility") or "")
        if visibility not in ALLOWED_VISIBILITY:
            raise ValueError(f"invalid dossier visibility for {kid}: {visibility}")
        visibility_counts[visibility] += 1
        if visibility == "visible_update":
            visible_update_ids.append(kid)
        else:
            absorbed_ids.append(kid)

        evidence_ids = _card_ids(unit)
        targets = item.get("targets") or []
        additions = item.get("new_signals") or []
        if not targets and not additions:
            raise ValueError(f"dossier routing has no target for {kid}")

        for target in targets:
            section_key = str(target.get("section_key") or "")
            field = str(target.get("field") or "")
            signal = signals.get((section_key, field))
            if signal is None:
                raise ValueError(f"unknown dossier target for {kid}: {(section_key, field)}")
            overrides = {
                key: target[key]
                for key in ("state", "scope", "basis")
                if key in target
            }
            if overrides and visibility != "visible_update":
                raise ValueError(
                    f"only visible_update may change existing dossier state: {kid}"
                )
            if overrides:
                before = {key: signal.get(key) for key in overrides}
                for key, value in overrides.items():
                    if not value:
                        raise ValueError(
                            f"visible dossier update cannot blank {key}: {kid}"
                        )
                    signal[key] = value
                after = {key: signal.get(key) for key in overrides}
                if before != after:
                    visible_changes.append({
                        "knowledge_id": kid,
                        "section_key": section_key,
                        "field": field,
                        "before": before,
                        "after": after,
                    })
            silver_ids = set(signal.get("silver_ids") or [])
            silver_ids.add(kid)
            signal["silver_ids"] = sorted(silver_ids)
            selected_evidence = set(target.get("evidence_card_ids") or evidence_ids)
            unknown_evidence = selected_evidence - set(evidence_ids)
            if unknown_evidence:
                raise ValueError(
                    f"dossier target references evidence outside Silver unit {kid}: "
                    f"{sorted(unknown_evidence)}"
                )
            signal_evidence = set(signal.get("evidence_ids") or [])
            signal_evidence.update(selected_evidence)
            signal["evidence_ids"] = sorted(signal_evidence)
            target_links += 1

        for addition in additions:
            section_key = str(addition.get("section_key") or "")
            section = sections.get(section_key)
            if section is None:
                raise ValueError(f"unknown dossier section for new signal {kid}: {section_key}")
            signal_data = copy.deepcopy(addition.get("signal") or {})
            field = str(signal_data.get("field") or "")
            if not field:
                raise ValueError(f"new dossier signal missing field for {kid}")
            pair = (section_key, field)
            for required in ("state", "scope", "basis"):
                if not signal_data.get(required):
                    raise ValueError(f"new dossier signal missing {required}: {pair}")
            existing_signal = signals.get(pair)
            if existing_signal is not None:
                same_definition = all(
                    existing_signal.get(key) == signal_data.get(key)
                    for key in ("state", "scope", "basis")
                )
                already_linked = kid in set(existing_signal.get("silver_ids") or [])
                if not same_definition or not already_linked:
                    raise ValueError(f"new dossier signal already exists with different lineage: {pair}")
                signal_data = existing_signal
            selected_evidence = set(addition.get("evidence_card_ids") or evidence_ids)
            unknown_evidence = selected_evidence - set(evidence_ids)
            if unknown_evidence:
                raise ValueError(
                    f"new dossier signal references evidence outside Silver unit {kid}: "
                    f"{sorted(unknown_evidence)}"
                )
            signal_data["evidence_ids"] = sorted(
                set(signal_data.get("evidence_ids") or []) | selected_evidence
            )
            signal_data["silver_ids"] = sorted(
                set(signal_data.get("silver_ids") or []) | {kid}
            )
            if existing_signal is None:
                section.setdefault("signals", []).append(signal_data)
                signals[pair] = signal_data
                created_new_signal_count += 1

    result["silver_routing"] = {
        "status": "reviewed",
        "contract": {
            "similarity_can_apply_routing": False,
            "baseline_absorb_visible_in_first_read": False,
            "silent_support_visible_in_first_read": False,
            "visible_update_visible_in_first_read": True,
        },
        "counts": {
            "reviewed_infinite_queue_units": len(expected),
            "baseline_absorb": visibility_counts["baseline_absorb"],
            "silent_support": visibility_counts["silent_support"],
            "visible_update": visibility_counts["visible_update"],
            "new_signals": declared_new_signal_count,
            "target_links": target_links,
        },
        "absorbed_knowledge_ids": sorted(absorbed_ids),
        "visible_update_knowledge_ids": sorted(visible_update_ids),
        "visible_changes": visible_changes,
    }
    audit = {
        "status": "infinite_dossier_routing_applied",
        "counts": {
            **copy.deepcopy(result["silver_routing"]["counts"]),
            "created_new_signals": created_new_signal_count,
        },
        "absorbed_knowledge_ids": sorted(absorbed_ids),
        "visible_update_knowledge_ids": sorted(visible_update_ids),
        "visible_changes": copy.deepcopy(visible_changes),
    }
    return result, audit
