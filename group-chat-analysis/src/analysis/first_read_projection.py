"""Build the user-facing first-read projection from reviewed semantic lineage.

Topic Cards are retrieval candidates, not final reading units.  A raw candidate may
leave the first-read queue in either of two ways:

1. its source card is explicitly fully normalized by a reviewed component; or
2. every reviewed Atomic Claim from that card reaches a reviewed terminal semantic
   decision (reuse_existing, consolidation exclusion, or publication decision).

The second rule is important after the full-history cleanup: evidence coverage
("partial") describes one Silver unit's relationship to a source card.  It does not
mean the raw Topic Card must remain user-visible when all of the card's reviewed
claims have independently reached terminal destinations.

This module is strict by design.  Any dangling claim/question/draft becomes an error
instead of silently leaking an old Topic Card back into the reading queue.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .semantic_fingerprint import semantic_fingerprint

DEFAULT_CANDIDATES = WORK / "silver-candidates-v1.json"
DEFAULT_ATOMIC = WORK / "atomic-claims-reviewed-v1.json"
DEFAULT_NO_CLAIM = WORK / "atomic-claim-no-claim-reviewed-v1.json"
DEFAULT_QUESTIONS = WORK / "question-cluster-registry-current.json"
DEFAULT_ROUTING = WORK / "question-cluster-silver-routing-reviewed-v1.json"
DEFAULT_CONSOLIDATION = WORK / "silver-draft-consolidation-reviewed-v1.json"
DEFAULT_PUBLICATION = WORK / "silver-publication-gate-reviewed-v1.json"
DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"
DEFAULT_REVIEWED_STATE = WORK / "reviewed-semantic-state-v1.json"
DEFAULT_DOSSIER = WORK / "infinite-dossier-v1.json"
DEFAULT_OUT = WORK / "first-read-projection-v1.json"


def _unique_map(rows: list[dict], key: str, label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if not value:
            raise ValueError(f"{label} missing {key}")
        if value in result:
            raise ValueError(f"duplicate {label} {key}: {value}")
        result[value] = row
    return result


def _build_lineage_indexes(
    reviewed_atomic: dict,
    questions: dict,
    routing: dict,
    consolidation: dict,
    publication: dict,
) -> dict:
    atomic_by_card: dict[str, list[dict]] = {}
    claim_to_card: dict[str, str] = {}
    for row in reviewed_atomic.get("items", []):
        card = str(row.get("card") or "")
        if not card:
            raise ValueError("reviewed atomic item missing card")
        if card in atomic_by_card:
            raise ValueError(f"duplicate reviewed atomic card: {card}")
        claims = list(row.get("claims", []))
        if not claims:
            raise ValueError(f"reviewed atomic card has no claims: {card}")
        atomic_by_card[card] = claims
        for claim in claims:
            claim_id = str(claim.get("id") or "")
            if not claim_id:
                raise ValueError(f"atomic claim missing id: {card}")
            if claim_id in claim_to_card:
                raise ValueError(f"duplicate atomic claim id: {claim_id}")
            claim_to_card[claim_id] = card

    question_rows = questions.get("clusters", [])
    question_map = _unique_map(question_rows, "question_id", "question")
    claim_to_question: dict[str, str] = {}
    for question in question_rows:
        qid = str(question["question_id"])
        for claim_id in question.get("members", []):
            claim_id = str(claim_id)
            if claim_id in claim_to_question:
                raise ValueError(
                    f"claim belongs to multiple reviewed questions: {claim_id}: "
                    f"{claim_to_question[claim_id]} / {qid}"
                )
            claim_to_question[claim_id] = qid

    missing_questions = sorted(set(claim_to_card) - set(claim_to_question))
    extra_question_claims = sorted(set(claim_to_question) - set(claim_to_card))
    if missing_questions:
        raise ValueError(f"reviewed claims missing question assignment: {missing_questions[:5]}")
    if extra_question_claims:
        raise ValueError(f"question registry contains unknown claims: {extra_question_claims[:5]}")

    route_map = _unique_map(routing.get("items", []), "question_id", "routing")
    missing_routes = sorted(set(question_map) - set(route_map))
    extra_routes = sorted(set(route_map) - set(question_map))
    if missing_routes:
        raise ValueError(f"reviewed questions missing Silver routing: {missing_routes[:5]}")
    if extra_routes:
        raise ValueError(f"routing contains unknown questions: {extra_routes[:5]}")

    group_by_question: dict[str, str] = {}
    group_map = _unique_map(consolidation.get("groups", []), "group_id", "consolidation group")
    for group_id, group in group_map.items():
        for qid in group.get("members", []):
            qid = str(qid)
            if qid in group_by_question:
                raise ValueError(
                    f"question assigned to multiple consolidation groups: {qid}: "
                    f"{group_by_question[qid]} / {group_id}"
                )
            group_by_question[qid] = group_id

    exclusion_map = _unique_map(consolidation.get("exclusions", []), "question_id", "consolidation exclusion")
    overlap = sorted(set(group_by_question) & set(exclusion_map))
    if overlap:
        raise ValueError(f"question both grouped and excluded: {overlap[:5]}")

    new_draft_questions = {
        qid for qid, route in route_map.items()
        if route.get("decision") == "new_draft"
    }
    invalid_route_decisions = sorted(
        qid for qid, route in route_map.items()
        if route.get("decision") not in {"reuse_existing", "new_draft"}
    )
    if invalid_route_decisions:
        raise ValueError(f"unsupported Silver routing decision: {invalid_route_decisions[:5]}")

    unresolved_new = sorted(new_draft_questions - set(group_by_question) - set(exclusion_map))
    stray_consolidation = sorted(
        (set(group_by_question) | set(exclusion_map)) - new_draft_questions
    )
    if unresolved_new:
        raise ValueError(f"new_draft questions missing consolidation decision: {unresolved_new[:5]}")
    if stray_consolidation:
        raise ValueError(f"consolidation contains non-new_draft questions: {stray_consolidation[:5]}")

    publication_map = _unique_map(publication.get("items", []), "group_id", "publication")
    missing_publication = sorted(set(group_map) - set(publication_map))
    extra_publication = sorted(set(publication_map) - set(group_map))
    if missing_publication:
        raise ValueError(f"consolidation groups missing publication decision: {missing_publication[:5]}")
    if extra_publication:
        raise ValueError(f"publication contains unknown groups: {extra_publication[:5]}")
    invalid_publication = sorted(
        gid for gid, row in publication_map.items()
        if row.get("decision") not in {"append_new", "update_existing", "hold"}
    )
    if invalid_publication:
        raise ValueError(f"unsupported publication decision: {invalid_publication[:5]}")

    return {
        "atomic_by_card": atomic_by_card,
        "claim_to_card": claim_to_card,
        "claim_to_question": claim_to_question,
        "question_map": question_map,
        "route_map": route_map,
        "group_by_question": group_by_question,
        "exclusion_map": exclusion_map,
        "publication_map": publication_map,
    }


def _claim_endpoint(claim_id: str, indexes: dict) -> dict:
    qid = indexes["claim_to_question"][claim_id]
    route = indexes["route_map"][qid]
    decision = route["decision"]
    if decision == "reuse_existing":
        targets = sorted({
            str(target.get("knowledge_id"))
            for target in route.get("targets", [])
            if target.get("knowledge_id")
        })
        if not targets:
            raise ValueError(f"reuse_existing route has no Silver target: {qid}")
        return {
            "claim_id": claim_id,
            "question_id": qid,
            "terminal": "reuse_existing",
            "knowledge_ids": targets,
        }

    if qid in indexes["exclusion_map"]:
        row = indexes["exclusion_map"][qid]
        return {
            "claim_id": claim_id,
            "question_id": qid,
            "terminal": "consolidation_excluded",
            "reason": row.get("reason", ""),
        }

    group_id = indexes["group_by_question"][qid]
    row = indexes["publication_map"][group_id]
    action = str(row["decision"])
    endpoint = {
        "claim_id": claim_id,
        "question_id": qid,
        "terminal": f"published_{action}",
        "group_id": group_id,
    }
    target = (
        row.get("target_knowledge_id")
        if action == "update_existing"
        else row.get("draft_knowledge_id")
    )
    if target:
        endpoint["knowledge_ids"] = [str(target)]
    if action == "hold":
        endpoint["reason"] = row.get("reason", "")
    return endpoint


def build_first_read_projection(
    candidates: dict,
    reviewed_atomic: dict,
    no_claim: dict,
    questions: dict,
    routing: dict,
    consolidation: dict,
    publication: dict,
    silver: dict,
    reviewed_state: dict | None = None,
    dossier: dict | None = None,
) -> dict:
    indexes = _build_lineage_indexes(
        reviewed_atomic, questions, routing, consolidation, publication
    )

    no_claim_map = _unique_map(no_claim.get("cards", []), "card_id", "reviewed no-claim")
    atomic_cards = set(indexes["atomic_by_card"])
    overlap = sorted(atomic_cards & set(no_claim_map))
    if overlap:
        raise ValueError(f"cards cannot be both reviewed-claim and no-claim: {overlap[:5]}")

    candidate_rows = candidates.get("candidates", [])
    candidate_map = _unique_map(candidate_rows, "card_id", "candidate")
    resolutions: list[dict] = []
    residual_card_ids: list[str] = []
    resolution_counts: collections.Counter[str] = collections.Counter()
    endpoint_counts: collections.Counter[str] = collections.Counter()

    for card_id, card in candidate_map.items():
        normalized_status = str(card.get("normalized_status") or card.get("silver_status") or "")
        if normalized_status == "full":
            resolution = {
                "card_id": card_id,
                "resolution": "normalized_component_full",
                "user_facing_raw_card": False,
            }
        elif card_id in no_claim_map:
            resolution = {
                "card_id": card_id,
                "resolution": "reviewed_no_claim",
                "user_facing_raw_card": False,
                "reason": no_claim_map[card_id].get("reason", ""),
            }
            endpoint_counts["reviewed_no_claim"] += 1
        elif card_id in indexes["atomic_by_card"]:
            endpoints = [
                _claim_endpoint(str(claim["id"]), indexes)
                for claim in indexes["atomic_by_card"][card_id]
            ]
            for endpoint in endpoints:
                endpoint_counts[endpoint["terminal"]] += 1
            resolution = {
                "card_id": card_id,
                "resolution": "reviewed_claim_lineage_resolved",
                "user_facing_raw_card": False,
                "claim_count": len(endpoints),
                "terminals": sorted({row["terminal"] for row in endpoints}),
                "endpoints": endpoints,
            }
        else:
            resolution = {
                "card_id": card_id,
                "resolution": "unresolved",
                "user_facing_raw_card": True,
                "normalized_status": normalized_status or "unknown",
            }
            residual_card_ids.append(card_id)
        resolutions.append(resolution)
        resolution_counts[resolution["resolution"]] += 1

    # A completed full-history projection must not silently expose legacy Topic Cards.
    if residual_card_ids:
        raise ValueError(
            "first-read projection has unresolved raw candidate cards: "
            f"{len(residual_card_ids)}; examples={residual_card_ids[:10]}"
        )

    units = silver.get("units", [])
    reviewed_state = reviewed_state or {"states": []}
    reviewed_id_decisions: dict[str, str] = {}
    reviewed_fingerprint_decisions: dict[str, str] = {}
    for row in reviewed_state.get("states", []):
        decision = str(row.get("decision") or "")
        if decision not in {"discard", "knowledge"}:
            continue
        fingerprint = str(row.get("semantic_fingerprint") or "")
        if fingerprint:
            existing = reviewed_fingerprint_decisions.get(fingerprint)
            if existing and existing != decision:
                raise ValueError(
                    f"conflicting reviewed semantic decisions for fingerprint: {fingerprint}"
                )
            reviewed_fingerprint_decisions[fingerprint] = decision
        for raw_id in (row.get("aliases") or {}).get("knowledge_ids", []):
            kid = str(raw_id or "")
            if not kid:
                continue
            existing = reviewed_id_decisions.get(kid)
            if existing and existing != decision:
                raise ValueError(
                    f"conflicting reviewed semantic decisions for knowledge_id: {kid}"
                )
            reviewed_id_decisions[kid] = decision

    dossier = dossier or {}
    dossier_routing = dossier.get("silver_routing") or {}
    dossier_absorbed_ids = {
        str(x)
        for x in dossier_routing.get("absorbed_knowledge_ids", [])
        if x
    }

    unit_ids: set[str] = set()
    queue_knowledge_ids: list[str] = []
    reviewed_queue_knowledge_ids: list[str] = []
    reviewed_knowledge_knowledge_ids: list[str] = []
    reviewed_discard_knowledge_ids: list[str] = []
    dossier_absorbed_knowledge_ids: list[str] = []
    initial_knowledge_knowledge_ids: list[str] = []
    other_state_ids: list[str] = []
    for unit in units:
        kid = str(unit.get("knowledge_id") or "")
        if not kid:
            raise ValueError("Silver unit missing knowledge_id")
        if kid in unit_ids:
            raise ValueError(f"duplicate formal Silver knowledge_id: {kid}")
        unit_ids.add(kid)
        state = unit.get("initial_state")
        if state == "queue":
            id_decision = reviewed_id_decisions.get(kid)
            if id_decision:
                reviewed_decision = id_decision
            elif reviewed_fingerprint_decisions:
                reviewed_decision = reviewed_fingerprint_decisions.get(
                    semantic_fingerprint(unit)
                )
            else:
                reviewed_decision = None
            if reviewed_decision:
                reviewed_queue_knowledge_ids.append(kid)
                if reviewed_decision == "knowledge":
                    reviewed_knowledge_knowledge_ids.append(kid)
                else:
                    reviewed_discard_knowledge_ids.append(kid)
            elif kid in dossier_absorbed_ids:
                dossier_absorbed_knowledge_ids.append(kid)
            else:
                queue_knowledge_ids.append(kid)
        elif state == "knowledge":
            initial_knowledge_knowledge_ids.append(kid)
        else:
            other_state_ids.append(kid)

    if other_state_ids:
        raise ValueError(
            f"formal Silver contains unsupported initial_state: {other_state_ids[:10]}"
        )

    return {
        "schema_version": 1,
        "status": "reviewed_first_read_projection",
        "contract": {
            "topic_cards_are_final_reading_units": False,
            "full_component_coverage_is_terminal": True,
            "reviewed_claim_lineage_can_close_partial_or_unabsorbed_cards": True,
            "reviewed_semantic_state_closes_queue_units": True,
            "dossier_absorption_closes_non_update_queue_units": True,
            "dangling_semantics_must_fail_closed": True,
        },
        "counts": {
            "candidate_cards": len(candidate_rows),
            "normalized_component_full": resolution_counts["normalized_component_full"],
            "reviewed_claim_lineage_resolved": resolution_counts["reviewed_claim_lineage_resolved"],
            "reviewed_no_claim": resolution_counts["reviewed_no_claim"],
            "raw_card_queue": len(residual_card_ids),
            "formal_silver_units": len(units),
            "first_read_silver_units": len(queue_knowledge_ids),
            "reviewed_queue_silver_units": len(reviewed_queue_knowledge_ids),
            "reviewed_knowledge_silver_units": len(reviewed_knowledge_knowledge_ids),
            "reviewed_discard_silver_units": len(reviewed_discard_knowledge_ids),
            "dossier_absorbed_silver_units": len(dossier_absorbed_knowledge_ids),
            "initial_knowledge_silver_units": len(initial_knowledge_knowledge_ids),
            "knowledge_silver_units": (
                len(initial_knowledge_knowledge_ids)
                + len(reviewed_knowledge_knowledge_ids)
            ),
        },
        "endpoint_counts": dict(sorted(endpoint_counts.items())),
        "queue": {
            "silver_knowledge_ids": sorted(queue_knowledge_ids),
            "reviewed_silver_knowledge_ids": sorted(reviewed_queue_knowledge_ids),
            "reviewed_knowledge_silver_ids": sorted(reviewed_knowledge_knowledge_ids),
            "reviewed_discard_silver_ids": sorted(reviewed_discard_knowledge_ids),
            "dossier_absorbed_silver_knowledge_ids": sorted(dossier_absorbed_knowledge_ids),
            "residual_card_ids": sorted(residual_card_ids),
        },
        "knowledge": {
            "initial_silver_knowledge_ids": sorted(initial_knowledge_knowledge_ids),
            "reviewed_silver_knowledge_ids": sorted(reviewed_knowledge_knowledge_ids),
            "silver_knowledge_ids": sorted(
                set(initial_knowledge_knowledge_ids)
                | set(reviewed_knowledge_knowledge_ids)
            ),
        },
        "candidate_resolutions": sorted(resolutions, key=lambda row: row["card_id"]),
    }


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--atomic", type=Path, default=DEFAULT_ATOMIC)
    parser.add_argument("--no-claim", type=Path, default=DEFAULT_NO_CLAIM)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--routing", type=Path, default=DEFAULT_ROUTING)
    parser.add_argument("--consolidation", type=Path, default=DEFAULT_CONSOLIDATION)
    parser.add_argument("--publication", type=Path, default=DEFAULT_PUBLICATION)
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    parser.add_argument("--reviewed-state", type=Path, default=DEFAULT_REVIEWED_STATE)
    parser.add_argument("--dossier", type=Path, default=DEFAULT_DOSSIER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    paths = {
        "candidates": args.candidates,
        "atomic": args.atomic,
        "no_claim": args.no_claim,
        "questions": args.questions,
        "routing": args.routing,
        "consolidation": args.consolidation,
        "publication": args.publication,
        "silver": args.silver,
    }
    if args.reviewed_state.exists():
        paths["reviewed_state"] = args.reviewed_state
    if args.dossier.exists():
        paths["dossier"] = args.dossier
    result = build_first_read_projection(
        _load(args.candidates),
        _load(args.atomic),
        _load(args.no_claim),
        _load(args.questions),
        _load(args.routing),
        _load(args.consolidation),
        _load(args.publication),
        _load(args.silver),
        _load(args.reviewed_state) if args.reviewed_state.exists() else None,
        _load(args.dossier) if args.dossier.exists() else None,
    )
    result["inputs"] = {
        name: {"file": path.name, "sha256": sha256_file(path)}
        for name, path in paths.items()
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "counts": result["counts"],
        "endpoint_counts": result["endpoint_counts"],
        "out": str(args.out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
