# SKU 库存计算器 — 待办

## Phase 1: 算法 + 纯计算流水线 ✓（2026-05-14 完成）

- [x] 1.1 项目脚手架（CLAUDE.md、package.json、docs/INDEX.md）
- [x] 1.2 单品目录注册（product-catalog.js + product-columns.json）
- [x] 1.3 加购数据解析（parse-cart-adds.js）
- [x] 1.4 组合明细 mock 数据（data/sku-components.json）
- [x] 1.5 核心分配算法（allocate.js + 单元测试，64个测试全通过）
- [x] 1.6 Excel 报告生成（write-report.js）
- [x] 1.7 CLI 入口（cli.js）

## Phase 2: 接入 ERP 自动化 ✓（2026-05-20 完成）

- [x] 2.1 组合明细自动获取（resolve-components.js）
- [x] 2.2 ERP 库存查询（query-stock.js）
- [x] 2.3 全流程验证 — 杭州共途 60/60 + 13 gift = 73/73 SKU resolved

## Phase 3: 健壮性 + 可选项

- [x] 3.1 供应商ID验证（validate-supplier.js + parse --supplier-id 参数，2026-05-20）
- [x] 3.2 店铺名自动推导 + 反向验证硬门禁（2026-05-22，L5 教训修复）
- [x] 3.3 满赠SKU支持（2026-05-22 ~ 2026-05-23）
  - [x] 货号自动展开（resolve-components 从对应表查找所有SKU）
  - [x] Phase G 受限单品等比例缩减（替代旧版报错）
  - [x] 80/20 分账（赠品最多占库存80%，正常SKU至少20%）
  - [x] Phase M SKU保底预扣（每个正常SKU至少5件，优先于赠品）
- [ ] 3.4 mergeStock 支持 — 将两个 ERP 名合并为同一 displayName（当前动态目录不支持，按需添加）
- [ ] 3.5 kgossynt-sm 商品匹配 — 该货号尚未在商品匹配项目中完成，3 个 SKU 无法包含在计算中
