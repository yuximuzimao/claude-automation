# product-detect

本项目训练本地 YOLOv8 商品识别模型，用于替代 `product-mapping` 里的 LLM 识图成本。当前 KGOS 路线处在 Detect-vs-Seg pilot：先用 64 张真实 SKU 主图比较检测框和实例分割，路线选定后再标完整 270 张。

## 当前入口

- Agent 入口：`SKILL.md`
- 任务台账：`tasks/todo.md`
- 数据质量和训练门禁：`docs/dataset-quality.md`
- Detect-vs-Seg pilot：`docs/detect-vs-seg-pilot-plan-v2.md`
- Label Studio SAM 自动轮廓：`docs/sam-auto-detect-runbook.md`
- 标注操作指南：`datasets/kgos_real_all/标注操作指南.md`（本地数据目录，被 git ignore）

## 运行速查

```bash
# 回归测试
python3 -m unittest tests.test_generate tests.test_train tests.test_verify tests.test_nms_sweep tests.test_sam_ml_backend -v

# Label Studio
LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true \
LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/Users/chat/claude/product-detect/datasets \
label-studio start --port 8080

# SAM ML Backend 健康检查
curl --noproxy '*' http://localhost:9090/health

# 手动启动 SAM ML Backend（launchd 正常运行时不需要）
bash start-sam-backend.sh
```

## 关键约束

- 训练和标注标签必须使用 ERP 标准商品名，来源为 `product-mapping/data/products/kgos/features.json` 的 `erpName`。
- `models/kgos_best.onnx` 只有黄金验证集通过后才能覆盖。
- 64 张 pilot 未完成前，不要让用户把 270 张全部按旧检测框路线标完。
- SAM 自动轮廓只生成 `BrushLabels name="mask"` 建议；`RectangleLabels name="bbox"` 仍需独立标注，并且每张图的 mask/bbox 数量和 ERP 聚合数量必须一致。
