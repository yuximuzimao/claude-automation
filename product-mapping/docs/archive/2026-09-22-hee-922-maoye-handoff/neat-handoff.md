# 悦希 9.22 跨店铺商品匹配 — NEAT 交接

日期：2026-09-22

## 已完成

### 蘅圆

- 48 个货号 / 94 SKU。
- 全量识图已由用户核对。
- 正式匹配结束，final check：
  - recognitionDone = 94
  - comparisonMatch = 94
  - comparisonMismatch = 0
  - comparisonPending = 0
  - pendingVisualReview = 0
  - unmatchedAwaitingMatch = 0
- 可复用识图快照：`../2026-09-21-hengyuan-hee-922/recognition-snapshot.json`。
- 平台原图识图规则、参考图边界、`imgUrl` 原图直链渠道已经进入现行 `docs/INDEX.md`。

### 库存分配

- 蘅圆 94 SKU 库存分配已完成并归档到 `../../../sku-calculator/docs/archive/2026-09-21-hengyuan-hee-922-allocation/`。
- 最终 Excel 保存在用户桌面。
- 当前库存页新版路由已经确认是 `#/stock/newstatu_next/`；2026-09-21 只读验证表明 Vue store 仍有 `title` / `availableStock`。

## 懋业当前未完成状态

- 鲸灵账号：17。
- 已实时确认：杭州懋业电子商务有限公司，商家 ID 43306。
- 首次 check 已成功读取鲸灵真实活动范围：42 个货号。
- ERP 懋业对应表只读成功：130 个货号 / 204 SKU / 204 张平台图。
- 本轮明确跳过 ERP“下载平台商品”，没有重复下载。

两次首次 check 都在“商品档案V2”阶段停止：

1. 旧路由 `#/prod/parallel/` 已迁移为 `#/prod/parallel_next/`。
2. 修正路由后，新版页面不再暴露旧的 `handleQuery/dataList` 上层 Vue 结构。

当前证据边界：

- **尚未生成懋业 check 报告。**
- **尚未将运行态 `sku-records.json` 重写成懋业。**
- **尚未对懋业执行任何 ERP match 写入。**
- 因此蘅圆当前运行态和独立 recognition 快照都未被破坏。

新版档案页只读探针已验证：

- “主商家编码/规格商家编码”输入框仍存在。
- 可见“查询”按钮可触发查询。
- 结果可从可见 `.el-table.__vue__.store.states.data` 读取。
- 主表当前可见“子商品信息”列；数字链接仍存在，但旧 class `a.ml_15` 已消失。
- 子商品弹窗的稳定读取基准仍应是表头 `商品名称 / 商家编码 / 组合比例`。

## 三项目 / 两 ERP 页面兼容

### 商品匹配 `product-mapping`

需复核/适配：

- `lib/navigate.js`：商品档案V2路由已经改为 `#/prod/parallel_next/`；库存状态共享路由已改为 `#/stock/newstatu_next/`。
- `lib/archive.js`：旧 `handleQuery/dataList` 与 `a.ml_15` 需要按新版结构做最小兼容。
- `lib/fetch-archive-names.js`：仍直接依赖旧 `dataList/pageData/handleQuery`，需同步适配，不得只修 check 主链。
- 相关测试与当前文档要随最终实现一起校正。

### 库存分配 `sku-calculator`

- `resolve-components` 间接依赖商品匹配的 `archive.js`，无需复制一套档案逻辑。
- `lib/query-stock.js` 直接读取库存状态页。新版实测数据字段仍是 `title` 与 `availableStock`；待用户调整页面列后再做一次正式回归。
- 分配算法本身不改。

### 售后 `aftersales-automation`

- `lib/erp/navigate.js` 仍是旧商品档案V2路由。
- `lib/product/archive.js` 有独立的一套旧 `handleQuery/dataList/a.ml_15` 实现，必须同步最小适配。
- 修改后必须跑售后完整测试并按项目规则安全重启；不得自动重跑历史工单。

## 下一会话执行顺序

1. 用户先按本轮给出的“脚本所需数据 → 页面字段/列头”清单调整新版 ERP 页面列顺序/列标题。
2. 回读两个页面当前 DOM/表头，确认用户配置结果。
3. 一次性最小修正三个项目相关脚本；先只读探针和测试，不做 ERP 写入。
4. 重跑懋业首次 check：42 个真实活动货号、`brand=hee`、skip-download。
5. 从蘅圆 recognition 快照向懋业当前范围做 **`productCode + platformCode` 精确交集复用**；目标店铺没有的收单王链接自然忽略，不人为补进范围。
6. 核对首次 check：已有匹配不得有 mismatch；未匹配属于正常待处理。
7. 用户本轮已明确授权：首次 check 和识图复用正确后，直接对剩余未匹配项执行 `match --shop 懋业`；异常仍 fail-fast。
8. 最后执行 `check --shop 懋业 --reuse-active --skip-download`。
9. 完成门禁：recognitionDone = comparisonMatch = 目标 SKU 总数；comparisonMismatch / comparisonPending / pendingVisualReview / unmatchedAwaitingMatch 全部为 0。

## 不要恢复的旧做法

- 不用 SKU 名/图片文字覆盖平台原图实物识图。
- 不把参考图当具体 SKU 绑定真值。
- 不为第二店铺重新下载已经存在的 ERP 平台商品。
- 不把蘅圆的 ERP 匹配状态直接复制到懋业；只复用同复合键 recognition。
- 不在用户调整新版页面字段前继续猜 DOM 做大改。
