# 品牌建档 SOP

> 开始前先读 `docs/preflight-brand.md` checklist，确认全部通过再进入下一步。

## 什么时候需要做品牌建档？

- 首次对一个品牌做视觉核查（如 HEE）
- 品牌添加了新产品（对 `features.json` 做增量更新）
- 数据被污染需要重建

## 完整流程（Step 0 → Step 6）

```text
Step 0: 清空旧数据工作区
  - 无需手动清空：check 命令开始时自动清空 data/imgs/ 和 data/reports/
  - 无需手动清空：match 命令开始时自动清空 done[] 和 failed[]
  - 无需手动清空：sku-records.json 由 check 全量重写
  - 只需确保 ERP 和鲸灵 Tab 正常打开

Step 1: 获取全量数据
  - 跑 node cli.js check --shop <店铺> --brand <品牌目录名>
  - 产出：data/imgs/（SKU 图片）+ data/reports/check-{shop}-{date}.json
  - 注意：check 会自动下载图片，这是唯一合法的图片来源

Step 2: 建立 sku-map（货号→platformCode 追踪台账）
  - 从 check 报告提取所有产品的 {productCode → [{platformCode, skuName, erpCode, erpName}]}
  - 存入 data/products/{brand}/sku-map.json
  - 当前手动执行；第三个品牌建档时实现自动化脚本

Step 3: 下载/整理参考图片
  - 目标：data/products/{brand}/*.jpg（单品标准图，命名=商品中文名）
  - 来源：从 data/imgs/ 中找对应 platformCode 的图片复制
    - 查 sku-map：商品中文名 → 货号 → platformCode
    - cp data/imgs/{platformCode}.jpg data/products/{brand}/{商品名}.jpg
  - “不在对应表”的产品：需额外获取图片（见下方异常处理）

Step 4: 建立/完善 features.json
  - 每个 ERP 活跃产品需要一个条目
  - erpName 必须与 ERP 档案V2 精确一致（可从 check 报告的 archiveTitle 字段获取）
  - 颜色 + 特征字段描述视觉识别依据
  - 如有体验装/正装两个版本，分别建条目

Step 5: 交叉验收（Phase Gate — 全部通过才算建档完成）

  自动可验（可写脚本或人工检查）：
  ✅ #1 sku-map keys 覆盖所有活动产品（无遗漏）
  ✅ #2 sku-map 中每个 platformCode 在 data/imgs/ 都有对应图片
  ✅ #4 features.json 产品数 = ERP 档案V2 该品牌活跃产品数
  ✅ #6 data/imgs/ 中无跨品牌图片（或确认品牌作用域已隔离）
  ✅ #7 features.json 每个条目都有对应参考图（data/products/{brand}/{name}.jpg）

  必须人工执行：
  👁 #3 随机抽 5+ 张图片目视 spot-check，确认内容与产品名一致
  👁 #5 随机抽 5~10 个 SKU 实跑识图，确认 features.json 可正确匹配

Step 6: 记录建档时间戳
  - 在 data/products/{brand}/features.json 的 _meta.lastUpdated 更新日期
```

## “不在对应表”产品的图片获取

有些产品活动期间不通过对应表销售（如礼盒整体包装图），需要特殊处理：

1. 确认该产品是否在鲸灵活动中（check 报告显示“不在对应表”）
2. 通过 ERP 档案V2 查询该产品的实物图
3. 或由用户直接提供参考图片

## 长期架构方向（可选，不是当前阻塞项）

现状判断：品牌参考资料已按 `data/products/{brand}/` 隔离；运行态工作区仍是全局单槽：`data/imgs/`、`data/sku-records.json`、`data/reports/`。当前脚本按“一轮只处理一个店铺/品牌”设计，`check` 会自动清空图片/报告并全量重写 `sku-records.json`，所以 KGOS/HEE 多品牌已可用。

只有出现以下需求时才重构：

- 需要并行处理多个品牌/店铺；
- 需要长期保留每个品牌的运行态图片、报告、sku-records；
- 需要在不同品牌之间频繁切换且不能接受 `check` 重跑恢复上下文。

可选目标架构：

```text
data/brands/{brand}/
  imgs/           ← 该品牌 SKU 图片（隔离）
  sku-records.json
  sku-map.json
  check-report.json
  ref-imgs/       ← 参考图（原 data/products/{brand}/）
```

未触发上述需求前，不为了“已有第二品牌”单独重构；继续保持 one-brand-per-run，并依赖 `check` 的自动清空/重写保证运行态干净。
