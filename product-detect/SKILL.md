# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。输出：[{name, count}]。

## 当前状态

- Phase: 3（第五次训练进行中，2026-05-29）
- **第五次训练**：yolov8s + 3000张 + AR clipping（修复v4维C泡腾片崩溃），日志 `runs/kgos_train5.log`
- **第四次训练结果**：epoch 100/100，mAP50=0.977，mAP50-95=0.951（退步于v3；tight_bbox 双刃剑：阻断片+0.034 但 维C泡腾片-0.212）
- **第三次训练结果**：epoch 100/100，mAP50=0.986，mAP50-95=0.958（2026-05-28）
  - `runs/kgos_yolov8n/weights/best.pt` 已更新；`models/kgos_best.onnx` 仍是旧版（待导出）
- hee 未开始

## ENTRY MAP

| 任务 | 入口 |
|------|------|
| 生成训练数据 | `python scripts/generate.py --brand kgos` |
| 验证标注效果 | `python scripts/verify.py --brand kgos` |
| 训练模型 | `conda activate yolov8 && python scripts/train.py --brand kgos` |
| 推理测试 | `python scripts/infer.py --brand kgos --image xxx.jpg` |
| 查看进度 | `tasks/todo.md` |

## PATHS

```
assets/
  kgos/          ← 单品素材图（文件名=ERP产品名，与 features.json key 一致）
  hee/           ← hee 品牌素材图
datasets/
  kgos/          ← generate.py 输出，含 data.yaml + images/ + labels/
  hee/           ← 同上
models/
  kgos_best.onnx ← 训练完成后的生产模型
  hee_best.onnx
scripts/
  generate.py    ← 合成数据生成器（主工具）
  train.py       ← CPU 训练脚本
  verify.py      ← 标注可视化验证
  infer.py       ← 生产推理（ProductDetector 类）
runs/            ← 训练日志和权重（git ignore）
```

## DO FIRST（新 session 进入）

1. 读 `tasks/todo.md` 确认当前阶段
2. 确认 conda yolov8 环境是否就绪
3. 确认 `assets/kgos/` 素材图是否已放入
