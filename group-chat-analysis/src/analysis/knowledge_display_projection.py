"""Reviewed display projection from canonical Silver into compact user-facing QA units.

This module is presentation-only. It never mutates or redefines canonical Silver facts.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


PROJECTION_STATUS = "reviewed_knowledge_display_projection"
ALLOWED_DISPLAY_STATUS = {"visible", "hidden_no_value"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_LIFECYCLE = {"durable", "time_bound"}


def qa_fingerprint(knowledge_id: str, qa: dict[str, Any]) -> str:
    payload = {
        "knowledge_id": knowledge_id,
        "qa_id": str(qa.get("qa_id") or ""),
        "question": str(qa.get("question") or "").strip(),
        "answer": str(qa.get("answer") or "").strip(),
        # Confidence is review metadata. Raising/lowering it without changing the
        # usable conclusion must not reopen a QA the user has already reviewed.
        "lifecycle": str(qa.get("lifecycle") or ""),
        "time_context": str(qa.get("time_context") or "").strip(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_qa(knowledge_id: str, qa: dict[str, Any], seen_qa_ids: set[str]) -> dict[str, Any]:
    if not isinstance(qa, dict):
        raise ValueError(f"display QA must be an object: {knowledge_id}")

    qa_id = str(qa.get("qa_id") or "").strip()
    if not qa_id:
        raise ValueError(f"display QA missing qa_id: {knowledge_id}")
    if qa_id in seen_qa_ids:
        raise ValueError(f"duplicate qa_id: {qa_id}")
    if not qa_id.startswith(knowledge_id + "::"):
        raise ValueError(f"qa_id must be namespaced by knowledge_id: {qa_id}")
    seen_qa_ids.add(qa_id)

    question = str(qa.get("question") or "").strip()
    answer = str(qa.get("answer") or "").strip()
    if not question:
        raise ValueError(f"display QA missing question: {qa_id}")
    if not answer:
        raise ValueError(f"display QA missing answer: {qa_id}")

    confidence = str(qa.get("confidence") or "").strip()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"invalid display QA confidence: {qa_id}: {confidence}")

    lifecycle = str(qa.get("lifecycle") or "").strip()
    if lifecycle not in ALLOWED_LIFECYCLE:
        raise ValueError(f"invalid display QA lifecycle: {qa_id}: {lifecycle}")

    time_context = str(qa.get("time_context") or "").strip()
    if lifecycle == "time_bound" and not time_context:
        raise ValueError(f"time_bound QA requires time_context: {qa_id}")

    evidence_refs = qa.get("evidence_refs", [])
    if evidence_refs is None:
        evidence_refs = []
    if not isinstance(evidence_refs, list) or any(
        not isinstance(ref, str) or not ref.strip() for ref in evidence_refs
    ):
        raise ValueError(f"display QA evidence_refs must be string list: {qa_id}")

    normalized = {
        "qa_id": qa_id,
        "question": question,
        "answer": answer,
        "confidence": confidence,
        "lifecycle": lifecycle,
        "time_context": time_context,
        "verification_note": str(qa.get("verification_note") or "").strip(),
        "evidence_refs": [ref.strip() for ref in evidence_refs],
    }
    normalized["qa_fingerprint"] = qa_fingerprint(knowledge_id, normalized)
    return normalized


def apply_knowledge_display_projection(
    units: list[dict[str, Any]],
    projection: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(projection, dict):
        raise ValueError("display projection must be an object")
    if projection.get("schema_version") != 1:
        raise ValueError("unsupported display projection schema_version")
    if projection.get("status") != PROJECTION_STATUS:
        raise ValueError("unexpected display projection status")
    items = projection.get("items")
    if not isinstance(items, list):
        raise ValueError("display projection items must be a list")

    result = copy.deepcopy(units)
    unit_map: dict[str, dict[str, Any]] = {}
    for unit in result:
        kid = str(unit.get("knowledge_id") or "").strip()
        if not kid:
            raise ValueError("Silver unit missing knowledge_id")
        if kid in unit_map:
            raise ValueError(f"duplicate Silver knowledge_id: {kid}")
        unit_map[kid] = unit

    seen_units: set[str] = set()
    seen_qa_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("display projection item must be an object")
        kid = str(item.get("knowledge_id") or "").strip()
        if kid not in unit_map:
            raise ValueError(f"unknown knowledge_id in display projection: {kid}")
        if kid in seen_units:
            raise ValueError(f"duplicate display projection knowledge_id: {kid}")
        seen_units.add(kid)

        display_status = str(item.get("display_status") or "visible").strip()
        if display_status not in ALLOWED_DISPLAY_STATUS:
            raise ValueError(f"invalid display_status for {kid}: {display_status}")

        qas = item.get("qas", [])
        if not isinstance(qas, list):
            raise ValueError(f"display projection qas must be a list: {kid}")
        if display_status == "visible" and not qas:
            raise ValueError(f"visible display projection requires qas: {kid}")
        if display_status == "hidden_no_value" and qas:
            raise ValueError(f"hidden_no_value projection cannot contain qas: {kid}")

        unit = unit_map[kid]
        unit["display_projection_status"] = display_status
        unit["display_projection_reason"] = str(item.get("reason") or "").strip()
        unit["display_qas"] = [
            _validate_qa(kid, qa, seen_qa_ids)
            for qa in qas
        ]

    missing = sorted(set(unit_map) - seen_units)
    if missing:
        preview = ", ".join(missing[:5])
        suffix = " ..." if len(missing) > 5 else ""
        raise ValueError(
            f"display projection missing knowledge_id coverage: {preview}{suffix}"
        )

    return result
