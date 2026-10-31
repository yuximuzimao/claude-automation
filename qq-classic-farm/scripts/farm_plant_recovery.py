"""Crash-safe M2 planting recovery journal; never authorizes game input.

A live phase must durably mark each transaction IN_FLIGHT *before* its first
CGEvent. After independent UI postcondition verification, it checkpoints the
confirmed-only inventory. Any existing journal blocks a fresh run: even a
verified but uncommitted phase requires reconciliation with farm-state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from farm_runner import save_state_atomic


class RecoveryJournalStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class PlantRecoveryJournal:
    """One journal per plan/cycle/platform; no automatic resume or replay."""

    def __init__(self, path: Path, *, plan_id: str, plan_revision: int,
                 cycle_id: str, platform: str, inventory_revision: int):
        if (not isinstance(plan_id, str) or not plan_id
            or type(plan_revision) is not int or plan_revision < 1
            or not isinstance(cycle_id, str) or not cycle_id
            or platform not in ("qq", "wechat")
            or type(inventory_revision) is not int or inventory_revision < 0):
            raise RecoveryJournalStop("INVALID_RECOVERY_CONTEXT", "Invalid plan/state identity")
        self.path = Path(path)
        self.context = {
            "plan_id": plan_id, "plan_revision": plan_revision,
            "cycle_id": cycle_id, "platform": platform,
            "inventory_revision": inventory_revision,
        }
        self._record: dict | None = None

    @staticmethod
    def _quantities(quantities: Mapping[str, int]) -> dict[str, int]:
        if (not isinstance(quantities, Mapping)
            or any(not isinstance(k, str) or not k or type(v) is not int or v < 0
                   for k, v in quantities.items())):
            raise RecoveryJournalStop("INVALID_RECOVERY_INVENTORY",
                                      "Recovery inventory must contain nonnegative integer counts")
        return dict(quantities)

    def start(self, quantities: Mapping[str, int]) -> None:
        """Exclusive creation: any pre-existing journal is a reconciliation stop."""
        if self._record is not None:
            raise RecoveryJournalStop("RECOVERY_ALREADY_STARTED", "Journal already started")
        record = {
            "schema_version": 1, **self.context, "status": "prepared",
            "pending_transaction": None, "completed_transactions": [],
            "confirmed_quantities": self._quantities(quantities),
            "retry_allowed": False, "farm_state_committed": False,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RecoveryJournalStop(
                "RECOVERY_RECONCILIATION_REQUIRED",
                "Existing recovery journal; inspect real field and inventory before any new actions",
            ) from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            dirfd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except Exception:
            # Even an incomplete journal blocks retry. Do not unlink it.
            raise
        self._record = record

    def _save(self, record: dict) -> None:
        # Atomic replacement with file and directory fsync; never write farm-state.
        save_state_atomic(self.path, record)
        self._record = record

    def before_transaction(self, transaction: dict, completed: list[dict],
                           quantities: dict[str, int]) -> None:
        old = self._record
        if old is None or old["status"] not in ("prepared", "checkpointed"):
            raise RecoveryJournalStop("RECOVERY_RECONCILIATION_REQUIRED",
                                      "Journal is not ready for another transaction")
        if (old["completed_transactions"] != completed
            or old["confirmed_quantities"] != self._quantities(quantities)):
            raise RecoveryJournalStop("RECOVERY_STATE_DRIFT", "Journal differs from phase state")
        if (not isinstance(transaction, dict) or transaction.get("kind") not in ("special", "ordinary")
            or not isinstance(transaction.get("seed"), str) or not transaction["seed"]):
            raise RecoveryJournalStop("INVALID_RECOVERY_TRANSACTION", "Unknown planting transaction")
        if transaction["kind"] == "special":
            if (set(transaction) != {"kind", "seed", "placement"}
                or not isinstance(transaction["placement"], str) or not transaction["placement"]):
                raise RecoveryJournalStop("INVALID_RECOVERY_TRANSACTION", "Invalid special placement")
        elif (set(transaction) != {"kind", "seed", "count"}
              or type(transaction["count"]) is not int or transaction["count"] <= 0):
            raise RecoveryJournalStop("INVALID_RECOVERY_TRANSACTION", "Invalid ordinary count")
        self._save({**old, "status": "in_flight",
                    "pending_transaction": dict(transaction)})

    def checkpoint(self, completed: list[dict], quantities: dict[str, int]) -> None:
        old = self._record
        if old is None or old["status"] != "in_flight":
            raise RecoveryJournalStop("RECOVERY_RECONCILIATION_REQUIRED",
                                      "No pending transaction to confirm")
        pending = old["pending_transaction"]
        if (len(completed) != len(old["completed_transactions"]) + 1
            or completed[:-1] != old["completed_transactions"]):
            raise RecoveryJournalStop("RECOVERY_STATE_DRIFT", "Transaction sequence differs")
        last = completed[-1]
        if (not isinstance(last, dict) or last.get("seed") != pending["seed"]
            or last.get("status") != ("special_plant_verified" if pending["kind"] == "special"
                                    else "ordinary_plant_verified")
            or (pending["kind"] == "special" and last.get("placement") != pending["placement"])
            or (pending["kind"] == "ordinary" and last.get("count") != pending["count"])):
            raise RecoveryJournalStop("RECOVERY_STATE_DRIFT", "Confirmed transaction mismatch")
        self._save({**old, "status": "checkpointed", "pending_transaction": None,
                    "completed_transactions": list(completed),
                    "confirmed_quantities": self._quantities(quantities)})

    def finish(self, result: dict) -> None:
        old = self._record
        if (old is None or old["status"] != "checkpointed"
            or result.get("status") != "plant_phase_verified"
            or result.get("platform") != self.context["platform"]
            or result.get("completed_transactions") != old["completed_transactions"]
            or result.get("quantities_after") != old["confirmed_quantities"]
            or result.get("persisted") is not False):
            raise RecoveryJournalStop("RECOVERY_RECONCILIATION_REQUIRED",
                                      "Cannot finalize an unverified/uncheckpointed phase")
        self._save({**old, "status": "phase_verified_uncommitted"})


def run_plant_phase_with_recovery(journal: PlantRecoveryJournal, adapter, *,
                                  platform: str, actions: dict, stable_order,
                                  quantities: Mapping[str, int], layout: dict,
                                  inventory_verified: bool = False) -> dict:
    """Compose existing phase with durable preaction and confirmed-only checkpoints.

    No UI adapter is constructed here. This helper does not authorize live clicks
    or commit farm-state; callers must verify real inventory and field first.
    """
    from farm_plant_cycle import run_plant_phase
    if platform != journal.context["platform"]:
        raise RecoveryJournalStop("INVALID_RECOVERY_CONTEXT", "Journal platform mismatch")
    if not inventory_verified:
        raise RecoveryJournalStop("INVENTORY_DIRTY", "Refuse journaled run on stale inventory")
    journal.start(quantities)
    result = run_plant_phase(
        adapter, platform=platform, actions=actions, stable_order=stable_order,
        quantities=quantities, layout=layout, inventory_verified=True,
        before_transaction=journal.before_transaction,
        checkpoint=journal.checkpoint,
    )
    journal.finish(result)
    return result
