# product-detect — YOLOv8 商品识别

替代 product-mapping 中的 LLM 识图，本地推理，零 token 消耗。

## 工作流程

```
1. 放素材图  →  assets/kgos/益生菌.jpg  （每类1-3张，白底）
2. 生成数据  →  python scripts/generate.py --brand kgos --preview
3. 确认效果  →  python scripts/verify.py --brand kgos --samples 20
4. 正式生成  →  python scripts/generate.py --brand kgos --count 1200
5. 训练模型  →  conda activate yolov8 && python scripts/train.py --brand kgos
6. 推理测试  →  python scripts/infer.py --brand kgos --image xxx.jpg --verbose
```

## 目录结构

```
assets/kgos/        ← 放单品素材图（每类1-3张，文件名=产品名）
assets/hee/         ← hee 品牌同上
datasets/kgos/      ← generate.py 自动生成，不要手动编辑
models/kgos_best.onnx  ← 训练完成后的最终模型
scripts/
  generate.py       ← 合成数据生成器
  train.py          ← 本机 CPU 训练（nice +10 低优先级）
  verify.py         ← 可视化验证标注是否正确
  infer.py          ← 生产推理模块
```

## 命令速查

```bash
# 预览合成效果（生成10张，看素材去背景是否干净）
python scripts/generate.py --brand kgos --preview

# 生成正式训练数据（1200张，训练集1020+验证集180）
python scripts/generate.py --brand kgos --count 1200

# 验证标注框是否准确（抽20张画框）
python scripts/verify.py --brand kgos --samples 20

# 训练（低优先级，可后台跑）
conda activate yolov8
nohup python scripts/train.py --brand kgos > runs/kgos_train.log 2>&1 &

# 中断后继续训练
python scripts/train.py --brand kgos --resume

# 推理测试
python scripts/infer.py --brand kgos --image /path/to/combo.jpg --verbose
```

## 注意事项

- 素材图文件名直接作为类别名，必须和 features.json 的 key 完全一致
- 训练需要先 `conda activate yolov8`（Python 3.10 环境）
- 推理（infer.py）可在系统 Python 3.14 下运行，不需要 conda 环境
- 训练默认用 yolov8n（快，约6-10小时），效果差再换 yolov8s
