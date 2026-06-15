# X-AnyLabeling 标注工具 Runbook

> 2026-06-15 标注工具从 Label Studio + 外挂 SAM backend 切换为 **X-AnyLabeling**（内置 SAM，本地单进程）。
> 旧方案废弃原因：Label Studio 的 interactive 转发链路（前端→LS→外挂 9090 backend）在本机点击不出 mask，多接点易断。X-AnyLabeling 把 SAM 编进 GUI，无外挂链路。

## 运行环境

- conda 环境：`x-anylabeling`（Python 3.12，独立于训练用的 `yolov8` 环境）
- 包：`x-anylabeling-cvhub==4.0.0b7`（PyQt6）
- 模型缓存：`~/xanylabeling_data/models/mobile_sam_vit_h-r20230810/`（encoder 27M + decoder 16M，已预置）
- 界面语言：简体中文（`~/.xanylabelingrc` 里 `language: zh_CN`）

## 启动

```bash
source ~/miniconda3/etc/profile.d/conda.sh && conda activate x-anylabeling
cd ~/claude/product-detect
xanylabeling \
  --filename "$PWD/datasets/kgos_real_all/images/gift_001.jpg" \
  --labels "$PWD/datasets/kgos_real_all/classes.txt"
```

传 images 目录里任一张图，GUI 右下角文件列表会列出同目录全部 270 张，可直接点选切图。

## 本机已知坑与已打的补丁（重要）

X-AnyLabeling 4.0 beta + numpy 2.x 在本机有 3 个崩溃点，已在包源码里打补丁（均备份 `.bak`）：

| 文件 | 问题 | 补丁 |
|------|------|------|
| `services/auto_labeling/sam_onnx.py` | CoreML EP 跑不动 MobileSAM encoder（error -1），点击不出轮廓 | `providers` 强制 `["CPUExecutionProvider"]`（CPU 下 encode 0.5s、decode ~40ms，准确） |
| `views/labeling/utils/qt.py` | numpy 2.x 删了 2D `np.cross`，鼠标在画布移动即崩 | 改用标量叉积公式 |
| `views/labeling/label_widget.py` | 删标签文件后 `currentItem()` 为 None 崩溃 | 加空值保护 |

> 若重装 X-AnyLabeling，这 3 个补丁会被覆盖，需重打。

## 标注流程（每个商品只标一遍多边形）

1. 左侧 AI/机器人图标 → 顶部模型下拉选 **MobileSAM (ViT-Huge)**（秒加载，已预置权重）。
2. 工具栏：`pointQ`=正样本点、`pointE`=负样本点、`完成F`=确认、`清除B`=清空。
3. 选 `pointQ`，在商品上点一下 → 出贴合轮廓；多框了用 `pointE` 点掉。
4. `完成F` → 选 ERP 标准标签名。
5. 标错标签：**右键该轮廓 → 编辑标签**（不要用「永久删除此标签文件」，那是删整图标注的重操作）。
6. 每标完一张勾「已检查」当进度条；`Ctrl+S` 保存，生成图片同名 `.json`。

**所有商品（含盒子等矩形物）统一用 SAM 多边形，不手画矩形。** 检测框由转换脚本从多边形外接矩形自动派生，不标第二遍。

## 标注 → YOLO 双数据集转换

```bash
python scripts/convert_xanylabeling.py \
  --images datasets/kgos_real_all/images \
  --classes datasets/kgos_real_all/classes.txt \
  --out-seg datasets/kgos_seg_pilot \
  --out-det datasets/kgos_detect_pilot \
  --val-ratio 0.2
```

一份多边形标注产出两套：seg（多边形点）给 yolov8n-seg，det（外接矩形）给 yolov8n。未标注的图自动跳过。

## 新增图片去重

新图入库前先查是否与现有 270 张重复：

```bash
python scripts/dedup_images.py --new <新图或目录> --against datasets/kgos_real_all/images
```

结果 EXACT/DUPLICATE→丢弃；NEAR_DUPLICATE→人工确认是否同款（这批电商图同款不同赠品很常见）；UNIQUE→入库。
