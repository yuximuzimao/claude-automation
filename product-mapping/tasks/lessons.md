# 临时教训暂存

---

## Lesson: 对应表搜索框是平台规格商家编码（platformCode），不是货号（2026-05-27）

**现象**：`auto-match2.js` Phase 1 Step A 把 productCode（货号，如 `0605zh-1`）填入 `.el-input-popup-editor input`，表格返回 0 行，导致展开+勾选失败。

**根因**：`el-input-popup-editor input` 是「平台规格商家编码」搜索框（platformCode 维度），不是货号搜索框。填货号会 0 结果。

**铁律**：对应表搜索框填 platformCode；展开目标行靠 `tds[6]`（值=productCode）匹配。两个字段类型不同，不可混用。

---

## Lesson: 识图结果不能包含配件，配件由 accessories.json 临时注入（2026-05-27）

**现象**：识图 `260605- 6` 时，把不可见包装配件（礼盒）写进了 recognition.items，导致识图结果不纯净；同时 accessories.json 用 productCode + skuNameContains 模糊匹配，当同一 productCode 下有多个 platformCode 时匹配脆弱。

**根因**：
1. recognition 的语义是「图片中可见商品」，不可见配件（礼盒/礼袋/雪梨纸）永远不应进入 recognition，图片里标「赠」的可见商品（如托特包）才进 recognition。
2. accessories.json 旧格式 key=productCode 无法精确定位 platformCode，且 annotate.js 的注入逻辑在当前扁平格式下已断路，配件从未实际注入到 match 流程。

**修复**：
- accessories.json 改为 key=platformCode（精确匹配，无模糊）
- 新增 `lib/utils/resolve-items.js`：拿 platformCode + recognition.items → 临时合并配件，不写回原始数据
- check.js 对比逻辑改用 resolveItems；auto-match2.js 传子品列表时改用 resolveItems；verify-table.js 显示识图对比时改用 resolveItems

**铁律**：识图时看到什么写什么，配件不写。accessories.json 管的是「确定会带但图片不显示的包装件」，key 必须是 platformCode。

---

## Lesson: 识图漏掉图片角落的赠品（2026-05-27）

**现象**：`260605- 6` 图片右下角有蓝色托特包标「赠」，识图时完全漏掉，只识了主品。

**根因**：图片有多区块布局（主品在上方、赠品在角落），只关注了主体区域。

**铁律**：识图必须扫描整张图的全部区域，包括角落、底部小物件。有「赠」字标签的商品是可见赠品，同样要识别并记入 recognition。

---

## Lesson: 识图相似商品必须读图上文字，不能凭外观描述区分（2026-05-27）

**现象**：`260605- 6` 图中白色扁平盒是眼膜（`HEE悦希焕颜紧致淡纹眼膜`），识图时误判为眼贴膜（`悦希抗皱紧致淡纹眼贴膜 5片装`）。

**根因**：features.json 区分眼膜 vs 眼贴膜靠「外观特征描述」（白盒+logo颜色+装饰图案），识图时没有直接读图片上的商品名称文字，而是凭外观特征记忆匹配，在两款都是白盒的情况下判断错误。

**铁律**：识图时遇到相似商品（同品牌、同类别、外观接近），**必须读图片上的中文商品名称文字**作为第一判据，外观特征描述只作辅助。图片文字模糊看不清时，才退而用外观描述 + features.json 核对。不能凭记忆或描述直接写 erpName。

---

## Lesson: 识图必须覆盖全部 SKU，不只是 unmatched 部分（2026-05-27）

**现象**：识图步骤执行完后告知用户「识图已完成」，实际上只识了 15 个无 erpCode 的 SKU，跳过了 38 个 matched-original SKU（已有 erpCode 但无 recognition）。

**根因**：识图的目的不只是提供匹配所需的信息，更重要的是为 verify-table 人工核对提供依据。verify-table 需要对所有 SKU 做「图片识图结论 vs 档案 erpCode」的对比，若 matched-original SKU 无 recognition，则 verify-table 无法核查这批 SKU 是否映射正确。

**铁律**：识图步骤必须覆盖 sku-records.json 中**全部** SKU（erpCode 有无均覆盖）。识图前先统计 `recognition === null` 的条数，全部识完后再次统计确认为 0，才能报告「识图完成」。

---

## Lesson: check 前必须先对齐 JL 账号（2026-05-22，触发两次）

**现象**：跑 `check --shop 共途` 后，JL 抓到 RITEKOKO 品牌产品（非 KGOS），全部「不在对应表」，误判为新活动未上线。

**根因**：`--shop` 只控制 ERP 端查哪张对应表。JL 标签页当前登录的是百浩账号（账号3），所以抓的是百浩的活动商品，与 ERP 共途对应表 cross-reference 当然全空。

**铁律**：用户说「<店铺>的匹配」→ 第一步查 `sessions/accounts.json` 确认账号 → `jl <编号>` 注入 → 才跑 check。
账号映射（快查）：账号3=百浩/RITEKOKO，账号4=蓄力生长/KGOS，账号5=共途/KGOS，账号6=上海绰绰/悦希，账号14=茗瑞/KGOS。

---

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

---

## Lesson: 人工处理部分 SKU 后，必须重跑 check 才能继续 match

**现象**：match 中途某 SKU 出错，人工在 ERP 界面手动完成匹配。之后直接重跑 match，同一 SKU 被再次尝试匹配，触发同样错误。

**根因**：`getTodo()` 的判断条件是 `erpCode === null`。`erpCode` 只有 `check.js` 运行时通过读取 ERP 实时对应表才会被填入。人工在 ERP 界面完成匹配后，`sku-records.json` 里这条记录的 `erpCode` 仍是 null，match 看到的还是"未匹配"。

同时，`auto-match2.js main()` 每次启动时都会清空 `log.done[]` 和 `log.failed[]`，所以"上次 done 过"的记录对本次毫无防护作用。

**正确流程**：人工处理若干 SKU → **重跑 check** → sku-records.json 被全量重写（erpCode 同步为 ERP 最新状态）→ 重跑 match（getTodo 返回剩余未匹配）。

**铁律**：任何人工 ERP 操作后，下一步必须是 `check`，不能是 `match`。

---

## Lesson: 同一 productCode 多比例套件触发「提示」弹窗，当前代码不处理

**现象**：同一 productCode（如 `0519sy`）有两个 platformCode，第一个（0519-3）匹配为青柑×10+茉莉×10。第二个（0519-4）尝试匹配为青柑×5+茉莉×5 时，ERP 弹出「提示」弹窗（内容："该商品有未完成的订单，换绑是否将关联订单状态置为对应关系变更？"），后面的「选择商品」弹窗同时打开但被遮挡，代码报 `Expected 选择商品 dialog, got: 提示`。

**根因**：ERP 在"同 productCode 已有未完成套件、且新套件比例不同"时，在打开选择商品弹窗之前插入一个确认弹窗。当前 copy-as-suite.js 没有处理这个前置弹窗。

**现实处置**：遇到此情况，人工在 ERP 处理（点提示弹窗确认或取消），然后走「人工处理后重跑 check」流程。

**后续优化方向**（如有必要）：在 `clickCopyAsSuite` 后、`addProductToDialog` 前，检测「提示」弹窗是否存在，若存在则先点确认再继续。

---

## Lesson: archive.js queryArchive 错误分类：count=0 vs 瞬态错误（2026-05-20）

**现象**：档案V2查询出现 `dataList 为空 (count=-1)` 时，旧代码 `if (d.error) return null` 一律返回 null，retry 永远不触发，SKU 静默丢失（0 resolved）。

**根因**：count=-1 是 Vue 组件未就绪的瞬态错误，与 count=0（精确查询真实无结果）是完全不同的两种情况，旧代码没有区分：
- `count=0`：真实不存在 → 返回 null（正确）
- `count=-1` 或其他：Vue 未就绪等瞬态错误 → 应 throw，让 retry 重试

**修复**（已提交 2f7b644）：
```javascript
if (d.error) {
  if (d.count === 0) return null;
  throw new Error(`${d.error} (count=${d.count})`);
}
```

**影响**：sku-calculator 的 resolve-components 曾因此 bug 导致 56 个 erpCode 全部查询失败（0/56 resolved）。修复后 54/54。

---

## Lesson: 酵素4.0体验装 vs 正装 — 形状比例是关键识图线索（2026-05-23）

**现象**：识图时将酵素4.0体验装误识别为酵素4.0正装，导致后续匹配错误。

**根因**：体验装和正装包装设计相似，但**形状比例不同**——体验装盒子更窄（长条形），正装盒子更接近方形。识图时只关注了包装图案/文字，忽略了盒子长宽比这一关键视觉特征。

**铁律**：
- 同款商品有正装/体验装两个版本时，**盒子形状是首要识别线索**：体验装=窄长条，正装=偏方形
- 识图三步走流程中，第一步「看实物」必须包含形状/比例判断，不能只看图案和颜色
- features.json 中应为体验装/正装分别记录形状特征（如 `"形状": "窄长条"` vs `"形状": "方形"`）

---

## Lesson: 营养粉买赠 SKU 漏识酵素4.0体验装（2026-05-23）

**现象**：核对表人工核查发现 0525-4（莓果味×4）、0525-5（牛油果味×4）、0525-6（莓果味×2+牛油果味×2）三个 SKU 的识图结果都漏掉了酵素4.0体验装×1。

**根因**：营养粉「买3送1」类 SKU，图片中附带 1 盒酵素4.0体验装作为赠品展示。体验装盒子小（窄长条，50ml×3袋），被大盒营养粉（方形，30g×12）遮挡或挤到角落，识图时注意力集中在数营养粉盒数，忽略了小件赠品。

**铁律**：
- 营养粉买赠类 SKU（kgosyyf-44：0525-4/0525-5/0525-6）和益生菌买3送1（KGOSYSJ-30：0525-7），图片必有酵素4.0体验装×1
- 识图时特别注意图片四角和边缘位置的小件赠品
- 三步走第二步「数量自检」：营养粉盒数数对后，扫一眼图片全部区域确认没有其他产品

---

## Lesson: 修复过程中间产物不应该 open，只有最终版本才打开（2026-06-23）

**现象**：修复 0624zp-5 识图错误 → `preview-match` → `open`；修复 recognition 未写入 → `preview-match` → `open`，浏览器被打开了两个标签页。

**根因**：每次重跑 `preview-match` 后立即调用 `open`，没有判断"这是否是本轮用户要看的最终版本"。修复过程的中间产物不需要立刻打开。

**铁律**：`open` 只在最后一次生成（确认是本轮最终版）时调用一次。如果同一 session 内需要多次重跑，只在最终版本后 `open`。

---

## Lesson: recognition.items.name 必须用 ERP 标准名称（erpName），不能用简称（2026-06-23）

**现象**：visual-ok 写入 notes 时用了"冰霸杯"、"保温壶"、"一次性吸管袋"等简称，导致 preview-match 展示非标准名称，match 脚本 Set 等值比对时会全部 mismatch。

**根因**：识图输出 notes 时直接写了好记的简称，没有对照 features.json 的 erpName 字段。规则 §5「视觉匹配数据契约」已明确要求：匹配基准是 ERP 档案精确名称，脚本做 Set 等值比对，不做模糊匹配。

**铁律**：识图 visual-ok 写 notes 时，每个 item 的 name 必须等于 features.json 对应条目的 erpName（精确字符串），不能用别名、简称、中文简写。识图三步走第一步之后，立刻查 features.json 确认 erpName 再写。

---

## Lesson: 禁止在生成文件后主动调用 open（2026-06-23）

**现象**：每次重新生成 preview-match HTML 后立即 `open`，导致浏览器累积多个标签页（本次最多3个）。

**铁律**：生成文件后**不调用 open**。只在用户明确说"打开"/"给我看"时才执行一次 `open`。规则覆盖所有文件类型（HTML 报告、PDF、图片）。
