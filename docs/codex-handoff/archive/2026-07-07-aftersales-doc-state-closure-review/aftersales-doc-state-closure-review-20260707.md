# 售后自动化文档状态收口 — Codex 细节审查交接

日期：2026-07-07
项目：`aftersales-automation/`
请求方：用户
当前任务性质：**只审查，不直接改代码/文档**

## 一句话背景

用户的理解是正确的：售后系统之前经历了一个 no-auto / 只读 smoke / 测试验证阶段，后来代码继续推进并直接进入了实际运行状态；但 `README.md` / `SKILL.md` / `tasks/todo.md` / 若干 2026-06 计划文档没有被逐句收口，仍残留“未重启加载、no-auto、禁止真实 approve/reject、自动执行未交付”等旧状态。现在需要 Codex 复核这些判断是否准确，再决定是否执行文档修改。

## Codex 审查目标

请 Codex 做细节审查：

1. 复核下面列出的“旧文档状态”和“当前代码实际状态”是否一致。
2. 判断建议修改范围是否过大、是否漏掉关键文件、是否误删仍有价值的历史门禁。
3. 审查通过后，再由用户另行要求执行修改；本交接不要求立即改文件。
4. 不要访问真实鲸灵/ERP 页面，不要运行会触发业务操作的命令。只做静态代码/文档审查即可。

## 需要特别注意的口径

不要把两件事混在一起：

- “自动执行真实 approve/reject 是否已启用”：根据当前代码，已启用。Step14 默认会走 `shouldAutoExecute` + `executionJournal`，命中后调用 `approveTicket` / `rejectTicket`。
- “auto-execution recovery 是否有 CLI/API/UI 外部入口”：根据当前代码，仍没有。`auto-execution-recovery.js` 仍是本地人工收口服务，future CLI/API/UI。

旧文档的问题是把第二件事推导成第一件事未交付，导致状态误导。

---

# 一、当前真实代码状态证据

## 1. 前端按钮已经是正式“处理工单”按钮，不是 no-auto / 只读 smoke 按钮

证据文件：`aftersales-automation/public/app.js`

关键位置：`runA1FixedBatch()`，约 `public/app.js:2038-2049`。

当前前端确认文案明确说明：

```text
将采集当前48小时内工单，符合自动执行条件的工单会直接执行（同意或拒绝退款），其余写入待确认。
```

然后调用：

```js
api(`/accounts/${num}/a1-fixed-batch`, { method: 'POST' })
```

这说明：

- 前端已经不是“代码已接入但未重启加载”。
- 按钮已经不是 no-auto 口径。
- 用户点击后二次确认，再调用正式 fixed-batch 入口。

## 2. 按钮显示条件已经上线

证据文件：`aftersales-automation/public/account-relogin-state.js`

关键位置：约 `public/account-relogin-state.js:27-32`。

```js
function shouldShowA1FixedBatchButton(account) {
  return !!account && account.hasFile === true && account.status === 'ok';
}

function renderA1FixedBatchButton(num) {
  return `<button class="btn-ghost btn-sm btn-a1-fixed-batch" onclick="runA1FixedBatch(${num}, this)">处理工单</button>`;
}
```

这说明按钮已按账号 session / status 门禁显示，不是“未加载 UI”。

## 3. 后端 API 已注册正式入口

证据文件：`aftersales-automation/lib/server/routes.js`

关键位置：约 `routes.js:807-812`。

```js
router.post('/accounts/:num/a1-fixed-batch', createA1FixedBatchRouteHandler({
  readAccounts: () => JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8')),
  readAccountStatus: () => JSON.parse(fs.readFileSync(ACCOUNT_STATUS_FILE, 'utf8')),
  validateSessionFile: ({ accountNum, file }) => validateSessionFile({ accountNum, file, sessionsDir: SESSIONS_DIR }),
  opQueue,
}));
```

说明 `POST /api/accounts/:num/a1-fixed-batch` 已是 Express 路由。

## 4. 后端入口只固定“单账号 + 48h”，不再强制 no-auto

证据文件：`aftersales-automation/lib/server/a1-fixed-batch-entry.js`

关键位置：约 `a1-fixed-batch-entry.js:14-25`。

```js
function buildA1FixedBatchOp({ accountNum, accountNote }) {
  const num = parseAccountNum(accountNum);
  const note = String(accountNote || `账号${num}`).trim() || `账号${num}`;
  return {
    type: 'a1-fixed-batch',
    label: `处理工单 账号${num}「${note}」`,
    params: {
      accountNum: num,
      accountNote: note,
      thresholdHours: 48,
    },
  };
}
```

这里没有 `disableAutoExecute:true`。

审查点：旧文档多处写“默认关闭自动执行 / 强制 disableAutoExecute:true / no-auto defaults”，这些已经和当前代码不一致。

## 5. 前端传入的篡改参数会被忽略，但这不等于强制 no-auto

证据文件：`aftersales-automation/test/server/a1-fixed-batch-entry.test.js`

关键位置：约 `test/server/a1-fixed-batch-entry.test.js:52-67`。

测试里请求体传了：

```js
body: { disableAutoExecute: false, thresholdHours: 1, accounts: ['1', '14'] }
```

最终断言入队参数仍只有：

```js
params: {
  accountNum: '14',
  accountNote: '茗瑞-KGOS',
  thresholdHours: 48,
}
```

这证明：

- 前端不能篡改账号数组。
- 前端不能篡改 48h 范围。
- 前端不能通过请求体控制 `disableAutoExecute`。
- 但也证明当前入口没有默认 `disableAutoExecute:true`。

## 6. op-queue 已接入 `a1-fixed-batch`，并调用 Step14

证据文件：`aftersales-automation/lib/server/op-queue.js`

关键位置 1：约 `op-queue.js:256-267`。

```js
case 'a1-fixed-batch': return execA1FixedBatch(op);
```

关键位置 2：约 `op-queue.js:373-389`。

```js
async function execA1FixedBatch(op) {
  assertNotAborted(op);
  const { processSingleAccountFixedBatch } = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const { accountNum, accountNote } = op.params;
  const note = accountNote || `账号${accountNum}`;
  return processSingleAccountFixedBatch(String(accountNum), {
    thresholdHours: 48,
    abortSignal: op._abortSignal,
    onTicketProgress: (item) => {
      sse.broadcast('ticket-progress', {
        accountNum: String(accountNum),
        note,
        workOrderNum: item.workOrderNum,
        status: item.status,
      });
    },
  });
}
```

这里同样没有传 `disableAutoExecute:true`。

审查点：旧文档“op-queue 层也强制 48h/no-auto”应改为“op-queue 层强制 48h，是否自动执行由 Step14 的 shouldAutoExecute + executionJournal 决定”。

## 7. Step14 默认会走自动执行判断，命中后真实执行

证据文件：`aftersales-automation/scripts/jl-steps/14-process-single-account-fixed-batch.js`

关键位置：约 `14-process-single-account-fixed-batch.js:380-420`。

逻辑概要：

```js
const collectedData = await dependencies.collectDetail(context);
const decision = await dependencies.inferDecision(collectedData, queueItem);

if (context && context.disableAutoExecute === true) {
  return { status: 'simulated', ... };
}

const auto = await dependencies.shouldAutoExecute(decision, collectedData, context.queueItem);
if (!auto) return { status: 'simulated', collectedData, decision };

const gate = await dependencies.assertAutoExecutionAllowed(...);
if (!gate.allowed) return { status: 'simulated', autoBlockedReason: ... };

await dependencies.reserveAutoExecution(...);
await dependencies.markPageActionStarted(...);
const execution = await dependencies.executeDecision(...);
await dependencies.markPageActionSucceeded(...);
await dependencies.markAutoExecuted(...);
return { status: 'auto_executed', collectedData, decision, execution };
```

结论：

- `disableAutoExecute === true` 只是显式调试/no-auto 选项。
- 默认路径会进入 `shouldAutoExecute`。
- 命中且通过 journal gate 后会真实执行。

## 8. Step14 的 `executeDecision` 已装配真实 approve/reject

证据文件：`aftersales-automation/scripts/jl-steps/14-process-single-account-fixed-batch.js`

关键位置：约 `14-process-single-account-fixed-batch.js:633-645`。

```js
executeDecision: async ({ detailTargetId, ticket, decision }) => {
  if (decision && decision.action === 'approve') {
    return approveTicket(detailTargetId, ticket.workOrderNum);
  }
  if (decision && decision.action === 'reject') {
    return rejectTicket(
      detailTargetId, ticket.workOrderNum,
      decision.rejectReason || decision.reason,
      decision.rejectDetail || decision.rejectReason || decision.reason,
      decision.imageUrl || null
    );
  }
  throw new Error(`不支持自动执行动作: ${decision && decision.action}`);
}
```

这直接推翻旧状态：“自动执行真实工单仍未交付 / 当前不得启用真实自动执行”。

## 9. Step14 写回原系统 queue/simulation，不是独立新系统

证据文件：`aftersales-automation/scripts/jl-steps/14-process-single-account-fixed-batch.js`

关键位置：约 `14-process-single-account-fixed-batch.js:655-661`。

```js
const sim = buildSimulationPayload({ account, queueItem, ticket, processed });
const queueStatus = statusForProcessed(processed, queueItem);
db.appendSimulation(sim);
db.updateQueueItem(queueItem.id, { status: queueStatus });
return { ...sim, queueStatus };
```

结论：旧计划里的“必须接回原 queue/simulation/三标签页”已经实现，应作为当前生产约束，而不是未完成前置条件。

## 10. 定时扫描已经恢复，部分文档“定时扫描停用 / 纯手动模式”过期

证据文件 1：`aftersales-automation/server.js`

关键位置：约 `server.js:103-112`。

```js
function runAutoScan() {
  if (skipNextScan) { ... }
  console.log('[auto-scan] 开始定时扫描');
  opQueue.enqueue('scan', '定时扫描工单', { accounts: [] });
}
```

证据文件 2：`aftersales-automation/server.js`

关键位置：约 `server.js:190-191`。

```js
// 恢复定时扫描（2026-06-30）：runAutoScan 走 execScan 新路径，遵守 scanEnabled 开关。
scheduleNextScan();
```

证据文件 3：`aftersales-automation/lib/constants.js`

关键位置：约 `constants.js:44`。

```js
const SCAN_HOURS = [0, 8, 12, 16, 20];
```

结论：

- README 第 3 行“定时扫描已恢复（每天 5 次）”是正确的。
- `aftersales-automation/CLAUDE.md` 第 55 行“定时扫描/ERP心跳已停用”过期。
- `aftersales-automation/SKILL.md` 第 21 行“定时扫描/ERP心跳/启动自动入队已停用”至少其中“定时扫描已停用”过期。

## 11. auto-execution recovery 仍然没有 CLI/API/UI 外部入口

证据文件：`aftersales-automation/lib/server/auto-execution-recovery.js`

关键位置：文件头约 `auto-execution-recovery.js:1-7`。

```js
/**
 * WHAT: auto-execution journal 的人工恢复收口服务
 * WHERE: 未来 CLI/API 恢复入口调用；当前只做纯本地状态修复，不碰 JL/ERP 页面
 * WHY: 人工归档必须同步关闭 journal + queue + simulation/audit，避免只关 journal 留下危险状态
 * ENTRY: future cli.js auto-journal resolve / routes.js recovery endpoint
 */
```

另查：`routes.js`、`cli.js`、`public/` 没有 recovery 外部入口。

结论：旧文档“recovery 没有 CLI/API/UI”仍正确；但不能据此说“真实自动执行未启用”。

---

# 二、建议修改文件清单与逐项改动

## A. `aftersales-automation/README.md`

### A1. 第 45-53 行 “当前目标链路”

现状问题：仍写 no-auto、未重启加载、recovery Phase 1 未开放等测试阶段口径。

建议改为当前生产链路：

```text
安全打开账号 → 固定导航售后列表 → 排序/读取 48h 固定清单
            → 逐单定位工单 → 打开详情 tab → target-aware 采集
            → inferDecision → shouldAutoExecute + executionJournal 门禁
            → 命中自动执行范围则 approve/reject，否则写入待确认/等待重查
            → 写回原 queue/simulation/三标签页 → 关闭详情 tab → 账号收尾
```

对应证据：

- `public/app.js:2038-2049` 前端正式按钮。
- `routes.js:807-812` 后端正式 API。
- `op-queue.js:373-389` op-queue 调 Step14。
- `14-process-single-account-fixed-batch.js:380-420` 自动执行判断与执行流程。

### A2. 第 55 行 legacy 链路说明

现状：

```text
旧 scan-all.js → queue → collect → infer → auto-execute 链路尚未完成安全迁移，不代表当前可用入口。
```

建议：

```text
legacy collect.js / scan-all.js / 旧 pipeline 文件仍保留，但不作为当前 A1/前端采集处理入口；当前扫描、重采、执行、固定清单处理统一走 op-queue 的 A1 安全链路。
```

对应证据：

- `routes.js:376` 注释：Scan 是 op-queue A1 固定清单入口，不走旧 scan-all.js。
- `SKILL.md:204` 已有 legacy 注意：旧文件仍保留，但当前入口走 op-queue A1 安全链路。

### A3. 第 57 行 Pipeline 描述

现状：

```text
旧 scan/auto-execute 入口停用，等待新 A1 接管
```

建议：

```text
Pipeline 保留 collect → infer → execute 的历史兼容能力；当前生产入口以 op-queue + A1 安全链路为准。
```

对应证据：

- `op-queue.js:682-739` 重新采集/推理已走 Step14 的 target-aware + journal 链路。

### A4. 第 63 行 A1 固定清单编排

现状问题点：

- “默认关闭自动执行”错。
- “前端 no-auto 按钮”错。
- “未重启加载”错。
- “自动执行真实工单仍未交付”错。
- “recovery 无 CLI/API/UI”对，但应独立陈述。

建议改为：

```text
A1/A2 固定清单编排：当前生产入口为 POST /api/accounts/:num/a1-fixed-batch → op-queue → processSingleAccountFixedBatch。入口固定单账号 + 48h 清单；前端“处理工单”按钮只在账号 session ok 时显示，点击后二次确认。Step14 严格串行逐单处理，写回原 queue/simulation；命中 shouldAutoExecute 且通过 executionJournal 安全门时会真实 approve/reject，否则进入待确认/等待重查。
```

对应证据：

- `a1-fixed-batch-entry.js:14-25` 入队参数。
- `public/app.js:2038-2049` 前端正式按钮。
- `14-process-single-account-fixed-batch.js:633-645` approve/reject 装配。

### A5. 第 64 行 自动执行恢复账本

现状：

```text
当前只用于本地安全基础，不代表已开放自动 approve/reject、CLI、API 或 UI 恢复入口。
```

建议：

```text
自动执行恢复账本：executionJournal 已作为自动执行安全门使用，记录 auto_executing/auto_executed/failed/manually_resolved 和 phase，防重复执行并 fail-closed；auto-execution-recovery 仍是本地人工收口服务，尚无外部 CLI/API/UI recovery 入口，不碰 JL/ERP 页面。
```

对应证据：

- `14-process-single-account-fixed-batch.js:647-653` journal reserve/mark 方法装配。
- `auto-execution-recovery.js:1-7` recovery 本地服务定位。

### A6. 第 80-84 行文档表

建议把 2026-06 计划/交接文档说明改成“历史计划/历史交接，仅用于追溯设计依据；当前状态以 README/SKILL/tasks/todo 最新状态为准”。

---

## B. `aftersales-automation/SKILL.md`

这是最容易误导 agent 的文件，建议优先处理。

### B1. 第 21 行 `server.js` 描述

现状：

```text
定时扫描/ERP心跳/启动自动入队已停用（2026-06-16 停旧系统）
```

建议：

```text
Express 服务（port 3457），队列管理 + Web 面板 + 定时扫描调度。定时扫描已恢复，走 opQueue scan 新路径并遵守 scanEnabled；legacy scan-all 不作为当前前端/A1处理入口。
```

对应证据：

- `server.js:103-112`
- `server.js:190-191`
- `constants.js:44`

### B2. 第 54 行 Step14 描述

现状：

```text
A1 固定清单逐单处理草案 ... 后端入口和前端 no-auto 按钮代码已接入 ... 禁止自动执行真实工单
```

建议：

```text
A1/A2 固定清单逐单生产编排：processSingleAccountFixedBatch，固定 48h 清单，逐单打开详情 tab，target-aware 采集，inferDecision，shouldAutoExecute + executionJournal 安全门，命中后真实 approve/reject，否则写回待确认/等待重查。
```

对应证据：

- `14-process-single-account-fixed-batch.js:670-875` 完整链路。

### B3. 第 55 行 `target-aware-collector.js` 描述

现状：

```text
前端按钮代码已接入但未重启加载
```

建议：

```text
当前 A1/A2 生产采集入口使用它显式绑定 JL 详情 tab 和 ERP tab。
```

对应证据：

- `14-process-single-account-fixed-batch.js:613-619`
- `op-queue.js:709-715`

### B4. 第 56 行 `auto-execution-journal.js` 描述

现状：

```text
当前不得启用真实自动执行
```

建议：

```text
自动执行审计风险层：生产自动执行前置安全门，记录 reserve/page_action_started/page_action_succeeded/auto_executed，防重复执行并 fail-closed；不得作为自动重试助手。
```

对应证据：

- `14-process-single-account-fixed-batch.js:406-420`
- `14-process-single-account-fixed-batch.js:647-653`

### B5. 第 57 行 `auto-execution-recovery.js` 描述

现状基本正确，但建议更明确：

```text
人工恢复收口服务：当前仍是本地服务，没有 routes.js / cli.js / public UI 外部入口；只修本地状态，不碰 JL/ERP 页面。
```

对应证据：

- `auto-execution-recovery.js:1-7`

### B6. 第 58 行 A1 用户确认计划描述

现状把旧计划作为当前质量问题和恢复开发门禁。

建议：

```text
历史 A1 确认计划：只用于追溯固定清单口径和早期门禁；当前生产状态以本 SKILL、README 和 tasks/todo 最新状态为准。
```

### B7. 第 72 行 `a1-fixed-batch-entry.js` 描述

现状：

```text
默认 48h + disableAutoExecute:true
```

建议：

```text
只允许显式单账号入队，固定 48h，忽略前端传入的 thresholdHours / accounts / disableAutoExecute 等可篡改参数；是否自动执行由 Step14 的 shouldAutoExecute + executionJournal 决定。
```

对应证据：

- `a1-fixed-batch-entry.js:14-25`
- `test/server/a1-fixed-batch-entry.test.js:52-67`

### B8. 第 85 行标题

现状：

```text
当前 A1 重建流程
```

建议：

```text
当前 A2 安全编排 / A1 固定清单生产流程
```

### B9. 第 90 行 Step14 状态整段

应删除/替换这些旧语句：

- 前端单账号 no-auto 按钮代码已接入但未重启加载。
- 禁止自动执行真实工单。
- 禁止未经授权重启加载后运行。
- 恢复入口见旧计划/交接。

建议改为：

```text
步骤 14 是当前固定清单生产入口：首次读取 <=48h 清单作为不可变快照；逐单定位、打开详情 tab、采集、推理、自动执行判定、写回原 queue/simulation、关闭详情 tab。前端“处理工单”按钮已接入正式入口；命中 shouldAutoExecute 且通过 executionJournal 安全门时会真实 approve/reject，未命中则写回 simulated/waiting。恢复收口服务仍仅本地可调用，无外部 CLI/API/UI。
```

### B10. 第 99 行延迟重查

现状：

```text
旧“下次自动扫描重置”目前不存在；未来只能由新 A1 手动/计划扫描显式重置，禁止假设固定扫描周期。
```

问题：定时扫描已恢复，而且 `scan-finalize` 已有 waiting 节流重置。

建议：

```text
延迟重查：推理返回 waitingRescan:true 时工单进入 waiting；scan-finalize 会按 lastInferAt / collectDoneAt + RESCAN_INTERVAL_HOURS 节流重置为 pending，定时扫描已恢复但仍必须走 op-queue A1 安全路径。
```

对应证据：

- `op-queue.js:416-430` waiting reset 逻辑。
- `server.js:190-191` 定时扫描恢复。

---

## C. `aftersales-automation/CLAUDE.md`

### C1. 第 55 行“纯手动模式 / 定时扫描停用”

现状：

```text
停旧系统后（2026-06-16）启动只重置残留状态为 pending、不自动入队处理（纯手动模式）；是否处理由用户手动选择。定时扫描/ERP心跳已停用。
```

建议：

```text
server 启动时加载模块到内存，不重启新逻辑不生效。当前定时扫描已恢复，由 server.js scheduleNextScan → opQueue scan 触发，并遵守账号 scanEnabled；真实处理入口仍由用户点击“处理工单”或队列操作触发，所有浏览器操作必须经 op-queue 串行。
```

对应证据：

- `server.js:103-112`
- `server.js:190-191`
- `routes.js:741-765` 支持 `scanEnabled`

---

## D. `aftersales-automation/tasks/todo.md`

这个文件是最大误导源，建议把 `2026-06 A1 逐账号扫描闭环待办` 整段收口。

### D1. 第 1 行标题日期

现状：

```text
# 待处理问题台账（2026-06-19 更新）
```

建议：

```text
# 待处理问题台账（2026-07 状态收口）
```

### D2. 第 80 行当前交接入口大段

现状仍写：

```text
仍未重启加载、未放开真实自动执行。不要重启加载正式入口、不要真实点击 A1 按钮、不要真实 approve/reject。
```

建议改成：

```text
> 2026-07 状态：A1/A2 固定清单链路已进入当前生产版本。前端“处理工单”按钮、POST /api/accounts/:num/a1-fixed-batch、op-queue 串行、Step14 固定 48h 清单、target-aware 采集、shouldAutoExecute + executionJournal 自动执行门禁均已接入并运行。系统已连续运行数日，当前版本可视为完成。旧 2026-06 计划/交接文档只作为历史依据，不再作为当前禁止事项来源。
```

### D3. 第 86 行 `A1-single-account-fixed-batch-chain`

现状：

- 仍是 `[ ]`。
- 标题写 no-auto UI。
- 正文写强制 `disableAutoExecute:true`。
- 正文写“仍不得重启加载正式入口、不得真实 approve/reject”。

建议：

```text
- [x] A1/A2-single-account-fixed-batch-chain（当前生产入口已完成）
```

同时保留历史验证摘要，但删除/改写旧 no-auto 和禁止真实执行口径。建议补一句：

```text
后续代码已从 no-auto 验证阶段推进到生产入口：前端按钮调用 fixed-batch POST，后端固定单账号 + 48h，Step14 默认允许 shouldAutoExecute 命中后真实执行；disableAutoExecute 仅作为 CLI/测试/显式调试选项保留。
```

### D4. 第 103 行“当前门禁”

现状仍写：

```text
下一步只能在用户明确授权后重启加载并做只读 UI smoke test
自动执行真实工单前，必须另行实现 CLI/API/UI 恢复入口和端到端门禁验证
```

建议改为当前安全边界：

```text
当前仍保留的安全边界：鲸灵行为操作报错即停；op-queue 串行；固定 48h 范围；账号 status/session fail-closed；自动执行前必须通过 shouldAutoExecute、circuit breaker、executionJournal duplicate/unresolved gate；auto-execution-recovery 仍无外部 CLI/API/UI，只能作为本地人工收口服务。
```

---

## E. 历史计划/交接文档：只加顶部“状态覆盖说明”，不建议重写全文

这些文件有历史价值，不建议大删。只加顶部状态说明，避免后续 agent 把旧状态当当前状态。

### E1. `docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`

旧状态中写了：

- 自动执行真实工单仍未交付。
- 禁止重启加载。
- 禁止真实 approve/reject。

建议顶部加：

```text
> 2026-07 状态覆盖：本文件是历史确认计划。其“未重启加载 / 未交付 / 禁止真实 approve/reject”状态已过期。当前生产状态以 README.md、SKILL.md、tasks/todo.md 和代码入口为准：前端“处理工单”按钮已接入正式 fixed-batch 入口，命中 shouldAutoExecute 且通过 executionJournal 门禁时会真实 approve/reject。
```

### E2. `docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md`

旧状态中写：

```text
自动执行真实工单仍未交付。
```

建议顶部加：

```text
> 2026-07 状态覆盖：本交接文档记录的是 2026-06-27 no-auto 验证阶段。当前版本已继续推进：fixed-batch 前端按钮、后端 API、op-queue 和 Step14 自动执行门禁均已运行；不再以本文“真实自动执行未交付”为当前状态。
```

### E3. `docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md`

旧状态围绕“按钮只读 smoke，不得 POST，不得真实点击”。

建议顶部加：

```text
> 2026-07 状态覆盖：本文件是前端按钮加载/只读冒烟阶段的历史计划。当前前端按钮已成为正式“处理工单”入口，点击后二次确认并调用 POST /api/accounts/:num/a1-fixed-batch；当前状态请看 README.md / SKILL.md。
```

### E4. `docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`

旧文档顶部写：

```text
Do not enable true automatic approve/reject from this document.
```

这句话本身不是错误，因为它说不要“从这个设计文档”启用自动执行。但现在容易被误读为当前仍不能自动执行。

建议顶部补：

```text
> 2026-07 说明：本文件只定义 recovery / journal 设计边界，不代表当前自动执行状态。当前自动执行已由 Step14 + shouldAutoExecute + executionJournal 生产链路启用；recovery 外部 CLI/API/UI 入口仍未开放。
```

### E5. `docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md`

旧状态中有 no-auto / 未开放阶段计划。

建议顶部加：

```text
> 2026-07 状态覆盖：本文件是 2026-06-27 并行任务计划，记录当时 no-auto / 未开放阶段。当前 fixed-batch 生产入口和自动执行已继续推进并运行；本文不再作为当前状态源。
```

---

## F. 测试文件：只改测试标题，不改测试逻辑

### F1. `test/server/a1-fixed-batch-entry.test.js`

当前测试标题约第 20 行：

```js
buildA1FixedBatchOp always defaults to no-auto fixed 48h live batch
```

问题：测试断言中没有 `disableAutoExecute:true`，标题误导。

建议改为：

```js
buildA1FixedBatchOp always builds single-account fixed 48h live batch
```

### F2. `test/server/a1-fixed-batch-op-queue.test.js`

当前测试标题约第 24 行：

```js
op-queue executes a1-fixed-batch through Step14 with no-auto defaults
```

问题：op-queue 当前只传 `thresholdHours:48`，没有传 no-auto。

建议改为：

```js
op-queue executes a1-fixed-batch through Step14 with fixed 48h defaults
```

---

# 三、不建议改的内容

## 1. 不建议改 `auto-execution-recovery.js`

当前文件头状态准确：

- 当前是本地人工恢复收口服务。
- future CLI/API 恢复入口。
- 不碰 JL/ERP 页面。

## 2. 不建议大规模改 `docs/INDEX.md`

`docs/INDEX.md` 主要是规则和历史坑位，不是当前版本状态页。除非 Codex 发现明确错误，否则本轮不应扩散。

## 3. 不建议提交 `data/auto-execution-journal.json`

它有大量 `auto_executed` 记录，可以作为运行痕迹旁证，但属于运行时数据，不作为文档收口的主要依据，也不应该提交。

---

# 四、建议 Codex 审查问题清单

请 Codex 按以下问题逐条回答：

1. 当前 `POST /api/accounts/:num/a1-fixed-batch` 是否确实不再强制 `disableAutoExecute:true`？
2. 当前 Step14 是否默认会调用 `shouldAutoExecute`，并在通过 executionJournal gate 后调用 `approveTicket` / `rejectTicket`？
3. “auto-execution recovery 无 CLI/API/UI”是否仍准确？
4. “自动执行真实工单仍未交付”是否已经过期？
5. “前端 no-auto 按钮代码已接入但未重启加载”是否已经过期？
6. “定时扫描已停用 / 纯手动模式”是否已经过期？
7. 建议改动文件是否过多？是否可以只改 README/SKILL/CLAUDE/tasks/todo + 历史文档顶部覆盖说明？
8. 两个测试标题中的 no-auto 是否应只改标题，不改断言？
9. 是否还存在其他文档残留类似“未交付 / 禁止真实执行 / 未重启加载”的当前状态误导？

---

# 五、建议最终修改范围

如果 Codex 审查通过，建议由执行 agent 修改以下文件：

```text
aftersales-automation/README.md
aftersales-automation/SKILL.md
aftersales-automation/CLAUDE.md
aftersales-automation/tasks/todo.md
aftersales-automation/docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md
aftersales-automation/docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md
aftersales-automation/docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md
aftersales-automation/docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md
aftersales-automation/docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md
aftersales-automation/test/server/a1-fixed-batch-entry.test.js
aftersales-automation/test/server/a1-fixed-batch-op-queue.test.js
```

核心文件是前 4 个；历史计划只加顶部状态覆盖；测试文件只改测试标题。

---

# 六、执行注意事项

- 本交接只做审查交接，不要求立即修改。
- 如果后续执行修改，建议先改核心 4 文件，再改历史计划顶部覆盖说明，最后改测试标题。
- 修改后至少跑与文档无关的轻量检查；如果只改文档和测试标题，可以跑对应 node test 文件确认没有语法/测试名问题。
- 不要运行会访问真实鲸灵/ERP 的脚本。
- 不要提交 `data/`、`*.log`、`.server.lock`。
