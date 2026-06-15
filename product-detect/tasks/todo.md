# product-detect 任务台账

## 当前阶段：Phase 3 — 标注 270 张真实图（X-AnyLabeling）→ Detect-vs-Seg pilot

路线调整（2026-06-11）：合成训练集分布与真实 SKU 主图差距过大，转为标注真实图，比较 YOLO Detection 与 YOLO Segmentation 在密排 gift/combo 场景的业务计数效果。三层管道计划（NMS→OCR→LLM）暂缓，等视觉基础路线选定后重新评估。

标注工具切换（2026-06-15）：弃用 Label Studio + 外挂 SAM backend → 改用 X-AnyLabeling（内置 SAM、本地单进程、中文界面）。标注策略：每商品只标一遍 SAM 多边形，检测框由 `scripts/convert_xanylabeling.py` 自动派生。270 张全量标，不去重。手册 `docs/annotation-tool-xanylabeling.md`。

三层管道计划见 `~/.claude/plans/nested-mapping-trinket.md`（v2）——暂缓不删。

### 近期完成

- [x] **P3** KGOS 第四次训练（epoch 1→100，2026-05-28 启动，已完成）
  - mAP50=0.977, mAP50-95=0.951（退步：tight_bbox 导致维C泡腾片崩溃 -0.212）
  - 11 类退步, 8 类进步, 10 类持平

- [x] **P3** KGOS 第五次训练（epoch 1→100，2026-05-29 启动，已完成）
  - 模型: **yolov8s** (11M)，数据: 3000 张（2550 train + 450 val）
  - 改进: AR clipping (MIN_BBOX_AR=0.35) + 遮挡降档(30%) + 去杯子共现 + 权重重校准
  - 结果: 默认 val mAP50=0.992, mAP50-95=0.984（450 val，2026-05-31 完成）；business-val mAP50-95=0.89898（2026-06-04 补评估）

### 待办

- [废弃] **P3-C-0a** Label Studio Auto-Detect / SAM backend（2026-06-15 整套方案废弃）
  - 旧方案：`scripts/sam_ml_backend.py` + Label Studio 外挂 9090 backend。本机 interactive 链路点击不出 mask。
  - 已删除：sam_ml_backend.py、start-sam-backend.sh、test_sam_ml_backend.py、launchd 服务、LS 数据库。
  - 取代方案：X-AnyLabeling 内置 SAM，见 `docs/annotation-tool-xanylabeling.md`。

- [x] **P3** 用新白底/混放/遮挡规则重新生成 KGOS 训练集与业务验收集（2026-06-01）
  ```bash
  python scripts/generate.py --brand kgos --count 4000 --profile train
  python scripts/generate.py --brand kgos --count 600 --profile business-val
  python scripts/verify.py --brand kgos --dataset kgos_business_val --split val --samples 50
  ```
  - 注意：生成前确认没有训练进程正在读取 `datasets/kgos/`
  - 第 6 轮旧规则：固定白底、混放、遮挡后只标可见 bbox；当前密排生成规则见 `SKILL.md` 和 `docs/dataset-quality.md`
  - 已生成：`datasets/kgos/` 3400 train + 600 val；`datasets/kgos_business_val/` 600 val

- [x] **P3** 启动并完成新规则 yolov8s 第 6 轮训练（2026-06-01 启动，2026-06-03 完成）
  - 独立目录 `runs/kgos_yolov8s_train6/`，日志 `runs/kgos_train6.log`
  - 训练集 3400 + val 600，白底/混放/遮挡新规则，弱项类加权
  - 默认 val：best epoch 93，mAP50=0.99138，mAP50-95=0.96728
  - business-val：mAP50=0.99221，mAP50-95=0.96993
  - 结论：默认 val 低于第五轮，但 business-val 明显高于第五轮；说明评价集与真实目标未对齐

- [x] **P3** 审查真实 KGOS SKU 主图语料（2026-06-04）
  - 来源：微信文件目录 `.../2026-05/1主图汇总`
  - 270 张可读图片，形态以规则矩阵、买赠组合、重复排列、文字说明、赠品角标、小件靠边为主
  - 审查输出：`runs/dataset_audit_2026-06-04/kgos_real_sku_main_images/`
  - 结论：当前随机散放/随机遮挡合成器不贴近真实 SKU 主图分布

- [x] **P3-阶段0** NMS+conf 联合扫描（2026-06-04 完成）
  - 创建 `scripts/nms_sweep.py`，验证集：gift13(13张) + business-val(20张)
  - 扫描矩阵：iou=[0.3,0.4,0.5,0.6,0.7] × conf=[0.25,0.35,0.45]，共 15 组
  - 输出 `docs/nms-sweep-report.md`（热力图），确定最佳 (iou, conf)
  - 结论：最佳 `iou=0.70, conf=0.25`，综合 recall=0.749、precision=0.973；NMS/conf 只能小幅改善，必须继续阶段1密排数据生成器改造

- [x] **P3-阶段1** generate.py 改造（2026-06-04 完成）
  - 新增 ROW_LAYOUT / GRID_LAYOUT / GIFT_PACKAGE 三种密排场景（各占 20%）
  - 加入可控前后遮挡（10~30%）+ 高斯投影阴影
  - 重新生成 4000 train + 600 business-val
  - 生成结果：`datasets/kgos/` 为 3400 train + 600 val；`datasets/kgos_business_val/` 为 600 val
  - 验证结果：图片/label 数量匹配，0 个空 label，0 个 label 越界，总标注 33,635 个；`_verify` 抽样图已生成并抽看通过

- [x] **P3-阶段2** train7 训练与真实口径评估（2026-06-04 启动，2026-06-06 完成；2026-06-07 复评）
  - 从 train6 weights finetune，lr0=0.002，epochs=60，mosaic=0.8
  - 验收口径必须与 product-mapping 一致：`recognition.items = [{ name: ERP标准商品名, qty }]`，ERP 标准名来自 `product-mapping/data/products/kgos/features.json` 的 `erpName`；不得用“玉米片”等聚合名代替不同口味/规格商品。
  - 结果：默认 val mAP50-95=0.97564；business-val mAP50-95=0.96925；gift13 ERP标准口径 recall=61.11%、precision=81.48%、exact=3/13
  - 对比 train6：recall 55.56%→61.11%，但 precision 98.36%→81.48%，说明密排召回有提升但误检增加，仍不达 `gift13` recall ≥85% 验收线
  - 结论：不要马上开下一训；下一步先做文字结合验证。详见 `docs/train7-evaluation-report.md`

- [x] **P3-清理** 旧低效数据集和历史 run 清理（2026-06-05）
  - 已移到废纸篓归档：`/Users/chat/.Trash/product-detect-cleanup-20260605`，大小约 153M
  - 保留当前训练、基线和黄金验证相关目录：`datasets/kgos`、`datasets/kgos_business_val`、`datasets/kgos_real_golden_*`、`runs/kgos_yolov8s_train6`、`runs/kgos_yolov8s_train7`
  - 当前训练日志保留：`runs/kgos_train7.log`、`runs/kgos_train7.err.log`

- [进行中] **P3-B-1** 标注 270 张真实图（X-AnyLabeling，全量；当前 1/270，gift_001 已标）
  - 工具：X-AnyLabeling（conda x-anylabeling），每商品 SAM 点一遍多边形，存图片同名 .json
  - 标签必须使用 ERP 标准名（28类，见 `datasets/kgos_real_all/classes.txt`）
  - 流程/补丁/排障：`docs/annotation-tool-xanylabeling.md`
  - gift_001 一图端到端冒烟已通过（SAM→标注→json→转换→overlay）

- [ ] **P3-C-0** Detect-vs-Seg pilot（标注积累一批后即可起）
  - 计划：`docs/detect-vs-seg-pilot-plan-v2.md`（已按"只标一遍多边形"修订）
  - 转换：`scripts/convert_xanylabeling.py` 一份多边形→seg + det 两套数据集
  - 模型：pilot 用 `yolov8n.pt` 和 `yolov8n-seg.pt`
  - 评估：图片级 exact、ERP item recall/precision、gift/combo 子集

- [ ] **P3-B-2** 路线选定后构建完整集数据集
  ```bash
  # 用 convert_xanylabeling.py 从 270 张标注生成 seg + det 双数据集
  # 检测胜出用 det，分割胜出用 seg；80/20 split
  # 加入 5-10 张背景图（空标注，防止误检）
  ```

- [ ] **P3-B-3** 启动完整集训练（从 COCO 权重重训，不微调 train6/7）
  ```bash
  # 检测胜出：从 yolov8s.pt 开始，独立目录 runs/kgos_yolov8s_train8/
  # 分割胜出：从 yolov8s-seg.pt 开始，独立目录 runs/kgos_yolov8s_seg_train8/
  ```

- [ ] **P3-B-4** train8 完成后在 gift13 评估 recall，目标 ≥ 85%
  - 若 recall ≥ 85%：考虑是否还需要三层管道；若达 98% 准确率可跳过
  - 若 recall < 85%：重启三层管道 / TTA / YOLOv8m 路线

- [ ] **P3-阶段3** 文字结合验证（**暂缓** — 等 train8 基础 recall 结果再决定）
  - [x] 创建 `scripts/ocr_verify.py` 试验入口，先支持可见文字/人工文本输入，不依赖本机 OCR 引擎
  - [x] 固定 YOLO-first 纠正规则：YOLO 决定具体口味/规格；文字只修正数量。模糊文字如“玉米片 10”只能在 YOLO 已识别出具体子类时均分/补数；无法确定子类时标为 unresolved，不生成 ERP 子品。
  - [x] gift13 小集试评估：`docs/text-correction-gift13-report.md`。在可由 YOLO 支持解析的 103 个期望件口径下，YOLO-only recall=0.631、precision=0.802；YOLO+text recall=1.000、precision=0.866。该结果说明文字纠正确实能补密排计数，但不是最终黄金验收。
  - [x] Phase C 初版 text50 实验框架：`datasets/kgos_real_text50/ground_truth.json` 当前纳入 50 张候选，其中 12 张 labeled、1 张 ambiguous、37 张 pending；`scripts/text50_eval.py` 按 exact-match 评估，pending/ambiguous 不进入分母。
  - [x] Phase D 最小 gating 实验：`docs/text50-evaluation-report.md` 显示 12 张已标注样本中 YOLO-only exact=3/12，YOLO+text exact=5/12，YOLO+text gated exact=11/12。结论：路线可继续，但必须保留 anomaly gating，不能直接把 YOLO+text 合并结果写入 product-mapping。
  - [x] 建立可积累简称/别名表：`data/kgos_text_aliases.json`。精确简称（如“莓果营养粉”）直接映射 ERP 标准名；模糊简称（如“营养粉”“玉米片”）只映射候选组，必须由 YOLO/LLM/人工视觉确认具体口味后才能落到 ERP 子品。
  - [x] 文档收口（2026-06-07）：`CLAUDE.md` / `SKILL.md` 已同步到 text50 gating 结论和简称表规则；下一次继续不应回到“直接裸合并 YOLO+text”。
  - [ ] 持久化 text50 标注文件：`datasets/kgos_real_text50/ground_truth.json` 当前被 `.gitignore` 的 `datasets/` 规则忽略；若作为长期基准集，应移动到 `docs/` 或调整 ignore。
  - [ ] 接入真实 OCR 或 LLM 文本提取：底部 20% 区域优先，增强多对提取
  - [ ] OCR 有效性专项测试（50 张 ground truth），目标有效率 ≥90%
  - [ ] 处理 unresolved 样本：`real_003` 黑茶体验装随机口味需要业务规则；`real_011` 营养粉 3 文字有但 YOLO 无子类支持，需要 LLM/人工视觉兜底或改成 SKU 级识别

- [ ] **P3-阶段4** 异常管道 + Codex 多模态修正接口（3-4h，可与阶段2并行）
  - 创建 `scripts/anomaly.py` + `scripts/codex_correct.py`
  - 将 text50 gating 中的 `blocked` / `unresolved` 升级为正式异常类型：`YOLO_EXTRA_NOT_IN_TEXT`、`TEXT_UNRESOLVED`、`NO_VISUAL_SUBTYPE_SUPPORT`
  - OCR 失效时强制 LLM 多模态看图兜底（NO_OCR_SIGNAL 触发）

- [ ] **P3-阶段5** 黄金验证集 100 张 + 最终评估（6-8h，依赖阶段2）
  - 抽样：根目录 40 + 1/子目录 47 + 赠品 13 = 100 张，密排占 60%
  - 人工校验，eval_golden.py 分层报告（单品/组合/密排）
  - 验收：三层管道全集准确率 ≥98%

- [ ] **P3-阶段6** TTA / YOLOv8m 集成（兜底，按需）
  - 触发：阶段2密排召回 <85% 或阶段5准确率 <98%
  - 优先 TTA（水平翻转+微旋转+WBF），不够再上 YOLOv8m

- [ ] **P4** 黄金验证集通过后导出 ONNX 覆盖生产模型（原 models/kgos_best.onnx 仍是 2026-05-26 版本）
  ```bash
  # models/kgos_best.onnx 目前仍是 2026-05-26 版本
  # 不要在黄金验证集完成前覆盖
  ```

- [ ] **P4** 集成到 product-mapping（替代 LLM 识图；需先通过黄金验证集）

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
