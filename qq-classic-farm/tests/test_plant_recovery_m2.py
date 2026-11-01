"""M2 recovery journal contract: durable before any action, never auto replay."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_plant_cycle import PlantPhaseStop, run_plant_phase
from farm_plant_recovery import (
    PlantRecoveryJournal, RecoveryJournalStop, run_plant_phase_with_recovery,
)
from seed_order import consume_confirmed

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text())
ORDER = ["a", "b", "c", "d", "s", "o"]
INITIAL = {"a": 1, "b": 1, "c": 1, "d": 1, "s": 3, "o": 12}
ACTIONS = {
    "special": [{"seed": "s", "placements": ["gold_a", "gold_b", "gold_c"]}],
    "ordinary": [{"seed": "o", "count": 12}],
}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "runs" / "m2-qq-recovery.json"

    def journal(self):
        return PlantRecoveryJournal(
            self.path, plan_id="p1", plan_revision=2, cycle_id="c1",
            platform="qq", inventory_revision=3,
        )

    def record(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_preaction_durable_and_restart_is_reconciliation_only(self):
        journal = self.journal()
        journal.start(INITIAL)
        self.assertEqual(self.record()["status"], "prepared")
        tx = {"kind": "special", "seed": "s", "placement": "gold_a"}
        journal.before_transaction(tx, [], INITIAL)
        self.assertEqual(self.record()["status"], "in_flight")
        self.assertEqual(self.record()["pending_transaction"], tx)
        self.assertFalse(self.record()["retry_allowed"])
        self.assertFalse(self.record()["farm_state_committed"])
        with self.assertRaises(RecoveryJournalStop) as caught:
            self.journal().start(INITIAL)
        self.assertEqual(caught.exception.code, "RECOVERY_RECONCILIATION_REQUIRED")
        self.assertEqual(self.record()["status"], "in_flight")

    def test_confirmed_checkpoint_and_final_status_never_commit_farm_state(self):
        journal = self.journal()
        journal.start(INITIAL)
        journal.before_transaction({"kind": "ordinary", "seed": "o", "count": 12},
                                   [], INITIAL)
        after = consume_confirmed(ORDER, INITIAL, "o", 12)
        event = {"status": "ordinary_plant_verified", "platform": "qq",
                 "seed": "o", "count": 12}
        journal.checkpoint([event], after)
        self.assertEqual(self.record()["status"], "checkpointed")
        self.assertIsNone(self.record()["pending_transaction"])
        journal.finish({"status": "plant_phase_verified", "platform": "qq",
                        "completed_transactions": [event],
                        "quantities_after": after, "persisted": False})
        self.assertEqual(self.record()["status"], "phase_verified_uncommitted")
        self.assertFalse(self.record()["farm_state_committed"])
        with self.assertRaises(RecoveryJournalStop):
            self.journal().start(after)

    def test_bad_confirmed_transaction_keeps_pending_for_reconciliation(self):
        journal = self.journal()
        journal.start(INITIAL)
        journal.before_transaction({"kind": "special", "seed": "s",
                                    "placement": "gold_a"}, [], INITIAL)
        with self.assertRaises(RecoveryJournalStop) as caught:
            journal.checkpoint([{"status": "special_plant_verified", "seed": "s",
                                 "placement": "gold_b"}], INITIAL)
        self.assertEqual(caught.exception.code, "RECOVERY_STATE_DRIFT")
        self.assertEqual(self.record()["status"], "in_flight")

    def test_unverified_inventory_stops_before_journal_creation(self):
        with self.assertRaises(RecoveryJournalStop) as caught:
            run_plant_phase_with_recovery(
                self.journal(), object(), platform="qq", actions=ACTIONS,
                stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                inventory_verified=False)
        self.assertEqual(caught.exception.code, "INVENTORY_DIRTY")
        self.assertFalse(self.path.exists())

    def test_full_phase_has_preaction_markers_and_confirmed_only_checkpoints(self):
        journal = self.journal()
        seen = []
        original_begin = journal.before_transaction
        original_checkpoint = journal.checkpoint

        def begin(tx, events, counts):
            original_begin(tx, events, counts)
            seen.append(("begin", tx["kind"], self.record()["status"]))

        def checkpoint(events, counts):
            self.assertEqual(self.record()["status"], "in_flight")
            original_checkpoint(events, counts)
            seen.append(("verified", len(events), self.record()["status"]))

        journal.before_transaction = begin
        journal.checkpoint = checkpoint

        def special(_adapter, *, seed, placement, stable_order, quantities, **_):
            self.assertEqual(self.record()["status"], "in_flight")
            return {"status": "special_plant_verified", "platform": "qq",
                    "seed": seed, "placement": placement,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, 1),
                    "persisted": False, "llm_round_trips": 0}

        def ordinary(_adapter, *, seed, count, stable_order, quantities, **_):
            self.assertEqual(self.record()["status"], "in_flight")
            return {"status": "ordinary_plant_verified", "platform": "qq",
                    "seed": seed, "count": count,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, count),
                    "persisted": False, "llm_round_trips": 0}

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key", side_effect=ordinary):
            result = run_plant_phase_with_recovery(
                journal, object(), platform="qq", actions=ACTIONS,
                stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                inventory_verified=True)
        self.assertEqual([x[0] for x in seen], ["begin", "verified"] * 4)
        self.assertEqual(self.record()["status"], "phase_verified_uncommitted")
        self.assertEqual(self.record()["confirmed_quantities"], result["quantities_after"])
        self.assertEqual(self.record()["confirmed_quantities"]["s"], 0)
        self.assertEqual(self.record()["confirmed_quantities"]["o"], 0)
        self.assertEqual(INITIAL["s"], 3)

    def test_preaction_write_failure_prevents_new_game_action(self):
        journal = self.journal()
        journal.start(INITIAL)
        with patch("farm_plant_cycle.plant_one_special") as special, \
             patch.object(journal, "before_transaction", side_effect=OSError("disk full")):
            with self.assertRaises(PlantPhaseStop) as caught:
                run_plant_phase(
                    object(), platform="qq", actions=ACTIONS,
                    stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                    inventory_verified=True,
                    before_transaction=journal.before_transaction,
                    checkpoint=journal.checkpoint)
            special.assert_not_called()
        self.assertEqual(caught.exception.code, "RECOVERY_PREACTION_FAILED")
        self.assertFalse(caught.exception.action_may_have_been_sent)

    def test_partial_action_leaves_pending_and_preserves_prior_confirmed(self):
        journal = self.journal()

        def special(_adapter, *, seed, placement, stable_order, quantities, **_):
            if placement == "gold_b":
                from farm_plant_special import SpecialPlantStop
                raise SpecialPlantStop("PLANT_PREVIEW_MISMATCH", "Unknown preview",
                                       action_may_have_been_sent=True)
            return {"status": "special_plant_verified", "platform": "qq",
                    "seed": seed, "placement": placement,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, 1),
                    "persisted": False, "llm_round_trips": 0}

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                run_plant_phase_with_recovery(
                    journal, object(), platform="qq", actions=ACTIONS,
                    stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                    inventory_verified=True)
            ordinary.assert_not_called()
        self.assertEqual(caught.exception.code, "PLANT_PREVIEW_MISMATCH")
        self.assertEqual(len(caught.exception.completed), 1)
        self.assertEqual(self.record()["status"], "in_flight")
        self.assertEqual(self.record()["pending_transaction"]["placement"], "gold_b")
        self.assertEqual(len(self.record()["completed_transactions"]), 1)
        self.assertEqual(self.record()["confirmed_quantities"]["s"], 2)
        with self.assertRaises(RecoveryJournalStop):
            self.journal().start(INITIAL)

    def test_verified_phase_commits_only_confirmed_inventory(self):
        state_path = Path(self.tmp.name) / "farm-state.json"
        state = {"schema_version": 1, "inventory_revision": 3,
                 "platforms": {
                     "qq": {"quantities": dict(INITIAL), "inventory_dirty": False,
                            "last_daily_date": "2026-10-31"},
                     "wechat": {"quantities": {"w": 9}, "inventory_dirty": True}}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        journal = self.journal()
        journal.start(INITIAL)
        tx = {"kind": "ordinary", "seed": "o", "count": 12}
        journal.before_transaction(tx, [], INITIAL)
        after = consume_confirmed(ORDER, INITIAL, "o", 12)
        event = {"status": "ordinary_plant_verified", "platform": "qq",
                 "seed": "o", "count": 12}
        journal.checkpoint([event], after)
        journal.finish({"status": "plant_phase_verified", "platform": "qq",
                        "completed_transactions": [event],
                        "quantities_after": after, "persisted": False})
        committed = journal.commit_verified_inventory(state_path)
        self.assertEqual(committed["inventory_revision"], 4)
        self.assertEqual(committed["platforms"]["qq"]["quantities"], after)
        self.assertEqual(committed["platforms"]["wechat"], state["platforms"]["wechat"])
        self.assertEqual(committed["platforms"]["qq"]["last_daily_date"], "2026-10-31")
        self.assertEqual(self.record()["status"], "committed")
        self.assertTrue(self.record()["farm_state_committed"])
        with self.assertRaises(RecoveryJournalStop):
            journal.commit_verified_inventory(state_path)

    def test_commit_refuses_dirty_or_drifted_inventory_without_writing(self):
        for dirty, drift in ((True, False), (False, True), (False, False)):
            with self.subTest(dirty=dirty, drift=drift):
                journal = self.journal()
                if self.path.exists():
                    self.path.unlink()
                journal.start(INITIAL)
                tx = {"kind": "ordinary", "seed": "o", "count": 12}
                journal.before_transaction(tx, [], INITIAL)
                after = consume_confirmed(ORDER, INITIAL, "o", 12)
                event = {"status": "ordinary_plant_verified", "platform": "qq",
                         "seed": "o", "count": 12}
                journal.checkpoint([event], after)
                journal.finish({"status": "plant_phase_verified", "platform": "qq",
                                "completed_transactions": [event],
                                "quantities_after": after, "persisted": False})
                quantities = dict(INITIAL)
                if drift:
                    quantities["o"] += 1
                state = {"schema_version": 1,
                         "inventory_revision": (4 if not dirty and not drift else 3),
                         "platforms": {"qq": {"quantities": quantities,
                                              "inventory_dirty": dirty}}}
                state_path = Path(self.tmp.name) / "farm-state.json"
                state_path.write_text(json.dumps(state), encoding="utf-8")
                before = state_path.read_bytes()
                with self.assertRaises(RecoveryJournalStop):
                    journal.commit_verified_inventory(state_path)
                self.assertEqual(state_path.read_bytes(), before)
                self.assertEqual(self.record()["status"], "phase_verified_uncommitted")

    def test_journal_write_failure_after_state_commit_is_idempotent_in_process(self):
        state_path = Path(self.tmp.name) / "farm-state.json"
        state = {"schema_version": 1, "inventory_revision": 3,
                 "platforms": {"qq": {"quantities": dict(INITIAL),
                                       "inventory_dirty": False}}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        journal = self.journal()
        journal.start(INITIAL)
        tx = {"kind": "ordinary", "seed": "o", "count": 12}
        journal.before_transaction(tx, [], INITIAL)
        after = consume_confirmed(ORDER, INITIAL, "o", 12)
        event = {"status": "ordinary_plant_verified", "platform": "qq",
                 "seed": "o", "count": 12}
        journal.checkpoint([event], after)
        journal.finish({"status": "plant_phase_verified", "platform": "qq",
                        "completed_transactions": [event],
                        "quantities_after": after, "persisted": False})
        original_save = journal._save
        with patch.object(journal, "_save", side_effect=OSError("journal fsync failed")):
            with self.assertRaises(OSError):
                journal.commit_verified_inventory(state_path)
        self.assertEqual(json.loads(state_path.read_text())["inventory_revision"], 4)
        self.assertEqual(self.record()["status"], "phase_verified_uncommitted")
        journal._save = original_save
        journal.commit_verified_inventory(state_path)
        self.assertEqual(json.loads(state_path.read_text())["inventory_revision"], 4)
        self.assertEqual(self.record()["status"], "committed")

    def test_composed_phase_checks_durable_inventory_before_any_action(self):
        state_path = Path(self.tmp.name) / "farm-state.json"
        for dirty, revision in ((True, 3), (False, 4)):
            with self.subTest(dirty=dirty, revision=revision):
                state_path.write_text(json.dumps({
                    "schema_version": 1, "inventory_revision": revision,
                    "platforms": {"qq": {"quantities": dict(INITIAL),
                                         "inventory_dirty": dirty}}
                }), encoding="utf-8")
                with patch("farm_plant_cycle.plant_one_special") as special:
                    with self.assertRaises(RecoveryJournalStop) as caught:
                        run_plant_phase_with_recovery(
                            self.journal(), object(), platform="qq", actions=ACTIONS,
                            stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                            inventory_verified=True, state_path=state_path)
                    special.assert_not_called()
                self.assertEqual(caught.exception.code, "RECOVERY_STATE_DRIFT")
                self.assertFalse(self.path.exists())

    def test_composed_phase_can_commit_verified_stock_without_live_ui(self):
        state_path = Path(self.tmp.name) / "farm-state.json"
        state = {"schema_version": 1, "inventory_revision": 3,
                 "platforms": {"qq": {"quantities": dict(INITIAL), "inventory_dirty": False},
                               "wechat": {"quantities": {"w": 7}, "inventory_dirty": True}}}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        def special(_adapter, *, seed, placement, stable_order, quantities, **_):
            return {"status": "special_plant_verified", "platform": "qq",
                    "seed": seed, "placement": placement,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, 1),
                    "persisted": False, "llm_round_trips": 0}

        def ordinary(_adapter, *, seed, count, stable_order, quantities, **_):
            return {"status": "ordinary_plant_verified", "platform": "qq",
                    "seed": seed, "count": count,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, count),
                    "persisted": False, "llm_round_trips": 0}

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key", side_effect=ordinary):
            result = run_plant_phase_with_recovery(
                self.journal(), object(), platform="qq", actions=ACTIONS,
                stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                inventory_verified=True, state_path=state_path)
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "plant_phase_verified")
        self.assertTrue(result["persisted"])
        self.assertEqual(result["inventory_revision"], 4)
        self.assertEqual(saved["platforms"]["qq"]["quantities"], result["quantities_after"])
        self.assertEqual(saved["platforms"]["wechat"], state["platforms"]["wechat"])
        self.assertEqual(self.record()["status"], "committed")

    def test_composed_phase_commit_drift_stops_without_claiming_persisted(self):
        state_path = Path(self.tmp.name) / "farm-state.json"
        state = {"schema_version": 1, "inventory_revision": 3,
                 "platforms": {"qq": {"quantities": dict(INITIAL), "inventory_dirty": False}}}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        def special(_adapter, *, seed, placement, stable_order, quantities, **_):
            return {"status": "special_plant_verified", "platform": "qq",
                    "seed": seed, "placement": placement,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, 1),
                    "persisted": False, "llm_round_trips": 0}

        def ordinary(_adapter, *, seed, count, stable_order, quantities, **_):
            # Simulate a concurrent inventory change after the game action
            # but before the final verified-only farm-state commit.
            changed = json.loads(state_path.read_text(encoding="utf-8"))
            changed["inventory_revision"] = 4
            state_path.write_text(json.dumps(changed), encoding="utf-8")
            return {"status": "ordinary_plant_verified", "platform": "qq",
                    "seed": seed, "count": count,
                    "quantities_after": consume_confirmed(stable_order, quantities, seed, count),
                    "persisted": False, "llm_round_trips": 0}

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key", side_effect=ordinary):
            with self.assertRaises(RecoveryJournalStop) as caught:
                run_plant_phase_with_recovery(
                    self.journal(), object(), platform="qq", actions=ACTIONS,
                    stable_order=ORDER, quantities=INITIAL, layout=LAYOUT,
                    inventory_verified=True, state_path=state_path)
        self.assertEqual(caught.exception.code, "RECOVERY_STATE_DRIFT")
        self.assertEqual(self.record()["status"], "phase_verified_uncommitted")
        self.assertEqual(json.loads(state_path.read_text())["platforms"]["qq"]["quantities"], INITIAL)


if __name__ == "__main__":
    unittest.main()
