# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。最终验收输出必须对齐 product-mapping：`recognition.items = [{ name: ERP标准商品名, qty }]`。

## 当前状态

- Phase: 3-C（**Detect-vs-Seg pilot 路线选择**）
- **路线调整（2026-06-11）**：合成训练集分布与真实 SKU 主图差距过大；train7 在 gift13 上 recall=61.11%，未达生产门槛。当前先用 64 张真实图对比 YOLO Detection 与 YOLO Segmentation，再决定完整 270 张走哪条标注/训练路线。
- **Pilot 计划**：
  - 计划文件：`docs/detect-vs-seg-pilot-plan-v2.md`
  - 执行方：Claude Code；Codex 已回复审查材料 `../docs/codex-handoff/product-detect-detect-vs-seg-pilot-plan-v2-codex-review.md`
  - 图集：gift_001~013、combo_001~040、main_001~011
  - 模型：`yolov8n.pt` vs `yolov8n-seg.pt`，路线选定后完整集再上 yolov8s / yolov8s-seg
  - 标注：同一 Label Studio 项目内同时做 `BrushLabels name="mask"` 与 `RectangleLabels name="bbox"`；ML Backend 自动轮廓标注只辅助 mask
  - 门禁：先用 `gift_001.jpg` 跑通 ML Backend 到导出转换的一图端到端冒烟；每张图 mask/bbox 按 ERP 名聚合数量必须一致
- **270 张真实图状态**：
  - 270 张真实图已复制至 `datasets/kgos_real_all/images/`（main_001~183、combo_001~074、gift_001~013）
  - Label Studio 在 localhost:8080，项目 3（KGOS Train8），270 个任务，pre-annotations 已加载
  - 当前进度（2026-06-11）：约 3/270 已完成
  - 28 类（随机杯子移除），标签必须是 ERP 标准名（见 `datasets/kgos_real_all/label_studio_config.xml`）
  - 标注指南：`datasets/kgos_real_all/标注操作指南.md`
- **train8 / 完整集训练**：等 pilot 选定路线后再推进；不要在路线未定前继续按旧检测框路线标满 270 张
- **train7（最新完成训练）**：gift13 ERP 口径 recall=61.11%，exact=3/13，未达生产门槛
- **文字结合验证（暂缓）**：text50 gated 91.7%，等 train8 结果再决定是否继续三层管道
  - 相关工具仍保留：`scripts/ocr_verify.py`、`scripts/text50_eval.py`、`data/kgos_text_aliases.json`
- **真实 KGOS SKU 主图源**：微信文件目录 `.../2026-05/1主图汇总`，270 张，只读参考
- hee 未开始

## ENTRY MAP

| 任务 | 入口 |
|------|------|
| **标注操作指南** | `datasets/kgos_real_all/标注操作指南.md` |
| **Label Studio**（标注工具） | http://localhost:8080（需先 `label-studio start`） |
| Detect-vs-Seg pilot 计划 | `docs/detect-vs-seg-pilot-plan-v2.md` |
| Codex 对 v2 的审查回复 | `../docs/codex-handoff/product-detect-detect-vs-seg-pilot-plan-v2-codex-review.md` |
| 数据集质量规范 | `docs/dataset-quality.md` |
| 查看进度 | `tasks/todo.md` |
| 生成训练数据（合成） | `python scripts/generate.py --brand kgos --count 4000 --profile train` |
| 生成业务验收验证集（合成） | `python scripts/generate.py --brand kgos --count 600 --profile business-val` |
| NMS/conf 扫描 | `python scripts/nms_sweep.py` |
| YOLO-first 文字纠正（暂缓） | `python scripts/ocr_verify.py` |
| text50 gating 评估（暂缓） | `python scripts/text50_eval.py` |
| KGOS 简称/模糊组表 | `data/kgos_text_aliases.json` |
| train7 评估报告 | `docs/train7-evaluation-report.md` |
| 推理测试 | `python scripts/infer.py --brand kgos --image xxx.jpg` |
| 回归测试 | `python3 -m unittest tests.test_train tests.test_generate tests.test_verify tests.test_nms_sweep -v` |

## PATHS

```
assets/
  kgos/          ← 单品素材图（文件名=ERP产品名，与 features.json key 一致）
  hee/           ← hee 品牌素材图
datasets/
  kgos_real_all/         ← 270张真实 SKU 主图 + Label Studio 标注工程
    images/              ← 270张图（main_001~183, combo_001~074, gift_001~013）
    labels_pretrain/     ← train7 预标注（conf=0.35, iou=0.45），标注前参考
    label_studio_config.xml  ← 28类 ERP 标准名 Label Studio 配置
    label_studio_import.json ← 270个任务导入文件（已导入，无需重复）
    标注操作指南.md          ← Label Studio 操作步骤与标注规则
  kgos_seg_pilot/        ← pilot 分割数据集（计划创建）
  kgos_detect_pilot/     ← pilot 检测数据集（计划创建）
  kgos/          ← generate.py --profile train 合成集（暂缓使用）
  kgos_business_val/ ← 合成业务验收验证集（暂缓使用）
  hee/           ← 同上
models/
  kgos_best.onnx ← 训练完成后的生产模型（未更新，等 train8 通过门禁）
  hee_best.onnx
scripts/
  generate.py    ← 合成数据生成器（暂缓）
  train.py       ← CPU 训练脚本；--finetune 微调；--export-production 才覆盖生产 ONNX
  verify.py      ← 标注可视化验证
  infer.py       ← 生产推理（ProductDetector 类）
  nms_sweep.py   ← NMS/conf 扫描
  ocr_verify.py  ← YOLO-first 文字纠正规则参考实现（暂缓）
  text50_eval.py ← text50 exact-match / gating 评估（暂缓）
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
2. 读 `docs/detect-vs-seg-pilot-plan-v2.md` 和 `../docs/codex-handoff/product-detect-detect-vs-seg-pilot-plan-v2-codex-review.md`
3. 当前主线由 Claude Code 执行 pilot；Codex 不要并行改计划或启动训练，除非用户明确转交
4. 若继续标注，先确认 `gift_001.jpg` 一图端到端冒烟已通过

## 生成规则

- 背景固定纯白，不再生成噪声背景。
- 训练集按 `single` / `mixed_clean` / `mixed_occluded` / `row_layout` / `grid_layout` / `gift_package` 生成，比例 10% / 15% / 15% / 20% / 20% / 20%。
- 遮挡样本按最终可见 alpha mask 计算 bbox；可见面积低于原始面积 35% 的目标不写 label。
- 密排场景加入可控前后遮挡和高斯投影阴影，目标是贴近真实 SKU 主图的规则矩阵、重复排列、买赠组合。
- `business-val` 独立写入 `datasets/<brand>_business_val/`，不做亮度/对比度增强，用于业务验收。
