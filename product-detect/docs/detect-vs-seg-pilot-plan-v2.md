# KGOS Detect vs Seg Pilot — 完整执行计划 v2

> 版本：v2（Claude Code 修订）
> 状态：Codex 已审查；由 Claude Code 执行
> 执行方：Claude Code

## 目标

用 64 张图跑一次小规模对比实验，决定 KGOS 主图识别的训练路线：

- **候选 A**：YOLO Detection（矩形框），继续原来 train8 方向
- **候选 B**：YOLO Segmentation（实例分割轮廓），切换路线

实验完成后，选定的路线应用到完整 270 张图的标注和训练。

## 对比原则

> **标注工具已切换为 X-AnyLabeling（内置 SAM，本地单进程），不再用 Label Studio + 外挂 SAM backend。**
> 工具切换原因：Label Studio 的 interactive 转发链路在本机点击不出 mask（前端→LS→外挂 backend 多接点易断）。X-AnyLabeling 把 SAM 编进 GUI，无外挂链路。详见 `docs/annotation-tool-xanylabeling.md`。

两个模型使用**相同 64 张图**、**相同 train/val 分组**。

**标注策略（2026-06-15 修订，经用户决策）：每个商品只用 SAM 点出一遍多边形轮廓，不手标矩形。**

- 分割候选：直接用人工 SAM 多边形 mask。
- 检测候选：由脚本从每个多边形的**外接矩形**自动派生检测框，**不手标第二遍**。

修订理由（第一性原理）：原计划要求两种标注各自人工标一遍，理由是"对各自任务最优、对比公平"。但实测要求用户对 270 张每个商品标两遍，双倍工作量；而"外接矩形"本就是检测框的标准定义，派生框与手画框几乎无差别。省一半工作量 > 那一点理论公平性。用户已确认采用"只标一遍多边形"。

> 历史说明：v2 原文曾写"不从 mask 自动派生检测框、两种各自人工标"，已被本次修订取代。

---

## 第一步：确认 64 张 pilot 图集

全部来自 `datasets/kgos_real_all/images/`，图像已存在。

**Train split（50 张）**

| 类别 | 范围 | 数量 |
|------|------|------|
| gift | gift_001 ~ gift_010 | 10 |
| combo | combo_001 ~ combo_032 | 32 |
| main | main_001 ~ main_008 | 8 |

**Val split（14 张）**

| 类别 | 范围 | 数量 |
|------|------|------|
| gift | gift_011 ~ gift_013 | 3 |
| combo | combo_033 ~ combo_040 | 8 |
| main | main_009 ~ main_011 | 3 |

**注意**：28 类 ERP 标签在 50 张 train 图中不会全部覆盖，部分类别可能出现 0-1 次。这对路线选择是可接受的——本次 pilot 只验证"分割是否改善密排 gift/combo 场景计数"，不要求全类别覆盖。

---

## 第二步：标注（X-AnyLabeling）

工具已切换为 X-AnyLabeling，**不再用 Label Studio**。启动、模型加载、本机补丁、操作流程见 `docs/annotation-tool-xanylabeling.md`。

- conda 环境 `x-anylabeling`，模型 MobileSAM（权重已预置）
- 图集目录：`datasets/kgos_real_all/images/`，右下角文件列表直接切图
- 标签来源：`datasets/kgos_real_all/classes.txt`（28 类 ERP 标准名）

## 第三步：标注流程（每张图）

**每个商品只标一遍 SAM 多边形**（含盒子等规则形状也用多边形，不手画矩形）：

1. 选 MobileSAM 模型 → `pointQ` 在商品上点一下出轮廓
2. 多框了用 `pointE` 负点修正；满意按 `完成F` 选 ERP 标准标签
3. 标错标签：右键该轮廓 → 编辑标签（不要用「永久删除此标签文件」）
4. 每标完一张勾「已检查」当进度条；`Ctrl+S` 保存，生成图片同名 `.json`
5. 不标：活动文字、价格、"赠"字贴、背景图、包装印刷

检测框无需手标——由转换脚本从多边形外接矩形自动派生。

## 第四步：导出与数据集构建

X-AnyLabeling 标注产物是图片同目录的 `<name>.json`（多边形 points）。一条命令出两套：

```bash
python scripts/convert_xanylabeling.py \
  --images datasets/kgos_real_all/images \
  --classes datasets/kgos_real_all/classes.txt \
  --out-seg datasets/kgos_seg_pilot \
  --out-det datasets/kgos_detect_pilot \
  --val-ratio 0.2
```

- 分割数据集 `datasets/kgos_seg_pilot/`：YOLO-seg 多边形（给 yolov8n-seg）
- 检测数据集 `datasets/kgos_detect_pilot/`：YOLO-det 外接矩形（给 yolov8n，自动派生）
- 两个数据集各带 `data.yaml`，确定性 split（同名图永远落同一侧），未标注的图自动跳过

---
## 第五步：训练

Pilot 全程使用 yolov8n（不用 yolov8s）。

原因：50 张训练图的瓶颈是数据量而非模型容量，yolov8s 在此数据量下不会有实质性能提升，但 CPU 训练时间是 yolov8n 的 4-5 倍。路线选定后再用 yolov8s 训完整 270 张集。

**Smoke test（训练前先跑，验证脚本和数据集格式正确）**：

```bash
yolo detect train model=yolov8n.pt \
  data=datasets/kgos_detect_pilot/data.yaml \
  epochs=3 imgsz=640 batch=2 \
  project=runs name=kgos_detect_pilot_smoke

yolo segment train model=yolov8n-seg.pt \
  data=datasets/kgos_seg_pilot/data.yaml \
  epochs=3 imgsz=640 batch=2 \
  project=runs name=kgos_seg_pilot_smoke
```

**正式训练**：

```bash
# 检测候选
yolo detect train model=yolov8n.pt \
  data=datasets/kgos_detect_pilot/data.yaml \
  epochs=80 imgsz=1280 batch=4 \
  project=runs name=kgos_detect_pilot_yolov8n

# 分割候选
yolo segment train model=yolov8n-seg.pt \
  data=datasets/kgos_seg_pilot/data.yaml \
  epochs=80 imgsz=1280 batch=4 \
  project=runs name=kgos_seg_pilot_yolov8n_seg
```

**内存不足时**：先减 batch（batch=2），不减 imgsz。1280 对密排小商品很重要，不要轻易降。

---

## 第六步：评估

评估脚本：`scripts/evaluate_detect_vs_seg.py`

在 14 张 val 图上对两个模型各自推理，输出对比表：

| 模型 | box mAP50 | box mAP | seg mAP50 | seg mAP | 图片精确匹配 | gift 精确匹配 | combo 精确匹配 | 平均推理 ms |
|------|-----------|---------|-----------|---------|------------|--------------|---------------|------------|
| detect yolov8n | | | — | — | /14 | /3 | /8 | |
| seg yolov8n-seg | | | | | /14 | /3 | /8 | |

**图片精确匹配**的定义：该图所有 `recognition.items = [{name, qty}]` 完全正确（商品名 × 数量全对）。这是最终业务指标，mAP 只作参考。

---

## 第七步：路线决策标准

满足以下任一条，切换到分割路线：

1. 图片精确匹配：分割比检测多 ≥ 2 张（占 14 张 val 的 14pp）
2. gift/combo 子集精确匹配：分割比检测多 ≥ 2 张（共 11 张）
3. ERP item recall：分割比检测高 ≥ 10pp，且 precision 下降不超过 3pp

否则维持检测路线（简单、易导出、易维护）。

**Inconclusive 处理**：如果差距低于所有阈值但 val 结果接近（1 张之差），**不直接判断为检测胜出**。补标 20 张 combo/gift 图扩充 val 集后重新评估。

---

## 需要创建的文件

```
scripts/convert_xanylabeling.py     ← 已创建：X-AnyLabeling 标注 → YOLO seg+det 双数据集
scripts/evaluate_detect_vs_seg.py   ← 待创建：两模型对比评估
docs/detect-vs-seg-pilot-report.md  ← 待创建：评估结果（训练完后填写）
```

> 注：原计划列的 LS 导入/导出/RLE 转换脚本（prepare_seg_pilot_import、convert_labelstudio_*）已随工具切换作废，不再需要。convert_xanylabeling.py 一个脚本即覆盖 seg+det 双输出。