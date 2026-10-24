from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.analysis.analysis_release import (
    AnalysisReleaseError,
    REQUIRED_ARTIFACTS,
    WORK_PACKAGE_ARTIFACTS,
    sha256_path,
    write_json_atomic,
)
from src.app.run_analysis import AnalysisRunner
from src.store import (
    BatchStateStore,
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageStore,
    StateError,
)
from src.store.finalize import finalize_batch


def records(batch_id: str = "batch-1") -> list[dict[str, object]]:
    rows = []
    for sequence, text in enumerate(("older", "newer")):
        rows.append({
            "schema_version": MESSAGE_SCHEMA_VERSION,
            "record_id": f"{batch_id}:group-a:{sequence}",
            "batch_id": batch_id,
            "group_key": "group-a",
            "group_display": "测试群",
            "sequence": sequence,
            "sender_display": "甲",
            "timestamp": None,
            "timestamp_text": f"09:0{sequence}",
            "message_type": "text",
            "content_text": text,
            "ocr_confidence": 1.0,
            "observed_at": "2026-01-01T00:00:00Z",
            "source": MESSAGE_SOURCE,
            "capture_refs": [],
        })
    return rows


class AnalysisRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.runtime = self.root / "runtime"
        self.work = self.runtime / "analysis-work"
        self._seed_completed_batch()
        self._seed_analysis_artifacts()

        self.clock = iter([
            "2026-01-01T01:00:00Z",
            "2026-01-01T01:00:01Z",
            "2026-01-01T01:00:02Z",
            "2026-01-01T01:00:03Z",
            "2026-01-01T01:00:04Z",
            "2026-01-01T01:00:05Z",
            "2026-01-01T01:00:06Z",
            "2026-01-01T01:00:07Z",
            "2026-01-01T01:00:08Z",
            "2026-01-01T01:00:09Z",
            "2026-01-01T01:00:10Z",
            "2026-01-01T01:00:11Z",
            "2026-01-01T01:00:12Z",
            "2026-01-01T01:00:13Z",
            "2026-01-01T01:00:14Z",
            "2026-01-01T01:00:15Z",
            "2026-01-01T01:00:16Z",
            "2026-01-01T01:00:17Z",
            "2026-01-01T01:00:18Z",
            "2026-01-01T01:00:19Z",
        ])

    def _now(self) -> str:
        return next(self.clock)

    def _seed_completed_batch(self) -> None:
        state = BatchStateStore(self.runtime / "state" / "batch-state.json")
        messages = MessageStore(self.runtime / "messages" / "messages.jsonl")
        state.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a"],
        )
        state.begin_capture(
            "batch-1",
            "group-a",
            0,
            mode="current",
            started_at="2026-01-01T00:01:00Z",
        )
        state.record_page(
            "batch-1",
            "group-a",
            0,
            updated_at="2026-01-01T00:01:00Z",
        )
        state.mark_group_capture_complete(
            "batch-1",
            "group-a",
            completed_at="2026-01-01T00:01:30Z",
        )
        finalize_batch(
            state_store=state,
            message_store=messages,
            batch_id="batch-1",
            records=records(),
            completed_at="2026-01-01T00:02:00Z",
            current_destination=self.runtime / "inbox" / "current.md",
        )

    def _seed_analysis_artifacts(self) -> None:
        artifacts = {**WORK_PACKAGE_ARTIFACTS, **REQUIRED_ARTIFACTS}
        for key, relative in artifacts.items():
            path = self.root / relative
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == ".json":
                    path.write_text("{}\n", encoding="utf-8")
                else:
                    path.write_text(f"{key}\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / "fixture.txt").write_text(f"{key}\n", encoding="utf-8")

        # These are frozen into each release after render.
        (self.work / "silver-candidates-v1.json").write_text(
            json.dumps({"candidates": []}) + "\n", encoding="utf-8"
        )
        (self.work / "silver-knowledge-v1.json").write_text(
            json.dumps({"units": []}) + "\n", encoding="utf-8"
        )
        (self.work / "infinite-dossier-v1.json").write_text(
            json.dumps({"sections": []}) + "\n", encoding="utf-8"
        )

    def _runner(self, *, quality=None, render=None) -> AnalysisRunner:
        runner = AnalysisRunner(
            self.root,
            now=self._now,
            quality_executor=quality or self._quality_ok,
            render_executor=render or self._render_ok,
        )
        runner._code_hashes = lambda: {"test": "a" * 64}
        return runner

    def _quality_ok(self, report_path: Path) -> dict:
        report = {
            "result": "PASS_WITH_WARNINGS",
            "quality": {"errors": 0, "warnings": 1},
            "counts": {},
        }
        write_json_atomic(report_path, report)
        return report

    def _render_ok(self, output: Path, details: Path) -> dict:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<html>release</html>\n", encoding="utf-8")
        details.mkdir(parents=True, exist_ok=True)
        (details / "T1.html").write_text("<html>detail</html>\n", encoding="utf-8")
        write_json_atomic(
            self.work / "first-read-projection-v1.json",
            {
                "counts": {
                    "first_read_silver_units": 3,
                    "knowledge_silver_units": 2,
                    "dossier_absorbed_silver_units": 1,
                }
            },
        )
        write_json_atomic(
            self.work / "reviewed-semantic-state-v1.json",
            {"counts": {"states": 4}},
        )
        return {"effective_v3_queue": 3, "effective_v3_knowledge": 2}

    def _review_receipt(self, runner: AnalysisRunner) -> Path:
        runner.create_work_package("batch-1")
        draft = runner.create_review_draft("batch-1")
        document = json.loads(draft.read_text(encoding="utf-8"))
        document["status"] = "reviewed_analysis_ready"
        document["reviewed_at"] = "2026-01-01T00:30:00Z"
        document["reviewer"] = "test-reviewer"
        target = self.work / "batches" / "batch-1" / "reviewed-analysis-v1.json"
        write_json_atomic(target, document)
        return target

    def test_work_package_is_idempotent_and_binds_starting_baseline(self) -> None:
        runner = self._runner()
        first = runner.create_work_package("batch-1")
        first_bytes = first.read_bytes()
        second = runner.create_work_package("batch-1")

        self.assertEqual(first, second)
        self.assertEqual(second.read_bytes(), first_bytes)
        package = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual(package["status"], "analysis_work_prepared")
        self.assertEqual(package["batch_id"], "batch-1")
        self.assertIn("question_registry", package["baseline_artifacts"])

    def test_changed_baseline_requires_explicit_work_package_refresh(self) -> None:
        runner = self._runner()
        package = runner.create_work_package("batch-1")
        before = json.loads(package.read_text(encoding="utf-8"))
        before_sha = before["baseline_artifacts"]["silver_knowledge"]["sha256"]
        (self.work / "silver-knowledge-v1.json").write_text(
            json.dumps({"units": [{"knowledge_id": "new"}]}) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(AnalysisReleaseError, "explicit refresh"):
            runner.create_work_package("batch-1")

        refreshed = runner.create_work_package("batch-1", refresh=True)
        self.assertEqual(refreshed, package)
        document = json.loads(refreshed.read_text(encoding="utf-8"))
        after_sha = document["baseline_artifacts"]["silver_knowledge"]["sha256"]
        self.assertNotEqual(after_sha, before_sha)

    def test_review_draft_requires_prepared_work_package(self) -> None:
        runner = self._runner()
        with self.assertRaisesRegex(AnalysisReleaseError, "work package is missing"):
            runner.create_review_draft("batch-1")

    def test_publish_marks_analyzed_only_after_release_is_current(self) -> None:
        runner = self._runner()
        self._review_receipt(runner)

        result = runner.run("batch-1")

        self.assertEqual(result["status"], "published")
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "analyzed")
        self.assertTrue((self.runtime / "analysis" / "current").is_symlink())
        self.assertTrue((self.runtime / "reports" / "current-analysis").is_symlink())
        page = self.runtime / "reports" / "current-analysis" / "page.html"
        self.assertEqual(page.read_text(encoding="utf-8"), "<html>release</html>\n")
        release = self.runtime / "analysis" / "releases" / result["run_id"]
        frozen = json.loads((release / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["counts"]["first_read_silver_units"], 3)
        self.assertTrue((release / "analysis-work-package-v1.json").is_file())
        self.assertTrue((release / "reviewed-analysis-v1.json").is_file())
        self.assertEqual(
            frozen["review"]["work_package"]["path"],
            "analysis-work-package-v1.json",
        )

    def test_quality_failure_leaves_batch_completed_and_no_current_release(self) -> None:
        def quality_fail(report_path: Path) -> dict:
            report = {
                "result": "FAIL",
                "quality": {"errors": 1, "warnings": 0},
            }
            write_json_atomic(report_path, report)
            return report

        runner = self._runner(quality=quality_fail)
        self._review_receipt(runner)

        with self.assertRaisesRegex(AnalysisReleaseError, "quality gate"):
            runner.run("batch-1")

        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")
        self.assertFalse((self.runtime / "analysis" / "current").exists())
        manifests = list((self.runtime / "analysis" / "runs").glob("*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")

    def test_render_failure_does_not_publish_partial_page(self) -> None:
        def render_fail(output: Path, details: Path) -> dict:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("partial", encoding="utf-8")
            raise RuntimeError("render crash")

        runner = self._runner(render=render_fail)
        self._review_receipt(runner)

        with self.assertRaisesRegex(RuntimeError, "render crash"):
            runner.run("batch-1")

        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")
        self.assertFalse((self.runtime / "analysis" / "current").exists())
        self.assertFalse((self.runtime / "reports" / "current-analysis").exists())

    def test_review_receipt_rejects_changed_work_package(self) -> None:
        runner = self._runner()
        receipt = self._review_receipt(runner)
        package = runner._work_package_path("batch-1")
        document = json.loads(package.read_text(encoding="utf-8"))
        document["prepared_at"] = "2026-01-01T09:09:09Z"
        write_json_atomic(package, document)

        with self.assertRaisesRegex(AnalysisReleaseError, "work package hash is stale"):
            runner.run("batch-1", receipt_path=receipt)

        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")

    def test_review_receipt_rejects_changed_work_package(self) -> None:
        runner = self._runner()
        receipt = self._review_receipt(runner)
        package = runner._work_package_path("batch-1")
        document = json.loads(package.read_text(encoding="utf-8"))
        document["prepared_at"] = "2026-01-01T00:59:59Z"
        write_json_atomic(package, document)

        with self.assertRaisesRegex(AnalysisReleaseError, "work package hash is stale"):
            runner.run("batch-1", receipt_path=receipt)

        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")

    def test_review_receipt_rejects_changed_artifact(self) -> None:
        runner = self._runner()
        receipt = self._review_receipt(runner)
        (self.work / "silver-knowledge-v1.json").write_text(
            json.dumps({"units": [{"knowledge_id": "changed"}]}) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(AnalysisReleaseError, "changed after review"):
            runner.run("batch-1", receipt_path=receipt)

        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")

    def test_second_run_is_idempotent(self) -> None:
        runner = self._runner()
        self._review_receipt(runner)
        first = runner.run("batch-1")
        releases_before = sorted((self.runtime / "analysis" / "releases").iterdir())

        second = runner.run("batch-1")

        self.assertEqual(second["status"], "already_analyzed")
        self.assertEqual(second["run_id"], first["run_id"])
        releases_after = sorted((self.runtime / "analysis" / "releases").iterdir())
        self.assertEqual(releases_after, releases_before)

    def test_crash_after_current_switch_can_roll_forward_without_rebuild(self) -> None:
        runner = self._runner()
        self._review_receipt(runner)

        original_mark = runner.state_store.mark_analyzed
        calls = {"count": 0}

        def fail_once(batch_id: str, *, analyzed_at: str):
            calls["count"] += 1
            if calls["count"] == 1:
                raise StateError("simulated state write crash")
            return original_mark(batch_id, analyzed_at=analyzed_at)

        runner.state_store.mark_analyzed = fail_once
        with self.assertRaisesRegex(StateError, "simulated"):
            runner.run("batch-1")

        self.assertTrue((self.runtime / "analysis" / "current").is_symlink())
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")

        recovered = runner.run("batch-1")
        self.assertEqual(recovered["status"], "recovered_publish")
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "analyzed")

    def test_rollback_switches_formal_current_release(self) -> None:
        runner = self._runner()
        self._review_receipt(runner)
        first = runner.run("batch-1")
        first_release = self.runtime / "analysis" / "releases" / first["run_id"]

        # Create a second valid immutable release fixture to exercise pointer rollback.
        second_id = "ar1-batch-2-" + "b" * 20
        second_release = self.runtime / "analysis" / "releases" / second_id
        second_release.mkdir(parents=True)
        for child in first_release.iterdir():
            if child.name == "result.json":
                continue
            if child.is_dir():
                import shutil
                shutil.copytree(child, second_release / child.name)
            else:
                (second_release / child.name).write_bytes(child.read_bytes())
        second_result = json.loads(
            (first_release / "result.json").read_text(encoding="utf-8")
        )
        second_result["run_id"] = second_id
        second_result["batch_id"] = "batch-2"
        write_json_atomic(second_release / "result.json", second_result)
        from src.analysis.analysis_release import atomic_symlink
        atomic_symlink(
            self.runtime / "analysis" / "current",
            f"releases/{second_id}",
        )

        rolled = runner.rollback_to(first["run_id"])

        self.assertEqual(rolled["status"], "rolled_back")
        self.assertEqual(
            (self.runtime / "reports" / "current-analysis" / "page.html").read_text(
                encoding="utf-8"
            ),
            "<html>release</html>\n",
        )
        self.assertEqual(
            (self.runtime / "analysis" / "current").resolve(),
            first_release.resolve(),
        )


if __name__ == "__main__":
    unittest.main()
