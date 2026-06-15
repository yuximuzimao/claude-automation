"""
X-AnyLabeling SAM 引擎冒烟测试（脱离 GUI，直接验证 SAM 在本机能出 mask）。
目的：证明换工具后「点一下出轮廓」的核心功能在这台 Mac 上真的可用，并测速。
用法：python scripts/sam_smoke_xanylabeling.py
"""
import time
import os
import numpy as np
import cv2
from anylabeling.services.auto_labeling.sam_onnx import SegmentAnythingONNX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = os.path.join(ROOT, "models/sam/mobile_sam.encoder.onnx")
DEC = os.path.join(ROOT, "models/sam/sam_vit_h_4b8939.decoder.onnx")
IMG = os.path.join(ROOT, "datasets/kgos_real_all/images/gift_001.jpg")
OUT = os.path.join(ROOT, "models/sam/_smoke")
os.makedirs(OUT, exist_ok=True)

# 两个商品各点一个正例（坐标基于 1280x1280 原图肉眼定位）
POINTS = {
    "box_诺丽果益生元饮": (410, 580),
    "tape_腰围卡尺": (730, 650),
}

def best_mask(masks):
    # masks: (batch, n, H, W) logits -> 取面积最大的一张二值 mask
    m = masks[0]
    bins = [(mm > 0).astype(np.uint8) for mm in m]
    areas = [int(b.sum()) for b in bins]
    i = int(np.argmax(areas))
    return bins[i], areas[i]

def mask_to_yolo_seg(mask, W, H, cls=0):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, None
    c = max(cnts, key=cv2.contourArea)
    eps = 0.002 * cv2.arcLength(c, True)
    poly = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
    seg = " ".join(f"{x/W:.6f} {y/H:.6f}" for x, y in poly)
    x, y, w, h = cv2.boundingRect(c)
    det = f"{(x+w/2)/W:.6f} {(y+h/2)/H:.6f} {w/W:.6f} {h/H:.6f}"
    return f"{cls} {seg}", f"{cls} {det}"

def main():
    print(f"[load] encoder={os.path.getsize(ENC)//1024//1024}MB decoder={os.path.getsize(DEC)//1024//1024}MB")
    import onnxruntime as ort
    t0 = time.time()
    model = SegmentAnythingONNX(ENC, DEC)
    # 本机 CoreML EP 跑不动 MobileSAM encoder（onnxruntime -1），强制 CPU（与 GUI 的 Preferred Device=CPU 一致）
    model.providers = ["CPUExecutionProvider"]
    model.encoder_session = None  # 触发 CPU 懒加载重建
    model.decoder_session = ort.InferenceSession(DEC, providers=["CPUExecutionProvider"])
    print(f"[load] sessions ready in {time.time()-t0:.2f}s, providers={model.providers}")

    img = cv2.imread(IMG)
    H, W = img.shape[:2]
    print(f"[img] {IMG} {W}x{H}")

    t0 = time.time()
    emb = model.encode(img)
    t_enc = time.time() - t0
    print(f"[encode] {t_enc:.2f}s  (整图编码一次，之后每次点击只跑 decoder)")

    overlay = img.copy()
    seg_lines, det_lines = [], []
    for name, (px, py) in POINTS.items():
        prompt = [{"type": "point", "data": [px, py], "label": 1}]
        t0 = time.time()
        masks = model.predict_masks(emb, prompt)
        t_dec = time.time() - t0
        mask, area = best_mask(masks)
        pct = 100.0 * area / (W * H)
        seg, det = mask_to_yolo_seg(mask, W, H)
        seg_lines.append(seg); det_lines.append(det)
        npoly = len(seg.split()) // 2 if seg else 0
        print(f"[click {name}] decoder={t_dec*1000:.0f}ms  mask面积={area}px ({pct:.1f}%图)  多边形点数={npoly}")
        color = np.random.RandomState(abs(hash(name)) % 2**32).randint(60, 255, 3)
        overlay[mask > 0] = (0.5 * overlay[mask > 0] + 0.5 * color).astype(np.uint8)
        cv2.circle(overlay, (px, py), 8, (0, 0, 255), -1)

    op = os.path.join(OUT, "gift_001_overlay.png")
    cv2.imwrite(op, overlay)
    with open(os.path.join(OUT, "gift_001_seg.txt"), "w") as f:
        f.write("\n".join(seg_lines) + "\n")
    with open(os.path.join(OUT, "gift_001_det.txt"), "w") as f:
        f.write("\n".join(det_lines) + "\n")
    print(f"[done] overlay -> {op}")
    print(f"[done] YOLO-seg/detect 标签已写入 {OUT}")

if __name__ == "__main__":
    main()
