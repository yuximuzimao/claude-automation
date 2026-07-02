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

1. **供应商ID → 店铺名映射** 通过共享模块 `aftersales-automation/lib/erp/shop-map.js`（`getErpShopBySupplierId()`），新供应商在此注册 `supplierId` 字段
2. **parse 步骤写 supplierId 到 `_meta`**：`parse-cart-adds.js` 取第一个非空 supplierId 写入 `_meta.supplierId`
3. **resolve-components 自动推导店铺**：从 `cart-adds.json` 读 supplierId → 查共享 shop-map.js → 得店铺名。映射表未覆盖时立即报错
4. **反向验证硬门禁**：`matchedSkus < totalSkus` 时 `process.exit(1)`，列出所有未匹配 SKU

**铁律**：
- 店铺名永远不设默认值——从 shop-map.js 推导、`--shop` 显式传入、或报错
- 新供应商接入第一步：在 `aftersales-automation/lib/erp/shop-map.js` 注册 `supplierId`

## L6 满赠货号自动展开 + 受限单品 80/20 + SKU保底预扣（2026-05-22 ~ 2026-05-23）

**背景**：共途活动有 4 个满赠货号（0525zp1~4），每个 500 件。对应表显示 4 个货号共 13 个 SKU。但帆布袋（库存 1312）/冰霸杯（库存 1255）库存不足，赠品需求远超可用量，且旧算法赠品不足直接报错，或赠品吃光库存导致正常 SKU 分配到 0~4 件。

**修复（三板斧）**：

1. **货号自动展开**（`resolve-components.js`）：赠品配置只需填货号，运行后自动从 ERP 对应表查找该货号下所有 SKU（`corrAll` Map 查询 O(1)），生成完整配置写回 `gift-sku-config.json`。防重复展开（已含 skuName 的配置跳过）。

2. **受限单品 80/20 分账**（`allocate.js` Phase G）：赠品最多占单品库存的 `stock × (1-reserve)`（默认 80%），超出时等比例缩减。提取 `reduceAllocs()` 通用迭代缩减逻辑（保底和赠品共用）。

3. **Phase M SKU 保底预扣**（`allocate.js`）：每个正常 SKU 至少 `coldFixed` 件（默认 5），从全量库存预扣，优先级高于赠品。受限单品按比例缩减。

**核心架构**：`Phase M（全量预扣 5 件） > Phase G（赠品 ≤ stock×80%） > reserve（剩余 ×80%） > Phase A-C`

**关键实现细节**：
- LRM 回填排序用 `invFloat % 1`（浮点余数），不能用 `invFloat - inv`——后者因 minInv 导致 inv 大于 invFloat，排序为负
- intRem 仅扣 Phase A 分配量（`Math.floor(invFloat)`），minInv 已在 Phase M 预扣，不能重复

## L7 多项目 ERP 浏览器互扰导致 resolve-components 全量失败（2026-05-23）

**事故**：连续两次 `resolve-components` 失败，第一次 0/73 resolved（72 errors），第二次对应表返回 0 行。两次都在用户刷新页面后才恢复。

**根因**：`aftersales-automation` server 进程持有同一 Chrome 的 ERP tab，两者共享 CDP target。售后系统的 DOM 操作导致 resolve-components 依赖的 Vue 组件状态被破坏：
- 档案V2 的 `dataList` 在第一个查询后变为 unreachable（`count=-1`，Vue 组件消失）
- 对应表页面被售后系统导航到其他页，`el-table__row` 数量归零

**修复三板斧**：
1. **跑 sku-calculator 前先停售后 server**：kill 掉 aftersales 进程，避免 CDP target 冲突
2. **失败后刷新页面**：resolve-components 异常中止后，需在 Chrome 中手动刷新对应表和档案V2两个页面
3. **禁止两个项目同时操作同一 ERP target**：这是根目录 CLAUDE.md 「禁止并行」规则的跨项目扩展

**诊断信号**：
- `展开: 20/0` → 对应表页面状态异常（表有分页但无数据行），刷新对应表页面
- `dataList 为空 (count=-1)` 全量出现 → 档案V2 Vue 组件状态丢失，刷新档案V2页面

## L8 resolve-components 部分失败可手工补丁，不必全量重跑（2026-06-04）

**背景**：百浩创展活动跑 resolve-components，48/53 resolved，5条失败：2条因加购表与对应表名称不一致（对应表有赠品括号后缀），3条因商家编码是特殊规格条码（档案V2 查不到）。全量重跑会清空已有的 48 条正确数据，且重跑也不会解决根因。

**解法（三类补丁路径）**：

1. **名称不一致** → 单独调 `queryArchive(erpId, erpCode)` + `querySubItems()` 拿实际子品明细，写入 sku-components.json。对应关系由用户确认。
2. **特殊规格编码查不到** → 按同货号已有 SKU（2支/4支）的 components 等比反推 1支版本。
3. **新增单品**（如托特包-蓝）→ 同步追加 product-columns.json，colIndex 接续现有最大值+1。

**补丁完成后必须执行的验证**：
```javascript
// 确认 key 数量 == totalSkus
const keys = Object.keys(sc).filter(k => k !== '_meta');
assert(keys.length === sc._meta.totalSkus);
// 确认 resolvedSkus/matchedSkus 已更新为 totalSkus
assert(sc._meta.resolvedSkus === sc._meta.totalSkus);
// 确认 warnings 已清空
assert(sc._meta.warnings.length === 0);
```

**铁律**：
- 补丁要同步更新 `_meta`（matchedSkus、resolvedSkus、warnings 清空）并加 `_manualOverrides` 字段记录每条补丁来源
- 补丁完成后直接跑 `resolve-stock → calculate → report`，不重跑 resolve-components（会清空补丁）
- 临时 queryArchive 脚本写完即删，不进 git

## L9 加购 SKU 变体名含平台后缀导致 resolve-components 全量 0 匹配（2026-06-23）

**背景**：茗瑞 KGOS 首次跑 resolve-components，37/37 全部未命中。

**根因**：鲸灵"商品数据"页面的规格列格式为 `美式风味咖啡 6盒送2盒到手8盒;KGOS`，分号后面是平台标签。`corrIndex` 构建时（第71行）正确地 `.replace(/;.*$/, '')` 去掉了分号，但匹配时（原第144行）只做了空格规范，**漏掉去分号**，导致 key 带着 `;KGOS` 无法命中任何条目。

**修复**：`resolve-components.js` 第144行匹配前同样加 `.replace(/;.*$/, '')`。

**诊断信号**：全部37条警告内容格式均为 `货号::…;KGOS`（带分号后缀）→ 立即检查加购数据来源是否来自鲸灵 SKU 明细页（该平台导出规格名带平台标签）。

## L10 resolve-stock pageSize 硬编码导致翻页重复读取（2026-06-23）

**背景**：`resolve-stock` 连续两次报 `数据不完整: 读取 724 条，ERP 显示共 181 条`。

**根因**：`query-stock.js` 硬编码 `PAGE_SIZE = 50`，但 ERP 库存状态页的每页条数实际被设为 200。`ceil(181/50)=4` 翻了4页，每页都读到全量181条，累计 724。

**修复**：改为运行时读页面实际 pageSize（`.el-pagination .el-select .el-input__inner` 的 value），fallback 50。

**诊断信号**：读取条数 = 期望条数 × N（N 为整数倍）→ 翻页逻辑与实际 pageSize 不符；去 ERP 页面底部核查每页显示条数和总条数。

## L11 CDP Session 过期恢复（2026-07-02）

**现象**：`agent-browser --cdp 9222 eval` 全部报 `Session with given id not found`，`tab list` 正常但无法执行任何 eval。

**根因**：Chrome 重启或长时间闲置后 CDP WebSocket session 过期，agent-browser 缓存的 session ID 失效。

**修复**：
```bash
agent-browser close   # 清理过期 session，杀掉残留 daemon
agent-browser --cdp 9222 eval 'document.title'   # 重新连接
```

**铁律**：agent-browser 操作报 session 错误时不要绕路（写 WebSocket 直连脚本），先 `close` 再重连。

## L12 鲸灵 SKU 明细页使用 Element UI 多 Table 布局（2026-07-02）

**现象**：按 `feedback_sku_cart_scraping.md` 的 td 索引读取，td[2] 返回的是数字（浏览量）而非规格名，td[3-5] 为空。

**根因**：鲸灵商品数据 SKU 明细页使用 Element UI 多 `<table>` 并行渲染，页面有 5 个 tbody，每个 tbody 只渲染部分列。数据列（规格/加购人数/加购件数/支付件数）全部集中在 tbody[4]（0-based），而 tbody[0] 只有排名+商品+浏览量。`document.querySelectorAll('.el-table__row')` 会混合返回所有 tbody 的行，td 索引完全错位。

**修复**：
1. 先 inspect 各 tbody 的列结构（找哪个 tbody 包含规格/加购件数/支付件数）
2. 只从目标 tbody 中 querySelectorAll
3. 列映射：td[1]=商品, td[2]=规格, td[3]=加购人数, td[4]=加购件数, td[5]=支付件数

**诊断信号**：抓取到的 td[2] 是数字而非规格名 → 读错了 tbody。立即 inspect 所有 tbody 的结构。
