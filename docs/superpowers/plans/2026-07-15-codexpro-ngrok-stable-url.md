# CodexPro ngrok Stable URL Implementation Plan

> **状态：已完成（2026-07-15）。** 固定域名为 `atop-chewing-tidiness.ngrok-free.dev`；两次启动的 endpoint 与 token 哈希一致，公网未鉴权请求返回 401、正确鉴权返回 200，用户已在 GPT 网页端创建应用并实测连接成功。下方未勾选项保留为实施时的原始执行清单，不代表当前待办。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/Users/chat/claude` 的 CodexPro 使用同一个 ngrok HTTPS 地址，并让无参数 `codexpro` 能安全重启断线后残留的本地 CodexPro 服务。

**Architecture:** CodexPro 继续监听 `127.0.0.1:8787`，工作区 profile 保存 ngrok 账号分配的 dev domain 和现有 CodexPro token。启动脚本在拉起 CodexPro 前调用一个独立、可测试的端口守卫，只终止当前用户且命令路径明确属于全局 CodexPro `dist/http.js` 的监听进程；其他占用者一律拒绝处理。

**Tech Stack:** Bash 3.2、Node.js 22、CodexPro 0.28.5、ngrok CLI、Homebrew、`lsof`、`ps`、`jq`、Git worktree

---

## 文件结构

- 创建 `scripts/lib/codexpro-startup-guard.sh`：识别并温和终止残留的 CodexPro HTTP 服务。
- 修改 `scripts/start-codexpro-full.sh`：启动前加载端口守卫，保留现有工作区、代理和额外 allowed root 行为。
- 创建 `test/workspace/codexpro-startup-guard.test.sh`：使用真实监听进程验证“拒绝其他程序、终止 CodexPro 服务”两条安全边界。
- 修改 `docs/HANDOFF.md`：记录固定 URL 的日常启动方式和秘密信息边界，但不记录域名中的鉴权 token 或 ngrok authtoken。

### Task 1: 创建隔离 worktree 并验证基线

**Files:**
- No repository changes

- [ ] **Step 1: 确认当前不是 linked worktree**

Run:

```bash
git -C /Users/chat/claude rev-parse --git-dir
git -C /Users/chat/claude rev-parse --git-common-dir
git -C /Users/chat/claude branch --show-current
```

Expected: 前两项都是 `.git`，分支是 `main`。

- [ ] **Step 2: 在既有全局 worktree 目录创建隔离分支**

Run:

```bash
git -C /Users/chat/claude worktree add /Users/chat/.config/superpowers/worktrees/claude/codexpro-ngrok-stable-url -b codexpro-ngrok-stable-url
```

Expected: 创建分支和目录，不影响 `/Users/chat/claude` 当前未提交改动。

- [ ] **Step 3: 运行与启动脚本直接相关的基线检查**

Run:

```bash
bash -n /Users/chat/.config/superpowers/worktrees/claude/codexpro-ngrok-stable-url/scripts/start-codexpro-full.sh
git -C /Users/chat/.config/superpowers/worktrees/claude/codexpro-ngrok-stable-url status --short
```

Expected: `bash -n` 退出码为 0，worktree 状态为空。

### Task 2: 用 TDD 增加 CodexPro 残留进程守卫

**Files:**
- Create: `scripts/lib/codexpro-startup-guard.sh`
- Modify: `scripts/start-codexpro-full.sh`
- Create: `test/workspace/codexpro-startup-guard.test.sh`

- [ ] **Step 1: 写入失败测试**

Create `test/workspace/codexpro-startup-guard.test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
GUARD="$ROOT_DIR/scripts/lib/codexpro-startup-guard.sh"
TMP_DIR="$(mktemp -d)"
PIDS=()

cleanup() {
  local pid
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

free_port() {
  node -e 'const s=require("net").createServer();s.listen(0,"127.0.0.1",()=>{console.log(s.address().port);s.close();});'
}

wait_for_listener() {
  local port="$1" attempt=0
  while ! lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 40 ]; then
      fail "listener did not start on port $port"
    fi
    sleep 0.1
  done
}

[ -f "$GUARD" ] || fail "startup guard is missing"
# shellcheck source=/dev/null
source "$GUARD"

EMPTY_PORT="$(free_port)"
if ! bash -euo pipefail -c 'source "$1"; codexpro_stop_stale_server "$2"' _ "$GUARD" "$EMPTY_PORT"; then
  fail "guard failed when the port was already free"
fi

UNRELATED_PORT="$(free_port)"
node -e 'require("http").createServer((_,res)=>res.end("ok")).listen(Number(process.argv[1]),"127.0.0.1")' "$UNRELATED_PORT" &
UNRELATED_PID=$!
PIDS+=("$UNRELATED_PID")
wait_for_listener "$UNRELATED_PORT"

if codexpro_stop_stale_server "$UNRELATED_PORT" 2>/dev/null; then
  fail "guard accepted a non-CodexPro listener"
fi
kill -0 "$UNRELATED_PID" 2>/dev/null || fail "guard killed a non-CodexPro listener"

MANAGED_PORT="$(free_port)"
mkdir -p "$TMP_DIR/workspace"
CODEXPRO_HTTP="$(npm root -g)/codexpro/dist/http.js"
[ -f "$CODEXPRO_HTTP" ] || fail "global CodexPro HTTP entrypoint was not found"
CODEXPRO_ROOT="$TMP_DIR/workspace" \
CODEXPRO_ALLOWED_ROOTS="$TMP_DIR/workspace" \
CODEXPRO_HOST=127.0.0.1 \
CODEXPRO_PORT="$MANAGED_PORT" \
CODEXPRO_BASH_MODE=off \
CODEXPRO_WRITE_MODE=off \
CODEXPRO_TOOL_MODE=minimal \
CODEXPRO_HTTP_TOKEN=test-only-token \
node "$CODEXPRO_HTTP" >/dev/null 2>&1 &
MANAGED_PID=$!
PIDS+=("$MANAGED_PID")
wait_for_listener "$MANAGED_PORT"

codexpro_stop_stale_server "$MANAGED_PORT"
if lsof -nP -iTCP:"$MANAGED_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
  fail "CodexPro listener still owns port $MANAGED_PORT"
fi

grep -Fq 'codexpro_stop_stale_server 8787' "$ROOT_DIR/scripts/start-codexpro-full.sh" || fail "launcher does not call the startup guard"
grep -Fq 'unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy' "$ROOT_DIR/scripts/start-codexpro-full.sh" || fail "launcher does not isolate ngrok from proxy variables"

printf 'PASS: CodexPro startup guard boundaries verified\n'
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run:

```bash
bash test/workspace/codexpro-startup-guard.test.sh
```

Expected: 退出码为 1，输出 `FAIL: startup guard is missing`。

- [ ] **Step 3: 写入最小端口守卫实现**

Create `scripts/lib/codexpro-startup-guard.sh`:

```bash
#!/usr/bin/env bash

codexpro_port_owner_pid() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1
}

codexpro_process_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null
}

codexpro_is_managed_server() {
  local pid="$1" owner_uid command_line
  owner_uid="$(ps -p "$pid" -o uid= 2>/dev/null | tr -d ' ')"
  [ "$owner_uid" = "$(id -u)" ] || return 1
  command_line="$(codexpro_process_command "$pid")"
  [[ "$command_line" == "node "* || "$command_line" == *"/node "* ]] || return 1
  [[ "$command_line" == *"/lib/node_modules/codexpro/dist/http.js"* ]]
}

codexpro_stop_stale_server() {
  local port="${1:-8787}" pid command_line attempt=0
  pid="$(codexpro_port_owner_pid "$port" || true)"
  [ -n "$pid" ] || return 0

  if ! codexpro_is_managed_server "$pid"; then
    command_line="$(codexpro_process_command "$pid")"
    printf '端口 %s 已被非 CodexPro 进程占用（PID %s）：%s\n' "$port" "$pid" "$command_line" >&2
    printf '为避免误杀，启动已停止。请先确认并处理该进程。\n' >&2
    return 1
  fi

  printf '检测到残留的 CodexPro 本地服务（PID %s），正在安全停止...\n' "$pid"
  kill -TERM "$pid"
  while codexpro_port_owner_pid "$port" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 20 ]; then
      printf 'CodexPro 进程收到 TERM 后仍未释放端口 %s；未使用强制终止。\n' "$port" >&2
      return 1
    fi
    sleep 0.25
  done
}
```

- [ ] **Step 4: 把守卫接入启动脚本**

Modify `scripts/start-codexpro-full.sh` so the complete file is:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/codexpro-startup-guard.sh
source "$SCRIPT_DIR/lib/codexpro-startup-guard.sh"

codexpro_stop_stale_server 8787

cd /Users/chat/claude

# Search-heavy monorepo default. CodexPro clamps this to 2000 internally.
export CODEXPRO_MAX_SEARCH_RESULTS="${CODEXPRO_MAX_SEARCH_RESULTS:-1000}"

# Keep full env inheritance opt-in because it can expose local tokens and proxy/env
# values to ChatGPT-triggered bash commands.
export CODEXPRO_INHERIT_ENV="${CODEXPRO_INHERIT_ENV:-0}"

# ngrok's free agent rejects inherited HTTP/SOCKS proxy settings (ERR_NGROK_9009).
# Keep the shell shortcut's proxy behavior for other CodexPro subcommands, but let
# the local server and ngrok tunnel use the machine's direct network path.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

exec codexpro start \
  --allow-root /Users/chat/.config/superpowers/worktrees
```

- [ ] **Step 5: 运行测试和语法检查，确认转绿**

Run:

```bash
bash test/workspace/codexpro-startup-guard.test.sh
bash -n scripts/lib/codexpro-startup-guard.sh
bash -n scripts/start-codexpro-full.sh
```

Expected: 测试输出 `PASS: CodexPro startup guard boundaries verified`，两个语法检查退出码均为 0；由 shell 快捷函数注入的代理变量不会传给 ngrok，因此不会触发 `ERR_NGROK_9009`。

- [ ] **Step 6: 提交守卫与测试**

Run:

```bash
git add scripts/lib/codexpro-startup-guard.sh scripts/start-codexpro-full.sh test/workspace/codexpro-startup-guard.test.sh
git commit -m "fix(workspace): restart stale CodexPro service safely"
```

Expected: commit 只包含上述 3 个文件。

### Task 3: 安装 ngrok 并保存固定 profile

**Files:**
- Modify outside repository: ngrok CLI 报告的用户配置文件（macOS 当前为 `~/Library/Application Support/ngrok/ngrok.yml`）
- Modify outside repository: `~/.codexpro/profiles/*.json` for root `/Users/chat/claude`

- [ ] **Step 1: 安装官方 ngrok CLI**

Run:

```bash
brew install ngrok
ngrok version
```

Expected: `ngrok version` 输出已安装版本并以 0 退出。

- [ ] **Step 2: 由用户完成一次 ngrok 登录和本机鉴权**

Open `https://dashboard.ngrok.com/get-started/setup/macos` in a new background browser tab. If the dashboard is not authenticated, ask the user to log in or register; after the user explicitly confirms, let the user copy and execute the dashboard-provided `ngrok config add-authtoken` command in their own terminal. Do not copy the real authtoken into the plan, repository, agent command text, or transcript.

Run after the user confirms:

```bash
ngrok config check
```

Expected: ngrok reports a valid config file under the user's home directory.

- [ ] **Step 3: 读取账号分配的固定 dev domain**

Open `https://dashboard.ngrok.com/domains` in the authenticated browser tab and read the account-assigned dev domain. Store it only as the runtime shell variable `NGROK_DOMAIN`; it is not a secret.

- [ ] **Step 4: 保存 CodexPro ngrok profile，同时证明 token 没变**

Run from `/Users/chat/claude`:

```bash
PROFILE="$(rg -l '"root": "/Users/chat/claude"' /Users/chat/.codexpro/profiles/*.json | head -n 1)"
BEFORE_TOKEN_SHA="$(jq -r '.token' "$PROFILE" | shasum -a 256 | awk '{print $1}')"
codexpro settings set --root /Users/chat/claude --tunnel ngrok --hostname "$NGROK_DOMAIN"
AFTER_TOKEN_SHA="$(jq -r '.token' "$PROFILE" | shasum -a 256 | awk '{print $1}')"
test "$BEFORE_TOKEN_SHA" = "$AFTER_TOKEN_SHA"
jq '{root,tunnel,hostname,mode,write,bash,toolMode,token:(if .token then "<saved>" else null end)}' "$PROFILE"
```

Expected: token 哈希比较退出码为 0；脱敏输出显示 `tunnel: ngrok`、账号固定 hostname，其他权限字段保持原值。

### Task 4: 合并启动脚本并验证同一 URL 可重复启动

**Files:**
- Modify: `docs/HANDOFF.md`

- [ ] **Step 1: 更新 handoff 的稳定运行事实**

Append this section to `docs/HANDOFF.md` without any real token:

```markdown
## CodexPro 固定地址（2026-07-15）

- `/Users/chat/claude` 已切换到 ngrok 账号固定 dev domain；GPT App Server URL 不再随 CodexPro 重启变化。
- 日常恢复：网络可用后在终端输入一次 `codexpro`。
- 启动脚本会自动 TERM 当前用户残留的 CodexPro `dist/http.js`，但拒绝处理任何无法确认身份的 8787 端口占用者。
- ngrok authtoken 只保存在 ngrok 官方本机配置；CodexPro token 只保存在 `~/.codexpro` profile，文档和 Git 不记录真实值。
```

- [ ] **Step 2: 提交 handoff**

Run:

```bash
git add docs/HANDOFF.md
git commit -m "docs(workspace): record CodexPro stable URL operation"
```

Expected: commit 只包含 `docs/HANDOFF.md`。

- [ ] **Step 3: 合并前检查没有删除运行时文件**

Run:

```bash
OLD="$(git -C /Users/chat/claude rev-parse HEAD)"
NEW="$(git -C /Users/chat/.config/superpowers/worktrees/claude/codexpro-ngrok-stable-url rev-parse HEAD)"
git -C /Users/chat/claude diff --diff-filter=D --name-only "$OLD" "$NEW"
```

Expected: 无输出，尤其不能出现 `data/`、日志或状态文件。

- [ ] **Step 4: 把实现分支快进合并到 main**

Run:

```bash
git -C /Users/chat/claude merge --ff-only codexpro-ngrok-stable-url
```

Expected: main 快进到实现分支，用户原有未提交文件保持不变。

- [ ] **Step 5: 第一次启动并保存脱敏证据**

Run `/Users/chat/claude/scripts/start-codexpro-full.sh` through a line-buffered redaction filter that replaces every `codexpro_token=` query value before it reaches the agent transcript. Once ready, read the workspace runtime JSON and store only `endpoint` plus the SHA-256 of the profile token as `FIRST_ENDPOINT` and `FIRST_TOKEN_SHA`.

Expected: endpoint hostname equals `NGROK_DOMAIN`，公网健康检查通过；任何展示文本中的 token 都是 `<redacted>`。

- [ ] **Step 6: 停止第一次启动并再次启动**

Send Ctrl+C to the launcher, confirm its CodexPro and ngrok children release port 8787, then run the same redacted startup command again. Read `SECOND_ENDPOINT` and `SECOND_TOKEN_SHA` from the same files.

Expected: 第二次启动成功，没有端口占用错误。

- [ ] **Step 7: 比较两次地址和 token**

Run:

```bash
test "$FIRST_ENDPOINT" = "$SECOND_ENDPOINT"
test "$FIRST_TOKEN_SHA" = "$SECOND_TOKEN_SHA"
test "$SECOND_ENDPOINT" = "https://$NGROK_DOMAIN/mcp"
```

Expected: 三项比较都以 0 退出。

- [ ] **Step 8: 验证公网未授权边界**

Run:

```bash
STATUS="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "https://$NGROK_DOMAIN/healthz")"
test "$STATUS" = "401"
```

Expected: 无 token 请求返回 HTTP 401，证明固定域名可达且鉴权仍生效。

### Task 5: 完成一次 GPT 应用换址

**Files:**
- No repository changes

- [ ] **Step 1: 把固定 Server URL 安全写入剪贴板**

Run with the actual profile/runtime file paths, without printing the value:

```bash
jq -nr --slurpfile profile "$PROFILE" --slurpfile runtime "$RUNTIME" '$runtime[0].endpoint + "?codexpro_token=" + $profile[0].token' | pbcopy
```

Expected: 剪贴板包含固定完整 URL，终端和 agent transcript 不显示 token。

- [ ] **Step 2: 用户确认后在 GPT 网页端创建最后一个应用**

Open ChatGPT Developer Mode app configuration only after reporting that the local fixed endpoint passed both restarts. The user pastes the clipboard URL and performs the final create/save action; do not submit an account write without the user's explicit instruction.

- [ ] **Step 3: 用新应用执行只读自检**

Call `server_config` or `codexpro_self_test` from the new GPT app and confirm it reports `/Users/chat/claude`, expected tool/write/bash modes, and the saved ngrok hostname. Do not perform business-system writes.

Expected: GPT 应用可连接，断线恢复后的日常命令仍是 `codexpro`。

### Task 6: 最终验证和收尾

**Files:**
- Verify only

- [ ] **Step 1: 重新运行全部本任务检查**

Run:

```bash
bash /Users/chat/claude/test/workspace/codexpro-startup-guard.test.sh
bash -n /Users/chat/claude/scripts/lib/codexpro-startup-guard.sh
bash -n /Users/chat/claude/scripts/start-codexpro-full.sh
git -C /Users/chat/claude diff --check
git -C /Users/chat/claude log -3 --oneline
```

Expected: 测试 PASS、语法检查与 diff 检查退出码均为 0，最近提交包含设计、守卫实现和运行说明。

- [ ] **Step 2: 核对需求清单**

Confirm all are true:

```text
固定 hostname 已保存在 /Users/chat/claude profile
CodexPro token 切换前后哈希一致
两次重启 endpoint 完全一致
无 token 的公网请求返回 401
无参数 codexpro 仍是唯一日常恢复命令
Git 和文档中没有 ngrok authtoken 或真实 CodexPro token
```

- [ ] **Step 3: 按工作区规则推送已验证提交**

Run:

```bash
git -C /Users/chat/claude push
```

Expected: 推送成功；如果远端拒绝，不做 force push，保留本地提交并报告原因。
