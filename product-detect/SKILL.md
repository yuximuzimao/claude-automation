# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。输出：[{name, count}]。

## 当前状态

- Phase: 3（第六次训练进行中）
- **第六次训练**：2026-06-01 00:44 启动，PID 47371，`runs/kgos_yolov8s_train6/`，日志 `runs/kgos_train6.log`；新规则数据集 3400 train + 600 val，弱项类加权；按 2026-06-01 00:52 速度估算 65-72 小时，预计 2026-06-03 晚至 2026-06-04 凌晨完成
- **新规则数据集**：`datasets/kgos/` 4000 张（3400 train + 600 val），`datasets/kgos_business_val/` 600 val；固定白底 + 混放/遮挡 + 可见 bbox
- **第五次训练**：yolov8s + 3000张 + AR clipping 已完成，mAP50=0.992，mAP50-95=0.984，日志 `runs/kgos_train5.log`
- **第四次训练结果**：epoch 100/100，mAP50=0.977，mAP50-95=0.951（退步于v3；tight_bbox 双刃剑：阻断片+0.034 但 维C泡腾片-0.212）
- **第三次训练结果**：epoch 100/100，mAP50=0.986，mAP50-95=0.958（2026-05-28）
  - `runs/kgos_yolov8n/weights/best.pt` 已更新；`models/kgos_best.onnx` 仍是旧版（待导出）
- hee 未开始

## ENTRY MAP

| 任务 | 入口 |
|------|------|
| 生成训练数据 | `python scripts/generate.py --brand kgos --count 4000 --profile train` |
| 生成业务验收验证集 | `python scripts/generate.py --brand kgos --count 600 --profile business-val` |
| 验证标注效果 | `python scripts/verify.py --brand kgos` |
| 验证业务验收集标注 | `python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50` |
| 监控第六次训练 | `tail -f runs/kgos_train6.log` |
| 训练模型 | 使用独立 run name；`scripts/train.py --brand kgos --model yolov8s` 会写 `runs/kgos_yolov8s`，不要误覆盖旧权重 |
| 推理测试 | `python scripts/infer.py --brand kgos --image xxx.jpg` |
| 查看进度 | `tasks/todo.md` |
| 生成器单元测试 | `python3 -m unittest tests.test_generate` |

## PATHS

```
assets/
  kgos/          ← 单品素材图（文件名=ERP产品名，与 features.json key 一致）
  hee/           ← hee 品牌素材图
datasets/
  kgos/          ← generate.py --profile train 输出，含 data.yaml + images/ + labels/
  kgos_business_val/ ← generate.py --profile business-val 输出，独立业务验收验证集
  hee/           ← 同上
models/
  kgos_best.onnx ← 训练完成后的生产模型
  hee_best.onnx
scripts/
  generate.py    ← 合成数据生成器（主工具）
  train.py       ← CPU 训练脚本
  verify.py      ← 标注可视化验证
  infer.py       ← 生产推理（ProductDetector 类）
tests/
  test_generate.py ← 生成规则与遮挡标注回归测试
runs/            ← 训练日志和权重（git ignore）
```

## 训练注意事项

- 第 6 轮目标不是单纯刷默认 val 的 mAP，而是提升白底混放/遮挡业务图上的弱项召回和可见 bbox 稳定性。
- 默认 val 指标可能低于第 5 轮 `mAP50-95=0.984`，但如果 `datasets/kgos_business_val/` 和真实混放图更稳，仍更适合作为上线候选。
- 新训练必须保留独立输出目录，避免覆盖 `runs/kgos_yolov8s/weights/best.pt`。

## DO FIRST（新 session 进入）

1. 读 `tasks/todo.md` 确认当前阶段
2. 确认 conda yolov8 环境是否就绪
3. 确认 `assets/kgos/` 素材图是否已放入

## 生成规则

- 背景固定纯白，不再生成噪声背景。
- 训练集按 `single` / `mixed_clean` / `mixed_occluded` 三类场景生成，比例 20% / 35% / 45%。
- 遮挡样本按最终可见 alpha mask 计算 bbox；可见面积低于原始面积 35% 的目标不写 label。
- `business-val` 独立写入 `datasets/<brand>_business_val/`，不做亮度/对比度增强，用于业务验收。
