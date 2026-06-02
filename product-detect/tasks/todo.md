# product-detect 任务台账

## 当前阶段：Phase 3 — 新规则第 6 轮 yolov8s 训练进行中

### 进行中

- [x] **P3** KGOS 第四次训练（epoch 1→100，2026-05-28 启动，已完成）
  - mAP50=0.977, mAP50-95=0.951（退步：tight_bbox 导致维C泡腾片崩溃 -0.212）
  - 11 类退步, 8 类进步, 10 类持平

- [x] **P3** KGOS 第五次训练（epoch 1→100，2026-05-29 启动，已完成）
  ```bash
  tail -f /Users/chat/claude/product-detect/runs/kgos_train5.log
  ```
  - 模型: **yolov8s** (11M)，数据: 3000 张（2550 train + 450 val）
  - 改进: AR clipping (MIN_BBOX_AR=0.35) + 遮挡降档(30%) + 去杯子共现 + 权重重校准
  - 结果: mAP50=0.992, mAP50-95=0.984（450 val，2026-05-31 完成）

### 待办

- [x] **P3** 用新白底/混放/遮挡规则重新生成 KGOS 训练集与业务验收集（2026-06-01）
  ```bash
  python scripts/generate.py --brand kgos --count 4000 --profile train
  python scripts/generate.py --brand kgos --count 600 --profile business-val
  python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50
  ```
  - 注意：生成前确认没有训练进程正在读取 `datasets/kgos/`
  - 新规则：固定白底；20% 单品、35% 混放无遮挡、45% 混放遮挡；遮挡后只标可见 bbox；可见面积 <35% 不标注
  - 已生成：`datasets/kgos/` 3400 train + 600 val；`datasets/kgos_business_val/` 600 val

- [x] **P3** 启动新规则 yolov8s 第 6 轮训练（2026-06-01 启动）
  - PID 47371，独立目录 `runs/kgos_yolov8s_train6/`，日志 `runs/kgos_train6.log`
  - 训练集 3400 + val 600，白底/混放/遮挡新规则，弱项类加权
  - 启动命令：`nohup bash -c 'source ~/miniconda3/etc/profile.d/conda.sh && conda activate yolov8 && exec python -u /tmp/kgos_train6_launcher.py' > runs/kgos_train6.log 2>&1 &`
  - 预计耗时：按 2026-06-01 00:52 速度估算 65-72 小时，约 2026-06-03 晚至 2026-06-04 凌晨完成
  - 验收重点：默认 val 不必单纯超过 train5；重点看 `datasets/kgos_business_val/` 和真实业务混放图上的弱项 Recall、mAP50-95、漏检率

- [ ] **P3** 新规则训练完成后，同时评估默认 val 与 business-val
  ```bash
  conda run -n yolov8 python /tmp/eval_errors.py
  ```
  - 弱项重点：黑咖体验装、酵素4.0体验装、腰围卡尺、冰霸杯、KGO手提袋

- [ ] **P3** 导出新 ONNX 覆盖生产模型
  ```bash
  # models/kgos_best.onnx 目前仍是 2026-05-26 版本（第一次训练）
  # 第五次完成后需要导出 runs/kgos_yolov8s/weights/best.pt → models/kgos_best.onnx
  ```

- [ ] **P3** 推理测试（真实组合图）
  ```bash
  python scripts/infer.py --brand kgos --image /path/to/combo.jpg --verbose
  ```

- [ ] **P4** 集成到 product-mapping（替代 LLM 识图）

- [ ] **P5** hee 品牌训练（待素材图）

## 已完成

- [x] 项目目录结构创建
- [x] generate.py / train.py / infer.py / verify.py 编写完成
- [x] 安装 Miniconda + 创建 yolov8 conda 环境（Python 3.10）
- [x] KGOS 单品素材图放入 `assets/kgos/`（29个类别）
- [x] 预览去背景效果确认
- [x] 正式生成训练数据集（1700张，含遮挡增强，2026-05-26）
- [x] KGOS 第一次训练完成（epoch 67 早停，mAP50 ≈ 0.99，2026-05-25）
- [x] generate.py 遮挡增强（OCCLUSION_PROB=0.60，叠压 IoU≤0.55，2026-05-26）
- [x] train.py --resume bug 修复（路径从 runs/detect/ 改为 runs/kgos_yolov8n/，2026-05-27）
- [x] KGOS 第三次训练完成（epoch 100/100，mAP50=0.986，mAP50-95=0.958，2026-05-28）
- [x] 验证集弱项分析（eval_errors.py，FN/FP/混淆矩阵，2026-05-28）
- [x] generate.py 第四次训练改进：tight_bbox + 频率权重 + 杯型共现 + 背景噪声（2026-05-28）
- [x] 数据集第四次生成（2000张，seed=100，2026-05-28）
- [x] generate.py 业务白底规则改造：三类场景、遮挡后可见 bbox、35% 可见率丢弃、弱项定向权重、business-val profile（2026-05-31）
- [x] KGOS 新规则正式数据集生成并验证：文件数、label 范围、白底角点、弱项补量、overlay smoke 均通过（2026-06-01）
