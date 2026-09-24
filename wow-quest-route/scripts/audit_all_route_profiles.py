from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from rebuild_route_profile import audit_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "data/route-profiles"


def _load_optional(path: Path | None) -> dict | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _collect_issue_kinds(value: object) -> Counter[str]:
    counts: Counter[str] = Counter()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "issues" and isinstance(child, list):
                for issue in child:
                    if isinstance(issue, dict) and isinstance(issue.get("kind"), str):
                        counts[issue["kind"]] += 1
            else:
                counts.update(_collect_issue_kinds(child))
    elif isinstance(value, list):
        for child in value:
            counts.update(_collect_issue_kinds(child))
    return counts


def _audit_one(args: tuple[str, dict | None, dict | None, dict | None]) -> dict:
    profile_id, xp_input, economy_input, review_input = args
    report = audit_profile(
        profile_id,
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=review_input,
    )
    stage14 = report["mechanical_audit_cold_read"]
    return {
        "profile_id": profile_id,
        "implementation_status": report["implementation_status"],
        "artifact_evaluation_status": report["artifact_evaluation_status"],
        "unimplemented_stages": report["unimplemented_stages"],
        "blocked_stages": [
            row["name"] for row in report["stages"] if row["evaluation_status"] == "blocked"
        ],
        "requirement_stages": [
            row["name"] for row in report["stages"] if row["evaluation_status"] == "requirements"
        ],
        "stage_issue_counts": {
            row["name"]: dict(sorted(_collect_issue_kinds(row.get("detail")).items()))
            for row in report["stages"]
            if _collect_issue_kinds(row.get("detail"))
        },
        "stage14_issue_counts": dict(
            sorted(Counter(issue["kind"] for issue in stage14["issues"]).items())
        ),
    }


def audit_all_profiles(
    *,
    profile_ids: list[str] | None = None,
    xp_input: dict | None = None,
    economy_input: dict | None = None,
    review_input: dict | None = None,
    jobs: int = 1,
) -> dict:
    available_profile_ids = sorted(
        path.stem for path in PROFILES_DIR.glob("*.json") if path.name != "schema.json"
    )
    if profile_ids is None:
        profile_ids = available_profile_ids
    else:
        unknown = sorted(set(profile_ids) - set(available_profile_ids))
        if unknown:
            raise ValueError(f"unknown profile_ids: {unknown}")
        profile_ids = list(dict.fromkeys(profile_ids))
    if jobs < 1:
        raise ValueError("jobs must be >= 1")
    args = [(profile_id, xp_input, economy_input, review_input) for profile_id in profile_ids]
    if jobs == 1 or len(args) <= 1:
        reports = [_audit_one(item) for item in args]
    else:
        with ProcessPoolExecutor(max_workers=min(jobs, len(args))) as executor:
            reports = list(executor.map(_audit_one, args))
    return {
        "kind": "all_route_profiles_artifact_audit",
        "profile_count": len(profile_ids),
        "profiles": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only batch wrapper around the unique Route Lifecycle rebuild/audit entry. "
            "It does not modify Route Profiles or Generated Products."
        )
    )
    parser.add_argument(
        "--profile",
        action="append",
        dest="profile_ids",
        help="Audit only this profile_id. Repeat to audit a small batch; omit to audit all profiles.",
    )
    parser.add_argument("--jobs", type=int, default=1, help="Read-only worker process count.")
    parser.add_argument("--xp-input", type=Path)
    parser.add_argument("--economy-input", type=Path)
    parser.add_argument("--review-input", type=Path)
    args = parser.parse_args()
    result = audit_all_profiles(
        profile_ids=args.profile_ids,
        xp_input=_load_optional(args.xp_input),
        economy_input=_load_optional(args.economy_input),
        review_input=_load_optional(args.review_input),
        jobs=args.jobs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
