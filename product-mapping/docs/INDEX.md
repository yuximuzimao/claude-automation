# 商品匹配核查 — 操作规则

---

## §1 角色与红线

- **写操作（新增匹配）必须人工确认后执行**；确认后由脚本写入，异常必须 stop-on-error
- ERP 查询命令必须串行，禁止并行（对应表 + 档案V2 顺序执行）
- 页面等待按具体状态轮询，不用单一固定时长代替成功验证

---

## §2 核查流程（完整端到端）

**Step 0（首次 check 必做）：确认 JL 账号对齐**

新活动首次运行 `check` 时，先查 `sessions/accounts.json` 确认 JL 账号；用户已经手动打开并确认正确店铺页面时只读当前页，不重复注入。`match` 和 `check --reuse-active --skip-download` 只依赖 ERP，不需要鲸灵标签页。

| 账号 | 店铺 | 品牌 |
|------|------|------|
| `jl 3` | 百浩 | RITEKOKO |
| `jl 4` | 蓄力生长 | KGOS |
| `jl 5` | 共途 | KGOS |
| `jl 6` | 上海绰绰 | 悦希 |

> **根因**：JL 标签页登录哪个账号决定「抓哪家店的活动商品」。`--shop` 只控制 ERP 端。账号不对齐，JL 抓出来的是别家的产品，cross-reference 必然全是「不在对应表」。

> **自动开页/注入账号边界（2026-06-26）**：商品匹配当前安全默认是用户手动打开并筛选好鲸灵商品列表，再由脚本读取当前页面。若用户已手动打开正确店铺页面并确认账号态，后续 `jl-products` / `check` 只读商品列表，不触发自动注入错 tab 的风险。若后续需要 AI 自动打开鲸灵页面、自动切换账号或自动注入登录态，不能直接复用未绑定目标 tab 的旧注入逻辑；必须先让用户按操作指引手动完成，或先修复底层注入绑定 `targetId` 后再自动执行。这条是商品匹配项目的操作边界，不是售后工单系统待修项。

**命令序列**（每次新活动按此顺序执行）：

```
0  jl <账号编号>                         ← 必须先对齐 JL 账号
① node cli.js check --shop <店铺> --brand <品牌> ← 首次扫描，品牌只指定这一次
② 当前具备视觉能力的对话模型进行 AI 识图 ← AI 步骤，写入 sku-records.json
②.3 node cli.js check --shop <店铺> --reuse-active --skip-download
                                         ← 同一 check；我判断已匹配异常，未匹配是正常待处理
②.5 node cli.js preview-match           ← 全部 SKU 展示最终匹配明细（AI 识图+自动配件），由用户确认一次
③ node cli.js match --shop <店铺>       ← 自动匹配（异常立即停止）
④ node cli.js check --shop <店铺> --reuse-active --skip-download
                                         ← 最终自动核对全部 SKU
```

`--reuse-active --skip-download` 会用上一份 check 报告和当前 `sku-records.json`
精确核对同一组 `productCode + platformCode` 商品链接，只读 ERP 当前对应表并完整查询档案 V2；
两边活动范围不一致时会在写报告前停止。
品牌从首次 check 的报告和每条 SKU 记录自动继承，任一处缺失或冲突都会在 ERP 写入前停止。

**商品链接身份规则**：
- 一条待核对记录的唯一身份是 `productCode + platformCode`，不是单独的 `platformCode`。
- 不同活动链接允许复用同一个 `platformCode`；即使图片和商品明细相同，也必须按不同 `productCode` 分别读取对应表、分别核对、分别计入完成数。
- `sku-records.json` 使用 `productCode::platformCode` 作为记录键；图片 URL 收集索引也必须使用同一个联合键，落盘使用 `data/imgs/{productCode}__{platformCode}.jpg`，让每条商品链接都有独立核对证据。只改文件名、不改上游 imgUrl 索引仍会串图。
- 后置 check 的活动范围、match 断点日志和完成门禁都按链接身份比较，禁止用 `platformCode` 去重后缩小处理范围。

**各步骤明细**：

```
① 首次 check 内部流程:
   0. 【自动清空】data/imgs/ 和 data/reports/（旧活动数据对下次无用）
   1.1 鲸灵商品列表 → 筛选「特卖在售中」→ 抓取活动货号（处理范围）
   1.2 ERP 商品对应表 → 下载平台商品（选店铺+全量下载+等待完成）
   1.3 ERP 商品对应表 → 选店铺 → 展开所有行 → 读SKU映射 + 图片URL
   1.4 下载 SKU 图片到 data/imgs/，标记匹配/未匹配
   1.5 商品档案V2 → 按ERP编码查类型+子品明细
   1.6 仅在旧记录品牌与本轮品牌一致时保留 recognition → 保存报告
   1.7 【全量重写】sku-records.json（以 ERP 实时对应表为唯一数据源，写入 brand）
   报告输出：recognition + comparisonResult + comparisonDetail 字段

② AI 识图:
   - 由当前具备视觉能力的对话模型对照 `features.json` 判断图片可见商品
   - 本地执行端若能直接查看图片，可读取 `data/imgs/`；ChatGPT + CodexPro 不能把本地图片像素直接送入视觉通道，必须按 `docs/chatgpt-codexpro-operations.md` 生成联系表并桥接为当前对话附件
   - 写入 sku-records.json 的 recognition 字段；用户要求当前对话模型完成识图时，OCR/本地视觉模型不得替代该 AI 的识图结论
   - 重复 platformCode 必须按 productCode 分别写入；优先调用结构化 `recordRecognition()`，CLI 使用 `visual-ok/visual-flag ... --product <货号>`，多商品描述用中文分号分隔

②.3 匹配前 check（同一个 check 脚本，由我按阶段判断）:
   - matchedComparisonMatch 必须等于 matchedSkuCount
   - matchedComparisonMismatch 必须为 0；有异常时我只报告具体 SKU 和差异
   - 已有匹配异常的修正必须由用户在平台人工完成，自动流程禁止换绑或覆盖；用户完成后只对该链接回读并更新本地记录
   - unmatchedAwaitingMatch 是正常待处理，不在此阶段算失败

②.5 preview-match（确认 AI 识图后再 match）:
   - 只读取 sku-records.json
   - 已匹配和未匹配都展示“最终匹配明细”：`recognition.items` 的 AI 识图商品 + 本品牌自动注入配件
   - AI 识图商品与配件放在同一张明细表中；配件仅用不同字体颜色标识来源，不能从最终明细中拆除或降级为可选项
   - 用户核对的是最终将写入 ERP、并在后置 check 中逐项比较的完整商品名称和数量
   - 不展示 ERP 当前档案，不让用户在匹配前把历史绑定明细误认为识图结果
   - recognition 未覆盖全部 SKU 或品牌缺失/冲突时拒绝生成

③ match 内部流程:
   0. 按当前店铺和待匹配 `productCode + platformCode` 链接集合生成任务 scope；scope 变化才清空 done[]/failed[]，同 scope 重跑保留已完成进度并从 ERP 当前中间状态恢复
   - Phase 1: 组合装 → 勾选 → 标记套件 → 逐个复制为套件
   - Phase 2: 单品 → 逐个 remapSku（getTodo 过滤：erpCode=null + 有recognition）
   - 任何错误立即停止（stop-on-error）

④ 最终 check = 复用活动范围 + 对比:
   - 此时全部 SKU 应有 erpCode，sku-records 全量重写后回填 ERP 实况
   - comparisonResult: 识图预测 vs 档案实际 → match/mismatch
   - **比对铁律（禁止简化）**：
     - 单品（archiveType=0）：识图名称 AND 识图数量=1，两者同时满足才算 match；识图数量≠1 = mismatch（ERP未建套件档案）
     - 套件（archiveType=2）：识图 items 与 ERP subItems 的 {name, qty} 集合完全一致才算 match
     - 组合档案标题是创建时活动文案，不参与正确性判断；即使标题保留旧活动名称，只要 subItems 名称和数量完全一致就算 match
     - 任何一侧缺数量信息 = mismatch，禁止仅比名称
     - recognition 为空但 ERP 有档案明细 = mismatch，禁止归入 pending；verify-table 出现「无识图数据」即流程未完成
     - 有 recognition 但 ERP 无可比档案明细 = mismatch；若 erpCode 是规格编码，必须先用「规格商家编码」回退查询档案
   - 若有 mismatch，由我先定位并报告异常；用户只处理明确指出的 SKU

⑤ verify-table（仅最终自动核对异常时使用）:
   - 读取最新 check 报告，将各 SKU 的图片与 ERP 档案明细并排展示，供人工定位异常；全部自动比对一致时不要求用户重复核对
   - 图片嵌入 base64，HTML 自包含，生成后自动打开浏览器
   - 每次生成前自动清空旧 verify-*.html（与 check 清空 imgs/reports 一致，旧表对下次无用，不保留存档）
   - 用途：核对对比结论，防止识图错误漏过
   - 对比结果用颜色标注：绿色=一致，红色=不一致
   - **注意**：preview-match（②.5）已在 match 前由用户确认最终匹配明细，verify-table 仅在自动核对异常时使用，正常流程跳过
```

**异常处理原则**：
- match 任何 SKU 报错 → 立即 throw 停止；先按 `docs/matching-stability.md §4` 判断 ERP 中间状态，再决定续跑
- 人工在 ERP 完成任何匹配后 → 必须先跑 check 回读 ERP，不能直接续 match
- 已有匹配的识图/档案异常 → 只报告差异，等待用户人工修正；不得调用自动换绑。若用户把它改成新的未匹配商家编码，按 `productCode + 新 platformCode` 迁移识图和图片身份，再作为普通待匹配项处理
- check 读取异常（ERP 未登录、页面无法访问）→ navigateErp 已处理，手动刷新登录后重跑
- 匹配前 `matchedComparisonMismatch > 0` → 我主动报告已匹配异常，用户不需要自行翻查全部 ERP 明细
- 最终 mismatch/pending/未匹配任一项大于 0 → 不能判定本轮完成

---

## §3 视觉匹配（Claude 亲自执行，不写识别脚本）

**为什么不用脚本**：组合装图片有多商品、部分遮挡、角度差异，脚本无法做到100%准确。

**执行方式**：
- `check.js` 下载 SKU 图片到 `data/imgs/{productCode}__{platformCode}.jpg`，图片路径由商品链接身份推导；报告保留 imgUrl，不再使用 `data/tmp/imgs/`
- 我通过 Read 工具加载 `data/imgs/` 中的图片，直接目视识别内容
- 对照 `data/products/{brand}/features.json` 的视觉特征描述辅助判断
- 输出结论：商品名称 + 数量 + 置信度（高/低/无法判断）

**识图步骤**：
1. 读 SKU 名称（如"益生菌6盒+冰霸杯1个+玉米片10包+一次性吸管袋1盒"）→ 确定应有商品
2. Read 工具加载图片
3. 对照 features.json 描述逐一确认图中每个商品
4. 报告：每个商品是否在图中可见，数量是否一致
5. **erpName 校验（必做）**：写识图结果前，查 features.json 确认每个商品的 `erpName` 精确字符串；结构化写入优先，多商品文本必须用中文分号分隔，不能用空格拆项。脚本做 Set 等值比对，一字之差全部 mismatch。

**形状判别铁律（2026-05-23 酵素4.0教训）**：
- 同款商品有正装/体验装两个版本时，**盒子形状是第一识别线索**：体验装=窄长条（长宽比约2:1），正装=偏方形（长宽比约1:1）
- 第一步「看实物」必须包含形状/比例判断，不能只看图案和颜色
- 参考 features.json 中「形状」字段（正装、体验装分别有记录）

**营养粉买赠 SKU 漏识图陷阱（2026-05-23 营养粉教训）**：
- 营养粉「买X送Y」类 SKU（如买3送1=4盒），图片中常附带 1 盒**酵素4.0体验装**作为赠品展示
- 识图时只数了营养粉盒数，漏掉了角落的酵素4.0体验装（小窄盒，容易被大盒营养粉遮挡或忽略）
- **铁律**：营养粉买赠类 SKU 识图时，特别注意图片四角和边缘是否有酵素4.0体验装小盒

**参考图库**：`data/products/{brand}/*.jpg` — 单品标准图，命名 = 商品名称（如 `data/products/kgos/益生菌.jpg`、`data/products/hee/悦颜霜.jpg`）

**KGOS 真实主图语料**：用户在微信文件目录 `.../2026-05/1主图汇总` 收集了 270 张 KGOS 实际 SKU 主图。该目录用于 product-detect 数据集质量审查和黄金验证集建设；不要直接提交到 Git，也不要把 HEE 历史 `data/imgs/` 当作 KGOS 训练分布。

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
    pending-products.json ← 已知但资料未齐的新品；命中后提示待补，不得当作未知或套用旧版
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

### pending-products.json — 待图/待稳定身份新品

- 新品已经出现在 ERP、但商品图或稳定条码尚未齐全时，先进入此清单，不提前塞进 `features.json`。
- 名称、简称或当前编码任一命中都表示“已知待补”，不能显示为普通未知商品；同时必须停止视觉自动判断，等待商品图或最终条码。
- 新版产品不得复用旧版外观。商品图、ERP 精确名称和稳定条码齐全并验收后，才迁入 `features.json` / 参考图；迁完从待补清单删除。
- 审单项目可以用此清单区分“已知待补尺寸”和真正未知商品，但尺寸、箱规未确认前仍不得自动归入装箱白名单。

### accessories.json — 不可见配件规则（悦希专用）

**用途**：声明哪些 SKU 在 ERP 套件中含有图片不可见的配件（礼盒/礼袋/雪梨纸等）。
**更新时机**：每次活动前，先跑 `check --shop <店铺> --brand <品牌>` 读取活动商品，再根据报告把用户给的货号（productCode）映射到具体平台规格编码（platformCode）。
**注入时机**：主流程 `match/check` 通过 `resolveItems(platformCode, ...)` 临时叠加配件，不写回 recognition；识图不需要手动处理配件。

```json
{
  "_meta": { "campaign": "2026年X月活动", "lastUpdated": "YYYY-MM-DD" },
  "rules": {
    "260703-1": {
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
- 键 = platformCode，不是 productCode。用户只给货号时，必须先从最新 check 报告或 `sku-records.json` 查出该货号下所有 platformCode，再逐个写规则
- 同一货号有多个 SKU 时，配件数量可能不同；不要只写一个货号级规则，也不要漏掉同货号的第二个 platformCode
- 配件商品本身也需要在 features.json 中有条目（ERP 搜索时需要精确名称）
- 示例条目（`_` 开头的键）会被自动过滤，可保留作为格式参考

**本次活动排除项处理（2026-06-25 百浩/悦希）**：
- 用户明确说某些在售货号“不需要处理”时，仍应先读取列表确认它们存在，再从本次报告和 `sku-records.json` 里剔除；不要删除 `features.json` 或历史参考图
- 若不同货号复用同一个 platformCode（如折扣/免费两个活动入口），仍按不同商品链接分别保留或排除，不能按 platformCode 去重

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

通过表头文本“商品名称 / 商家编码 / 组合比例”定位列，不硬编码列号；弹窗空明细重试一次。关闭弹窗用 `button.el-dialog__closeBtn`（不是 `el-dialog__headerbtn`）。

### 对应表图片收集

图片列 class 名每次导航后动态变化，不能硬编码。正确方式：逐段滚动（12步）触发懒加载，用 `productCode + platformCode` 建立 imgUrl 索引。

### 图片存储规范

- **统一路径**：`data/imgs/{productCode}__{platformCode}.jpg`，货号与平台规格编码共同组成文件名
- **覆盖范围**：`check.js` 对**所有 SKU**（包括未匹配）都下载图片，不只是已匹配的
- **查找方式**：知道 productCode 与 platformCode 后直接拼路径，不需要在 JSON 里存 imgPath
- **生成入口**：统一调用 `lib/sku-identity.js` 的 `imageFileName()`；只替换路径不安全字符，保留编码中的空格等业务字符

### SKU 数据文件规范

- **`data/sku-records.json`**：单文件存全量商品链接 SKU 元数据 + 识图结果，按 `productCode::platformCode` 索引（纯平铺格式 `{recordKey→rec}`）
- **字段**：`platformCode / productCode / shopName / brand / skuName / erpCode / erpName / imgUrl / recognition / scope`
- **写入时机**：check 结束时**全量重写**（以 ERP 实时对应表为唯一来源，erpCode 回填实况值，recognition 从旧文件保留）
- **`scope` 字段**：
  - `"active-YYYY-MM-DD"` = 该日期 check 运行时确认的活动在售 SKU
  - `"history"` = 历史活动遗留，不在当前核查范围（旧格式遗留，全量重写后不再产生）
- **`recognition` 字段**：识图后写入，格式 `{type:"单品"|"组合装", items:[{name,qty}], raw:"描述"}`；所有 items 数量合计为 1 才是单品，合计大于 1 就是组合装，即使只有一种商品也不能把 `商品×3` 标成单品
- **禁止**：在 JSON 里存 `imgPath`（可从 productCode 与 platformCode 推导，存了是冗余）
- **品牌作用域**：首次 check 必须显式 `--brand`；每条 SKU 与报告都写入 brand，后续 preview/match/check 只能继承且必须一致，禁止静默兜底
- **`data/visual-verdicts.json`**：识图结论（ok/mismatch），独立于 sku-records.json（legacy，当前流程直接写 sku-records）

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
4. 验证：`sv.searchData.itemType === 1`，且 `sv.pageData.total` 为页面实时返回的普通商品总数（不要硬编码历史数值；历史 KGOS 曾约 174，只能作异常参考）

**禁止**：用 `sv.searchData.itemType = "0"` 直接赋值——无效，真实 type 值是数字 `1`，且不能绕过 UI 筛选

**识图前必读**：`data/products/{brand}/features.json`（含 erpName 精确名称 + 视觉特征）
- `erpName` = ERP 档案里的精确商品名称，脚本做 Set 等值比对，必须完全一致
- 识图输出格式：`erpName×数量`，每个子品一条，逗号分隔

---

## §5.6 对应表「套件处理→标记套件」操作规范

**流程**：
1. navigateErp → 商品对应表
2. 点左侧店铺名（如「澜泽」）
3. 在 `.el-input-popup-editor input` 输入 productCode（货号）并回车
4. 用 `tds[6]` 精确确认货号行并展开（点 `.el-table__expand-icon`）
5. 清除展开区全部旧勾选，再按子行 `tds[5]` 精确定位 platformCode
6. **只勾选目标 SKU 那一行**，并验证选中数严格等于 1
7. 从触发按钮的 `aria-controls` 精确定位所属菜单，再点击“标记套件”；后台标签页菜单动画可能停在高度 0，不能只按可见高度找菜单
8. 验证：目标行出现“复制为套件”按钮才算成功

**⚠️ 红线**：每次只处理当前要匹配的那一个 SKU，严禁批量勾选整个货号所有子行。每个 SKU 是独立的商品/组合，必须单独处理。

---

## §6 已知坑位

> 格式：`[触发次数/最后触发]` — 说明
>
> 连续 SKU、隐藏 Vue 状态、中断恢复和“立即修/先观察”的判断标准见
> `docs/matching-stability.md`；2026-07-24 澜泽实战证据见
> `docs/archive/2026-07-25-lanze-match/README.md`。

- `[1/2026-04]` **翻页溢出**：btn-next 不变灰，必须用"共X条"判断结束，否则死循环（实测抓558条，实际174条）
- `[1/2026-04]` **图片内容核查**：预存参考图片不可信任，每张图上线前必须打开目视确认
- `[1/2026-04]` **分页筛选残留**：切换筛选前必须先清空已有筛选，否则多条件叠加结果为0
- `[2/2026-04]` **档案V2 直接赋值失效**：`window.__sv.searchData = code` 不触发 Vue 响应，必须 DOM 输入法（见§5）
- `[1/2026-04]` **ERP 状态残留**：跳过 reload 直接操作读到上次的数据，所有页面操作前必须走 navigateErp()
- `[1/2026-04]` **对应表只读1条**：空搜索后未展开所有行，或页面状态未重置，导致只读到当前可见行
- `[2/2026-05-27→2026-07-24 结论反转]` **对应表搜索维度会随 ERP 页面变化**：当前实测 `.el-input-popup-editor input` 填 productCode（货号）有效，填 platformCode 返回 0 行；用 `tds[6]` 精确确认货号行，展开后用 `tds[5]` 精确确认 platformCode。再次出现 0 行时必须同页 A/B 实测，禁止凭历史文档猜字段
- `[1/2026-04]` **多层嵌套 dialog 确定按钮点错**：Element UI 多弹窗叠加时 querySelector 取到第一个隐藏 footer，必须用 `querySelectorAll('.el-dialog__footer')` 遍历取 `getBoundingClientRect().height > 0` 的那个，再点其 `el-button--primary`。禁止用 innerText 文字匹配（有的按钮是"确 定"带空格）
- `[1/2026-04]` **弹窗操作前未验证弹窗可见**：操作 dialog 内元素前必须先确认 wrapper 的 `getBoundingClientRect().height > 0`，否则操作到隐藏层
- `[1/2026-04]` **档案V2 查询前筛选残留**：`fetch-archive-names` 等操作会留下"普通商品"筛选，下次 `km-archive` 查组合装时返回 null。`initArchiveComp` 现已加「清空条件」步骤；通用原则：每次档案操作前必须检查/清空筛选状态
- `[1/2026-04]` **识图颜色规则必须执行**：features.json 记录了体验装口味颜色（浅绿=茉莉，淡黄=青柑），识图时若只看图片文字"黑茶体验装"而不看盒子颜色，会批量识别错误。规则：识图前必须逐条比对 features.json 颜色字段，视觉特征 > 文字标注
- `[1/2026-04，已被 2026-05-08 精确行规则替代]` **不能只用 count > 0 宽松选首行**：早期实现可能把套件商品写为子品。当前规则不是强制 `count===1`，而是在任意结果数下查找某个 td 与完整 ERP 商品名精确相等的行；无精确行才报错
- `[1/2026-04]` **商品类型下拉不能 UI 点击**：el-select 下拉 input 展开后 portal 在 dialog 外生成，触发 close-on-click-modal 关闭弹窗。正确做法：直接 Vue emit：`vm.$emit("input", value); vm.$emit("change", value)`
- `[1/2026-04，执行端相关]` **长脚本不要占用受限前台调用**：本地 Codex 或支持后台会话的本地工具可用后台运行并通过 `auto-match-log.json` 监控；ChatGPT + CodexPro 没有可承诺持续运行的后台任务，单次前台调用还有时间上限，应把长批量交给本地 Codex，见 `docs/chatgpt-codexpro-operations.md`
- `[∞/永久保留]` **#48 读表数据用<th>表头定位，禁用正则/长度过滤**：子品弹窗表读取必须通过 `<th>` 表头文本（"商品名称"/"商家编码"/"组合比例"）定位列索引。禁止硬编码固定位置 [1][3][10]，禁止对 specCode/name 做正则匹配过滤——会把非数字编码（kgoxnld等）合法行当垃圾误杀。
- `[1/2026-05-07]` **对应表图片列 = td[3]（左侧平台侧）**：sub-row 中 `imgs[0]` 在 td index 3，parent class `el-image el-popover__reference`。ERP 产品图若存在在 td[12]+（右侧）。`querySelector("img")` 取平台 SKU 图是正确行为。assertPlatformImageColumn() 断言：`img.closest("td")` 在同行所有 td 中 indexOf = 3。
- `[1/2026-05-07，2026-07-28 更新]` **货号 ≠ platformCode**：货号（productCode，如 yxxhtz）是 ERP 对应表的产品链接标识；platformCode（如 0509-1）是规格编码。图片文件名必须同时包含两者，不能用任一单字段直接定位。
- `[1/2026-07-28]` **platformCode 不是商品链接唯一键**：折扣、免费、秒杀等不同活动链接可能复用同一个 platformCode。运行态、核查范围、匹配日志和图片文件名都必须使用 `productCode + platformCode`；禁止只按 platformCode 去重。
- `[1/2026-05-07，已拆分]` **readAllCorrespondence 有下载副作用**：需要刷新数据时用 `readAllCorrespondence()`；仅查询用 `readCorrWithoutDownload()` 或 `readCorrespondence()`，禁止为只读需求触发平台商品下载
- `[1/2026-05-08]` **「选择商品」弹窗搜索返回2条结果不等于名称歧义**：气垫霜正装和替换装名称都包含"亮肤色"，ERP 弹窗是子串搜索，count=2 是正常的。wait-loop break 条件必须同时检查 `hasExact`（任意 td 的 innerText 精确等于 productName 即命中），不能只靠 count===1，否则10s 超时。行选择（r3）本就精确匹配，无需另改。
- `[1/2026-05-08]` **matched-original SKU 的 recognition 必须补填，不能留 null**：重跑 `--from annotate` 时，matched-original + recognition=null 会被 annotate 跳过，导致 itemType=null。识图阶段需要按 erpName/skuName 为这些条目补填 recognition.items，让 annotate 能正常生成 itemType。
- `[1/2026-05-13]` **全量下载选择是 el-radio，不是 el-checkbox**：下载平台商品弹窗里「全量下载」「增量下载」「指定下载」三个选项是 `el-radio` 组，默认选中「增量下载（value=2）」。代码若用 `.el-checkbox` + `input[type=checkbox]` 查找，永远 null，全量下载永远不被选中，静默跑增量。正确：`.el-radio` + `input[type=radio]`，查 checked 状态再 click。
- `[1/2026-05-13]` **ensureCorrPage 跳过 reload 导致残留 dialog 叠加超时**：`ensureCorrPage` 检测到 hash 已匹配时跳过 reload，仅清空搜索框。若前一次操作（如手动 inspect）留有未关闭 dialog，新 download dialog 叠加在顶层但 gone 检测（等所有 dialog 消失）永远不通过，导致 60s 超时。根治：download 操作前必须用 `navigateErp()`（强制 full reload），不能用 `ensureCorrPage`。
- `[1/2026-05-13]` **店铺侧边栏匹配必须用 .includes()，不能用 ===**：ERP 侧边栏文字是「百浩创展」，传入 shopName「百浩」，`===` 精确匹配失败。所有操作 ERP 店铺侧边栏的代码一律用 `.includes(shopName)`，禁止 `===`（已修复 copy-as-suite/mark-suite/create-suite/read-erp-codes/read-skus/remap-sku 共 6 个文件）
- `[1/2026-05-13，2026-07-25 加品牌门禁]` **check 必须全量重写 sku-records，不能 patch**：旧 patch 逻辑导致 erpCode=null 的已匹配 SKU 被 getTodo() 误判为未匹配。check 结束时以 ERP 实时对应表数据全量重写；只有旧记录 brand 与本轮一致时才保留 recognition，防止同 platformCode 跨品牌串数据。
- `[1/2026-05-13，2026-07-25 改为 scope 门禁，2026-07-28 改为链接身份]` **新活动必须清理旧匹配进度，同活动重跑必须保留进度**：`auto-match2.js` 以店铺和当前待匹配 `productCode + platformCode` 集合生成 scope；scope 变化才清空 done[]/failed[]，同 scope 中断恢复继续跳过已完成项
- `[1/2026-06-26]` **单品 erpCode 可能是规格商家编码，不是主商家编码**：商品档案V2按「主商家编码」查不到时，不能直接判定档案未录入；必须回退到「规格商家编码」精确查询。百浩悦希本次已确认 3 个特殊单品：`yxr-1` erpCode `6940079096228` → 主商家编码 `yx005`（悦希舒缓焕颜精华乳100ml）；`yxs-1` erpCode `6940079096211` → 主商家编码 `yx004`（悦希舒缓焕颜精粹水100ml）；`yxjm-1` erpCode `6975183893203` → 主商家编码 `yx003`（悦希氨基酸表活焕颜洁面膏100g）。
- `[1/2026-06-26]` **comparisonPending 不能掩盖脚本缺陷**：全量识图完成后，正常核对报告应当 `recognitionDone == SKU数` 且 `comparisonPending == 0`。若 recognition 为空但 ERP 有明细，脚本必须输出 mismatch；若有 recognition 但 ERP 无明细，先检查是否需要规格编码回退，仍无明细才输出 mismatch。
- `[2/2026-05-22]` **首次 check 前必须对齐 JL 账号**：`--shop 共途` 只控制 ERP 端查哪张对应表，JL 当前页面决定抓哪家店的活动商品。用户已手动打开并确认正确页面时直接只读；否则先查 `sessions/accounts.json` 再按安全边界切换账号。`match` 和后置 `check --reuse-active` 不需要 JL。
- `[1/2026-05-20]` **人工处理某些 SKU 后不能直接续跑 match，必须先重跑 check**：`getTodo()` 的判断条件是 `erpCode === null`，只有 check.js 运行时读 ERP 实时对应表才会回填 erpCode。人工在 ERP 界面完成匹配后，sku-records.json 里该条记录的 erpCode 仍是 null，match 仍视为未匹配并重试，触发重复操作或同样错误。正确流程：**人工处理 → check → match**，不能跳过 check 直接续 match。
- `[1/2026-05-20]` **同 productCode 多比例套件触发「提示」弹窗**：同一 productCode 下已有已匹配套件（如青柑×10+茉莉×10），尝试为另一 platformCode 配不同比例套件（如青柑×5+茉莉×5）时，ERP 在打开「选择商品」弹窗前插入「提示」弹窗（"该商品有未完成的订单，换绑是否将关联订单状态置为对应关系变更？"）。当前 copy-as-suite.js 无法处理此前置弹窗，脚本报 `Expected 选择商品 dialog, got: 提示`。处置：人工确认/取消提示弹窗后走「人工处理→check→match」流程。
- `[1/2026-05-22]` **downloadPlatformProducts 弹窗必须选含 .el-select 的 dialog**：ERP 对应表页面可能同时存在旧的进度弹窗（含 `.el-progress`）和新的下载配置弹窗，两者都 visible。取第一个可见 dialog 会错选进度弹窗，后续找不到店铺 el-select 报错。正确：`Array.from(ds).find(d => d.getBoundingClientRect().height>0 && d.querySelector('.el-select'))`。等待下载完成的终止条件是 `.el-progress` 消失，不是所有 dialog 消失（配置弹窗在确认后保持打开）。已同步处理：目标店铺已是唯一选项时跳过（`already-selected`），否则先清除多余 el-tag 再触发 `handleOptionSelect`。
- `[1/2026-05-22]` **识图必须三步走：实物→数量自检→底部文字兜底**：只看实物摆放会漏掉赠品小件（如玉米片×10）。更危险的盲区：漏识图→错误绑定→check 时识图与档案同步错误→静默通过，永远发现不了。铁律：①看实物写 recognition.items（口味/规格由实物图决定，不从文字推断）②自检：数图中所有商品总件数，与 items.qty 加总对比，不一致必有漏项 ③底部文字做品类完整性兜底（只验证品类是否齐全，不推断规格/口味）。有疑问先告知用户确认，不擅自修改数据文件。
- `[1/2026-05-23]` **识图形状必须判别：正装 vs 体验装靠长宽比**：酵素4.0 正装（50ml×10袋）盒子接近方形，体验装（50ml×3袋）盒子为窄长条。同款商品有正装/体验装双版本时，第一步必须看形状/比例。features.json 已拆分 酵素4.0 和 酵素4.0体验装 两条，分别记录形状特征。
- `[1/2026-05-23]` **营养粉/益生菌买赠 SKU 图片必含酵素4.0体验装赠品**：kgosyyf-44 货号下含「4盒」的 SKU（0525-4/0525-5/0525-6）和 KGOSYSJ-30 的 0525-7（益生菌买3送1到手4盒），图片中均附带酵素4.0体验装×1 作为赠品展示。体验装小盒易被大盒营养粉/益生菌遮挡或挤到角落。识图时数完主商品盒数后，扫一遍图片四角和边缘。
- `[2/2026-07-24→2026-07-28]` **套件处理菜单不能只靠 click 或可见高度判断**：先触发可见的“套件处理”按钮，再读取其 `aria-controls` 精确定位所属菜单。后台标签页可能把菜单动画卡在 `height=0`，但节点与事件已就绪；点击菜单项后仍必须等待目标行出现“复制为套件”。
- `[2/2026-08-24]` **确认套件不能固定等待 2 秒后一次性判断**：ERP 已接受保存时，“选择商品”弹窗可能稍后才关闭，或先出现“换对应商品”。确认后最多轮询 30 秒；任一状态出现都表示请求已被接收，超时才停止。2026-08-24 茗瑞实测保存超过 10 秒后成功，旧门限会产生假失败。
- `[1/2026-07-28]` **档案查询不能默认采用 dataList 首行**：主商家编码必须与 `outerId` 精确一致，规格商家编码回退也必须在返回对象中找到查询编码；子品弹窗空明细重试一次，仍为空才按异常处理。
- `[1/2026-07-24]` **选择商品弹窗会跨搜索保留隐藏选择**：只取消当前 DOM 的 checked checkbox 无法清掉 `TableItem.multipleSelection`。第一个子品搜索结果稳定后，调用 `TableItem.clearSelection()` + `updateCheckRows([])`，并验证“已选择商品：0”，再勾选本次商品。清理过早会被初始化 watcher 重新灌回旧选择。
- `[1/2026-07-24]` **套件标记是可恢复的中间状态**：匹配在配置子品阶段失败时，目标 SKU 可能已出现“复制为套件”。重试前先读目标行；已有按钮就跳过重复标记，直接续配置子品。
- `[1/2026-07-24]` **纯读取对应表也必须重置筛选和真实页码**：重置搜索下拉会异步重建输入框，必须等待后重新查询 DOM、清空并搜索；随后强制回第 1 页，用 ERP 实时总条数和 pageSize 计算总页数，每次翻页验证 active 页码。禁止依赖 btn-next 禁用状态。
- `[1/2026-07-24]` **动作依赖不能由 CLI 外层猜测**：`match` 和后置 `check` 只需要 ERP，不能因无关的鲸灵 tab 缺失而阻塞；新增入口前先 trace 目标函数的真实依赖
- `[1/2026-07-24]` **ERP lock 必须 finally 释放**：任何成功或异常出口都要恢复售后项目；Node 进程长时间不退出时先查锁生命周期

---

## §7 品牌建档 SOP

品牌建档完整流程已拆到 `docs/brand-onboarding.md`；开始前必须先读 `docs/preflight-brand.md` checklist。

本文件只保留入口原则：
- 新品牌、品牌新增产品、数据污染重建时，读 `docs/preflight-brand.md` → `docs/brand-onboarding.md`。
- 当前多品牌已按 `data/products/{brand}/` 隔离参考资料；运行态仍是 `data/imgs/` / `data/sku-records.json` 全局单槽。
- 未出现并行品牌处理、长期保留运行态或高频切换需求前，不为“已有第二品牌”单独重构 `data/brands/{brand}/`。
