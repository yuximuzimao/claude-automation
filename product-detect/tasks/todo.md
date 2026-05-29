# product-detect 任务台账

## 当前阶段：Phase 3 — 第五次训练进行中

### 进行中

- [x] **P3** KGOS 第四次训练（epoch 1→100，2026-05-28 启动，已完成）
  - mAP50=0.977, mAP50-95=0.951（退步：tight_bbox 导致维C泡腾片崩溃 -0.212）
  - 11 类退步, 8 类进步, 10 类持平

- [ ] **P3** KGOS 第五次训练（epoch 1→100，2026-05-29 启动，PID 36225）
  ```bash
  tail -f /Users/chat/claude/product-detect/runs/kgos_train5.log
  ```
  - 模型: **yolov8s** (11M)，数据: 3000 张（2550 train + 450 val）
  - 改进: AR clipping (MIN_BBOX_AR=0.35) + 遮挡降档(30%) + 去杯子共现 + 权重重校准
  - 预计 15-22 小时

### 待办

- [ ] **P3** 第五次训练完成后，用 eval_errors.py 对比 v4 弱项提升情况
  ```bash
  conda run -n yolov8 python /tmp/eval_errors.py
  ```

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

