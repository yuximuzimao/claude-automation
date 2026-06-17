# Aftersales 最小注入与百浩风控事件交接

From: Codex  
To: Claude Code  
Project: aftersales-automation  
Timestamp: 2026-06-15T15:30:05+0800  
Status: 待 Claude 复核和后续处理

## 用户当前要求

用户要求 Codex 停止继续处理服务，由 Claude 接手后续检查和处理。本交接记录本轮的前因后果、已改动内容、验证结果、已知风险和建议检查点。

用户明确约束：

- 不要再真实访问鲸灵平台做试验。
- 百浩账号 3 本次触发风控，需要标为重新登录。
- 账号 1 已解封且用户刷新页面确认登录状态正常，需要本地状态改为正常。
- 需要确认所有打开后台、定时扫描、处理工单前切账号、查看工单页面跳转都走新的最小注入逻辑。

## 事件背景

1. 早先问题：百浩扫描后工单消失。
   - 根因判断：`read-ticket: 已不在待处理列表` 被 `infer` 当作高置信终态，导致扫描刚发现但详情页暂时读不到的 live 工单被自动归档。
   - 目标：不确定状态保留在列表中复查，不直接消失。

2. 用户追加要求：扫描到的工单如果明确是已关闭、已退款等自动归档状态，不要悄无声息消失，要进入“已自动执行”。

3. 新风险事件：点击“打开店铺后台”时，百浩店铺导致浏览器卡住并显示平台登录页面，但店铺管理仍显示账号状态正常，随后 IP 被封。
   - 用户要求检查是否失败后有多次尝试。
   - 结论：原 `/accounts/:num/open` 是 fire-and-forget，直接后台启动 `jl.js <num>`，失败输出被吞，不会回写状态。没有内置 retry，但多个入口都可能独立触发注入。

4. 用户澄清：`ok` 状态超过 30 分钟不应强制重登。每天多次注入、每次登录要手机号验证，不能把账号正常状态按时间降级。
   - 已撤销“30 分钟 stale”思路。
   - 当前语义：`ok` 不因时间变旧自动异常；只有明确 `expired/error` 才阻断打开。

5. 用户提出成功经验：跨设备注入只搬认证态和账号身份，不搬设备/网络/监控指纹。
   - 保留 Cookie：`JSESSIONID`、`ssxmod_itna`、`ssxmod_itna2`、`_us`
   - 保留 localStorage：`__supplierId__`、`__subBizType__`、`currentSubBizType`、`supplierInfo`、`aifocus-cookie`
   - 丢弃：`_dx_*`、`_&MONITOR_*`、`acw_tc`、`cdn_sec_tc` 和其他设备 ID 类字段。
   - 原因：认证态可搬，设备指纹必须让本地浏览器自己生成，跨设备/网络搬运会触发风控。

## 已实施改动

### 1. 扫描工单不确定状态不再自动归档

涉及文件：

- `aftersales-automation/lib/infer.js`
- `aftersales-automation/lib/jl/read-ticket.js`
- `aftersales-automation/test/infer/scan-gone-from-list.test.js`

行为变化：

- live scan 工单遇到 `read-ticket: 已不在待处理列表` 时，不再输出 `skip/high`。
- 改为低置信人工/复查状态，原因口径为“详情页未确认，需复查”。
- 如果后续页面明确读到“已关闭/已退款/平台自动处理”等终态，仍允许自动归档逻辑。
- `read-ticket` 等待详情页确认时间加长，并在列表反查前等待列表渲染稳定，降低页面未加载导致误判的概率。

### 2. 明确终态的扫描工单进入“已自动执行”

涉及文件：

- `aftersales-automation/lib/server/pipeline.js`
- `aftersales-automation/lib/server/pipeline-status.js`
- `aftersales-automation/test/pipeline/terminal-skip-status.test.js`

行为变化：

- 扫描来源的明确终态 `skip` 不直接进入 `done`，而是进入 `auto_executed`，在“已自动执行”列表中可见。
- 非扫描来源终态 `skip` 保持原来的直接完成行为。

### 3. 打开店铺后台改为队列化单次注入

涉及文件：

- `aftersales-automation/lib/server/account-session-status.js`
- `aftersales-automation/lib/server/op-queue.js`
- `aftersales-automation/lib/server/routes.js`
- `aftersales-automation/public/app.js`
- `aftersales-automation/test/server/account-session-status.test.js`
- `aftersales-automation/test/server/relogin-session.test.js`

行为变化：

- `/api/accounts/:num/open` 不再直接后台 spawn `jl.js <num>`。
- 改为入队 `open-account`，由 `op-queue` 串行执行一次 `node sessions/jl.js inject <num>`。
- 成功后写 `current-session.json` 并更新账号状态为 `ok`。
- 失败后按错误内容写回 `expired/error`，前端收到失败 toast，并刷新账号列表。
- `ok` 状态不会因时间变旧被降级；`unknown` 允许尝试一次；`expired/error` 会拦截并提示重新登录或刷新状态。

### 4. 最小注入白名单

涉及文件：

- `aftersales-automation/lib/jl/session-filter.js`，新增且可被 git 跟踪。
- `aftersales-automation/test/jl/minimal-inject-filter.test.js`，新增。
- `sessions/jl.js`，本地运行入口已修改，但注意 `sessions/` 目录被 `.gitignore` 忽略。

当前 `sessions/jl.js` 引用：

```js
const { filterAuthCookies, filterIdentityLocalStorage } = require('../aftersales-automation/lib/jl/session-filter');
```

注入行为：

- Cookie 只注入 `JSESSIONID`、`ssxmod_itna`、`ssxmod_itna2`、`_us`。
- localStorage 只注入 `__supplierId__`、`__subBizType__`、`currentSubBizType`、`supplierInfo`、`aifocus-cookie`。
- localStorage 删除逻辑只删除这些账号身份 key，不再清空本地已有设备/风控字段。
- `_dx_*`、`_&MONITOR_*`、`acw_tc`、`cdn_sec_tc` 等字段不会从 session 文件注入。

重要风险：

- `sessions/jl.js` 在 ignored 目录中，`git status` 不会显示它。Claude 需要确认这类运行脚本的持久化策略，避免后续换机或恢复仓库时丢失最小注入改动。
- 核心白名单 helper 已放到 `aftersales-automation/lib/jl/session-filter.js`，是可追踪文件。

## 已确认的入口路径

这些服务内入口都调用同一个 `sessions/jl.js inject <账号>`，因此只要当前 `sessions/jl.js` 是新版本，就会走最小注入：

- 打开店铺后台：
  - `public/app.js` → `/api/accounts/:num/open`
  - `routes.js` → enqueue `open-account`
  - `op-queue.js execOpenAccount` → `node sessions/jl.js inject <num>`

- 定时扫描工单：
  - `server.js runAutoScan` → enqueue `scan-account`
  - `op-queue.js execScanAccount` → `node sessions/jl.js inject <num>`

- 处理工单前切账号：
  - `op-queue.js execExecute`
  - 若 `current-session.json` 不是目标账号，则执行 `node sessions/jl.js inject <num>`

- 页面“查看工单”按钮：
  - `public/app.js openTicket`
  - `/api/open-ticket`
  - `op-queue.js execOpenTicket` → `node sessions/jl.js inject <num>` → `cli.js open-ticket`

- 自动执行 approve：
  - `pipeline.js autoExecuteApprove`
  - 目标账号不同则执行 `node sessions/jl.js inject <num>`

另有旧脚本路径：

- `aftersales-automation/scan-all.js`
- `aftersales-automation/collect.js`

它们也调用 `node sessions/jl.js inject <num>`，但本轮重点是服务内入口。

## 11 个账号的最小注入核对结果

只核对字段名和数量，未输出任何 Cookie 值。

| 账号 | 备注 | Cookie 总数 | 注入 Cookie | 跳过 Cookie | localStorage 总数 | 注入 localStorage | 跳过 localStorage |
|---:|---|---:|---|---:|---:|---|---:|
| 1 | 汐澜-鲨鱼 | 15 | `JSESSIONID`, `_us`, `ssxmod_itna`, `ssxmod_itna2` | 10 | 26 | `aifocus-cookie`, `supplierInfo`, `currentSubBizType` | 23 |
| 2 | 展宏妍-悦希 | 16 | 同上 | 11 | 19 | 同上 | 16 |
| 3 | 百浩-RITEKOKO | 15 | 同上 | 10 | 20 | 同上 | 17 |
| 4 | 蓄力生长-KGOS | 15 | 同上 | 10 | 20 | 同上 | 17 |
| 5 | 共途-KGOS | 16 | 同上 | 11 | 19 | 同上 | 16 |
| 6 | 上海绰绰-悦希 | 15 | 同上 | 10 | 20 | 同上 | 17 |
| 7 | 厦门蒲颜-悦希 | 15 | 同上 | 10 | 19 | 同上 | 16 |
| 9 | 丰瑞宁-悦希 | 15 | 同上 | 10 | 19 | 同上 | 16 |
| 11 | 曼玲-悦希 | 15 | 同上 | 10 | 21 | 同上 | 18 |
| 12 | 顺链-肺肽 | 16 | 同上 | 11 | 19 | 同上 | 16 |
| 13 | 澜泽-KGOS | 15 | 同上 | 10 | 32 | `currentSubBizType`, `__subBizType__`, `__supplierId__`, `aifocus-cookie`, `supplierInfo` | 27 |

## 账号状态改动

文件：

- `aftersales-automation/data/account-status.json`

已按用户要求修改并读回确认：

```json
{
  "account1": {
    "status": "ok",
    "lastScan": "2026-06-15T07:23:46Z",
    "count": 0,
    "note": "汐澜-鲨鱼",
    "error": null
  },
  "account3": {
    "status": "expired",
    "lastScan": "2026-06-15T07:23:46Z",
    "count": 9,
    "note": "百浩-RITEKOKO",
    "error": "百浩账号本次触发平台风控，需重新登录后再使用"
  }
}
```

说明：

- 账号 1 用户已确认平台端解封、刷新页面读取状态正常，因此本地改为 `ok`。
- 账号 3 是百浩，本次风控来源账号，改为 `expired`，前端应显示重新登录。

## 服务状态

用户最后说“不用你重启了”，但在这条消息之前 Codex 已经完成了重启动作。请 Claude 如实复核。

实际执行过程：

- 旧服务 PID：`15153`，已运行约 2 天。
- Codex 对旧进程执行了 `kill -TERM 15153`，进程退出。
- 首次沙箱内 `nohup node server.js` 未成功。
- 随后用 escalated 方式启动：
  - 新 PID：`75902`
  - 命令：`node /Users/chat/claude/aftersales-automation/server.js`
  - 直连 health：`curl --noproxy '*' http://127.0.0.1:3457/health` 返回 `{"ok":true,...}`

注意：

- 普通 `curl http://localhost:3457/health` 会被 `ALL_PROXY=socks5://127.0.0.1:7897` 影响，可能得到 `Empty reply from server`。检查本地服务请用 `curl --noproxy '*' http://127.0.0.1:3457/health`。
- `server.js` 启动时会做 ERP 登录检查、定时扫描调度和 pending 工单入队。重启前 Codex 检查过 `queue.json`，当时 `live pending = 0`，仅有 `live:done = 1146`、`live:waiting = 1`。

## 验证已跑

本轮 Codex 已跑过：

- `node --test test/jl/minimal-inject-filter.test.js`：2/2 通过。
- `node --check /Users/chat/claude/aftersales-automation/lib/jl/session-filter.js`：通过。
- `node --check /Users/chat/claude/sessions/jl.js`：通过。
- `npm test`：67/67 通过。

后续服务重启后未再触发真实平台操作验证。

## 平台说“刷接口”的含义

结合当前代码，平台所谓“刷接口”不一定是业务接口被代码显式循环打爆，也可能是这些行为在平台风控侧表现为接口频率异常：

1. 多账号在同一个 Chrome/CDP 会话里频繁注入 Cookie/localStorage，然后访问同一 SCRM 域名。
2. 失败后页面跳登录页，但系统仍认为账号 `ok`，用户或自动流程再次打开/扫描/查看工单，形成多次独立注入和页面请求。
3. 旧全量注入搬运了 `_dx_*`、`_&MONITOR_*`、`acw_tc`、`cdn_sec_tc` 等设备/网络绑定字段，导致认证态、设备指纹、WAF 网关 token、IP 环境彼此不一致，平台可能把这类异常请求归类为接口刷量或风险请求。
4. 定时扫描会对 11 个账号逐个切换并读取列表；如果某个账号失效、被封或页面卡住，平台侧看到的可能是一段时间内来自同一 IP 的反复异常认证/跳转请求。

建议给用户的口径：

- “刷接口”是平台风控侧的归类，不一定等于我们主动写了高频接口循环。
- 这次更像是全量注入跨设备/网络字段 + 失败状态未回写 + 多入口可重复触发，共同让平台看到异常请求模式。
- 新的最小注入和队列化打开后台，是为了减少设备指纹错配和并发/重复触发，但百浩账号 3 应先重新登录，短期内不要连续尝试。

## 请 Claude 后续处理

建议按顺序：

1. 只读复核当前服务状态：
   - `ps -p 75902 -o pid,etime,pcpu,pmem,command`
   - `curl --noproxy '*' --silent --max-time 5 http://127.0.0.1:3457/health`
   - 不要主动打开鲸灵页面。

2. 复核 `sessions/jl.js` 当前是否仍是最小注入：
   - 检查是否引用 `../aftersales-automation/lib/jl/session-filter`。
   - 检查 cookie/localStorage 写入前是否调用 `filterAuthCookies` 和 `filterIdentityLocalStorage`。

3. 复核所有服务入口是否走 `jl.js inject`：
   - `routes.js /accounts/:num/open`
   - `op-queue.js execOpenAccount / execScanAccount / execExecute / execOpenTicket`
   - `pipeline.js autoExecuteApprove`

4. 决定如何持久化 ignored 的 `sessions/jl.js` 改动：
   - 方案 A：继续保留本地脚本，但在 aftersales docs/ops 中明确这是运行态文件，需要手工同步。
   - 方案 B：把运行脚本纳入版本管理或建立生成/部署脚本。
   - 方案 C：让 `sessions/jl.js` 只做薄包装，核心逻辑全部迁移到 tracked module。

5. 不建议立即对百浩账号 3 做任何自动刷新/扫描/打开后台。先让用户手动完成重新登录，再做低频单次验证。

6. 若需要验证“点击打开后台”路径，建议先用非百浩账号或由用户明确授权，再只做一次，并观察队列状态和账号状态回写。

## 当前 git/工作区注意事项

工作区已有多处未提交改动，包含本轮和可能的既有脏改动。不要盲目回滚。

本轮相关重点文件：

- `aftersales-automation/lib/infer.js`
- `aftersales-automation/lib/jl/read-ticket.js`
- `aftersales-automation/lib/jl/session-filter.js`
- `aftersales-automation/lib/server/account-session-status.js`
- `aftersales-automation/lib/server/op-queue.js`
- `aftersales-automation/lib/server/pipeline.js`
- `aftersales-automation/lib/server/pipeline-status.js`
- `aftersales-automation/lib/server/routes.js`
- `aftersales-automation/public/app.js`
- `aftersales-automation/data/account-status.json`
- `aftersales-automation/test/infer/scan-gone-from-list.test.js`
- `aftersales-automation/test/jl/minimal-inject-filter.test.js`
- `aftersales-automation/test/pipeline/terminal-skip-status.test.js`
- `aftersales-automation/test/server/account-session-status.test.js`
- `aftersales-automation/test/server/relogin-session.test.js`
- `sessions/jl.js`，ignored 但运行态已改。

