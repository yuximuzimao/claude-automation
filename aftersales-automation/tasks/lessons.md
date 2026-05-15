# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

> 本文件上次清理：2026-04-22。历史教训已迁入 `docs/INDEX.md §6`。
> 2026-05-02 evening session：新教训 #51-#54 直接写入 memory/feedback_jingling_dev.md；
> 操作坑位 #51-#57 同步写入 docs/INDEX.md §6。

---

## 待处理优化项

| 优先级 | 内容 | 状态 |
|---|---|---|
| ✅ | RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，条目关闭 | 完成 |

---

## 2026-05-03 session 教训

| # | 教训 |
|---|------|
| 1 | **先理解数据来源再写代码**：simulations.jsonl 的 decision 来自 AI inference（ai-infer.js），不是 rule engine（infer.js）。生成测试 fixture 前未确认此前提，导致4次迭代返工。规则：处理数据结构前，先 grep/读源码确认数据的生产者和消费者。 |
| 2 | **TOCTOU：existsSync + readFileSync 改为 try/catch**：先检查文件存在再读是经典竞态。统一用 try { readFileSync } catch (e) { handle ENOENT }。 |

## 2026-05-04 session 教训

| # | 教训 |
|---|------|
| 3 | **先 CLI 实测再下结论，禁止只看模拟数据**：看了 9 条 simulation 记录直接断言"ERP 档案查不到 fssy"，未跑 `node cli.js product-archive fssy`。实测后数据一直在，是脚本选择器 bug。模拟数据是历史快照不是实时真值。多次犯，全局铁律。 |
| 4 | **信任现有工具链，不绕过 CLI 自写 CDP 脚本**：已有 `node cli.js product-archive`，手写 WebSocket CDP 调用绕过标准接口 → 污染 server 的 ERP tab 状态 → batch-reprocess 全挂。 |
| 5 | **怀疑代码变化前先 git log**：分析中怀疑 match.js 文本变了，未先查 git log。git log 显示近期无改动，白绕了一大圈。 |
| 6 | **querySelector 必须与同文件其他函数一致的可见性过滤**：archive.js 中 4 个函数 3 个用了 `querySelectorAll` + `getBoundingClientRect` 过滤，唯独 READ_DATALIST_JS 用裸 `querySelector`。读到隐藏 input（0×0）导致 dataList 假阴性。已修并记入 INDEX.md §6 #60。 |
| 7 | **DOM 移除 Element UI 弹窗破坏 Vue 内部 dialogVisible 状态**：`parentNode.removeChild(el)` 绕过 Vue close 流程 → `dialogVisible` 仍为 true → 下次点 `a.ml_15` 被 Vue 跳过 → "子商品弹窗未打开" → subItems 空。必须用 btn.click() 关闭后轮询等待 `display:none`。已修并记入 INDEX.md §6 #61。 |

## 2026-05-09 session 教训

| # | 教训 |
|---|------|
| 10 | **单品档案 subItems=[] 不等于无档案**：`productArchive` 返回 `type=0, subItemNum=0` 的单品时，`subItems` 为空是正常的（单品无子品），但 `infer.js` 错误地把 `archiveSubItems.length === 0` 当成"无档案"处理，强制上报。修复：遍历 `productArchives` 时检测 `pa.subItems.length === 0 && pa.title`，补构造虚拟 subItem（qty=1），与赠品逻辑对称。根本教训：有档案 ≠ 有子品，"有档案但无子品"对单品是正常态，推理逻辑必须区分三种情况：①套件（subItems>0）②单品（subItems=0 but title exists）③真正无档案（title 也没有）。 |

> 新的 session 级发现从这里往下记，稳定后迁入 §6。

## 2026-05-13 session 教训（退货入库集成）— 已迁入 docs/INDEX.md §6 #69-#72

这次 4 次失败的底层逻辑：**没有在交付前自测，导致多个 bug 叠加，每次只修一个，反复往返**。

| # | 教训 | 根因 |
|---|------|------|
| 16 | **写完代码必须立即自读一遍，清除"草稿残留"**：`ensureFilterCorrect` 写了 `await cdp.clickAt(targetId, (() => { return null; })())` ——这是"边写边想"留下的死代码，在实际工作代码之前执行并 throw。`clickAt(null)` 直接抛 `Element not found: null`，后面的 `inp.click()` 永远不到。**规则：每段生成代码交付前，从头读一遍，找 placeholder/dead code**。 | 没有 code review 自检 |
| 17 | **DOM 查询必须限定在正确容器内，不能全局 `document.querySelectorAll`**：`selectAllItems` 用 `document.querySelectorAll('.el-table__header .el-checkbox')` 全局查，主页工单列表的表头 checkbox 排在 DOM 前面且可见 → 点了主页，商品行没被选。**规则：弹窗内的操作全部用 `wrapper.querySelector`，wrapper 已经是 `el-dialog__wrapper`，不要再走全局**。这是 lesson #6 的延伸：不只是"可见性过滤"，还要"容器作用域正确"。 | 作用域意识不足，已有教训没有泛化 |
| 18 | **弹窗必须按标题或内容精确匹配，禁止 `find(第一个可见 wrapper)`**：多个弹窗同时存在时（"提示"关联弹窗 + "新建售后工单"弹窗），DOM 顺序决定谁排前面。取"第一个"结果是随机的。"提示"弹窗无 el-select → `sels[1]` undefined → throw。**规则：所有弹窗操作必须加 title 过滤：`t.textContent.includes('新建售后工单')`**。 | 没有考虑"多弹窗并存"场景 |
| 19 | **调用外部函数前必须先读其返回结构**：`navigate.js` 的 `erpNav` 返回 `{ success, data }`，代码却检查 `navResult.ok`（undefined），条件永远 falsy → 抛 "ERP导航失败: undefined"。**规则：调用新模块的函数，先用 `smart_unfold` 或 Read 看返回值结构，不要凭"猜测"写 `.ok / .result / .data`**。 | 没有验证 API contract |
| 20 | **新功能必须逐步骤自测，不能一次性跑全链路**：4 个 bug（死代码、全局选择器、弹窗不精确、navResult.ok）是独立的，但叠加在一起，每次只暴露最外层那个，要多轮才能清干净。**规则：逐函数独立测（cdp.eval 验证 DOM，再测单步 processOne），确认每步通过后再组装，最后再跑全链路**。用户明确说"一步一步来"，但我一次性写完提交，直接违反了这条。 | 过度自信，跳过分步验证 |

## 2026-05-12 session 教训

| # | 教训 | memory |
|---|------|--------|
| 11 | **批量执行用状态白名单，不用黑名单**：routes.js 未过滤 queue item 状态 → waiting 工单被批量执行拾取。修复：`BATCH_EXECUTABLE_STATUSES = ['simulated']` 白名单 + `isBatchExecutable()` 函数。新增状态默认不可执行，比"排除 waiting"更安全。 | feedback_jingling_dev.md §67 |
| 12 | **拒绝分类用 reasonCode，禁止 substring 匹配 message**：reject() 调用站点补 `reasonCode` 字段（`SIGNED_NO_INTERCEPT`/`AT_STATION`/`INTERCEPT_TIMEOUT`/`OVERDUE_RETURN`），批量执行白名单 `BATCH_SAFE_REJECT_CODES` 通过 reasonCode 判断，文本可改而枚举稳定。 | feedback_jingling_dev.md §68 |
| 13 | **ERP tab URL 匹配用 includes，不用 startsWith 硬编码子域名**：`viperp.superboss.cc` 打开后重定向到 `erpb.superboss.cc`。用 startsWith('https://viperp...') → 找不到已有 tab → 创建新 tab → 3 次调用堆 3 个 ERP tab。修复：`t.url.includes('superboss.cc')`。 | feedback_jingling_dev.md §69 |
| 14 | **op-queue.js execExecute 内禁止 execFileSync**：execFileSync 阻塞整个 Node.js 事件循环，SSE 无法 flush → 批量执行期间队列面板完全冻结，前端看不到进度，失败 toast 也被覆盖。改用 spawnAsync（已有函数）。 | feedback_jingling_dev.md §70 |
| 15 | **历史记录 source 字段区分批量/手动**：批量执行 `source:'batch_executed'`，手动执行 `source:'executed'`；入队时传 `fromBatch:true`。否则历史记录无法按来源维度复盘。 | feedback_jingling_dev.md §71 |

## 2026-05-06 session 教训

| # | 教训 |
|---|------|
| 8 | **ERP 自动登录的真正根因：单点依赖 Chrome 自动填充**。已修 5 轮（reload 时机、重试次数、页面判断等）每次都在调整"触发自动填充的时机"，但从未触及核心：Chrome 密码管理器在同一页面生命周期内只触发一次，macOS sleep 或 Chrome 长时间运行后这一次也变得不确定。真正解：确定性 fallback（凭据注入）+ 主动保活（1h fetch 续期）+ 熔断（避免失效时无限重试）。下次遇到"修了 N 次的问题"，先问：是在调参数，还是在解决根因？ |
| 9 | **"反复修复"场景必须先做 5-Why 再动手**：5 轮修复绕了一大圈都在表层——问题是时机不对、重试不够、reload 位置错，从没追到"为什么密码永远填不进去"。第六轮换了方法论：(1) 根因分析（Chrome 自动填充机制） → (2) 防御性设计（三层降级注入）→ (3) 主动预防（心跳保活）→ (4) 失败熔断（不无限重试）。"反复修复同一问题"是信号：当前方向错了，需要先停下来重新理解问题。 |

## 2026-05-14 session 教训

| # | 教训 |
|---|------|
| 21 | **Chrome 自动填充在 CDP headless 模式下完全不触发**。测试：reload → 等 20 秒，三字段（companyName/userName/password）全空。ERP 登录页 Phase 1 Chrome 自动填充已彻底废弃，直接用 `injectCredentials(targetId)` 注入（nativeSetter + dispatchEvent）。memory: feedback_jingling_dev.md §12/§43/§57 |
| 22 | **cdp.clickAt(input) 会清除输入框内容**。ERP 登录页点击任何输入框（用户名/密码）会触发 Chrome 表单重置，清除已有内容。"先点用户名再点密码"的旧逻辑是主动破坏。登录恢复中禁止点击输入框。memory: feedback_jingling_dev.md §43 |
| 23 | **主页面 el-select 必须用 data-km-mark + cdp.clickAt，JS .click() 完全无效**。el-select 监听 mousedown，JS click 不触发 mousedown，下拉永不展开。ERP 对应表 `setMainPageSelect` 旧代码用 JS click → `hasExact=false` 始终 → product-match 所有工单失败。修复：eval 内打 data-km-mark 标记，外部 cdp.clickAt 物理点击。memory: feedback_jingling_dev.md §76 |
| 24 | **setTimeout 重新调度前必须先 clearTimeout 旧句柄**。`scheduleNextScan()` 无 clear，resumeScan 每次调用叠加一个新 timer。用户多次暂停/恢复后 21 个 timer 同时触发，队列爆炸 70+ 条。修复：函数第一行 `if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }`。memory: feedback_jingling_dev.md §77 |

## 2026-04-23 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 18 | HTML data 属性嵌 JSON 必须单引号包裹 | feedback_jingling_dev.md §18 |
| 19 | batch-reprocess 含 auto_executed，禁止用于部分重查 | feedback_jingling_dev.md §19 |
| 20 | routes.js/data.js 改动后必须重启服务器 | feedback_jingling_dev.md §20 |

## 2026-04-28 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 21 | ERP trade-detail-dialog 关闭方式 | feedback_jingling_dev.md §21 |
| 22 | session 缓存跳过 reload 后必须清残留弹窗；`node -e require()` 会执行 main() | feedback_jingling_dev.md §22 |
| 23 | ERP 多行数据必须聚合读取 | feedback_jingling_dev.md §23 |
| 24 | ERP 交易关闭状态 fallback textSnippet | feedback_jingling_dev.md §24 |
| 25 | 已执行工单重处理防护（executedAt 检查） | feedback_jingling_dev.md §25 |
| 27 | 并发扫描同一账号导致 CDP 脏数据 crash | feedback_jingling_dev.md §27 |
| 28 | list.js 不点筛选标签会读到所有状态工单 | feedback_jingling_dev.md §28 |
| 29 | 驿站待取件 ≠ 已签收，两者处理方式不同 | feedback_jingling_dev.md §29 |
| 30 | collect.js 重采时必须继承 feedbackStatus/groundTruth | feedback_jingling_dev.md §30 |
| 31 | scan-all.js ok 状态必须整条覆盖，不能 Object.assign | feedback_jingling_dev.md §31 |
| 32 | 重启系统必须同时验证队列状态 | feedback_jingling_dev.md §32 |

## 2026-04-28 session 新发现（未入 memory，待稳定后迁入）

### 33. Express 路由顺序：字面路由必须在动态路由前注册

`router.post('/accounts/add', ...)` 必须在 `router.post('/accounts/:num/relogin', ...)` 之前注册。
即使路径段数不同（`/add` 是2段，`/:num/relogin` 是3段），Express 仍可能先尝试动态匹配，导致 `/add` 返回 404。
**修复**：所有字面路径（无 `:param`）统一注册到动态路由段之前。

### 34. pkill -f 杀进程不可靠，必须用 lsof 找 PID

`pkill -f "node server.js"` 可能杀不到真正监听端口的进程（存在多个同名进程时只杀其中一个）。
**修复**：重启服务器前先 `lsof -i :PORT` 拿到监听进程 PID，再 `kill <PID>`，再启动新进程。

## 2026-04-29 session 教训

### 35. launchd KeepAlive:true 导致多实例堆积

`KeepAlive: true` 的 plist 配置会在进程退出时无条件重启。如果同时存在手动启动的实例，launchd 会不断叠加新进程。
**根因**：6 个 server.js 同时运行 → 6 个 op-queue 同时触发 auto-scan → 6 个 cli.js list 同时操作同一 Chrome 标签页 → CDP 冲突 → workOrderNum crash + waitFor 超时。
**修复**：
1. server.js 添加 lockfile 单实例锁（启动时检查 PID，退出时清理）
2. launchd 改用 `KeepAlive: { SuccessfulExit: true }`（只在正常退出时重启）
3. 禁用重复的 launchd 扫描任务（com.jl.scan-orders 和 server.js 的 auto-scan 重叠）

### 36. Object.assign 合并状态会保留旧字段

`updateAccountStatus` 用 `Object.assign(prev, patch)` 合并，如果 patch 不含 `error` 字段，旧的 error 会残留。
**修复**：当 `patch.status === 'ok'` 时显式 `delete merged.error`。
**同类问题**：scan-all.js 的成功路径已用整条覆盖（正确），但 op-queue.js 的 updateAccountStatus 遗漏了。

### 37. list.js 导航 3 次刷新可合并为 1 次

原来的流程：`location.reload()` → Vue Router `$router.push()` → 筛选点击 = 3 次刷新。
**优化**：合并为 CDP `Page.navigate` 直接跳转完整 URL + 等待 Vue 初始化 + 筛选点击 = 1 次刷新。
**效果**：每个账号从 9-24 秒降到约 3 秒，12 账号扫描总时间从 ~3 分钟降到 ~40 秒。

### 38. Bash 工作目录陷阱

`node -e "require('./lib/...')"` 的相对路径基于 Bash 工具的持久工作目录（`/Users/chat/claude`），不是项目目录。
**修复**：用 `require('./aftersales-automation/lib/...')` 或在命令前 `cd`。反复犯同一个错误 = 转圈式失败，必须立刻换方法。

## 2026-04-30 session 教训

### 39. 对应表搜索输入框必须用 `.el-input-popup-editor`（严重 bug）

**问题**：`makeSearchBarcodeJS` 用 `inputs[pivotIdx+1]`（从 `.el-input__inner` 列表中按"平台商家编码"字段的下一个 input 定位搜索框），但实际搜索输入框在 `.el-input-popup-editor` 内，不一定出现在 `.el-input__inner` 的相邻位置。
**后果**：搜索值被填到错误的 input → 搜索不执行或搜到错误结果 → hcsp 和 kgoskfzh-sm 两个货号的 product-match 步骤持续失败 → 工单被 escalate → 69% escalation 率中约 2-3 条是这个 bug 直接造成的。
**修复**：`document.querySelector('.el-input-popup-editor').querySelector('input')` — **与 product-mapping 项目保持一致**。
**教训**：product-mapping 项目在同一个 ERP 页面早已验证了正确选择器（`.el-input-popup-editor`），aftersales 项目用了不同方法却没有拉通对齐，属于跨项目知识未复用。

### 40. NodeList 没有 .filter() 方法（JS 基础 bug）

`document.querySelectorAll(...)` 返回 NodeList，不是 Array。调用 `.filter()` 会抛 TypeError → `cdp.eval` 返回 undefined → 后续的 `=== 0` 或 `> 50` 守卫检查全部失效（undefined 不等于任何数字）。
**修复**：必须 `Array.from(document.querySelectorAll(...)).filter(...)`。

### 41. 调试 ERP 问题必须操作真实页面，禁止从旧采集数据推测

之前在 simulations.jsonl 里看到7个候选就断定"ERP对应表只有7行"，实际上那7个是在错误选择器下搜到的残留数据。正确做法：直接用 `cdp.eval` 操作真实页面、刷新后逐步检查，用眼睛看到的结果说话。
**铁律**：如果结论依赖 ERP 页面状态，必须亲自执行 DOM 操作验证，不能从有 bug 的采集结果倒推。

## 2026-05-01 session 教训

### 42. ERP 登录恢复禁止 reload 已在登录页的页面

Chrome 密码管理器在同一页面生命周期内只自动填充一次。`location.reload()` 清掉已填充的密码 → 后续点击密码框时 Chrome 不再触发。
**修复**：检测 `url.includes('login')` → 跳过 reload → 先点用户名 → 再点密码 → 3次重试。

### 43. 赠品必须和主品做完全对等的采集链路

collect.js 只对主品做了 product-match → product-archive，赠品只做了 erp-search。
**修复**：新增 Step 6b，赠品也跑完整的 product-match + product-archive 链路。
**教训**：新增采集步骤时必须检查"主品做了赠品是否也做了"。

### 44. 活动组合更新导致 archive 不含全部入库品

ERP 对应表 SKU 是当前版本，工单 attr1 是下单时版本。更新后 archive 可能缺少旧版配件。
**修复**：逐商品匹配后检查未匹配入库项 > 0 → escalate + attr1 解析提示。
**教训**：不能假设 archive.subItems 覆盖了所有入库品类。

### 45. DOM 选择器必须限定在目标容器内

archive.js `READ_SUB_ITEMS_JS` 用全局 `tr.el-table__row` 读到了主页面残留行（订单列表文本），导致 subItems 全是垃圾数据。
**修复**：弹窗内读取用 `dialog.querySelectorAll(...)`，不用全局 `document.querySelectorAll(...)`。

**⚠️ 2026-05-02 修订**：仅在 dialog 内限定还不够——硬编码列索引 [1][3][10] 在 dialog 表结构不同时失效；数据特征过滤（`!/^\d{6,}$/`）会把合法的非数字编码（如 kgoxnld、kgosbbb）误杀。**最终方案**：通过 `<th>` 表头文本定位列索引，不做任何正则/关键词/长度过滤。见 §48。

### 46. attr1 匹配必须先完整再 stripGift（两轮匹配）

ERP 对应表的 skuName 本身包含"赠XXX"后缀。一上来就 strip 两边都去掉了就对不上。
**修复**：两轮匹配 — 第1轮完整归一化，第2轮才去赠品后缀。

### 47. collect.js 步骤顺序必须按 ERP 页面分组

erp-logistics-all 放在 product-match 之后，ERP 已不在订单管理页面，需要切回去再切走。
**修复**：erp-logistics-all 紧接 erp-search，同一页面操作连续执行。

### 48. 读表格列数据：表头定位，不做数据特征过滤（2026-05-02）

archive.js 子品读取经历了三轮错误修复才找到正确方案：
1. 全局选择器 → 读到主页面垃圾 → 限定 dialog
2. 硬编码列索引 [1][3][10] → 表结构差异失效 → 退回全页+数据验证
3. 数据特征过滤（specCode 纯数字 ≥6 位、name 不含订单元数据）→ 把合法的 kgoxnld/kgosbbb 当垃圾杀了

**正确方案**：通过 `<th>` 表头文本（"商品名称"/"商家编码"/"组合比例"）定位列索引，直接读对应列。唯一允许的过滤：非空 + qty > 0。

**教训**：永远用表头文本定位数据源，不做数据内容的正则/格式过滤。这不是"验证"，是"误杀"。

### 49. 验证数据正确性 = 读实时源头，不分析旧采集（2026-05-02）

用户指出系统识别结果有问题时，反复分析 simulations.jsonl 里的过期数据做判断，而不是直接 `node cli.js product-archive` 读 ERP 实时数据验证。

**教训**：判断数据是否正确 → 从数据源头重新读取（ERP 页面、CLI 命令），不分析已有采集结果。验证单一环节用 CLI 直调，不走完整 pipeline。

### 50. 后台进程 osascript Reminders 失败需降级通知（2026-05-02）

server 进程无 TTY（PPID=1, TTY=??）时 osascript 操作 Reminders.app AppleEvent 超时 -1712。旧代码静默吞错。
**修复**：`createReminder(title)` 函数优先 Reminders，失败降级 `display notification`。
