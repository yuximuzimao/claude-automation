# 队列紧急停止与恢复

> 适用场景：队列操作卡住、出错或需要立即中断。紧急停止后不会自动恢复被中断任务。

> 2026-07-02 实现。旧 `emergencyStop()` 只杀 `spawnAsync` 子进程，对 async executor 完全无效——紧急停止按钮实际是摆设。现已通过 AbortController + 检查点机制修复。

## 1. 如何停止

| 方式 | 操作 | 效果 |
|------|------|------|
| 全局紧急停止 | 前端面板点「🛑 紧急停止」 | 清空排队 + 中断运行中操作 |
| 单操作停止 | 队列下拉面板中运行中操作旁的「⏹」 | 只停该操作，保留排队 |
| API 停止 | `POST /api/emergency-stop` | 同上，返回验证结果 |
| API 单操作 | `DELETE /api/op-queue/:id` | 取消排队或停止运行中 |

## 2. 停止流程（内部机制）

```
emergencyStop()
  ├─ paused = true（阻断新操作调度）
  ├─ 清空所有 queued 操作（内存队列）
  ├─ abortController.abort()（中断运行中 async executor）
  ├─ killAllTrackedProcs()（SIGTERM → 等2s → SIGKILL 僵尸）
  ├─ writeStopEvent() → data/emergency-stop.json
  └─ verifyStopState() → 返回 {queueEmpty, runningCleared, aliveProcs, allClean}
```

## 3. 中断检查点

每个 executor 在关键步骤间调用 `assertNotAborted(op)`，检查 `op._abortSignal.aborted`。已中断时抛出 `AbortError`，被 `processNext()` 捕获标记为 `cancelled`（非 `error`）。

| Executor | 检查点 |
|----------|--------|
| execExecute | 打开账号后 → 列表排序后 → 打开详情后 |
| execReprocessOne | 打开账号后 → 列表排序后 → 定位工单后 → 打开详情后 |
| execOpenTicket | 打开账号后 → 列表排序后 → 定位工单后 |
| execScan | 10 秒预告和账号间隔均可立即中断；每个账号迭代前 + 传入子函数 |
| Step14 单工单采集 | 定位、打开详情、读工单、逐子订单 ERP 查询、物流、商品档案、推理之间均检查停止信号；停止后保留当前详情 tab 原样，不再为了收尾关闭页面，也不写入假的“处理失败”结果 |
| execA1FixedBatch | 入口 + 传入子函数（每个工单迭代前检查） |
| execScanFinalize | 入口 → 清理拦截后 → 入队前 |
| execReturnInbound | 每个快递单号前 |
| execOpenAccount | 入口 |
| execReinfer | 入口 + 传入 execReprocessOne |

平台写操作例外：如果“同意/拒绝”的页面动作已经发出，当前工单会先完成结果验证和 execution journal 记账，然后停止。这不是继续处理下一步业务，而是避免留下“平台可能已执行，本地却未记录”的不确定状态。

停止优先级高于普通读取、等待、导航、翻页、关闭 tab 和账号异常隔离：收到停止后不再发起新的浏览器动作，现场允许原样保留。鼠标 `mousePressed` 已发出时只补配对 `mouseReleased`；Cookie/storage 清理或单次账号注入已经启动时不在半途中强杀，完成该原子动作后立即停止后续步骤。

## 4. Stop 事件文件

**位置**：`data/emergency-stop.json`

```json
{
  "stoppedAt": "2026-07-02T08:49:27.576Z",
  "interrupted": { "id": "op-...", "type": "scan", "label": "...", "startedAt": "..." },
  "clearedCount": 5,
  "queueEmpty": true,
  "runningCleared": true
}
```

**生命周期**：
- 写入：`emergencyStop()` 调用时
- 读取：server 启动时输出警告；前端页面加载时检查并 Toast
- 查询：`GET /api/stop-event`
- 清除：`resume()` 调用时删除文件

## 5. 重启后行为

1. server 启动时调用 `readStopEvent()` → 发现文件 → `console.log` 警告（含被中断的操作和清除的排队数）
2. 启动残留状态清理：`collecting/collected/inferring` → `pending`（与 stop 无关，是崩溃恢复通用逻辑）
3. **紧急停止后不会自动恢复被中断任务**：用户自行决定是否重新处理；这不影响 server 的定时扫描调度

## 6. 验证停止结果

`POST /api/emergency-stop` 响应包含 `verify` 字段：

```json
{
  "ok": true,
  "paused": true,
  "verify": {
    "queueEmpty": true,
    "runningCleared": true,
    "aliveProcs": null,
    "paused": true,
    "allClean": true
  }
}
```

- `allClean: true` → 前端显示 "⏹️ 已停止：队列清空，进程已终止"
- `stopRequested: true` → 前端立即显示“已收到停止指令”，并短轮询直到当前步骤退出
- `allClean: false` 且未进入停止中 → 前端显示具体问题（队列未清空 / 子进程残留 / 运行中操作未清除）

## 7. 定时扫描状态窗

仅 `label=定时扫描工单` 的自动扫描在 `execScan` 真正开始浏览器操作前启动 macOS 浮动状态窗；人工发起的单笔处理、重新采集、执行操作和手动扫描不增加等待。

- 开始前固定倒计时 10 秒，期间不执行本轮扫描的任何 Chrome/CDP 操作，供用户暂存当前工作。
- 运行中显示当前店铺序号/总店铺数、剩余店铺数、当前工单序号/本店工单数、工单号和累计异常店铺数。
- 状态窗显示单店异常。扫描能否继续由队列和固定批次的安全判断决定，见[单工单浏览器异常](#81-单工单浏览器异常)。
- 整轮正常完成、带店铺异常完成、队列异常结束或被紧急停止时，状态窗显示对应终态约 5 秒后自动关闭。
- 状态窗仅观察 `op-queue` 的真实进度，不承担队列控制。实现位于 `lib/server/scan-hud.js` + `scripts/scan-status-hud.js`，通过 `/tmp/aftersales-scan-hud/` 下的临时 JSON 状态文件通信；状态窗退出后清理自身状态文件。

### 7.1 万物定时扫描

- 万物心选巡检每天 07:00、15:00 入统一 `op-queue`，与鲸灵/ERP 浏览器操作严格串行。
- 状态窗沿用 10 秒预告，再显示打开后台、单次登录、间隔 3 秒双读、关闭标签页等阶段。
- 每轮只操作本次创建的棒棒糖后台标签页；成功、异常或人工停止都在收尾时按精确 `targetId` 关闭并验证，不关闭用户手动打开的标签页。
- 待办非零时每轮只创建一条“万物待办”汇总提醒；全部为 0 时只更新顶部绿色状态。登录失败、风控或数字不稳定时更新红色异常状态并创建提醒。

业务提醒的发送入口与失败处理见 [工作区提醒说明](../../docs/reminders.md)；本节的扫描状态窗继续负责进度显示。

## 8. 提醒触发与汇总

| 提醒 | 当前触发和频次 |
|---|---|
| 快递拦截 | 本轮出现新的拦截待办标记时，整轮最多一条；具体业务规则见 [flow-5.3 Step 4c](flow-5.3.md#step-4c汇总拦截待办在途驿站未取件时) |
| 取消拦截 | 本轮发现工单已取消且存在拦截记录时，整轮最多一条 |
| 工单即将超时 | 存在尚未到期且进入 `REMIND_HOURS` 阈值的工单时，按最早截止时间生成一条汇总，不逐单创建 |
| 线下换货待人工 | 固定批次或单笔重采保存人工结论后创建，按 queue item 的成功时间持久去重；业务范围见 [flow-5.4 §线下换货](flow-5.4.md#线下换货)，字段见 [采集合约](collect-schema.md#线下换货提醒状态queue-item) |
| 单工单浏览器异常 | 固定批次确认可跳过该工单、保存待人工结果后单独提醒，按 queue item 持久去重。见 [§8.1](#81-单工单浏览器异常) 和[字段合约](collect-schema.md#固定批次单工单浏览器异常)。 |
| 店铺异常 | 本次扫描或打开后台产生新的 `expired/error` 状态或异常原因变化时提醒；同一异常持续存在不重复提醒 |
| 手动工单提醒 | `node cli.js remind` 按本次明确指定的工单创建 |

万物待办和扫描异常的触发见 §7.1；ERP 启动校验和认证熔断告警见 [ops-erp.md §2](ops-erp.md#2-erp-登录状态检测与恢复)。发送实现仍统一由 `lib/helpers.js` 的 `createReminder()` 提供。

### 8.1 单工单浏览器异常

固定批次只对明确可隔离的故障跳过当前工单，包括处理按钮滚动后仍越界、点击结束后无法确认详情页，以及售后列表或当前详情标签在读取或滚轮动作中的浏览器控制连接失败。已经打开的详情须完成现有关闭校验，再只读复核原列表标签仍属于同一店铺。每个账号批次开始时记录一次标签页集合，跳过前用它排除遗留或新增的未知标签。通过后，系统保存该工单的待人工结果，单独提醒，并按原清单处理同店下一张。

鼠标按下或释放中断、进入自动执行临界区、账号或标签身份不明、发现风控信号、收尾或校验失败、人工停止以及其他未知错误，沿用现有停止路径。跳过前复核判定主列表或账号身份不可信时，交给队列隔离现场并停止整轮扫描。工单跳过只在本轮继续处理下一张，原失败动作报错即停。提醒在工单写回之后发送，成功时间保存到 `browserSkipReminderAt`。发送失败会记录结果，后续自然再次命中时仍可提醒。

详情页识别发现风控信号时，共用打开工单步骤就地持久化熔断，固定批次直接停止当轮。队列在扫描、打开账号、查看工单、重采、执行或固定批次开始前读取同一状态。人工确认后运行 `node cli.js reset-circuit`，只写入本地复位记录，供运行中的服务在下一次操作前读取。

在 `server.log` 查 `jl_work_order_browser_skipped` 可看到逐单原因和提醒结果。固定批次结束、失败或被停止时，`jl_fixed_batch_browser_observation` 汇总 `attempted`、`browserFaults`、`skipped`、`attemptedAfterSkip` 和 `completedAfterSkip`。已记录批次的触发率用累计故障数除以累计尝试数。浏览器故障取证字段见[鲸灵与 CDP 操作指南](ops-jingling.md#浏览器异常取证)。
