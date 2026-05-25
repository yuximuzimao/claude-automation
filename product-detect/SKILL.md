# product-detect SKILL MAP

## 项目定位

本地 YOLOv8 商品检测模型，替代 product-mapping 中的 LLM 识图。
输入：组合商品图。输出：[{name, count}]。

## 当前状态

- Phase: 1（环境安装阶段）
- 品牌进度: KGOS 待训练，hee 待训练
- 素材图: 待用户提供 → assets/kgos/

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
