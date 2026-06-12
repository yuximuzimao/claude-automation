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

两个模型使用**相同 64 张图**、**相同 train/val 分组**、**各自独立人工标注**。

- 检测候选：人工画矩形框（RectangleLabels）
- 分割候选：Label Studio ML Backend 自动轮廓标注辅助生成 mask（BrushLabels）

不从 mask 自动派生检测框——两种标注类型各自由人工完成，确保每个模型的训练数据都是为其任务类型优化的标注，对比才公平。

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

## 第二步：Label Studio 项目配置

新建 Label Studio 项目，**不修改现有项目 3（KGOS Train8）**。

**项目名**：`KGOS Detect-vs-Seg Pilot`

**配置文件路径**：
```
datasets/kgos_real_all/label_studio_seg_pilot_config.xml
```

**配置内容**：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>

  <Header value="标注说明：① 用 Label Studio ML Backend 自动轮廓标注辅助生成每个商品的 mask（BrushLabels）② 再为同一批商品手动画矩形框（RectangleLabels bbox）③ KeyPoint 仅作自动轮廓提示用，不是训练标签"/>

  <!-- 分割训练标签（ML Backend 自动轮廓标注辅助） -->
  <BrushLabels name="mask" toName="image" showInline="true">
    <Label value="KGOS 三围尺 150cm"/>
    <Label value="KGOS加维诺维生素C泡腾片（甜橙味）4g*20"/>
    <Label value="KGOS手提保温壶"/>
    <Label value="KGOS新年礼袋"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（青柑普洱味）21g（1g*21）"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（青柑普洱味）试用装 5g（1g*5）"/>
    <Label value="KGOS玉米浓汤味玉米片 30g"/>
    <Label value="KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12"/>
    <Label value="KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*3 体验装"/>
    <Label value="KGOS益生菌固体饮料 2g*15"/>
    <Label value="KGOS绿色圆手柄锤纹杯"/>
    <Label value="KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*12"/>
    <Label value="KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*3 三袋体验装"/>
    <Label value="KGOS蛋白多肽营养强化粉（莓果味） 30g*12"/>
    <Label value="KGOS蛋白多肽营养强化粉（莓果味） 30g*3 三袋体验装"/>
    <Label value="KGOS逐光冰霸杯 900ml"/>
    <Label value="KGOS饮料袋 10个/袋"/>
    <Label value="KGOS香菜牛肉味玉米片 30g"/>
    <Label value="KGO复合多种压片糖果2.0"/>
    <Label value="KGO夏季随行咖啡杯"/>
    <Label value="KGO手提袋"/>
    <Label value="KGO摇摇杯 500ML"/>
    <Label value="kgos帆布袋"/>
    <Label value="甘油二酯咖啡固体饮料（生椰拿铁味） 8g*12 新包装"/>
    <Label value="诺丽果红树莓益生元饮 50ml*10袋/盒"/>
    <Label value="诺丽果红树莓益生元饮 50ml*3袋/盒 体验装"/>
  </BrushLabels>

  <!-- 检测训练标签（人工画框，不是自动轮廓提示） -->
  <RectangleLabels name="bbox" toName="image" showInline="true">
    <Label value="KGOS 三围尺 150cm"/>
    <Label value="KGOS加维诺维生素C泡腾片（甜橙味）4g*20"/>
    <Label value="KGOS手提保温壶"/>
    <Label value="KGOS新年礼袋"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（青柑普洱味）21g（1g*21）"/>
    <Label value="KGOS灵芝金花黑茶固体饮料（青柑普洱味）试用装 5g（1g*5）"/>
    <Label value="KGOS玉米浓汤味玉米片 30g"/>
    <Label value="KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12"/>
    <Label value="KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*3 体验装"/>
    <Label value="KGOS益生菌固体饮料 2g*15"/>
    <Label value="KGOS绿色圆手柄锤纹杯"/>
    <Label value="KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*12"/>
    <Label value="KGOS蛋白多肽营养强化粉（牛油果猕猴桃味） 30g*3 三袋体验装"/>
    <Label value="KGOS蛋白多肽营养强化粉（莓果味） 30g*12"/>
    <Label value="KGOS蛋白多肽营养强化粉（莓果味） 30g*3 三袋体验装"/>
    <Label value="KGOS逐光冰霸杯 900ml"/>
    <Label value="KGOS饮料袋 10个/袋"/>
    <Label value="KGOS香菜牛肉味玉米片 30g"/>
    <Label value="KGO复合多种压片糖果2.0"/>
    <Label value="KGO夏季随行咖啡杯"/>
    <Label value="KGO手提袋"/>
    <Label value="KGO摇摇杯 500ML"/>
    <Label value="kgos帆布袋"/>
    <Label value="甘油二酯咖啡固体饮料（生椰拿铁味） 8g*12 新包装"/>
    <Label value="诺丽果红树莓益生元饮 50ml*10袋/盒"/>
    <Label value="诺丽果红树莓益生元饮 50ml*3袋/盒 体验装"/>
  </RectangleLabels>

  <!-- ML Backend 点击提示（仅辅助生成 mask，不作为训练标签） -->
  <KeyPointLabels name="prompt_point" toName="image" smart="true" showInline="true">
    <Label value="object"/>
  </KeyPointLabels>

</View>
```

**ML Backend 配置**：
- URL：`http://localhost:9090`
- 验证：`curl http://localhost:9090` → 返回 `{"status":"UP"}`
- 开启 interactive preannotations（对应 BrushLabels + KeyPoint）
- auto-accept 保持关闭，每个 mask 人工确认后再保存

如果 ML Backend 或其自动轮廓模型无法启动：**不要放弃 pilot**，改用 Label Studio 内置 Polygon 工具手动画多边形轮廓。矩形框始终手动画。

---

## 第三步：标注流程（每张图）

每张图做两种标注，顺序不强制但建议先 mask 再 bbox：

**Mask 标注（BrushLabels）**：
1. 对每个真实商品实例，用 Label Studio ML Backend + KeyPoint 提示生成轮廓 mask
2. 确认 mask 未合并相邻同类商品（密排商品必须各自独立 mask）
3. 不需要完美边缘，能区分相邻实例即可
4. 不标：活动文字、价格、"赠"字贴、背景图、包装印刷

**Bbox 标注（RectangleLabels）**：
1. 为同一批商品实例手动画矩形框
2. 框的边界与 mask 大致对齐，可以稍留一点空白
3. 与 mask 标注的实例数量必须一致（同一张图，两种标注的 instance 总数要相同）

**一致性门禁**：
1. 转换或训练前必须检查每张图的 `mask` 实例数与 `bbox` 实例数一致
2. 按 ERP 标准名聚合后，`mask` 的 `{name: qty}` 必须与 `bbox` 的 `{name: qty}` 一致
3. 不一致的图片不能进入训练或评估，必须回 Label Studio 修正

**一图端到端冒烟**：
正式标 64 张前，先只用 `gift_001.jpg` 跑通：ML Backend 自动轮廓 → 人工 bbox → JSON 导出 → YOLO-seg / YOLO-detect 转换 → overlay 肉眼确认。

---

## 第四步：导出与数据集构建

导出时从同一个 Label Studio 项目导出两次：

### 分割数据集（供 yolov8n-seg 训练）

导出格式：JSON（Label Studio 原生格式）
转换脚本：`scripts/convert_labelstudio_seg_export.py`
输出目录：`datasets/kgos_seg_pilot/`

**BrushLabels RLE 解码方式（高风险，必须先验证）**：

```python
# 优先用官方库
from label_studio_converter.brush import decode_rle

# 或手动解码（Label Studio 专用格式，非标准 COCO RLE）
import base64, numpy as np

def decode_ls_brush_rle(rle_str, original_height, original_width):
    # original_height/width 从 LS JSON 的 original_height/original_width 字段读取
    # 不要用图像文件实际尺寸（有时不一致）
    rle_bytes = base64.b64decode(rle_str)
    mask = np.frombuffer(rle_bytes, dtype=np.uint8).reshape(original_height, original_width)
    return mask  # binary mask，再用 cv2.findContours 转多边形
```

转换后验证：**将解码的 mask 叠到原图上肉眼确认位置和形状正确，再接入训练**。

输出 YOLO seg label 格式（每行一个实例）：
```
class_id x1 y1 x2 y2 x3 y3 ...  # 归一化坐标 [0,1]
```

### 检测数据集（供 yolov8n 训练）

导出格式：JSON（Label Studio 原生格式）
转换脚本：`scripts/convert_labelstudio_det_export.py`
输出目录：`datasets/kgos_detect_pilot/`

读取 `RectangleLabels name="bbox"` 的标注（不读 prompt_point）。

输出 YOLO detect label 格式（每行一个实例）：
```
class_id x_center y_center width height  # 归一化坐标 [0,1]
```

### data.yaml（两个数据集各一份）

```yaml
# datasets/kgos_seg_pilot/data.yaml
path: /Users/chat/claude/product-detect/datasets/kgos_seg_pilot
train: images/train
val: images/val
nc: 28
names: [...]  # 28 个 ERP 标准名，顺序与 label_studio_config.xml 一致
```

两个数据集共用同一套图像文件（软链接或复制均可），split 相同。

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
scripts/prepare_seg_pilot_import.py          ← 生成 64 张图的 LS 导入 JSON
scripts/convert_labelstudio_seg_export.py    ← LS 导出 → YOLO seg 格式（含 RLE 解码）
scripts/convert_labelstudio_det_export.py    ← LS 导出 → YOLO detect 格式（读 bbox 标签）
scripts/evaluate_detect_vs_seg.py            ← 两模型对比评估
tests/test_convert_labelstudio_seg_export.py ← RLE 解码回归测试
tests/test_convert_labelstudio_det_export.py ← bbox 转换回归测试
datasets/kgos_real_all/label_studio_seg_pilot_config.xml  ← Label Studio 配置
docs/detect-vs-seg-pilot-report.md           ← 评估结果（训练完后填写）
```

如需修改：
```
CLAUDE.md    ← 更新当前阶段描述
SKILL.md     ← 更新 PATHS / ENTRY MAP
tasks/todo.md
```

---

## 相对于 Codex v1 的变更点

| 项目 | Codex v1 | 本计划 v2 |
|------|----------|-----------|
| 检测训练标签来源 | 从 mask 自动派生 bbox | 人工独立标注 RectangleLabels |
| Label Studio 配置 | `prompt_box` 兼作自动轮廓提示和框标签 | 新增独立 `RectangleLabels name="bbox"` |
| 检测数据集名 | kgos_detect_from_seg_pilot | kgos_detect_pilot |
| 转换脚本 | 1 个（seg+派生detect） | 2 个独立脚本 |
| 模型规格 | yolov8s | yolov8n |
| Inconclusive 处理 | 未明确 | 补标 20 张再评估 |
