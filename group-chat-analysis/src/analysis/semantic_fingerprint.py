"""Stable semantic fingerprints for reviewed Silver knowledge units.

A fingerprint answers one narrow question: has the user already reviewed this
semantic conclusion?  It deliberately excludes evidence volume, confidence,
freshness and observation dates.  Those may change silently as more chat evidence
arrives and must not make an old conclusion re-enter the first-read queue.

New conditions, exceptions or applicability boundaries should be represented as a
new reviewed question/Silver delta upstream.  The fingerprint therefore includes the
stable applicability scope that materially changes who/when the conclusion applies.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

FINGERPRINT_VERSION = 1

# Keys whose value changes the applicability boundary of the conclusion.
STABLE_SCOPE_KEYS = {
    "game_variant",
    "phase_context",
    "class",
    "class_spec",
    "spec",
    "role",
    "level",
    "level_range",
    "realm",
    "realm_scope",
    "server",
    "server_scope",
    "faction",
    "difficulty",
    "content",
    "content_scope",
    "profession",
    "event",
}

# Observation/evidence metadata.  These may evolve without producing a new user
# interruption.  Unknown scope keys are excluded by default rather than guessed.
VOLATILE_SCOPE_KEYS = {
    "time_window",
    "observed_at",
    "observed_date",
    "date",
    "date_range",
    "source_window",
    "freshness",
    "time_sensitive",
}


def normalize_semantic_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"\s+", " ", text)


def stable_scope(scope: dict | None) -> dict:
    if not isinstance(scope, dict):
        return {}
    result: dict[str, Any] = {}
    for key in sorted(STABLE_SCOPE_KEYS):
        if key not in scope:
            continue
        value = scope[key]
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            result[key] = normalize_semantic_text(value)
        elif isinstance(value, list):
            result[key] = [
                normalize_semantic_text(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def semantic_identity(unit: dict) -> dict:
    subject = normalize_semantic_text(unit.get("subject"))
    question = normalize_semantic_text(unit.get("question"))
    kind = normalize_semantic_text(unit.get("kind"))
    if not subject or not question:
        raise ValueError(
            f"semantic fingerprint requires subject + question: "
            f"{unit.get('knowledge_id', '<unknown>')}"
        )
    return {
        "subject": subject,
        "question": question,
        "kind": kind,
        "scope": stable_scope(unit.get("scope")),
    }


def semantic_fingerprint(unit: dict) -> str:
    identity = semantic_identity(unit)
    payload = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sf{FINGERPRINT_VERSION}:{digest}"


def build_fingerprint_registry(silver: dict) -> dict:
    units = silver.get("units", [])
    entries: list[dict] = []
    by_fingerprint: dict[str, list[str]] = {}
    seen_ids: set[str] = set()

    for unit in units:
        kid = str(unit.get("knowledge_id") or "")
        if not kid:
            raise ValueError("Silver unit missing knowledge_id")
        if kid in seen_ids:
            raise ValueError(f"duplicate knowledge_id: {kid}")
        seen_ids.add(kid)
        identity = semantic_identity(unit)
        fingerprint = semantic_fingerprint(unit)
        by_fingerprint.setdefault(fingerprint, []).append(kid)
        entries.append({
            "knowledge_id": kid,
            "semantic_fingerprint": fingerprint,
            "semantic_identity": identity,
            "initial_state": unit.get("initial_state"),
        })

    collisions = {
        fp: ids
        for fp, ids in by_fingerprint.items()
        if len(ids) > 1
    }
    if collisions:
        examples = list(collisions.items())[:5]
        raise ValueError(
            "distinct Silver IDs share an exact semantic fingerprint; "
            f"review required before dedupe: {examples}"
        )

    return {
        "schema_version": 1,
        "status": "semantic_fingerprint_registry",
        "fingerprint_version": FINGERPRINT_VERSION,
        "contract": {
            "identity_fields": ["subject", "question", "kind", "stable_scope"],
            "excluded_from_identity": [
                "canonical_facts",
                "structured",
                "evidence_refs",
                "evidence_state",
                "freshness",
                "search_terms",
                "scope.time_window",
                "scope.observed_date",
                "scope.date",
                "scope.time_sensitive",
            ],
            "matching_order": [
                "exact_knowledge_id",
                "exact_semantic_fingerprint",
                "reviewed_semantic_match",
            ],
            "fuzzy_similarity_can_auto_hide": False,
        },
        "counts": {
            "silver_units": len(entries),
            "fingerprints": len(by_fingerprint),
            "exact_collisions": 0,
        },
        "entries": sorted(entries, key=lambda row: row["knowledge_id"]),
    }
