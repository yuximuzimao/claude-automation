# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。最终验收输出必须对齐 product-mapping：`recognition.items = [{ name: ERP标准商品名, qty }]`。

## 当前状态

- Phase: 3-C（**Detect-vs-Seg pilot 路线选择**；标注工具已切换 X-AnyLabeling）
- **路线调整（2026-06-11）**：合成训练集分布与真实 SKU 主图差距过大；train7 在 gift13 上 recall=61.11%，未达生产门槛。改用真实图对比 YOLO Detection 与 YOLO Segmentation 路线。
- **标注工具切换（2026-06-15）**：弃用 Label Studio + 外挂 SAM backend（interactive 链路在本机点击不出 mask），改用 **X-AnyLabeling**（内置 SAM、本地单进程、中文界面）。完整使用手册见 `docs/annotation-tool-xanylabeling.md`。
- **标注策略（2026-06-15 用户决策）**：每个商品只用 SAM 点一遍多边形，**不手标矩形**；检测框由 `scripts/convert_xanylabeling.py` 从多边形外接矩形自动派生。一份标注出 seg + det 两套数据集。
- **Pilot 计划**：
  - 计划文件：`docs/detect-vs-seg-pilot-plan-v2.md`（2026-06-15 已按"只标一遍多边形"修订）
  - 模型：`yolov8n.pt` vs `yolov8n-seg.pt`，路线选定后完整集再上 yolov8s / yolov8s-seg
  - 一图端到端冒烟（gift_001）：✅ 已通过（SAM 出 mask + 人工标 + Ctrl+S 存 json + 转换脚本生成 seg/det + overlay 确认）
- **270 张真实图状态**：
  - 270 张真实图位于 `datasets/kgos_real_all/images/`（main_001~183、combo_001~074、gift_001~013）
  - 标注工具：X-AnyLabeling（启动见 runbook），右下角文件列表直接切图
  - 当前进度（2026-06-15）：1/270（gift_001 已标，决定全量标 270 张，不去重）
  - 28 类，标签必须是 ERP 标准名（见 `datasets/kgos_real_all/classes.txt`）
  - 标注产物：图片同目录 `<name>.json`（X-AnyLabeling 多边形格式）
- **train8 / 完整集训练**：等 270 张标完 + pilot 选定路线后推进
- **train7（最新完成训练）**：gift13 ERP 口径 recall=61.11%，exact=3/13，未达生产门槛
- **文字结合验证（暂缓）**：text50 gated 91.7%，等 train8 结果再决定是否继续三层管道
  - 相关工具仍保留：`scripts/ocr_verify.py`、`scripts/text50_eval.py`、`data/kgos_text_aliases.json`
- **真实 KGOS SKU 主图源**：微信文件目录 `.../2026-05/1主图汇总`，270 张，只读参考
- hee 尚未训练；已知待图新品以 `../product-mapping/data/products/hee/pending-products.json` 为准，不能当作未知类别或借旧图建类

## ENTRY MAP

| 任务 | 入口 |
|------|------|
| **标注工具 X-AnyLabeling**（含启动/补丁/流程） | `docs/annotation-tool-xanylabeling.md` |
| 启动标注 GUI | 当前批量标注默认传图片目录：`conda activate x-anylabeling` 后 `xanylabeling --filename "$PWD/datasets/kgos_real_all/images" --labels "$PWD/datasets/kgos_real_all/classes.txt"`；单图只用于临时冒烟/查看，文件列表为空，不作为 270 张标注入口 |
| 标注→YOLO 双数据集转换 | `python scripts/convert_xanylabeling.py --images datasets/kgos_real_all/images --classes datasets/kgos_real_all/classes.txt --out-seg datasets/kgos_seg_pilot --out-det datasets/kgos_detect_pilot` |
| 新图去重 | `python scripts/dedup_images.py --new <新图> --against datasets/kgos_real_all/images` |
| Detect-vs-Seg pilot 计划 | `docs/detect-vs-seg-pilot-plan-v2.md` |
| 数据集质量规范 | `docs/dataset-quality.md` |
| 查看进度 | `tasks/todo.md` |
| 生成训练数据（合成） | `python scripts/generate.py --brand kgos --count 4000 --profile train` |
| 生成业务验收验证集（合成） | `python scripts/generate.py --brand kgos --count 600 --profile business-val` |
| NMS/conf 扫描 | `python scripts/nms_sweep.py` |
| YOLO-first 文字纠正（暂缓） | `python scripts/ocr_verify.py` |
| text50 gating 评估（暂缓） | `python scripts/text50_eval.py` |
| KGOS 简称/模糊组表 | `data/kgos_text_aliases.json` |
| HEE 已知待图新品 | `../product-mapping/data/products/hee/pending-products.json` |
| train7 评估报告 | `docs/train7-evaluation-report.md` |
| 推理测试 | `python scripts/infer.py --brand kgos --image xxx.jpg` |
| 回归测试 | `python3 -m unittest tests.test_train tests.test_generate tests.test_verify tests.test_nms_sweep -v` |

## PATHS

```
assets/
  kgos/          ← 单品素材图（文件名=ERP产品名，与 features.json key 一致）
  hee/           ← hee 品牌素材图
datasets/
  kgos_real_all/         ← 270张真实 SKU 主图 + X-AnyLabeling 当前标注工作区
    images/              ← 270张图（main_001~183, combo_001~074, gift_001~013）+ 同名 .json 标注输出
    labels_pretrain/     ← train7 预标注（conf=0.35, iou=0.45），标注前参考
    classes.txt          ← 28类 ERP 标准名，X-AnyLabeling 当前标签来源
    label_studio_config.xml  ← Label Studio 旧方案遗留配置，仅作历史参考，不作为当前入口
    label_studio_import.json ← Label Studio 旧方案遗留导入文件，不再重复导入
    标注操作指南.md          ← Label Studio 旧方案操作说明，当前以 docs/annotation-tool-xanylabeling.md 为准
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
../product-mapping/data/products/hee/pending-products.json ← HEE 跨项目待补商品真值
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
2. 读 `docs/detect-vs-seg-pilot-plan-v2.md`
3. 若处理标注 / SAM 出图问题，先读 `docs/annotation-tool-xanylabeling.md`（含 3 个已打的本机崩溃补丁说明），不要只从界面图标判断链路是否可用
4. 当前主线由 Claude Code 执行 pilot；Codex 不要并行改计划或启动训练，除非用户明确转交
5. 若继续标注，先确认 `gift_001.jpg` 一图端到端冒烟已通过
6. 若任务涉及 HEE/悦希，先读 `../product-mapping/data/products/hee/pending-products.json`；待图商品只能标记为已知待补，不能生成训练类别

## 生成规则

- 背景固定纯白，不再生成噪声背景。
- 训练集按 `single` / `mixed_clean` / `mixed_occluded` / `row_layout` / `grid_layout` / `gift_package` 生成，比例 10% / 15% / 15% / 20% / 20% / 20%。
- 遮挡样本按最终可见 alpha mask 计算 bbox；可见面积低于原始面积 35% 的目标不写 label。
- 密排场景加入可控前后遮挡和高斯投影阴影，目标是贴近真实 SKU 主图的规则矩阵、重复排列、买赠组合。
- `business-val` 独立写入 `datasets/<brand>_business_val/`，不做亮度/对比度增强，用于业务验收。
