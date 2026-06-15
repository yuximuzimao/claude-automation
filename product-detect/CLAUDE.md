# product-detect — YOLOv8 商品识别

项目中文名：商品识别训练

替代 product-mapping 中的 LLM 识图，本地推理，零 token 消耗。

路线调整（2026-06-11）：合成训练集与真实主图分布差距过大，`train7` 在 gift13 上 recall=61.11%，未达生产门槛，转为标注真实图。最终验收输出必须对齐 product-mapping 的 `recognition.items = [{ name: ERP标准商品名, qty }]`，标准名来自 `product-mapping/data/products/kgos/features.json` 的 `erpName`。

标注工具切换（2026-06-15）：弃用 Label Studio + 外挂 SAM backend（本机 interactive 链路点击不出 mask），改用 **X-AnyLabeling**（内置 SAM、本地单进程、中文界面）。完整手册见 `docs/annotation-tool-xanylabeling.md`。标注策略经用户决策：每个商品只用 SAM 点一遍多边形，检测框由 `scripts/convert_xanylabeling.py` 自动派生外接矩形，不手标第二遍。270 张决定全量标，不去重。

## 工作流程（当前阶段：标注 270 张真实图 → Detect-vs-Seg pilot）

```
1. 标注真实图 → X-AnyLabeling（conda x-anylabeling 环境）
   目录 datasets/kgos_real_all/images/，每商品 SAM 点多边形，存图片同名 .json
   启动/补丁/流程见 docs/annotation-tool-xanylabeling.md

2. 标注 → YOLO 双数据集（一份多边形出两套）
   python scripts/convert_xanylabeling.py --images datasets/kgos_real_all/images \
     --classes datasets/kgos_real_all/classes.txt \
     --out-seg datasets/kgos_seg_pilot --out-det datasets/kgos_detect_pilot

3. 训练两个 yolov8n pilot
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
  convert_xanylabeling.py ← X-AnyLabeling 标注 → YOLO seg+det 双数据集
  dedup_images.py   ← 新图去重（双哈希+彩色MAE）
  sam_smoke_xanylabeling.py ← SAM 引擎冒烟
data/kgos_text_aliases.json  ← 可积累简称表；exact_aliases 可直映，ambiguous_groups 必须视觉确认
docs/annotation-tool-xanylabeling.md  ← X-AnyLabeling 标注工具手册（启动/补丁/流程/转换）
docs/dataset-quality.md  ← KGOS 数据集质量规范与训练门禁
docs/detect-vs-seg-pilot-plan-v2.md  ← 检测/分割路线对比计划
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

# 启动 X-AnyLabeling 标注 GUI（详见 docs/annotation-tool-xanylabeling.md）
conda activate x-anylabeling && xanylabeling \
  --filename "$PWD/datasets/kgos_real_all/images/gift_001.jpg" \
  --labels "$PWD/datasets/kgos_real_all/classes.txt"
```

## 注意事项

- 素材图文件名直接作为类别名，必须和 features.json 的 key 完全一致
- **生产门禁**：黄金验证集和三层管道评估通过前，不要覆盖 `models/kgos_best.onnx`
- **下一步顺序**：先完成 detect-vs-seg pilot；不要在路线未定前让用户把 270 张都按旧检测框路线标完
- **标注工具**：X-AnyLabeling（conda `x-anylabeling` 环境），内置 SAM，本机已打 3 个崩溃补丁（CoreML→CPU、numpy 2.x 叉积、删除空值保护），重装会覆盖补丁需重打。详见 `docs/annotation-tool-xanylabeling.md`。
- **一图端到端冒烟**：gift_001 已通过（SAM 出 mask → 标注 → 存 json → `convert_xanylabeling.py` 转 seg/det → overlay 确认）。
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
