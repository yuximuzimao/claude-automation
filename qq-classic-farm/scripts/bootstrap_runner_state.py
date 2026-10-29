"""One-time M0 bootstrap from historical evidence; never overwrites live state."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "data/inventory-live-2026-10-28.json"
HISTORY = ROOT / "data/picker-order.json"
ORDER = ROOT / "data/seed-order.json"
STATE = ROOT / "data/farm-state.json"

# Confirmed 2026-10-29 planting / merchant deltas in IMPLEMENTATION_PLAN §13.
KNOWN_CURRENT_QUANTITIES = {
    "qq": {"泡泡棉花糖种子": 21, "天山红枫种子": 18},
    "wechat": {"星语铃花种子": 8, "天山红枫种子": 14, "哈哈南瓜种子": 8},
}


def make_bootstrap() -> tuple[dict, dict]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    historical = json.loads(HISTORY.read_text(encoding="utf-8"))
    order = {
        "schema_version": 1,
        "page_size": 5,
        "hypothesis": "newly acquired seeds may be temporarily inserted; fresh entry restores stable order (UNVERIFIED)",
        "platforms": {},
    }
    state = {
        "schema_version": 1,
        "inventory_revision": 1,
        "quantity_observed_at": inventory["captured_at"],
        "quantity_updated_through": "2026-10-29 (only explicitly recorded deltas)",
        "platforms": {},
    }
    for platform in ("qq", "wechat"):
        rows = [item for page in inventory[platform]["pages"] for item in page]
        names = [item["name"] for item in rows]
        if len(names) != len(set(names)) or len(names) != inventory[platform]["visible_seed_types"]:
            raise ValueError(f"{platform}: snapshot contains duplicate/missing seed names")
        quantities = {item["name"]: item["quantity"] for item in rows}
        for name, value in KNOWN_CURRENT_QUANTITIES[platform].items():
            if name not in quantities or not 0 <= value <= quantities[name] + 1:
                raise ValueError(f"{platform}: unexpected quantity delta for {name}")
            quantities[name] = value
        old = historical["platforms"][platform]["order"]
        missing = [name for name in old if name not in names]
        # Do NOT guess where absent historical seeds would reappear; fresh-entry
        # observation only verifies currently visible seeds' relative order.
        order["platforms"][platform] = {
            "stable_order": names,
            "verified_at": inventory["captured_at"],
            "evidence": [
                "data/inventory-live-2026-10-28.json warehouse row-major",
                "same-day picker first page matched warehouse first row",
                "data/picker-order.json historical comparison only",
            ],
            "historical_zero_candidates_uncalibrated": missing,
            "fresh_entry_reacquisition_hypothesis_verified": False,
            "notes": (
                "Fresh 2026-10-28 sequence overrides older ordering; "
                "historical-only seeds need calibration if quantity becomes positive. "
                "WeChat 艾草/森野白桃 ordering conflict is not treated as permanent revision."
            ),
        }
        state["platforms"][platform] = {
            "quantities": quantities,
            "inventory_dirty": True,
            "inventory_dirty_reason": (
                "Historical 2026-10-28 snapshot plus recorded 2026-10-29 deltas; "
                "no live revalidation yet. Block real clicks until synced."
            ),
            "last_daily_date": "2026-10-29",
            "last_successful_cycle": None,
            "last_inventory_sync_at": inventory["captured_at"],
            "known_deltas_applied": KNOWN_CURRENT_QUANTITIES[platform],
        }
    return order, state


def main() -> None:
    order, state = make_bootstrap()
    for path, value in ((ORDER, order), (STATE, state)):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite {path}; state is owned by Runner")
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"created {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
