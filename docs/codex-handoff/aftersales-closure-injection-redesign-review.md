# 请审计：鲸灵售后自动化大改造方案（逐账号闭环 + 安全注入 + 真点击导航）

From: Claude Code
To: Codex
Project: aftersales-automation
Action: review-plan
Timestamp: 2026-06-16
Status: 待 Codex 审计

## 背景

百浩账号 3 点"打开店铺后台"浏览器卡住、重复点 2 次后 IP 被封，平台回复"刷接口"。你（Codex）上一轮做了最小注入白名单、open-account 队列化、扫描终态进"已自动执行"等改动（见 `aftersales-minimal-inject-risk-handoff-20260615.md`）。Claude 复核后与用户对齐了一个更大的改造方案，现请你审计。

## 请重点审计的点（用人话反馈，用户来裁决是否采纳）

1. **安全注入用 `Storage.clearDataForOrigin('https://scrm.jlsupp.com', 'all')` 清该域全存储**——这个 CDP API 的 origin 参数能否精确只清 scrm 域而不误伤快麦 ERP（同一自动化 Chrome 内）？origin 是精确匹配还是前缀匹配？是否需要 protocol+host 完全一致？如果不可靠，按域 `Network.deleteCookies` + eval 清 localStorage 的回退方案是否更稳？

2. **注入后打开登录页 URL `micro-businessPlatform/login` 靠登录态自动跳后台**——这个假设是否成立？当前代码注入后进的是 `micro-customer/business/after-sale-list`。打开登录页URL在有 cookie 时是否真的会自动重定向进后台？会不会反而停在登录页导致误判注入失败？

3. **全局停止机制**：任何鲸灵操作报错→停整个售后系统+清残留+熔断+建提醒。这个"整系统停"会不会过于激进（一次偶发超时就停全系统）？残留检测（队列空/无running/关非主tab/无半开弹窗）是否覆盖完整？熔断态写 `circuit-breaker.json` 与现有 `erp-circuit-breaker.json` 是否会冲突？

4. **冒泡式处理算法**：翻页==刷新这个假设是否成立（翻页时鲸灵列表是否真的重新拉取最新数据，已处理工单是否会消失前移）？"超出时效就停止扫描"依赖列表已按逾期排序，若排序失败会漏扫——校验排序生效的方式是否足够？

5. **多 tab 管理**：点处理开新 tab 后用 `diffNewTargets` + `pickTargetByUrl` 锁定。若点击瞬间有其他无关 tab 也在变化（如 ERP 保活弹窗），差集会不会取错？处理报错关 tab 时若 `closeTarget` 失败如何兜底？

6. **逐账号闭环替代两阶段**：保留旧 `scan-account`/`scan-finalize` 作 feature flag 回退——feature flag 怎么切？新旧路径共存期间 queue.json 状态机会不会冲突？

7. **队列忙拒绝人工操作**：三个人工路由（refresh-status/open/open-ticket）队列非空就 409 拒绝。但 refresh-status 本身是"依次打开所有店铺"会占满队列——它自己入队后，用户再点别的就全被拒，这个交互是否可接受？是否需要给 refresh-status 特殊豁免？

## 完整方案全文

（以下为 Claude 写入 plan 文件的完整内容）

---

（见下方完整 plan 内容，已逐条标注「人话 + 技术表述」双栏，并嵌入用户原话引用）

# 鲸灵售后自动化 — 逐账号闭环 + 安全注入 + 真点击导航 改造

## Context（为什么做这个改动）

百浩账号 3 点击"打开店铺后台"时浏览器卡住，重复点击 2 次后 IP 被平台封禁，平台端回复"刷接口"。根因不是代码显式循环打接口，而是多个因素叠加让风控把请求模式判定为异常：

1. **注入不像真人**：当前 `injectSession` 复用停在旧账号的已登录 tab，直接逐条 `Network.setCookie` 注入新账号 cookie（**不清旧 cookie / 不清旧 localStorage**），再 reload。页面加载时读到残留的旧 localStorage（旧店铺ID、旧token），**先发起旧店铺请求再跳新店铺**——这就是你看到的"先显示旧后台再跳新后台"，也正是风控眼里的"多账号跳跃式切换"信号。
2. **内部跳转不像真人**：内部页面跳转用 Vue `$router.push()` 编程式路由，绕过页面按钮，无真人点击轨迹。
3. **失败不回写 + 多入口重复触发**：`scan-all.js` catch 块注入失败不回写状态，下次定时扫描重复注入；多个路由入队无去重，连点产生并发注入。

Codex 已做一轮改动（最小注入白名单只搬认证态、open-account 队列化单次注入、扫描终态进"已自动执行"），但 P0 风险点未堵，注入方式和导航方式的根本问题未解决。

**预期结果**：让自动化对鲸灵的每个请求，在平台后端看到的信号都和真人一致——清空旧身份后的单身份会话、真实按钮点击轨迹、失败即停不重复请求。同时"先扫完所有账号再统一处理"改为"逐账号完整闭环"。

---

## 核心设计（人话 + 原话/技术表述 双栏对照，方便核对）

### 一、安全注入：清空旧身份再注入（用户纠正后统一版）

> **用户原话**：「无平台页即使关掉tab但是没有退出登录，已经保留的登录状态依然存在……是否应该统一为，无论有没有平台页，先检测，关闭所有旧的鲸灵tab→清空cookie→注入→进首页？」「进首页的操作是注入后打开指定网址 https://scrm.jlsupp.com/micro-businessPlatform/login，打开后等10秒，检测页面状态是否是正确店铺，如果不是，直接报错停止所有操作而不是停止单店铺操作。」

> **DeepSeek 建议（用户采纳）**：只清 Cookie 绝对不够，必须连同 LocalStorage/SessionStorage/IndexedDB/SW/Cache 一起清。旧 localStorage 残留的旧店铺ID/token 会让页面加载时先发旧店铺请求 = 风控特征。应整站清除该域下所有存储，再注入，首动作像真人。

| 人话 | 技术表述 |
|------|---------|
| 1. 关掉所有旧的鲸灵标签页 | 遍历 `/json` 找所有 `scrm.jlsupp.com` 的 target，`closeTarget` 全部关闭（切断可能的 WebSocket 长连接） |
| 2. 把鲸灵这个网站的所有本地存储彻底清空（cookie、localStorage、sessionStorage、IndexedDB、缓存全清，但只清鲸灵这个域，不碰快麦ERP） | `Storage.clearDataForOrigin('https://scrm.jlsupp.com', 'all')`（按域清，ERP 域不受影响） |
| 3. 等几秒让后台残留请求断干净 | `sleep(3000~5000)` |
| 4. 注入新账号的最小认证态 | 现有白名单逻辑：`filterAuthCookies` + `filterIdentityLocalStorage`（只搬 JSESSIONID/_us/ssxmod_* + __supplierId__ 等身份键） |
| 5. 开新标签页打开登录页URL，靠注入的登录态自动跳进店铺后台 | `createTarget('https://scrm.jlsupp.com/micro-businessPlatform/login')`（有态自动进后台，无态停在登录页=注入失败） |
| 6. 等10秒，检测页面显示的店铺名 == 该账号配置的 note；不一致或仍在登录页→**报错停止整个售后系统** | 等 10s → 读页面店铺名 DOM（选择器待 dump）与 `accounts.json` 的 note 比对（如"百浩-RITEKOKO"）→ 不符抛错触发全局停止 |

**为什么统一清而不分情况**：关 tab ≠ 退出登录，服务端 session 和本地存储仍在；只有清空该域所有存储才能真正消除旧身份。这也是"店铺管理重新登录页是干净的"原因——它走 Playwright 全新浏览器无残留。

### 二、所有内部跳转改"真点击"（用户纠正了我的错误结论）

> **认知纠正**：内部跳转现在不是真点击，是 Vue `$router.push()` 编程式路由（绕过按钮直接命令路由跳），和"改网址"是同一类风控问题。

| 人话 | 技术表述 |
|------|---------|
| 除了"注入后打开首页/登录页"这一个动作用浏览器直接打开网址，其他所有平台内部页面跳转，都改成在当前页面上找到那个真实按钮、模拟人点一下，然后检测有没有跳到目标页，没跳到就报错 | 保留 3 处入口级 `cdp.navigate`（list.js:146、alerts.js:24、cli.js:61）；其余 `navigate()`(基于 $router.push) 改为 `clickNavigate`：找真实按钮→`clickAt` 点击→轮询 `isAtTarget` 到达→没到抛错即停。改造点：read-ticket.js:163、approve.js:57/88、add-note.js:69、logistics.js:139、reject.js:211、cli.js:162 |

### 三、多标签页管理（点处理会开新tab）

> **用户确认**：在工单列表点工单的"处理"按钮**会另开新浏览器标签页**。

| 人话 | 技术表述 |
|------|---------|
| 点处理前先记下当前有哪些标签页，点完对比多出来哪个，锁定那个新标签页去操作；处理完关掉它，切回工单列表标签页 | 点击前 `getTargets` 快照→点击→轮询 `diffNewTargets(before,after)` 找新增 targetId→`pickTargetByUrl` 按 URL/标题精确锁定（命中0或>1报错，禁止赌最后/第一个，落实坑#16/#25）→处理→`closeTarget`→`activateTarget` 切回列表 tab |

### 四、冒泡式扫描-处理算法（用户口述 + 最终简化）

> **用户原话（处理顺序）**：「先按逾期时间最近排序……从第一个工单开始处理，不刷新，处理完第一页的工单后……第二页同样依次处理……就像冒泡排序，你处理过的工单相当于已经冒泡到最前面了，从需要处理的列表里忽略它，依次看后面的工单。」

> **用户最终简化**：「可以去掉步骤10（处理完一页主动刷新），因为你在翻第二页的时候已经自动刷新了，所以你只需要在第二页没有的时候，回第一页从头找。」

**第一阶段（扫描，定清单）**：
| 人话 | 技术表述 |
|------|---------|
| 进列表页先按"逾期时间最近"排序 | 点排序按钮（选择器待 dump）+ 校验排序生效 |
| 从第一个工单依次往后看，逐个判断在不在时效范围内 | 遍历列表行，读每行逾期时间，与现有时效常量比 |
| 扫到某条超出时效就停（已排序，后面一定也超时）；本页扫完没遇超时就翻页继续 | `collectInScopeWorkOrders(sortedRows, maxHours)` 遇第一个超时即停 |
| 收集到的所有时效内工单号 = 本次待处理清单（顺序=页面顺序） | 返回工单号有序数组 |

**第二阶段（逐个处理，冒泡）**：
| 人话 | 技术表述 |
|------|---------|
| 回第一页，按工单号在列表定位那一行，点处理→新tab处理→关tab→切回→打标已处理 | `nextActionInPage`→`process`；多tab走"三"；`markProcessed` |
| 继续在当前页找清单下一个未处理工单号→处理（**不主动刷新**） | 当前页还有清单未处理→继续 process |
| 当前页清单全处理完→翻下一页（**翻页自带刷新**，已处理的冒泡前移消失） | 当前页清单全 done→`next-page` |
| 翻到第二页没找到原本应在第二页的工单（冒泡前移了）→回第一页从头找 | 翻页后当前页找不到清单未处理→`back-to-first` |
| 直到清单全部处理完 | 全 done→`complete` |

### 五、逐账号闭环（替代全量扫完再统一处理）

> **用户决策**：完整闭环含执行（approve/reject）；账号间强制间隔 20-30s，前一个 tab 关闭/确认完成才切下一个。

| 人话 | 技术表述 |
|------|---------|
| 每个账号一次做完：注入→扫工单→采集→推理→满足条件自动审批/拒绝→扫首页提醒，彻底做完再隔20-30秒切下一个 | 新增 op `scan-and-process-account` → `execScanAndProcessAccount`，替代 `scan-account`+`scan-finalize`批量入队；保留旧路径作 feature flag 回退 |

### 六、错误处理：整个系统停止（用户纠正：不是单账号中止）

> **用户原话**：「处理报错的话，我认为直接整个售后系统停止，并检测没有任何残留操作，然后给我创建一条1分钟后提醒的mac提醒事项，要写清楚错误情况，我来处理。」

> **确认范围**：所有鲸灵操作报错（注入失败/点击未到达/处理报错/检测错店铺）都触发整系统停止，不区分风控vs普通。

| 人话 | 技术表述 |
|------|---------|
| 任何一步鲸灵操作报错 → 立即停掉整个售后系统所有操作 | 抛全局停止信号：清空 op 队列、不再启动任何新 op、写 `data/circuit-breaker.json` 熔断态（重启不丢） |
| 停止后检测没有任何残留：队列空、没有 running op、所有临时新开的 tab 已关、没有半开的弹窗/未完成提交 | 检测 `opQueue.getState()` 队列空+无 running；遍历 tab 关闭所有非主鲸灵 tab；读页面 DOM 确认无半开弹窗 |
| 给我建一条1分钟后的Mac提醒，写清错误情况，我来处理 | `createReminder(标题含错误账号+错误原因, 1分钟后)`（helpers.js 已有 createReminder） |

### 七、堵 P0 风控风险点（Codex 漏掉的）

| 人话 | 技术表述 |
|------|---------|
| 扫描某账号注入失败时，立即把这个账号标记成失效，别等扫完统一写——否则下次定时扫描又去重复注入它 | `scan-all.js:174-178` catch 块加 `updateAccountStatus(num, expired/error)` |
| 人工触发的三种单一操作（刷新状态/打开后台/查看工单），只要队列里还有没跑完的活，就直接拒绝，不让它入队 | `routes.js` 三处入队前写死判断：`opQueue.getState()` 队列非空（有 running 或 queued）→ 返回 409 拒绝，**不做按账号筛选去重**。涉及 refresh-status(724)、open(740)、open-ticket(61) |

> **用户原话（去重逻辑的纠正）**：「刷新状态是依次打开所有店铺，如果无法连接则状态标记为异常。打开后台是单一账号页面打开，可以遵循安全注入的流程。查看工单也是单一账号页面打开，可以遵循安全注入流程，然后接模拟鼠标操作跳转到工单列表，找到工单后点击处理按钮进入对应页面即可，此时是人工处理所以不需要再检查标签页。以上三种情况，由于是人工处理，不需要筛选排队问题，直接写死如果队列非空不能执行，拒绝入队。」

**三种人工操作的行为说明**：
- **刷新状态**：依次打开所有店铺，连不上则该账号状态标记为异常。
- **打开后台**：单账号打开页面，走安全注入流程（清存储→注入→打开登录页→检测店铺名）。
- **查看工单**：单账号打开页面，走安全注入流程→模拟鼠标跳转到工单列表→找到工单点处理进对应页面。**人工处理，不需要检查/管理标签页**（区别于自动闭环的多 tab 管理）。

---

## 真实操作方法（用户指定：找/确认/点 三步分离，边做边测）

> **用户原话**：「直接一边做一边测试，我来指挥……找这一步不是实际操作，你可以单独进行……比如你截图然后在截图上标记给我，我来确认对不对，或者我开F12你找到之后我在F12里搜一下……如果核对位置没问题，再单独做一次点击操作的脚本测试，只点击，坐标由你前面确认好的点位来指定，这样点位的核对和操作就是分开的……就算一个点击操作错误，最多就是坐标错了，也不会触发风控。因为人也会乱点，这很安全。」

**每个 DOM 选择器/按钮的落地流程（你我配合）**：
1. **找（纯扫描，不操作）**：我只读当前页面 DOM 找目标按钮，截图标记给你 / 或告诉你位置信息你在 F12 搜核对。这一步不点击、不触发任何平台行为。
2. **你确认点位对不对**。
3. **点（单独最小脚本）**：点位确认后，单独做"只点这一个坐标/这一个按钮"的最小脚本测一次。

点位核对与点击操作**分开**——最多坐标错（等于人乱点一下），不触发风控。涉及选择器：退出登录按钮（注：统一清存储后可能不需要点退出，但店铺名检测、排序按钮、列表行处理按钮、详情入口仍需此流程拿准）、排序按钮、列表行处理按钮、店铺名显示位置、新tab特征。

---

## 工程约束

- worktree 内分阶段做（改 ≥3 文件 + 流程结构 + 跨项目 inject 脚本，三条都触发）。
- 铁律：鲸灵操作报错即停绝不重试（`wait.js` `FORCE_NO_RETRY_DOMAINS`）。
- 不能真实访问鲸灵试错；真实操作走上面"找/确认/点"三步分离，你指挥。
- 测试基线：`npm test` 67/67；本次不动 infer 决策逻辑（若触碰必跑 `node test/flow-test.js`）。
- 改 lib/ 后 `/aftersales-restart` 重启。
- 改 `sessions/jl.js` 保持 `inject <num>` CLI 契约（退出码、stderr 关键字）；注入成功后须 `saveSessionState`（坑#22）。
- 账号 3（百浩）已手动重新登录，可正常操作。

---

## 分阶段实施

原则：**纯逻辑先单测打穿**，**真实 DOM 操作走"找/确认/点"三步、你指挥**。选择器先在 `selectors.js` 留 null 占位。

### Phase 0 — worktree + 选择器骨架（纯单测）
- 建 worktree；新增 `lib/jl/selectors.js`（已验证的填实值，新增的留 null+注释"待 dump"）。
- 验证：`npm test` 67/67；`test/jl/selectors.test.js` 断言占位标记明确。

### Phase 1 — 堵 P0 风险（队列忙拒绝+状态回写，纯单测，先合并）
- `scan-all.js:174-178` catch 回写状态；`routes.js` 三处人工操作入队前写死：队列非空→409 拒绝入队（不按账号去重）；`op-queue.js` 新增 `isQueueBusy(state)` 纯函数（有 running 或 queued 即忙）。
- 验证：`test/server/queue-busy-reject.test.js` + `test/server/scan-all-status-writeback.test.js`；`npm test` 全绿，不碰鲸灵。

### Phase 2 — 冒泡处理纯状态机（纯单测）
- 新增 `lib/jl/bubble-plan.js`：`collectInScopeWorkOrders`、`makeBubbleState`、`nextActionInPage`（简化版无主动刷新中间态）、`markProcessed`/`markFailedAbort`。
- 验证：`test/jl/bubble-plan.test.js`（超时截断/翻页/冒泡回第一页/失败aborted/全完complete）。

### Phase 3 — 多 tab 管理器（薄壳+可单测决策）
- 新增 `lib/jl/tab-manager.js`：`diffNewTargets`、`pickTargetByUrl`、`openProcessTabAndLock`、`closeTabAndSwitchBack`；`cdp.js` 新增 `closeTarget`。
- 验证：`test/jl/tab-manager.test.js`（差集顺序无关/唯一零多命中/锁定超时）。真实关tab走"找/确认/点"。

### Phase 4 — 点击导航器（薄壳+可单测到达判定）
- 新增 `lib/jl/click-navigate.js`：`isAtTarget`、`clickNavigate`；`navigate.js` 改兼容壳内部调 clickNavigate；改造内部跳转调用点。
- 验证：`test/jl/click-navigate.test.js`（isAtTarget分支/clickNavigate mock到达与抛错）。真按钮跳转走"找/确认/点"。

### Phase 5 — 安全注入（清存储再注入 + 店铺检测）
- 改 `sessions/jl.js injectSession()`：关所有旧鲸灵tab→`Storage.clearDataForOrigin`清该域全存储→等几秒→注入白名单→开新tab打开登录页URL→等10s→比对店铺名与note→不符抛错触发全局停止。
- 新增 `lib/jl/inject-plan.js`：`isAtLoginUrl`、店铺名比对纯函数、注入步骤序列。`cdp.js`/jl.js 加 `clearDataForOrigin` 封装。
- 验证：`test/jl/inject-plan.test.js` 各分支。真注入走"找/确认/点"（店铺名选择器需 dump）。契约保持+saveSessionState。

### Phase 6 — 逐账号闭环 op（编排汇聚）
- `op-queue.js` 新增 `execScanAndProcessAccount`（注入→排序+冒泡收集→逐单多tab处理+真点击+approve/reject→扫首页→sleep 20-30s→下一个）；失败→全局停止+清残留+熔断+建提醒。保留旧路径 feature flag。
- `server.js runAutoScan()` 改每账号入队新 op。推理复用 pipeline 不改 infer。（注：定时扫描是自动流程，不受 Phase 1 的"人工操作队列忙拒绝"约束）
- 验证：`test/server/account-closure.test.js`（spy 测编排顺序/失败全局停/账号间隔）。改后 `/aftersales-restart`。端到端走"找/确认/点"。

### Phase 7 — 全局停止 + 残留检测 + 提醒（纯单测 + 联调）
- 新增全局停止机制：清队列+停新op+熔断持久化+遍历关非主tab+残留检测（队列空/无running/无半开弹窗）+`createReminder`1分钟后写清错误。
- 验证：`test/server/global-halt.test.js`（spy 测停止+清残留+建提醒调用）。

### Phase 8 — 真实 DOM 联调 + 选择器 dump 填充（你指挥，找/确认/点）
- 逐个选择器走"找/确认/点"三步填入 selectors.js：店铺名、排序按钮、列表行处理按钮、详情入口、新tab特征。
- 排序"按逾期时间最近"真实实现接入。
- 端到端：安全注入→单账号闭环（排序→冒泡→多tab→关tab切回→间隔）→风控信号观察。先低风险非百浩账号单次。
- 真跑前 `npm test` 全绿 + `/aftersales-restart`。

---

## Phase 依赖

```
Phase 0 ──┬─ Phase 1 (P0队列忙拒绝/状态回写) [纯单测,先合并]
          ├─ Phase 2 (冒泡状态机)  [纯单测] ┐
          ├─ Phase 3 (tab管理器)   [纯单测] ├ 可并行
          ├─ Phase 4 (点击导航器)  [纯单测] │
          ├─ Phase 5 (安全注入)    [纯单测] │
          └─ Phase 7 (全局停止)    [纯单测] ┘
                    ↓ (2,3,4,5,7 完成)
             Phase 6 (逐账号闭环编排)
                    ↓
             Phase 8 (selectors dump + 排序 + 端到端) [你指挥真跑]
```

纯单测可验证：0-7。需真跑（找/确认/点 + 端到端）：4、5、6、8 收口到 Phase 8。
合并节奏：Phase 1 先合并降封禁风险；2-5、7 独立 commit 可并行；6 汇聚；8 收口。

## 可单测纯模块

| 模块 | 纯函数 | 需求 |
|---|---|---|
| `lib/jl/selectors.js` | 配置 | 全局 |
| `op-queue.js` `isQueueBusy` | 队列忙判定 | 七 |
| `lib/jl/bubble-plan.js` | 收集/翻页/中止 | 四 |
| `lib/jl/tab-manager.js` | diffNewTargets/pickTargetByUrl | 三 |
| `lib/jl/click-navigate.js` | isAtTarget | 二 |
| `lib/jl/inject-plan.js` | isAtLoginUrl/店铺名比对 | 一 |
| 全局停止 | 残留检测纯判定 | 六 |

## 关键风险
1. jl.js 跨目录：保持 `inject <num>` CLI 契约。
2. 保留旧路径可回退（Phase 6 feature flag）。
3. 新操作失败一律报异常→全局停止，沿用 `domain:'scrm.jlsupp.com'`。
4. 安全注入后须 `saveSessionState`（坑#22）。
5. `Storage.clearDataForOrigin` 必须只清 scrm 域，不碰 ERP 域——需验证 origin 参数精确。
6. SKILL.md 同步：新增 selectors/bubble-plan/tab-manager/click-navigate/inject-plan + 全局停止机制须更新 ENTRY MAP + PATHS。

