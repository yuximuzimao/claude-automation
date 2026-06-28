# A1 固定清单逐单处理：用户确认计划

> 状态：**业务口径已于 2026-06-22 用户确认；2026-06-26 已完成账号 14 茗瑞单工单真实页面采集、推理和模拟写回验证；2026-06-26/27 已完成账号 14 茗瑞-KGOS 关闭自动执行的最小整账号固定清单批次验证；2026-06-27 后端 op-queue/API 入口已接入并经审查加固，前端单账号 no-auto 入队按钮代码已接入并通过测试；auto-execution journal recovery 已完成设计但未实现。自动执行真实工单仍未交付。禁止重启加载、禁止真实 approve/reject，直到用户再次授权。**

## 本轮目的

A1 不是重做一套新的售后系统。目标是把“单账号固定清单逐单处理 + 详情 tab 隔离”接入原售后系统已经验证过的数据流和页面流转：`queue.json`、`simulations.jsonl`、原三标签页、原归档逻辑、原反馈逻辑继续作为事实来源。

后续 Agent 不得把 `scripts/jl-steps/14-process-single-account-fixed-batch.js` 做成独立闭环系统；它必须成为原系统扫描/采集/推理/执行顺序的安全编排层。

## 已编码草案

- `scripts/jl-steps/10-read-urgent-after-sale-list.js`：读取 48 小时清单、分页状态和页面“共 N 条”。
- `scripts/jl-steps/12-click-work-order-action.js`：精确点击目标工单并识别新增 tab。
- `scripts/jl-steps/14-process-single-account-fixed-batch.js`：冻结首次清单，逐单定位、采集、推理、自动执行门禁、关闭详情 tab。
- `lib/jl/target-aware-collector.js`：显式绑定 `detailTargetId` 和 ERP target 的采集草案。
- `lib/server/auto-execution-journal.js`：自动执行 intent / completed 防重复日志草案；恢复策略设计见 `docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`。

2026-06-26 已在用户授权下运行真实浏览器完成单工单采集验证；2026-06-26/27 已完成账号 14 关闭自动执行的最小整账号固定清单批次验证；2026-06-27 已接入并加固后端 `op-queue/API` 入口，且已接入前端单账号 no-auto 入队按钮代码。2026-06-27 已完成 auto-execution journal recovery 设计，明确人工归档必须同步更新 journal、queue、simulation/audit 和执行门禁。验证期间没有重启 server、没有真实 approve/reject。

## 用户已确认的业务口径（2026-06-22）

- [x] 首次排序后读取到的全部 `<=48h` 工单就是本轮不可变清单。后续新增、消失或排序变化，不改变本轮处理范围和顺序。
- [x] 表面流程为：列表定位 → 新详情 tab → 采集 → 推理 → 判断结果 → 仅现有自动执行范围可提交 → 写回原售后系统 → 关闭详情 tab → 下一单。
- [x] “写回原售后系统”是硬要求：每张工单都必须使用原系统数据结构记录采集结果、推理结果、判断结果、执行结果、错误信息，并显示在原售后系统页面。不得只在步骤 14 内部返回 `items`。
- [x] 不新增正式业务分类，不改变原页面三类：待确认、已自动执行、等待重查。`manual_review` 只能作为草案临时词，不得落地为正式状态。
- [x] 非自动执行工单和自动执行工单都要保留完整 `collectedData` + `decision`。差异只在 queue status：非自动执行进入原“待确认”，自动执行进入原“已自动执行”，等待重查进入原“等待重查”。
- [x] 当前页找不到目标工单时，必须回到第一页逐页查看。只有完整查完仍找不到，才可判定“已不在待商家处理列表”。
- [x] 单页判定必须同时满足：`total <= 10`、只有页码 1、页码 1 激活、下一页禁用。严格优先于错漏。
- [x] “已不在待商家处理列表”不等于客户取消、不等于已退款、不等于终态。它仍归入原“待确认”标签页，等待人工复核和手动归档。
- [x] 若待确认或等待重查列表中存在本次未处理旧工单，下一次扫描同账号时扫不到，应写入“已不在列表中”的人工复核结果，放到待确认标签页，不自动归档。
- [x] 本轮进度需要持久化，但展示仍按原售后系统逻辑。允许在每个标签页增加店铺筛选项：全部、店铺 1、店铺 2……筛选不改变状态分类、不改变按时效排序。2026-06-27 用户追加要求已完成：`待确认` / `等待重查` 店铺筛选已接入，筛选后的店铺视角也会成为批量操作作用域；前端发送显式 `{statusScope, accountNum?}`，后端校验并按 scope 选择候选，避免“页面只看单店铺但后端仍全量批量重来/执行”。计划已原地归档：`docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md`；交接见 `docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`。
- [x] 单账号固定清单全部工单确认处理完成后，等待 5 秒，再切换首页读取提醒。
- [x] 每单处理后正常只关闭该工单详情 tab，并验证关闭成功。账号收尾时做兜底清理：关闭所有“当前账号鲸灵后台、且不是售后列表主 tab”的 tab；不得关闭 ERP、专属售后系统、非鲸灵 tab 或用户手动打开的其他域 tab。清理后复核仅剩一个当前账号鲸灵 tab，且它是售后工单列表页、店铺名匹配当前账号。

## 必须按原系统串联的实现要求

1. 固定清单里的每张工单必须有原系统 queue item。已有未完成 queue item 时更新 `urgency/deadlineAt/accountNum/accountNote/type`，不存在时新增 `mode:'live'`, `source:'scan'` 或 `source:'fixed_batch'`。
2. 采集完成后必须 append 或 update 原系统 simulation：至少包含 `id/workOrderNum/queueItemId/accountNote/mode:'live'/source:'fixed_batch'/collectedData/decision/createdAt`。
3. 推理结果进入原状态流转：
   - `decision.waitingRescan === true` → queue status `waiting`。
   - 可人工确认的 approve/reject/escalate → queue status `simulated`，显示在待确认。
   - 自动执行中 → queue status `auto_executing`。
   - 自动执行成功 → queue status `auto_executed`，保留 `autoExecutedAt/executedAt`。
   - 自动执行失败 → queue status `simulated`，保留 `autoExecuteError`，人工处理。
   - 列表消失/找不到 → 生成人工复核 decision，queue status `simulated`，显示在待确认。
4. 不得直接把旧 `collect.js` / `pipeline.js` 原样接进新编排导致重新注入、重新导航或跨账号错 tab；但必须复用旧系统的数据模型、推理函数、自动执行条件、页面渲染和归档语义。
5. `target-aware-collector` 只解决“在已锁定详情 tab 上采集”的安全入口问题，不得替代原系统的数据持久化和页面状态流转。
6. 原页面三标签页不主动改版。只允许增加店铺筛选和由筛选派生的批量操作作用域；筛选不得改变状态分类、推理逻辑、归档逻辑或按时效排序。

## 当前批次质量问题

此前质量审查结论为：**当前不可交付**。2026-06-24 已完成以下 3 项代码修正和纯单测覆盖，并在复审中补齐 `fixed_batch` 终态 `skip` 的原系统状态语义。2026-06-26 已完成单工单真机采集验证；2026-06-26/27 已完成账号 14 关闭自动执行的最小整账号固定清单批次验证；2026-06-27 已完成后端 `op-queue/API` 入口、GPT 审查加固、前端单账号 no-auto 入队按钮代码，以及 live 三标签店铺筛选 + 批量 scope 加固。因此下一步不再是重复最小批次、后端入口设计、前端按钮代码或店铺筛选实现，而是等待用户明确授权后重启加载并做 UI smoke test；继续禁止自动执行真实工单。

1. [x] **初始清单翻页可能漏单（阻断）**：步骤 10 翻页不再只确认页码变化，已等待 loading 消失、列表指纹变化且连续读取稳定，防止 Element UI 页码先变但卡片未刷新的竞态。
2. [x] **倒计时解析失败会漏单（阻断）**：有工单号但 `totalHours === null` 时停止冻结清单并报错，不再静默跳过。
3. [x] **当前账号鲸灵 tab 清理必须更强校验**：关闭详情 tab 前验证域名、当前店铺名、非售后列表主 tab；账号收尾只关闭当前账号鲸灵非列表 tab，并复核售后列表主 tab 仍匹配当前账号。ERP、非鲸灵 tab、其他店铺鲸灵 tab 不会被关闭。

## 收尾风险把控阶段再处理的问题

以下风险仍不得扩大自动执行范围或接入真机。2026-06-27 已先完成第 4 项设计，但未实现代码：

4. **自动执行锁 / intent 可能永久残留**：recovery 设计已完成，见 `docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`。核心要求：人工归档必须同步更新 journal、queue、simulation/audit 和执行门禁，不能只把 journal 标成 resolved；`manually_resolved` 是审计收口，不是自动重试放行。后续仍需实现状态机、CLI/API 恢复入口和测试矩阵。
5. **点击后 target 枚举异常可能遗留 tab**：新 tab 已打开但 `getTargets()` 报错时，当前清理路径可能拿不到 tab ID；该项仍留到后续单独设计。

当前实现可以保留现有保守失败行为，但不得因为上述风险尚未实现而扩大自动执行范围或接入真机。

## 当前验证证据

- 2026-06-26 用户指定账号 14 茗瑞、工单 `100001782462690101360`，已完成真实页面单工单链路：固定执行排序下拉命中、读取 48 小时列表、定位目标工单、打开详情 tab、target-aware 采集、推理、模拟写回。写回 queue 状态为 `simulated`，decision action 为 `escalate`，原因是主品已退回但赠品在途未拦截成功需人工确认。用户随后手动删除页面中的 active 推理采集信息，历史 simulation 仍保留在 `data/simulations.jsonl`。
- 2026-06-26/27 账号 14 茗瑞-KGOS 关闭自动执行的最小整账号固定清单批次已完成：冻结清单 4 张；4 张均完成列表定位、打开详情 tab、采集、推理、写回 queue/simulation、关闭详情 tab；queue writeback 均为 `status:"simulated"`、`source:"fixed_batch"`；无 `executedAt` 或 `autoExecutedAt`；最终浏览器状态只剩 1 个鲸灵售后列表主 tab。
- 本轮拆分前测试基线：`npm test` 204/204 通过。覆盖点包括排序下拉 3 个可能文案、工单类型归一化，以及仅退款类型不再因 `subBizType=323` 误走商品明细核对。
- 2026-06-24 本轮复审修正后：`npm test` 193/193 通过；新增覆盖关闭详情 tab 前校验、拒绝关闭非鲸灵/列表主 tab/非当前账号 tab、账号收尾只清当前账号鲸灵额外 tab，以及 `fixed_batch` 来源终态 `skip` 进入原“已自动执行”列表。
- 2026-06-27 live 三标签店铺筛选 + 批量 scope 加固已完成：`待确认` / `等待重查` 均有 `全部` + 店铺筛选；前端批量操作发送显式 `{statusScope, accountNum?}`；后端校验 `accountNum/statusScope` 并按页面 deadline/urgency 顺序选择候选；`等待重查` 不暴露批量执行。全量 `npm test` 228/228 通过。
- 2026-06-27 auto-execution journal recovery 设计已完成：`docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`。该设计明确区分页动作不确定和本地写回失败；禁止盲重试 approve/reject；人工归档必须同步关闭 journal、queue、simulation/audit 和执行门禁。
- 测试通过只证明现有用例通过；账号 14 最小整账号批次只证明 no-auto 固定清单串行链路可跑通；后端队列入口、前端单账号 no-auto 按钮代码、live 店铺筛选代码已交付并加固，journal recovery 只是设计完成但尚未实现；这些都不代表已重启加载或自动执行真实工单已可运行。

## 与原计划差异

- 原计划截至 2026-06-25 只要求做 1 个账号 + 1 个工单的最小浏览器回归：打开账号、准备列表、定位工单、点击处理并锁定新详情 tab、关闭详情 tab、复核列表 tab；明确不采集、不同意、不拒绝。
- 实际执行时用户在 2026-06-26 追加授权完整采集，并允许写回“待确认”或“等待重查”。因此本轮比原计划多验证了一层：target-aware 采集、推理和原系统模拟写回。
- 2026-06-26/27 又继续验证了账号 14 关闭自动执行的 4 张固定清单串行批处理，范围进一步推进到最小整账号批次。
- 这个差异是正向推进，但范围不能外推：正式 UI 按钮、平台提醒收尾策略和自动执行真实工单仍未交付。

## 恢复开发的门禁

1. 已完成：按本文更新设计文档和 todo，明确 A1 只是原系统的安全编排层。
2. 已完成到单工单层面：原系统 queue/simulation 写回可行，非自动执行结论可进入原“待确认”语义。
3. 已完成到最小整账号批次层面：真实页面排序、列表冻结、逐单定位、新详情 tab 锁定、采集、推理、写回、关闭详情 tab、回到列表继续下一单、账号收尾已验证。
4. 已完成 live 三标签店铺筛选与批量 scope 加固：筛选不改变分类/排序，批量执行和批量重来不会作用隐藏店铺，等待重查只允许批量重来。
5. 已完成前端按钮加载/冒烟计划：`docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md`。计划确认现有按钮只做安全加载和只读冒烟，不重复实现；smoke 不得真实点击按钮或发送 fixed-batch POST。
6. 下一步：等待用户明确授权后重启加载并做只读 UI smoke test；按钮只调用后端 `POST /api/accounts/:num/a1-fixed-batch`，不传可篡改参数，不批量，不绕过状态/session 门禁。
7. 再下一步：自动执行真实工单必须另行处理 journal 恢复和人工审计路径。
8. 真机和正式入口仍需用户单独授权；不得从文档确认推导出更大范围授权。
