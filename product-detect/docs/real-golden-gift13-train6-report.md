# Train6 on KGOS real gift13

Date: 2026-06-04

## Inputs

- Model: `runs/kgos_yolov8s_train6/weights/best.pt`
- Images: `datasets/kgos_real_golden_gift13/images/`
- Predict output: `runs/predict_real_gift13_train6_conf040/`
- Contact sheet: `runs/predict_real_gift13_train6_conf040/_contact_sheet.jpg`
- Confidence threshold: `0.40`

## Result

Train6 is not production-safe for these 13 real gift-package images if the business requires accurate package counts.

It usually detects the major SKU categories, but repeated rows/grids are undercounted because the detector often treats a repeated row as one or a few objects.

## Image-Level Review

| Image | Expected from visible caption | Train6 prediction | Review |
|---|---|---|---|
| `1.jpg` | 酵素4.0体验装 1 + 腰围卡尺 1 | 酵素4.0体验装 1 + 腰围卡尺 1 | Pass |
| `2.jpg` | 黑咖体验装 1 + 腰围卡尺 1 | 黑咖体验装 1 + 腰围卡尺 1 | Pass |
| `3.jpg` | 黑茶体验装 1（口味随机）+ 腰围卡尺 1 | 黑茶体验装-茉莉花茶味 1 + 黑茶体验装-青柑普洱味 1 + 腰围卡尺 2 | Fail / semantic ambiguity |
| `4.jpg` | 一次性吸管袋 1 + 腰围卡尺 1 | 一次性吸管袋 1 + 腰围卡尺 1 | Pass |
| `5.jpg` | 玉米片 10 | 玉米片-玉米浓汤味 3 + 玉米片-香菜牛肉味 2 | Fail, undercount |
| `6.jpg` | 益生菌 3 + 玉米片 10 | 益生菌 3 + 玉米片-玉米浓汤味 1 + 玉米片-香菜牛肉味 1 | Partial, corn chips undercount |
| `7.jpg` | 一次性吸管袋 3 | 一次性吸管袋 3 | Pass |
| `8.jpg` | 益生菌 1 | 益生菌 1 | Pass |
| `9.jpg` | 营养粉 1 + 玉米片 10 | 营养粉-莓果味 1 + 玉米片-玉米浓汤味 2 + 玉米片-香菜牛肉味 1 | Partial, corn chips undercount |
| `10.jpg` | 帆布袋 3 + 玉米片 10 | 帆布袋 3 + 玉米片-玉米浓汤味 2 + 玉米片-香菜牛肉味 1 | Partial, corn chips undercount |
| `11.jpg` | 营养粉 3 + 冰霸杯 1 + 玉米片 10 | 营养粉-莓果味 3 + 冰霸杯 1 + 玉米片-玉米浓汤味 1 + 玉米片-香菜牛肉味 2 | Partial, corn chips undercount and nutrition flavor uncertain |
| `12.jpg` | 益生菌 6 + 冰霸杯 1 + 玉米片 10 | 益生菌 2 + 冰霸杯 1 + 玉米片-玉米浓汤味 2 + 玉米片-香菜牛肉味 1 | Fail, repeated items undercount |
| `13.jpg` | 帆布袋 6 + 冰霸杯 1 + 玉米片 10 | 帆布袋 5 + 冰霸杯 1 + 玉米片-玉米浓汤味 1 + 玉米片-香菜牛肉味 1 | Fail, repeated items undercount |

## Failure Pattern

- Repeated rows/grids are the main failure mode.
- Class recognition is mostly usable for prominent single items.
- Counting is not reliable for repeated套餐组合.
- The real images include caption text that directly states the套餐 contents; the current detector ignores this useful signal.

## Next Step

Before any new training run, add real ground-truth labels for this set or define a caption-level expected-count benchmark. If the production goal is套餐识别 rather than visible-instance counting, the evaluation target should include OCR/caption parsing or SKU-combo rules, not only YOLO boxes.

