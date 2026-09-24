from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "data/journey/current-paladin.json"
TASK_CARDS = ROOT / "data/task-cards"
PROFILES = ROOT / "data/route-profiles"
OUT = ROOT / "data/observations/daily-task-timing-samples.json"

TZ = dt.timezone(dt.timedelta(hours=8))
ZONE_ORDER = ["北风苔原","龙骨荒野","风暴峭壁","冰冠冰川","索拉查盆地","祖达克","灰熊丘陵","嚎风峡湾"]


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, TZ).isoformat()


def pair_samples(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    samples: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    occurrence = 0
    for event in events:
        action = event.get("event")
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, int):
            continue
        if action == "Accept":
            pending = event
        elif action == "Abandon":
            pending = None
        elif action == "Complete" and pending is not None:
            accept_ts = int(pending["timestamp"])
            complete_ts = timestamp
            occurrence += 1
            accept_dt = dt.datetime.fromtimestamp(accept_ts, TZ)
            complete_dt = dt.datetime.fromtimestamp(complete_ts, TZ)
            samples.append({
                "occurrence": occurrence,
                "accept_at": accept_dt.isoformat(),
                "complete_at": complete_dt.isoformat(),
                "elapsed_minutes": round((complete_ts - accept_ts) / 60.0, 2),
                "cross_day": accept_dt.date() != complete_dt.date(),
            })
            pending = None
    return samples, pending


def current_route_membership() -> tuple[dict[int, list[str]], dict[str, str]]:
    membership: dict[int, list[str]] = {}
    names: dict[str, str] = {}
    for path in sorted(PROFILES.glob("*.json")):
        if path.name == "schema.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        display = data.get("display") or {}
        key = str(display.get("publish_key") or data.get("profile_id") or path.stem)
        names[key] = str(display.get("display_name") or data.get("scope", {}).get("route_scope") or key)
        for task_id in data.get("task_ids") or []:
            if isinstance(task_id, int):
                membership.setdefault(task_id, []).append(key)
    return membership, names


def daily_task_cards() -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for path in sorted(TASK_CARDS.glob("*.json")):
        if path.name == "schema.json" or not path.stem.isdigit():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        identity = data.get("identity") or {}
        if identity.get("repeatability") != "daily":
            continue
        result[int(path.stem)] = {
            "name": str(identity.get("name_zhcn") or identity.get("name_en") or path.stem),
            "source": "task_card",
        }
    return result


def main() -> None:
    journey = json.loads(JOURNEY.read_text(encoding="utf-8"))
    membership, route_names = current_route_membership()
    daily_defs = daily_task_cards()

    events_by_quest: dict[int, list[dict[str, Any]]] = {}
    for event in journey.get("events", []):
        qid = event.get("quest_id")
        if isinstance(qid, int):
            events_by_quest.setdefault(qid, []).append(event)

    zones: dict[str, list[dict[str, Any]]] = {}
    completed_sample_count = 0
    repeat_sample_task_ids: list[int] = []
    accepted_only_task_ids: list[int] = []

    for qid, meta in sorted(daily_defs.items()):
        events = events_by_quest.get(qid, [])
        if not events:
            continue
        samples, pending = pair_samples(events)
        route_keys = sorted(set(membership.get(qid, [])))
        route_zone_names = [route_names[key] for key in route_keys if key in route_names]
        zone = route_zone_names[0] if route_zone_names else "未知"

        completed_sample_count += len(samples)
        if len(samples) > 1:
            repeat_sample_task_ids.append(qid)
        if pending is not None:
            accepted_only_task_ids.append(qid)

        same_day = [sample["elapsed_minutes"] for sample in samples if not sample["cross_day"]]
        all_intervals = [sample["elapsed_minutes"] for sample in samples]
        task = {
            "quest_id": qid,
            "name": meta["name"],
            "definition_source": meta["source"],
            "route_status": "current_route_first_run_once" if route_keys else "observed_not_in_current_route",
            "current_route_keys": route_keys,
            "samples": samples,
            "sample_count": len(samples),
            "best_observed_interval_minutes": min(all_intervals) if all_intervals else None,
            "best_same_day_observed_interval_minutes": min(same_day) if same_day else None,
        }
        if pending is not None:
            task["open_accept"] = {
                "accept_at": iso(int(pending["timestamp"])),
                "status": "accepted_only_no_complete_sample",
            }
        zones.setdefault(zone, []).append(task)

    ordered_zones: dict[str, Any] = {}
    for zone in ZONE_ORDER:
        if zone in zones:
            ordered_zones[zone] = zones.pop(zone)
    for zone in sorted(zones):
        ordered_zones[zone] = zones[zone]

    unique_task_count = sum(len(tasks) for tasks in ordered_zones.values())
    payload = {
        "schema_version": 3,
        "purpose": "保存当前Task Card识别的日常任务在Journey中的接取→完成墙钟样本；不参与一次性清图路线排序。",
        "source": {
            "journey": "data/journey/current-paladin.json",
            "task_definitions": "data/task-cards/",
            "route_membership": "data/route-profiles/",
            "source_sha256": journey.get("source_sha256"),
            "journey_latest_timestamp": journey.get("latest_timestamp"),
            "timezone": "+08:00",
            "generated_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        },
        "timing_policy": {
            "metric": "journey_accept_to_complete_wall_interval_minutes",
            "caveat": "原始区间可能混入其它任务、交通、等待、离线或人为停顿；只保存事实样本，不当作净任务服务时间。",
            "selection_policy": "后续筛日常优先比较同日短区间、重复样本和单独报时；跨日长区间只保留事实。",
            "route_policy": "当前Route Profile只决定该日常是否属于一次性清图路线；Journey重复记录只增加样本，不生成第二轮路线动作。",
        },
        "summary": {
            "observed_daily_task_count": unique_task_count,
            "completed_sample_count": completed_sample_count,
            "repeat_sample_task_ids": repeat_sample_task_ids,
            "accepted_only_task_ids": accepted_only_task_ids,
        },
        "zones": ordered_zones,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT.relative_to(ROOT)), **payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
