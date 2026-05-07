# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

## Lesson: 行动前必须 trace 实际依赖链，不能从调用方推断被调用方的需求

**错误现象**：要测试 download 操作，却去开了鲸灵 tab，原因是"CLI 入口需要两个 tab"。

**根本原因**：用调用方视角（CLI 结构）直接替代被调用函数的实际需求，没有读 `lib/ops/download-products.js` 的函数签名就行动。

**铁律**：行动前先读目标函数签名及其直接依赖，确认实际需要哪些资源。不能从外层入口逆推内层需求。

**具体规则**：
- `downloadProducts(erpId, shopName)` 只需 ERP tab，不需鲸灵 tab
- `listActiveProducts(jlId)` 才需要鲸灵 tab
- 判断依据：读函数参数列表，不是看 CLI `getTargetIds()` 的调用
