# SKU 库存计算器 — 当前待办

## 当前批次

当前没有进行中的库存批次；已完成活动见 `docs/archive/README.md`。

## 按需实现

- [ ] **对齐ERP命令的售后守卫接口**：`cli.js` 的 `resolve-components` / `resolve-stock` 仍调用 `releaseErpLock()`，而共享模块现仅导出 `ensureAftersalesPaused()` / `resumeAftersales()`；需修复命令收尾接口并验证暂停/恢复语义。本轮双活动已直接复用只读模块完成，未依赖该CLI收尾路径。

- [ ] **mergeStock 支持**：允许把两个 ERP 商品名合并为同一 `displayName`。当前动态目录按 ERP 原名分别建列；只有真实活动再次出现同一库存被多个 ERP 名拆分的场景时再实现，不为假设场景预建抽象。

已完成批次和阶段证据统一见 `docs/archive/README.md`；当前算法、数据和ERP规则见 `docs/operations.md`。
