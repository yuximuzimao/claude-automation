# product-detect — YOLOv8 商品识别

项目中文名：商品识别训练

替代 product-mapping 中的 LLM 识图，本地推理，零 token 消耗。

## 工作流程

```
1. 放素材图  →  assets/kgos/益生菌.jpg  （每类1-3张，白底）
2. 生成数据  →  python scripts/generate.py --brand kgos --profile train --preview
3. 确认效果  →  python scripts/verify.py --brand kgos --samples 20
4. 正式生成  →  python scripts/generate.py --brand kgos --count 4000 --profile train
5. 业务验收集 →  python scripts/generate.py --brand kgos --count 600 --profile business-val
6. 训练模型  →  使用独立 run name 启动，避免覆盖旧 runs/kgos_yolov8s
7. 推理测试  →  python scripts/infer.py --brand kgos --image xxx.jpg --verbose
```

## 目录结构

```
assets/kgos/        ← 放单品素材图（每类1-3张，文件名=产品名）
assets/hee/         ← hee 品牌同上
datasets/kgos/      ← generate.py --profile train 自动生成，不要手动编辑
datasets/kgos_business_val/  ← generate.py --profile business-val 自动生成，用于业务验收
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

# 生成正式训练数据（4000张，训练集3400+默认验证集600）
python scripts/generate.py --brand kgos --count 4000 --profile train

# 生成独立业务验收验证集（600张，全部写入 val）
python scripts/generate.py --brand kgos --count 600 --profile business-val

# 验证标注框是否准确（抽20张画框）
python scripts/verify.py --brand kgos --samples 20

# 验证业务验收集标注框
python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50

# 监控当前第 6 轮训练（新规则 yolov8s，独立目录 runs/kgos_yolov8s_train6）
tail -f runs/kgos_train6.log

# 新启动 yolov8s 训练时必须使用独立 run name；不要直接覆盖 runs/kgos_yolov8s
# scripts/train.py 默认 name=kgos_yolov8s，会覆盖第 5 轮目录，除非明确要这么做。

# 中断后继续训练
python scripts/train.py --brand kgos --resume

# 评估验证集弱项
conda run -n yolov8 python /tmp/eval_errors.py

# 推理测试
python scripts/infer.py --brand kgos --image /path/to/combo.jpg --verbose
```

## 注意事项

- 素材图文件名直接作为类别名，必须和 features.json 的 key 完全一致
- 训练需要 conda yolov8 环境（Python 3.10）
- 推理（infer.py）可在系统 Python 3.14 下运行，不需要 conda 环境
- yolov8n=快速验证(~8h)，yolov8s=生产精度(~18h)
- **日志输出**：必须用 `source conda.sh + conda activate + exec python -u`，conda run 会缓冲日志
- 生成器只使用白底真实素材，不使用 AI 生图；遮挡样本按最终可见 alpha 区域写 bbox，可见面积低于 35% 不写入 label
