# SKU 库存计算器 — 当前待办

## 当前批次

悦希 9.22 蘅圆库存分配已于 2026-09-21 完成，事实与最终报告指纹见 `docs/archive/2026-09-21-hengyuan-hee-922-allocation/`。

- [ ] **ERP 新版页面兼容复验**
  - `resolve-components` 间接依赖 `../product-mapping/lib/archive.js` 的“商品档案V2”读取；该页面已迁移到 `#/prod/parallel_next/` 且 Vue 查询结构变化，待商品匹配项目完成最小兼容后一起复验。
  - `resolve-stock` 直接依赖“库存状态”；新路由为 `#/stock/newstatu_next/`。2026-09-21 已验证新版 Vue store 仍有 `title` / `availableStock`，但用户将先按脚本需求调整新版页面列头/顺序，之后再正式回归 `lib/query-stock.js`。
  - 仅做必要 URL/结构兼容，不改变库存分配算法。

## 按需实现

- [ ] **mergeStock 支持**：允许把两个 ERP 商品名合并为同一 `displayName`。当前动态目录按 ERP 原名分别建列；只有真实活动再次出现同一库存被多个 ERP 名拆分的场景时再实现，不为假设场景预建抽象。

已完成批次和阶段证据统一见 `docs/archive/README.md`；当前算法、数据和 ERP 规则见 `docs/INDEX.md`。
