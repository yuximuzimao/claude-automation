# Train7 Evaluation Report

Date: 2026-06-07

## Acceptance Standard

Final acceptance must use the same format as `product-mapping`:

```js
recognition.items = [{ name: "<ERP standard product name>", qty: <number> }]
```

- `name` is the `erpName` from `product-mapping/data/products/kgos/features.json`.
- Comparison is exact set equality by `name×qty`.
- Business-distinct flavors/specs stay separate. Example: `KGOS玉米浓汤味玉米片 30g×5 + KGOS香菜牛肉味玉米片 30g×5` is not equivalent to `玉米片×10`.

## Training Result

Model: `runs/kgos_yolov8s_train7/weights/best.pt`

- Default val: `mAP50=0.99208`, `mAP50-95=0.97564`
- Business-val: `mAP50=0.99084`, `mAP50-95=0.96925`
- Production ONNX was not overwritten.

## Real Gift13 Result

Evaluation used `datasets/kgos_real_golden_gift13/images` with `conf=0.25`, `iou=0.70`, and the product-mapping ERP-name standard.

| Model | Correct | Expected | Detected | Recall | Precision | Exact Images |
|---|---:|---:|---:|---:|---:|---:|
| train6 | 60 | 108 | 61 | 55.56% | 98.36% | 5/13 |
| train7 | 66 | 108 | 81 | 61.11% | 81.48% | 3/13 |

## Interpretation

Train7 improved dense-layout recall, so the dense synthetic-data direction is useful. It is still far below the `gift13` dense recall target of `>=85%`, and it increased false positives enough to reduce precision.

The remaining business blocker is not ordinary val mAP. Real KGOS gift/combo images often contain bottom text that states the actual SKU names and quantities. YOLO still undercounts dense repeated items; text can correct this only after an OCR/text/LLM layer is implemented and evaluated.

## Decision

Do not start another long training run yet.

Next session must first implement or run text-combined validation:

1. Parse visible title/OCR text into `recognition.items` using ERP standard names and `qty`.
2. Merge text counts with YOLO detections; text quantity wins when it is explicit.
3. Re-evaluate real gift/combo images in three modes: YOLO-only, text-only, YOLO+text.
4. Only if YOLO+text still misses the target, start the next training/TTA/model-size experiment using the remaining failure cases.
