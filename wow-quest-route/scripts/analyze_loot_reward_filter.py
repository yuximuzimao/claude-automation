from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value[:200]):
            yield from walk(child, f"{path}[{i}]")


def inspect(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    print("FILE", path)
    print("TOP", type(data).__name__, list(data)[:50] if isinstance(data, dict) else len(data))

    key_counts: Counter[str] = Counter()
    interesting: list[tuple[str, list[str], dict[str, Any]]] = []
    needles = (
        "reward", "xp", "experience", "objective", "item", "quest", "title", "name",
        "choice", "money", "gold", "level", "source", "drop", "object",
    )
    for node_path, obj in walk(data):
        for key in obj:
            key_counts[key] += 1
        keys = [str(k) for k in obj]
        lower = " ".join(keys).lower()
        if sum(token in lower for token in needles) >= 3 and len(interesting) < 30:
            slim: dict[str, Any] = {}
            for k, v in obj.items():
                kl = str(k).lower()
                if any(token in kl for token in needles):
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        slim[k] = v
                    elif isinstance(v, list):
                        slim[k] = v[:5]
                    elif isinstance(v, dict):
                        slim[k] = {kk: vv for kk, vv in list(v.items())[:10] if isinstance(vv, (str, int, float, bool)) or vv is None}
            interesting.append((node_path, keys, slim))

    print("COMMON_KEYS")
    for key, count in key_counts.most_common(80):
        print(count, key)
    print("INTERESTING")
    for node_path, keys, slim in interesting:
        print(node_path)
        print(" keys=", keys)
        print(" slim=", json.dumps(slim, ensure_ascii=False)[:4000])


def list_collection_candidates(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    catalog = data.get("quest_catalog", []) if isinstance(data, dict) else []
    patterns = (
        "收集", "带去", "带回", "交给", "找回", "找到", "拾取", "采集", "获取", "获得",
        "将", "份", "块", "枚", "瓶", "片", "颗", "只", "根", "个", "卷轴", "样本", "精华",
    )
    rows = []
    for q in catalog:
        text = str(q.get("objective_text", ""))
        score = sum(token in text for token in patterns)
        if score >= 2:
            rows.append({
                "quest_id": q.get("quest_id"),
                "name": q.get("name"),
                "quest_level": q.get("quest_level"),
                "next_quest": q.get("next_quest"),
                "child_quests": q.get("child_quests"),
                "objective_text": text,
                "score": score,
            })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: analyze_loot_reward_filter.py <json> [collections]")
    path = ROOT / sys.argv[1]
    if len(sys.argv) == 3 and sys.argv[2] == "collections":
        list_collection_candidates(path)
    else:
        inspect(path)


if __name__ == "__main__":
    main()
