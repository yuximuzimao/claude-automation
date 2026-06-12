#!/usr/bin/env python3
"""
生成 Label Studio 导入 JSON，供 KGOS Detect-vs-Seg Pilot 项目使用。
用法：
  python scripts/prepare_seg_pilot_import.py --smoke   # 只导入 gift_001.jpg（冒烟测试）
  python scripts/prepare_seg_pilot_import.py           # 导入全部 64 张 pilot 图

输出：
  datasets/kgos_real_all/seg_pilot_smoke_import.json   (--smoke)
  datasets/kgos_real_all/seg_pilot_import.json         (全量)
"""

import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
IMAGES_DIR = PROJECT_ROOT / "datasets" / "kgos_real_all" / "images"
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "kgos_real_all"

# 64 张 pilot 图，顺序固定（train 50 + val 14）
TRAIN_IMAGES = (
    [f"gift_{i:03d}.jpg" for i in range(1, 11)] +   # gift_001~010
    [f"combo_{i:03d}.jpg" for i in range(1, 33)] +  # combo_001~032
    [f"main_{i:03d}.jpg" for i in range(1, 9)]      # main_001~008
)

VAL_IMAGES = (
    [f"gift_{i:03d}.jpg" for i in range(11, 14)] +  # gift_011~013
    [f"combo_{i:03d}.jpg" for i in range(33, 41)] + # combo_033~040
    [f"main_{i:03d}.jpg" for i in range(9, 12)]     # main_009~011
)

ALL_PILOT_IMAGES = TRAIN_IMAGES + VAL_IMAGES


def make_task(image_filename: str, split: str) -> dict:
    # 相对路径，相对于 DOCUMENT_ROOT（datasets/）
    return {
        "data": {
            "image": f"/data/local-files/?d=kgos_real_all/images/{image_filename}",
            "filename": image_filename,
            "split": split,
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true",
                        help="只生成 gift_001.jpg 的单图冒烟导入文件")
    args = parser.parse_args()

    if args.smoke:
        tasks = [make_task("gift_001.jpg", "train")]
        output_file = OUTPUT_DIR / "seg_pilot_smoke_import.json"
    else:
        tasks = (
            [make_task(f, "train") for f in TRAIN_IMAGES] +
            [make_task(f, "val") for f in VAL_IMAGES]
        )
        output_file = OUTPUT_DIR / "seg_pilot_import.json"

    # 验证图像文件存在
    missing = []
    for task in tasks:
        fname = task["data"]["filename"]
        if not (IMAGES_DIR / fname).exists():
            missing.append(fname)

    if missing:
        print(f"[ERROR] 以下图像文件不存在，请检查路径：")
        for f in missing:
            print(f"  {IMAGES_DIR / f}")
        raise SystemExit(1)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    print(f"[OK] 生成 {len(tasks)} 个任务 → {output_file}")
    if args.smoke:
        print("     冒烟测试文件，仅含 gift_001.jpg")
    else:
        train_count = len(TRAIN_IMAGES)
        val_count = len(VAL_IMAGES)
        print(f"     train: {train_count} 张，val: {val_count} 张")


if __name__ == "__main__":
    main()
