# product-detect

本项目训练本地 YOLOv8 商品识别模型，用于替代 `product-mapping` 里的 LLM 识图成本。当前 KGOS 路线处在 Detect-vs-Seg pilot：先用 64 张真实 SKU 主图比较检测框和实例分割，路线选定后再标完整 270 张。

## 当前入口

- Agent 入口：`SKILL.md`
- 任务台账：`tasks/todo.md`
- 数据质量和训练门禁：`docs/dataset-quality.md`
- Detect-vs-Seg pilot：`docs/detect-vs-seg-pilot-plan-v2.md`
- X-AnyLabeling 标注工具：`docs/annotation-tool-xanylabeling.md`
- 旧 Label Studio 指南：`datasets/kgos_real_all/标注操作指南.md`（历史参考；当前不作为入口）

## 运行速查

```bash
# 回归测试
python3 -m unittest tests.test_generate tests.test_train tests.test_verify tests.test_nms_sweep tests.test_ocr_verify tests.test_text50_eval -v

# X-AnyLabeling 当前标注入口（批量标注传目录，不传单图）
conda activate x-anylabeling && xanylabeling \
  --filename "$PWD/datasets/kgos_real_all/images" \
  --labels "$PWD/datasets/kgos_real_all/classes.txt"

# 标注转换：一份多边形同时派生 seg + det
python scripts/convert_xanylabeling.py \
  --images datasets/kgos_real_all/images \
  --classes datasets/kgos_real_all/classes.txt \
  --out-seg datasets/kgos_seg_pilot \
  --out-det datasets/kgos_detect_pilot
```

## 关键约束

- 训练和标注标签必须使用 ERP 标准商品名，来源为 `product-mapping/data/products/kgos/features.json` 的 `erpName`。
- `models/kgos_best.onnx` 只有黄金验证集通过后才能覆盖。
- Detect-vs-Seg pilot 未完成前，不要让用户把 270 张全部按旧检测框路线标完。
- 当前只标 X-AnyLabeling 多边形；检测框由 `scripts/convert_xanylabeling.py` 从多边形外接矩形自动派生，并且每张图派生出的 mask/bbox 数量和 ERP 聚合数量必须一致。
