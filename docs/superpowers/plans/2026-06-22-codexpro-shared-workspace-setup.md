# CodexPro 共享工作区接入实施计划

> **历史状态：已被固定地址方案取代。** 本文保留 2026-06-22 首次接入时的 Cloudflare 临时地址步骤；当前实施结果以 [CodexPro ngrok 固定地址计划](2026-07-15-codexpro-ngrok-stable-url.md) 与 `docs/HANDOFF.md` 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ChatGPT 网页版安全连接到 `/Users/chat/claude`，并通过真实工具调用验证它能按 Claude/Codex 的共享规则处理项目。

**Architecture:** CodexPro 在本机 `127.0.0.1:8787` 提供受限 MCP 服务，Cloudflare 临时隧道提供带随机密钥的 HTTPS 地址，ChatGPT Developer Mode 以私人草稿 App 连接。工作区权限止于 `/Users/chat/claude`，命令使用安全模式，实际上下文通过根规则、项目规则、Git 状态和交接文档加载。

**Tech Stack:** CodexPro 0.28.5、Node.js 22、MCP、Cloudflare Tunnel、ChatGPT Developer Mode

---

### Task 1: 本机预检

**Files:**
- Read: `/Users/chat/claude/AGENTS.md`
- Read: `/Users/chat/claude/CLAUDE.md`
- Read: `/Users/chat/claude/docs/HANDOFF.md`
- Create on first saved run: a workspace profile under `/Users/chat/.codexpro/profiles/`

- [ ] **Step 1: 确认 CodexPro、Node 和端口状态**

Run:

```bash
command -v codexpro
node --version
lsof -nP -iTCP:8787 -sTCP:LISTEN
```

Expected: 找到 CodexPro，Node >= 20，端口没有现有监听进程。

- [ ] **Step 2: 运行不启动服务的诊断**

Run:

```bash
codexpro doctor --root /Users/chat/claude --tunnel cloudflare
```

Expected: 构建产物、工作区、剪贴板和浏览器检查通过；缺少 `cloudflared` 时允许 CodexPro 后续安装到 `~/.codexpro/bin`。

### Task 2: 启动安全 MCP 和隧道

**Files:**
- Create: a workspace profile under `/Users/chat/.codexpro/profiles/`
- Create if missing: `/Users/chat/.codexpro/bin/cloudflared`

- [ ] **Step 1: 启动并保存工作区配置**

Run in a persistent terminal session:

```bash
codexpro start \
  --root /Users/chat/claude \
  --mode agent \
  --tool-mode full \
  --write workspace \
  --bash safe \
  --host 127.0.0.1 \
  --port 8787 \
  --tunnel cloudflare \
  --save-config \
  --copy-url \
  --no-open-chatgpt
```

Expected: 显示本地 MCP 地址、Cloudflare HTTPS 地址和已保存配置；公开地址包含 `codexpro_token`，不得写入日志或项目文件。

- [ ] **Step 2: 验证本地健康状态**

从 CodexPro 启动输出读取本次生成的 token，只在当前诊断进程内请求 `http://127.0.0.1:8787/healthz`，不把完整 URL 写入文件或回复。

Expected: 返回健康状态，根目录为 `/Users/chat/claude`，模式为 `agent/full/workspace/safe`。

- [ ] **Step 3: 验证公网隧道**

使用 CodexPro 本次输出的完整 HTTPS 地址请求同一 `healthz` 路径，完整地址只保留在当前进程和系统剪贴板中。

Expected: 返回与本地一致的健康状态，未带 token 的请求必须被拒绝。

### Task 3: 创建 ChatGPT 私人 App

**Files:**
- No local file changes

- [ ] **Step 1: 检查 ChatGPT 套餐和 Developer Mode**

在新的 ChatGPT 后台标签页打开 `Settings -> Apps -> Advanced settings`。

Expected: 当前账号已登录，并显示 Developer Mode 或创建自定义 App 的入口；若账号套餐限制写入能力，记录实际提示。

- [ ] **Step 2: 获得用户确认后开启 Developer Mode**

Expected: Developer Mode 开启，保留 CSP 安全选项。

- [ ] **Step 3: 获得用户确认后创建私人 App**

Use:

```text
Name: CodexPro Workspace
Description: Claude、Codex 与 ChatGPT 共用项目工作区
Server URL: 使用剪贴板中的带密钥 HTTPS MCP 地址
Authentication: None / No Authentication
```

Expected: 工具扫描成功，App 以私人开发草稿形式出现，不发布到团队或市场。

### Task 4: ChatGPT 真机验收

**Files:**
- Create/edit/delete during probe: `/Users/chat/claude/.ai-bridge/codexpro-self-test.md`
- Read: `/Users/chat/claude/AGENTS.md`
- Read: `/Users/chat/claude/CLAUDE.md`
- Read: `/Users/chat/claude/aftersales-automation/SKILL.md`
- Read: `/Users/chat/claude/aftersales-automation/CLAUDE.md`

- [ ] **Step 1: 在新对话中启用 CodexPro App 并运行开场提示**

Prompt:

```text
使用 CodexPro。

先调用 server_config，再调用 codexpro_self_test，并明确传入 write_probe=false；若自检失败就停止并报告。
然后调用 open_current_workspace，include_tree=false，include_skills=true。
读取根目录 AGENTS.md、CLAUDE.md、docs/HANDOFF.md 和协作收件箱。
接着进入 aftersales-automation，先读取 SKILL.md、CLAUDE.md、tasks/todo.md、docs/INDEX.md。
只报告你识别到的工作区边界、当前项目状态和必须遵守的安全红线，不执行任何真实业务操作。
```

Expected: GPT 正确报告 `/Users/chat/claude` 边界、售后项目入口文件和真实业务操作需确认的红线。

- [ ] **Step 2: 验证写入边界**

Prompt:

```text
只在 .ai-bridge/codexpro-self-test.md 写入一行“CodexPro 写入验证”，读回确认后删除该文件。不要修改其他文件。
```

Expected: 支持写操作的套餐完成写入、读回、删除；只读套餐明确拒绝写入，但读取能力保持正常。

- [ ] **Step 3: 检查无意外改动**

Run:

```bash
git -C /Users/chat/claude status --short
```

Expected: 与验证前状态相比，没有新增源代码或业务数据改动，测试探针已清理。

### Task 5: 日常使用交付

**Files:**
- Read: the saved workspace profile under `/Users/chat/.codexpro/profiles/`, with token redacted from all output

- [ ] **Step 1: 验证保存配置可复用**

Run after the initial server is stopped only when a restart test is needed:

```bash
cd /Users/chat/claude
codexpro start
```

Expected: 自动复用工作区、端口、权限和 tunnel 选择。Cloudflare 临时 URL 会变化，因此 ChatGPT App 的 Server URL 需要同步更新。

- [ ] **Step 2: 交付日常使用说明**

Expected: 用户只需要保持 CodexPro 终端运行、在 ChatGPT 对话中启用 App，并使用统一开场提示；密钥不出现在项目或聊天总结中。
