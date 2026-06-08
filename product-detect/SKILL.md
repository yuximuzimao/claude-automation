# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。最终验收输出必须对齐 product-mapping：`recognition.items = [{ name: ERP标准商品名, qty }]`。

## 当前状态

- Phase: 3（**密排漏检优化 — 三层管道 v2 计划进行中**）
- **train7 已完成并复评**：输出 `runs/kgos_yolov8s_train7/`
  - 默认 val mAP50-95=0.97564；business-val mAP50-95=0.96925
  - gift13 按 product-mapping ERP 标准名+qty 口径：recall=61.11%，precision=81.48%，exact=3/13
  - 结论：密排召回比 train6 有提升，但误检增加，未达生产门槛；不要先开下一训，先做文字结合验证
- **文字结合验证已进入 text50 初测**：
  - `scripts/ocr_verify.py` 固定 YOLO-first 规则：视觉决定具体商品，文字只纠正数量或确认已识别子类
  - `scripts/text50_eval.py` 初测 12 张 labeled 样本：YOLO-only exact=3/12，raw YOLO+text exact=5/12，YOLO+text gated exact=11/12
  - 结论：文字路线有价值，但必须通过 anomaly gating 拦截误检和模糊子类；不能把 raw YOLO+text 直接写入 product-mapping
- **简称/别名表已建立**：`data/kgos_text_aliases.json`
  - `exact_aliases`：如“莓果营养粉”“牛油果营养粉”，可直映一个 ERP 标准名
  - `ambiguous_groups`：如“玉米片”“营养粉”“黑茶体验装”，只给候选组，必须由 YOLO/LLM/人工视觉确认具体口味
- **第六次训练**：2026-06-01 启动，2026-06-03 完成 100 epochs
  - 默认 val mAP50-95=0.96728，business-val mAP50-95=0.97000
  - 真实礼品图密排召回率约 40%，确认问题来自训练分布不贴近真实 SKU 主图
- **三层管道计划 v2**（2026-06-04 起执行）：
  - 计划：`~/.claude/plans/nested-mapping-trinket.md`
  - 目标：98%（OCR 有效率≥90%，YOLO 密排召回≥92%）
  - 已完成：NMS+conf 扫描、generate.py 密排布局/遮挡/投影阴影、train7 训练与真实口径评估、YOLO-first 文字纠正、text50 gating 初测、简称表
  - 下一步优先：正式 anomaly pipeline → 真实 OCR/LLM 多模态兜底 → 扩充 text50 标注 → 黄金验证集 100 张 → [TTA/集成按需]
- **真实 KGOS SKU 主图语料**：微信文件目录 `.../2026-05/1主图汇总`，270 张可读图；规则矩阵、买赠组合、重复排列、赠品角标。详见 `docs/dataset-quality.md`
- hee 未开始

## ENTRY MAP

| 任务 | 入口 |
|------|------|
| 生成训练数据 | `python scripts/generate.py --brand kgos --count 4000 --profile train` |
| 生成业务验收验证集 | `python scripts/generate.py --brand kgos --count 600 --profile business-val` |
| 数据集质量规范 | `docs/dataset-quality.md` |
| NMS/conf 扫描 | `python scripts/nms_sweep.py` |
| YOLO-first 文字纠正试验 | `python scripts/ocr_verify.py` |
| text50 exact/gating 评估 | `python scripts/text50_eval.py` |
| KGOS 简称/模糊组表 | `data/kgos_text_aliases.json` |
| 验证标注效果 | `python scripts/verify.py --brand kgos` |
| 验证业务验收集标注 | `python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50` |
| train7 微调 | `python -u scripts/train.py --brand kgos --model yolov8s --finetune runs/kgos_yolov8s_train6/weights/best.pt --name kgos_yolov8s_train7 --epochs 60` |
| train7 评估报告 | `docs/train7-evaluation-report.md` |
| 推理测试 | `python scripts/infer.py --brand kgos --image xxx.jpg` |
| 查看进度 | `tasks/todo.md` |
| 回归测试 | `python3 -m unittest tests.test_train tests.test_generate tests.test_verify tests.test_nms_sweep -v` |

## PATHS

```
assets/
  kgos/          ← 单品素材图（文件名=ERP产品名，与 features.json key 一致）
  hee/           ← hee 品牌素材图
datasets/
  kgos/          ← generate.py --profile train 输出，含 data.yaml + images/ + labels/
  kgos_business_val/ ← generate.py --profile business-val 输出，独立业务验收验证集
  hee/           ← 同上
models/
  kgos_best.onnx ← 训练完成后的生产模型
  hee_best.onnx
scripts/
  generate.py    ← 合成数据生成器（主工具）
  train.py       ← CPU 训练脚本；--finetune 微调；--export-production 才覆盖生产 ONNX
  verify.py      ← 标注可视化验证
  infer.py       ← 生产推理（ProductDetector 类）
  nms_sweep.py   ← NMS/conf 扫描
  ocr_verify.py  ← YOLO-first 文字纠正规则参考实现
  text50_eval.py ← text50 exact-match / gating 评估
data/
  kgos_text_aliases.json ← 可积累简称表，exact/ambiguous 语义分开
tests/
  test_generate.py ← 生成规则与遮挡标注回归测试
runs/            ← 训练日志和权重（git ignore）
```

## 训练注意事项

- 黄金验证集和三层管道评估通过前，不要覆盖 `models/kgos_best.onnx`；`train.py` 默认不会导出生产 ONNX。
- 当前 train7 已按真实验收指标判断为不可直接生产；不要只看默认 val mAP，也不要在文字结合验证前启动下一轮长训。
- 文字描述是辅助纠错，不是事实来源。模糊文字如“玉米片 10”“营养粉 3”不得直接生成具体 ERP 子品，必须由视觉确认具体口味。
- `datasets/kgos_real_text50/ground_truth.json` 当前位于 git ignore 的 `datasets/` 下；如果要作为长期基准集提交，先移动到 `docs/` 或调整 `.gitignore`。
- 新训练必须保留独立输出目录，避免覆盖历史 run 和生产权重。
- 清理旧数据时保留当前/基线/黄金相关目录：`datasets/kgos*`、`datasets/kgos_real_*`、`runs/kgos_yolov8s_train6/`、`runs/kgos_yolov8s_train7/`、当前 `runs/kgos_train7.log`。

## DO FIRST（新 session 进入）

1. 读 `tasks/todo.md` 确认当前阶段
2. 读 `docs/train7-evaluation-report.md`、`docs/text50-evaluation-report.md`、`docs/text-correction-followup-plan.md`
3. 继续阶段4：把 text50 gating 升级成正式 anomaly pipeline，并接 OCR/LLM 视觉兜底
4. 扩充 text50 ground truth 前，先处理 `datasets/` 被 git ignore 的持久化位置
5. 确认 conda yolov8 环境是否就绪

## 生成规则

- 背景固定纯白，不再生成噪声背景。
- 训练集按 `single` / `mixed_clean` / `mixed_occluded` / `row_layout` / `grid_layout` / `gift_package` 生成，比例 10% / 15% / 15% / 20% / 20% / 20%。
- 遮挡样本按最终可见 alpha mask 计算 bbox；可见面积低于原始面积 35% 的目标不写 label。
- 密排场景加入可控前后遮挡和高斯投影阴影，目标是贴近真实 SKU 主图的规则矩阵、重复排列、买赠组合。
- `business-val` 独立写入 `datasets/<brand>_business_val/`，不做亮度/对比度增强，用于业务验收。
