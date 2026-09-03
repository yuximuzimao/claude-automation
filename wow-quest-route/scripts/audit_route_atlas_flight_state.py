from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/route-atlas/flight-state-audit.json"

# Canonical flight hubs and the player-facing aliases that may appear in route text.
# This is intentionally route-layer state, not a global "all known flight points" list.
HUB_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "borean": {
        "战歌要塞": ("战歌要塞",),
        "琥珀崖": ("琥珀崖",),
        "永生之盾": ("永生之盾", "Transitus Shield"),
        "牦牛村": ("牦牛村", "牦牛人村"),
        "博古洛克": ("博古洛克",),
    },
    "dragonblight": {
        "阿格玛之锤": ("阿格玛之锤", "阿格玛"),
        "莫亚基港口": ("莫亚基港口", "莫亚基"),
        "龙眠神殿": ("龙眠神殿", "龙眠"),
        "怨毒镇": ("怨毒镇",),
        "库卡隆先锋营地": ("库卡隆先锋营地", "库卡隆"),
    },
    "grizzly": {
        "征服堡": ("征服堡", "Conquest Hold"),
        "欧尼瓦营地": ("欧尼瓦营地", "欧尼瓦", "Camp Oneqwah"),
    },
    "zuldrak": {
        "圣光据点": ("圣光据点", "Light's Breach"),
        "黑锋哨站": ("黑锋哨站", "Ebon Watch"),
        "银色前沿": ("银色前沿", "The Argent Stand", "Argent Stand"),
        "希姆托加": ("希姆托加", "Zim'Torga"),
        "古达克": ("古达克", "Gundrak"),
    },
    "storm": {
        "K3": ("K3",),
        "格罗玛什坠毁点": ("格罗玛什坠毁点", "Grom'arsh Crash-Site"),
        "丹尼芬雷": ("丹尼芬雷", "Dun Niffelem"),
        "奥杜尔": ("奥杜尔", "Ulduar"),
        "布德克拉格庇护所": ("布德克拉格庇护所", "Bouldercrag's Refuge"),
        "唐卡洛营地": ("唐卡洛营地", "Camp Tunka'lo"),
    },
    "icecrown": {
        "银色前线基地": ("银色前线基地", "Argent Vanguard"),
        "北伐军之峰": ("北伐军之峰", "Crusaders' Pinnacle"),
        "暗影拱顶": ("暗影拱顶", "The Shadow Vault"),
        "死亡高地": ("死亡高地", "Death's Rise"),
    },
    "howling": {
        "药剂师营地": ("药剂师营地", "Apothecary Camp"),
        "冬蹄营地": ("冬蹄营地", "Camp Winterhoof"),
        "新阿加曼德": ("新阿加曼德", "New Agamand"),
        "复仇港": ("复仇港", "Vengeance Landing"),
        "卡玛古": ("卡玛古", "Kamagua"),
    },
    "sholazar": {
        "奈辛瓦里营地": ("奈辛瓦里营地", "Nesingwary Base Camp"),
        "河流之心": ("河流之心", "River's Heart"),
        "龙眠神殿": ("龙眠神殿", "Wyrmrest Temple"),
        "达拉然": ("达拉然", "Dalaran"),
        "银色比武场": ("银色比武场", "Argent Tournament"),
    },
}

# Flight points inherited from already-completed earlier maps. Route-local opening actions are
# still discovered from the point timeline below.
INITIAL_OPENED_HUBS: dict[str, set[str]] = {
    "sholazar": {"龙眠神殿", "达拉然", "银色比武场"},
}


def point_text(point: list[Any]) -> str:
    return " ".join(str(value or "") for value in point[2:6])


def mentioned_hubs(text: str, aliases: dict[str, tuple[str, ...]]) -> list[str]:
    matches: list[tuple[int, str]] = []
    for canonical, names in aliases.items():
        last = max((text.rfind(alias) for alias in names), default=-1)
        if last >= 0:
            matches.append((last, canonical))
    matches.sort()
    return [canonical for _, canonical in matches]


def opened_hubs_from_text(text: str, aliases: dict[str, tuple[str, ...]]) -> list[str]:
    if "飞行点" not in text or not any(token in text for token in ("开启", "开飞行点", "开点")):
        return []
    return mentioned_hubs(text, aliases)


def flight_destination(point: list[Any], aliases: dict[str, tuple[str, ...]]) -> str | None:
    label = str(point[2] if len(point) > 2 else "")
    if "→" in label:
        arrow_target = label.rsplit("→", 1)[-1]
        hubs = mentioned_hubs(arrow_target, aliases)
        if hubs:
            return hubs[-1]

    text = point_text(point)
    hubs = mentioned_hubs(text, aliases)
    if not hubs:
        return None
    return hubs[-1]


def audit_route(route_key: str, route: dict[str, Any]) -> dict[str, Any]:
    aliases = HUB_ALIASES[route_key]
    opened: set[str] = set(INITIAL_OPENED_HUBS.get(route_key, set()))
    flights: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    unknown_destinations: list[dict[str, Any]] = []

    for index, point in enumerate(route.get("points", [])):
        text = point_text(point)
        opened_before = sorted(opened)
        transport = str(point[6] if len(point) > 6 and point[6] else "ride")
        # Transport metadata is authoritative. For legacy rows without taxi metadata, only the
        # step label/action may imply an actual flight; notes about *future* flight availability must not.
        action_text = " ".join(str(value or "") for value in point[2:4])
        is_system_flight = transport == "taxi" or (transport != "crossmap" and any(token in action_text for token in ("系统鸟", "系统航线", "系统飞行")))

        if is_system_flight:
            destination = flight_destination(point, aliases)
            row = {
                "point_index": index,
                "label": point[2] if len(point) > 2 else "",
                "action": point[3] if len(point) > 3 else "",
                "transport": transport,
                "destination_hub": destination,
                "opened_before_arrival": opened_before,
            }
            flights.append(row)
            if destination is None:
                unknown_destinations.append(row)
            elif destination not in opened:
                violations.append(row)

        # Opening a destination on arrival affects only later flight edges, never the edge
        # used to reach this point.
        for hub in opened_hubs_from_text(text, aliases):
            opened.add(hub)

    return {
        "route_key": route_key,
        "flight_count": len(flights),
        "violation_count": len(violations),
        "unknown_destination_count": len(unknown_destinations),
        "flights": flights,
        "violations": violations,
        "unknown_destinations": unknown_destinations,
        "final_opened_flight_points": sorted(opened),
    }


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    result = {
        "status": "route_timepoint_flight_state_audit",
        "rule": "A system-flight destination may be used only after that destination flight point has been opened earlier in the route timeline.",
        "routes": {
            key: audit_route(key, routes[key])
            for key in ("borean", "dragonblight", "grizzly", "zuldrak", "storm", "icecrown", "howling", "sholazar")
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: {
            "flight_count": row["flight_count"],
            "violation_count": row["violation_count"],
            "unknown_destination_count": row["unknown_destination_count"],
            "violations": [
                {
                    "point_index": item["point_index"],
                    "label": item["label"],
                    "destination_hub": item["destination_hub"],
                    "opened_before_arrival": item["opened_before_arrival"],
                }
                for item in row["violations"]
            ],
        }
        for key, row in result["routes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["unknown_destination_count"] for row in result["routes"].values()):
        raise SystemExit("Flight-state audit has unknown flight destinations; add an explicit hub alias before trusting the result.")
    if any(row["violation_count"] for row in result["routes"].values()):
        raise SystemExit("Flight-state audit found a system flight whose destination had not been opened earlier in the route timeline.")


if __name__ == "__main__":
    main()
