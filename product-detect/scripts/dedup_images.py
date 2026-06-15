#!/usr/bin/env python3
"""
图片去重 / 近重复检测工具（product-detect）

用途
====
1. 对一个图片目录做两两去重扫描，找出完全重复（字节级 md5 相同）和
   近重复（感知哈希汉明距离很小，可能裁剪/压缩/微调/重存）。
2. 新增图片时，把新图与已有图库比对，报告新图是否与库内某张图重复，
   以及最相似的是哪一张、距离多少。

设计要点
========
本数据集特性（重要）
--------------------
KGOS 商品主图都是「纯白底 + 居中商品 + 底部中文文案」的电商主图。
缩到 8x8 灰度后，这类构图天然高度相似，单一感知哈希阈值会海量误报
（实测 270 张内 min(aHash,dHash)<=5 有 2700+ 对，绝大多数是不同商品）。
因此本工具用三级闸门联合判定，缺一不可：

  级别1  md5 相同            → 字节完全相同（同一文件被复制）
  级别2  aHash 和 dHash 都小 → 两个独立哈希都认同（AND，不是 OR/min）
  级别3  灰度 64x64 像素 MAE → 直接像素证据，过滤哈希巧合碰撞

- 感知哈希自实现（仅依赖 PIL + numpy，不依赖 imagehash 库）：
    * average hash (aHash)：8x8 灰度，与均值比较，对整体亮度/压缩鲁棒。
    * dhash：9x8 灰度，比较相邻像素，对裁剪/局部变化更敏感。
  两者都是 64-bit。综合哈希距离 = max(aHash距离, dHash距离)，
  即「两个哈希都说像」才算像（取 min 会放大 aHash 误报，已验证）。
- grayMAE = 两图缩到 64x64 灰度后逐像素绝对差均值（0~255）。
- colorMAE = 两图缩到 32x32 RGB 后逐像素逐通道绝对差均值（0~255）。
  灰度会抹掉颜色差异：KGOS 有「同排版模板换主体盒色」的不同口味商品
  （如青柑普洱黄盒 vs 茉莉绿盒），灰度 MAE 仅 2~3 会误判成重复，
  必须用 colorMAE 把它们区分开。
  实测：真重复(同图重存) grayMAE<1 且 colorMAE<3；
        同模板换色的不同口味 grayMAE 2~3 但 colorMAE >8。
- 判定阈值（默认，收紧后）：
    * 字节 md5 相同                                   → EXACT_DUPLICATE
    * 哈希 <= 1 且 grayMAE <= 1.2 且 colorMAE <= 4.0  → DUPLICATE（同图重存/仅重新编码，可安全去重）
    * 哈希 <= 5 且 grayMAE <= 6.0 且 colorMAE <= 12   → NEAR_DUPLICATE（高度相似，人工确认是否同款）
    * 其余                                            → 视为不同图

用法
====
# A. 自检 / 库内两两扫描（拿目录自己跟自己比）
python scripts/dedup_images.py --against datasets/kgos_real_all/images

# B. 新增图片比对（单张或一批新图 vs 已有图库）
python scripts/dedup_images.py --new path/to/new.jpg --against datasets/kgos_real_all/images
python scripts/dedup_images.py --new path/to/new_dir --against datasets/kgos_real_all/images

# 可调阈值（默认近重复阈值 5）
python scripts/dedup_images.py --against <dir> --threshold 8
"""

import argparse
import hashlib
import os
import sys
from itertools import combinations

import numpy as np
from PIL import Image

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

# 闸门阈值（综合哈希距离 = max(aHash, dHash)）
DUP_HASH = 1           # 内容重复：综合哈希 <= 1
DUP_GMAE = 1.2         # 内容重复：灰度 MAE <= 1.2
DUP_CMAE = 4.0         # 内容重复：彩色 MAE <= 4.0（挡住同模板换色）
NEAR_HASH = 5          # 近重复：综合哈希 <= 5（默认，可 --threshold 覆盖）
NEAR_GMAE = 6.0        # 近重复：灰度 MAE <= 6.0
NEAR_CMAE = 12.0       # 近重复：彩色 MAE <= 12.0


def list_images(path):
    """返回 path 下（或单文件）的所有图片绝对路径，排序稳定。"""
    if os.path.isfile(path):
        return [os.path.abspath(path)]
    out = []
    for name in sorted(os.listdir(path)):
        ext = os.path.splitext(name)[1].lower()
        if ext in IMG_EXTS:
            out.append(os.path.abspath(os.path.join(path, name)))
    return out


def _gray_resize(img, w, h):
    """转灰度并缩放到 (w, h)，返回 numpy 数组。"""
    g = img.convert("L").resize((w, h), Image.LANCZOS)
    return np.asarray(g, dtype=np.float64)


def ahash(img):
    """average hash，8x8 = 64 bit。返回 Python int。"""
    a = _gray_resize(img, 8, 8)
    bits = a > a.mean()
    return _bits_to_int(bits.flatten())


def dhash(img):
    """dhash，9x8 -> 8x8 = 64 bit（比较水平相邻像素）。返回 Python int。"""
    a = _gray_resize(img, 9, 8)
    bits = a[:, 1:] > a[:, :-1]
    return _bits_to_int(bits.flatten())


def _bits_to_int(bits):
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def hamming(a, b):
    """两个 int 哈希的汉明距离。"""
    return bin(a ^ b).count("1")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gray64(img):
    """缩到 64x64 灰度，作为灰度 MAE 复核的像素向量。"""
    return _gray_resize(img, 64, 64)


def rgb32(img):
    """缩到 32x32 RGB，作为彩色 MAE 复核向量（区分同模板换色）。"""
    r = img.convert("RGB").resize((32, 32), Image.LANCZOS)
    return np.asarray(r, dtype=np.float64)


def fingerprint(path):
    """计算一张图的 (md5, ahash, dhash, gray, rgb)。读图失败返回 None。"""
    try:
        with Image.open(path) as img:
            img.load()
            a = ahash(img)
            d = dhash(img)
            g = gray64(img)
            c = rgb32(img)
        return {"path": path, "md5": md5_of(path), "ahash": a, "dhash": d,
                "gray": g, "rgb": c}
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[WARN] 跳过无法读取的文件 {path}: {e}\n")
        return None


def gray_mae(fp_a, fp_b):
    """两图 64x64 灰度逐像素绝对差均值（0~255）。"""
    return float(np.abs(fp_a["gray"] - fp_b["gray"]).mean())


def color_mae(fp_a, fp_b):
    """两图 32x32 RGB 逐像素逐通道绝对差均值（0~255）。"""
    return float(np.abs(fp_a["rgb"] - fp_b["rgb"]).mean())


def hash_distance(fp_a, fp_b):
    """综合哈希距离 = max(aHash距离, dHash距离)，两哈希都认同才算近。"""
    return max(
        hamming(fp_a["ahash"], fp_b["ahash"]),
        hamming(fp_a["dhash"], fp_b["dhash"]),
    )


def classify(fp_a, fp_b, near_hash=NEAR_HASH):
    """四级闸门判定两图关系，返回 (verdict, hash_dist, gray_mae, color_mae)。

    EXACT_DUPLICATE 由调用方按 md5 判定，这里不涉及。
    """
    h = hash_distance(fp_a, fp_b)
    if h > near_hash:
        return ("DIFFERENT", h, None, None)
    gm = gray_mae(fp_a, fp_b)
    cm = color_mae(fp_a, fp_b)
    if h <= DUP_HASH and gm <= DUP_GMAE and cm <= DUP_CMAE:
        return ("DUPLICATE", h, gm, cm)
    if h <= near_hash and gm <= NEAR_GMAE and cm <= NEAR_CMAE:
        return ("NEAR_DUPLICATE", h, gm, cm)
    return ("DIFFERENT", h, gm, cm)  # 哈希碰撞但被 MAE 否决


def build_index(paths):
    """对一批路径计算指纹，返回 list[dict]（已过滤失败项）。"""
    fps = []
    for p in paths:
        fp = fingerprint(p)
        if fp is not None:
            fps.append(fp)
    return fps


def scan_within(fps, near_hash):
    """库内两两扫描。返回 (md5_groups, dup_pairs)。

    md5_groups: list[list[name]] 字节完全相同的分组（每组 >=2）。
    dup_pairs: list[(verdict, nameA, nameB, hash, gray_mae, color_mae)]
               判定为 DUPLICATE / NEAR_DUPLICATE 的对，按 (color_mae, gray_mae) 升序。
    """
    by_md5 = {}
    for fp in fps:
        by_md5.setdefault(fp["md5"], []).append(os.path.basename(fp["path"]))
    md5_groups = [sorted(v) for v in by_md5.values() if len(v) > 1]

    dup_pairs = []
    for a, b in combinations(fps, 2):
        verdict, h, gm, cm = classify(a, b, near_hash)
        if verdict in ("DUPLICATE", "NEAR_DUPLICATE"):
            dup_pairs.append(
                (verdict, os.path.basename(a["path"]),
                 os.path.basename(b["path"]), h, gm, cm)
            )
    dup_pairs.sort(key=lambda x: (x[5] if x[5] is not None else 999, x[4], x[3]))
    return md5_groups, dup_pairs


def check_new(new_fps, lib_fps, near_hash):
    """每张新图 vs 图库，返回报告列表（用四级闸门）。"""
    lib_md5 = {}
    for fp in lib_fps:
        lib_md5.setdefault(fp["md5"], []).append(os.path.basename(fp["path"]))

    reports = []
    for nf in new_fps:
        nname = os.path.basename(nf["path"])
        exact = sorted(x for x in lib_md5.get(nf["md5"], []) if x != nname)

        best = None  # (name, hash, gray_mae, color_mae, verdict, score)
        for lf in lib_fps:
            if os.path.abspath(lf["path"]) == os.path.abspath(nf["path"]):
                continue
            verdict, h, gm, cm = classify(nf, lf, near_hash)
            score = (
                0 if verdict in ("DUPLICATE", "NEAR_DUPLICATE") else 1,
                cm if cm is not None else 999.0,
                gm if gm is not None else 999.0,
                h,
            )
            if best is None or score < best[5]:
                best = (os.path.basename(lf["path"]), h, gm, cm, verdict, score)

        if exact:
            final = "EXACT_DUPLICATE"
        elif best is not None and best[4] in ("DUPLICATE", "NEAR_DUPLICATE"):
            final = best[4]
        else:
            final = "UNIQUE"

        reports.append(
            {
                "new": nname,
                "verdict": final,
                "exact_matches": exact,
                "most_similar": best[0] if best else None,
                "hash_dist": best[1] if best else None,
                "gray_mae": best[2] if best else None,
                "color_mae": best[3] if best else None,
            }
        )
    return reports


def main():
    ap = argparse.ArgumentParser(description="图片去重 / 近重复检测")
    ap.add_argument("--against", required=True, help="已有图库目录")
    ap.add_argument("--new", help="新图片（单文件或目录）；不给则做库内两两自检")
    ap.add_argument(
        "--threshold",
        type=int,
        default=NEAR_HASH,
        help=f"近重复综合哈希阈值（默认 {NEAR_HASH}；灰度/彩色 MAE 复核阈值固定）",
    )
    args = ap.parse_args()

    lib_paths = list_images(args.against)
    if not lib_paths:
        sys.exit(f"[ERROR] 图库目录无图片: {args.against}")
    lib_fps = build_index(lib_paths)
    print(f"图库: {args.against}  有效图片 {len(lib_fps)} 张")

    if args.new:
        new_paths = list_images(args.new)
        if not new_paths:
            sys.exit(f"[ERROR] --new 路径无图片: {args.new}")
        new_fps = build_index(new_paths)
        reports = check_new(new_fps, lib_fps, args.threshold)
        print(f"\n=== 新图比对结果（{len(reports)} 张）===")
        for r in reports:
            line = f"[{r['verdict']}] {r['new']}"
            if r["most_similar"] is not None:
                gm = f"{r['gray_mae']:.1f}" if r["gray_mae"] is not None else "-"
                cm = f"{r['color_mae']:.1f}" if r["color_mae"] is not None else "-"
                line += (f"  最相似: {r['most_similar']} "
                         f"(hash {r['hash_dist']}, 灰MAE {gm}, 彩MAE {cm})")
            if r["exact_matches"]:
                line += f"  字节相同: {', '.join(r['exact_matches'])}"
            print(line)
        dup = [r for r in reports if r["verdict"] != "UNIQUE"]
        print(f"\n小结: {len(dup)}/{len(reports)} 张新图与图库重复或近重复。")
    else:
        md5_groups, dup_pairs = scan_within(lib_fps, args.threshold)
        print(f"\n=== 库内自检（综合哈希<= {args.threshold} + 灰度/彩色 MAE 复核）===")
        print(f"\n字节级完全相同（md5）分组: {len(md5_groups)} 组")
        for g in md5_groups:
            print("  - " + " == ".join(g))
        dups = [p for p in dup_pairs if p[0] == "DUPLICATE"]
        nears = [p for p in dup_pairs if p[0] == "NEAR_DUPLICATE"]
        print(f"\n内容重复对 DUPLICATE（同图重存/仅重编码，可安全去重）: {len(dups)} 对")
        for _, a, b, h, gm, cm in dups:
            print(f"  - [hash {h}, 灰MAE {gm:.1f}, 彩MAE {cm:.1f}] {a}  <->  {b}")
        print(f"\n近重复对 NEAR_DUPLICATE（高度相似，需人工确认是否同款）: {len(nears)} 对")
        for _, a, b, h, gm, cm in nears:
            print(f"  - [hash {h}, 灰MAE {gm:.1f}, 彩MAE {cm:.1f}] {a}  <->  {b}")


if __name__ == "__main__":
    main()
