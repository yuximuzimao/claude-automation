from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lib.questie_lua import LuaTableParser, seq


def parse_saved_variables(path: Path) -> dict[Any, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "QuestieConfig"
    marker_pos = text.find(marker)
    if marker_pos == -1:
        raise ValueError(f"QuestieConfig assignment not found in {path}")
    table_pos = text.find("{", marker_pos)
    if table_pos == -1:
        raise ValueError(f"QuestieConfig table not found in {path}")
    parsed = LuaTableParser(text, pos=table_pos).parse()
    if not isinstance(parsed, dict):
        raise ValueError(f"QuestieConfig is not a table in {path}")
    return parsed


def first_present(table: dict[Any, Any], keys: tuple[Any, ...]) -> Any:
    for key in keys:
        if key in table:
            return table[key]
    return None


def normalize_event(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"index": index, "raw": raw}

    raw_event = first_present(raw, ("Event", "event", "eventType", "type", "action", 1))
    if raw_event == "Quest":
        event = first_present(raw, ("SubType", "subType"))
    elif raw_event == "Level":
        event = "LevelUp"
    else:
        event = raw_event

    quest_id = first_present(raw, ("Quest", "questId", "questID", "quest_id", "quest", "id", 2))
    level = first_present(raw, ("NewLevel", "Level", "level", "playerLevel", "player_level", 3))
    timestamp = first_present(raw, ("Timestamp", "timestamp", "time", "date", "createdAt", 4))

    normalized = {
        "index": index,
        "event": event,
        "quest_id": quest_id,
        "level": level,
        "timestamp": timestamp,
    }
    if all(value is None for key, value in normalized.items() if key != "index"):
        normalized["raw"] = raw
    return normalized


def numeric_values(value: Any) -> list[int]:
    values: list[int] = []
    if isinstance(value, bool):
        return values
    if isinstance(value, int):
        values.append(value)
    elif isinstance(value, float) and value.is_integer():
        values.append(int(value))
    elif isinstance(value, dict):
        for item in value.values():
            values.extend(numeric_values(item))
    return values


def event_timestamp(event: dict[str, Any]) -> int | None:
    timestamp = event.get("timestamp")
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        value = int(timestamp)
        if value > 1_000_000_000:
            return value
    raw = event.get("raw")
    for value in numeric_values(raw):
        if value > 1_000_000_000:
            return value
    return None


def event_level(event: dict[str, Any]) -> int | None:
    level = event.get("level")
    if isinstance(level, (int, float)) and not isinstance(level, bool):
        value = int(level)
        if 1 <= value <= 100:
            return value
    raw = event.get("raw")
    candidates = [value for value in numeric_values(raw) if 1 <= value <= 100]
    return candidates[-1] if candidates else None


def summarize(path: Path, preview: int) -> dict[str, Any]:
    config = parse_saved_variables(path)
    char_table = config.get("char")
    if not isinstance(char_table, dict):
        raise ValueError("QuestieConfig.char is missing or not a table")

    candidates: list[dict[str, Any]] = []
    for entry in char_table.values():
        if not isinstance(entry, dict):
            continue
        journey = entry.get("journey")
        events_raw = seq(journey)
        if not events_raw:
            continue
        events = [normalize_event(raw, index) for index, raw in enumerate(events_raw, start=1)]
        timestamps = [value for event in events if (value := event_timestamp(event)) is not None]
        levels = [value for event in events if (value := event_level(event)) is not None]

        quest_states: dict[int, str] = {}
        completed_in_order: list[int] = []
        for event in events:
            quest_id = event.get("quest_id")
            event_name = event.get("event")
            if not isinstance(quest_id, int) or not isinstance(event_name, str):
                continue
            quest_states[quest_id] = event_name
            if event_name == "Complete":
                completed_in_order.append(quest_id)

        candidates.append(
            {
                "event_count": len(events),
                "earliest_timestamp": min(timestamps) if timestamps else None,
                "latest_timestamp": max(timestamps) if timestamps else None,
                "min_level": min(levels) if levels else None,
                "max_level": max(levels) if levels else None,
                "active_quest_ids": sorted(
                    quest_id for quest_id, state in quest_states.items() if state == "Accept"
                ),
                "recent_completed_quest_ids": completed_in_order[-30:],
                "events_preview": events[-preview:],
            }
        )

    candidates.sort(key=lambda item: item.get("latest_timestamp") or 0, reverse=True)
    return {
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "journey_character_count": len(candidates),
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a redacted Questie journey summary")
    parser.add_argument("source", type=Path)
    parser.add_argument("--preview", type=int, default=40)
    parser.add_argument("--latest-only", action="store_true")
    args = parser.parse_args()

    result = summarize(args.source, max(1, args.preview))
    if args.latest_only:
        result["candidates"] = result["candidates"][:1]
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
