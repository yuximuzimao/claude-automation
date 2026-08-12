from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SQL_TUPLE = re.compile(r"^\((.*)\)[,;]$")


def sql_columns(path: Path) -> list[str]:
    columns: list[str] = []
    in_create = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CREATE TABLE"):
            in_create = True
            continue
        if in_create and line.lstrip().startswith("`"):
            match = re.match(r"\s*`([^`]+)`", line)
            if match:
                columns.append(match.group(1))
        if in_create and line.lstrip().startswith("PRIMARY KEY"):
            break
    return columns


def parse_scalar(value: str) -> Any:
    if value == "NULL":
        return None
    try:
        if any(char in value for char in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def iter_sql_rows(path: Path) -> Iterable[list[Any]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for raw in handle:
            line = raw.strip()
            match = SQL_TUPLE.match(line)
            if not match:
                continue
            values = next(csv.reader(
                [match.group(1)],
                delimiter=",",
                quotechar="'",
                escapechar="\\",
                doublequote=False,
            ))
            yield [parse_scalar(value) for value in values]


def effective_group_chances(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["groupid"])].append(row)
    result: list[dict[str, Any]] = []
    for group_id, group_rows in grouped.items():
        if group_id == 0:
            for row in group_rows:
                copy = dict(row)
                copy["effective_chance"] = abs(float(row["chance"]))
                result.append(copy)
            continue
        explicit = sum(abs(float(row["chance"])) for row in group_rows if float(row["chance"]) != 0)
        zeros = [row for row in group_rows if float(row["chance"]) == 0]
        equal = max(0.0, 100.0 - explicit) / len(zeros) if zeros else 0.0
        for row in group_rows:
            copy = dict(row)
            copy["effective_chance"] = equal if float(row["chance"]) == 0 else abs(float(row["chance"]))
            result.append(copy)
    return result


def load_loot_table(path: Path) -> dict[int, list[dict[str, Any]]]:
    columns = sql_columns(path)
    index = {name: columns.index(name) for name in columns}
    raw: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for values in iter_sql_rows(path):
        if len(values) != len(columns):
            continue
        entry = int(values[index["entry"]])
        raw[entry].append({
            "entry": entry,
            "item": int(values[index["item"]]),
            "chance": float(values[index["ChanceOrQuestChance"]]),
            "lootmode": int(values[index["lootmode"]]),
            "groupid": int(values[index["groupid"]]),
            "mincount_or_ref": int(values[index["mincountOrRef"]]),
            "maxcount": int(values[index["maxcount"]]),
        })
    return {entry: effective_group_chances(rows) for entry, rows in raw.items()}


def load_creature_templates(path: Path, wanted: set[int]) -> dict[int, dict[str, Any]]:
    columns = sql_columns(path)
    index = {name: columns.index(name) for name in columns}
    result: dict[int, dict[str, Any]] = {}
    for values in iter_sql_rows(path):
        if len(values) != len(columns):
            continue
        entry = int(values[index["entry"]])
        if entry not in wanted:
            continue
        result[entry] = {
            "entry": entry,
            "name": str(values[index["name"]]),
            "lootid": int(values[index["lootid"]]),
            "quest_items": [
                int(values[index[f"questItem{number}"]])
                for number in range(1, 7)
                if int(values[index[f"questItem{number}"]]) > 0
            ],
        }
    return result


def load_gameobject_templates(path: Path, wanted: set[int]) -> dict[int, dict[str, Any]]:
    columns = sql_columns(path)
    index = {name: columns.index(name) for name in columns}
    result: dict[int, dict[str, Any]] = {}
    for values in iter_sql_rows(path):
        if len(values) != len(columns):
            continue
        entry = int(values[index["entry"]])
        if entry not in wanted:
            continue
        object_type = int(values[index["type"]])
        # For chest objects (type 3), Data1 is the loot-template entry.
        lootid = int(values[index["Data1"]]) if object_type == 3 else 0
        result[entry] = {
            "entry": entry,
            "name": str(values[index["name"]]),
            "type": object_type,
            "lootid": lootid,
            "quest_items": [
                int(values[index[f"questItem{number}"]])
                for number in range(1, 7)
                if int(values[index[f"questItem{number}"]]) > 0
            ],
        }
    return result


def combine_probabilities(probabilities: list[float]) -> float:
    no_drop = 1.0
    for probability in probabilities:
        no_drop *= 1.0 - max(0.0, min(100.0, probability)) / 100.0
    return (1.0 - no_drop) * 100.0


def resolve_item_probability(
    entry: int,
    item_id: int,
    rows_by_entry: dict[int, list[dict[str, Any]]],
    reference_rows: dict[int, list[dict[str, Any]]],
    stack: tuple[int, ...] = (),
) -> list[dict[str, Any]]:
    if entry in stack:
        return []
    result: list[dict[str, Any]] = []
    for row in rows_by_entry.get(entry, []):
        chance = float(row["effective_chance"])
        if row["item"] == item_id:
            result.append({
                "probability_percent": chance,
                "quest_only": float(row["chance"]) < 0,
                "mincount": max(1, int(row["mincount_or_ref"])),
                "maxcount": max(1, int(row["maxcount"])),
                "path": [entry],
                "groupid": int(row["groupid"]),
            })
        elif int(row["mincount_or_ref"]) < 0:
            reference_id = -int(row["mincount_or_ref"])
            nested = resolve_item_probability(
                reference_id,
                item_id,
                reference_rows,
                reference_rows,
                stack + (entry,),
            )
            for value in nested:
                copy = dict(value)
                copy["probability_percent"] = chance * float(value["probability_percent"]) / 100.0
                copy["quest_only"] = bool(copy["quest_only"] or float(row["chance"]) < 0)
                copy["path"] = [entry] + list(copy["path"])
                result.append(copy)
    return result


def binomial_tail(n: int, required: int, probability: float) -> float:
    if required <= 0:
        return 1.0
    if n < required or probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    p = probability
    q = 1.0 - p
    # Start at P(X=required) in log space, then use a stable recurrence.
    log_term = (
        math.lgamma(n + 1)
        - math.lgamma(required + 1)
        - math.lgamma(n - required + 1)
        + required * math.log(p)
        + (n - required) * math.log(q)
    )
    term = math.exp(log_term) if log_term > -745 else 0.0
    total = term
    successes = required
    while successes < n and term > 0.0:
        term *= (n - successes) / (successes + 1) * p / q
        total += term
        successes += 1
    return min(1.0, total)


def slowest_of_five_kill_quantile(required: int, probability: float, quantile: float) -> int:
    if probability >= 1.0:
        return required
    n = max(required, 1)
    while n < 10_000:
        all_complete = binomial_tail(n, required, probability) ** 5
        if all_complete >= quantile:
            return n
        n += 1
    return n


def time_from_item_objective(objective: dict[str, Any], level: int) -> dict[str, float] | None:
    evidence_pairs = [
        (source, value)
        for source in objective.get("sources", [])
        for value in source.get("loot_evidence", [])
        if value.get("probability_percent") is not None
    ]
    if not evidence_pairs:
        return None
    feasible_pairs = [
        (source, value)
        for source, value in evidence_pairs
        if source.get("min_level") is None or float(source["min_level"]) <= level + 2
    ] or evidence_pairs
    source, best = max(
        feasible_pairs,
        key=lambda pair: (
            float(pair[1]["probability_percent"]),
            int(pair[0].get("spawn_count") or 0),
            -float(pair[0].get("min_level") or 99),
        ),
    )
    probability = min(1.0, float(best["probability_percent"]) / 100.0)
    count = int(objective.get("required_count") or 1)
    mincount = max(1, int(best.get("mincount", 1)))
    required_successes = math.ceil(count / mincount)
    kills = {
        "optimistic": slowest_of_five_kill_quantile(required_successes, probability, 0.20),
        "central": slowest_of_five_kill_quantile(required_successes, probability, 0.50),
        "pessimistic": slowest_of_five_kill_quantile(required_successes, probability, 0.85),
    }
    health_values = [source.get("min_health"), source.get("max_health")]
    health_values = [float(value) for value in health_values if isinstance(value, (int, float))]
    target_health = sum(health_values) / len(health_values) if health_values else max(250.0, level ** 2)
    level_values = [source.get("min_level"), source.get("max_level")]
    level_values = [float(value) for value in level_values if isinstance(value, (int, float))]
    target_level = sum(level_values) / len(level_values) if level_values else float(level)
    # Same transparent one-active-paladin profile as the foundation script.
    anchors = {35: (34, 44, 58), 40: (43, 57, 75), 45: (57, 76, 99), 50: (74, 98, 128), 55: (92, 122, 158)}
    lower = max(key for key in anchors if key <= level)
    upper = min(key for key in anchors if key >= level)
    ratio = 0 if lower == upper else (level - lower) / (upper - lower)
    dps = tuple(anchors[lower][i] + ratio * (anchors[upper][i] - anchors[lower][i]) for i in range(3))
    delta = target_level - level
    penalties = (1.0, 1.0, 1.05) if delta <= 0 else ((1.05, 1.12, 1.25) if delta <= 1 else ((1.12, 1.32, 1.65) if delta <= 2 else ((1.25, 1.70, 2.30) if delta <= 3 else ((1.45, 2.35, 3.40) if delta <= 4 else (1.80, 3.50, 6.00)))))
    seconds = {
        "optimistic": target_health / dps[2] * penalties[0] + 6.0 + 5 * 4.0,
        "central": target_health / dps[1] * penalties[1] + 9.0 + 5 * 7.0,
        "pessimistic": target_health / dps[0] * penalties[2] + 14.0 + 5 * 10.0,
    }
    return {key: round(kills[key] * seconds[key] / 60.0, 2) for key in kills} | {
        "kills_optimistic": kills["optimistic"],
        "kills_central": kills["central"],
        "kills_pessimistic": kills["pessimistic"],
        "probability_percent": round(probability * 100, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich the 35-55 task foundation with AzerothCore WotLK loot rates")
    parser.add_argument("--foundation", default="data/routes/horde/blood-elf/35-55-task-foundation.json")
    parser.add_argument("--database", default="_sandbox/azerothcore-database-wotlk/extracted")
    parser.add_argument("--output", default="data/routes/horde/blood-elf/35-55-task-foundation-enriched.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / args.foundation).read_text(encoding="utf-8"))
    database = root / args.database

    wanted_npcs: set[int] = set()
    wanted_objects: set[int] = set()
    wanted_items: set[int] = set()
    for task in payload["tasks"]:
        for objective in task.get("objectives", []):
            if objective.get("item_id"):
                wanted_items.add(int(objective["item_id"]))
            for source in objective.get("sources", []):
                if source.get("entity_type") == "npc":
                    wanted_npcs.add(int(source["entity_id"]))
                elif source.get("entity_type") == "object":
                    wanted_objects.add(int(source["entity_id"]))

    creature_templates = load_creature_templates(database / "creature_template.sql", wanted_npcs)
    object_templates = load_gameobject_templates(database / "gameobject_template.sql", wanted_objects)
    creature_loot = load_loot_table(database / "creature_loot_template.sql")
    object_loot = load_loot_table(database / "gameobject_loot_template.sql")
    reference_loot = load_loot_table(database / "reference_loot_template.sql")

    evidence_count = 0
    exact_item_objectives = 0
    for task in payload["tasks"]:
        exact_objective_times: dict[int, dict[str, Any]] = {}
        for objective_index, objective in enumerate(task.get("objectives", [])):
            item_id = objective.get("item_id")
            if not item_id:
                continue
            item_id = int(item_id)
            for source in objective.get("sources", []):
                source["loot_evidence"] = []
                source_id = int(source["entity_id"])
                if source.get("entity_type") == "npc":
                    template = creature_templates.get(source_id)
                    if template:
                        rows = resolve_item_probability(template["lootid"], item_id, creature_loot, reference_loot) if template["lootid"] else []
                        probabilities = [float(row["probability_percent"]) for row in rows]
                        if probabilities:
                            source["loot_evidence"].append({
                                "database": "AzerothCore database-wotlk",
                                "source_type": "creature_loot_template",
                                "source_id": source_id,
                                "loot_entry": template["lootid"],
                                "probability_percent": round(combine_probabilities(probabilities), 4),
                                "quest_only": any(bool(row["quest_only"]) for row in rows),
                                "mincount": min(int(row["mincount"]) for row in rows),
                                "maxcount": max(int(row["maxcount"]) for row in rows),
                                "paths": [row["path"] for row in rows],
                            })
                        elif item_id in template["quest_items"]:
                            source["loot_evidence"].append({
                                "database": "AzerothCore database-wotlk",
                                "source_type": "creature_template_questItem_slot",
                                "source_id": source_id,
                                "loot_entry": template["lootid"],
                                "probability_percent": None,
                                "quest_only": True,
                                "mincount": 1,
                                "maxcount": 1,
                            })
                elif source.get("entity_type") == "object":
                    template = object_templates.get(source_id)
                    if template:
                        rows = resolve_item_probability(template["lootid"], item_id, object_loot, reference_loot) if template["lootid"] else []
                        probabilities = [float(row["probability_percent"]) for row in rows]
                        if probabilities:
                            source["loot_evidence"].append({
                                "database": "AzerothCore database-wotlk",
                                "source_type": "gameobject_loot_template",
                                "source_id": source_id,
                                "loot_entry": template["lootid"],
                                "probability_percent": round(combine_probabilities(probabilities), 4),
                                "quest_only": any(bool(row["quest_only"]) for row in rows),
                                "mincount": min(int(row["mincount"]) for row in rows),
                                "maxcount": max(int(row["maxcount"]) for row in rows),
                                "paths": [row["path"] for row in rows],
                            })
                        elif item_id in template["quest_items"]:
                            source["loot_evidence"].append({
                                "database": "AzerothCore database-wotlk",
                                "source_type": "gameobject_template_questItem_slot",
                                "source_id": source_id,
                                "loot_entry": template["lootid"],
                                "probability_percent": 100.0 if template["type"] != 3 else None,
                                "quest_only": True,
                                "mincount": 1,
                                "maxcount": 1,
                            })
                evidence_count += len(source["loot_evidence"])
            exact_time = time_from_item_objective(objective, int(task["earliest_completion_level"]))
            if exact_time:
                objective["azerothcore_time_at_earliest_level"] = exact_time
                exact_objective_times[objective_index] = exact_time
                exact_item_objectives += 1

        if exact_objective_times:
            components = task.get("standalone_time_components") or {}
            objective_components = {
                int(value["objective_index"]): value["time"]
                for value in components.get("objectives", [])
            }
            adjusted_objectives: list[dict[str, Any]] = []
            for index in range(len(task.get("objectives", []))):
                chosen = exact_objective_times.get(index) or objective_components.get(index) or {
                    "optimistic": 0.0, "central": 0.0, "pessimistic": 0.0,
                }
                adjusted_objectives.append({
                    "objective_index": index,
                    "source": "azerothcore_loot" if index in exact_objective_times else "foundation",
                    "time": {key: float(chosen[key]) for key in ("optimistic", "central", "pessimistic")},
                })
            fixed_components = [
                components.get("travel", {}),
                components.get("interactions", {}),
                components.get("escort_or_defense", {}),
            ]
            total = {
                key: round(
                    sum(value["time"][key] for value in adjusted_objectives)
                    + sum(float(value.get(key, 0.0)) for value in fixed_components),
                    2,
                )
                for key in ("optimistic", "central", "pessimistic")
            }
            task["azerothcore_adjusted_time_components"] = {
                "objectives": adjusted_objectives,
                "travel": components.get("travel", {}),
                "interactions": components.get("interactions", {}),
                "escort_or_defense": components.get("escort_or_defense", {}),
            }
            task["azerothcore_adjusted_standalone_time"] = total
            task["azerothcore_item_objective_time_total"] = {
                key: round(sum(float(value[key]) for value in exact_objective_times.values()), 2)
                for key in ("optimistic", "central", "pessimistic")
            }
            task["loot_enrichment_status"] = "one_or_more_item_objectives_have_reference_drop_rates"
        else:
            task["azerothcore_adjusted_standalone_time"] = task["standalone_time_at_earliest_level"]
            task["loot_enrichment_status"] = "no_exact_reference_drop_rate"

    payload["loot_reference"] = {
        "source": "AzerothCore database-wotlk",
        "commit": "68fcf0098b16388093989627f37be530fc91f07d",
        "warning": "Reference WotLK database, not proof that the current private/server database is identical.",
        "creature_source_count": len(creature_templates),
        "object_source_count": len(object_templates),
        "evidence_count": evidence_count,
        "item_objectives_with_reference_rates": exact_item_objectives,
    }
    output = root / args.output
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output.relative_to(root)),
        "tasks": len(payload["tasks"]),
        "wanted_items": len(wanted_items),
        "wanted_npcs": len(wanted_npcs),
        "wanted_objects": len(wanted_objects),
        "evidence_count": evidence_count,
        "item_objectives_with_reference_rates": exact_item_objectives,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
