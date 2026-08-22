from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MASTER = ROOT / "data" / "video-route" / "master-events.json"
OUT = ROOT / "data" / "video-route" / "map-reference-blocks.json"
REPORT = ROOT / "docs" / "archive" / "analysis" / "video-route-map-reference-audit.md"
QUESTIE = ROOT / "_sandbox" / "sources" / "Questie-v11.32.3.zip"
MAP_MANIFEST = ROOT / "data" / "routes" / "maps" / "manifest.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    from lib.questie_source import load_questie

    master = load_json(MASTER)
    questie = load_questie(QUESTIE)
    manifest = load_json(MAP_MANIFEST)
    zone_dirs = {int(x["zone_id"]): x.get("zone_dir") for x in manifest.get("maps", [])}

    groups: dict[int, dict[str, Any]] = {}
    unassigned: list[dict[str, Any]] = []

    for event in master["events"]:
        qid = event.get("quest_id")
        if not isinstance(qid, int):
            continue
        quest = questie.quests.get(qid) or {}
        zone_id = quest.get(17)
        if not isinstance(zone_id, int):
            unassigned.append({
                "event_id": event["event_id"],
                "quest_id": qid,
                "quest_name": event.get("quest_name"),
                "episode": event["episode"],
            })
            continue
        group = groups.setdefault(zone_id, {
            "zone_id": zone_id,
            "zone_dir": zone_dirs.get(zone_id),
            "episodes": set(),
            "events": [],
        })
        group["episodes"].add(event["episode"])
        group["events"].append({
            "event_id": event["event_id"],
            "episode": event["episode"],
            "episode_title": event["episode_title"],
            "series_sequence": event["series_sequence"],
            "series_seconds_start": event.get("series_seconds_start"),
            "episode_seconds_start": event.get("episode_seconds_start"),
            "action_class": event["action_class"],
            "original_action": event["original_action"],
            "quest_id": qid,
            "quest_name": event.get("quest_name"),
            "confidence": event.get("confidence"),
            "experience": event.get("experience"),
        })

    out_maps: list[dict[str, Any]] = []
    for zone_id, group in sorted(groups.items()):
        events = sorted(group["events"], key=lambda e: e["series_sequence"])
        completions = [e for e in events if e["action_class"] == "complete"]
        accepts = [e for e in events if e["action_class"] == "accept"]
        objectives = [e for e in events if e["action_class"] == "objective"]

        # Keep repeated completions because some quests are repeatable; provide first-completion sequence separately.
        first_completion_by_qid: list[dict[str, Any]] = []
        seen_qids: set[int] = set()
        for event in completions:
            qid = event["quest_id"]
            if qid in seen_qids:
                continue
            seen_qids.add(qid)
            first_completion_by_qid.append(event)

        edges = []
        for a, b in zip(first_completion_by_qid, first_completion_by_qid[1:]):
            edges.append({
                "from_quest_id": a["quest_id"],
                "from_quest_name": a["quest_name"],
                "to_quest_id": b["quest_id"],
                "to_quest_name": b["quest_name"],
                "from_event_id": a["event_id"],
                "to_event_id": b["event_id"],
            })

        out_maps.append({
            "zone_id": zone_id,
            "zone_dir": group["zone_dir"],
            "episodes": sorted(group["episodes"]),
            "event_count": len(events),
            "action_counts": dict(Counter(e["action_class"] for e in events)),
            "observed_quest_ids": sorted({e["quest_id"] for e in events}),
            "completion_sequence_first_by_quest_id": first_completion_by_qid,
            "completion_adjacency_first_by_quest_id": edges,
            "accept_sequence": accepts,
            "objective_events": objectives,
            "events": events,
        })

    payload = {
        "schema": "video-route-map-reference-blocks-v1",
        "purpose": "route_order_adjacency_and_omission_audit_only",
        "source": str(MASTER),
        "map_count": len(out_maps),
        "unassigned_quest_event_count": len(unassigned),
        "maps": out_maps,
        "unassigned_quest_events": unassigned,
        "notes": [
            "Quest zone is Questie compact quest field 17; it is a task ownership/reference zone, not proof that every video frame occurred inside that zone.",
            "Completion sequence keeps only first completion per Quest ID for adjacency comparison; raw repeated completions remain in events and may be legitimate repeatable quests.",
            "This dataset is evidence for our route audit, not a playable Alliance route and not a five-box timing model.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    useful = [m for m in out_maps if m["zone_dir"]]
    top = sorted(useful, key=lambda m: len(m["completion_sequence_first_by_quest_id"]), reverse=True)
    lines = [
        "# 视频按地图参考块 P3 审计",
        "",
        "用途：把已验证视频事件变成后续路线顺序/邻接和遗漏审计的查询入口。Questie地图归属只用于索引，不代表视频每一帧的真实所在地。",
        "",
        f"- 有任务事件的Questie区域：{len(out_maps)}。",
        f"- 能映射到本项目地图资源目录的区域：{len(useful)}。",
        f"- 无Questie zone的任务事件：{len(unassigned)}。",
        "",
        "## 完成任务较多的地图",
        "",
    ]
    for m in top[:30]:
        lines.append(
            f"- `{m['zone_id']}` `{m['zone_dir']}`：首次完成Quest {len(m['completion_sequence_first_by_quest_id'])}，"
            f"事件{m['event_count']}，涉及集数{','.join(map(str, m['episodes']))}。"
        )
    lines += [
        "",
        "完整事件和邻接边见`data/video-route/map-reference-blocks.json`。后续只能把它拿去和本项目当前任务池/路线比较，不能直接转成执行路线。",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "map_count": len(out_maps),
        "mapped_resource_maps": len(useful),
        "unassigned_quest_events": len(unassigned),
        "top_maps": [
            {
                "zone_id": m["zone_id"],
                "zone_dir": m["zone_dir"],
                "completion_quests": len(m["completion_sequence_first_by_quest_id"]),
                "episodes": m["episodes"],
            }
            for m in top[:12]
        ],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
