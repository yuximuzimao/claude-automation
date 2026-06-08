# KGOS 商品检测数据集质量规范

## 当前结论

截至 2026-06-07，KGOS 已完成真实主图语料审查、NMS/conf 扫描、密排合成器改造和 `train7` 评估。当前重点不是继续刷默认合成 val 或马上开启下一轮训练，而是先做文字结合验证，确认三层管道（YOLO→OCR/文字→LLM）的业务准确率。

已确认的真实 KGOS SKU 主图语料在：

```text
/Users/chat/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/qumiao2940_272e/msg/file/2026-05/1主图汇总
```

该目录只作为只读参考源，不直接写入 Git。目录审查结果：

- 270 张可读图片：269 JPEG + 1 PNG
- 尺寸：234 张 1280x1280，36 张 1200x1200
- 分组：根目录 183 张主图，`1/` 74 张买赠/组合图，`赠品/` 13 张赠品图
- 审查缩略图输出：`runs/dataset_audit_2026-06-04/kgos_real_sku_main_images/`

这些真实图的主要形态是规则矩阵、买赠组合、重复排列、文字说明、赠品角标、小件赠品靠边。2026-06-04 后的合成器已加入 `row_layout` / `grid_layout` / `gift_package` 三种密排场景，用于贴近该分布。

## 训练门禁

在启动下一轮长训、导出生产 ONNX 或接入 product-mapping 前，必须完成以下门禁：

1. 从真实 KGOS SKU 主图中抽样建立黄金验证集，不进入训练集。
2. 验收口径必须统一为 product-mapping 当前使用的 `recognition.items`：`[{ name: <ERP标准商品名>, qty: <数量> }]`。标准商品名唯一来源是 `product-mapping/data/products/kgos/features.json` 的 `erpName`；集合比较按 `name×qty` 完全一致，不允许用“玉米片”“营养粉”“黑茶”等临时聚合名替代。
3. 明确标注规则：标什么、不标什么、遮挡到什么程度算有效目标。
4. 用黄金验证集评估 train6、train7 和后续候选模型。
5. 保持合成器分布贴近真实 SKU 主图，而不是退回随机散落商品。

未完成门禁时，不要把 `models/kgos_best.onnx` 覆盖为新候选。

## 标注规则草案

- 只标图片中真实可见的商品实物。
- 不标活动文案、红色“赠”标、价格、说明文字、背景装饰。
- 不标不可见配件；配件是否计入 SKU 匹配应由 product-mapping 规则处理。
- 包装盒上的插画、商品示意图不算另一个商品，除非业务明确要求识别它。
- 重复商品矩阵要先决定任务目标：
  - 如果目标是商品存在性/组合匹配，可考虑改为多标签或 SKU 级识别。
  - 如果目标是精确计数，才逐个标注每个可见实例。
- 口味/规格对应不同 ERP 商品时必须拆开计数。例如两个口味的玉米片各 5 包，应输出 `KGOS玉米浓汤味玉米片 30g×5` 和 `KGOS香菜牛肉味玉米片 30g×5`，不能输出 `玉米片×10`。
- 遮挡目标只标可见主体区域；但遮挡严重到无法区分类别时不标。

## 当前训练结果对照

| 训练轮次 | 默认 val mAP50-95 | business-val mAP50-95 | 结论 |
|---|---:|---:|---|
| `runs/kgos_yolov8s_train6` 第六轮 | 0.96728 | 0.96993 | 默认 val 退步，业务验证明显更强 |
| `runs/kgos_yolov8s_train7` 第七轮 | 0.97564 | 0.96925 | 密排召回有提升但误检增加；gift13 ERP标准口径 recall=61.11%、precision=81.48%、exact=3/13，未达生产门槛 |

这说明默认合成验证集和业务目标不一致。后续不能只用默认 val mAP 判断模型好坏，也不要在文字结合验证前启动下一轮长训。`train7` 详见 `docs/train7-evaluation-report.md`。

## 合成器改造方向

真实 KGOS 主图显示，合成器应优先模拟：

- 同类商品横排、网格、上下分层矩阵（`row_layout` / `grid_layout`）
- 主品 + 赠品固定区域组合（`gift_package`）
- 小件赠品靠边或靠底部出现
- 活动文案存在但不作为检测目标
- 盒装商品大量重复，而不是少量随机物体散落

极端随机遮挡只应作为少量增强，不应成为主分布。

## 当前数据集边界

- `datasets/kgos/`：当前 train7 训练集，3400 train + 600 val，自动生成，不手动编辑。
- `datasets/kgos_business_val/`：当前业务验证集，600 val，自动生成，不参与训练。
- `datasets/kgos_real_golden_gift13/`：真实礼品图小集，保留用于密排回归。
- `datasets/kgos_real_golden_candidates_v1/`：真实主图候选集，保留用于后续黄金验证集。
- `runs/kgos_yolov8s_train6/`：train7 的回滚/对照基线，保留。
- `runs/kgos_yolov8s_train7/`：已完成的候选模型，保留用于文字结合验证和后续对照。
