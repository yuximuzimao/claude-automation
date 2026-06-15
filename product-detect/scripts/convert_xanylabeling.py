"""
X-AnyLabeling 标注 → YOLO 双数据集转换器。
一份人工 SAM 多边形标注，自动生成两套训练数据：
  - YOLO-seg（分割）：直接用多边形点
  - YOLO-det（检测）：用多边形的外接矩形派生检测框（无需手标第二遍）

用法：
  python scripts/convert_xanylabeling.py \
    --images datasets/kgos_real_all/images \
    --classes datasets/kgos_real_all/classes.txt \
    --out-seg datasets/kgos_seg_pilot \
    --out-det datasets/kgos_detect_pilot \
    --val-ratio 0.2

只转换有对应 .json 标注的图；没标的图跳过并计入报告。
"""
import os, json, argparse, shutil, hashlib


def load_classes(path):
    return [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]


def split_train_val(names, val_ratio):
    # 用文件名哈希做确定性 split（同名永远落同一侧，可复现）
    val = []
    train = []
    for n in sorted(names):
        h = int(hashlib.md5(n.encode()).hexdigest(), 16)
        (val if (h % 100) < val_ratio * 100 else train).append(n)
    return train, val


def poly_to_seg_line(cls, pts, W, H):
    coords = " ".join(f"{x/W:.6f} {y/H:.6f}" for x, y in pts)
    return f"{cls} {coords}"


def poly_to_det_line(cls, pts, W, H):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    cx, cy = (x0 + x1) / 2 / W, (y0 + y1) / 2 / H
    w, h = (x1 - x0) / W, (y1 - y0) / H
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def write_yaml(out_dir, classes):
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(classes))
    yaml = (
        f"path: {os.path.abspath(out_dir)}\n"
        f"train: images/train\nval: images/val\n"
        f"nc: {len(classes)}\nnames:\n{names}\n"
    )
    open(os.path.join(out_dir, "data.yaml"), "w", encoding="utf-8").write(yaml)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--classes", required=True)
    ap.add_argument("--out-seg", required=True)
    ap.add_argument("--out-det", required=True)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    args = ap.parse_args()

    classes = load_classes(args.classes)
    cls_idx = {c: i for i, c in enumerate(classes)}

    # 找有标注的图
    labeled = []
    skipped = []
    for f in sorted(os.listdir(args.images)):
        if not f.lower().endswith((".jpg", ".png")):
            continue
        jpath = os.path.join(args.images, os.path.splitext(f)[0] + ".json")
        (labeled if os.path.exists(jpath) else skipped).append(f)

    train, val = split_train_val(labeled, args.val_ratio)
    print(f"已标注 {len(labeled)} 张 | 未标注跳过 {len(skipped)} 张")
    print(f"split: train {len(train)} / val {len(val)}")

    for out in (args.out_seg, args.out_det):
        for sub in ("images/train", "images/val", "labels/train", "labels/val"):
            os.makedirs(os.path.join(out, sub), exist_ok=True)

    unknown_labels = set()
    for split_name, names in (("train", train), ("val", val)):
        for f in names:
            base = os.path.splitext(f)[0]
            jpath = os.path.join(args.images, base + ".json")
            d = json.load(open(jpath, encoding="utf-8"))
            W, H = d["imageWidth"], d["imageHeight"]
            seg_lines, det_lines = [], []
            for s in d.get("shapes", []):
                lbl = s.get("label")
                if lbl not in cls_idx:
                    unknown_labels.add(lbl)
                    continue
                ci = cls_idx[lbl]
                pts = s.get("points", [])
                if len(pts) < 3:
                    continue
                seg_lines.append(poly_to_seg_line(ci, pts, W, H))
                det_lines.append(poly_to_det_line(ci, pts, W, H))
            # 写两套
            for out, lines in ((args.out_seg, seg_lines), (args.out_det, det_lines)):
                shutil.copy(
                    os.path.join(args.images, f),
                    os.path.join(out, "images", split_name, f),
                )
                open(
                    os.path.join(out, "labels", split_name, base + ".txt"),
                    "w", encoding="utf-8",
                ).write("\n".join(lines) + ("\n" if lines else ""))

    write_yaml(args.out_seg, classes)
    write_yaml(args.out_det, classes)
    print(f"✅ 分割数据集 -> {args.out_seg}")
    print(f"✅ 检测数据集 -> {args.out_det}")
    if unknown_labels:
        print(f"⚠️ 跳过了不在 classes.txt 里的标签: {unknown_labels}")
    if skipped:
        print(f"ℹ️ 未标注（无 json）: {len(skipped)} 张，待标注完成后重跑")


if __name__ == "__main__":
    main()
