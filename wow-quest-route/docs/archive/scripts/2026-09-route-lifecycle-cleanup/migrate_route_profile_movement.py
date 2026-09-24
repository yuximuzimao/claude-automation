from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_movement import apply_approved_movement_review, build_movement_migration_review
from lib.route_profiles import load_all_route_profiles, load_route_profile, route_profile_path, validate_route_profile


def _profile_ids_from_disk() -> list[str]:
    return sorted(load_all_route_profiles(validate=True, validate_task_cards=False))


def build_reviews(profile_ids: list[str]) -> dict[str, Any]:
    rows = []
    for profile_id in profile_ids:
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        rows.append(build_movement_migration_review(profile))
    return {
        "schema": "route-movement-migration-review-set/v1",
        "profile_count": len(rows),
        "profiles": rows,
    }


def approve_mechanical_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    """Mark only deterministic incoming-movement candidates approved in a review payload.

    This approves only Stage-5 patches explicitly classified as mechanical candidates: direct incoming
    promotion and exact hearth/taxi leading-action reorder. It never approves primary-zone, move-mode,
    or manual-review rows and never applies the review.
    The existing profile version/fingerprint gate still runs when --apply-review is used later.
    """
    rows = _reviews_by_profile(payload)
    approved = 0
    for review in rows.values():
        for patch in review.get("patches") or []:
            if (
                patch.get("kind")
                in {
                    "incoming_movement",
                    "reorder_leading_movement",
                    "remove_nonterminal_incoming_movement",
                    "remove_stale_duplicate_incoming",
                }
                and patch.get("status") == "mechanical_candidate"
            ):
                patch["approved"] = True
                patch["approval_basis"] = "deterministic_stage5_mechanical_candidate"
                approved += 1
    payload["mechanical_candidate_approval_count"] = approved
    return payload


def _reviews_by_profile(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schema = payload.get("schema")
    if schema == "route-movement-migration-review/v1":
        profile_id = str(payload.get("profile_id") or "")
        if not profile_id:
            raise ValueError("single movement review missing profile_id")
        return {profile_id: payload}
    if schema != "route-movement-migration-review-set/v1":
        raise ValueError("unsupported movement migration review file")
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        raise ValueError("movement review set profiles must be a list")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("schema") != "route-movement-migration-review/v1":
            raise ValueError("movement review set contains invalid profile review")
        profile_id = str(row.get("profile_id") or "")
        if not profile_id or profile_id in out:
            raise ValueError(f"invalid/duplicate movement review profile_id: {profile_id!r}")
        out[profile_id] = row
    return out


def approve_primary_zones_from_map_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Approve primary_zone_id only from an exact local map-asset manifest match.

    Profiles with any unresolved legacy crossmap edge are intentionally skipped because their
    cross-zone visits still need explicit location-level zone overrides before a default zone is safe.
    """
    manifest = json.loads((ROOT / "data/routes/maps/manifest.json").read_text(encoding="utf-8"))
    asset_zone: dict[str, int] = {}
    for row in manifest.get("maps") or []:
        if not isinstance(row, dict) or not isinstance(row.get("zone_id"), int):
            continue
        for key in ("file", "hd_file"):
            name = row.get(key)
            if isinstance(name, str) and name:
                asset_zone[f"maps/{name}"] = int(row["zone_id"])

    reviews = _reviews_by_profile(payload)
    approved = 0
    skipped_crossmap: list[str] = []
    missing_asset_match: list[str] = []
    for profile_id, review in reviews.items():
        has_crossmap_review = any(
            patch.get("kind") == "manual_review"
            and isinstance(patch.get("issue"), dict)
            and patch["issue"].get("kind") == "legacy_transport_requires_operation_review"
            and patch["issue"].get("legacy_transport") == "crossmap"
            for patch in review.get("patches") or []
        )
        if has_crossmap_review:
            skipped_crossmap.append(profile_id)
            continue
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        map_image = (profile.get("display") or {}).get("map_image")
        zone_id = asset_zone.get(map_image)
        if zone_id is None:
            missing_asset_match.append(profile_id)
            continue
        for patch in review.get("patches") or []:
            if patch.get("kind") == "primary_zone_id" and patch.get("status") == "review_required":
                patch["zone_id"] = zone_id
                patch["approved"] = True
                patch["approval_basis"] = "exact_route_map_asset_manifest_match_no_unresolved_crossmap"
                approved += 1
                break

    payload["primary_zone_approval_count"] = approved
    payload["primary_zone_skipped_crossmap_profiles"] = sorted(skipped_crossmap)
    payload["primary_zone_missing_asset_match_profiles"] = sorted(missing_asset_match)
    return payload


def apply_review_file(review_path: Path) -> dict[str, Any]:
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    reviews = _reviews_by_profile(payload)
    results: list[dict[str, Any]] = []

    # Validate every approved patch against its current profile before writing any file. This keeps
    # multi-profile application all-or-nothing at the review/fingerprint gate.
    prepared: dict[str, dict[str, Any]] = {}
    for profile_id, review in reviews.items():
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        updated = apply_approved_movement_review(profile, review)
        validate_route_profile(updated, expected_profile_id=profile_id, known_task_cards=None)
        prepared[profile_id] = updated
        approved_count = sum(1 for patch in review.get("patches") or [] if patch.get("approved") is True)
        results.append({"profile_id": profile_id, "approved_patch_count": approved_count})

    for profile_id, updated in prepared.items():
        path = route_profile_path(profile_id)
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "schema": "route-movement-migration-apply-result/v1",
        "review_path": str(review_path),
        "profile_count": len(prepared),
        "profiles": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stage-5 movement migration helper. Default mode only emits review manifests; it never "
            "promotes legacy transport evidence into Route Profile truth automatically."
        )
    )
    parser.add_argument("profile_ids", nargs="*")
    parser.add_argument("--all", action="store_true", help="Generate review rows for every Route Profile.")
    parser.add_argument(
        "--approve-mechanical",
        action="store_true",
        help=(
            "In the generated review only, mark deterministic incoming_movement mechanical candidates approved. "
            "This does not apply the review and never approves manual/primary-zone/move-mode rows."
        ),
    )
    parser.add_argument(
        "--approve-primary-zones-from-map-manifest",
        action="store_true",
        help=(
            "In the generated review only, approve primary_zone_id from an exact local map manifest match, "
            "but skip profiles that still contain unresolved legacy crossmap edges."
        ),
    )
    parser.add_argument("--review-out", type=Path, help="Write the generated non-authoritative review JSON here.")
    parser.add_argument(
        "--apply-review",
        type=Path,
        help=(
            "Apply only patches explicitly marked approved=true in an existing review file. "
            "Profile version and Stage-5 fingerprint must still match exactly."
        ),
    )
    args = parser.parse_args()

    if args.apply_review is not None:
        if (
            args.profile_ids
            or args.all
            or args.approve_mechanical
            or args.approve_primary_zones_from_map_manifest
            or args.review_out is not None
        ):
            raise SystemExit("--apply-review cannot be combined with profile selection/review generation options")
        result = apply_review_file(args.apply_review)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.all and args.profile_ids:
        raise SystemExit("use either explicit profile_ids or --all, not both")
    profile_ids = _profile_ids_from_disk() if args.all else args.profile_ids
    if not profile_ids:
        raise SystemExit("provide profile_ids or --all")

    result = build_reviews(profile_ids)
    if args.approve_mechanical:
        result = approve_mechanical_candidates(result)
    if args.approve_primary_zones_from_map_manifest:
        result = approve_primary_zones_from_map_manifest(result)
    if args.review_out is not None:
        args.review_out.parent.mkdir(parents=True, exist_ok=True)
        args.review_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
