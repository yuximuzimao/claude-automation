from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_profiles import load_route_profile, route_profile_path, validate_route_profile
from lib.route_service_context import (
    apply_approved_service_override_review,
    build_service_override_review,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_review(profile_id: str, proposal_path: Path) -> dict[str, Any]:
    profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
    proposal = _load_json(proposal_path)
    if isinstance(proposal, dict) and proposal.get("schema") == "route-service-override-proposal/v1":
        if proposal.get("profile_id") != profile_id:
            raise ValueError("service proposal profile_id mismatch")
        proposed_overrides = proposal.get("service_overrides")
    elif isinstance(proposal, list):
        proposed_overrides = proposal
    else:
        raise ValueError("proposal must be a service override list or route-service-override-proposal/v1 object")
    if not isinstance(proposed_overrides, list):
        raise ValueError("service proposal service_overrides must be a list")

    # Validate the proposal only as a Profile contract. This script never derives candidates from
    # guide text, legacy cluster files, generated HTML, or coordinates.
    candidate = dict(profile)
    candidate["service_overrides"] = proposed_overrides
    validate_route_profile(candidate, expected_profile_id=profile_id, known_task_cards=None)
    return build_service_override_review(profile, proposed_overrides)


def apply_review(review_path: Path) -> dict[str, Any]:
    review = _load_json(review_path)
    profile_id = str(review.get("profile_id") or "")
    if not profile_id:
        raise ValueError("service override review missing profile_id")
    profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
    updated = apply_approved_service_override_review(profile, review)
    validate_route_profile(updated, expected_profile_id=profile_id, known_task_cards=None)
    path = route_profile_path(profile_id)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema": "route-service-override-apply-result/v1",
        "profile_id": profile_id,
        "approved_count": sum(1 for row in review.get("rows") or [] if row.get("approved") is True),
        "profile_path": str(path.relative_to(ROOT)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stage-6 service migration gate. It packages explicit proposals for review or applies "
            "approved rows; it never infers background/shared service from prose or legacy clusters."
        )
    )
    parser.add_argument("profile_id", nargs="?")
    parser.add_argument("--proposal", type=Path, help="Explicit service_overrides proposal JSON; no inference is performed.")
    parser.add_argument("--review-out", type=Path, help="Write the generated review manifest here.")
    parser.add_argument("--apply-review", type=Path, help="Apply only rows marked approved=true in this review manifest.")
    args = parser.parse_args()

    if args.apply_review is not None:
        if args.profile_id is not None or args.proposal is not None or args.review_out is not None:
            raise SystemExit("--apply-review cannot be combined with proposal generation options")
        print(json.dumps(apply_review(args.apply_review), ensure_ascii=False, indent=2))
        return

    if not args.profile_id or args.proposal is None:
        raise SystemExit("review generation requires profile_id and --proposal")
    review = build_review(args.profile_id, args.proposal)
    if args.review_out is not None:
        args.review_out.parent.mkdir(parents=True, exist_ok=True)
        args.review_out.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(review, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
