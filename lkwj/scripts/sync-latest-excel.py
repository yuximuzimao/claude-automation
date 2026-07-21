#!/usr/bin/env python3
import collections
import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "图鉴课题进度表（另存或存为副本使用）.xlsx"
PETS_PATH = ROOT / "data" / "pets.json"
TASKS_PATH = ROOT / "data" / "tasks.json"
CHAINS_PATH = ROOT / "data" / "evolution-chains.json"
COLLECTIONS_PATH = ROOT / "data" / "collections.json"

reader = runpy.run_path(str(ROOT / "scripts" / "read-latest-excel.py"))
read_xlsx = reader["read_xlsx"]
group_tasks = reader["group_tasks"]

sheets = read_xlsx(WORKBOOK)
pets = json.loads(PETS_PATH.read_text(encoding="utf-8"))
old_tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
chains = json.loads(CHAINS_PATH.read_text(encoding="utf-8"))
collections_data = json.loads(COLLECTIONS_PATH.read_text(encoding="utf-8"))

COMPLETE_MAX_NUMBER = 439
VERIFIED_TEXT_REPLACEMENTS = {
    "幽灵眼": "幽冥眼",
    "饮血狂兽": "饮雪狂兽",
    "斜眼巨魔": "邪眼巨魔",
    "象牙花形态": "象牙球形态",
}
PARTIAL_PETS = {
    440: {
        "name": "睡铃雪影娃娃",
        "element": [],
        "forms": {
            "basic": {
                "formName": "基础形态",
                "obtainMethods": [],
            },
        },
    },
}
VERIFIED_EVOLUTION_LEVELS = {
    430: 40,
}


def apply_verified_text_corrections(value):
    corrected = str(value or "")
    for wrong, right in VERIFIED_TEXT_REPLACEMENTS.items():
        corrected = corrected.replace(wrong, right)
    return corrected


def apply_verified_evolution_correction(number, value):
    corrected = str(value or "")
    level = VERIFIED_EVOLUTION_LEVELS.get(number)
    if level is not None:
        corrected = re.sub(r"\d+级", f"{level}级", corrected, count=1)
    return corrected


def pkey(number):
    return f"pet_{number}"


def number_from_code(value):
    match = re.fullmatch(r"N\.(\d+)", str(value or "").strip())
    return int(match.group(1)) if match else None


def canonical_name(value):
    value = apply_verified_text_corrections(value).strip()
    if value.startswith("（") and value.endswith("）"):
        value = value[1:-1].strip()
    return value.replace("两只海葵的样子", "双只海葵的样子")


def parse_form_groups(rows):
    groups = collections.OrderedDict()
    current_number = None
    current_name = None
    for row in rows[1:]:
        if row.get("B"):
            current_number = number_from_code(row.get("A"))
            current_name = row.get("B")
            if current_number:
                groups.setdefault(current_number, {"name": current_name, "rows": []})
        if current_number and row.get("D"):
            groups[current_number]["rows"].append({
                "name": canonical_name(row.get("D")),
                "rawName": row.get("D"),
                "method": row.get("E"),
            })
    return groups


def note_prefix(note):
    value = str(note or "")
    if "即可完成" in value:
        value = value.split("即可完成", 1)[0]
    return value


def form_aliases(form_name, pet_name):
    aliases = {form_name}
    if form_name == "本来的样子":
        aliases.add(pet_name)
    if form_name == "双只海葵的样子":
        aliases.update({"两只海葵的样子", "加油蟹（两只海葵的样子）", "（两只海葵的样子）"})
    return aliases


def parse_task(row, number, pet, form_groups):
    kind = row.get("type")
    content = apply_verified_text_corrections(row.get("content")).strip()
    note = apply_verified_text_corrections(row.get("note")).strip()
    if kind == "进化":
        note = apply_verified_evolution_correction(number, note)
    if kind == "捕捉":
        return {"type": "capture", "desc": "捕捉1只"}
    if kind == "天分":
        return {"type": "capture_gifted", "desc": "捕捉1只了不起天分的"}
    if kind == "亲密度":
        return {"type": "affection", "desc": content}
    if kind == "奖牌":
        return {"type": "destined_hero", "desc": "获得命定勇者奖牌"}
    if kind == "首领":
        return {"type": "leader_evolve", "desc": content or "使用进化之力，将精灵进化为首领"}
    if kind == "进化":
        task = {"type": "evolve", "desc": "成功进化一次"}
        if note:
            task["obtainMethods"] = [note]
        return task
    if kind == "炫彩":
        return {"type": "capture_chromatic", "desc": "捕捉1只炫彩突变的"}
    if kind == "异色":
        return {"type": "capture_shiny", "desc": "捕捉1只异色突变的精灵"}
    if kind == "果实":
        return {"type": "fruit", "desc": "捕捉20只精灵"}
    if kind == "技能":
        match = re.fullmatch(r"使用(\d+)次【(.+)】", content)
        if not match:
            raise ValueError(f"N.{number:03d} 无法解析技能任务：{content}")
        return {
            "type": "skill",
            "skillName": match.group(2),
            "count": int(match.group(1)),
            "desc": "使用",
        }
    if kind == "形态":
        count_match = re.search(r"确认(\d+)种", content)
        if not count_match:
            raise ValueError(f"N.{number:03d} 无法解析形态数量：{content}")
        count = int(count_match.group(1))
        available = [row["name"] for row in form_groups.get(number, {}).get("rows", [])]
        prefix = note_prefix(note)
        required = [
            form_name for form_name in available
            if any(alias in prefix for alias in form_aliases(form_name, pet.get("name", "")))
        ]
        if not required or (len(required) < count <= len(available)):
            required = available
        return {
            "type": "confirm_forms",
            "count": count,
            "desc": content,
            "requiredForms": required,
        }
    raise ValueError(f"N.{number:03d} 未支持课题类别：{kind}")


def task_signature(task):
    if task.get("type") == "skill":
        return ("skill", task.get("skillName"), task.get("count"))
    if task.get("type") == "confirm_forms":
        return ("confirm_forms", task.get("count"))
    return (task.get("type"),)


def migrate_task_progress(pet_key, old_list, new_list):
    progress = collections_data.get("sprite_progress", {}).get(pet_key, {}).get("tasks")
    if not isinstance(progress, dict):
        return {"mapped": 0, "unmapped": 0}

    available = set(range(len(new_list)))
    mapping = {}

    # First pass: exact semantic signature.
    for old_index, old_task in enumerate(old_list):
        signature = task_signature(old_task)
        candidates = [index for index in sorted(available) if task_signature(new_list[index]) == signature]
        if candidates:
            mapping[old_index] = candidates[0]
            available.remove(candidates[0])

    # Second pass: same task type, preserving sequence. This migrates corrected skill names.
    for old_index, old_task in enumerate(old_list):
        if old_index in mapping:
            continue
        candidates = [
            index for index in sorted(available)
            if new_list[index].get("type") == old_task.get("type")
        ]
        if candidates:
            mapping[old_index] = candidates[0]
            available.remove(candidates[0])

    new_progress = {}
    unmapped = 0
    for old_index_text, value in progress.items():
        try:
            old_index = int(old_index_text)
        except (TypeError, ValueError):
            unmapped += 1
            continue
        new_index = mapping.get(old_index)
        if new_index is None:
            unmapped += 1
            continue
        new_progress[str(new_index)] = value

    collections_data["sprite_progress"][pet_key]["tasks"] = new_progress
    return {"mapped": len(new_progress), "unmapped": unmapped}


def clean_condition_note(note, level):
    value = apply_verified_text_corrections(note).strip()
    value = value.replace("（两只海葵的样子）", "双只海葵的样子")
    value = value.replace("加油蟹（两只海葵的样子）", "双只海葵的样子")
    if level is not None:
        value = re.sub(rf"^{level}级\+", "", value)
        value = re.sub(rf"^{level}级进化[，,]?", "", value)
        value = re.sub(rf"^{level}级", "", value)
    value = value.strip("+，, ")
    if value.endswith("进化"):
        value = value[:-2].rstrip("+，, ")
    return value


def chain_for(pet_key):
    return next((chain for chain in chains if pet_key in chain.get("nodes", {})), None)


def parse_range_numbers(value):
    return [int(item) for item in re.findall(r"N[\.,](\d+)", str(value or ""))]


def find_named_target(numbers, description):
    match = re.search(r"捕捉\d+只(.+)$", str(description or "").strip())
    if not match:
        return None
    target_name = apply_verified_text_corrections(match.group(1)).strip()
    for number in range(min(numbers), max(numbers) + 1):
        if pets.get(pkey(number), {}).get("name") == target_name:
            return number
    return None


def fruit_target(row):
    numbers = parse_range_numbers(row.get("A"))
    if not numbers:
        return None
    named = find_named_target(numbers, row.get("D"))
    return named if named is not None else max(numbers)


def fruit_obtain_type(source):
    source = str(source or "").strip()
    if source == "捕捉20只精灵":
        return "课题任务"
    if source.startswith("智慧树苗"):
        return "智慧树苗"
    if source in {"一代御三家", "二代御三家"}:
        return "剧情任务"
    if source == "通行证契约礼券":
        return "通行证契约礼券"
    if source.startswith("赛季作业·"):
        return "赛季作业"
    return "限时活动"


NO_FRUIT_SOURCES = {"传说精灵", "特殊奇遇", "开局必送", "呱呱上学记"}
FRUIT_EXCLUSIVE_GROUPS = {
    4: "starter_gen1", 7: "starter_gen1", 10: "starter_gen1",
    155: "starter_gen2", 158: "starter_gen2", 161: "starter_gen2",
    309: "pass_s1", 312: "pass_s1",
    355: "pass_s2", 357: "pass_s2",
    419: "pass_s3", 421: "pass_s3",
}


def normalize_source_names(value):
    return apply_verified_text_corrections(value)


form_groups = parse_form_groups(sheets.get("多地区形态进度", []))

# Replace all static form definitions from the complete form sheet while preserving basic/leader.
form_renames = 0
for number, group in form_groups.items():
    pet = pets.get(pkey(number))
    if not pet:
        continue
    old_forms = pet.get("forms") or {}
    new_forms = collections.OrderedDict()
    if "basic" in old_forms:
        new_forms["basic"] = old_forms["basic"]
    else:
        new_forms["basic"] = {"formName": "基础形态", "obtainMethods": []}
    for row in group["rows"]:
        form_name = row["name"]
        methods = [row["method"]] if row.get("method") else []
        new_forms[form_name] = {"formName": form_name, "obtainMethods": methods}
        if row["rawName"] != form_name:
            form_renames += 1
    if "leader" in old_forms:
        new_forms["leader"] = old_forms["leader"]
    pet["forms"] = new_forms

# Migrate collected form keys after canonical naming.
forms_progress_mapped = 0
forms_progress_dropped = []
for pet_key, progress in collections_data.get("sprite_progress", {}).items():
    collected = progress.get("forms_collected")
    if not isinstance(collected, list):
        continue
    pet = pets.get(pet_key)
    valid = set((pet or {}).get("forms", {}))
    migrated = []
    for old_name in collected:
        new_name = canonical_name(old_name)
        if new_name in valid:
            if new_name not in migrated:
                migrated.append(new_name)
                forms_progress_mapped += int(new_name != old_name)
        else:
            forms_progress_dropped.append({"pet": pet_key, "form": old_name})
    progress["forms_collected"] = migrated

# Rebuild tasks from the latest Excel and migrate runtime task index progress.
groups = group_tasks(sheets["课题进度"])
group_by_number = {
    group["number"]: group for group in groups
    if group.get("number") and group["number"] <= COMPLETE_MAX_NUMBER
}
new_tasks = collections.OrderedDict()
progress_stats = {"mapped": 0, "unmapped": 0}
for number in range(1, COMPLETE_MAX_NUMBER + 1):
    pet_key = pkey(number)
    pet = pets.get(pet_key)
    group = group_by_number.get(number)
    if not pet or not group:
        raise ValueError(f"N.{number:03d} 缺少精灵或Excel分组")
    expected = [
        parse_task(row, number, pet, form_groups)
        for row in group["rows"] if row.get("type")
    ]
    old_list = old_tasks.get(pet_key, [])
    stats = migrate_task_progress(pet_key, old_list, expected)
    progress_stats["mapped"] += stats["mapped"]
    progress_stats["unmapped"] += stats["unmapped"]
    new_tasks[pet_key] = expected

# Keep user-verified partial Excel rows as append-only placeholders until full fields arrive.
for number, definition in PARTIAL_PETS.items():
    pets[pkey(number)] = definition
    new_tasks[pkey(number)] = []

# Sync every evolution condition from the latest Excel.
evolution_updates = 0
for number, group in group_by_number.items():
    evolve_row = next((row for row in group["rows"] if row.get("type") == "进化"), None)
    if not evolve_row:
        continue
    pet_key = pkey(number)
    chain = chain_for(pet_key)
    evolutions = (chain or {}).get("nodes", {}).get(pet_key, {}).get("evolvesTo", [])
    if not evolutions:
        continue
    note = apply_verified_evolution_correction(number, evolve_row.get("note"))
    level_match = re.search(r"(\d+)级", note)
    level = int(level_match.group(1)) if level_match else None
    mechanism = clean_condition_note(note, level)
    for evolution in evolutions:
        target = evolution.get("toSpeciesId")
        if number == 415:
            if target == "pet_416":
                mechanism_for_target = "精灵成长至2星，改萌系血脉进化为加尔"
            else:
                mechanism_for_target = "精灵成长至2星，改幽系血脉进化为黑化加尔"
        else:
            mechanism_for_target = mechanism
        condition = {"type": "level", "level": level} if level is not None else {"type": "unknown"}
        if mechanism_for_target:
            condition["note"] = mechanism_for_target
        evolution["condition"] = condition
        evolution_updates += 1

# Fix the one unambiguous legacy element/pinyin omission.
pets["pet_353"]["element"] = ["翼"]
pets["pet_353"]["pinyin"] = {"full": "fanying", "initial": "fy"}

# Rebuild all fruit definitions from the family fruit sheet.
for pet in pets.values():
    pet.pop("fruit", None)
fruit_records = 0
for row in sheets.get("果实进度", [])[1:]:
    description = str(row.get("D") or "")
    source = str(row.get("C") or "").strip()
    if source in NO_FRUIT_SOURCES or description.startswith("无果实"):
        continue
    target_number = fruit_target(row)
    if target_number is None or target_number > COMPLETE_MAX_NUMBER:
        continue
    pet = pets.get(pkey(target_number))
    if not pet:
        continue
    fruit = {
        "name": f"{pet['name']}果实",
        "acquired": False,
        "obtainMethod": normalize_source_names(description),
        "obtainType": fruit_obtain_type(source),
    }
    if target_number in FRUIT_EXCLUSIVE_GROUPS:
        fruit["exclusiveGroup"] = FRUIT_EXCLUSIVE_GROUPS[target_number]
    pet["fruit"] = fruit
    fruit_records += 1

# Add S3 shiny world definitions explicitly confirmed by the user's official S3 list.
S3_SHINY = {"tagName": "异色", "limitedTime": "S3「铅字幻梦」"}
s3_existing_shiny = [72, 78, 101, 178, 233, 241, 268, 269, 279]
for number in s3_existing_shiny:
    pets[pkey(number)].setdefault("tags", {})["shiny"] = dict(S3_SHINY)

collections_data.setdefault("meta", {})["last_updated"] = "2026-07-21"

PETS_PATH.write_text(json.dumps(pets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
TASKS_PATH.write_text(json.dumps(new_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
CHAINS_PATH.write_text(json.dumps(chains, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
COLLECTIONS_PATH.write_text(json.dumps(collections_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps({
    "tasks": sum(len(items) for items in new_tasks.values()),
    "taskProgress": progress_stats,
    "forms": sum(len(group["rows"]) for group in form_groups.values()),
    "formRenames": form_renames,
    "formProgressMapped": forms_progress_mapped,
    "formProgressDropped": forms_progress_dropped,
    "evolutionTargetsUpdated": evolution_updates,
    "fruitRecords": fruit_records,
    "s3ExistingShinyAdded": s3_existing_shiny,
}, ensure_ascii=False, indent=2))
