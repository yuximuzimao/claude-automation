# product-detect — YOLOv8 商品识别

项目中文名：商品识别训练

替代 product-mapping 中的 LLM 识图，本地推理，零 token 消耗。

路线调整（2026-06-11）：合成训练集与真实主图分布差距过大，`train7` 在 gift13 上 recall=61.11%，未达生产门槛。当前不要直接把 270 张全部按检测框路线标完；先由 Claude Code 执行 `docs/detect-vs-seg-pilot-plan-v2.md`，用 64 张真实图对比 YOLO Detection 与 YOLO Segmentation 路线。文字结合验证（三层管道计划）暂缓，等视觉基础路线选定后再决定是否继续。最终验收输出必须对齐 product-mapping 的 `recognition.items = [{ name: ERP标准商品名, qty }]`，标准名来自 `product-mapping/data/products/kgos/features.json` 的 `erpName`。

## 工作流程（当前阶段：Detect-vs-Seg pilot）

```
1. Claude Code 执行 pilot 计划 → docs/detect-vs-seg-pilot-plan-v2.md
   64 张图：gift_001~013、combo_001~040、main_001~011
   目标：判断检测框路线还是实例分割路线更适合密排计数

2. Label Studio 新建 pilot 项目 → KGOS Detect-vs-Seg Pilot
   同一批图分别标 BrushLabels mask 与 RectangleLabels bbox
   ML Backend 自动轮廓标注只辅助 mask，bbox 独立人工标
   SAM backend 运行手册 → docs/sam-auto-detect-runbook.md

3. 转换并训练两个 yolov8n pilot
   datasets/kgos_seg_pilot/ → yolo segment train model=yolov8n-seg.pt
   datasets/kgos_detect_pilot/ → yolo detect train model=yolov8n.pt

4. 按业务指标评估
   图片级 exact、ERP item recall/precision、gift/combo 子集表现

5. 路线选定后再推进完整 270 张
   检测胜出 → 继续 YOLO with Images / train8
   分割胜出 → 完整 270 张改走 YOLO-seg

6. 推理测试  →  python scripts/infer.py --brand kgos --image xxx.jpg --verbose
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
docs/detect-vs-seg-pilot-plan-v2.md  ← 64 张真实图检测/分割路线对比计划（Claude Code 执行）
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

# SAM 自动轮廓 backend（launchd 正常时无需手动启动）
curl --noproxy '*' http://localhost:9090/health
bash start-sam-backend.sh
```

## 注意事项

- 素材图文件名直接作为类别名，必须和 features.json 的 key 完全一致
- **生产门禁**：黄金验证集和三层管道评估通过前，不要覆盖 `models/kgos_best.onnx`
- **下一步顺序**：先完成 detect-vs-seg pilot；不要在路线未定前让用户把 270 张都按旧检测框路线标完
- **Pilot 门禁**：用户正式标 64 张前，先用 `gift_001.jpg` 跑通 ML Backend → mask/bbox 标注 → JSON 导出 → YOLO-seg/detect 转换 → overlay 肉眼确认；每张图的 mask 与 bbox 按 ERP 名聚合数量必须一致。2026-06-13 已完成 backend 级 `/setup` + `/predict` smoke，剩余 UI 保存/导出/转换/overlay 门禁仍要做
- **SAM Auto-Detect**：Label Studio 项目 4 的 `http://localhost:9090` backend 必须 `is_interactive=1`；本机 launchd 服务为 `com.chat.product-detect-sam-backend`，日志 `/tmp/sam_backend.log`
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
