#!/usr/bin/env python3
"""
Batch label pending images in text50_ground_truth.json using Agnes AI vision.

For each pending image:
1. Extract visible caption text from the bottom region (Agnes AI).
2. Propose ground-truth items using the full ERP product catalog (Agnes AI).
3. Save as status="auto_labeled" for human review.

Usage:
    python scripts/label_pending.py [--dry-run] [--limit N] [--image IMAGE]
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


AGNES_API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
AGNES_MODEL = "agnes-2.0-flash"

ERP_NAMES: list[str] = [
    "KGOS益生菌固体饮料 2g*15",
    "KGOS加维诺维生素C泡腾片（甜橙味）4g*20",
    "KGO摇摇杯 500ML",
    "KGOS逐光冰霸杯 900ml",
    "KGOS手提保温壶",
    "KGOS 三围尺 150cm",
    "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*3 体验装",
    "KGOS饮料袋 10个/袋",
    "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21",
    "KGOS灵芝金花黑茶固体饮料（青柑普洱味）21g（1g*21）",
    "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）",
    "KGOS灵芝金花黑茶固体饮料（青柑普洱味）试用装 5g（1g*5）",
    "KGOS蛋白多肽营养强化粉（莓果味） 30g*12",
    "KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*12",
    "KGOS香菜牛肉味玉米片 30g",
    "KGOS玉米浓汤味玉米片 30g",
    "KGOS新年礼袋",
    "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12",
    "甘油二酯咖啡固体饮料（生椰拿铁味） 8g*12 新包装",
    "诺丽果红树莓益生元饮 50ml*10袋/盒",
    "诺丽果红树莓益生元饮 50ml*3袋/盒 体验装",
    "KGOS绿色圆手柄锤纹杯",
    "kgos帆布袋",
    "KGO手提袋",
    "KGOS蛋白多肽营养强化粉（莓果味） 30g*3 三袋体验装",
    "KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*3 三袋体验装",
    "KGO复合多种压片糖果2.0",
    "KGO夏季随行咖啡杯",
]

ERP_CATALOG_TEXT = "\n".join(f"- {name}" for name in ERP_NAMES)


def get_api_key() -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-a", "agnes-ai", "-s", "product-detect-api-key", "-w"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def image_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def call_agnes(api_key: str, messages: list[dict], max_tokens: int = 300) -> str:
    payload = json.dumps({
        "model": AGNES_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(
        AGNES_API_URL, data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def extract_caption_text(api_key: str, b64: str) -> str:
    """Ask Agnes AI to extract visible product caption text from image."""
    return call_agnes(api_key, [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "这是一张产品SKU主图。\n"
                    "请仅提取图片底部说明文字区域中描述商品名称和数量的文字内容（如「玉米片10包+益生菌3盒」），"
                    "原文输出，不要分析、不要解读。\n"
                    "如果图片底部没有文字说明，回复空字符串。"
                ),
            },
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ],
    }], max_tokens=100)


def propose_items(api_key: str, b64: str) -> list[dict]:
    """Ask Agnes AI to propose ground-truth items for the image."""
    prompt = (
        "这是一张KGOS品牌产品的SKU主图，图中展示一个或多个商品（可能是组合礼盒、买赠套装等）。\n\n"
        "已知的ERP标准商品名如下（请严格使用这些名称，不要自行造名）：\n"
        f"{ERP_CATALOG_TEXT}\n\n"
        "请仔细数图中每种商品的数量（注意密排时要逐个数），"
        "用JSON数组格式输出，每个元素包含 name（严格使用上方ERP标准名）和 qty（整数）。\n"
        "格式示例：[{\"name\": \"KGOS玉米浓汤味玉米片 30g\", \"qty\": 5}]\n"
        "只输出JSON数组，不要其他内容。"
    )
    raw = call_agnes(api_key, [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ],
    }], max_tokens=300)

    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
        valid = []
        for item in items:
            if isinstance(item, dict) and "name" in item and "qty" in item:
                valid.append({"name": str(item["name"]).strip(), "qty": int(item["qty"])})
        return valid
    except (json.JSONDecodeError, ValueError):
        return []


def run(
    gt_path: Path,
    image_dir: Path,
    dry_run: bool = False,
    limit: int | None = None,
    target_image: str | None = None,
) -> None:
    api_key = get_api_key()

    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    records = raw["images"] if "images" in raw else raw

    pending = [
        name for name, rec in records.items()
        if rec.get("status") == "pending"
    ]
    if target_image:
        pending = [p for p in pending if p == target_image]
    if limit:
        pending = pending[:limit]

    print(f"Pending: {len(pending)} images to label")
    print(f"Dry run: {dry_run}\n")

    updated = 0
    for i, image_name in enumerate(pending, 1):
        img_path = image_dir / image_name
        if not img_path.exists():
            print(f"[{i}/{len(pending)}] {image_name}: image file not found, skip")
            continue

        print(f"[{i}/{len(pending)}] {image_name}...", end=" ", flush=True)
        try:
            b64 = image_to_b64(img_path)
            caption = extract_caption_text(api_key, b64)
            items = propose_items(api_key, b64)
            print(f"text='{caption}' items={len(items)}")
            for it in items:
                print(f"     {it['name']} × {it['qty']}")

            if not dry_run and items:
                records[image_name]["status"] = "auto_labeled"
                records[image_name]["text"] = caption
                records[image_name]["items"] = items
                records[image_name]["notes"] = "auto_labeled by Agnes AI vision — requires human verification"
                updated += 1
            elif not dry_run and not items:
                print(f"     [WARN] no items returned, keeping pending")
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.read().decode()[:100]}")
        except Exception as exc:
            print(f"ERROR: {exc}")

        time.sleep(0.5)

    if not dry_run and updated > 0:
        raw_out = dict(raw)
        if "images" in raw_out:
            raw_out["images"] = records
        else:
            raw_out = records
        gt_path.write_text(json.dumps(raw_out, ensure_ascii=False, indent=2), encoding="utf-8")
        mirror = PROJECT_ROOT / "datasets/kgos_real_text50/ground_truth.json"
        if mirror.exists():
            mirror.write_text(json.dumps(raw_out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Updated {updated}/{len(pending)} records → {gt_path}")
    elif dry_run:
        print(f"\n[dry-run] Would update {len([p for p in pending])} records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-label pending text50 images with Agnes AI")
    parser.add_argument("--ground-truth", type=Path,
                        default=PROJECT_ROOT / "docs/text50_ground_truth.json")
    parser.add_argument("--image-dir", type=Path,
                        default=PROJECT_ROOT / "datasets/kgos_real_golden_candidates_v1/images")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N images")
    parser.add_argument("--image", type=str, default=None, help="Process one specific image")
    args = parser.parse_args()

    run(
        gt_path=args.ground_truth,
        image_dir=args.image_dir,
        dry_run=args.dry_run,
        limit=args.limit,
        target_image=args.image,
    )
