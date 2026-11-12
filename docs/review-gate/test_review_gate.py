import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


MODULE = Path(__file__).with_name("review_gate.py")
gate = None
if MODULE.exists():
    spec = importlib.util.spec_from_file_location("review_gate", MODULE)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)


class ReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(gate, "review_gate.py is not implemented yet")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write("worker.py", "base\n")
        self.write("rules.md", "current rules\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.request = {"base": self.base, "requirements": "Original task and acceptance criteria", "files": ["worker.py"], "context": ["rules.md"]}

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                   GIT_TERMINAL_PROMPT="0")
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null",
                                        "-c", "core.fsmonitor=false", *args], cwd=self.repo,
                                       env=env, text=True, stderr=subprocess.PIPE)

    def write(self, name, content):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def candidate(self, work):
        claim = {"files": {"worker.py": {"index": gate._index(self.repo, "worker.py"),
                                         "worktree": gate._worktree(self.repo, "worker.py")}}, "context": []}
        return gate.create_candidate(self.repo, work, claim)

    def checks(self):
        return [{"name": "isolated test", "result": "passed", "evidence": "test output"}]

    def test_committed_staged_unstaged_and_untracked_versions_are_present(self):
        self.write("worker.py", "committed\n")
        self.git("add", "worker.py")
        self.git("commit", "-qm", "change")
        self.write("worker.py", "staged\n")
        self.git("add", "worker.py")
        self.write("worker.py", "working\n")
        self.write("new.py", "new untracked\n")
        self.request["files"].append("new.py")
        snap = gate.snapshot(self.repo, self.request)
        versions = snap["files"]["worker.py"]
        self.assertEqual([versions[k]["text"] for k in ("base", "head", "index", "worktree")],
                         ["base\n", "committed\n", "staged\n", "working\n"])
        self.assertIsNone(snap["files"]["new.py"]["base"])
        self.assertEqual(snap["files"]["new.py"]["worktree"]["text"], "new untracked\n")

    def test_snapshot_changes_invalidate_receipt(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "changed\n")
        candidate = self.candidate(work)
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})
        gate.verify_candidate(self.repo, work, candidate, receipt, [], self.checks())
        self.write("worker.py", "fixed\n")
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, receipt, [], self.checks())

    def test_staging_and_context_changes_also_invalidate(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "changed\n")
        candidate = self.candidate(work)
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})
        self.git("add", "worker.py")
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, receipt, [], self.checks())
        candidate = self.candidate(work)
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})
        self.write("rules.md", "changed rule\n")
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, receipt, [], self.checks())

    def test_mutation_during_review_rejects_result(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "changed\n")
        candidate = self.candidate(work)
        def reviewer(_):
            self.write("worker.py", "changed during review\n")
            return {"findings": []}
        with self.assertRaises(gate.GateError):
            gate.review_candidate(self.repo, work, candidate, reviewer)

    def test_important_findings_block_without_evidence_based_refutation(self):
        finding = {"severity": "important", "file": "worker.py", "line": 1,
                   "trigger": "two concurrent starts", "impact": "duplicate execution", "evidence": "no lock",
                   "recommendation": "serialize"}
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "changed\n")
        candidate = self.candidate(work)
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": [finding]})
        with self.assertRaisesRegex(gate.GateError, "finding"):
            gate.verify_candidate(self.repo, work, candidate, receipt, [], self.checks())
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, receipt,
                                  [{"index": 0, "snapshot": candidate["id"], "reason": "wrong", "evidence": ""}], self.checks())
        gate.verify_candidate(self.repo, work, candidate, receipt,
                              [{"index": 0, "snapshot": candidate["id"], "reason": "caller is serialized", "evidence": "queue.py:10"}], self.checks())

    def test_malformed_or_failed_review_is_not_a_pass(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "changed\n")
        candidate = self.candidate(work)
        for result in ({}, {"findings": None}, {"findings": [{}]}, {"findings": [{"severity": "important"}]}):
            with self.subTest(result=result), self.assertRaises(gate.GateError):
                gate.review_candidate(self.repo, work, candidate, lambda _: result)

    def test_symlink_refused_binary_fingerprinted(self):
        (self.repo / "link.py").symlink_to(self.repo / "worker.py")
        self.request["files"] = ["link.py"]
        with self.assertRaises(gate.GateError):
            gate.snapshot(self.repo, self.request)
        (self.repo / "binary.py").write_bytes(b"\xff\x00")
        self.request["files"] = ["binary.py"]
        value = gate.snapshot(self.repo, self.request)["files"]["binary.py"]["worktree"]
        self.assertEqual(value["kind"], "binary")
        self.assertEqual(value["size"], 2)
        self.assertNotIn("text", value)

    def test_reviewer_disables_discovered_skill_instructions_and_tools(self):
        def invoke(argv, **kwargs):
            self.assertIn("skills.include_instructions=false", argv)
            self.assertIn("skills.bundled.enabled=false", argv)
            for feature in ("hooks", "memories", "plugins", "multi_agent", "shell_tool", "unified_exec", "code_mode_host"):
                self.assertIn(feature, argv)
                self.assertEqual(argv[argv.index(feature) - 1], "--disable")
            self.assertIn("--ignore-user-config", argv)
            self.assertIn("read-only", argv)
            Path(argv[argv.index("-o") + 1]).write_text('{"findings": []}')
            return mock.Mock(returncode=0, stderr="")
        with mock.patch.object(gate.subprocess, "run", side_effect=invoke):
            self.assertEqual(gate.call_reviewer({}), {"findings": []})


class DeliveryLifecycleTests(unittest.TestCase):
    setUp = ReviewGateTests.setUp
    git = ReviewGateTests.git
    write = ReviewGateTests.write

    def claim(self, names):
        return {"files": {name: {"index": gate._index(self.repo, name),
                                  "worktree": gate._worktree(self.repo, name)} for name in names}, "context": []}

    def test_development_inspection_neat_and_historical_runner_do_not_launch_review(self):
        self.write("farm/runner.py", "historical paused changes\n")
        for activity in ("development", "auto", "inspection", "neat", "display"):
            with self.subTest(activity=activity):
                self.assertFalse(gate.review_required(activity))
                with self.assertRaises(gate.GateError):
                    gate.capture_work(self.repo, self.request, activity)

    def test_farm_behavior_change_review_and_delivery_exclude_other_dirty_files(self):
        self.write("worker.py", "base\nold user change\n")
        self.write("other/historical.py", "paused historical dirty file\n")
        self.assertTrue(gate.review_required("unattended_change"))
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "base\nold user change\nnew task change\n")
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        self.assertEqual(list(candidate["files"]), ["worker.py"])
        patch = candidate["files"]["worker.py"]["worktree_diff"]
        self.assertIn("+new task change", patch)
        self.assertNotIn("+old user change", patch)
        self.assertNotIn("other/historical.py", json.dumps(candidate))

    def test_first_unattended_run_reviews_complete_declared_runtime_even_without_changes(self):
        self.assertTrue(gate.review_required("unattended_first_run"))
        work = gate.capture_work(self.repo, self.request, "unattended_first_run")
        with self.assertRaises(gate.GateError):
            gate.create_candidate(self.repo, work, {"files": {}, "context": []})
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        self.assertEqual(candidate["files"]["worker.py"]["worktree"]["text"], "base\n")
        self.assertEqual(candidate["files"]["worker.py"]["worktree_diff"], "")

    def test_planned_but_unchanged_dependency_can_be_explicit_review_context(self):
        self.write("policy.json", '{"stop_on_error": true}\n')
        self.write("unused.py", "historical and unnecessary\n")
        self.request["files"].extend(["policy.json", "unused.py"])
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "uses policy.json\n")
        claim = self.claim(["worker.py"])
        claim["context"] = ["policy.json"]
        candidate = gate.create_candidate(self.repo, work, claim)
        self.assertEqual(candidate["context"]["policy.json"]["text"], '{"stop_on_error": true}\n')
        self.assertNotIn("policy.json", candidate["files"])
        self.assertNotIn("unused.py", candidate["context"])
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})
        self.write("policy.json", '{"stop_on_error": false}\n')
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, receipt, [],
                                  [{"name": "test", "result": "passed", "evidence": "output"}])

    def test_unregistered_unclaimed_and_unexpected_changes_block_candidate(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "our task edit\n")
        claim = self.claim(["worker.py"])
        with self.assertRaises(gate.GateError):
            gate.create_candidate(self.repo, work, {"files": {}, "context": []})
        self.write("worker.py", "our task edit\nconcurrent other edit\n")
        with self.assertRaises(gate.GateError):
            gate.create_candidate(self.repo, work, claim)
        with self.assertRaises(gate.GateError):
            gate.create_candidate(self.repo, work, {"files": {"new-unregistered.py": {"index": None, "worktree": None}}, "context": []})

    def test_new_file_requires_start_registration_and_head_change_fails_closed(self):
        self.request["files"].append("new.py")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("new.py", "new task file\n")
        candidate = gate.create_candidate(self.repo, work, self.claim(["new.py"]))
        self.assertIsNone(candidate["files"]["new.py"]["start_worktree"])
        self.git("add", "new.py")
        self.git("commit", "-qm", "concurrent commit")
        with self.assertRaises(gate.GateError):
            gate.create_candidate(self.repo, work, self.claim(["new.py"]))

    def test_work_requires_actual_repository_root(self):
        child = self.repo / "nested"
        child.mkdir()
        self.request["context"] = []
        with self.assertRaises(gate.GateError):
            gate.capture_work(child, self.request, "unattended_change")

    def test_candidate_diff_separates_lines_without_trailing_newlines(self):
        self.write("worker.py", "old without newline")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "new without newline")
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        patch = candidate["files"]["worker.py"]["worktree_diff"]
        self.assertIn("-old without newline\n", patch)
        self.assertIn("+new without newline\n", patch)
        self.assertIn("\\ No newline at end of file", patch)

    def test_staging_preexisting_dirty_content_cannot_be_claimed_as_task_change(self):
        self.write("historical.py", "pre-existing untracked user content\n")
        self.request["files"] = ["historical.py"]
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("historical.py", "pre-existing untracked user content\nnew task edit\n")
        self.git("add", "historical.py")
        with self.assertRaisesRegex(gate.GateError, "暂存"):
            gate.create_candidate(self.repo, work, self.claim(["historical.py"]))

    def test_context_change_after_work_start_blocks_candidate(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "task change\n")
        self.write("rules.md", "changed rule without candidate attribution\n")
        with self.assertRaisesRegex(gate.GateError, "上下文"):
            gate.create_candidate(self.repo, work, self.claim(["worker.py"]))

    def test_context_index_change_blocks_even_when_worktree_is_unchanged(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "task change\n")
        self.write("rules.md", "unrelated staged rule\n")
        self.git("add", "rules.md")
        self.write("rules.md", "current rules\n")
        with self.assertRaisesRegex(gate.GateError, "上下文"):
            gate.create_candidate(self.repo, work, self.claim(["worker.py"]))

    def test_dirty_context_requires_explicitly_registered_promotion(self):
        self.write("rules.md", "pre-existing dirty rule\n")
        with self.assertRaisesRegex(gate.GateError, "上下文"):
            gate.capture_work(self.repo, self.request, "unattended_change")
        self.request["context"] = []
        self.request["files"].append("rules.md")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "task change\n")
        claim = self.claim(["worker.py"])
        claim["context"] = ["rules.md"]
        candidate = gate.create_candidate(self.repo, work, claim)
        self.assertEqual(candidate["context"]["rules.md"]["text"], "pre-existing dirty rule\n")

    def test_missing_receipt_path_does_not_start_reviewer(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "our task edit\n")
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        work_path = Path(self.temp.name) / "work.json"
        candidate_path = Path(self.temp.name) / "candidate.json"
        work_path.write_text(json.dumps(work))
        candidate_path.write_text(json.dumps(candidate))
        argv = ["review_gate.py", "review", "--repo", str(self.repo), "--work", str(work_path),
                "--candidate", str(candidate_path)]
        with mock.patch.object(gate.sys, "argv", argv), mock.patch.object(gate, "call_reviewer") as reviewer:
            self.assertEqual(gate.main(), 1)
            reviewer.assert_not_called()

    def test_candidate_changes_during_review_and_missing_review_fail_closed(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "our task edit\n")
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        def changed(_):
            self.write("worker.py", "changed during review\n")
            return {"findings": []}
        with self.assertRaises(gate.GateError):
            gate.review_candidate(self.repo, work, candidate, changed)
        with self.assertRaises(gate.GateError):
            gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})

    def test_unavailable_reviewer_important_finding_and_skipped_verification_block(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "our task edit\n")
        candidate = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        def unavailable(_):
            raise gate.GateError("reviewer unavailable")
        with self.assertRaises(gate.GateError):
            gate.review_candidate(self.repo, work, candidate, unavailable)
        finding = {"severity": "important", "file": "worker.py", "line": 1,
                   "trigger": "two starts", "impact": "duplicate execution", "evidence": "no lock", "recommendation": "serialize"}
        blocked = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": [finding]})
        checks = [{"name": "isolated test", "result": "passed", "evidence": "test output"}]
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, candidate, blocked, [], checks)
        receipt = gate.review_candidate(self.repo, work, candidate, lambda _: {"findings": []})
        with self.assertRaises(gate.GateError):
            gate.final_check(self.repo, work, candidate, receipt, [], None)
        verification = gate.verify_candidate(self.repo, work, candidate, receipt, [], checks)
        gate.final_check(self.repo, work, candidate, receipt, [], verification)
        self.write("worker.py", "changed after verification\n")
        with self.assertRaises(gate.GateError):
            gate.final_check(self.repo, work, candidate, receipt, [], verification)

    def test_revision_requires_new_candidate_and_new_review(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("worker.py", "unsafe edit\n")
        first = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        finding = {"severity": "important", "file": "worker.py", "line": 1, "trigger": "repeat",
                   "impact": "duplicate", "evidence": "no lock", "recommendation": "lock"}
        first_review = gate.review_candidate(self.repo, work, first, lambda _: {"findings": [finding]})
        checks = [{"name": "isolation", "result": "passed", "evidence": "fixture output"}]
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, first, first_review, [], checks)
        self.write("worker.py", "fixed edit\n")
        second = gate.create_candidate(self.repo, work, self.claim(["worker.py"]))
        self.assertNotEqual(first["id"], second["id"])
        with self.assertRaises(gate.GateError):
            gate.verify_candidate(self.repo, work, second, first_review, [], checks)
        second_review = gate.review_candidate(self.repo, work, second, lambda _: {"findings": []})
        verification = gate.verify_candidate(self.repo, work, second, second_review, [], checks)
        gate.final_check(self.repo, work, second, second_review, [], verification)


class FixtureIsolationTests(unittest.TestCase):
    def test_fixture_git_does_not_run_user_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hooks = root / "hooks"
            hooks.mkdir()
            hook = hooks / "pre-commit"
            hook.write_text('#!/bin/sh\n: > "$REVIEW_GATE_TEST_MARKER"\n')
            hook.chmod(0o700)
            config = root / "gitconfig"
            config.write_text(f'[core]\n  hooksPath = "{hooks}"\n')
            marker = root / "executed"
            fixture = ReviewGateTests("test_snapshot_changes_invalidate_receipt")
            self.addCleanup(fixture.doCleanups)
            with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config), "REVIEW_GATE_TEST_MARKER": str(marker)}):
                fixture.setUp()
            self.assertFalse(marker.exists(), "fixture executed the user's pre-commit hook")


if __name__ == "__main__":
    unittest.main()
