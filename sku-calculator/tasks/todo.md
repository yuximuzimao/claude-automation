# SKU 库存计算器 — 待办

## Phase 1: 算法 + 纯计算流水线 ✓（2026-05-14 完成）

- [x] 1.1 项目脚手架（CLAUDE.md、package.json、docs/INDEX.md）
- [x] 1.2 单品目录注册（product-catalog.js + product-columns.json）
- [x] 1.3 加购数据解析（parse-cart-adds.js）
- [x] 1.4 组合明细 mock 数据（data/sku-components.json）
- [x] 1.5 核心分配算法（allocate.js + 单元测试，37个测试全通过）
- [x] 1.6 Excel 报告生成（write-report.js）
- [x] 1.7 CLI 入口（cli.js）

## Phase 2: 接入 ERP 自动化 ✓（2026-05-20 完成）

- [x] 2.1 组合明细自动获取（resolve-components.js）— 采用与 check.js 相同路径（readCorrWithoutDownload + initArchiveComp + queryArchive）
- [x] 2.2 ERP 库存查询（query-stock.js）— 分页修复，全量读取
- [x] 2.3 全流程验证 — 杭州共途 54/54 SKU resolved，0 警告

## Phase 3: 健壮性 + 可选项

- [x] 3.1 供应商ID验证（validate-supplier.js + parse --supplier-id 参数，2026-05-20）
- [x] 3.4 店铺名自动推导 + 反向验证硬门禁（2026-05-22，L5 教训修复）
  - parse 写 supplierId 到 _meta
  - resolve-components 自动从共享 shop-map.js 推导店铺名
  - matchedSkus < totalSkus → exit(1) 硬中止
- [ ] 3.2 mergeStock 支持 — 将两个 ERP 名合并为同一 displayName（当前动态目录不支持，按需添加）
- [ ] 3.3 kgossynt-sm 商品匹配 — 该货号尚未在商品匹配项目中完成，3个 SKU 无法包含在计算中
