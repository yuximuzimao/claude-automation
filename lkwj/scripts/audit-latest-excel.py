#!/usr/bin/env python3
import collections
import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "图鉴课题进度表（另存或存为副本使用）.xlsx"
REPORT = ROOT / "tasks" / "latest-excel-audit.md"
REPORT_JSON = ROOT / "tasks" / "latest-excel-audit.json"

reader = runpy.run_path(str(ROOT / "scripts" / "read-latest-excel.py"))
read_xlsx = reader["read_xlsx"]
group_tasks = reader["group_tasks"]

sheets = read_xlsx(WORKBOOK)
pets = json.loads((ROOT / "data" / "pets.json").read_text(encoding="utf-8"))
tasks = json.loads((ROOT / "data" / "tasks.json").read_text(encoding="utf-8"))
chains = json.loads((ROOT / "data" / "evolution-chains.json").read_text(encoding="utf-8"))


def pkey(number):
    return f"pet_{number}"


def number_from_code(value):
    match = re.fullmatch(r"N\.(\d+)", str(value or "").strip())
    return int(match.group(1)) if match else None


def split_elements(value):
    return [part.strip() for part in re.split(r"[,，]", str(value or "")) if part.strip()]


def canonical_form_name(value):
    value = str(value or "").strip()
    if value.startswith("（") and value.endswith("）"):
        return value[1:-1].strip()
    return value


def task_signature_from_excel(row):
    kind = row.get("type")
    mapping = {
        "捕捉": "capture",
        "天分": "capture_gifted",
        "亲密度": "affection",
        "奖牌": "destined_hero",
        "首领": "leader_evolve",
        "进化": "evolve",
        "炫彩": "capture_chromatic",
        "果实": "fruit",
        "形态": "confirm_forms",
        "异色": "capture_shiny",
    }
    if kind == "技能":
        match = re.fullmatch(r"使用(\d+)次【(.+)】", str(row.get("content") or "").strip())
        if not match:
            return f"skill:UNPARSED:{row.get('content')}"
        return f"skill:{match.group(2)}:{int(match.group(1))}"
    return mapping.get(kind, f"UNKNOWN:{kind}")


def task_signature_from_json(task):
    if task.get("type") == "skill":
        return f"skill:{task.get('skillName')}:{task.get('count')}"
    return str(task.get("type"))


def counter_diff(expected, actual):
    expected_counter = collections.Counter(expected)
    actual_counter = collections.Counter(actual)
    missing = list((expected_counter - actual_counter).elements())
    extra = list((actual_counter - expected_counter).elements())
    return missing, extra


def chain_for(pet_key):
    return next((chain for chain in chains if pet_key in chain.get("nodes", {})), None)


def normalize_method(value):
    return re.sub(r"\s+", "", str(value or "")).replace("，", ",").strip()


def parse_form_groups(rows):
    groups = collections.OrderedDict()
    current_number = None
    for row in rows[1:]:
        if row.get("B"):
            current_number = number_from_code(row.get("A"))
            if current_number:
                groups.setdefault(current_number, {
                    "number": current_number,
                    "code": row.get("A"),
                    "name": row.get("B"),
                    "rows": [],
                })
        if current_number and row.get("D"):
            groups[current_number]["rows"].append({
                "excelRow": row.get("row"),
                "name": row.get("D"),
                "method": row.get("E"),
            })
    return list(groups.values())


def parse_fruit_ranges(value):
    return [int(match) for match in re.findall(r"N[\.,](\d+)", str(value or ""))]


def find_fruit_target(numbers, description):
    match = re.search(r"捕捉\d+只(.+)$", str(description or "").strip())
    if match:
        target_name = match.group(1).strip()
        aliases = {"幽灵眼": "幽冥眼", "饮血狂兽": "饮雪狂兽", "斜眼巨魔": "邪眼巨魔"}
        target_name = aliases.get(target_name, target_name)
        for number in range(min(numbers), max(numbers) + 1):
            if pets.get(pkey(number), {}).get("name") == target_name:
                return number
    return max(numbers)


def clean_condition_note(note, level):
    value = str(note or "").strip()
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


def form_aliases(form_name, pet_name):
    aliases = {form_name}
    if form_name == "本来的样子":
        aliases.add(pet_name)
    if form_name == "双只海葵的样子":
        aliases.update({"两只海葵的样子", "加油蟹（两只海葵的样子）", "（两只海葵的样子）"})
    return aliases


def condition_summary(condition):
    if not condition:
        return "缺失"
    parts = [str(condition.get("type"))]
    if condition.get("level") is not None:
        parts.append(f"level={condition.get('level')}")
    if condition.get("note"):
        parts.append(f"note={condition.get('note')}")
    return ", ".join(parts)


task_groups_all = group_tasks(sheets["课题进度"])
valid_groups = [group for group in task_groups_all if group.get("number") and group["number"] <= 439]
group_by_number = {group["number"]: group for group in valid_groups}

results = {
    "workbook": str(WORKBOOK),
    "summary": {},
    "excelInternal": [],
    "nameElement": [],
    "tasks": [],
    "evolution": [],
    "fruit": [],
    "forms": [],
    "shiny": [],
    "acceptedSourceConflicts": [],
    "unresolvedSourceConflicts": [],
}

# Excel internal consistency.
for group in valid_groups:
    actual_rows = [row for row in group["rows"] if row.get("type")]
    declared = group.get("declaredTaskCount")
    if declared not in (None, ""):
        try:
            declared_number = int(float(str(declared)))
        except ValueError:
            results["excelInternal"].append({
                "pet": group["code"],
                "issue": f"课题总数不是数字：{declared}",
            })
        else:
            if declared_number != len(actual_rows):
                results["excelInternal"].append({
                    "pet": group["code"],
                    "issue": f"D列课题总数 {declared_number}，实际任务行 {len(actual_rows)}",
                })
    elif actual_rows:
        results["excelInternal"].append({
            "pet": group["code"],
            "issue": f"D列课题总数为空，但存在 {len(actual_rows)} 条任务行",
        })

# Incomplete N.440 placeholder.
extra_groups = [group for group in task_groups_all if group.get("number") and group["number"] > 439]
for group in extra_groups:
    results["excelInternal"].append({
        "pet": group["code"],
        "issue": f"Excel存在未完整条目“{group.get('name')}”，系别/课题尚未提供，不应入库",
    })

# Names/elements and tasks.
for number in range(1, 440):
    group = group_by_number.get(number)
    pet = pets.get(pkey(number))
    if not group:
        results["nameElement"].append({"pet": f"N.{number:03d}", "issue": "Excel缺少精灵分组"})
        continue
    if not pet:
        results["nameElement"].append({"pet": group["code"], "issue": "JSON缺少精灵定义"})
        continue

    if pet.get("name") != group.get("name"):
        issue = {
            "pet": group["code"],
            "issue": f"名称：Excel“{group.get('name')}” vs JSON“{pet.get('name')}”",
        }
        if number not in (392, 402):
            results["nameElement"].append(issue)

    expected_elements = split_elements(group.get("element"))
    actual_elements = pet.get("element") or []
    if expected_elements != actual_elements:
        results["nameElement"].append({
            "pet": group["code"],
            "issue": f"系别：Excel {expected_elements} vs JSON {actual_elements}",
        })

    expected_signatures = [task_signature_from_excel(row) for row in group["rows"] if row.get("type")]
    actual_signatures = [task_signature_from_json(task) for task in tasks.get(pkey(number), [])]
    missing, extra = counter_diff(expected_signatures, actual_signatures)
    if missing or extra:
        results["tasks"].append({
            "pet": group["code"],
            "name": pet.get("name"),
            "excelCount": len(expected_signatures),
            "jsonCount": len(actual_signatures),
            "missing": missing,
            "extra": extra,
        })

# Evolution rows and reverse consistency.
excel_evolve_numbers = set()
for group in valid_groups:
    number = group["number"]
    evolve_row = next((row for row in group["rows"] if row.get("type") == "进化"), None)
    if not evolve_row:
        continue
    excel_evolve_numbers.add(number)
    pet_key = pkey(number)
    chain = chain_for(pet_key)
    evolutions = (chain or {}).get("nodes", {}).get(pet_key, {}).get("evolvesTo", [])
    if not evolutions:
        results["evolution"].append({
            "pet": group["code"],
            "issue": f"Excel有进化任务（{evolve_row.get('note')}），JSON无进化目标",
        })
        continue
    note = str(evolve_row.get("note") or "").strip()
    level_match = re.search(r"(\d+)级", note)
    expected_level = int(level_match.group(1)) if level_match else None
    for evolution in evolutions:
        condition = evolution.get("condition") or {}
        if expected_level is not None and condition.get("level") != expected_level:
            results["evolution"].append({
                "pet": group["code"],
                "issue": f"进化等级：Excel {expected_level} vs JSON {condition.get('level')}；目标 {evolution.get('toSpeciesId')}",
            })
        expected_mechanism = clean_condition_note(note, expected_level)
        json_note = str(condition.get("note") or "")
        # Branch text is split into one note per target in JSON, so compare by target phrase.
        if number == 415:
            target = evolution.get("toSpeciesId")
            expected_phrase = "萌系血脉" if target == "pet_416" else "幽系血脉"
            if expected_phrase not in json_note:
                results["evolution"].append({
                    "pet": group["code"],
                    "issue": f"分支条件缺少“{expected_phrase}”：{condition_summary(condition)}",
                })
        elif normalize_method(expected_mechanism) != normalize_method(json_note):
            results["evolution"].append({
                "pet": group["code"],
                "issue": f"进化机制：Excel“{expected_mechanism or '仅等级'}” vs JSON“{json_note or '仅等级'}”",
            })

for chain in chains:
    for pet_key, node in chain.get("nodes", {}).items():
        number_match = re.fullmatch(r"pet_(\d+)", pet_key)
        if not number_match:
            continue
        number = int(number_match.group(1))
        if number > 439 or not node.get("evolvesTo"):
            continue
        if number not in excel_evolve_numbers:
            results["evolution"].append({
                "pet": f"N.{number:03d}",
                "issue": "JSON存在进化目标，但Excel没有进化任务行",
            })

# Fruit definitions.
expected_fruit_targets = {}
for row in sheets.get("果实进度", [])[1:]:
    numbers = parse_fruit_ranges(row.get("A"))
    if not numbers:
        continue
    final_number = find_fruit_target(numbers, row.get("D"))
    if final_number > 439:
        continue
    no_fruit = str(row.get("D") or "").startswith("无果实")
    if no_fruit:
        continue
    expected_fruit_targets[final_number] = row

actual_fruit_targets = {
    int(key.split("_")[1]): pet.get("fruit")
    for key, pet in pets.items()
    if pet.get("fruit") and int(key.split("_")[1]) <= 439
}

for number, row in expected_fruit_targets.items():
    fruit = actual_fruit_targets.get(number)
    if not fruit:
        results["fruit"].append({
            "pet": f"N.{number:03d}",
            "issue": f"Excel果实记录存在（{row.get('B')}），JSON缺少fruit定义",
        })
        continue
    expected_method = str(row.get("D") or "")
    actual_method = str(fruit.get("obtainMethod") or "")
    accepted_typo = (
        ("幽灵眼" in expected_method and "幽冥眼" in actual_method)
        or ("饮血狂兽" in expected_method and "饮雪狂兽" in actual_method)
        or ("斜眼巨魔" in expected_method and "邪眼巨魔" in actual_method)
    )
    if normalize_method(expected_method) != normalize_method(actual_method) and not accepted_typo:
        results["fruit"].append({
            "pet": f"N.{number:03d}",
            "issue": f"果实获取说明：Excel“{expected_method}” vs JSON“{actual_method}”",
        })

for number in sorted(set(actual_fruit_targets) - set(expected_fruit_targets)):
    results["fruit"].append({
        "pet": f"N.{number:03d}",
        "issue": "JSON有fruit定义，但Excel果实进度没有对应有效记录",
    })

# Forms and form obtain methods.
form_groups = parse_form_groups(sheets.get("多地区形态进度", []))
excel_form_numbers = set()
for group in form_groups:
    number = group.get("number")
    if not number or number > 439:
        continue
    excel_form_numbers.add(number)
    pet = pets.get(pkey(number))
    if not pet:
        results["forms"].append({"pet": group.get("code"), "issue": "多形态表对应JSON精灵不存在"})
        continue
    excel_forms = {canonical_form_name(row["name"]): row for row in group["rows"]}
    json_forms = {
        key: value
        for key, value in (pet.get("forms") or {}).items()
        if key not in ("basic", "leader")
    }
    missing = sorted(set(excel_forms) - set(json_forms))
    extra = sorted(set(json_forms) - set(excel_forms))
    if missing or extra:
        results["forms"].append({
            "pet": group.get("code"),
            "issue": f"形态集合差异：缺少 {missing or '无'}；额外 {extra or '无'}",
        })
    for form_name in sorted(set(excel_forms) & set(json_forms)):
        excel_row = excel_forms[form_name]
        json_form = json_forms[form_name]
        if str(excel_row["name"]).startswith("（") and str(excel_row["name"]).endswith("）"):
            results["excelInternal"].append({
                "pet": group.get("code"),
                "issue": f"多形态表名称额外包裹括号：“{excel_row['name']}”，助手规范为“{form_name}”",
            })
        expected_method = str(excel_row.get("method") or "")
        actual_methods = json_form.get("obtainMethods") or []
        if expected_method and all(normalize_method(expected_method) != normalize_method(item) for item in actual_methods):
            results["forms"].append({
                "pet": group.get("code"),
                "issue": f"形态“{form_name}”获取方式：Excel“{expected_method}” vs JSON {actual_methods}",
            })

for pet_key, pet in pets.items():
    number = int(pet_key.split("_")[1])
    if number > 439:
        continue
    forms = [key for key in (pet.get("forms") or {}) if key not in ("basic", "leader")]
    if forms and number not in excel_form_numbers:
        results["forms"].append({
            "pet": f"N.{number:03d}",
            "issue": f"JSON有多形态 {forms}，Excel多地区形态进度无该精灵分组",
        })

# confirm_forms tasks: count and eligible pool.
for group in valid_groups:
    form_row = next((row for row in group["rows"] if row.get("type") == "形态"), None)
    pet_key = pkey(group["number"])
    form_task = next((task for task in tasks.get(pet_key, []) if task.get("type") == "confirm_forms"), None)
    if not form_row:
        if form_task:
            results["forms"].append({"pet": group["code"], "issue": "JSON有confirm_forms，但Excel没有形态课题"})
        continue
    if not form_task:
        results["forms"].append({"pet": group["code"], "issue": "Excel有形态课题，但JSON缺少confirm_forms"})
        continue
    count_match = re.search(r"确认(\d+)种", str(form_row.get("content") or ""))
    expected_count = int(count_match.group(1)) if count_match else None
    if expected_count is not None and form_task.get("count") != expected_count:
        results["forms"].append({
            "pet": group["code"],
            "issue": f"形态任务数量：Excel {expected_count} vs JSON {form_task.get('count')}",
        })
    all_form_names = [
        key for key in (pets.get(pet_key, {}).get("forms") or {})
        if key not in ("basic", "leader")
    ]
    note = str(form_row.get("note") or "")
    note_scope = note.split("即可完成", 1)[0] if "即可完成" in note else note
    pet_name = pets.get(pet_key, {}).get("name", "")
    eligible = [
        name for name in all_form_names
        if any(alias in note_scope for alias in form_aliases(name, pet_name))
    ]
    if expected_count is not None and len(eligible) < expected_count <= len(all_form_names):
        eligible = all_form_names
    if eligible and form_task.get("requiredForms") != eligible:
        results["forms"].append({
            "pet": group["code"],
            "issue": f"形态课题候选池：Excel备注对应 {eligible} vs JSON {form_task.get('requiredForms')}",
        })

# Shiny task/tag relation (report only, never infer silently).
shiny_task_numbers = {
    number for number in range(1, 440)
    if any(task.get("type") == "capture_shiny" for task in tasks.get(pkey(number), []))
}
shiny_tag_numbers = {
    number for number in range(1, 440)
    if pets.get(pkey(number), {}).get("tags", {}).get("shiny")
}
for number in sorted(shiny_task_numbers - shiny_tag_numbers):
    results["shiny"].append({
        "pet": f"N.{number:03d}",
        "issue": "有官方capture_shiny课题，但pets.tags.shiny缺失；不能自动反推，需核对异色世界定义",
    })
for number in sorted(shiny_tag_numbers - shiny_task_numbers):
    label = pets[pkey(number)]["tags"]["shiny"].get("limitedTime")
    if "通行证" not in str(label):
        results["shiny"].append({
            "pet": f"N.{number:03d}",
            "issue": f"有异色世界定义（{label}），但无capture_shiny课题；若非通行证需核对",
        })

# Explicit source conflicts known from the supplied official images.
results["acceptedSourceConflicts"].extend([
    {
        "pet": "N.392",
        "issue": "官方图片为“饮雪狂兽”，Excel课题/果实表写“饮血狂兽”；助手保留图片名称“饮雪狂兽”",
    },
    {
        "pet": "N.402",
        "issue": "官方图片为“邪眼巨魔”，Excel课题/果实表写“斜眼巨魔”；助手保留图片名称“邪眼巨魔”",
    },
])
results["unresolvedSourceConflicts"].extend([
    {
        "pet": "N.063–N.065",
        "issue": "蹦蹦种子家族的多地区形态表写“象牙花形态”，课题备注写“象牙球形态”。助手暂保留形态明细表名称“象牙花形态”，课题候选池按全部四种形态处理，正式名称需人工确认。",
    },
    {
        "pet": "N.427–N.429",
        "issue": "十字蝌蚪家族图片显示第二系别图标，但Excel结构化系别为：十字蝌蚪=水、十字蛙=水、深渊蛙=水+武。助手暂按Excel，需人工确认图片中的第二图标含义。",
    },
])

# Summary.
results["summary"] = {
    "excelPets1to439": len(valid_groups),
    "jsonPets": len(pets),
    "excelTasks": sum(len([row for row in group["rows"] if row.get("type")]) for group in valid_groups),
    "jsonTasks": sum(len(items) for items in tasks.values()),
    "excelFruitTasks": sum(1 for group in valid_groups for row in group["rows"] if row.get("type") == "果实"),
    "jsonFruitTasks": sum(1 for items in tasks.values() for task in items if task.get("type") == "fruit"),
    "excelFormItems": sum(len(group["rows"]) for group in form_groups if group.get("number") and group["number"] <= 439),
    "jsonFormItems": sum(
        1 for pet in pets.values() for key in (pet.get("forms") or {}) if key not in ("basic", "leader")
    ),
    "excelConfirmForms": sum(1 for group in valid_groups for row in group["rows"] if row.get("type") == "形态"),
    "jsonConfirmForms": sum(1 for items in tasks.values() for task in items if task.get("type") == "confirm_forms"),
    "excelShinyTasks": sum(1 for group in valid_groups for row in group["rows"] if row.get("type") == "异色"),
    "jsonShinyTasks": len(shiny_task_numbers),
    "jsonShinyTags": len(shiny_tag_numbers),
    "issueCounts": {
        section: len(items)
        for section, items in results.items()
        if isinstance(items, list)
    },
}


def render_issue(item):
    pet = item.get("pet", "未知")
    if "missing" in item or "extra" in item:
        return (
            f"- **{pet} {item.get('name', '')}**：Excel {item.get('excelCount')} 条，JSON {item.get('jsonCount')} 条；"
            f"缺少 `{item.get('missing')}`；额外 `{item.get('extra')}`"
        )
    return f"- **{pet}**：{item.get('issue')}"


section_titles = [
    ("excelInternal", "一、Excel 自身结构或内容问题"),
    ("acceptedSourceConflicts", "二、图片优先、已按图片修正的来源冲突"),
    ("unresolvedSourceConflicts", "三、仍需人工确认的图片 / Excel 冲突"),
    ("nameElement", "四、精灵名称与系别差异"),
    ("tasks", "五、课题任务差异"),
    ("evolution", "六、进化链与进化条件差异"),
    ("fruit", "七、果实定义差异"),
    ("forms", "八、多形态与形态课题差异"),
    ("shiny", "九、异色课题与异色世界定义差异"),
]

lines = [
    "# 最新图鉴 Excel 全量审计",
    "",
    f"- 来源：`{WORKBOOK.name}`",
    "- 范围：N.001–N.439；N.440 仅作为不完整占位单独报告",
    "- 规则：按 B 列精灵名称识别分组边界，避免合并单元格导致 A 列编号错位",
    "- 本报告只列差异和来源冲突；不会从任务反向生成异色世界定义",
    "",
    "## 汇总",
    "",
]
for key, value in results["summary"].items():
    if key == "issueCounts":
        continue
    lines.append(f"- {key}: {value}")
lines.append("")
lines.append("### 各类问题数量")
lines.append("")
for key, value in results["summary"]["issueCounts"].items():
    lines.append(f"- {key}: {value}")

for key, title in section_titles:
    lines.extend(["", f"## {title}", ""])
    items = results[key]
    if not items:
        lines.append("- 无")
    else:
        lines.extend(render_issue(item) for item in items)

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
REPORT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "report": str(REPORT),
    "reportJson": str(REPORT_JSON),
    "summary": results["summary"],
}, ensure_ascii=False, indent=2))
