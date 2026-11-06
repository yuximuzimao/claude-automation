import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


MODULE = Path(__file__).with_name("review_gate.py")
spec = importlib.util.spec_from_file_location("review_gate_delivery", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.write("farm/worker.py", "def run():\n    return False\n")
        self.write("rules.md", "offline fixture\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.request = {"base": self.git("rev-parse", "HEAD").strip(), "requirements": "Implement the requested change",
                        "files": ["farm/worker.py"], "context": ["rules.md"]}
        self.policy = {"version": 1, "required_code_patterns": [
            {"pattern": r"(?i)\b(?:pyautogui\.click|retry|stop_worker|switch_account|queue\.put)\s*\(",
             "reason": "unattended execution"}], "guidance": []}

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                   GIT_TERMINAL_PROMPT="0")
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
                                       cwd=self.repo, env=env, text=True, stderr=subprocess.PIPE)

    def write(self, name, text):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def claim(self, name="farm/worker.py"):
        return {"files": {name: {"index": gate._index(self.repo, name),
                                 "worktree": gate._worktree(self.repo, name)}}, "context": []}

    def test_baseline_inventory_excludes_unchanged_history_but_blocks_new_unregistered_changes(self):
        self.write("other/old.py", "old dirty work\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    return True\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        self.assertNotIn("other/old.py", json.dumps(candidate))
        self.write("other/old.py", "changed after work started\n")
        with self.assertRaisesRegex(gate.GateError, "范围外"):
            gate.create_candidate(self.repo, work, self.claim())

    def test_new_unregistered_path_is_not_silently_delivered(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    return True\n")
        self.write("other/unregistered.py", "new unknown change\n")
        with self.assertRaisesRegex(gate.GateError, "范围外"):
            gate.create_candidate(self.repo, work, self.claim())

    def test_outside_index_change_is_detected_even_if_status_and_worktree_match(self):
        self.write("other.py", "base\n")
        self.git("add", "other.py")
        self.git("commit", "-qm", "other base")
        self.request["base"] = self.git("rev-parse", "HEAD").strip()
        self.write("other.py", "staged A\n")
        self.git("add", "other.py")
        self.write("other.py", "working C\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "task edit\n")
        self.write("other.py", "staged B\n")
        self.git("add", "other.py")
        self.write("other.py", "working C\n")
        with self.assertRaisesRegex(gate.GateError, "范围外"):
            gate.create_candidate(self.repo, work, self.claim())

    def test_inventory_does_not_follow_a_symlinked_parent(self):
        self.write("nested/item.txt", "tracked\n")
        self.git("add", "nested/item.txt")
        self.git("commit", "-qm", "tracked nested file")
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "item.txt").write_text("outside user file\n")
        (self.repo / "nested/item.txt").unlink()
        (self.repo / "nested").rmdir()
        (self.repo / "nested").symlink_to(outside, target_is_directory=True)
        entries = gate._inventory(self.repo)
        self.assertEqual(entries["nested/item.txt"]["entry"]["type"], "symlink_parent")

    def test_actual_automation_changes_cannot_be_downgraded_by_low_risk_classification(self):
        for expression in ("pyautogui.click(1, 2)", "retry()", "stop_worker()", "switch_account()", "queue.put(job)"):
            with self.subTest(expression=expression):
                self.write("farm/worker.py", "def run():\n    return False\n")
                work = gate.capture_work(self.repo, self.request, "unattended_change")
                self.write("farm/worker.py", "def run():\n    " + expression + "\n")
                candidate = gate.create_candidate(self.repo, work, self.claim())
                risk = gate.classify_candidate(candidate, self.policy, lambda _: {
                    "classification": "review_not_required", "reason": "low", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True})
                self.assertEqual(risk["classification"], "review_required")

    def test_code_pattern_floor_only_applies_after_unattended_runtime_begins(self):
        candidate = {
            "runtime_manifest": False,
            "activity": "development",
            "files": {"farm/worker.py": {
                "index_diff": "",
                "worktree_diff": "@@ -1 +1 @@\n+pyautogui.click(1, 2)\n",
            }},
        }
        for activity in ("development", "auto"):
            with self.subTest(activity=activity):
                candidate["activity"] = activity
                self.assertEqual(gate._risk_floor(candidate, self.policy), "")
        candidate["activity"] = "unattended_change"
        self.assertIn("unattended execution", gate._risk_floor(candidate, self.policy))

    def test_workspace_policy_automatically_invokes_review_for_realistic_runtime_changes(self):
        policy = json.loads(MODULE.with_name("policy.json").read_text())
        for expression in ("pyautogui.click(1, 2)", "retry()", "stop_worker()", "switch_account()", "queue.put(job)", "MAX_RETRIES = 1", "MAX_ACTIVE = 2"):
            with self.subTest(expression=expression):
                self.write("farm/worker.py", "def run():\n    return False\n")
                work = gate.capture_work(self.repo, self.request, "unattended_change")
                self.write("farm/worker.py", "def run():\n    " + expression + "\n")
                calls = []
                def reviewer(candidate):
                    calls.append(candidate["id"])
                    return {"findings": []}
                prepared = gate.prepare_delivery(self.repo, work, self.claim(), policy,
                    lambda _: {"classification": "review_required", "reason": "runtime", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True}, reviewer)
                self.assertEqual(prepared["risk"]["classification"], "review_required")
                self.assertEqual(prepared["state"], "waiting_verification")
                self.assertEqual(len(calls), 1)

    def test_high_risk_with_unresolved_impact_runs_review_but_cannot_deliver(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        calls = []
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy,
            lambda _: {"classification": "needs_classification", "reason": "missing call graph", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": False},
            lambda _: calls.append("reviewed") or {"findings": []})
        self.assertEqual(calls, ["reviewed"])
        self.assertEqual(prepared["state"], "needs_classification")

    def test_review_required_with_unknown_impact_scope_cannot_be_delivered(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        calls = []
        assessor = lambda _: {"classification": "review_required",
                              "reason": "存在可达执行风险，但影响范围不明",
                              "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": False}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, assessor,
                                         lambda _: calls.append("reviewed") or {"findings": []})
        self.assertEqual(calls, ["reviewed"])
        self.assertEqual(prepared["risk"]["classification"], "review_required")
        self.assertFalse(prepared["risk"]["impact_scope_complete"])
        self.assertFalse(prepared["risk"]["assessment_complete"])
        self.assertEqual(prepared["state"], "needs_classification")
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, prepared, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "fixture"}],
                                   [], assessor)

    def test_risk_floor_does_not_complete_unresolved_classification(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        calls = []
        assessor = lambda _: {"classification": "needs_classification",
                              "reason": "无法确定该调用是否属于当前无人监管执行范围",
                              "evidence": [], "runtime_manifest_required": False,
                              "impact_scope_complete": True}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, assessor,
                                         lambda _: calls.append("reviewed") or {"findings": []})
        self.assertEqual(calls, ["reviewed"])
        self.assertEqual(prepared["risk"]["classification"], "review_required")
        self.assertTrue(prepared["risk"]["impact_scope_complete"])
        self.assertFalse(prepared["risk"]["assessment_complete"])
        self.assertEqual(prepared["state"], "needs_classification")
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, prepared, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "fixture"}],
                                   [], assessor)

    def test_neat_name_does_not_exempt_actual_execution_change(self):
        self.request["requirements"] = "NEAT 阶段同时修改实际自动执行逻辑"
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    retry()\n")
        calls = []
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy,
            lambda _: {"classification": "review_not_required", "reason": "NEAT", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True},
            lambda _: calls.append("reviewed") or {"findings": []})
        self.assertEqual(prepared["risk"]["classification"], "review_required")
        self.assertEqual(calls, ["reviewed"])

    def test_display_only_uses_actual_diff_and_can_skip_reviewer(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "label = 'new text'\n")
        calls = []
        def assessor(material):
            calls.append(material)
            return {"classification": "review_not_required", "reason": "display text only",
                    "evidence": [{"file": "farm/worker.py", "quote": "label = 'new text'"}], "runtime_manifest_required": False, "impact_scope_complete": True}
        candidate = gate.create_candidate(self.repo, work, self.claim())
        risk = gate.classify_candidate(candidate, self.policy, assessor)
        self.assertEqual(risk["classification"], "review_not_required")
        self.assertIn("label = 'new text'", json.dumps(calls[0]))
        self.assertEqual(risk["candidate"], candidate["id"])

    def test_review_not_required_with_incomplete_impact_scope_is_not_exempt(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "label = 'new text'\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        risk = gate.classify_candidate(candidate, self.policy, lambda _: {
            "classification": "review_not_required", "reason": "no runtime impact",
            "evidence": [{"file": "farm/worker.py", "quote": "label = 'new text'"}],
            "runtime_manifest_required": False, "impact_scope_complete": False})
        self.assertEqual(risk["classification"], "needs_classification")
        self.assertFalse(risk["assessment_complete"])

    def test_exemption_evidence_must_quote_actual_changed_lines(self):
        for quote in ("+++ worktree/farm/worker.py", "@@ -1,2 +1,2 @@", "keep this unchanged context"):
            with self.subTest(quote=quote):
                self.write("farm/worker.py", "keep this unchanged context\nlabel = 'old'\n")
                work = gate.capture_work(self.repo, self.request, "unattended_change")
                self.write("farm/worker.py", "keep this unchanged context\nlabel = 'new'\n")
                candidate = gate.create_candidate(self.repo, work, self.claim())
                risk = gate.classify_candidate(candidate, self.policy, lambda _: {
                    "classification": "review_not_required", "reason": "display only",
                    "evidence": [{"file": "farm/worker.py", "quote": quote}],
                    "runtime_manifest_required": False, "impact_scope_complete": True})
                self.assertEqual(risk["classification"], "needs_classification")

    def test_exemption_evidence_accepts_added_or_removed_content(self):
        self.write("farm/worker.py", "keep context\nlabel = 'old'\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "keep context\nlabel = 'new'\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        for quote in ("label = 'new'", "label = 'old'"):
            with self.subTest(quote=quote):
                risk = gate.classify_candidate(candidate, self.policy, lambda _: {
                    "classification": "review_not_required", "reason": "display only",
                    "evidence": [{"file": "farm/worker.py", "quote": quote}],
                    "runtime_manifest_required": False, "impact_scope_complete": True})
                self.assertEqual(risk["classification"], "review_not_required")

    def test_document_example_does_not_trigger_review_by_keyword_alone(self):
        self.write("guide.md", "# Guide\nOld text\n")
        self.request["files"] = ["guide.md"]
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("guide.md", "# Guide\nExample: retry()\n")
        candidate = gate.create_candidate(self.repo, work, self.claim("guide.md"))
        risk = gate.classify_candidate(candidate, self.policy, lambda _: {
            "classification": "review_not_required", "reason": "documentation example only",
            "evidence": [{"file": "guide.md", "quote": "Example: retry()"}], "runtime_manifest_required": False, "impact_scope_complete": True})
        self.assertEqual(risk["classification"], "review_not_required")

    def test_ui_string_containing_code_like_words_does_not_force_review(self):
        self.write("farm/worker.py", "label = 'old text'\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "label = 'Press retry() to continue'\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        risk = gate.classify_candidate(candidate, self.policy, lambda _: {
            "classification": "review_not_required", "reason": "display text only",
            "evidence": [{"file": "farm/worker.py", "quote": "Press retry() to continue"}], "runtime_manifest_required": False, "impact_scope_complete": True})
        self.assertEqual(risk["classification"], "review_not_required")

    def test_status_island_display_text_skips_full_reviewer(self):
        self.write("codex-monitor/ui.py", "LABEL = 'old'\n")
        self.request["files"] = ["codex-monitor/ui.py"]
        self.request["requirements"] = "只修改状态岛的静态展示文案"
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("codex-monitor/ui.py", "LABEL = 'new'\n")
        calls = []
        prepared = gate.prepare_delivery(self.repo, work, self.claim("codex-monitor/ui.py"), self.policy,
            lambda _: {"classification": "review_not_required", "reason": "display only",
                       "evidence": [{"file": "codex-monitor/ui.py", "quote": "LABEL = 'new'"}], "runtime_manifest_required": False, "impact_scope_complete": True},
            lambda _: calls.append("review"))
        self.assertEqual(prepared["risk"]["classification"], "review_not_required")
        self.assertEqual(calls, [])

    def test_unknown_or_invalid_assessment_cannot_be_treated_as_low_risk(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "unknown_change()\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        for response in ({}, {"classification": "review_not_required", "reason": "unsupported", "evidence": []},
                         {"classification": "needs_classification", "reason": "missing call graph", "evidence": []},
                         {"classification": "review_required", "reason": "reachable risk but scope unknown",
                          "evidence": [], "runtime_manifest_required": False}):
            risk = gate.classify_candidate(candidate, self.policy, lambda _: response)
            self.assertEqual(risk["classification"], "needs_classification")
        def unavailable(_):
            raise gate.GateError("classifier unavailable")
        self.assertEqual(gate.classify_candidate(candidate, self.policy, unavailable)["classification"], "needs_classification")

    def test_classifier_schema_requires_explicit_impact_scope_completion(self):
        response = {"classification": "review_not_required", "reason": "low risk",
                    "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True}
        with mock.patch.object(gate, "_codex_json", return_value=response) as invoke:
            self.assertEqual(gate.call_classifier({"candidate": "fixture"}), response)
        prompt, schema = invoke.call_args.args
        self.assertIn("impact_scope_complete", schema["required"])
        self.assertEqual(schema["properties"]["impact_scope_complete"]["type"], "boolean")
        self.assertIn("影响范围", prompt)

    def test_evidence_parser_accepts_source_lines_that_resemble_diff_headers(self):
        self.write("farm/worker.py", "--old-marker\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "++new-marker\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        for quote in ("++new-marker", "--old-marker"):
            with self.subTest(quote=quote):
                risk = gate.classify_candidate(candidate, self.policy, lambda _: {
                    "classification": "review_not_required", "reason": "text-only fixture",
                    "evidence": [{"file": "farm/worker.py", "quote": quote}],
                    "runtime_manifest_required": False, "impact_scope_complete": True})
                self.assertEqual(risk["classification"], "review_not_required")

    def test_first_unattended_run_is_required_even_without_a_diff(self):
        work = gate.capture_work(self.repo, self.request, "unattended_first_run")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        risk = gate.classify_candidate(candidate, self.policy, lambda _: {
            "classification": "review_not_required", "reason": "no changes", "evidence": []})
        self.assertEqual(risk["classification"], "review_required")

    def test_first_run_can_be_identified_from_original_goal_without_start_label(self):
        self.request["requirements"] = "首次将这个自动化投入无人监管运行，审查实际运行代码。"
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        seen = []
        def assessor(material):
            seen.append(material)
            return {"classification": "review_required", "reason": "首次无人运行", "evidence": [],
                    "runtime_manifest_required": True, "impact_scope_complete": False}
        risk = gate.classify_candidate(candidate, self.policy, assessor)
        self.assertEqual(risk["classification"], "needs_classification")
        self.assertIn("return False", json.dumps(seen[0]))

    def test_first_run_with_some_changes_requires_complete_runtime_manifest(self):
        self.write("farm/config.py", "READY = True\n")
        self.request["files"].append("farm/config.py")
        self.request["requirements"] = "首次将自动化投入无人监管运行，并修改执行逻辑。"
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    return True\n")
        claim = {"files": {name: {"index": gate._index(self.repo, name), "worktree": gate._worktree(self.repo, name)}
                           for name in ("farm/worker.py", "farm/config.py")}, "context": [], "runtime": True}
        candidate = gate.create_candidate(self.repo, work, claim)
        self.assertTrue(candidate["runtime_manifest"])
        self.assertEqual(set(candidate["files"]), {"farm/worker.py", "farm/config.py"})
        self.assertEqual(gate.classify_candidate(candidate, self.policy, lambda _: None)["classification"], "review_required")

    def test_delivery_automatically_reviews_high_risk_and_blocks_unresolved_findings(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        calls = []
        finding = {"severity": "important", "file": "farm/worker.py", "line": 2, "trigger": "repeat",
                   "impact": "duplicate", "evidence": "no guard", "recommendation": "guard"}
        def reviewer(material):
            calls.append(material)
            return {"findings": [finding]}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy,
            lambda _: {"classification": "needs_classification", "reason": "uncertain", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": False}, reviewer)
        self.assertEqual(prepared["state"], "revision_required")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, prepared, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "output"}], [], lambda _: None)

    def test_unavailable_reviewer_produces_failed_state_not_delivered(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        def unavailable(_):
            raise gate.GateError("reviewer unavailable")
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, lambda _: None, unavailable)
        self.assertEqual(prepared["state"], "review_failed")
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, prepared, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "output"}], [], lambda _: None)

    def test_route_respects_explicit_runtime_stage(self):
        expected = {
            "development": "review_not_required",
            "auto": "review_not_required",
            "unattended_change": "needs_classification",
            "unattended_first_run": "review_required",
        }
        for activity, classification in expected.items():
            with self.subTest(activity=activity):
                result = subprocess.run(
                    ["python3", str(MODULE), "route", "--activity", activity],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["classification"], classification)

    def test_pause_never_starts_classification_or_reviewer(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        calls = []
        result = gate.prepare_delivery(self.repo, work, {"files": {}, "context": []}, self.policy,
                                       lambda _: calls.append("classify"), lambda _: calls.append("review"), paused=True)
        self.assertEqual(result["state"], "paused")
        self.assertEqual(calls, [])

    def test_cli_pause_does_not_require_work_or_create_a_delivery_record(self):
        output = Path(self.tmp.name) / "should-not-exist.json"
        result = subprocess.run(["python3", str(MODULE), "deliver", "--pause", "--delivery", str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "paused")
        self.assertFalse(output.exists())

    def test_delivery_final_check_rejects_modified_state_and_stale_candidate(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "label = 'new text'\n")
        assessor = lambda _: {"classification": "review_not_required", "reason": "display only",
                              "evidence": [{"file": "farm/worker.py", "quote": "label = 'new text'"}], "runtime_manifest_required": False, "impact_scope_complete": True}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, assessor, lambda _: None)
        self.assertEqual(prepared["state"], "waiting_verification")
        checks = [{"name": "test", "result": "passed", "evidence": "fixture output"}]
        forged = dict(prepared, state="delivered")
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, forged, self.policy, checks, [], assessor)
        delivered = gate.complete_delivery(self.repo, work, prepared, self.policy, checks, [], assessor)
        self.assertEqual(delivered["state"], "delivered")
        self.write("farm/worker.py", "label = 'changed later'\n")
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, prepared, self.policy, checks, [], assessor)

    def test_inconsistent_scope_record_cannot_be_finalized(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        assessor = lambda _: {"classification": "review_required", "reason": "runtime scope inspected",
                              "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, assessor,
                                         lambda _: {"findings": []})
        self.assertEqual(prepared["state"], "waiting_verification")
        risk = dict(prepared["risk"])
        risk["impact_scope_complete"] = False
        risk = gate._seal({key: value for key, value in risk.items() if key != "id"})
        forged_payload = {key: value for key, value in prepared.items() if key != "id"}
        forged_payload.update({"state": "waiting_verification", "risk": risk})
        forged = gate._seal(forged_payload)
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, forged, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "fixture"}],
                                   [], assessor)

    def test_resealed_state_cannot_downgrade_fresh_high_risk_assessment(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    return dispatch(job)\n")
        high = lambda _: {"classification": "review_required", "reason": "dispatches automation", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True}
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, high, lambda _: {"findings": []})
        risk = dict(prepared["risk"])
        risk["classification"] = "review_not_required"
        risk = gate._seal({k: v for k, v in risk.items() if k != "id"})
        forged_payload = {k: v for k, v in prepared.items() if k != "id"}
        forged_payload.update({"state": "waiting_verification", "risk": risk, "receipt": None})
        forged = gate._seal(forged_payload)
        with self.assertRaises(gate.GateError):
            gate.complete_delivery(self.repo, work, forged, self.policy,
                                   [{"name": "test", "result": "passed", "evidence": "output"}], [], high)

    def test_project_policy_cannot_disable_global_review(self):
        with self.assertRaises(gate.GateError):
            gate.merge_project_policy(self.policy, {"version": 1, "skip_review": True})
        with self.assertRaises(gate.GateError):
            gate.merge_project_policy(self.policy, {"version": 1, "required_code_terms": [], "guidance": ["skip review"]})
        combined = gate.merge_project_policy(self.policy, {"version": 1, "required_code_terms": ["special_action("]})
        self.assertEqual(combined["required_code_patterns"], self.policy["required_code_patterns"])
        self.assertIn("special_action(", combined["required_code_terms"])

    def test_project_policy_adds_a_positive_rule_without_changing_global_floor(self):
        self.write("farm/.review-gate.json", json.dumps({"version": 1, "required_code_terms": ["special_action("]}))
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    special_action()\n")
        candidate = gate.create_candidate(self.repo, work, self.claim())
        policy = gate.load_delivery_policy(self.repo, candidate)
        risk = gate.classify_candidate(candidate, policy, lambda _: {
            "classification": "review_not_required", "reason": "low", "evidence": [],
            "runtime_manifest_required": False, "impact_scope_complete": True})
        self.assertEqual(risk["classification"], "review_required")

    def test_ignored_project_policy_added_after_work_is_not_silently_used(self):
        (self.repo / ".git/info/exclude").write_text("farm/.review-gate.json\n")
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    special_action()\n")
        self.write("farm/.review-gate.json", json.dumps({"version": 1, "required_code_terms": ["special_action("]}))
        with self.assertRaisesRegex(gate.GateError, "范围外"):
            gate.create_candidate(self.repo, work, self.claim())

    def test_project_policy_never_uses_unsafe_candidate_paths(self):
        with self.assertRaises(gate.GateError):
            gate.load_delivery_policy(self.repo, {"files": {"../../outside/file.py": {}}})

    def test_single_delivery_entry_requires_review_and_verification_before_success(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        directory = Path(self.tmp.name)
        key = gate._create_work_key(directory / "work.json")
        (directory / "work.json").write_text(json.dumps(gate._sign_delivery(work, key)))
        (directory / "claim.json").write_text(json.dumps(self.claim()))
        prepare_args = ["review_gate.py", "deliver", "--repo", str(self.repo), "--work", str(directory / "work.json"),
                        "--claim", str(directory / "claim.json"), "--delivery", str(directory / "prepared.json")]
        classifier = {"classification": "review_required", "reason": "fixture automation", "evidence": [], "runtime_manifest_required": False, "impact_scope_complete": True}
        with mock.patch.object(sys, "argv", prepare_args), mock.patch.object(gate, "call_classifier", return_value=classifier), mock.patch.object(gate, "call_reviewer", return_value={"findings": []}) as reviewer:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(), 2)
            reviewer.assert_called_once()
        self.assertEqual(json.loads((directory / "prepared.json").read_text())["record"]["state"], "waiting_verification")
        (directory / "checks.json").write_text(json.dumps([{"name": "test", "result": "passed", "evidence": "fixture output"}]))
        finish_args = ["review_gate.py", "deliver", "--repo", str(self.repo), "--work", str(directory / "work.json"),
                       "--prepared", str(directory / "prepared.json"), "--checks", str(directory / "checks.json"),
                       "--delivery", str(directory / "delivered.json")]
        with mock.patch.object(sys, "argv", finish_args), mock.patch.object(gate, "call_classifier", return_value=classifier), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(), 0)
        self.assertEqual(json.loads((directory / "delivered.json").read_text())["record"]["state"], "delivered")

    def test_modified_prepared_record_cannot_pass_by_resealing_json(self):
        work = gate.capture_work(self.repo, self.request, "unattended_change")
        self.write("farm/worker.py", "def run():\n    pyautogui.click(1, 2)\n")
        directory = Path(self.tmp.name)
        work_file = directory / "work.json"
        work_file.write_text(json.dumps(work))
        key = gate._create_work_key(work_file)
        prepared = gate.prepare_delivery(self.repo, work, self.claim(), self.policy, lambda _: None,
                                         lambda _: {"findings": []})
        envelope = gate._sign_delivery(prepared, key)
        altered = dict(envelope["record"])
        altered["state"] = "delivered"
        envelope["record"] = gate._seal({k: v for k, v in altered.items() if k != "id"})
        with self.assertRaises(gate.GateError):
            gate._open_delivery(envelope, key)

    def test_work_key_is_private_and_insecure_permissions_fail_closed(self):
        work_file = Path(self.tmp.name) / "work.json"
        gate._create_work_key(work_file)
        key_file = Path(str(work_file) + ".key")
        self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
        key_file.chmod(0o644)
        with self.assertRaises(gate.GateError):
            gate._read_work_key(work_file)

    def test_verification_evidence_must_be_created_after_prepare(self):
        directory = Path(self.tmp.name)
        prepared = directory / "prepared.json"
        checks = directory / "checks.json"
        prepared.write_text("{}")
        checks.write_text("[]")
        os.utime(checks, ns=(1_000_000_000, 1_000_000_000))
        with self.assertRaises(gate.GateError):
            gate._checks_after(prepared, checks)


if __name__ == "__main__":
    unittest.main()
