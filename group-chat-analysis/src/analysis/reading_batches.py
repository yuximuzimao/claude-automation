"""Immutable release-derived reading batches, independent of QA review decisions.

Publication validates every expected day before switching the single current pointer.
QA inclusion is an exact ID difference against the hash-bound prepare-work baseline;
changing evidence/answers for an existing ID is not a new QA. Seen state never writes
user or system QA decisions.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import fcntl
import json
from pathlib import Path
import re
from typing import Iterator

from src.app.runtime_deadline import check_environment_deadline

from .analysis_release import sha256_file, sha256_json, sha256_path, write_json_atomic
from .knowledge_display_projection import PROJECTION_STATUS, _validate_qa

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")


class ReadingBatchError(ValueError):
    pass


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ReadingBatchError("invalid reading/release identifier")
    return value


def _load(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReadingBatchError(f"missing or invalid document: {path.name}") from exc
    if not isinstance(doc, dict):
        raise ReadingBatchError(f"document must be an object: {path.name}")
    return doc


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ReadingBatchError("artifact path must be relative")
    path = root / relative
    if any(part == ".." for part in Path(relative).parts):
        raise ReadingBatchError("artifact path escapes release")
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise ReadingBatchError("artifact path escapes release or is a symlink")
    return path


def _projection(doc: dict) -> dict[str, dict]:
    if doc.get("schema_version") != 1 or doc.get("status") != PROJECTION_STATUS:
        raise ReadingBatchError("not a reviewed QA projection")
    if not isinstance(doc.get("items"), list):
        raise ReadingBatchError("projection items must be an array")
    rows: dict[str, dict] = {}
    seen: set[str] = set()
    seen_units: set[str] = set()
    for unit in doc["items"]:
        kid = unit.get("knowledge_id")
        if not isinstance(kid, str) or not kid or kid in seen_units:
            raise ReadingBatchError("missing or duplicate projection knowledge ID")
        seen_units.add(kid)
        if not isinstance(unit.get("qas"), list):
            raise ReadingBatchError("projection qas must be an array")
        for qa in unit["qas"]:
            normalized = _validate_qa(kid, qa, seen)
            rows[normalized["qa_id"]] = {**normalized, "knowledge_id": kid}
    return rows


def _release_delta(project_root: Path, run_id: str) -> dict:
    _identifier(run_id)
    release = project_root / "runtime" / "analysis" / "releases" / run_id
    if release.is_symlink():
        raise ReadingBatchError("release must be an immutable directory")
    result = _load(release / "result.json")
    if result.get("status") != "published_analysis_result" or result.get("run_id") != run_id:
        raise ReadingBatchError("release is not fully published")
    batch_id = _identifier(result.get("batch_id"))
    source = result.get("source") or {}
    capture_runtime = str(source.get("capture_runtime") or "")
    match = re.fullmatch(r"runtime/history-days/(\d{4}-\d{2}-\d{2})", capture_runtime)
    if not match or source.get("batch_id") != batch_id:
        raise ReadingBatchError("release lacks exact history-day lineage")
    day = match.group(1)
    date.fromisoformat(day)
    if batch_id != f"history-{day.replace('-', '')}-full":
        raise ReadingBatchError("history-day batch ID/date mismatch")
    quality = result.get("quality") or {}
    if quality.get("errors") != 0 or quality.get("result") not in {"PASS", "PASS_WITH_WARNINGS"}:
        raise ReadingBatchError("release quality did not pass")
    artifacts = result.get("artifacts")
    required = {"work_package", "review_receipt", "display_projection", "silver_knowledge", "page", "page_details", "quality_report"}
    if not isinstance(artifacts, dict) or not required.issubset(artifacts):
        raise ReadingBatchError("release artifact index is incomplete")
    paths = {}
    for key, ref in artifacts.items():
        if not isinstance(ref, dict):
            raise ReadingBatchError("invalid release artifact reference")
        path = _inside(release, ref.get("path"))
        try:
            actual = sha256_path(path)
        except (ValueError, OSError) as exc:
            raise ReadingBatchError(f"missing release artifact: {key}") from exc
        if actual != ref.get("sha256"):
            raise ReadingBatchError(f"release artifact hash mismatch: {key}")
        paths[key] = path
    work = _load(paths["work_package"])
    receipt = _load(paths["review_receipt"])
    if work.get("status") != "analysis_work_prepared" or work.get("batch_id") != batch_id or work.get("source") != source:
        raise ReadingBatchError("work package lineage mismatch")
    if receipt.get("status") != "reviewed_analysis_ready" or receipt.get("batch_id") != batch_id:
        raise ReadingBatchError("release receipt was not reviewed")
    for key in ("current_sha256", "canonical_batch_sha256", "message_count"):
        if (receipt.get("source") or {}).get(key) != source.get(key):
            raise ReadingBatchError("receipt source mismatch")
    work_ref = receipt.get("work_package") or {}
    expected_work_path = f"runtime/analysis-work/batches/{batch_id}/analysis-work-package-v1.json"
    if work_ref.get("sha256") != artifacts["work_package"]["sha256"] or work_ref.get("path") != expected_work_path:
        raise ReadingBatchError("receipt/work-package binding mismatch")
    if (result.get("review") or {}).get("receipt_sha256") != artifacts["review_receipt"]["sha256"]:
        raise ReadingBatchError("result/receipt binding mismatch")
    # The baseline file is frozen by prepare-work's caller; its content must match
    # the work package, not the mutable current projection or today's QA count.
    baseline_ref = (work.get("baseline_artifacts") or {}).get("display_projection") or {}
    if baseline_ref.get("path") != "runtime/analysis-work/knowledge-display-projection-v1.json":
        raise ReadingBatchError("work package lacks display projection baseline")
    baseline = project_root / "runtime" / "analysis-work" / "batches" / batch_id / "baseline" / "knowledge-display-projection-v1.json"
    if not baseline.is_file() or baseline.is_symlink() or sha256_file(baseline) != baseline_ref.get("sha256"):
        raise ReadingBatchError("frozen baseline does not match prepare-work hash")
    before = _projection(_load(baseline))
    after = _projection(_load(paths["display_projection"]))
    # Frozen final projection is also bound by the reviewed artifact receipt.
    reviewed_projection = (receipt.get("artifacts") or {}).get("display_projection") or {}
    if reviewed_projection.get("sha256") != artifacts["display_projection"]["sha256"]:
        raise ReadingBatchError("final projection is not bound by review receipt")
    system = _load(paths["system_qa_decisions"]) if "system_qa_decisions" in paths else {"items": []}
    decisions = {q.get("qa_id"): q for q in system.get("items", [])}
    new = []
    for qid, qa in after.items():
        if qid in before:
            continue
        row = dict(qa)
        row["run_id"] = run_id
        row["source_day"] = day
        row["evidence"] = []
        for card_id in qa["evidence_refs"]:
            evidence = {"card_id": card_id}
            if _ID.fullmatch(card_id):
                detail = paths["page_details"] / f"{card_id}.html"
                if detail.is_file() and not detail.is_symlink():
                    evidence.update({"detail_file": f"{card_id}.html", "sha256": sha256_file(detail)})
            row["evidence"].append(evidence)
        decision = decisions.get(qid, {})
        if decision.get("qa_fingerprint") == qa["qa_fingerprint"]:
            row["system_decision"] = decision.get("decision")
        # No filtering by system decision: discarded QA is still newly produced.
        new.append(row)
    return {"day": day, "run_id": run_id, "capture_batch_id": batch_id,
            "result_sha256": sha256_file(release / "result.json"),
            "baseline_sha256": baseline_ref["sha256"],
            "final_projection_sha256": artifacts["display_projection"]["sha256"],
            "page_details_path": artifacts["page_details"]["path"], "qas": new}


class ReadingBatchStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.root = self.project_root / "runtime" / "reading-batches"
        self.entries = self.root / "batches"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def get(self, batch_id: str) -> dict:
        doc = _load(self.entries / f"{_identifier(batch_id)}.json")
        if doc.get("status") != "published_reading_batch" or doc.get("reading_batch_id") != batch_id:
            raise ReadingBatchError("invalid reading batch")
        return doc

    def _with_release_context(self, doc: dict) -> dict:
        # Read-time enrichment leaves existing immutable reading snapshots intact.
        parents = {}
        for run in doc["releases"]:
            directory = self.project_root / "runtime/analysis/releases" / _identifier(run["run_id"])
            result_path = directory / "result.json"
            if sha256_file(result_path) != run["result_sha256"]:
                raise ReadingBatchError("reading release lineage changed")
            ref = _load(result_path)["artifacts"]["silver_knowledge"]
            silver_path = _inside(directory, ref["path"])
            if sha256_file(silver_path) != ref["sha256"]:
                raise ReadingBatchError("frozen parent Silver changed")
            parents[run["run_id"]] = {u["knowledge_id"]: u for u in _load(silver_path)["units"]}
        enriched = []
        for qa in doc["qas"]:
            parent = parents.get(qa["run_id"], {}).get(qa["knowledge_id"])
            if parent is None:
                raise ReadingBatchError("reading QA has no frozen parent Silver")
            enriched.append({**qa, "topics": parent.get("topics", []),
                             "scope": parent.get("scope", {}), "subject": parent.get("subject", "")})
        return {**doc, "qas": enriched}

    def snapshot(self) -> dict:
        current = _load(self.root / "current.json") if (self.root / "current.json").exists() else None
        docs = [_load(p) for p in self.entries.glob("*.json")] if self.entries.exists() else []
        docs.sort(key=lambda d: (d["expected_days"][-1], d["created_at"], d["reading_batch_id"]), reverse=True)
        if current:
            doc = self.get(current["reading_batch_id"])
            if sha256_json(doc) != current.get("sha256"):
                raise ReadingBatchError("reading batch current hash mismatch")
        seen = _load(self.root / "seen.json") if (self.root / "seen.json").exists() else {"items": []}
        seen_map = {row["reading_batch_id"]: row["seen_at"] for row in seen.get("items", [])}
        return {"schema_version": 1, "current_batch_id": current["reading_batch_id"] if current else None,
                "batches": [{**self._with_release_context(d), "seen_at": seen_map.get(d["reading_batch_id"])} for d in docs]}

    def mark_seen(self, batch_id: str, *, now: str | None = None) -> dict:
        with self._lock():
            self.get(batch_id)
            path = self.root / "seen.json"
            doc = _load(path) if path.exists() else {"schema_version": 1, "items": []}
            for row in doc["items"]:
                if row["reading_batch_id"] == batch_id:
                    return dict(row)
            row = {"reading_batch_id": batch_id, "seen_at": now or datetime.now(timezone.utc).isoformat()}
            doc["items"].append(row)
            write_json_atomic(path, doc)
            return row

    def evidence_file(self, batch_id: str, qa_id: str, card_id: str) -> Path:
        doc = self.get(batch_id)
        for qa in doc["qas"]:
            if qa["qa_id"] != qa_id:
                continue
            for evidence in qa["evidence"]:
                if evidence["card_id"] == card_id and evidence.get("detail_file"):
                    run = next(r for r in doc["releases"] if r["run_id"] == qa["run_id"])
                    directory = self.project_root / "runtime" / "analysis" / "releases" / _identifier(qa["run_id"])
                    path = _inside(directory, run["page_details_path"] + "/" + evidence["detail_file"])
                    if not path.is_file() or sha256_file(path) != evidence["sha256"]:
                        raise ReadingBatchError("reading evidence changed")
                    return path
        raise ReadingBatchError("unknown reading evidence")


def publish_reading_batch(project_root: Path, *, reading_batch_id: str, run_ids: list[str], expected_days: list[str], now: str | None = None) -> dict:
    """Validate complete day releases and atomically publish their exact new-QA union.

    Idempotent for the same ID/content. All expected days must be supplied once,
    contiguous and backed by a published release; current remains unchanged on failure.
    """
    check_environment_deadline()
    _identifier(reading_batch_id)
    if not expected_days or len(set(expected_days)) != len(expected_days):
        raise ReadingBatchError("expected days must be nonempty and unique")
    days = sorted(expected_days)
    dates = [date.fromisoformat(day) for day in days]
    if any((b - a).days != 1 for a, b in zip(dates, dates[1:])):
        raise ReadingBatchError("expected days must be contiguous")
    if len(run_ids) != len(days) or len(set(run_ids)) != len(run_ids):
        raise ReadingBatchError("all expected days require distinct complete releases")
    store = ReadingBatchStore(project_root)
    with store._lock():
        releases = []
        for run_id in run_ids:
            releases.append(_release_delta(store.project_root, run_id))
            check_environment_deadline()
        releases.sort(key=lambda r: r["day"])
        if [r["day"] for r in releases] != days:
            raise ReadingBatchError("release days do not match expected days")
        qas = []
        seen: set[str] = set()
        for release in releases:
            for qa in release["qas"]:
                if qa["qa_id"] in seen:
                    raise ReadingBatchError("new QA ID appears in multiple release deltas")
                seen.add(qa["qa_id"])
                qas.append(qa)
        core = {"schema_version": 1, "status": "published_reading_batch", "reading_batch_id": reading_batch_id,
                "expected_days": days, "run_ids": [r["run_id"] for r in releases],
                "releases": [{k: v for k, v in r.items() if k != "qas"} for r in releases], "qas": qas, "qa_count": len(qas)}
        path = store.entries / f"{reading_batch_id}.json"
        if path.exists():
            existing = store.get(reading_batch_id)
            if {k: v for k, v in existing.items() if k != "created_at"} != core:
                raise ReadingBatchError("reading batch ID already has different immutable content")
            doc = existing
        else:
            doc = {**core, "created_at": now or datetime.now(timezone.utc).isoformat()}
            check_environment_deadline()
            write_json_atomic(path, doc)
        check_environment_deadline()
        write_json_atomic(store.root / "current.json", {"schema_version": 1, "reading_batch_id": reading_batch_id, "sha256": sha256_json(doc)})
        return doc


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a reading batch from complete immutable releases")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--reading-batch-id", required=True)
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--expected-day", action="append", required=True)
    args = parser.parse_args()
    doc = publish_reading_batch(args.project_root, reading_batch_id=args.reading_batch_id, run_ids=args.run_id, expected_days=args.expected_day)
    print(json.dumps({"reading_batch_id": doc["reading_batch_id"], "qa_count": doc["qa_count"], "expected_days": doc["expected_days"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
