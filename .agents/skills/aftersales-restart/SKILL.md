---
name: aftersales-restart
description: 重启鲸灵售后自动化 server。重启后只报告工单状态，由用户手动选择处理，不自动重跑。
---

# 鲸灵售后自动化 — 重启

## 触发时机（必须执行）

满足**任一条件**即触发：

1. 修改了 `lib/infer.js`、`lib/constants.js`、`lib/server/pipeline.js` 等决策逻辑文件
2. 修改了 `lib/` 下任何影响推理/采集/执行的模块
3. 用户明确要求重启
4. commit 了 `refactor` / `fix` 类型的 aftersales 改动后

## 执行流程

### Step 1：检查 op-queue 状态（防打断）

```bash
curl -s http://localhost:3457/api/op-queue | node -e "
const d = require('fs').readFileSync('/dev/stdin','utf8');
const q = JSON.parse(d);
console.log('running:', q.running ? q.running.label : 'null (空闲)');
console.log('pending ops:', (q.pending || []).length);
"
```

**红线**：`running` 非 null → **禁止重启**，等操作完成后再执行。

### Step 2：记录当前状态 → 记录旧 PID

```bash
# 记录当前工单状态
curl -s http://localhost:3457/api/queue | node -e "
const d = require('fs').readFileSync('/dev/stdin','utf8');
const q = JSON.parse(d);
const live = (q.items || []).filter(i => i.mode === 'live');
const notDone = live.filter(i => i.status !== 'done');
console.log('重启前工单:', 'live=' + live.length, '| 非done=' + notDone.length);
notDone.forEach(i => console.log(' ', i.workOrderNum, i.status, i.waitingRescan ? '[重查]' : ''));
"

# 记录 launchd 托管的旧 PID（第一列；为 - 表示当前未运行）
LABEL=com.heizong.aftersale-server
launchctl list | grep heizong
OLD_PID=$(launchctl list | awk -v label="$LABEL" '$3 == label {print $1}')
echo "旧 PID: ${OLD_PID:-unknown}"
```

### Step 3：通过 LaunchAgent 重启

```bash
LABEL=com.heizong.aftersale-server
launchctl kickstart -k gui/$(id -u)/$LABEL
sleep 3
```

### Step 4：验证新进程与 API

```bash
LABEL=com.heizong.aftersale-server
NEW_PID=$(launchctl list | awk -v label="$LABEL" '$3 == label {print $1}')
echo "新 PID: ${NEW_PID:-unknown}"
if [ -n "${OLD_PID:-}" ] && [ "$OLD_PID" != "-" ] && [ -n "$NEW_PID" ] && [ "$OLD_PID" = "$NEW_PID" ]; then
  echo "FAIL: PID 未变化（$OLD_PID）"
  exit 1
fi

launchctl list | grep heizong
lsof -nP -iTCP:3457 -sTCP:LISTEN

curl -s http://localhost:3457/api/queue | node -e "
const d = require('fs').readFileSync('/dev/stdin','utf8');
const q = JSON.parse(d);
const live = (q.items || []).filter(i => i.mode === 'live');
const pending = live.filter(i => i.status === 'pending' || i.status === 'waiting');
console.log('live:', live.length, '| pending/waiting:', pending.length);
"
```

### Step 5：报告工单状态（不自动重跑）

```bash
curl -s http://localhost:3457/api/queue | node -e "
const d = require('fs').readFileSync('/dev/stdin','utf8');
const q = JSON.parse(d);
const live = (q.items || []).filter(i => i.mode === 'live');
const byStatus = {};
live.forEach(i => { byStatus[i.status] = (byStatus[i.status] || 0) + 1; });
console.log('状态分布:', JSON.stringify(byStatus));
const notDone = live.filter(i => i.status !== 'done');
if (notDone.length > 0) {
  console.log('待处理工单:');
  notDone.forEach(i => {
    const flags = [];
    if (i.waitingRescan) flags.push('重查');
    if (i.decision?.action) flags.push('上次决策=' + i.decision.action);
    console.log('  ' + i.workOrderNum + ' [' + i.status + ']' + (flags.length ? ' ' + flags.join(', ') : ''));
  });
} else {
  console.log('无待处理工单');
}
"
```

### Step 6：输出摘要

```
✅ 重启完成
  旧 PID: <old> → 新 PID: <new>
  监听端口: 3457 OK
  API 响应: OK
  N 条待处理工单（状态已列出）

⚠️ 不会自动重跑。用户自行选择处理或重跑。
```

## 注意

- 重启后 `server.js` 加载的是最新代码，无需重新 `npm install`
- server 由 LaunchAgent `com.heizong.aftersale-server` 守护，并受 `server.js` 单实例锁保护；禁止手动 `kill` + `nohup node server.js &`，否则新手动进程会因锁退出或与 launchd 托管状态冲突
- **重启后不自动重跑工单**，由用户手动选择处理。原因：自动重跑会覆盖用户已审阅但未执行的决策（如绿色的 approve），并可能因重新采集导致误判
- `data/` 下的运行时数据不受重启影响
- Chrome 浏览器 tab 不受 server 重启影响（CDP 直连 9222 port）
