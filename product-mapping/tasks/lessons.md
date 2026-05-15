# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

## Lesson: ERP 展开行后必须 waitFor 等 Vue mount 完成再 click

**现象**：`icon.click()` 展开行返回 `"expanded"` 成功，但紧接着 `links[j].click()` 触发弹窗，CDP `Runtime.evaluate` 返回 `{exceptionDetails: {text: "Uncaught"}}`。  
**根因**：Vue 组件异步 mount，mount 期间产生 unhandled rejection，Chrome 把这个异常附到当前 evaluate 的 exceptionDetails 里返回。  
**误判过程**：先以为是代码逻辑 bug → 加 try-catch → 以为是 session 污染 → 加 noop eval → 以为是坐标点击问题 → 改成 elementFromPoint → 浪费了大量时间。  
**正确做法**：展开后用 `waitFor` 轮询「换」链接 `getBoundingClientRect().height>0`，确认 Vue 完全 mount 后再 click。

---

## Lesson: 同一 ERP Tab 绝对不能并发跑多个 Node.js 进程

**现象**：同时跑 `remapSku` 后台进程 + 调试脚本，两个进程的 `cdp.eval` 交叉执行，页面 JS 状态被破坏，出现 `Uncaught` 错误。
**误判**：把并发干扰导致的运行时错误当成代码逻辑 Bug，花了大量时间查代码。
**正确做法**：单 Tab ERP 操作，前一个 Node.js 进程退出后再跑下一个。诊断时也只跑一个进程，不并发。

---

## Lesson: readAllCorrespondence 有下载副作用，纯查询用 readCorrWithoutDownload

**代码层**：`readAllCorrespondence(erpId, shopName)` 内部调用 `downloadPlatformProducts()`，会触发 ERP 对应表的"下载平台商品"弹窗操作。不是只读操作。

**拆分后**：
- `readAllCorrespondence()` = navigate + download + read（check.js 用，需要刷新数据）
- `readCorrWithoutDownload()` = navigate + read（单品查询用，不触发下载）
- `readCorrespondence(erpId, shopName, productCode)` 现在调用 `readCorrWithoutDownload`（无副作用）

**触发时机**：任何仅需"读取对应表数据"而不需要"刷新/重新下载商品列表"的场景，必须用 `readCorrWithoutDownload`，禁止用 `readAllCorrespondence`。

---

## Lesson: check 必须全量重写 sku-records，不能 patch 旧文件

**根因**：旧逻辑只给 sku-records 里已有记录打 scope/erpCode 补丁，导致旧记录里 erpCode=null 的已匹配 SKU 被 getTodo() 误判为"未匹配"再跑一遍。

**正确做法**：check 结束时以本次 ERP 实时对应表数据**全量重写** sku-records.json，不读旧文件做 patch。每次 check 后文件即为当前批次的完整干净数据源，recognition 字段从旧文件读取后写回（保留识图结果）。

---

## Lesson: 新匹配任务开始前的清空规则（已固化到代码）

**判断标准**：对下次匹配有没有任何作用。

| 数据 | 清空时机 | 原因 |
|------|---------|------|
| `data/imgs/*.jpg` | check 开始时自动清空 | 旧活动图片，下次活动换新图，留着是干扰 |
| `data/reports/*.json` | check 开始时自动清空 | 历史报告，对下次无用 |
| `auto-match-log.json` done[] | match 开始时自动清空 | 旧活动 platformCode 全新，旧 done 只会误过滤 |
| `auto-match-log.json` failed[] | match 开始时自动清空 | 历史错误，干扰本次统计排查 |
| `sku-records.json` | 无需手动清，check 全量重写 | check 以 ERP 实时数据覆盖 |

**以上清空均已固化到代码**（check.js 开头清空 imgs/+reports/；auto-match2.js main() 开头清空 done[]+failed[]）。

---

## Lesson: 店铺侧边栏匹配必须用 .includes()，不能用 ===

**根因**：ERP 侧边栏文字是「百浩创展」，传入 shopName 是「百浩」，`===` 精确匹配失败。问题存在于 copy-as-suite / mark-suite / create-suite / read-erp-codes / read-skus 共 5 个文件，已全部修复（2026-05-13）。

**铁律**：所有操作 ERP 店铺侧边栏的代码，一律用 `.includes(shopName)`，禁止 `===`。

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
