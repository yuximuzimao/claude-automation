#!/usr/bin/env python3
"""
素材图诊断工具

放好素材图后，先运行此脚本：
  python scripts/check_assets.py --brand kgos

输出报告：
  1. 控制台：每张图的背景类型 + 去背后透明像素比例
  2. assets/kgos/_check/ 目录：每张图的「原图 | 去背效果」对比图

重点关注：
  - 白色系产品（益生菌白盒、冰霸杯、保温壶）去背后是否有残缺
  - 透明背景 PNG 是否有白边残留
"""

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np


WHITE_THRESHOLD = 235


def remove_white_bg(img: Image.Image, threshold: int = WHITE_THRESHOLD) -> Image.Image:
    img = img.convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    mask = (r > threshold) & (g > threshold) & (b > threshold)
    arr[:, :, 3] = np.where(mask, 0, a)
    return Image.fromarray(arr)


def check_one(path: Path) -> dict:
    """检查单张素材图，返回诊断结果。"""
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    total_pixels = arr.shape[0] * arr.shape[1]

    has_real_transparency = bool((arr[:, :, 3] < 255).any())

    if has_real_transparency:
        # 已有透明通道
        transparent_ratio = (arr[:, :, 3] == 0).sum() / total_pixels
        bg_type = "透明背景 PNG"
        processed = img
        status = "✓ 直接使用"
        note = f"透明像素占比 {transparent_ratio:.1%}"
    else:
        # 去白底
        bg_type = "白底（JPG 或白底 PNG）"
        processed = remove_white_bg(img)
        proc_arr = np.array(processed)
        transparent_ratio = (proc_arr[:, :, 3] == 0).sum() / total_pixels
        # 产品占比太低说明白色产品被过度去除
        product_ratio = 1 - transparent_ratio
        if product_ratio < 0.03:
            status = "⚠ 产品过度去除"
            note = f"产品仅占 {product_ratio:.1%}，可能是白色产品被误删，需调整阈值"
        elif product_ratio < 0.08:
            status = "△ 请核查"
            note = f"产品占 {product_ratio:.1%}，请查看对比图确认是否正常"
        else:
            status = "✓ 去背正常"
            note = f"产品占 {product_ratio:.1%}"

    return {
        "path": path,
        "size": img.size,
        "bg_type": bg_type,
        "status": status,
        "note": note,
        "original": img,
        "processed": processed,
    }


def make_comparison(result: dict, size: int = 400) -> Image.Image:
    """生成原图 | 去背结果 对比图（棋盘格背景凸显透明区域）。"""
    # 棋盘格背景（凸显透明区域）
    def checkerboard(w, h, tile=20):
        board = Image.new("RGB", (w, h), (200, 200, 200))
        draw = ImageDraw.Draw(board)
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                if (x // tile + y // tile) % 2 == 0:
                    draw.rectangle([x, y, x + tile, y + tile], fill=(240, 240, 240))
        return board

    def resize_to_square(img, sz):
        img = img.copy()
        img.thumbnail((sz, sz), Image.LANCZOS)
        canvas = Image.new("RGBA", (sz, sz), (255, 255, 255, 0))
        offset = ((sz - img.width) // 2, (sz - img.height) // 2)
        canvas.paste(img, offset, img if img.mode == "RGBA" else None)
        return canvas

    orig_sq = resize_to_square(result["original"].convert("RGBA"), size)
    proc_sq = resize_to_square(result["processed"].convert("RGBA"), size)

    board = checkerboard(size * 2 + 4, size)

    # 左：原图贴白底
    left_bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    left_bg.paste(orig_sq, (0, 0), orig_sq)
    board.paste(left_bg.convert("RGB"), (0, 0))

    # 分隔线
    ImageDraw.Draw(board).rectangle([size, 0, size + 3, size], fill=(80, 80, 80))

    # 右：处理后贴棋盘格
    right_bg = checkerboard(size, size)
    right_bg = right_bg.convert("RGBA")
    right_bg.paste(proc_sq, (0, 0), proc_sq)
    board.paste(right_bg.convert("RGB"), (size + 4, 0))

    # 标注状态
    draw = ImageDraw.Draw(board)
    status_color = (34, 139, 34) if "✓" in result["status"] else (200, 100, 0)
    draw.text((4, 4), f"原图", fill=(80, 80, 80))
    draw.text((size + 8, 4), f"去背后 ({result['status']})", fill=status_color)
    draw.text((4, size - 16), result["note"][:50], fill=(80, 80, 80))

    return board


def main():
    import argparse
    parser = argparse.ArgumentParser(description="素材图诊断工具")
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"])
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    brand_dir = project_root / "assets" / args.brand
    out_dir = brand_dir / "_check"
    out_dir.mkdir(exist_ok=True)

    supported = {".jpg", ".jpeg", ".png", ".webp"}
    paths = sorted(p for p in brand_dir.iterdir() if p.suffix.lower() in supported)

    if not paths:
        print(f"⚠ {brand_dir} 下没有找到图片，请先放入素材图")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  素材诊断报告 — {args.brand.upper()}  ({len(paths)} 张)")
    print(f"{'='*60}")

    issues = []
    for path in paths:
        result = check_one(path)
        icon = result["status"].split()[0]
        print(f"  {icon}  {path.name:<30}  {result['bg_type']}")
        print(f"       {result['note']}")

        # 保存对比图
        comp = make_comparison(result)
        comp.save(out_dir / f"{path.stem}_check.jpg", quality=88)

        if "⚠" in result["status"] or "△" in result["status"]:
            issues.append(result)

    print(f"\n{'='*60}")
    print(f"对比图已保存到: {out_dir}")
    print(f"请用图片查看器打开 _check/ 目录，左边是原图，右边是去背后效果")

    if issues:
        print(f"\n⚠ 需要人工核查的素材（{len(issues)} 张）：")
        for r in issues:
            print(f"  - {r['path'].name}: {r['note']}")
        print(f"\n如果去背效果不理想（白色产品被误删），请联系开发调整阈值")
    else:
        print(f"\n✓ 全部素材去背正常，可以运行 generate.py 生成训练数据")

    print()


if __name__ == "__main__":
    main()
