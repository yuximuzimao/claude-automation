#!/usr/bin/env python3
"""Simulate seed-picker page/slot from fixed platform order and current inventory.

Model:
1. take platform fixed picker order
2. keep seeds whose latest known inventory for that platform is > 0
3. paginate in groups of five

This script is read-only and never clicks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(path.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["qq", "wechat"], required=True)
    ap.add_argument("--target")
    ap.add_argument("--show-visible", action="store_true")
    args = ap.parse_args()

    order_data = load_json(ROOT / "data/picker-order.json")
    catalog = load_json(ROOT / "data/seed-catalog.json")
    page_size = int(order_data["page_size"])
    order = order_data["platforms"][args.platform]["order"]

    by_name = {s["name"]: s for s in catalog["seeds"]}

    visible = []
    uncertain = []
    for name in order:
        seed = by_name.get(name)
        obs = ((seed or {}).get("observations", {}).get(args.platform) or {})
        qty = obs.get("quantity_latest_known")
        if qty is None:
            uncertain.append(name)
            continue
        if qty > 0:
            visible.append({
                "name": name,
                "quantity": qty,
                "basis": obs.get("quantity_latest_known_basis"),
                "confidence": obs.get("quantity_confidence"),
            })

    pages = [
        visible[i : i + page_size]
        for i in range(0, len(visible), page_size)
    ]

    target = None
    if args.target:
        for i, item in enumerate(visible):
            if item["name"] == args.target:
                target = {
                    **item,
                    "visible_index": i,
                    "page": i // page_size + 1,
                    "slot": i % page_size + 1,
                }
                break

    out = {
        "platform": args.platform,
        "model": order_data["model"],
        "page_size": page_size,
        "visible_count": len(visible),
        "page_count": len(pages),
        "target": target,
        "unknown_inventory_in_order": uncertain,
    }
    if args.show_visible:
        out["pages"] = pages

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
