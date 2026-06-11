# 售后系统 3457 launchd 双托管问题交接

## 背景

用户要求将售后系统 launchd 托管状态问题交给 Claude Code 处理。业务逻辑修复已经由 Codex 完成并提交推送：

- commit: `f5c42fa fix(aftersales): flag wrong-item reason as merchant fault`
- 分支: `data-model-restructure`
- 影响: `卖家发错货` 已加入 `MERCHANT_FAULT_REASONS`，当前代码纯推理会将工单 `100001780880893428074` 判为 `escalate`，reason 包含商责提示。

本交接只处理 3457 服务托管状态，不要求重新修改退款判断逻辑。

## 已确认事实

### 当前真正运行的托管项

`com.heizong.aftersale-server` 是当前真正生效的 launchd 服务：

- plist: `/Users/chat/Library/LaunchAgents/com.heizong.aftersale-server.plist`
- 状态: `state = running`
- 当前 PID: `85538`（交接时刻）
- 运行命令: `/Users/chat/.nvm/versions/node/v22.22.1/bin/node /Users/chat/claude/aftersales-automation/server.js`
- 端口: `3457`
- health: `http://127.0.0.1:3457/health` 正常返回
- `RunAtLoad = true`
- `KeepAlive.SuccessfulExit = true`

### 重复/冲突托管项

`com.jl.server` 也指向同一个售后系统：

- plist: `/Users/chat/Library/LaunchAgents/com.jl.server.plist`
- 运行命令: `/Users/chat/.nvm/versions/node/v22.22.1/bin/node server.js`
- working directory: `/Users/chat/claude/aftersales-automation`
- 同样写入 `server.log`

当两个服务同时存在时，`com.heizong.aftersale-server` 先成功启动并持有 `data/.server.lock`；`com.jl.server` 后续反复尝试启动，新进程读到已有 PID 后退出，于是日志持续刷：

```text
[server] 已有实例运行中 (PID xxxx)，退出
```

## 风险判断

不整理时：

- 业务层低风险：当前 3457 可用，脚本能跑。
- 运维层中风险：`server.log` 被重复启动失败刷屏，真实错误容易被淹没。
- 托管层中风险：两个 launch agent 同时声明管理同一个 `server.js`，后续重启、崩溃恢复、排障会混乱。

## 建议 Claude Code 处理方式

不要盲目重启。先做只读确认：

```bash
launchctl print gui/501/com.heizong.aftersale-server
launchctl print gui/501/com.jl.server
lsof -nP -iTCP:3457 -sTCP:LISTEN
curl --noproxy '*' -sS http://127.0.0.1:3457/health
curl --noproxy '*' -sS http://127.0.0.1:3457/api/op-queue
```

确认队列为空或没有不可中断任务后，再决定清理。

推荐保留：

- `com.heizong.aftersale-server`

推荐禁用/移除：

- `com.jl.server`

原因：`com.heizong.aftersale-server` 当前是唯一确认 `running` 且 PID 对应 3457 的托管项；`com.jl.server` 是重复旧项。

## 注意事项

- 不要同时 bootstrap 两个 plist。
- 不要删除 `server.log`。
- 不要在队列运行中 kill server。
- 如果需要停服务，先确认 `/api/op-queue` 中 `running === null` 且 `queued` 为空。
- 如果要删除/移动 plist，建议先备份或改 `.disabled` 后缀。

## 当前状态快照

交接前最后一次只读确认：

```text
com.heizong.aftersale-server: state = running, pid = 85538
3457 listener: node PID 85538
health: {"ok":true,...}
com.jl.server: 重复旧托管项，曾导致 launchd spawn scheduled + lock 冲突
```

