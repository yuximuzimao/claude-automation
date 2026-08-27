from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
JOURNEY = ROOT / "data/journey/current-paladin.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/observations/daily-task-timing-samples.json"

TZ = dt.timezone(dt.timedelta(hours=8))
ZONE_ORDER = [
    "北风苔原",
    "龙骨荒野",
    "风暴峭壁",
    "冰冠冰川",
    "索拉查盆地",
    "祖达克",
    "灰熊丘陵",
    "嚎风峡湾",
]

# 银色比武场独立分类任务不在当前诺森德assigned-zone任务宇宙中，
# 但首组Journey已经有真实记录，仍应进入日常时间样本表。
EXTRA_DAILIES: dict[int, dict[str, Any]] = {
    13677: {
        "name": "学习驾驭",
        "assigned_zone_name": "冰冠冰川",
        "source": "icecrown_tournament_sidecar",
    },
    13674: {
        "name": "A Worthy Weapon",
        "assigned_zone_name": "冰冠冰川",
        "source": "icecrown_tournament_sidecar",
    },
}


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, TZ).isoformat()


def route_texts(workbench: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, route in workbench.items():
        lines = []
        for point in route.get("points", []):
            if isinstance(point, list) and len(point) > 3:
                lines.append(str(point[3]))
        out[key] = "\n".join(lines)
    return out


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
            samples.append(
                {
                    "occurrence": occurrence,
                    "accept_at": accept_dt.isoformat(),
                    "complete_at": complete_dt.isoformat(),
                    "elapsed_minutes": round((complete_ts - accept_ts) / 60.0, 2),
                    "cross_day": accept_dt.date() != complete_dt.date(),
                }
            )
            pending = None

    return samples, pending


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    journey = json.loads(JOURNEY.read_text(encoding="utf-8"))
    workbench = json.loads(WORKBENCH.read_text(encoding="utf-8"))

    route_text = route_texts(workbench)
    by_id: dict[int, dict[str, Any]] = {
        int(row["quest_id"]): row for row in universe.get("tasks", [])
    }

    daily_defs: dict[int, dict[str, Any]] = {
        qid: {
            "name": row.get("name") or row.get("english_name") or str(qid),
            "assigned_zone_name": row.get("assigned_zone_name") or "未知",
            "source": "northrend_task_universe",
        }
        for qid, row in by_id.items()
        if row.get("is_daily")
    }
    daily_defs.update(EXTRA_DAILIES)

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
        current_route_keys = [
            key
            for key, text in route_text.items()
            if f"《{meta['name']}》" in text
        ]
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
            "route_status": (
                "current_route_first_run_once"
                if current_route_keys
                else "observed_not_in_current_route"
            ),
            "current_route_keys": current_route_keys,
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

        zones.setdefault(meta["assigned_zone_name"], []).append(task)

    ordered_zones: dict[str, Any] = {}
    for zone in ZONE_ORDER:
        if zone in zones:
            ordered_zones[zone] = zones.pop(zone)
    for zone in sorted(zones):
        ordered_zones[zone] = zones[zone]

    unique_task_count = sum(len(tasks) for tasks in ordered_zones.values())
    payload = {
        "schema_version": 2,
        "purpose": (
            "保存首组诺森德实跑中的日常任务接取→交付原始墙钟样本，"
            "供全部地图首跑完成后单独筛选每日值得重复做的日常。"
            "本文件不参与一次性清图Route Atlas排序。"
        ),
        "source": {
            "journey": "data/journey/current-paladin.json",
            "source_sha256": journey.get("source_sha256"),
            "journey_latest_timestamp": journey.get("latest_timestamp"),
            "timezone": "+08:00",
            "generated_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        },
        "timing_policy": {
            "metric": "journey_accept_to_complete_wall_interval_minutes",
            "caveat": (
                "原始区间可能混入其它任务、交通、等待、离线或人为停顿；"
                "现在只保存事实样本，不把它当净任务服务时间。"
            ),
            "selection_policy": (
                "后续筛日常优先比较同日短区间、重复样本和单独报时；"
                "跨日长区间只保留事实，不参与初步速度排名。"
            ),
            "route_policy": (
                "一次性清图Route Atlas中每个日常最多保留首轮；"
                "Journey里的跨日/重复接取只增加这里的时间样本，不生成第二轮路线动作。"
            ),
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
    print(
        json.dumps(
            {
                "output": str(OUT.relative_to(ROOT)),
                **payload["summary"],
                "zones": {key: len(value) for key, value in ordered_zones.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
