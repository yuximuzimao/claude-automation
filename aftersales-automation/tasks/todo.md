# 待处理问题台账（2026-06-19 更新）

> 按执行顺序排列。Phase A 修点，Phase B 架构重构。

---

## Phase A-0：文档引用清理 ✅

- [x] lib/ 中 6 处 `见 RULES X.X` 注释 → 已更新为 docs/ 实际路径
- [x] RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，此条目已关闭

---

## Phase A-1：脚本架构拆分 ✅

- [x] **A1.1** 定义采集数据 Schema → `docs/collect-schema.md`
- [x] **A1.2** infer.js 入口加数据完整性校验（validateCollectedData）
- [x] **A1.3** infer.js 四个 flow 拆分为独立函数（inferRefundReturn / inferRefundOnly）

---

## Phase A-2：店铺管理 UI 修复 ✅

- [x] **A2.1** scan-all.js：写 ok 状态时整条覆盖（清除残留 error 字段）
- [x] **A2.2** UI：`error` 状态账号也显示"重新登录"按钮
- [x] **A2.3** UI：店铺管理页新增"新增店铺"按钮
- [x] **A2.4** UI：每个账号行新增"打开店铺后台"按钮（调用 jl <num> 打开鲸灵）

---

## Phase A-3：虚假工单扫描修复

- [x] **A3.1** 排查账号2（展宏妍）崩溃：防御性修复 `out.data.urgent` undefined crash
- [x] **A3.2** 账号12顺链18个工单：queue 现已全部 done，A3.3 修复后可防止再发生
- [x] **A3.3** 修复 list.js 筛选：读工单前先点击"待商家处理"筛选标签

> 并发竞争根因（A3.1）：两个批次同时扫同账号，cli.js 通过 CDP 接收到脏数据导致 out.data undefined；防御性修复已加；待实际扫描验证无复发

---

## Phase A-4：判断逻辑修复

### P0：资金安全

- [x] **A4.1** 移除"ERP发货行数 vs 申请套数"错误规则 → 已替换为"发货行数 vs 采集到的包裹数"完整性校验（见 A4.6）
- [x] **A4.2** 商责关键词补全：`MERCHANT_FAULT_REASONS` 加 `'少件'`、`'缺件'`
- [x] **A4.3** 终态识别补全：加 `'已取消'`、`'用户已取消'`、`'客服-已同意'`、`'客服-已拒绝'`

### P1：流程准确性

- [x] **A4.4** 超期退货检测（补全）：售后原因=`其他`/`质量问题` + remark 含超期关键词 + 物流签收时间距今>7天 → 拒绝 ✅ 已验证（签收时间从物流文本解析，三重校验）
- [x] **A4.5** 驿站待取件判断修正：仅退款已发货 + 物流"驿站待取件" → 拒绝+拦截提醒
- [x] **A4.6** 物流采集完整性：erp-logistics-all 遍历所有ERP行读物流，infer.js 兼容多行数据，不再只采 rowIndex=0
- [x] **A4.10** 物流状态逐包裹判断：SIGNED_KEYWORDS 增加门口投递关键词（放置门口/投递门口/放门口），覆盖家门口签收场景

### P2：数据层

- [x] **A4.7** 赠品数量计算：应退总数 = 主品(afterSaleNum×subItemNum) + 赠品数量，入库总数统一比较 ✅ 已验证
  > 剩余问题：部分案例 ticket.gifts=[]（赠品未被采集到），属采集阶段 bug，非推理问题
- [x] **A4.8** 重复归档防护：processOne/reprocessOne 已有 prevExecuted 检查，已覆盖
- [x] **A4.9** 重新采集保留评价字段：collect.js 重采时继承 feedbackStatus/groundTruth

### P3：系统健壮性

- [x] **A4.11** 工单页面找不到时误报：read-ticket.js + approve.js 已加反查列表逻辑，区分"已处理"vs"详情页加载失败"
- [x] **A4.12** ERP未登录/标签页缺失自动恢复：read-logistics.js 加登录检查，navigateErp 加 recoverLogin 重试
- [x] **A4.13** 时效显示精度：UI改为总小时数保留1位小数（如38.5h），infer.js去掉"充足/紧张"定性描述

---

## Phase B：架构深度重构（Phase A 稳定后）

- [x] ~~**B1** Phase 2 无痕浏览器隔离~~ **已永久放弃**：2026-05-28 实施 tab 隔离方案时 ensureTab 并行创建触发鲸灵 IP 风控（HTTP 426），回退后决定不再尝试
- [x] **B2** collect-schema.md 正式文档化 → `docs/collect-schema.md`

---

## 2026-06 A1 逐账号扫描闭环待办

> 当前交接入口：先读 `docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md`，再读 `docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md` 和完整确认计划。账号 14 茗瑞-KGOS 的关闭自动执行最小整账号固定清单批次已验证；后端 `op-queue/API` 入口已接入并经审查加固，前端单账号 no-auto 入队按钮代码已接入；live 三标签店铺筛选与批量 scope 加固已完成。仍未重启加载、未放开真实自动执行。不要重启加载正式入口、不要真实 approve/reject。

- [x] **A1-atomic-08-12** 真机最小测试并沉淀原子脚本：点击「售后工单」、选择按逾期时间最近排序、读取 48h 内列表、列表准备编排、按指定工单号打开正确处理 tab。验证：相关 node:test 12/12，通过全量 `npm test` 119/119。
- [x] **A1-chain-single-account-open-ticket** 已新增 `13-open-single-account-work-order.js`，串联 `openAccountFlow(num)` → `prepareAfterSaleList()` → urgent 目标门禁 → `clickWorkOrderAction(workOrderNum)`；只打开并定位正确工单详情 tab，不做同意/拒绝。相关测试 32/32，全量 `npm test` 129/129；真实账号/工单真机验证需用户指定目标后执行。
- [x] **A1-direct-after-sale-navigation** `04-inject.js` 注入后不再 reload 旧 URL，固定导航售后列表并保留店铺名匹配；`openAccountFlow` 在 Cookie 清理 `verified === true` 后把同一 targetId 传给 04，避免清理 tab A 后导航/验证 tab B；CLI 未传 targetId 时只接受唯一鲸灵 tab。`11-prepare-after-sale-list.js` 对指定 targetId 直接导航列表后再校验/排序/读取，不再依赖首页菜单或弹窗。旧 reload 会继承详情路径并可能造成店铺与工单上下文错配。停止账号 4-14 弹窗枚举测试，本轮不做真实浏览器操作。第二轮 TDD：相关测试先 10/15（5 个预期失败）RED，修改后 15/15 GREEN；关键链路 36/36、全量 `npm test` 138/138。
- [x] **A1-read-list-total** 列表页“共 N 条”、分页稳定读取、目标工单定位和详情 tab 锁定已进入真实页面链路验证。2026-06-26 用户指定账号 14 茗瑞、工单 `100001782462690101360` 后，步骤 09/10/13 成功完成排序、读取列表、定位目标工单并打开详情 tab。步骤 09 固定执行下拉命中，不因当前值已是目标排序而跳过，并补齐 3 个可能下拉文案的识别。
- [ ] **A1-single-account-fixed-batch-chain（账号14最小整账号批次已验证；no-auto UI 代码已接入）** 单账号固定清单逐单串联已有草案实现；排序后首次读取的全部 `<=48h` 工单已确认作为“本轮不可变清单”。2026-06-24 已补 queue/simulation 写回、非自动执行/列表消失回原“待确认”、自动执行回原“已自动执行”、等待重查回原 `waiting`、`fixed_batch` 来源终态 `skip` 也进入原“已自动执行”列表，并加强详情 tab/账号收尾清理校验。2026-06-25 已补自动执行 journal 残留 intent 阻断：发现 `auto_executing` 残留时不再 approve，转回 `simulated` 并写明需人工复核。2026-06-26 用户授权完整采集，并允许写回“待确认/等待重查”后，账号 14 茗瑞、工单 `100001782462690101360` 已完成单工单完整采集、推理和模拟写回：工单类型由 `323` / `仅退款（无需退货）` 归一为 `仅退款`，采集跳过商品明细和退货快递核验，ERP 搜索 2 次、ERP 物流 3 次、物流包裹 2 个，推理结论为 `escalate`，原因是主品已退回但赠品 `YT7629306404466` 在途未拦截成功，需人工确认。写回 queue 状态为 `simulated`，simulation id 为 `manual-collect-1782470482079-100001782462690101360`；用户随后手动删除页面中的推理采集信息，`queue.json` 已无该 active item，但 `simulations.jsonl` 仍保留历史记录。2026-06-26/27 已完成账号 14 茗瑞-KGOS 关闭自动执行的最小整账号固定清单批次：冻结清单 4 张，4 张均完成列表定位、详情 tab、采集、推理、写回 queue/simulation、关闭详情 tab；queue 均为 `status:"simulated"`、`source:"fixed_batch"`，无 `executedAt`/`autoExecutedAt`，收尾后仅保留 1 个鲸灵售后列表主 tab。后端 `POST /api/accounts/:num/a1-fixed-batch` 已接入 `op-queue`，显式单账号入队，默认 48 小时清单且强制 `disableAutoExecute:true`。2026-06-27 GPT 审查后已加固：固定清单入口读取 `account-status.json` 并 fail-closed，`expired/error` 不支持 `confirmed:true` 绕过；入队前预检 session 文件名、realpath、JSON、认证 Cookie 和目标域身份 localStorage；op-queue 层也强制 48h/no-auto。2026-06-27 前端按钮代码已接入：仅 `status=ok` 且有 session 的账号显示，点击后二次确认，只 POST 空 body 到单账号 endpoint，不传 `thresholdHours`/`disableAutoExecute`/账号数组。仍不得重启加载正式入口、不得真实 approve/reject。

  每张固定清单工单严格串行：在列表定位工单号 → 复用步骤 12/13 点击该工单的处理按钮并锁定新 `detailTargetId` → 在该详情 tab 完成采集、推理、自动执行判定 → **写回原售后系统 queue/simulation** → 只有命中现有自动执行范围才直接处理 → 关闭详情 tab 并确认已关闭 → 回到列表 tab → 处理下一单。

  **原系统兼容前置**：不能创造新的正式状态或独立批处理结果页。每张工单仍必须写入/更新 `data/queue.json` 和 `data/simulations.jsonl`，继续由 `/api/queue?mode=live`、`/api/simulations?mode=live` 和 `public/app.js` 原有三标签渲染。`manual_review` 只能作为草案内部临时状态，落地时必须映射回原“待确认”列表可展示状态（如 `simulated` + 完整 simulation）。等待重查仍是 `waiting`，自动执行仍是 `auto_executing/auto_executed`，归档仍靠原手动/批量归档流程。

  **安全适配前置**：不能把旧 `lib/server/pipeline.js` / `collect.js` 原样接进新编排。现有 `autoExecuteApprove` 在账号不同时仍会直接调用 `sessions/jl.js inject`，`collect.js` 也会按缓存直接注入并自行导航详情；`pipeline.processOne` 未导出且不接受已锁定的 `detailTargetId`。完整串联必须抽出或新增 targetId-aware 适配层，复用旧系统采集、推理、状态写回和页面展示语义，但始终使用步骤 12 打开的目标详情 tab，禁止进入旧直接注入路径。ERP tab 不按“多 tab 风险”处理：有 ERP tab 时选择其中一个并锁定该 `erpTargetId` 复用；没有 ERP tab 时创建 `https://viperp.superboss.cc` 后锁定；不因多个 ERP tab 自动失败。2026-06-25 代码已落地并通过全量测试。原本采集动作若未改动，不重复做完整采集验证，只验证新 A1 wrapper 的 target 绑定是否正确。

  **当前页找不到目标工单时的定位恢复分支**：
  - 若 `total <= 10`、确认只有第 1 页、页码 1 激活且下一页禁用，可判定该工单已从“待商家处理”列表消失。
  - 若存在多页，必须真实点击第 1 页并确认页 1 已激活且列表已刷新，再从第 1 页逐页查到末页；仍找不到才判定消失。
  - 翻页失败、列表未加载、页码未确认或达到安全上限时，只能报错停止/保留待处理，**不得**判定消失。
  - 该逻辑属于逐单定位的恢复分支，不拆成独立分页查找模块；步骤 10 的真实翻页能力继续复用，但必须修复稳定读取。
  - “从待处理列表消失”只表示这张工单当前无需继续处理，不等价于断言客户取消，也不自动写成“已取消/已终态”。落地时写入原待确认列表，等待人工复核和手动归档。

  **页面与账号收尾**：原待确认/已自动执行/等待重查三类不变；`待确认` / `等待重查` 已增加店铺筛选（全部/店铺名），不改变分类也不改变按时效排序。2026-06-27 用户追加要求已完成：筛选后的店铺视角会同时约束批量操作作用域，避免“页面只看单店铺但后端仍全量批量重来/执行”；计划已在 `docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md` 原地归档，交接见 `docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`。单账号固定清单处理完后等待 5 秒，切首页读取平台提醒；随后兜底关闭当前账号除售后列表主 tab 外的鲸灵 tab，不动 ERP、专属售后系统或非鲸灵 tab，并复核只剩一个当前账号售后列表 tab。

  **当前门禁**：完整确认口径、已编码草案和未闭合范围统一记录在 `docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`。2026-06-26 已验证单工单真实采集和模拟写回；2026-06-26/27 已验证账号 14 关闭自动执行的最小整账号固定清单批次；2026-06-27 后端 `op-queue/API` 入口已接入、审查并加固，前端单账号 no-auto 入队按钮代码已接入，live 三标签店铺筛选与批量 scope 加固已完成，全量测试 228/228 通过。下一步只能在用户明确授权后重启加载并做 UI smoke test；自动执行真实工单前，必须另行确认用户授权、journal 恢复和失败闭环。自动执行锁永久残留、target 枚举异常遗留 tab 两项留到最后收尾风险把控时单独讨论。步骤 10 的翻页、步骤 12/13 的目标工单打开与新 tab 定位是既有能力，后续不得重复实现。

---

## Claude Code 优化项目（2026-05-03 完成 Phase 0+1）

> 详见 workspace plan: `.claude/plans/shimmering-skipping-dolphin.md`

### Phase 0：语义对齐层 ✅

- [x] **P0-1** aftersales-automation/SKILL.md（6区块：DO FIRST/ENTRY MAP/CORE FLOWS/NON-STANDARD PATTERNS/FAILURE PATTERNS/PATHS）
- [x] **P0-1** product-mapping/SKILL.md（同上结构）
- [x] **P0-2** 20 个核心 lib 文件补齐 WHAT/WHERE/WHY/ENTRY 文件头
- [x] **P0-3** 防过时机制：PATHS 读时验证 + CLAUDE.md 同步铁律 + pre-commit hook

### Phase 1：CI + 流程测试 + 三刀防失效 ✅

- [x] **P1-0** 3个CLAUDE.md 加入强制入口规则（Session第一步读SKILL.md）
- [x] **P1-1** CORE FLOWS 加 function anchor，smart_search 可校验
- [x] **P1-2** test/fixtures/decision-regression.json（20条 frozen 推理场景）
- [x] **P1-3** test/flow-test.js（纯逻辑回归测试，20/20通过，7ms）
- [x] **P1-4** .github/workflows/test.yml（CI 自动跑 flow-test + pm L1）

### Phase 2（按需）：Worktree 强制规则

- [x] workspace CLAUDE.md 加 worktree 强制触发条件（≥3文件/改流程结构/涉及shared）
