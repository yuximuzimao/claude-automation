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
**2026-06-17 更新**：server 已由 LaunchAgent `com.heizong.aftersale-server` 接管；重启统一用 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`，`lsof` 仅用于排查端口占用和验证监听者。

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

## 2026-06-09 session 教训

| # | 教训 |
|---|------|
| 61 | **pipeline 历史执行守卫：skip 记录不等于"已执行"**。`pipeline.js` 的自动执行守卫通过 `!!s.executedAt` 检测是否已执行过，但"工单暂时不可访问"时的 skip action 也会写入 `executedAt`（自动归档逻辑）。工单恢复可访问后，新一轮 approve 决策被该 skip 的 `executedAt` 误判为"已执行"，导致永久跳过真正的审批操作。**修复**：守卫条件增加 `&& s.decision?.action !== 'skip'`，只有非 skip 的历史执行记录才阻断重复执行。**规则**：executedAt 代表"该工单曾被处理"，必须区分"真实审批操作"（approve/reject）与"跳过归档"（skip），两者语义不同，不能混用同一守卫。 |

## 2026-05-22 session 教训（归档重复根因分析）

| # | 教训 | memory |
|---|------|--------|
| 25 | **归档副作用是根因，不是重复写入本身**：`submitPendingFeedback` 在评价提交后自动调 `archive-manual` 归档（副作用），用户随后再点「归档」按钮又调一次，产生重复。正确设计：评价提交只提交评价，归档只由显式归档按钮触发。任何"捎带做了另一件事"的设计都要警惕。 | feedback_jingling_dev.md §80 |
| 26 | **写操作端点必须加幂等守卫**：`archive-manual` 缺少 `status=done` 检查，任意重复调用都会写新 case。所有写 `cases.jsonl`/`simulations.jsonl` 的端点，都要先检查目标状态再决定是否执行。 | feedback_jingling_dev.md §80 |
| 27 | **launchctl restart 后检查暂停状态**：如果系统在 stop 前已经是暂停状态，restart 后仍为暂停，需 `curl -X POST http://localhost:3457/api/resume` 或面板点「恢复运行」。若 stop 前是运行中的则自动恢复。 | — |

## 2026-05-29 session 教训（infer.js 赠品/在途规则修复 + CI 回归）

| # | 教训 |
|---|------|
| 57 | **`const` 内层变量重声明会静默遮蔽外层 `let`**：外层 `let giftPkgStatuses = []`，if 块内 `const giftPkgStatuses = ...` 不报错但覆盖了外层引用，导致下游 `giftPkgStatuses.forEach(...)` 永远遍历空数组。修复后首次正确赋值反而引入新 bug（见 #58）。JS 铁律：if/else 块内禁止用 `const`/`let` 重声明外层已有变量名。 |
| 58 | **`{ ...escalate(reason), waitingRescan: true }` 不能修正 action**：`escalate()` 返回 `{ action: 'escalate', ... }`，spread 展开后追加 `waitingRescan: true` 并不改变 `action`，额外字段只是多余。修复：直接返回 `{ action: 'reject', waitingRescan: true, reason, ... }` 字面量。 |
| 59 | **赠品物流校验只在 approve 门禁生效，不提前 escalate**：原代码在赠品未退回时直接 escalate，不管主品是否已签收。正确逻辑：主品状态决定拒绝/同意，赠品检查只在"主品全部退回准备 approve"时介入。修复：将 `giftNotReturned` 检查从赠品块移至 approve gate。 |
| 60 | **冻结测试期望必须跟着业务规则更新**：4 个 fixture 期望 `escalate`（旧规则），改为 `reject`（新规则）后测试通过。同时在途+赠品物流未知的案例也需更新。CI 回归失败是业务规则变更的直接反映，不是代码 bug。 |

## 2026-05-28 session 教训（ERP 物流修复 + 鲸灵物流 pipeline 超时）

| # | 教训 |
|---|------|
| 53 | **ERP 物流容器选择器必须用 CDP 实地验证**：`.js-logistics-container` 和 `.box-nav.box-toogle-el` 从 2026-04-27 初始提交起从未存在于生产 DOM（726 次超时 0 次成功）。实际 DOM 是 `.el-dialog__wrapper.trade-detail-dialog`；运单号用 `.list-title[运单号:].nextSibling`；物流文本用 `.box[h3.sub-title 含 "物流信息"]`。**规则：新 DOM 选择器上线前必须 cdp.eval 在真实页面验证存在**。memory: feedback_jingling_dev.md §81 |
| 54 | **鲸灵 logistics pipeline 超时 vs 隔离运行正常**：`cli.js logistics` 单独运行、`read-ticket → logistics` 序列均成功；但 collect.js 完整流水线稳定超时（waitFor 超时: 等待物流弹窗关闭）。根因未找到，待用户协助排查。下次：在 collect.js logistics 步骤前 log VISIBLE_DIALOG_COUNT_JS 值确认 pipeline 与隔离差异点。memory: feedback_jingling_dev.md §82 |
| 55 | **Element UI 弹窗 waitFor 必须检测内容加载完成，不能只检测骨架渲染**：`h3.sub-title` 存在仅代表骨架已渲染，内容区仍显示"暂无数据"（innerText ~317 字符）。内容异步填充后文本 ~3488 字符。条件改为 `hasH3 && !(text.includes('暂无数据') && text.length < 500)`。timeout 10s→15s，interval 500ms→800ms。memory: feedback_jingling_dev.md §83 |
| 56 | **`.some()` vs `.every()` 语义差异可导致退款误批**：判断"所有包裹是否都退回"必须用 `.every()`。`.some()` 表示任一满足，1 个包裹退回就批准整个订单。同时注意空数组 `.every()` 返回 true，需先 `.filter().length > 0`。memory: feedback_jingling_dev.md §84 |

## 2026-05-27 session 教训

### 51. jl.js 注入后页面就绪检测：轮询 readyState + Vue 初始化，不用固定延时

**问题**：`inject` 命令在 navigate 后等固定 2 秒，若页面未加载完毕就执行下一步抓取，得到的是上一个账号的数据。
**根因**：导航是异步的，固定延时无法保证页面已渲染完成；账号切换时旧 localStorage（storeId、userId）未清除，新账号的标识可能覆盖不完整。
**修复**：
1. 注入 localStorage 前先 `localStorage.clear()`，确保旧账号标识不残留
2. navigate 后轮询 `document.readyState === 'complete'`（最多 10 秒，500ms 间隔）
3. 继续轮询 `#app.__vue__` 初始化（最多 5 秒）
4. 验证最终 URL 不含 `/login` / `/sso`（跳回登录页 = session 失效）
**教训**：固定延时是最坏方案。能检测状态的地方必须用状态检测，不靠时间猜测。

### 52. 多子订单工单：logistics.js 只点第一个「查看物流」按钮，漏读其余子订单

**问题**：工单 `100001779759971976518` 含 3 个子订单（2 主品 + 1 赠品），鲸灵页面每个子订单有独立的「查看物流」按钮。系统只读到 1 个包裹（第 1 个子订单），漏读了第 2 个主品子订单和赠品子订单。
**根因**：`logistics.js` 的 `OPEN_LOGISTICS_JS` 用 `btns.find(...)` 只取**第一个**可见的「查看物流」按钮并点击，然后读弹窗内的 tab（包裹1/包裹2），这些 tab 只对应单个子订单内的多包裹，不跨子订单。
- 其余子订单的「查看物流」按钮被直接跳过
- 赠品子订单（748113610，快递 YT7623159902791）在 ERP 有发货记录，但鲸灵侧物流完全未读
- 推理因信息不足做出错误的 approve 决策

**正确方案**：先展开页面上所有子订单（可能有折叠的），再用 `querySelectorAll` 收集**所有**「查看物流」按钮，逐一点击 → 读弹窗 → 关闭，汇总所有子订单的物流。
**教训**：多子订单 = 多个「查看物流」入口。`find()` 只拿第一个，必须改 `filter()` + 循环处理全部。

### 53. LaunchAgent 双 plist 并存导致日志刷屏（2026-06-11）

`com.heizong.aftersale-server`（2026-04-29）和 `com.jl.server`（2026-05-25）同时存在于 `~/Library/LaunchAgents/`，指向同一 `server.js`。heizong 先抢 lockfile，jl 每 `ThrottleInterval=10` 秒重启一次、读到已有 PID 就退出，日志持续刷 `已有实例运行中 (PID xxxx)，退出`（共 89 条）。

**根因**：创建新 plist 时未删除旧 plist；两者 `RunAtLoad=true` + 不同 `KeepAlive` 配置形成竞争。

**修复**：旧 plist rename 为 `.disabled` 后缀（launchd 只扫 `*.plist`，`.disabled` 不会被加载）。不删除保留后悔药。

**铁律**：
1. 更换 LaunchAgent plist 时，必须先 `launchctl bootout` 旧项 + rename 旧 plist，再 bootstrap 新项
2. 诊断时用 `launchctl print gui/$(id -u)/<label>` 而非 `launchctl list`（list 在某些环境不完整）
3. 新旧 plist 并存且都 `RunAtLoad=true` 的状态随时可能在重启后复现冲突，即使当前安静

### 54. EnterWorktree 默认从 origin fresh 切，会落后于当前本地分支（2026-06-16）

执行"停旧系统"重构时，在 `data-model-restructure` 分支上 `EnterWorktree`，得到的 worktree 基线却是 `cd555ae`——落后当前分支 30+ commit，缺了百浩风控修复等关键更新。直接合并会污染主分支、丢失这些更新。

**根因**：EnterWorktree 的 `worktree.baseRef` 默认 `fresh`，从 `origin/<默认分支>`（main）切，而不是当前本地工作的分支 HEAD。当本地分支领先 origin 默认分支很多时，worktree 基线就严重过时。在项目 `.claude/settings.json` 设 `worktree.baseRef: head` 后**当前 session 的 EnterWorktree 仍未读取**（设置疑似需重启 session 才加载）。

**正确做法**：不依赖 EnterWorktree 自动切基线。手动 `git worktree add <路径> -b <新分支> <当前分支>` 显式指定基线为当前分支，再 `EnterWorktree({path: <路径>})` 进入已注册的 worktree。

**铁律**：
1. 开 worktree 前先 `git -C <worktree> log --oneline -1` + `git log --oneline <worktree分支>..<当前分支>` 验证基线（后者应为空）。基线错了立即删掉重开，不要在错基线上写代码。
2. 当前分支领先 origin 默认分支时，永远手动 `git worktree add ... <当前分支>` 指定基线，不靠 EnterWorktree 默认 fresh。
3. 合并前确认 fast-forward 可行（`git merge-base --is-ancestor <当前分支> <worktree分支>`），用 `git merge --ff-only` 避免意外 merge commit。

### 55. server.js 由 LaunchAgent KeepAlive 守护，kill 后会自动重启（2026-06-16）

`/aftersales-restart` 重启后，新 PID（PPID=1）由当前 `com.heizong.aftersale-server` LaunchAgent 接管；旧 `com.jl.server.plist` 已改名为 `.disabled`，不得重新加载形成双托管。

**影响**：重启验证时不能假设"kill 后端口空闲需手动 nohup 启动"——launchd 会自动重启并加载磁盘上的最新 server.js。要验证新进程加载了新代码，看 `ps -p <PID> -o lstart` 确认启动时间晚于 kill 时刻，再从 server.log 最后一次"已启动"横幅截取该进程的日志段（log 是 append 模式，新旧混写）。

**铁律**：grep server 进程用完整路径 `aftersales-automation/server.js`，不用 `node server`（漏匹配 nvm 全路径 node）。lsof -ti:3457 会列出 Chrome 网络进程的连接，需 `ps -p` 辨明真正的 server 监听者。

### 56. 已登录目标账号时禁止重复注入（2026-06-17）

新安全注入路径（第二步）的底层逻辑就是「先检测能否复用、已登录目标账号就跳过注入直接用」。但 2026-06-17 验证 04-inject 完整版时，我在已登录百浩的情况下又跑了一次 `04-inject.js 3` 重复注入——这恰恰是第二步要消灭的危险操作，自相矛盾。

**根因**：把"测试脚本功能"凌驾于"业务正确流程"之上。注入是写操作，已登录目标账号时再注入 = 无意义的重复登录态写入，是风控眼里的异常信号。

**铁律**：
1. **任何脚本/测试都不得在「已登录且店铺名匹配目标账号」时执行注入**。注入前必须先 02 检测登录态：`logged-in` 且 `matchShopName` 通过 → 直接复用，不注入。
2. 验证注入脚本本身时，只能使用本就未登录且已获用户许可的场景；禁止为了测试调用已停用的 03 退出，也禁止在已登录态强行重注入。
3. 正确的统一前置流程：确定唯一 tab → 读登录态 → 匹配目标则复用 / 未登录或错号则清 Cookie 并二次验证后注入。复用是常态，注入是例外。

### 57. 注入与导航必须解耦，导航由安全编排绑定目标 tab（2026-06-19 最终态）

`sessions/jl.js inject <num>` 只写认证态，不负责页面跳转。`openAccountFlow` 必须把已经过 tab 数量门、Cookie 清理和二次验证的同一个 `targetId` 传给 `04-inject.js`；04 只对该 tab 固定导航售后列表并校验店铺名。

**铁律**：禁止注入后重新 `.find()` 任意鲸灵 tab；CLI 未显式传 `targetId` 时只接受唯一鲸灵 tab，多个直接报错。

### 58. 切换鲸灵账号禁用"退出登录"，改清cookie；JSESSIONID在seller-portal域（2026-06-17）

真机验证 A2 错号切换：从账号1界面点账号2"打开后台"→退出账号1→进账号2无反应→回头账号1也失效。**鲸灵"退出登录"是破坏性操作，让原账号服务端 session 失效**，不能用来切账号。

**根因（第一性）**：要的不是"退出"或"隐私窗口"这个形式，本质是「注入前页面没有旧账号残留」。

**铁律**：
1. 错号/未登录切换账号 = **清当前 tab 的鲸灵 cookie/storage → 注入新账号**，绝不点退出登录。03-logout 已停用。
2. **清 cookie 必须显式覆盖全部 jlsupp 子域**：真登录凭证 `JSESSIONID` 在 `seller-portal.jlsupp.com/merchant`，`_us` 在 seller-portal+scrm。CDP `Network.getCookies({})` 默认只返回"当前 tab URL 适用"的 cookie，**看不到 seller-portal 的 JSESSIONID → 漏清 → 新账号注入后混旧账号登录态**。必须 `getCookies({urls:[scrm, seller-portal, seller-portal/merchant]})` 取全集再逐条 deleteCookies。
3. **判"清干净"看登录凭证(JSESSIONID/_us)是否全域清零，不是数 cookie 条数**：WAF/验证码指纹(acw_tc/cdn_sec_tc/_dx_*/ssxmod_*)清掉后页面会立即重种，这是正常的（本应浏览器自生成），不算残留。
4. 清理后必须二次 `Network.getCookies({urls:[...]})`；只有 `verified:true` 才允许注入。残留错误只输出 cookie 的 name/domain/path，不输出 value。
5. 工具：`cdp.clearJlCookiesAndStorage(targetId)` + `scripts/jl-steps/07-clear-jl-data.js`。

### 59. 注入后禁止原地 reload，固定导航售后列表（2026-06-19 最终态）

原地 `Page.reload` 会继承旧 tab URL。若上一账号停在某张工单详情，新认证态刷新后会形成“新店铺身份 + 旧工单路径”的上下文错配风险。

**最终时序**：确定唯一 `targetId` → 清 jlsupp Cookie/storage → 二次确认 `JSESSIONID/_us` 清零 → 注入该账号认证态 → 对同一 `targetId` 导航固定售后列表 URL → 读取实时店铺名并匹配目标账号。任一步失败立即停止，不重试。

### 60. 状态标记不能既挡 UI 又挡后端，高风险入口要留人工放行通道（2026-06-22）

账号12（顺链-肺肽）切换时网络抖动报一次错，被写入 `account-status.json` 的 `status:error`。旧逻辑下 `error/expired` **同时**触发两道封锁：前端隐藏「打开店铺后台」按钮 + 后端 `/api/accounts/:num/open` 经 `getAccountOpenGuard` 直接 409。结果一个其实正常的账号被双重锁死，没有任何自助恢复路径——只能手改 JSON。

**根因（第一性）**：把"单次操作失败"等同于"账号已失效"，并且用"既隐藏入口、又拦后端"的双保险把人也挡在外面。状态标记的本意是**降级提示风险**，不是**剥夺操作权**。失败可能只是网络抖动，不是账号真失效。

**铁律**：
1. 风险状态可以加提示、加确认，但**不能既挡 UI 又挡后端把入口彻底封死**。
2. 高风险操作入口（打开后台 = 真实登录写操作）必须保留「人工确认放行」通道：前端 `confirm` → 后端凭 `confirmed:true` 放行 `getAccountOpenGuard` 拦下的账号（仍返回 `needConfirm:true` 供前端区分）。
3. 正常态也保留「重新登录」入口（`shouldShowReloginButton` 对 `ok` 返回 true），随时可手动重登；仅 `unknown`（已保存未扫描）不显示，避免误导为已失效。
4. 改动文件：`public/account-relogin-state.js`、`public/app.js` `openAccountStore`、`lib/server/routes.js` `/accounts/:num/open`。回归用例见 `test/server/relogin-session.test.js`。

### 61. el-pagination 物理点击失效原因是 viewport 边界，不是 Element UI 结构（2026-06-29）

鲸灵售后列表分页条（`.el-pagination`）`top ≈ 2400px`，CDP `Input.dispatchMouseEvent` 只处理 viewport 内坐标，超出 viewport 的点击被浏览器静默丢弃——诊断时页码停留在第 2 页长达 40 次轮询，物理点击完全无效。

**两类 CDP 点击失效的根因完全不同：**

| 故障 | 现象 | 根因 | 正确修法 |
|------|------|------|---------|
| el-select 下拉候选项 | `filter(visible)` 返回空 | dropdown li 的 `getBoundingClientRect().height = 0` | Vue emit `input` + `change` |
| el-pagination 翻页按钮 | 物理点击静默无效，页码不变 | 分页条在页面底部，超出 CDP viewport 坐标范围 | `mouseWheel` 大幅下滚 → 重读坐标 → 物理点击 |

**铁律**：
1. 元素坐标超出 viewport → 先 `mouseWheel` 大幅滚动（不用计算精确量，滚到页底即可），重读 `getBoundingClientRect()`，再物理点击（与 step 12 `scrollActionButtonIntoView` 同原则）。
2. `getBoundingClientRect().height = 0` → 才改用 Vue emit（el-select 专属）。
3. 绝不因"Vue emit 可用"而跳过物理点击——Vue emit 绕过了真实用户行为信号，应作为最后手段。
4. 侧边栏固定元素（如"后台首页"`.nav-item`）fixed 定位，始终在 viewport，直接 DOM `.click()` 即可，不需要滚动。

---

## 2026-06-29/30 session — A1 执行/重新采集重构教训

### CDP dispatchMouseEvent 后台 tab 必超时
- **现象**：`clickWorkOrderAction` 打开详情新 tab 后，列表 tab `Input.dispatchMouseEvent` 卡死 30s
- **根因**：Chrome 不处理非激活 tab 的 input 事件
- **修复**：`cdp.dispatchMouseEvent()` 包装函，每次先 `activateTarget` 再发事件
- **规则**：所有 mouse 操作必须走 `cdp.dispatchMouseEvent`，禁止直接 `cdp.cdpCall(target, 'Input.dispatchMouseEvent', ...)`

### inferDecision 第二参数必须是 queueItem
- `processOpenedDetail` 回调传 `ctxTicket`（仅 workOrderNum/type/accountNote）→ deadlineAt/urgency 全空 → remainingHours=null → JS 里 null>12=false → 误判
- **规则**：`inferDecision({ collectedData }, queueItem)` 第二参数必须是完整 queueItem

### waitForNewWorkOrderTarget 只在 URL 匹配后即返回
- 详情 tab URL 含工单号就判定成功，但 body 可能未渲染
- 紧接着 `approveTicket(skipNavigation:true)` 直接校验 body → 失败 → 错误处理把详情 tab 导航到列表页
- **修复**：去掉 skipNavigation，让 approveTicket 自己 navigate（内含 3s wait）

### prepareAfterSaleList 读全量列表 → 多余操作
- 执行/重新采集只需找单个工单，`readUrgentAfterSaleList` 读了全部页
- **修复**：改为只做导航+排序，由 `locateWorkOrderOnFreshList` 逐页搜索

### ERP shop-map 名称必须与页面实际标签完全一致
- SHOP_MAP: `erpShop: '16广州茗瑞'`，页面标签: `广州茗瑞`（无"16"）→ 永远匹配不上
- 第一条工单（不同店铺）成功通过，掩盖了后续失败

### 重新采集推理的 API 路由 ≠ op 类型
- 前端按钮调 `POST /simulations/:id/reinfer`（`execReinfer`），不是 `POST /queue/:id/reprocess`（`execReprocessOne`）
- `execReinfer` 还在走旧的 `pipeline.reprocessOne` → 功能完全无效
- **规则**：改功能时检查所有触发入口（前端按钮 → 路由 → op 类型 → 执行函数）

### collect.js --workOrderNum 未匹配时 exit 1
- 旧逻辑 exit 0 → pipeline 拿旧 simulation 数据推理 → 用户看到"秒完成"
- **修复**：显式指定 workOrderNum 但未找到时 exit 1

### 旧 hint 残留污染新推理
- pipeline.collect.js 失败时写 `hint: '采集连续失败，需人工核查'` 到 queue item
- `execReinfer` 没清除 → `inferDecision` 读到非空 hint → 当用户评价指令覆盖推理
- **修复**：`execReinfer` 把新 hint（空输入则为 null）写入 queue item

## 2026-06-30 session 教训

### processOpenedDetail 传 raw ticket 给 inferDecision（#29 延伸）
- SKILL.md #29 记录了 `pipeline.js`/`op-queue.js` 的修复，但 `14-process-single-account-fixed-batch.js` 的 `processOpenedDetail` 仍在传原始扫描 ticket
- `context.ticket` 只有 totalHours/type/workOrderNum，没有 queueItem 的 deadlineAt/urgency/hoursUntilNextScan → remainingHours=null
- **规则**：新增 `inferDecision` 调用方时必须检查第二参数是否完整 queueItem。`hoursUntilNextScan` 不在持久化字段中，需 `getHoursUntilNextScan()` 动态追加

### 前端 badge 更新依赖 SSE 事件，切换标签不触发
- 快递行动红点仅页面加载和 SSE 事件时更新，切标签时 `loadActionBadge()` 不被调用 → badge 停滞
- `loadActionBadge()` 不查 `/api/action-dismissed` → 已标记处理的条目仍被计入 → 红点虚高
- **规则**：标签切换时，非当前 tab 的 badge 也要刷新；badge 计数逻辑必须与列表渲染逻辑同源（查同一份 dismissed 数据）

## 2026-07-01 session 重大事故

### 🔴 级别：严重事故 — git fast-forward merge 删除全部运行时数据

**影响**：merge 后 211 个文件从磁盘消失，包括：
- `aftersales-automation/data/queue.json`（~1222 条实时工单）
- `aftersales-automation/data/simulations.jsonl`、`cases.jsonl`、`feedback.jsonl`
- `product-mapping/data/imgs/` 146 张商品图片
- `product-mapping/data/products/` 全部产品配置

**根因**：老 main（cd555ae）里 `data/` 文件仍被 git 追踪，但合并目标 data-model-restructure 分支里的 `ac377b1`（5月29日）已通过 `git rm` 删除了这些文件的追踪。fast-forward merge 时，git 发现新 HEAD 里这些文件已被删除 → 物理删除磁盘文件来对齐工作目录。

**为什么 git 会删文件**：
1. 老 main 里 data 文件是 TRACKED 状态
2. dev 分支里已被 `git rm` 删除追踪
3. merge 看到：文件在老 HEAD 追踪、新 HEAD 不追踪 → 执行删除
4. `.gitignore` 阻止不了——它只管未追踪文件，已追踪文件不受 `.gitignore` 保护

**恢复情况**：产品图片/配置从 git 历史恢复；aftersales 运行时数据只能恢复到 6月8日备份（1026条），6月9日-7月1日的新增数据永久丢失。

**铁律（所有项目通用）**：
1. merge 前必须跑 `git diff --diff-filter=D <old> <new>`，确认不会删除任何运行时数据文件
2. 如果删除列表包含 `data/`、运行状态文件、日志 → 先备份，再 merge
3. 清理 git 仓库时，如果两个分支对"哪些文件不追踪"不一致 → 先对齐老分支（`git rm --cached`），再 merge
4. `.gitignore` 只能保护从未追踪过的文件。已追踪文件必须先用 `git rm --cached` 取消追踪，之后 `.gitignore` 才生效

### 🔴 execOpenTicket 修复不完整——表层审查的教训（2026-07-01）

- 声称"已修复 execOpenTicket 并完成全量审查"，但实际修复只做了一半：把裸 `spawnSync inject` 换成了 `openAccountFlow`（注入安全了），但打开工单的方式仍然是 `navigate(targetId, url)`——Vue Router 直接 URL 跳转，没有模拟鼠标点击。
- 用户点击"查看工单"后，系统直接导航到详情页 URL，而不是：进入列表→找到工单→模拟点击按钮→打开详情 tab。和 `execExecute` 的实际行为不一致。
- 审查时看到 `openAccountFlow` 就打了勾，没有继续往下读后面的导航逻辑。**审查只看函数签名和 import，没有追踪完整的执行流。**
- **规则**：审查代码链路时，必须逐行读完整执行流，不能在某一步"看到安全了就停"。审查 = 确认每一个步骤的行为和预期一致，不是确认某个函数被调用了。
