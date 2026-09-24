from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import effective_quest_rows
from lib.questie_lua import seq
from lib.questie_objectives import raw_objective_slots
from lib.questie_source import load_questie

DEFAULT_QUESTIE = ROOT / "data/sources/questie/Questie.zip"
PROFILE_IDS = ("storm-peaks-fivebox", "icecrown-fivebox", "howling-fivebox")
WARN_DISTANCE = 5.0
FAIL_DISTANCE = 8.0
NPC_SPAWNS = 7
OBJECT_SPAWNS = 4
ITEM_NPC_DROPS = 2
ITEM_OBJECT_DROPS = 3
EXCEPTIONS = ROOT / "data/route-audits/objective-anchor-exceptions.json"


def spawn_points(spawns: Any, zone_id: int) -> list[tuple[float, float]]:
    if not isinstance(spawns, dict):
        return []
    raw = spawns.get(zone_id)
    points: list[tuple[float, float]] = []
    for entry in seq(raw):
        values = seq(entry)
        if len(values) >= 2 and all(isinstance(v, (int, float)) for v in values[:2]):
            points.append((float(values[0]), float(values[1])))
    return points


def envelope(points: list[tuple[float, float]]) -> dict[str, float] | None:
    if not points:
        return None
    xs=[p[0] for p in points]; ys=[p[1] for p in points]
    return {"min_x":min(xs),"max_x":max(xs),"min_y":min(ys),"max_y":max(ys)}


def distance_to_envelope(x: float, y: float, env: dict[str, float]) -> float:
    dx = 0.0 if env["min_x"] <= x <= env["max_x"] else min(abs(x-env["min_x"]), abs(x-env["max_x"]))
    dy = 0.0 if env["min_y"] <= y <= env["max_y"] else min(abs(y-env["min_y"]), abs(y-env["max_y"]))
    return math.hypot(dx, dy)


def source_envelopes(data: Any, slot: dict[str, Any], zone_id: int) -> list[dict[str, Any]]:
    sources: list[tuple[str,int]]=[]
    kind=slot.get("objective_type")
    if kind=="kill" and isinstance(slot.get("entity_id"), int):
        sources.append(("npc", int(slot["entity_id"])))
    elif kind=="object" and isinstance(slot.get("entity_id"), int):
        sources.append(("object", int(slot["entity_id"])))
    elif kind=="event":
        sources.extend(("npc", int(x)) for x in slot.get("entity_ids") or [] if isinstance(x,int))
    elif kind=="item" and isinstance(slot.get("entity_id"), int):
        item=data.items.get(int(slot["entity_id"]))
        if isinstance(item, dict):
            sources.extend(("npc", int(x)) for x in seq(item.get(ITEM_NPC_DROPS)) if isinstance(x,int))
            sources.extend(("object", int(x)) for x in seq(item.get(ITEM_OBJECT_DROPS)) if isinstance(x,int))
    out=[]
    for source_type, source_id in sources:
        row=(data.npcs if source_type=="npc" else data.objects).get(source_id)
        if not isinstance(row, dict):
            continue
        points=spawn_points(row.get(NPC_SPAWNS if source_type=="npc" else OBJECT_SPAWNS), zone_id)
        env=envelope(points)
        if env:
            out.append({"source_type":source_type,"source_id":source_id,**env})
    return out


def audit_profile(profile: dict[str, Any], data: Any, effective_rows: dict[int, dict[Any,Any]], manual: dict[str,str]) -> dict[str, Any]:
    profile_id=str(profile["profile_id"])
    primary_zone=int(profile["scope"]["primary_zone_id"])
    locations=profile["geometry"]["locations"]
    execution: dict[int,list[dict[str,Any]]]=defaultdict(list)
    for action in profile.get("actions") or []:
        if action.get("kind")!="objective" or not isinstance(action.get("task_id"),int):
            continue
        ref=str(action.get("location_ref") or "")
        location=locations.get(ref) or {}
        x=location.get("x"); y=location.get("y")
        zone=int(location.get("zone_id") or primary_zone)
        if isinstance(x,(int,float)) and isinstance(y,(int,float)) and zone==primary_zone:
            execution[int(action["task_id"])].append({"action_id":action.get("action_id"),"location_ref":ref,"x":float(x),"y":float(y)})
    rows=[]; requirements=[]; skipped=[]
    for task_id, points in sorted(execution.items()):
        if str(task_id) in manual:
            skipped.append({"task_id":task_id,"reason":manual[str(task_id)]})
            continue
        quest=effective_rows.get(task_id)
        if not isinstance(quest,dict):
            requirements.append({"task_id":task_id,"kind":"questie_task_missing"})
            continue
        slots=raw_objective_slots(quest)
        for objective_index,slot in enumerate(slots,1):
            sources=source_envelopes(data,slot,primary_zone)
            if not sources:
                requirements.append({"task_id":task_id,"objective_index":objective_index,"kind":"objective_spawn_coordinates_unavailable","objective_type":slot.get("objective_type")})
                continue
            candidates=[]
            for point in points:
                for src in sources:
                    candidates.append((distance_to_envelope(point["x"],point["y"],src),point,src))
            distance,point,src=min(candidates,key=lambda x:x[0])
            status="pass" if distance<=WARN_DISTANCE else ("review" if distance<=FAIL_DISTANCE else "fail")
            rows.append({"task_id":task_id,"objective_index":objective_index,"objective_type":slot.get("objective_type"),"distance":round(distance,2),"status":status,"action_id":point["action_id"],"location_ref":point["location_ref"],"source_type":src["source_type"],"source_id":src["source_id"]})
    failures=[r for r in rows if r["status"]=="fail"]
    reviews=[r for r in rows if r["status"]=="review"]
    return {"profile_id":profile_id,"checked_objectives":len(rows),"failure_count":len(failures),"review_count":len(reviews),"requirement_count":len(requirements),"failures":failures,"reviews":reviews,"requirements":requirements,"manual_resolved":skipped}


def main() -> None:
    parser=argparse.ArgumentParser(description="Audit current Route Profile objective anchors against Questie spawn coordinates.")
    parser.add_argument("--questie-source",type=Path,default=DEFAULT_QUESTIE)
    parser.add_argument("--profile",action="append",dest="profiles")
    args=parser.parse_args()
    source=args.questie_source.expanduser().resolve()
    if not source.exists():
        print(json.dumps({"status":"requirements","issue":"questie_source_missing","path":str(source)},ensure_ascii=False,indent=2))
        raise SystemExit(2)
    ids=tuple(args.profiles or PROFILE_IDS)
    profiles=[json.loads((ROOT/"data/route-profiles"/f"{pid}.json").read_text(encoding="utf-8")) for pid in ids]
    task_ids={int(a["task_id"]) for p in profiles for a in p.get("actions") or [] if a.get("kind")=="objective" and isinstance(a.get("task_id"),int)}
    data=load_questie(source)
    effective_rows,_=effective_quest_rows(data,source,task_ids)
    cfg=json.loads(EXCEPTIONS.read_text(encoding="utf-8")) if EXCEPTIONS.exists() else {"profiles":{}}
    reports=[audit_profile(p,data,effective_rows,(cfg.get("profiles") or {}).get(str(p["profile_id"]),{})) for p in profiles]
    failures=sum(r["failure_count"] for r in reports)
    reviews=sum(r["review_count"] for r in reports)
    requirements=sum(r["requirement_count"] for r in reports)
    status="blocked" if failures else ("requirements" if reviews or requirements else "pass")
    out={"status":status,"source":{"path":str(source),"questie_version":data.version,"sha256":data.source_sha256},"profiles":reports}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if failures:
        raise SystemExit(1)


if __name__=="__main__":
    main()
