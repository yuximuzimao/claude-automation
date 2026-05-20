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
