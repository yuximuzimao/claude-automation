"""Quality validation for atomic-claim datasets."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .quality import WORK, sha256_file

SOURCE_DIR = WORK / "full-history-chunks"


def validate_source_ref(ref: dict, issues: list[dict], owner: str) -> None:
    for key in ("date", "file", "start_line", "end_line"):
        if key not in ref:
            issues.append({"severity": "error", "code": "missing_source_ref_field", "id": owner, "field": key})
            return
    path = SOURCE_DIR / ref["date"] / ref["file"]
    if not path.exists():
        issues.append({"severity": "error", "code": "source_file_missing", "id": owner, "path": str(path)})
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start, end = int(ref["start_line"]), int(ref["end_line"])
    if start < 1 or end < start or end > len(lines):
        issues.append({"severity": "error", "code": "source_range_invalid", "id": owner, "path": str(path), "range": [start, end]})


def assess(doc: dict) -> dict:
    issues: list[dict] = []
    claim_ids: set[str] = set()
    card_ids: set[str] = set()
    claim_count = 0
    kinds = collections.Counter()
    certainties = collections.Counter()

    items = doc.get("items")
    if not isinstance(items, list):
        return {"result": "FAIL", "issues": [{"severity": "error", "code": "items_not_array"}]}

    for item in items:
        card_id = item.get("card")
        if not card_id:
            issues.append({"severity": "error", "code": "missing_card_id"})
            continue
        if card_id in card_ids:
            issues.append({"severity": "error", "code": "duplicate_card_id", "id": card_id})
        card_ids.add(card_id)

        claims = item.get("claims")
        if not isinstance(claims, list) or not claims:
            issues.append({"severity": "error", "code": "no_atomic_claims", "id": card_id})
            continue
        rejected = item.get("rejected", [])
        if not isinstance(rejected, list):
            issues.append({"severity": "error", "code": "invalid_hard_negative_list", "id": card_id})
        elif doc.get("status") == "calibration_rebuilt_from_canonical" and not rejected:
            issues.append({"severity": "error", "code": "no_hard_negative", "id": card_id})

        # Item refs are aggregate/legacy convenience only. Claim-level refs are the provenance contract.
        refs = item.get("refs", [])
        if refs is not None and not isinstance(refs, list):
            issues.append({"severity": "error", "code": "invalid_item_source_refs", "id": card_id})
        elif isinstance(refs, list):
            for ref in refs:
                validate_source_ref(ref, issues, card_id)

        for claim in claims:
            claim_count += 1
            cid = claim.get("id")
            if not cid:
                issues.append({"severity": "error", "code": "missing_claim_id", "id": card_id})
                continue
            if cid in claim_ids:
                issues.append({"severity": "error", "code": "duplicate_claim_id", "id": cid})
            claim_ids.add(cid)
            for field in ("statement", "entity", "question", "kind", "evidence_type", "certainty"):
                if not isinstance(claim.get(field), str) or not claim[field].strip():
                    issues.append({"severity": "error", "code": "missing_claim_field", "id": cid, "field": field})
            claim_refs = claim.get("source_refs")
            if not isinstance(claim_refs, list) or not claim_refs:
                issues.append({"severity": "error", "code": "claim_missing_source_refs", "id": cid})
            else:
                for ref in claim_refs:
                    validate_source_ref(ref, issues, cid)
            kinds[claim.get("kind", "<missing>")] += 1
            certainties[claim.get("certainty", "<missing>")] += 1

    if doc.get("source_cards_rebuilt") != len(card_ids):
        issues.append({"severity": "error", "code": "source_card_count_mismatch"})
    if doc.get("atomic_claim_count") != claim_count:
        issues.append({"severity": "error", "code": "atomic_claim_count_mismatch"})

    errors = sum(i["severity"] == "error" for i in issues)
    return {
        "contract": "atomic-claim-v1",
        "result": "FAIL" if errors else "PASS",
        "counts": {
            "source_cards": len(card_ids),
            "atomic_claims": claim_count,
            "claims_with_direct_source_refs": sum(
                bool(claim.get("source_refs")) for item in items for claim in item.get("claims", [])
            ),
            "hard_negatives": sum(len(item.get("rejected", [])) for item in items),
            "kinds": dict(sorted(kinds.items())),
            "certainties": dict(sorted(certainties.items())),
        },
        "quality": {"errors": errors, "by_code": dict(sorted(collections.Counter(i["code"] for i in issues).items()))},
        "issues": issues,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=WORK / "atomic-claim-calibration-v1.json")
    p.add_argument("--report", type=Path, default=WORK / "atomic-claim-quality-v1.json")
    args = p.parse_args()
    doc = json.loads(args.input.read_text(encoding="utf-8"))
    report = assess(doc)
    report["inputs"] = {"atomic_claims_sha256": sha256_file(args.input)}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("result", "counts", "quality")}, ensure_ascii=False))
    return 1 if report["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
