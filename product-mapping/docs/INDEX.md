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

**参考图库**：`data/products/*.jpg` — 单品标准图，命名 = 商品名称

---

## §4 商品参考库维护规范

- 文件名用商品中文名（如 `益生菌.jpg`、`黑茶体验装-茉莉花茶味.jpg`）
- 同款不同规格：正装无后缀、体验装加"体验装"前缀
- 视觉特征记录在 `data/products/features.json`，字段：颜色、特征、别名
- **每次新增图片必须打开确认内容与文件名一致**（教训：预存 `益生菌.jpg` 实为阻断片）

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
