# 教训记录

## L1 产品目录不能静态维护（2026-05-14）

**背景**：product-columns.json 最初是手动维护的 KGOS 专属目录（20条）。跑百浩创展（RITEKOKO品牌）时，resolvedSkus=0，因为 ERP 子品名找不到对应的 displayName。

**根因**：静态目录与店铺强绑定，换一个品牌就要手动加条目，违背"单次用完就丢"原则。

**修复**：resolve-components 运行时动态发现 ERP 子品名，直接用 ERP 原名作 displayName，写入 product-columns.json。clearCache() 刷新同进程缓存，确保后续 resolve-stock 读到最新目录。

**铁律**：
- product-columns.json 每次 resolve-components 清空重建，不手动维护
- resolve-components 必须先于 resolve-stock（stock 查询依赖目录做名称映射）
- 所有 data/ 文件均为运行时产出，全部加入 .gitignore

## L2 resolve-components 必须与 check.js 路径完全一致（2026-05-20，修正旧错误假设）

**旧错误记录**（已证伪）：~~readCorrWithoutDownload 返回 0 行，改用逐货号精确搜索~~

**真实情况**：readCorrWithoutDownload 工作正常，返回全量数据。旧路径（逐货号精确搜索 + 自写 readTableRows）与 check.js 路径不同，archive 查询逻辑也有差异，导致 0/56 resolved。

**根因分析**：
1. `archive.js` 的 `if (d.error) return null` 错误：count=-1（Vue未就绪瞬态错误）和 count=0（真实不存在）都返回 null，retry 从未触发
2. resolve-components 用了完全不同于 check.js 的对应表读取路径，导致找不到 erpCode

**正确路径**（与 check.js 完全一致）：
```
readCorrWithoutDownload(erpId, shopName)
  → 过滤 uniqueHuohao，建立 huohao::normalizedSkuName → erpCode 索引
    → initArchiveComp(erpId)
      → queryArchive(erpId, erpCode) 逐个查询（erpCode 去重）
```

**铁律**：resolve-components 的 ERP 查询逻辑永远与 check.js 保持一致，不自行重写。如果两者行为出现差异，优先怀疑 resolve-components 的路径是否偏离。

## L3 archive.js 错误分类：count=0 vs 瞬态错误（2026-05-20）

**现象**：档案V2查询出现 `dataList 为空 (count=-1)` 时，旧代码 `if (d.error) return null` 一律返回 null，retry 永远不触发。

**根因**：两种不同错误被同等对待：
- `count=0`：精确查询无结果，真实不存在 → 应返回 null
- `count=-1`（或其他）：Vue 组件未就绪等瞬态错误 → 应 throw，触发 retry

**修复**：
```javascript
if (d.error) {
  if (d.count === 0) return null; // 真实不存在
  throw new Error(`${d.error} (count=${d.count})`); // 瞬态，交给 retry
}
```

**所在文件**：`../product-mapping/lib/archive.js`（共享模块，两个项目都受益）

## L4 parse 前校验供应商ID防止脏数据（2026-05-20）

**背景**：加购 Excel 可能混入其他店铺数据（供应商ID不同），导致数据污染。

**解决**：`parse --supplier-id <id>` 在解析后立即校验所有行的供应商ID，任一不匹配立即 abort，要求人工处理。

**实现**：`lib/validate-supplier.js`，读 cart-adds.json 校验 supplierId 字段。Excel 必须包含「供应商id」列。

**铁律**：跑任意店铺时，必须传入 `--supplier-id`。商家ID需从 ERP 后台右上角实时读取，不能凭记忆。

## L5 店铺名不能靠默认值——供应商ID→店铺名自动推导（2026-05-22）

**事故**：共途 KGOS 库存分配时，`resolve-components` 默认 `--shop 澜泽`，读了错误店铺的对应表，43/60 匹配（漏 17 个 SKU）。换杭州共途后 57/60（差 3 个是 erpCode 为空的数据问题）。

**根因**：parse 步骤已经校验了供应商ID=42528（共途），但 resolve-components 没有利用这个信息，用了硬编码默认值「澜泽」。不同店铺的对应表数据不同，会静默产生错误结果。

**修复（三板斧）**：

1. **供应商ID → 店铺名映射表** `data/supplier-shop-map.json`：持久化映射 `{ "42528": "杭州共途" }`，新供应商在此注册
2. **parse 步骤写 supplierId 到 `_meta`**：`parse-cart-adds.js` 取第一个非空 supplierId 写入 `_meta.supplierId`
3. **resolve-components 自动推导店铺**：`getShopFromCartData()` 从 `cart-adds.json` 读 supplierId → 查映射表 → 得店铺名。映射表未覆盖时立即报错（而非静默用默认值），强制人工确认一次
4. **反向验证硬门禁**：`matchedSkus < totalSkus` 时 `process.exit(1)`，列出所有未匹配 SKU，不给错误数据进入 calculate 的机会

**铁律**：
- 店铺名永远不设默认值——要么从映射表推导，要么 `--shop` 显式传入，要么报错
- resolve-components 后反向验证：所有加购 SKU 必须全部匹配，否则中止流水线
- 新供应商接入第一步：在 `supplier-shop-map.json` 注册映射
- 大模型的角色：处理异常（如映射表未覆盖的新供应商）、审计最终结果、反向数据测试
