# 商品匹配核查 — 操作规则

---

## §1 角色与红线

- **写操作（新增匹配）必须人工确认后执行**，脚本只读不写
- ERP 查询命令必须串行，禁止并行（对应表 + 档案V2 顺序执行）
- 每次查询等待 2000ms

---

## §2 核查流程（完整端到端）

**命令序列**（每次新活动按此顺序执行）：

```
① node cli.js check --shop <店铺>   ← 扫描+标记（自动完成以下子步骤）
② 我（Claude）识图                   ← 人工步骤，写入 sku-records.json
③ node cli.js match --shop <店铺>   ← 自动匹配（异常立即停止）
④ node cli.js check --shop <店铺>   ← 重新扫描+对比报告
```

**各步骤明细**：

```
① check 内部流程:
   1.1 鲸灵商品列表 → 筛选「特卖在售中」→ 抓取活动货号（处理范围）
   1.2 ERP 商品对应表 → 下载平台商品（选店铺+全量下载+等待完成）
   1.3 ERP 商品对应表 → 选店铺 → 展开所有行 → 读SKU映射 + 图片URL
   1.4 下载 SKU 图片到 data/imgs/，标记匹配/未匹配
   1.5 商品档案V2 → 按ERP编码查类型+子品明细
   1.6 合并识图结论（visual-verdicts.json）→ 保存报告
   报告输出：recognition + comparisonResult + comparisonDetail 字段

② 我识图:
   - 读 visual-pending 查看待识图列表
   - Read 工具加载图片，对照 features.json 规则
   - visual-ok / visual-flag 记录结论 → 更新 sku-records.json

③ match 内部流程:
   - Phase 1: 组合装 → 勾选 → 标记套件 → 逐个复制为套件
   - Phase 2: 单品 → 逐个 remapSku
   - 任何错误立即停止（stop-on-error），已完成的自动跳过

④ 第二次 check = 重新扫描 + 对比:
   - 同①，此时 SKU 已有 erpCode
   - comparisonResult: 识图预测 vs 档案实际 → match/mismatch
   - 若有 mismatch，人工核查
```

**异常处理原则**：
- match 任何 SKU 报错 → 立即 throw 停止，人工处理后重跑（done 列表防止重复）
- check 读取异常（ERP 未登录、页面无法访问）→ navigateErp 已处理，手动刷新登录后重跑
- comparisonMismatch > 0 → check 报告会警告，需人工核查后继续

---

## §3 视觉匹配（Claude 亲自执行，不写识别脚本）

**为什么不用脚本**：组合装图片有多商品、部分遮挡、角度差异，脚本无法做到100%准确。

**执行方式**：
- `check.js` 下载 SKU 图片到 `data/tmp/imgs/` 并保留 imgUrl
- 我通过 Read 工具加载图片，直接目视识别内容
- 对照 `data/products/features.json` 的视觉特征描述辅助判断
- 输出结论：商品名称 + 数量 + 置信度（高/低/无法判断）

**识图步骤**：
1. 读 SKU 名称（如"益生菌6盒+冰霸杯1个+玉米片10包+一次性吸管袋1盒"）→ 确定应有商品
2. Read 工具加载图片
3. 对照 features.json 描述逐一确认图中每个商品
4. 报告：每个商品是否在图中可见，数量是否一致

**参考图库**：`data/products/{brand}/*.jpg` — 单品标准图，命名 = 商品名称（如 `data/products/kgos/益生菌.jpg`、`data/products/hee/悦颜霜.jpg`）

**配件不识图**：礼盒/礼袋/雪梨纸等不可见配件**不在识图范围内**，由系统在 annotate 步骤读取 `data/products/{brand}/accessories.json` 自动注入。识图时只记录图片中**可见**商品。

---

## §4 商品参考库维护规范

### 目录结构（多品牌）

```
data/products/
  kgos/            ← KGOS 品牌（原有文件）
    features.json  ← 商品视觉特征库
    益生菌.jpg
    ...
  hee/             ← 悦希（HEE）品牌
    features.json  ← 商品视觉特征库
    accessories.json ← 不可见配件规则（每次活动更新）
    悦颜霜.jpg
    ...
```

### 图片维护规范

- 文件名用商品中文名（如 `益生菌.jpg`、`黑茶体验装-茉莉花茶味.jpg`）
- 同款不同规格：正装无后缀、体验装加"体验装"前缀
- **每次新增图片必须打开确认内容与文件名一致**（教训：预存 `益生菌.jpg` 实为阻断片）

### features.json 维护规范

- 视觉特征记录在 `data/products/{brand}/features.json`，字段：`erpName`（必填）、`颜色`、`特征`、`别名`
- `erpName` 必须与 ERP 档案V2 精确一致，脚本做 Set 等值比对

### accessories.json — 不可见配件规则（悦希专用）

**用途**：声明哪些货号（productCode）在 ERP 套件中含有图片不可见的配件（礼盒/礼袋/雪梨纸等）。
**更新时机**：每次活动前，由用户直接编辑 `data/products/hee/accessories.json`。
**注入时机**：annotate 步骤自动读取，追加到 recognition.items，识图不需要手动处理配件。

```json
{
  "_meta": { "campaign": "2026年X月活动", "lastUpdated": "YYYY-MM-DD" },
  "rules": {
    "yxxh-cx": {
      "note": "修颜四件组礼盒套装",
      "accessories": [
        { "erpName": "HEE悦希印花礼盒（天地盖）白色", "qty": 1 },
        { "erpName": "HEE悦希印花礼袋-白", "qty": 1 },
        { "erpName": "HEE悦希雪梨纸", "qty": 2 }
      ]
    }
  }
}
```

**注意**：
- `erpName` 必须与 features.json 中的 erpName 完全一致（脚本精确匹配）
- 键 = productCode（货号），同一货号下所有 SKU 共享配件规则
- 配件商品本身也需要在 features.json 中有条目（ERP 搜索时需要精确名称）
- 示例条目（`_` 开头的键）会被自动过滤，可保留作为格式参考

---

## §5 技术操作规范

### ERP 页面导航（navigate.js）

**每次 ERP 操作前必须走完整流程**：`location.reload()` → 等5s → 检登录（`.inner-login-wrapper`）→ 点顶部 tab → 验 hash → 等 Vue mount。直接 `cdp.navigate` 跳过 reload 会导致页面状态残留，读到脏数据。

### 档案V2 搜索（DOM 输入法，非 window.__sv）

**不能直接赋值** `window.__sv.searchData.outerId = code` —— Vue 双向绑定不触发，`handleQuery()` 拿到旧值或空值。

**正确做法**：
1. 找 `input[placeholder="主商家编码"]`
2. 设 `.value = code`，dispatch `input` + `change` 事件
3. 从 input 向上遍历最多12层父元素，找到有 `handleQuery` 方法的 Vue 组件
4. 调用 `vm.handleQuery()`

### 档案V2 编码类型

**不区分 EAN-13 条形码**：`6979499760044` 之类的纯数字编码也存在 `outerId`（主商家编码）字段，不走 `skuOuterId`。原来的 `isBarcode()` 分支已删除，全部走 `outerId`。

### 子品明细读取

列索引固定：`cells[1]`=商品名称，`cells[3]`=商家编码，`cells[10]`=组合数量。关闭弹窗用 `button.el-dialog__closeBtn`（不是 `el-dialog__headerbtn`）。

### 对应表图片收集

图片列 class 名每次导航后动态变化，不能硬编码。正确方式：逐段滚动（12步）触发懒加载，用 `platformCode`（cells[5].innerText）作为 key 建立 imgUrl 索引。

### 图片存储规范

- **统一路径**：`data/imgs/{platformCode}.jpg`，platformCode 即文件名，无需额外索引
- **覆盖范围**：`check.js` 对**所有 SKU**（包括未匹配）都下载图片，不只是已匹配的
- **查找方式**：知道 platformCode 直接拼路径，不需要在 JSON 里存 imgPath
- **禁止**：用 `dl_` 前缀或 `safeCode` 替换字符做文件名（历史遗留，已废除）

### SKU 数据文件规范

- **`data/sku-records.json`**：单文件存全量 SKU 元数据 + 识图结果，按 platformCode 索引
- **字段**：`productCode / shopName / skuName / platformCode / erpCode / erpName / imgUrl / recognition / scope`
- **`scope` 字段**：
  - `"active-YYYY-MM-DD"` = 该日期 check 运行时确认的活动在售 SKU
  - `"history"` = 历史活动遗留，不在当前核查范围
  - check.js 运行后自动更新；手动可用 auto-match-log + check 报告补全
- **`recognition` 字段**：识图后写入，格式 `{type:"单品"|"组合装", items:[{name,qty}], raw:"描述"}`
- **禁止**：在 JSON 里存 `imgPath`（可从 platformCode 推导，存了是冗余）
- **`data/visual-verdicts.json`**：识图结论（ok/mismatch），独立于 sku-records.json

### 视觉匹配数据契约

- 匹配基准：ERP 档案的**精确名称**，不是 SKU 名称
- 单品：`archiveTitle × 1`；组合装：`subItem.name × qty`（每个子品一条）
- 我输出的识图结果必须与上述精确字符串完全一致
- 脚本用 Set 等值比对，不做模糊匹配

### 翻页终止检测（鲸灵）

`btn-next` 按钮在最后一页**不会变灰**，不能用按钮状态判断。正确做法：读"共X条"总数推算总页数。

---

## §5.5 档案V2 商品类型筛选（普通商品）

**位置**：表头「商品名称」列旁的漏斗图标 `span.ui-datalist_cell-filter-icon`

**操作步骤**：
1. 点击 `span.ui-datalist_cell-filter-icon` → 下拉列表显示
2. 点击 `div.ui-datalist_filters-list-item`（文字="普通商品"）
3. 等待 3000ms，数据刷新
4. 验证：`sv.pageData.total` 应为 174（普通商品总数），`sv.searchData.itemType === 1`

**禁止**：用 `sv.searchData.itemType = "0"` 直接赋值——无效，真实 type 值是数字 `1`，且不能绕过 UI 筛选

**识图前必读**：`data/products/features.json`（含 erpName 精确名称 + 视觉特征）
- `erpName` = ERP 档案里的精确商品名称，脚本做 Set 等值比对，必须完全一致
- 识图输出格式：`erpName×数量`，每个子品一条，逗号分隔

---

## §5.6 对应表「套件处理→标记套件」操作规范

**流程**：
1. navigateErp → 商品对应表
2. 点左侧店铺名（如「澜泽」）
3. 平台商家编码输入框回车刷新（placeholder：`请输入商家编码，多个商家编码请以英文逗号分隔`）
4. 找货号行展开（点 `.el-table__expand-icon`）
5. **只勾选目标 SKU 那一行的复选框**，不勾选其他行
6. 点「套件处理」下拉 → 点 `li.el-dropdown-menu__item` 文字="标记套件"
7. 验证：目标行出现「复制为套件」按钮即成功

**⚠️ 红线**：每次只处理当前要匹配的那一个 SKU，严禁批量勾选整个货号所有子行。每个 SKU 是独立的商品/组合，必须单独处理。

---

## §6 已知坑位

> 格式：`[触发次数/最后触发]` — 说明

- `[1/2026-04]` **翻页溢出**：btn-next 不变灰，必须用"共X条"判断结束，否则死循环（实测抓558条，实际174条）
- `[1/2026-04]` **图片内容核查**：预存参考图片不可信任，每张图上线前必须打开目视确认
- `[1/2026-04]` **分页筛选残留**：切换筛选前必须先清空已有筛选，否则多条件叠加结果为0
- `[2/2026-04]` **档案V2 直接赋值失效**：`window.__sv.searchData = code` 不触发 Vue 响应，必须 DOM 输入法（见§5）
- `[1/2026-04]` **ERP 状态残留**：跳过 reload 直接操作读到上次的数据，所有页面操作前必须走 navigateErp()
- `[1/2026-04]` **对应表只读1条**：空搜索后未展开所有行，或页面状态未重置，导致只读到当前可见行
- `[1/2026-04]` **对应表搜索框按 platformCode 无效**：搜索框 placeholder 为「请输入商家编码」，实际只按货号（productCode）过滤，输入 SKU 的 platformCode（如 260422-37）不会筛选。正确做法：全量读取40行，按 `tds[6].innerText` 找目标货号行再展开
- `[1/2026-04]` **多层嵌套 dialog 确定按钮点错**：Element UI 多弹窗叠加时 querySelector 取到第一个隐藏 footer，必须用 `querySelectorAll('.el-dialog__footer')` 遍历取 `getBoundingClientRect().height > 0` 的那个，再点其 `el-button--primary`。禁止用 innerText 文字匹配（有的按钮是"确 定"带空格）
- `[1/2026-04]` **弹窗操作前未验证弹窗可见**：操作 dialog 内元素前必须先确认 wrapper 的 `getBoundingClientRect().height > 0`，否则操作到隐藏层
- `[1/2026-04]` **档案V2 查询前筛选残留**：`fetch-archive-names` 等操作会留下"普通商品"筛选，下次 `km-archive` 查组合装时返回 null。`initArchiveComp` 现已加「清空条件」步骤；通用原则：每次档案操作前必须检查/清空筛选状态
- `[1/2026-04]` **识图颜色规则必须执行**：features.json 记录了体验装口味颜色（浅绿=茉莉，淡黄=青柑），识图时若只看图片文字"黑茶体验装"而不看盒子颜色，会批量识别错误。规则：识图前必须逐条比对 features.json 颜色字段，视觉特征 > 文字标注
- `[1/2026-04]` **搜索 count 必须精确等于1**：自动匹配时 `count > 0` 宽松匹配会选中套件商品写为子品，早期 260422-73 等因此可能错误。规则：count !== 1 直接报错"名称歧义"，不继续
- `[1/2026-04]` **「选择商品」dialog v-show 状态残留**：dialog 关闭后 Vue 保留上次勾选（v-show 不销毁实例），再次打开时旧勾选仍在。每次打开弹窗后立即全选反选清零（`querySelectorAll("input[type=checkbox]:checked").click()`），再添加子品
- `[1/2026-04]` **商品类型下拉不能 UI 点击**：el-select 下拉 input 展开后 portal 在 dialog 外生成，触发 close-on-click-modal 关闭弹窗。正确做法：直接 Vue emit：`vm.$emit("input", value); vm.$emit("change", value)`
- `[1/2026-04]` **脚本长时间运行用 run_in_background**：`node lib/auto-match2.js` 同步跑时全量 stderr 输出消耗大量 token。正确：`run_in_background: true`，结束后只读 `data/auto-match-log.json` 的 done/failed 数字
- `[1/2026-04-30]` **对应表搜索输入框是 `.el-input-popup-editor input`**：form-item[4] 是"精确搜索"下拉框，form-item[5] 是"平台商家编码"下拉框，form-item[6] 的 `el-input-popup-editor` 才是真正的搜索输入框。把货号输入到下拉框会导致搜索无效、表格不刷新。`_setMainPageSelect` 索引：精确搜索=4，平台商家编码=5（排除 dialog 内的 select 后）
- `[∞/永久保留]` **#48 读表数据用<th>表头定位，禁用正则/长度过滤**：子品弹窗表读取必须通过 `<th>` 表头文本（"商品名称"/"商家编码"/"组合比例"）定位列索引。禁止硬编码固定位置 [1][3][10]，禁止对 specCode/name 做正则匹配过滤——会把非数字编码（kgoxnld等）合法行当垃圾误杀。
- `[1/2026-05-07]` **对应表图片列 = td[3]（左侧平台侧）**：sub-row 中 `imgs[0]` 在 td index 3，parent class `el-image el-popover__reference`。ERP 产品图若存在在 td[12]+（右侧）。`querySelector("img")` 取平台 SKU 图是正确行为。assertPlatformImageColumn() 断言：`img.closest("td")` 在同行所有 td 中 indexOf = 3。
- `[1/2026-05-07]` **货号 ≠ platformCode**：货号（productCode，如 yxxhtz）是 ERP 对应表的主键；platformCode（如 0509-1）是 SKU 级别标识，也是 data/imgs/ 的文件名。用货号查图片必须先查对应表获取 platformCode，不能直接拼路径。
- `[1/2026-05-07]` **readAllCorrespondence 有副作用**：内部硬编码调用 downloadPlatformProducts()，不是只读操作。仅查询数据时用 readCorrespondence()（待实现），需要刷新数据时才用 readAllCorrespondence()。
- `[1/2026-05-08]` **「选择商品」弹窗搜索返回2条结果不等于名称歧义**：气垫霜正装和替换装名称都包含"亮肤色"，ERP 弹窗是子串搜索，count=2 是正常的。wait-loop break 条件必须同时检查 `hasExact`（任意 td 的 innerText 精确等于 productName 即命中），不能只靠 count===1，否则10s 超时。行选择（r3）本就精确匹配，无需另改。
- `[1/2026-05-08]` **matched-original SKU 的 recognition 必须补填，不能留 null**：重跑 `--from annotate` 时，matched-original + recognition=null 会被 annotate 跳过，导致 itemType=null。识图阶段需要按 erpName/skuName 为这些条目补填 recognition.items，让 annotate 能正常生成 itemType。
- `[1/2026-05-13]` **全量下载选择是 el-radio，不是 el-checkbox**：下载平台商品弹窗里「全量下载」「增量下载」「指定下载」三个选项是 `el-radio` 组，默认选中「增量下载（value=2）」。代码若用 `.el-checkbox` + `input[type=checkbox]` 查找，永远 null，全量下载永远不被选中，静默跑增量。正确：`.el-radio` + `input[type=radio]`，查 checked 状态再 click。
- `[1/2026-05-13]` **ensureCorrPage 跳过 reload 导致残留 dialog 叠加超时**：`ensureCorrPage` 检测到 hash 已匹配时跳过 reload，仅清空搜索框。若前一次操作（如手动 inspect）留有未关闭 dialog，新 download dialog 叠加在顶层但 gone 检测（等所有 dialog 消失）永远不通过，导致 60s 超时。根治：download 操作前必须用 `navigateErp()`（强制 full reload），不能用 `ensureCorrPage`。

---

## §7 品牌建档 SOP（新品牌上线前必做）

> **入口**：开始前先读 `docs/preflight-brand.md` checklist，确认全部通过再进入下一步

### 什么时候需要做品牌建档？

- 首次对一个品牌做视觉核查（如本次 HEE）
- 品牌添加了新产品（对 features.json 做增量更新）
- 数据被污染需要重建

### 完整流程（Step 0 → Step 6）

```
Step 0: 清空旧数据工作区
  - 直接清空（无需备份）：rm -f data/imgs/*
  - 直接重置：echo '{}' > data/sku-records.json
  - 清空 data/products/{brand}/sku-map.json（如果存在）
  - （data/imgs/ 是一次性工作区，每次 check 重新下载，不保留历史）

Step 1: 获取全量数据
  - 跑 node cli.js check --shop <店铺>
  - 产出：data/imgs/（SKU 图片）+ data/reports/check-{shop}-{date}.json
  - 注意：check 会自动下载图片，这是唯一合法的图片来源

Step 2: 建立 sku-map（货号→platformCode 追踪台账）
  - 从 check 报告提取所有产品的 {productCode → [{platformCode, skuName, erpCode, erpName}]}
  - 存入 data/products/{brand}/sku-map.json
  - 当前手动执行；第三个品牌建档时实现自动化脚本

Step 3: 下载/整理参考图片
  - 目标：data/products/{brand}/*.jpg（单品标准图，命名=商品中文名）
  - 来源：从 data/imgs/ 中找对应 platformCode 的图片复制
    - 查 sku-map：商品中文名 → 货号 → platformCode
    - cp data/imgs/{platformCode}.jpg data/products/{brand}/{商品名}.jpg
  - "不在对应表"的产品：需额外获取图片（见下方异常处理）

Step 4: 建立/完善 features.json
  - 每个 ERP 活跃产品需要一个条目
  - erpName 必须与 ERP 档案V2 精确一致（可从 check 报告的 archiveTitle 字段获取）
  - 颜色 + 特征字段描述视觉识别依据
  - 如有体验装/正装两个版本，分别建条目

Step 5: 交叉验收（Phase Gate — 全部通过才算建档完成）

  自动可验（可写脚本或人工检查）：
  ✅ #1 sku-map keys 覆盖所有活动产品（无遗漏）
  ✅ #2 sku-map 中每个 platformCode 在 data/imgs/ 都有对应图片
  ✅ #4 features.json 产品数 = ERP 档案V2 该品牌活跃产品数
  ✅ #6 data/imgs/ 中无跨品牌图片（或确认品牌作用域已隔离）
  ✅ #7 features.json 每个条目都有对应参考图（data/products/{brand}/{name}.jpg）

  必须人工执行：
  👁 #3 随机抽 5+ 张图片目视 spot-check，确认内容与产品名一致
  👁 #5 随机抽 5~10 个 SKU 实跑识图，确认 features.json 可正确匹配

Step 6: 记录建档时间戳
  - 在 data/products/{brand}/features.json 的 _meta.lastUpdated 更新日期
```

### "不在对应表"产品的图片获取

有些产品活动期间不通过对应表销售（如礼盒整体包装图），需要特殊处理：
1. 确认该产品是否在鲸灵活动中（check 报告显示"不在对应表"）
2. 通过 ERP 档案V2 查询该产品的实物图
3. 或由用户直接提供参考图片

### 长期架构方向（当前为止血补丁）

**当前问题**：所有品牌数据混在 `data/imgs/` 和 `data/sku-records.json`，品牌切换时需手动清空。

**目标架构**（重构 ticket 已建立，触发条件：第二个品牌建档开始前）：
```
data/brands/{brand}/
  imgs/           ← 该品牌 SKU 图片（隔离）
  sku-records.json
  sku-map.json
  check-report.json
  ref-imgs/       ← 参考图（原 data/products/{brand}/）
```
