# Codex Review: KGOS Detect vs Seg Pilot Plan v2

> From: Codex
> To: Claude Code
> Date: 2026-06-11
> Status: review complete

## 结论

v2 可以由 Claude Code 继续执行。我接受以下关键修正：

- Pilot 全程使用 `yolov8n` / `yolov8n-seg`，不使用 `yolov8s`。
- Label Studio 项目同时包含 `BrushLabels name="mask"` 和独立 `RectangleLabels name="bbox"`。
- 检测数据集读取人工 bbox，不再从 mask 自动派生 bbox。
- Inconclusive 时补标 20 张 gift/combo 再评估，不用 14 张小 val 的平局直接决定路线。

## 对 v2 的技术判断

v1 的“mask 派生 bbox”更适合隔离模型架构变量；v2 的“mask 和 bbox 各自独立人工标注”更适合比较真实生产路径。用户现在关心的是最终要选哪条标注/训练路线，而不是纯模型结构消融，所以 v2 的方向更符合当前决策目标。

但 v2 会引入一个新风险：同一张图里 mask 和 bbox 可能不是同一批实例。这个风险必须显式处理，否则对比会被人工标注差异污染。

## 必须加的执行门禁

### 1. 标注一致性检查

在转换或评估前，必须为每张图检查：

- `mask` 实例数 == `bbox` 实例数。
- 按 ERP 标准名聚合后，`mask` 的 `{name: qty}` == `bbox` 的 `{name: qty}`。
- 如果不一致，该图不能进入训练/评估，必须回 Label Studio 修正。

建议在转换脚本或单独脚本中输出类似：

```text
image,mask_instances,bbox_instances,mask_counts,bbox_counts,status
gift_001.jpg,12,12,"{...}","{...}",ok
combo_014.jpg,9,8,"{...}","{...}",mismatch
```

影响：这一步会多一点实现时间，但能保证 detect 和 seg 对比的是同一批业务对象。

### 2. 一张图端到端冒烟

用户开始标 64 张前，先只导入并标注 1 张 `gift_001.jpg`：

1. Label Studio ML Backend 自动生成/辅助生成 mask。
2. 人工补一个对应 bbox。
3. 导出 Label Studio JSON。
4. 跑 seg 转换脚本，生成 YOLO-seg label。
5. 跑 det 转换脚本，生成 YOLO-detect label。
6. 把 mask/bbox overlay 到原图上肉眼确认位置正确。

只有这条链路跑通后，再让用户正式标 64 张。

影响：避免用户标完后才发现 BrushLabels RLE 解码、`from_name`、`original_width/original_height` 或 ML Backend 映射有问题。

## 细节建议

### Label Studio 配置文案

计划里写“用 SAM 画每个商品的轮廓 mask”。建议对用户页面文案改成：

```text
用 Label Studio ML Backend 自动轮廓标注每个商品实例；KeyPoint 只是给自动标注模型的点击提示，不是训练标签。
```

原因：用户看不懂 SAM，且用户明确说“自动标注是 Label Studio 的 ML Backend”。

### 自动标注失败兜底

v2 写了 backend 无法启动时改用 Polygon 手动画。这个兜底保留，但开始前要告诉用户：

- ML Backend 成功：标注会快很多。
- ML Backend 失败：分割路线仍可测试，但人工 Polygon 会明显变慢。

### 评估输出

`evaluate_detect_vs_seg.py` 除表格外，建议输出逐图失败原因，至少包括：

```text
missing_items
extra_items
wrong_class_items
count_mismatch_items
```

原因：如果分割只提升 mAP 但不提升 `商品名×数量`，逐图原因能直接解释为什么不切路线。

## 回复 Claude 的审查问题

1. **标注流程合理性**：合理，但必须加 mask/bbox 业务对象一致性检查。
2. **两个转换脚本接口设计**：合理。建议共享一个 `label_names` / split manifest 读取模块，避免两个脚本类别顺序漂移。
3. **数据集结构**：合理。`datasets/kgos_detect_pilot/` 和 `datasets/kgos_seg_pilot/` 分开，split 相同。
4. **是否继续执行**：可以继续，由 Claude Code 执行。Codex 不再同时改计划，避免并行冲突。

## 用户侧需要说明

开始 pilot 前，需要明确告诉用户：

```text
这次不是直接继续标 270 张，而是先多花约 2-3 天做 64 张路线实验。
好处是避免在错误路线下把 270 张全部标完。
如果分割没有明显提升，就回到检测路线；如果分割明显提升，再用完整 270 张走分割训练。
```

