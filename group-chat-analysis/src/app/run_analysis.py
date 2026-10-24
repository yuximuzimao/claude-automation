"""Formal deterministic runner for publishing one reviewed analysis batch."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

from src.analysis.analysis_release import (
    AnalysisReleaseError,
    DERIVED_RELEASE_FILES,
    REQUIRED_ARTIFACTS,
    RESULT_SCHEMA_VERSION,
    REVIEW_RECEIPT_SCHEMA_VERSION,
    WORK_PACKAGE_ARTIFACTS,
    WORK_PACKAGE_SCHEMA_VERSION,
    atomic_symlink,
    canonical_batch_sha256,
    ensure_static_symlink,
    fsync_dir,
    parse_current_header,
    project_path,
    sha256_file,
    sha256_json,
    sha256_path,
    validate_review_receipt,
    write_json_atomic,
)
from src.store import BatchStateStore, MessageStore


RUNNER_CONTRACT_VERSION = "analysis-runner-v1"
RUN_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

QualityExecutor = Callable[[Path], dict]
RenderExecutor = Callable[[Path, Path], dict]
Now = Callable[[], str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AnalysisRunner:
    """Publish reviewed semantic artifacts without letting partial work become current."""

    def __init__(
        self,
        project_root: Path,
        *,
        now: Now = utc_now,
        quality_executor: QualityExecutor | None = None,
        render_executor: RenderExecutor | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.runtime = self.project_root / "runtime"
        self.analysis_work = self.runtime / "analysis-work"
        self.analysis_root = self.runtime / "analysis"
        self.runs_root = self.analysis_root / "runs"
        self.releases_root = self.analysis_root / "releases"
        self.current_link = self.analysis_root / "current"
        self.report_link = self.runtime / "reports" / "current-analysis"
        self.state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        self.message_store = MessageStore(self.runtime / "messages" / "messages.jsonl")
        self.current_inbox = self.runtime / "inbox" / "current.md"
        self.now = now
        self.quality_executor = quality_executor or self._run_quality
        self.render_executor = render_executor or self._run_render

    def _work_package_path(self, batch_id: str) -> Path:
        return (
            self.analysis_work
            / "batches"
            / batch_id
            / "analysis-work-package-v1.json"
        )

    def _receipt_path(self, batch_id: str) -> Path:
        return (
            self.analysis_work
            / "batches"
            / batch_id
            / "reviewed-analysis-v1.json"
        )

    def _draft_receipt_path(self, batch_id: str) -> Path:
        return (
            self.analysis_work
            / "batches"
            / batch_id
            / "analysis-review-draft-v1.json"
        )

    def _load_state_for_batch(self, batch_id: str | None) -> tuple[str, dict]:
        state = self.state_store.load()
        if state is None:
            raise AnalysisReleaseError("no active capture batch state exists")
        resolved = batch_id or str(state["batch_id"])
        if state["batch_id"] != resolved:
            raise AnalysisReleaseError("requested batch_id is not the active batch")
        if state["status"] not in {"completed", "analyzed"}:
            raise AnalysisReleaseError("analysis requires a completed or analyzed batch")
        return resolved, state

    def _source_snapshot(self, batch_id: str) -> dict:
        if not self.current_inbox.is_file():
            raise AnalysisReleaseError("completed batch is missing runtime/inbox/current.md")
        current_bytes = self.current_inbox.read_bytes()
        current_text = current_bytes.decode("utf-8")
        inbox_batch_id, message_count = parse_current_header(current_text)
        if inbox_batch_id != batch_id:
            raise AnalysisReleaseError("current.md batch_id does not match active batch")
        records = self.message_store.records_for_batch(batch_id)
        if len(records) != message_count:
            raise AnalysisReleaseError(
                "current.md message_count does not match canonical batch records"
            )
        return {
            "batch_id": batch_id,
            "current_sha256": sha256_file(self.current_inbox),
            "message_count": message_count,
            "canonical_batch_sha256": canonical_batch_sha256(records),
        }

    def create_work_package(
        self,
        batch_id: str | None = None,
        *,
        destination: Path | None = None,
        refresh: bool = False,
    ) -> Path:
        resolved, state = self._load_state_for_batch(batch_id)
        if state["status"] != "completed":
            raise AnalysisReleaseError(
                "analysis work package can only be prepared for a completed batch"
            )
        source = self._source_snapshot(resolved)
        baseline_artifacts = {}
        for key, relative in WORK_PACKAGE_ARTIFACTS.items():
            path = project_path(self.project_root, relative)
            baseline_artifacts[key] = {
                "path": relative,
                "sha256": sha256_path(path),
            }
        core = {
            "schema_version": WORK_PACKAGE_SCHEMA_VERSION,
            "status": "analysis_work_prepared",
            "batch_id": resolved,
            "source": source,
            "baseline_artifacts": baseline_artifacts,
            "contract": {
                "semantic_review_required_before_receipt": True,
                "baseline_hashes_are_analysis_start_state": True,
                "output_artifacts_may_change_after_review": True,
                "work_package_refresh_requires_explicit_flag": True,
            },
        }
        target = destination or self._work_package_path(resolved)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            comparable = {
                key: existing.get(key)
                for key in (
                    "schema_version",
                    "status",
                    "batch_id",
                    "source",
                    "baseline_artifacts",
                    "contract",
                )
            }
            if comparable == core:
                return target
            if not refresh:
                raise AnalysisReleaseError(
                    "analysis work package inputs changed; explicit refresh required"
                )
        document = {
            **core,
            "prepared_at": self.now(),
        }
        write_json_atomic(target, document)
        return target

    def _validated_work_package(self, batch_id: str, source: dict) -> tuple[Path, dict, str]:
        path = self._work_package_path(batch_id)
        if not path.is_file():
            raise AnalysisReleaseError(
                f"analysis work package is missing: {path}"
            )
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("schema_version") != WORK_PACKAGE_SCHEMA_VERSION:
            raise AnalysisReleaseError("unsupported analysis work package schema")
        if document.get("status") != "analysis_work_prepared":
            raise AnalysisReleaseError("analysis work package is not prepared")
        if document.get("batch_id") != batch_id:
            raise AnalysisReleaseError("analysis work package batch_id mismatch")
        if document.get("source") != source:
            raise AnalysisReleaseError(
                "analysis work package source snapshot no longer matches completed batch"
            )
        return path, document, sha256_file(path)

    def create_review_draft(
        self,
        batch_id: str | None = None,
        *,
        destination: Path | None = None,
    ) -> Path:
        resolved, state = self._load_state_for_batch(batch_id)
        if state["status"] != "completed":
            raise AnalysisReleaseError("review draft can only be prepared for completed batch")
        source = self._source_snapshot(resolved)
        work_package_path, _work_package, work_package_sha = (
            self._validated_work_package(resolved, source)
        )
        artifacts = {}
        for key, relative in REQUIRED_ARTIFACTS.items():
            path = project_path(self.project_root, relative)
            artifacts[key] = {
                "path": relative,
                "sha256": sha256_path(path),
            }
        document = {
            "schema_version": REVIEW_RECEIPT_SCHEMA_VERSION,
            "status": "draft",
            "batch_id": resolved,
            "source": {
                "current_sha256": source["current_sha256"],
                "message_count": source["message_count"],
                "canonical_batch_sha256": source["canonical_batch_sha256"],
            },
            "work_package": {
                "path": str(work_package_path.relative_to(self.project_root)),
                "sha256": work_package_sha,
            },
            "artifacts": artifacts,
            "reviewed_at": None,
            "reviewer": None,
            "note": (
                "This draft is not publishable. Semantic analysis must finish first; "
                "then refresh any changed artifact hashes and explicitly set "
                "status=reviewed_analysis_ready, reviewer, and reviewed_at."
            ),
        }
        target = destination or self._draft_receipt_path(resolved)
        write_json_atomic(target, document)
        return target

    def _code_hashes(self) -> dict[str, str]:
        relative_paths = [
            "src/app/run_analysis.py",
            "src/analysis/analysis_release.py",
            "src/analysis/quality.py",
            "src/analysis/first_read_projection.py",
            "src/analysis/reviewed_semantic_state.py",
            "src/analysis/page_builder.py",
            "src/analysis/page_renderer.py",
        ]
        return {
            relative: sha256_file(self.project_root / relative)
            for relative in relative_paths
        }

    @staticmethod
    def _safe_batch_token(batch_id: str) -> str:
        cleaned = RUN_ID_SAFE_RE.sub("-", batch_id).strip("-")
        return (cleaned or "batch")[:48]

    def _run_identity(
        self,
        source: dict,
        receipt_sha256: str,
        artifacts: dict,
        code_hashes: dict,
    ) -> tuple[str, dict]:
        identity = {
            "runner_contract_version": RUNNER_CONTRACT_VERSION,
            "source": source,
            "receipt_sha256": receipt_sha256,
            "artifacts": artifacts,
            "code_hashes": code_hashes,
        }
        digest = sha256_json(identity)
        run_id = f"ar1-{self._safe_batch_token(str(source['batch_id']))}-{digest[:20]}"
        return run_id, identity

    def _manifest_path(self, run_id: str) -> Path:
        return self.runs_root / run_id / "manifest.json"

    def _write_manifest(
        self,
        run_id: str,
        *,
        status: str,
        identity: dict,
        stages: dict,
        error: dict | None = None,
    ) -> None:
        document = {
            "schema_version": "1",
            "run_id": run_id,
            "status": status,
            "updated_at": self.now(),
            "identity": identity,
            "stages": stages,
        }
        if error is not None:
            document["error"] = error
        write_json_atomic(self._manifest_path(run_id), document)

    def _run_quality(self, report_path: Path) -> dict:
        args = [
            sys.executable,
            "-m",
            "src.analysis.quality",
            "--candidates",
            str(self.analysis_work / "silver-candidates-v1.json"),
            "--silver",
            str(self.analysis_work / "silver-knowledge-v1.json"),
            "--topic-dir",
            str(self.analysis_work / "topic-cards-v1"),
            "--chunks-dir",
            str(self.analysis_work / "full-history-chunks"),
            "--corrections",
            str(self.analysis_work / "semantic-correction-queue-v1.json"),
            "--report",
            str(report_path),
        ]
        result = subprocess.run(
            args,
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AnalysisReleaseError(
                f"quality gate command failed with exit code {result.returncode}"
            )
        if not report_path.is_file():
            raise AnalysisReleaseError("quality gate did not produce its report")
        return json.loads(report_path.read_text(encoding="utf-8"))

    def _run_render(self, output: Path, details_dir: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.analysis.page_builder",
                "--output",
                str(output),
                "--details-dir",
                str(details_dir),
            ],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AnalysisReleaseError(
                f"page builder failed with exit code {result.returncode}"
            )
        if not output.is_file():
            raise AnalysisReleaseError("page builder did not produce staged page")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return {}
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _current_release(self) -> tuple[str, dict] | None:
        if not self.current_link.is_symlink():
            if self.current_link.exists():
                raise AnalysisReleaseError("runtime/analysis/current is not a symlink")
            return None
        target = os.readlink(self.current_link)
        release_dir = (self.current_link.parent / target).resolve()
        try:
            release_dir.relative_to(self.releases_root.resolve())
        except ValueError as exc:
            raise AnalysisReleaseError("current analysis pointer escapes releases root") from exc
        result_path = release_dir / "result.json"
        if not result_path.is_file():
            raise AnalysisReleaseError("current analysis release is missing result.json")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        return release_dir.name, result

    def _verify_analyzed_idempotent(self, batch_id: str, source: dict) -> dict:
        current = self._current_release()
        if current is None:
            raise AnalysisReleaseError(
                "batch is analyzed but no formal current analysis release exists"
            )
        run_id, result = current
        if result.get("batch_id") != batch_id:
            raise AnalysisReleaseError(
                "batch is analyzed but current release belongs to another batch"
            )
        if (result.get("source") or {}).get("current_sha256") != source["current_sha256"]:
            raise AnalysisReleaseError(
                "batch is analyzed but current release source hash does not match current.md"
            )
        return {
            "status": "already_analyzed",
            "run_id": run_id,
            "batch_id": batch_id,
            "page": str(self.report_link / "page.html"),
        }

    @staticmethod
    def _quality_is_publishable(report: dict) -> bool:
        quality = report.get("quality") or {}
        return report.get("result") != "FAIL" and quality.get("errors") == 0

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _freeze_release(
        self,
        run_id: str,
        *,
        source: dict,
        receipt: dict,
        receipt_path: Path,
        receipt_sha256: str,
        work_package_path: Path,
        work_package_sha256: str,
        reviewed_artifacts: dict,
        code_hashes: dict,
        quality_report: Path,
        render_summary: dict,
        staged_page: Path,
        staged_details: Path,
    ) -> tuple[Path, dict]:
        self.releases_root.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(
            tempfile.mkdtemp(prefix=f".{run_id}.tmp-", dir=self.releases_root)
        )
        try:
            self._copy_file(staged_page, temp_dir / "page.html")
            if staged_details.exists():
                shutil.copytree(staged_details, temp_dir / "page-v2-details")
            else:
                (temp_dir / "page-v2-details").mkdir()
            self._copy_file(quality_report, temp_dir / "quality.json")
            self._copy_file(
                work_package_path,
                temp_dir / "analysis-work-package-v1.json",
            )
            self._copy_file(
                receipt_path,
                temp_dir / "reviewed-analysis-v1.json",
            )
            if sha256_file(temp_dir / "analysis-work-package-v1.json") != work_package_sha256:
                raise AnalysisReleaseError(
                    "work package changed while release was being frozen"
                )
            if sha256_file(temp_dir / "reviewed-analysis-v1.json") != receipt_sha256:
                raise AnalysisReleaseError(
                    "review receipt changed while release was being frozen"
                )

            frozen: dict[str, dict[str, str]] = {
                "page": {
                    "path": "page.html",
                    "sha256": sha256_file(temp_dir / "page.html"),
                },
                "page_details": {
                    "path": "page-v2-details",
                    "sha256": sha256_path(temp_dir / "page-v2-details"),
                },
                "quality_report": {
                    "path": "quality.json",
                    "sha256": sha256_file(temp_dir / "quality.json"),
                },
                "work_package": {
                    "path": "analysis-work-package-v1.json",
                    "sha256": work_package_sha256,
                },
                "review_receipt": {
                    "path": "reviewed-analysis-v1.json",
                    "sha256": receipt_sha256,
                },
            }
            for key, relative in DERIVED_RELEASE_FILES.items():
                source_path = project_path(self.project_root, relative)
                suffix = source_path.suffix or ".json"
                filename = f"{key}{suffix}"
                destination = temp_dir / filename
                self._copy_file(source_path, destination)
                frozen[key] = {
                    "path": filename,
                    "sha256": sha256_file(destination),
                }

            first_read = json.loads(
                (temp_dir / frozen["first_read_projection"]["path"]).read_text(
                    encoding="utf-8"
                )
            )
            semantic_state = json.loads(
                (temp_dir / frozen["reviewed_semantic_state"]["path"]).read_text(
                    encoding="utf-8"
                )
            )
            quality = json.loads((temp_dir / "quality.json").read_text(encoding="utf-8"))
            result = {
                "schema_version": RESULT_SCHEMA_VERSION,
                "status": "published_analysis_result",
                "run_id": run_id,
                "batch_id": source["batch_id"],
                "runner_contract_version": RUNNER_CONTRACT_VERSION,
                "source": source,
                "review": {
                    "receipt_sha256": receipt_sha256,
                    "work_package": copy.deepcopy(frozen["work_package"]),
                    "reviewed_at": receipt["reviewed_at"],
                    "reviewer": receipt["reviewer"],
                    "artifacts": reviewed_artifacts,
                },
                "code_hashes": code_hashes,
                "quality": {
                    "result": quality.get("result"),
                    "errors": (quality.get("quality") or {}).get("errors"),
                    "warnings": (quality.get("quality") or {}).get("warnings"),
                    "report_sha256": frozen["quality_report"]["sha256"],
                },
                "counts": {
                    "first_read_silver_units": (
                        first_read.get("counts") or {}
                    ).get("first_read_silver_units"),
                    "knowledge_silver_units": (
                        first_read.get("counts") or {}
                    ).get("knowledge_silver_units"),
                    "dossier_absorbed_silver_units": (
                        first_read.get("counts") or {}
                    ).get("dossier_absorbed_silver_units"),
                    "reviewed_semantic_states": (
                        semantic_state.get("counts") or {}
                    ).get("states"),
                },
                "render_summary": render_summary,
                "artifacts": frozen,
            }
            write_json_atomic(temp_dir / "result.json", result)

            release_dir = self.releases_root / run_id
            if release_dir.exists():
                existing = json.loads(
                    (release_dir / "result.json").read_text(encoding="utf-8")
                )
                if existing != result:
                    raise AnalysisReleaseError(
                        "deterministic run_id already exists with different release content"
                    )
                shutil.rmtree(temp_dir)
                return release_dir, existing

            os.replace(temp_dir, release_dir)
            fsync_dir(self.releases_root)
            return release_dir, result
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def _publish_release(self, run_id: str) -> None:
        ensure_static_symlink(self.report_link, "../analysis/current")
        atomic_symlink(self.current_link, f"releases/{run_id}")

    def run(
        self,
        batch_id: str | None = None,
        *,
        receipt_path: Path | None = None,
    ) -> dict:
        resolved, state = self._load_state_for_batch(batch_id)
        source = self._source_snapshot(resolved)

        if state["status"] == "analyzed":
            return self._verify_analyzed_idempotent(resolved, source)

        work_package_path, _work_package, work_package_sha = (
            self._validated_work_package(resolved, source)
        )
        receipt_file = receipt_path or self._receipt_path(resolved)
        if not receipt_file.is_file():
            raise AnalysisReleaseError(
                f"reviewed analysis receipt is missing: {receipt_file}"
            )
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        receipt_sha = sha256_file(receipt_file)
        reviewed_artifacts = validate_review_receipt(
            receipt,
            project_root=self.project_root,
            batch_id=resolved,
            current_sha256=source["current_sha256"],
            message_count=source["message_count"],
        )
        receipt_canonical_sha = (receipt.get("source") or {}).get(
            "canonical_batch_sha256"
        )
        if receipt_canonical_sha != source["canonical_batch_sha256"]:
            raise AnalysisReleaseError("analysis receipt canonical batch hash is stale")
        receipt_work_package = receipt.get("work_package") or {}
        expected_work_path = str(work_package_path.relative_to(self.project_root))
        if receipt_work_package.get("path") != expected_work_path:
            raise AnalysisReleaseError("analysis receipt work package path mismatch")
        if receipt_work_package.get("sha256") != work_package_sha:
            raise AnalysisReleaseError("analysis receipt work package hash is stale")

        code_hashes = self._code_hashes()
        run_id, identity = self._run_identity(
            source,
            receipt_sha,
            reviewed_artifacts,
            code_hashes,
        )
        run_dir = self.runs_root / run_id
        staging = run_dir / "staging"
        quality_path = run_dir / "quality.json"
        staged_page = staging / "page.html"
        staged_details = staging / "page-v2-details"
        stages: dict[str, dict] = {
            "snapshot": {
                "status": "passed",
                "input_sha256": sha256_json(identity),
                "source": source,
            }
        }
        self._write_manifest(
            run_id,
            status="running",
            identity=identity,
            stages=stages,
        )

        current = self._current_release()
        if current is not None and current[0] == run_id:
            result = current[1]
            if result.get("batch_id") != resolved:
                raise AnalysisReleaseError("current release run_id has wrong batch")
            analyzed = self.state_store.mark_analyzed(
                resolved,
                analyzed_at=self.now(),
            )
            stages["publish"] = {
                "status": "recovered",
                "current_target": f"releases/{run_id}",
                "state_status": analyzed["status"],
            }
            self._write_manifest(
                run_id,
                status="published",
                identity=identity,
                stages=stages,
            )
            return {
                "status": "recovered_publish",
                "run_id": run_id,
                "batch_id": resolved,
                "page": str(self.report_link / "page.html"),
            }

        try:
            quality = self.quality_executor(quality_path)
            if not self._quality_is_publishable(quality):
                raise AnalysisReleaseError("analysis quality gate has blocking errors")
            stages["quality"] = {
                "status": "passed",
                "input_artifacts_sha256": sha256_json(reviewed_artifacts),
                "output_sha256": sha256_file(quality_path),
                "result": quality.get("result"),
                "errors": (quality.get("quality") or {}).get("errors"),
                "warnings": (quality.get("quality") or {}).get("warnings"),
            }
            self._write_manifest(
                run_id,
                status="running",
                identity=identity,
                stages=stages,
            )

            if staging.exists():
                shutil.rmtree(staging)
            staged_details.mkdir(parents=True, exist_ok=True)
            render_summary = self.render_executor(staged_page, staged_details)
            stages["render"] = {
                "status": "passed",
                "input_sha256": sha256_json({
                    "reviewed_artifacts": reviewed_artifacts,
                    "quality_sha256": stages["quality"]["output_sha256"],
                }),
                "page_sha256": sha256_file(staged_page),
                "details_sha256": sha256_path(staged_details),
                "summary": render_summary,
            }
            self._write_manifest(
                run_id,
                status="running",
                identity=identity,
                stages=stages,
            )

            release_dir, result = self._freeze_release(
                run_id,
                source=source,
                receipt=receipt,
                receipt_path=receipt_file,
                receipt_sha256=receipt_sha,
                work_package_path=work_package_path,
                work_package_sha256=work_package_sha,
                reviewed_artifacts=reviewed_artifacts,
                code_hashes=code_hashes,
                quality_report=quality_path,
                render_summary=render_summary,
                staged_page=staged_page,
                staged_details=staged_details,
            )
            stages["release"] = {
                "status": "passed",
                "result_sha256": sha256_file(release_dir / "result.json"),
                "release_path": str(release_dir.relative_to(self.project_root)),
            }
            self._write_manifest(
                run_id,
                status="running",
                identity=identity,
                stages=stages,
            )

            # One atomic symlink is the formal publication switch.  Only after this
            # succeeds is the capture batch allowed to enter analyzed state.
            self._publish_release(run_id)
            analyzed = self.state_store.mark_analyzed(
                resolved,
                analyzed_at=self.now(),
            )
            stages["publish"] = {
                "status": "passed",
                "current_target": f"releases/{run_id}",
                "state_status": analyzed["status"],
            }
            self._write_manifest(
                run_id,
                status="published",
                identity=identity,
                stages=stages,
            )
            return {
                "status": "published",
                "run_id": run_id,
                "batch_id": resolved,
                "counts": result["counts"],
                "quality": result["quality"],
                "page": str(self.report_link / "page.html"),
            }
        except Exception as exc:
            self._write_manifest(
                run_id,
                status="failed",
                identity=identity,
                stages=stages,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            raise

    def rollback_to(self, run_id: str) -> dict:
        if not run_id or RUN_ID_SAFE_RE.search(run_id):
            raise AnalysisReleaseError("invalid analysis run_id")
        release_dir = self.releases_root / run_id
        result_path = release_dir / "result.json"
        if not result_path.is_file():
            raise AnalysisReleaseError(f"analysis release does not exist: {run_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("run_id") != run_id:
            raise AnalysisReleaseError("release result run_id does not match directory")
        for row in (result.get("artifacts") or {}).values():
            if not isinstance(row, dict):
                raise AnalysisReleaseError("release artifact index is invalid")
            relative = row.get("path")
            expected = row.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected, str):
                raise AnalysisReleaseError("release artifact index is incomplete")
            path = release_dir / relative
            if sha256_path(path) != expected:
                raise AnalysisReleaseError(
                    f"release artifact hash mismatch during rollback: {relative}"
                )
        ensure_static_symlink(self.report_link, "../analysis/current")
        atomic_symlink(self.current_link, f"releases/{run_id}")
        return {
            "status": "rolled_back",
            "run_id": run_id,
            "batch_id": result.get("batch_id"),
            "page": str(self.report_link / "page.html"),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--batch-id")
    parser.add_argument("--receipt", type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare-work", action="store_true")
    action.add_argument("--prepare-review", action="store_true")
    action.add_argument("--rollback-to")
    parser.add_argument("--refresh-work", action="store_true")
    args = parser.parse_args()
    if args.refresh_work and not args.prepare_work:
        parser.error("--refresh-work requires --prepare-work")

    runner = AnalysisRunner(args.project_root)
    if args.rollback_to:
        result = runner.rollback_to(args.rollback_to)
    elif args.prepare_work:
        path = runner.create_work_package(
            args.batch_id,
            refresh=args.refresh_work,
        )
        result = {
            "status": "analysis_work_prepared",
            "path": str(path),
        }
    elif args.prepare_review:
        path = runner.create_review_draft(args.batch_id)
        result = {
            "status": "review_draft_created",
            "path": str(path),
        }
    else:
        result = runner.run(args.batch_id, receipt_path=args.receipt)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
