# SKU 库存计算器 — 当前待办

## 当前批次

- [ ] KGOS账号4（蓄力生长，商家42214）库存计算：用户确认本次无加购数据；18个SPU已从ERP读全41个SKU（37个销售、4个满赠）、16种实体商品及当次库存，尚未生成最终报表。证据见 `data/batches/2026-10-28-kgos-account4/`。
  - 等待用户选择普通SKU等权分配或原规则保底5件，并明确`1029zp-1`～`1029zp-4`各预留份数；四档各1个规格，共用茉莉黑茶体验装及饮料袋库存，不沿用旧活动数量。
  - 加购字段用0占位但标记未取得数据，不视为实测为0。ERP读取和售后恢复已完成，等待本地分配参数期间服务正常运行。

## 按需实现

- [ ] **对齐ERP命令的售后守卫接口**：`cli.js` 的 `resolve-components` / `resolve-stock` 仍调用 `releaseErpLock()`，而共享模块现仅导出 `ensureAftersalesPaused()` / `resumeAftersales()`；需修复命令收尾接口并验证暂停/恢复语义。

- [ ] **mergeStock 支持**：允许把两个 ERP 商品名合并为同一 `displayName`。当前动态目录按 ERP 原名分别建列；只有真实活动再次出现同一库存被多个 ERP 名拆分的场景时再实现，不为假设场景预建抽象。

已完成批次和阶段证据统一见 `docs/archive/README.md`；当前算法、数据和ERP规则见 `docs/operations.md`。
