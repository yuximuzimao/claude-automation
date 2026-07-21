#!/usr/bin/env python3
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NO_FRUIT_SOURCES = {"传说精灵", "特殊奇遇", "开局必送", "呱呱上学记"}
NO_FRUIT_DESCRIPTIONS = {"唯一的迪莫", "达到100研学绩点获得蛋"}
LIMITED_FRUIT_SOURCES = {"官网下载", "火红迎新", "洛克筑梦师"}


def read_xlsx(path: Path):
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.parse(z.open("xl/sharedStrings.xml")).getroot()
            for si in root.findall(f"{NS}si"):
                strings.append("".join(t.text or "" for t in si.iter(f"{NS}t")))

        workbook = ET.parse(z.open("xl/workbook.xml")).getroot()
        rels_root = ET.parse(z.open("xl/_rels/workbook.xml.rels")).getroot()
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in rels_root.findall(f"{PKG_REL_NS}Relationship")
        }

        result = {}
        for sheet in workbook.find(f"{NS}sheets"):
            name = sheet.get("name")
            rid = sheet.get(f"{REL_NS}id")
            target = rels[rid]
            if not target.startswith("worksheets/"):
                continue
            root = ET.parse(z.open("xl/" + target)).getroot()
            rows = []
            for row_node in root.iter(f"{NS}row"):
                row_num = int(row_node.get("r", "0"))
                values = {}
                for cell in row_node.findall(f"{NS}c"):
                    ref = cell.get("r", "")
                    match = re.match(r"[A-Z]+", ref)
                    if not match:
                        continue
                    col = match.group(0)
                    cell_type = cell.get("t", "")
                    value = None
                    if cell_type == "inlineStr":
                        inline = cell.find(f"{NS}is")
                        if inline is not None:
                            value = "".join(t.text or "" for t in inline.iter(f"{NS}t"))
                    else:
                        v = cell.find(f"{NS}v")
                        if v is not None and v.text is not None:
                            if cell_type == "s":
                                value = strings[int(v.text)]
                            elif cell_type == "b":
                                value = v.text == "1"
                            else:
                                value = v.text
                    if value is not None:
                        values[col] = value
                if values:
                    rows.append({"row": row_num, **values})
            result[name] = rows
        return result


def number_from_code(code):
    match = re.fullmatch(r"N\.(\d+)", str(code or "").strip())
    return int(match.group(1)) if match else None


def parse_fruit_numbers(value):
    return [int(item) for item in re.findall(r"N[\.,](\d+)", str(value or ""))]


def map_fruit_obtain_type(source):
    source = str(source or "").strip()
    if source == "捕捉20只精灵":
        return "课题任务"
    if source.startswith("智慧树苗"):
        return "智慧树苗"
    if source in {"一代御三家", "二代御三家"}:
        return "剧情任务"
    if source == "通行证契约礼券":
        return "通行证契约礼券"
    if source.startswith("赛季作业"):
        return "赛季作业"
    if source in LIMITED_FRUIT_SOURCES:
        return "限时活动"
    raise ValueError(f"未知果实来源：{source or '空值'}")


def classify_fruit_row(row):
    source = str(row.get("C") or "").strip()
    description = str(row.get("D") or "").strip()
    numbers = parse_fruit_numbers(row.get("A"))
    if not numbers:
        raise ValueError(f"果实编号范围无法解析：{row.get('A')}")
    if source in NO_FRUIT_SOURCES or description.startswith("无果实"):
        return None
    if not description:
        raise ValueError(f"果实获取说明为空：{row.get('A')}")
    obtain_type = map_fruit_obtain_type(source)
    if description in NO_FRUIT_DESCRIPTIONS:
        return None
    return {
        "numbers": numbers,
        "familyNumberRange": [min(numbers), max(numbers)],
        "obtainType": obtain_type,
    }


def group_tasks(rows):
    groups = []
    current = None
    for row in rows[1:]:
        # Excel 合并单元格会让 A 列编号在个别任务行错位出现；
        # 只有 B 列出现精灵名称时才是真正的新精灵分组边界。
        if row.get("B"):
            if current:
                groups.append(current)
            current = {
                "number": number_from_code(row.get("A")),
                "code": row.get("A"),
                "name": row.get("B"),
                "element": row.get("C"),
                "declaredTaskCount": row.get("D"),
                "sourceVersion": row.get("J"),
                "rows": [],
            }
        if current:
            current["rows"].append({
                "excelRow": row["row"],
                "type": row.get("F"),
                "content": row.get("G"),
                "note": row.get("I"),
                "version": row.get("J"),
            })
    if current:
        groups.append(current)
    return groups


def main():
    workbook_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("图鉴课题进度表（另存或存为副本使用）.xlsx")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scripts/fixtures/s3-excel-extract.json")
    sheets = read_xlsx(workbook_path)
    groups = group_tasks(sheets["课题进度"])
    s3_groups = [group for group in groups if group["number"] is not None and 376 <= group["number"] <= 440]

    form_rows = []
    for row in sheets.get("多地区形态进度", []):
        text = " ".join(str(row.get(col, "")) for col in ["A", "B", "C", "D", "E", "H", "I"])
        if any(term in text for term in ["火山附近的样子", "穿星星睡衣的样子", "穿旧睡衣的样子"]):
            form_rows.append(row)

    fruit_rows = []
    for row in sheets.get("果实进度", []):
        a = str(row.get("A", ""))
        nums = [int(x) for x in re.findall(r"N\.(\d+)", a)]
        if nums and max(nums) >= 376:
            fruit_rows.append(row)

    output = {
        "workbook": str(workbook_path),
        "s3Groups": s3_groups,
        "formRows": form_rows,
        "fruitRows": fruit_rows,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "s3Groups": len(s3_groups),
        "completeGroups376to439": len([g for g in s3_groups if 376 <= g["number"] <= 439]),
        "extraGroups": [g["code"] for g in s3_groups if g["number"] > 439],
        "formRows": len(form_rows),
        "fruitRows": len(fruit_rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
