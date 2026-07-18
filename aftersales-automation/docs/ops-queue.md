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
| execScan | 每个账号迭代前 + 传入子函数 |
| execA1FixedBatch | 入口 + 传入子函数（每个工单迭代前检查） |
| execScanFinalize | 入口 → 清理拦截后 → 入队前 |
| execReturnInbound | 每个快递单号前 |
| execOpenAccount | 入口 |
| execReinfer | 入口 + 传入 execReprocessOne |

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
- `allClean: false` → 前端显示具体问题（队列未清空 / 子进程残留 / 运行中操作未清除）
