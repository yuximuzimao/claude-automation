#!/usr/bin/env python3
import json
import runpy
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
reader = runpy.run_path(str(ROOT / "scripts" / "read-latest-excel.py"))
errors = []

classify_fruit_row = reader.get("classify_fruit_row")
if classify_fruit_row is None:
    errors.append("read-latest-excel.py must export classify_fruit_row")
else:
    sheets = reader["read_xlsx"](ROOT / "图鉴课题进度表（另存或存为副本使用）.xlsx")
    rows = sheets.get("果实进度", [])[1:]
    classified = [(row, classify_fruit_row(row)) for row in rows]
    valid = [(row, info) for row, info in classified if info is not None]
    invalid = [(row, info) for row, info in classified if info is None]

    if len(rows) != 177: errors.append(f"fruit candidate rows: {len(rows)} != 177")
    if len(valid) != 168: errors.append(f"valid fruit rows: {len(valid)} != 168")
    if len(invalid) != 9: errors.append(f"non-fruit rows: {len(invalid)} != 9")

    invalid_ranges = {str(row.get("A") or "") for row, _ in invalid}
    for expected in ["N.001", "N.375"]:
        if expected not in invalid_ranges: errors.append(f"{expected} must be classified as non-fruit")

    fire = next((info for row, info in valid if row.get("A") == "N.005-N.007"), None)
    if fire is None or fire.get("familyNumberRange") != [5, 7]:
        errors.append("fire family fruit range must be [5, 7]")

    expected_types = {"课题任务", "智慧树苗", "剧情任务", "通行证契约礼券", "赛季作业", "限时活动"}
    actual_types = {info.get("obtainType") for _, info in valid}
    if actual_types != expected_types:
        errors.append(f"fruit obtain types mismatch: {sorted(actual_types)}")

    try:
        classify_fruit_row({"A": "N.999", "C": "未知来源", "D": "未知说明"})
        errors.append("unknown fruit source must raise ValueError")
    except ValueError:
        pass
    try:
        classify_fruit_row({"A": "N.999", "C": "未知来源", "D": "达到100研学绩点获得蛋"})
        errors.append("unknown egg-only source must raise ValueError instead of being silently excluded")
    except ValueError:
        pass

    pets = json.loads((ROOT / "data" / "pets.json").read_text(encoding="utf-8"))
    missing_ranges = [key for key, pet in pets.items() if pet.get("fruit") and pet["fruit"].get("familyNumberRange") is None]
    if missing_ranges:
        errors.append(f"fruit definitions missing familyNumberRange: {len(missing_ranges)}")

if errors:
    print("\n".join(errors))
    raise SystemExit(1)

print(json.dumps({
    "candidateRows": len(rows),
    "validFruitRows": len(valid),
    "nonFruitRows": len(invalid),
    "types": dict(sorted(Counter(info["obtainType"] for _, info in valid).items())),
}, ensure_ascii=False, indent=2))
