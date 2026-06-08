# product-detect — YOLOv8 商品识别

项目中文名：商品识别训练

替代 product-mapping 中的 LLM 识图，本地推理，零 token 消耗。

当前结论：`train7` 已完成但不能直接生产；文字结合验证已证明“有用但不能裸合并”。text50 初测中 YOLO+text gated exact=11/12，明显优于 YOLO-only 3/12，但 raw YOLO+text 只有 5/12。下一步应把 gating 升级为正式异常管道，并接入 OCR/LLM 视觉兜底；不要先开启下一轮长训。最终验收输出必须对齐 product-mapping 的 `recognition.items = [{ name: ERP标准商品名, qty }]`，标准名来自 `product-mapping/data/products/kgos/features.json` 的 `erpName`。

## 工作流程

```
1. 放素材图  →  assets/kgos/益生菌.jpg  （每类1-3张，白底）
2. 先建黄金验证集 → docs/dataset-quality.md（真实 KGOS SKU 主图）
3. 生成/改造合成数据 → 必须贴近真实 SKU 主图分布
4. 文字/简称只纠正数量或确认已识别子类 →  模糊文字不得直接生成 ERP 子品
5. 异常 gating + OCR/LLM 视觉兜底 →  先处理 unresolved，再决定是否训练
6. 需要训练时  →  使用独立 run name 启动，避免覆盖旧 runs/kgos_yolov8s
7. 推理测试  →  python scripts/infer.py --brand kgos --image xxx.jpg --verbose
```

## 目录结构

```
assets/kgos/        ← 放单品素材图（每类1-3张，文件名=产品名）
assets/hee/         ← hee 品牌同上
datasets/kgos/      ← generate.py --profile train 自动生成，不要手动编辑
datasets/kgos_business_val/  ← generate.py --profile business-val 自动生成，用于业务验收
models/kgos_best.onnx  ← 训练完成后的最终模型
scripts/
  generate.py       ← 合成数据生成器
  train.py          ← 本机 CPU 训练（nice +10 低优先级）
  verify.py         ← 可视化验证标注是否正确
  infer.py          ← 生产推理模块
  nms_sweep.py      ← NMS/conf 扫描评估脚本
  ocr_verify.py     ← YOLO-first 文字纠正规则参考实现
  text50_eval.py    ← text50 exact-match / gating 评估
data/kgos_text_aliases.json  ← 可积累简称表；exact_aliases 可直映，ambiguous_groups 必须视觉确认
docs/dataset-quality.md  ← KGOS 数据集质量规范与训练门禁
docs/train7-evaluation-report.md  ← train7 真实业务图评估和下一步决策
docs/text50-evaluation-report.md  ← text50 初测结果与 gating 结论
```

## 命令速查

```bash
# 预览合成效果（生成10张，看素材去背景是否干净）
python scripts/generate.py --brand kgos --preview

# 生成正式训练数据（4000张，训练集3400+默认验证集600）
python scripts/generate.py --brand kgos --count 4000 --profile train

# 生成独立业务验收验证集（600张，全部写入 val）
python scripts/generate.py --brand kgos --count 600 --profile business-val

# 验证标注框是否准确（抽20张画框）
python scripts/verify.py --brand kgos --samples 20

# 验证业务验收集标注框
python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50

# 查看数据集质量规范和训练门禁
sed -n '1,220p' docs/dataset-quality.md

# 新启动 yolov8s 训练时必须使用独立 run name；不要直接覆盖 runs/kgos_yolov8s
# scripts/train.py 默认 name=kgos_yolov8s，会覆盖第 5 轮目录，除非明确要这么做。

# train7 微调入口（不要加 --export-production）
python -u scripts/train.py \
  --brand kgos --model yolov8s \
  --finetune runs/kgos_yolov8s_train6/weights/best.pt \
  --name kgos_yolov8s_train7 \
  --epochs 60

# 查看 train7 评估结论
sed -n '1,220p' docs/train7-evaluation-report.md

# NMS/conf 扫描报告
python scripts/nms_sweep.py

# 文字纠正规则与 text50 gating 评估
python scripts/ocr_verify.py
python scripts/text50_eval.py

# 推理测试
python scripts/infer.py --brand kgos --image /path/to/combo.jpg --verbose
```

## 注意事项

- 素材图文件名直接作为类别名，必须和 features.json 的 key 完全一致
- **生产门禁**：黄金验证集和三层管道评估通过前，不要覆盖 `models/kgos_best.onnx`
- **下一步顺序**：先把 text50 gating 升级为正式异常管道，再接真实 OCR/LLM 视觉兜底；不要先开新训练
- **简称规则**：`data/kgos_text_aliases.json` 要持续积累。`exact_aliases` 才能直映 ERP 标准名；`ambiguous_groups` 如“玉米片”“营养粉”“黑茶体验装”必须由 YOLO/LLM/人工视觉确认具体口味后才能落到 ERP 子品
- **文字口径**：文字描述是辅助纠错，不是事实来源。实际商品以识图结果为准；例如“玉米片 10”只有在视觉确认两种口味各 5 包时，才能拆成两个 ERP 标准名各 5
- **text50 数据**：`datasets/kgos_real_text50/ground_truth.json` 当前在被 `.gitignore` 忽略的 `datasets/` 下；若要长期版本化，应移动到 `docs/` 或调整 ignore 规则
- 训练需要 conda yolov8 环境（Python 3.10）
- 推理（infer.py）可在系统 Python 3.14 下运行，不需要 conda 环境
- yolov8n=快速验证(~8h)，yolov8s=生产精度(~18h)
- **日志输出**：必须用 `source conda.sh + conda activate + exec python -u`，conda run 会缓冲日志
- 生成器只使用白底真实素材，不使用 AI 生图；密排训练分布为 single/mixed_clean/mixed_occluded/row_layout/grid_layout/gift_package = 10%/15%/15%/20%/20%/20%
- `train.py --finetune` 会使用 `optimizer=AdamW` 固定微调学习率；默认不导出生产 ONNX，只有显式 `--export-production` 才覆盖
- 清理旧数据时保留 `datasets/kgos*`、`datasets/kgos_real_*`、`runs/kgos_yolov8s_train6/`、`runs/kgos_yolov8s_train7/` 和当前 `runs/kgos_train7.log`
