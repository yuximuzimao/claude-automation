from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/route-atlas/route-atlas-timing-estimates.json"
BOREAN_FOUNDATION = ROOT / "data/route-atlas/borean-tundra-task-foundation.json"
DRAGON_FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
GRIZZLY_FOUNDATION = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
ZULDRAK_FOUNDATION = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
ZANG_AUDIT = ROOT / "data/route-atlas/zangarmarsh-global-solver-input-audit.json"
FIVEBOX_OBS = ROOT / "data/observations/fivebox-task-types.json"

# WoW map dimensions in yards. The first two are already used by the project;
# Nagrand/Dragonblight use the standard WotLK world-map dimensions for the same
# 0-100 coordinate system as the Route Atlas points.
MAP_SIZE_YARDS: dict[str, tuple[float, float]] = {
    "zang": (5027.0835, 3352.0833),
    "nagrand": (5525.0, 3683.3333),
    "borean": (5764.5830, 3843.7499),
    "dragonblight": (5608.3333, 3739.5833),
    "grizzly": (5249.9999, 3499.9999),
    "zuldrak": (4993.75, 3329.1665),
}

GROUND_SPEED_YPS = 16.8
GROUND_PATH_FACTOR = {
    "zang": 1.20,
    "nagrand": 1.17,
    "borean": 1.15,
    "dragonblight": 1.18,
    "grizzly": 1.18,
    "zuldrak": 1.20,
}
TAXI_SPEED_YPS = 32.0
TAXI_PATH_FACTOR = 1.25
SCRIPT_SPEED_YPS = 28.0
SCRIPT_PATH_FACTOR = 1.10
COMBAT_SECONDS_PER_MOB = 15.0
PERSONAL_LOOT_SECONDS_PER_CORPSE = 9.0
FIXED_OBJECT_SECONDS_PER_CHARACTER = 7.0
FIVEBOX = 5
DEFAULT_DROP_RATE = 0.50
ACCEPT_TURNIN_BASE_MINUTES = 0.65
ACCEPT_TURNIN_PER_QUEST_MINUTES = 0.16

HEARTH_CHAINS = {
    "zang": ["萨布拉金"],
    "nagrand": ["加拉达尔"],
    "borean": ["战歌要塞"],
    "dragonblight": ["阿格玛之锤"],
    "grizzly": ["征服堡"],
    "zuldrak": ["希姆托加"],
}

# Old Zangarmarsh/Nagrand point data predates typed transport fields, so these
# point indices correct only the movement edge INTO the named point.
TRANSPORT_OVERRIDES: dict[str, dict[int, str]] = {
    "zang": {7: "hearth", 9: "taxi", 15: "hearth", 32: "hearth", 37: "hearth", 41: "hearth"},
    "nagrand": {6: "hearth"},
}

# Actual timings are shown only when the recorded window is trustworthy and is
# explicitly scoped. Empty means the HTML intentionally shows no actual line.
ROUTE_POINT_EXTRA_MINUTES: dict[tuple[str, str], float] = {
    # Cross-map five-box service that cannot be represented by same-map Route Atlas geometry:
    # use the long-carried Dalaran teleport, move to Vixx, accept 12974 on all five characters,
    # open Dalaran flight if needed, then taxi back to the already-open Argent Stand.
    ("zuldrak", "银色前沿·达拉然短往返"): 6.0,
}

ACTUAL_RUNS: dict[str, list[dict[str, Any]]] = {
    "zang": [],
    "nagrand": [
        {
            "label": "首组实测（加拉达尔交付→到68）",
            "minutes": 41.4333,
            "note": "2026-08-15 Journey连续窗口 04:12:14→04:53:40；只代表该范围，不冒充完整跨图起点墙钟。",
        }
    ],
    # Long Borean Journey windows are intentionally excluded: the first run contains
    # extended AI discussion/route editing, learning and pauses, so it is progress evidence
    # rather than a clean wall-clock sample. Only future short, explicitly clean windows may
    # return here as timing calibration/display evidence.
    "borean": [],
    "dragonblight": [],
    "grizzly": [],
    "zuldrak": [],
}

# These tasks contain scripts/events whose service time is not recoverable from
# typed Questie objectives alone. Values exclude route movement and Hub hand-in.
SPECIAL_SERVICE_MINUTES: dict[str, float] = {
    "越狱": 2.5,
    # Verified five-box task mechanics from the first Borean run. These are intrinsic
    # task-service estimates only; route movement remains separate.
    "应急的物资": 7 * FIVEBOX * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0,
    "修修补补": (((5 / DEFAULT_DROP_RATE) + 1.2 * math.sqrt(5 * (1.0 - DEFAULT_DROP_RATE)) / DEFAULT_DROP_RATE) * (COMBAT_SECONDS_PER_MOB + PERSONAL_LOOT_SECONDS_PER_CORPSE) + 5 * FIVEBOX * FIXED_OBJECT_SECONDS_PER_CHARACTER) / 60.0,
    "海象人的先祖": 3 * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0,
    "蓝龙的卵": (5 * COMBAT_SECONDS_PER_MOB + 5 * FIXED_OBJECT_SECONDS_PER_CHARACTER) / 60.0,
    "牢笼": 2 * (COMBAT_SECONDS_PER_MOB + PERSONAL_LOOT_SECONDS_PER_CORPSE) / 60.0,
    "耐心是我们不需要的美德": 15 * FIVEBOX * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0,
    "纳萨姆平原": 15.0,  # user field upper bound: <=3 min per character * 5 sequential characters
    "监视裂谷：悬崖异常": 0.8,
    "调查": 3.5,
    "监视裂谷：峭壁断层": 0.8,
    "说服的艺术": 2.0,
    "与时间赛跑": 2.0,
    "营救艾瓦诺尔": 3.5,
    "猎龙": 3.5,
    "莎拉苟萨的末日": 3.0,
    "集结红龙": 2.0,
    "触动陷阱": 2.5,
    "空气的幻象": 3.0,
    "学习沟通": 1.2,  # one Scudder corpse + five sequential shell uses on the same corpse
    "冬鳞鱼人的贸易": 4.0,  # user-confirmed ground-clam pickup preferred; includes local search/5-box handling allowance
    "救救蝌蚪！": 4.0,  # user-confirmed group-shared progress; one 20-tadpole pass, not five separate passes
    "逃离冬鳞洞穴": 4.5,
    "横贯冰原": 6.0,
    # Grizzly Hills script/mixed-objective tasks. These are service-only centers; movement and Hub
    # handling remain separate, and five-box uncertainty is kept in the route range until first-run data exists.
    "幻象之瓶": 6.0,
    "必要的牺牲": 4.5,
    "破损的日记": 10.0,
    "符文中的预言": 3.5,
    "喔——哒！！": 4.5,
    "终获解救": 4.5,
    "死后相见": 3.0,
    "冷静一下，伙计": 8.0,
    "金亚拉克的末日": 4.5,
    "狼人的末日": 8.0,
    "有趣的计划": 0.7,
    "我们有能源": 4.5,
    "摧毁树苗": 3.5,
    "熊的美食": 7.0,
}

# Zangarmarsh's first run was performed while the route was still being redesigned,
# so the full raw elapsed time is not a reusable actual. These clean per-step
# budgets keep the verified route/task complexity while removing the obvious
# first-run pauses and learning detours.
ZANG_CENTER_OVERRIDES: dict[int, float] = {
    1: 12.0, 2: 30.0, 3: 25.0, 4: 15.0, 5: 35.0, 6: 30.0, 7: 35.0,
    8: 22.0, 9: 42.0, 10: 32.0, 11: 15.0, 12: 35.0, 13: 12.0,
}

# Borean currently has no step-level wall-clock overrides. The first live run contains
# learning, route editing and long AI-discussion pauses, and the route was subsequently
# restored from an efficiency-pruned version to the 68+ full-clear objective. Reusing the
# old step centers would therefore mix obsolete task selection with contaminated wall time.
# Keep all Borean steps on the component model until a clean repeated run supplies scoped
# evidence; short accept/turn-in observations should update task/Hub components rather than
# overwrite an entire logical step.
BOREAN_CENTER_OVERRIDES: dict[int, float] = {}

# Nagrand is only four player blocks and was actually run in a continuous
# 41-minute sprint. The current reusable route stops at 68, so the conditional
# fourth block is timed but excluded from the normal map total.
NAGRAND_CENTER_OVERRIDES: dict[int, float] = {1: 8.5, 2: 19.5, 3: 12.0, 4: 16.0}
NAGRAND_EXCLUDE_FROM_TOTAL = {4}

OBJECTIVE_TOKENS = (
    "完成",
    "做《",
    "做完",
    "击杀",
    "杀死",
    "消灭",
    "收集",
    "采集",
    "拾取",
    "调查",
    "侦察",
    "摧毁",
    "烧毁",
    "解救",
    "营救",
    "释放",
    "护送",
    "净化",
    "阻止",
    "夺取",
    "找到",
    "打败",
    "打服",
    "使用",
    "补完",
)


def expected_slowest_five_kills(required: int, drop_rate: float = DEFAULT_DROP_RATE) -> float:
    mean = required / drop_rate
    std = math.sqrt(required * (1.0 - drop_rate)) / drop_rate
    return mean + 1.2 * std


def load_foundation(path: Path) -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in data["tasks"] if str(row.get("scope_status", "")).startswith("include_")]
    by_name: dict[str, dict[str, Any]] = {}
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        by_id[int(row["quest_id"])] = row
        by_name.setdefault(str(row["name"]), row)
    return by_name, by_id


def load_zang_objective_seconds() -> dict[str, float]:
    data = json.loads(ZANG_AUDIT.read_text(encoding="utf-8"))
    result: dict[str, float] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            name = value.get("name")
            seconds = value.get("objective_seconds")
            if isinstance(name, str) and isinstance(seconds, (int, float)) and seconds >= 0:
                result[name] = float(seconds)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return result


def count_sum(task: dict[str, Any], objective_type: str) -> int:
    total = 0
    for obj in task.get("objectives", []):
        if obj.get("objective_type") != objective_type:
            continue
        required = obj.get("required_count")
        total += int(required) if isinstance(required, int) and required > 0 else 1
    return total


def task_mechanic_type(task_id: int, observations: dict[str, Any]) -> str:
    row = observations.get("tasks", {}).get(str(task_id), {})
    return str(row.get("type") or "")


def estimate_foundation_task_service_audit(task: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    """Return task-intrinsic service time without route movement or hub handling.

    The route estimator may use broad fallbacks to keep whole-route totals closed. This
    audit is stricter: if the task mechanism/count is not strong enough for a defensible
    task-level estimate, return unknown instead of inventing a default duration.
    """
    name = str(task["name"])
    if name in SPECIAL_SERVICE_MINUTES:
        return {"status": "estimated", "minutes": SPECIAL_SERVICE_MINUTES[name], "basis": "special_service_override"}

    cls = str(task.get("task_class") or "")
    mechanic = task_mechanic_type(int(task["quest_id"]), observations)
    shared = "shared" in mechanic and "personal" not in mechanic

    if cls == "travel_dialogue_or_turnin":
        if name == "攻击！":
            return {"status": "estimated", "minutes": 2.5, "basis": "known_script_service"}
        return {"status": "estimated", "minutes": 0.0, "basis": "no_independent_objective_service_hub_time_separate"}
    if cls in {"shared_kill", "multi_target_shared_kill"}:
        return {"status": "estimated", "minutes": count_sum(task, "kill") * COMBAT_SECONDS_PER_MOB / 60.0, "basis": "shared_kill_model"}
    if cls in {"single_named_kill", "single_named_drop", "single_creature_drop"}:
        return {"status": "estimated", "minutes": 1.5, "basis": "single_target_model"}
    if cls == "multi_creature_personal_drop":
        minutes = 0.0
        for obj in task.get("objectives", []):
            if obj.get("objective_type") != "item":
                continue
            required = obj.get("required_count")
            if not isinstance(required, int) or required <= 0:
                return {"status": "unknown", "minutes": None, "basis": "missing_item_count"}
            kills = expected_slowest_five_kills(required)
            minutes += kills * (COMBAT_SECONDS_PER_MOB + PERSONAL_LOOT_SECONDS_PER_CORPSE) / 60.0
        return {"status": "estimated", "minutes": minutes, "basis": "fivebox_personal_drop_model"}
    if cls in {"world_object_collection", "world_object_item_collection"}:
        objective_type = "object" if cls == "world_object_collection" else "item"
        matching = [obj for obj in task.get("objectives", []) if obj.get("objective_type") == objective_type]
        if any(not isinstance(obj.get("required_count"), int) or obj.get("required_count") <= 0 for obj in matching):
            return {"status": "unknown", "minutes": None, "basis": "missing_world_object_count"}
        count = sum(int(obj["required_count"]) for obj in matching)
        multiplier = 1 if shared else FIVEBOX
        return {"status": "estimated", "minutes": count * multiplier * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0, "basis": "fixed_object_fivebox_model"}
    if cls == "fixed_object_interaction":
        return {"status": "estimated", "minutes": (1 if shared else FIVEBOX) * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0, "basis": "single_fixed_object_model"}
    if cls == "mixed_with_personal_item":
        minutes = count_sum(task, "kill") * COMBAT_SECONDS_PER_MOB / 60.0
        for obj in task.get("objectives", []):
            if obj.get("objective_type") != "item":
                continue
            required = obj.get("required_count")
            if not isinstance(required, int) or required <= 0:
                return {"status": "unknown", "minutes": None, "basis": "missing_mixed_item_count"}
            if required == 1:
                minutes += 0.75
            else:
                kills = expected_slowest_five_kills(required)
                minutes += kills * (COMBAT_SECONDS_PER_MOB + PERSONAL_LOOT_SECONDS_PER_CORPSE) / 60.0
        return {"status": "estimated", "minutes": minutes, "basis": "mixed_personal_item_model"}
    if cls == "mixed_objectives":
        if name == "让他们安息":
            return {"status": "estimated", "minutes": 20 * COMBAT_SECONDS_PER_MOB / 60.0, "basis": "task_specific_mixed_override"}
        if name == "亡者的尊严":
            multiplier = 1 if shared else FIVEBOX
            return {"status": "estimated", "minutes": 10 * multiplier * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0, "basis": "task_specific_corpse_use_observation_aware"}
        if name == "就是他们！":
            return {"status": "estimated", "minutes": 15 * COMBAT_SECONDS_PER_MOB / 60.0, "basis": "task_specific_mixed_override"}
        for obj in task.get("objectives", []):
            if obj.get("objective_type") in {"kill", "event", "object"} and (not isinstance(obj.get("required_count"), int) or obj.get("required_count") <= 0):
                return {"status": "unknown", "minutes": None, "basis": "missing_mixed_objective_count"}
        kills = count_sum(task, "kill")
        events = count_sum(task, "event")
        objects = count_sum(task, "object")
        return {"status": "estimated", "minutes": max(1.5, kills * COMBAT_SECONDS_PER_MOB / 60.0 + events * 0.6 + objects * 0.4), "basis": "mixed_objective_model"}
    if cls == "item_source_not_in_questie":
        return {"status": "unknown", "minutes": None, "basis": "item_source_not_in_questie"}
    return {"status": "unknown", "minutes": None, "basis": f"unsupported_task_class:{cls}"}


def estimate_foundation_task_service(task: dict[str, Any], observations: dict[str, Any]) -> float:
    stored = task.get("intrinsic_service_time") or {}
    if stored.get("status") == "estimated" and str(stored.get("basis") or "").startswith("manual_pre_route:"):
        return float(stored["minutes"])
    audit = estimate_foundation_task_service_audit(task, observations)
    if audit["status"] == "estimated":
        return float(audit["minutes"])
    # Whole-route totals retain the historical fallback. The per-task audit never exposes
    # this fallback as a real task estimate.
    return 2.0


def objective_names_for_group(route: dict[str, Any], group: dict[str, Any], known_names: set[str]) -> list[str]:
    names: list[str] = []
    for point in route["points"][group["start"] : group["end"] + 1]:
        action = str(point[3])
        for clause in re.split(r"[；。]", action):
            # Do not let words inside quest titles (e.g. 《夺取装备》) falsely
            # classify a pure accept/turn-in clause as objective execution.
            prose = re.sub(r"《[^》]+》", "", clause)
            if not any(token in prose for token in OBJECTIVE_TOKENS):
                continue
            # Background/conditional opportunity work is not charged as a full
            # foreground service block unless the clause explicitly completes it.
            if any(token in prose for token in ("若", "自然经过", "顺手", "沿路")) and "完成" not in prose and "做" not in prose:
                continue
            for name in re.findall(r"《([^》]+)》", clause):
                if name in known_names and name not in names:
                    names.append(name)
    return names


def hub_minutes(route: dict[str, Any], group: dict[str, Any]) -> float:
    total = 0.0
    for point in route["points"][group["start"] : group["end"] + 1]:
        action = str(point[3])
        # Player text now requires every accept/turn-in to carry its own explicit verb
        # (`交《A》接《B》`, `交《A》交《B》接《C》`). Formatting punctuation must not
        # change the wall-clock estimate: one geometric stop pays the base stop cost once,
        # while each explicit accept/turn-in operation pays only the per-quest handling cost.
        operations = re.findall(r"(?:交|接)《[^》]+》", action)
        if operations:
            total += ACCEPT_TURNIN_BASE_MINUTES + ACCEPT_TURNIN_PER_QUEST_MINUTES * len(operations)
    return total


def transport_kind(route_key: str, point_index: int, point: list[Any]) -> str:
    override = TRANSPORT_OVERRIDES.get(route_key, {}).get(point_index)
    if override:
        return override
    return str(point[6] if len(point) > 6 and point[6] else "ride")


def movement_minutes(route_key: str, route: dict[str, Any], group: dict[str, Any]) -> float:
    width, height = MAP_SIZE_YARDS[route_key]
    total = 0.0
    for idx in range(group["start"], group["end"] + 1):
        if idx <= 0:
            continue
        a = route["points"][idx - 1]
        b = route["points"][idx]
        dx = (float(b[0]) - float(a[0])) / 100.0 * width
        dy = (float(b[1]) - float(a[1])) / 100.0 * height
        distance = math.hypot(dx, dy)
        kind = transport_kind(route_key, idx, b)
        if kind == "ride":
            total += distance / GROUND_SPEED_YPS / 60.0 * GROUND_PATH_FACTOR[route_key]
        elif kind == "taxi":
            total += distance / TAXI_SPEED_YPS / 60.0 * TAXI_PATH_FACTOR + 0.2
        elif kind == "script":
            total += distance / SCRIPT_SPEED_YPS / 60.0 * SCRIPT_PATH_FACTOR + 0.35
        elif kind == "hearth":
            total += 0.35
        elif kind == "crossmap":
            total += 0.0
    return total


def generic_uncertainty(task_names: list[str], tasks_by_name: dict[str, dict[str, Any]]) -> float:
    risky = {
        "multi_creature_personal_drop",
        "mixed_with_personal_item",
        "mixed_objectives",
        "item_source_not_in_questie",
    }
    if any(str(tasks_by_name.get(name, {}).get("task_class")) in risky for name in task_names):
        return 0.25
    return 0.18


def estimate_route(
    route_key: str,
    route: dict[str, Any],
    foundation_by_name: dict[str, dict[str, Any]],
    zang_seconds: dict[str, float],
    observations: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    known_names = set(foundation_by_name) if route_key in {"borean", "dragonblight", "grizzly", "zuldrak"} else set(zang_seconds)

    for step, group in enumerate(route["stepGroups"], 1):
        move = movement_minutes(route_key, route, group)
        hub = hub_minutes(route, group)
        names = objective_names_for_group(route, group, known_names)

        if route_key == "zang":
            service = sum(zang_seconds[name] / 60.0 for name in names)
            uncertainty = 0.25 if names else 0.18
        elif route_key in {"borean", "dragonblight", "grizzly", "zuldrak"}:
            service = sum(estimate_foundation_task_service(foundation_by_name[name], observations) for name in names)
            uncertainty = generic_uncertainty(names, foundation_by_name)
        else:
            service = 0.0
            uncertainty = 0.20

        point_extra = sum(
            ROUTE_POINT_EXTRA_MINUTES.get((route_key, str(point[2])), 0.0)
            for point in route["points"][group["start"] : group["end"] + 1]
        )
        special = (0.5 if names else 0.0) + point_extra
        center = move + hub + service + special

        if route_key == "zang":
            center = ZANG_CENTER_OVERRIDES[step]
            uncertainty = 0.22 if step in {2, 3, 5, 6, 7, 9, 10, 12} else 0.18
        elif route_key == "nagrand":
            center = NAGRAND_CENTER_OVERRIDES[step]
            uncertainty = 0.18 if step == 1 else 0.22
        elif route_key == "borean" and step in BOREAN_CENTER_OVERRIDES:
            center = BOREAN_CENTER_OVERRIDES[step]
            uncertainty = 0.20 if step <= 47 else (0.22 if step in {52, 54, 56, 60, 61, 62, 64, 65} else 0.12)
        else:
            # A logical route step with no typed objective still has task switching,
            # local navigation, formation and dialogue overhead not represented by
            # pure point-to-point geometry.
            center = max(center, move + hub + 1.0)

        low = min(center, max(move + min(hub, center), center * (1.0 - uncertainty)))
        high = center * (1.0 + uncertainty)
        include_in_total = not (route_key == "nagrand" and step in NAGRAND_EXCLUDE_FROM_TOTAL)
        row = {
            "step": step,
            "title": group["title"],
            "centerMinutes": round(center, 1),
            "rangeMinutes": [round(low, 1), round(high, 1)],
            "includeInTotal": include_in_total,
            "components": {
                "moveMinutes": round(move, 1),
                "objectiveMinutes": round(service, 1),
                "hubMinutes": round(hub, 1),
                "specialMinutes": round(special, 1),
            },
            "objectiveTasks": names,
        }
        rows.append(row)

    included = [row for row in rows if row["includeInTotal"]]
    center_total = round(sum(row["centerMinutes"] for row in included), 1)
    low_total = round(sum(row["rangeMinutes"][0] for row in included), 1)
    high_total = round(sum(row["rangeMinutes"][1] for row in included), 1)
    return {
        "route": route_key,
        "model": "component-wall-clock-v1",
        "hearthChain": HEARTH_CHAINS[route_key],
        "centerMinutes": center_total,
        "rangeMinutes": [low_total, high_total],
        "actualRuns": ACTUAL_RUNS[route_key],
        "rows": rows,
    }


def format_minutes(minutes: float) -> str:
    """Actual wall-clock display: preserve seconds when the record has them."""
    total_seconds = int(round(minutes * 60))
    hours, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        if secs:
            return f"{hours}小时{mins}分{secs}秒"
        return f"{hours}小时{mins}分"
    if secs:
        return f"{mins}分{secs}秒"
    return f"{mins}分钟"


def format_expected_minutes(minutes: float) -> str:
    """Predictions are deliberately shown at minute precision, never fake seconds."""
    total = max(1, int(round(minutes)))
    hours, mins = divmod(total, 60)
    if hours:
        return f"{hours}小时{mins}分" if mins else f"{hours}小时"
    return f"{mins}分钟"


def apply_to_routes(routes: dict[str, Any], estimates: dict[str, Any]) -> None:
    for key, estimate in estimates.items():
        route = routes[key]
        route["hearthChain"] = estimate["hearthChain"]
        route["timing"] = {
            "centerMinutes": estimate["centerMinutes"],
            "rangeMinutes": estimate["rangeMinutes"],
            "actualRuns": estimate["actualRuns"],
            "model": estimate["model"],
        }
        route.pop("badgeTitle", None)
        hearth = "-".join(estimate["hearthChain"])
        low, high = estimate["rangeMinutes"]
        parts = [
            f"炉石：{hearth}",
            f"预计总时间：{format_expected_minutes(estimate['centerMinutes'])}（{format_expected_minutes(low)}—{format_expected_minutes(high)}）",
        ]
        for run in estimate["actualRuns"]:
            parts.append(f"{run['label']}：{format_minutes(float(run['minutes']))}")
        route["badge"] = "\n".join(parts)
        for group, row in zip(route["stepGroups"], estimate["rows"], strict=True):
            group["timing"] = {
                "centerMinutes": row["centerMinutes"],
                "rangeMinutes": row["rangeMinutes"],
                "includeInTotal": row["includeInTotal"],
            }


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    borean_by_name, _ = load_foundation(BOREAN_FOUNDATION)
    dragon_by_name, _ = load_foundation(DRAGON_FOUNDATION)
    grizzly_by_name, _ = load_foundation(GRIZZLY_FOUNDATION)
    zuldrak_by_name, _ = load_foundation(ZULDRAK_FOUNDATION)
    zang_seconds = load_zang_objective_seconds()
    observations = json.loads(FIVEBOX_OBS.read_text(encoding="utf-8"))

    foundations = {
        "zang": {},
        "nagrand": {},
        "borean": borean_by_name,
        "dragonblight": dragon_by_name,
        "grizzly": grizzly_by_name,
        "zuldrak": zuldrak_by_name,
    }
    estimates = {
        key: estimate_route(key, routes[key], foundations[key], zang_seconds, observations)
        for key in ("zang", "nagrand", "borean", "dragonblight", "grizzly", "zuldrak")
    }
    apply_to_routes(routes, estimates)
    ROUTES.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(estimates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for key, estimate in estimates.items():
        (ROOT / "data/route-atlas" / f"{key}-timing-estimate.json").write_text(
            json.dumps(estimate, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        key: {
            "hearth": "-".join(value["hearthChain"]),
            "expected_minutes": value["centerMinutes"],
            "range_minutes": value["rangeMinutes"],
            "actual": [{"label": run["label"], "minutes": round(float(run["minutes"]), 2)} for run in value["actualRuns"]],
            "steps": len(value["rows"]),
        }
        for key, value in estimates.items()
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
