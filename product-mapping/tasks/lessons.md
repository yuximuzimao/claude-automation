# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

## Lesson: readAllCorrespondence 有下载副作用，纯查询用 readCorrWithoutDownload

**代码层**：`readAllCorrespondence(erpId, shopName)` 内部调用 `downloadPlatformProducts()`，会触发 ERP 对应表的"下载平台商品"弹窗操作。不是只读操作。

**拆分后**：
- `readAllCorrespondence()` = navigate + download + read（check.js 用，需要刷新数据）
- `readCorrWithoutDownload()` = navigate + read（单品查询用，不触发下载）
- `readCorrespondence(erpId, shopName, productCode)` 现在调用 `readCorrWithoutDownload`（无副作用）

**触发时机**：任何仅需"读取对应表数据"而不需要"刷新/重新下载商品列表"的场景，必须用 `readCorrWithoutDownload`，禁止用 `readAllCorrespondence`。

---

## Lesson: 货号 ≠ platformCode，概念必须区分

**货号（productCode）**：ERP 对应表的主键，如 `yxxhtz`、`yxjm-zl`。JingLing 活动中用于标识一个产品。
**platformCode**：SKU 级别标识符，如 `0509-1`、`yxjm-1`。是 `data/imgs/` 的文件名。

**用货号查图片必须先经过 sku-map**：货号 → sku-map → platformCode → `data/imgs/{platformCode}.jpg`。禁止用货号直接拼图片路径。

**查 sku-map 路径**：`data/products/{brand}/sku-map.json`，键 = productCode，值含 skus 数组（含 platformCode）。

---

## Lesson: 行动前必须 trace 实际依赖链，不能从调用方推断被调用方的需求

**错误现象**：要测试 download 操作，却去开了鲸灵 tab，原因是"CLI 入口需要两个 tab"。

**根本原因**：用调用方视角（CLI 结构）直接替代被调用函数的实际需求，没有读 `lib/ops/download-products.js` 的函数签名就行动。

**铁律**：行动前先读目标函数签名及其直接依赖，确认实际需要哪些资源。不能从外层入口逆推内层需求。

**具体规则**：
- `downloadProducts(erpId, shopName)` 只需 ERP tab，不需鲸灵 tab
- `listActiveProducts(jlId)` 才需要鲸灵 tab
- 判断依据：读函数参数列表，不是看 CLI `getTargetIds()` 的调用
