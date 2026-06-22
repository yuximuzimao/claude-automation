# CodexPro 人工接入 ChatGPT 完整操作手册

## 当前状态

- 已安装 `codexpro@0.28.5`，命令路径为 `~/.nvm/versions/node/v22.22.1/bin/codexpro`。
- 已确认 Node.js `v22.22.1`，满足 Node.js 20+ 要求。
- 已确认 `/Users/chat/claude` 是要授权给 ChatGPT 的共享工作区。
- 已确认端口 `8787` 可用。
- 尚未生成 `~/.codexpro` 配置。
- 尚未安装完整的 `cloudflared`。
- 尚未启动 CodexPro、本地 MCP 或公网隧道。
- 尚未在 ChatGPT 创建 App。
- 当前没有监听 `8787` 的 CodexPro 服务，也没有已暴露的 CodexPro 公网地址。
- 设计文档：`docs/superpowers/specs/2026-06-22-codexpro-shared-workspace-design.md`。
- 实施计划：`docs/superpowers/plans/2026-06-22-codexpro-shared-workspace-setup.md`。

## 重要边界

- GPT 可以访问 `/Users/chat/claude` 下的全部项目。
- GPT 不能通过 CodexPro 访问这个目录之外的普通文件或系统文件。
- CodexPro 默认屏蔽 `.env`、私钥、`.git` 内部文件、依赖/构建缓存和越界软链接。
- 使用 `bash=safe`，禁止任意联网、破坏性命令和危险 Git 操作。
- 退款、拒绝、账号登录、提交确认等真实业务操作仍必须先获得用户明确确认。
- 连接 URL 中包含私密 `codexpro_token`，不要发到聊天、截图、文档或 Git。

## 方法一：最短成功路径

### 第 1 步：确保代理可用

本机终端设置了以下代理：

```text
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
ALL_PROXY=socks5://127.0.0.1:7897
```

先打开 `Clash Verge`，确认它处于正常连接状态。然后在 Terminal 运行：

```bash
lsof -nP -iTCP:7897 -sTCP:LISTEN
```

看到监听进程后再继续。如果没有输出，先在 Clash Verge 中启动代理，不要继续下载。

### 第 2 步：运行诊断

```bash
cd /Users/chat/claude
codexpro doctor --root /Users/chat/claude --tunnel cloudflare
```

正常结果应包含：

```text
OK Node
OK Build artifacts
OK Package root
OK Local port
OK Ready
```

`Saved profile none` 和 `cloudflared missing` 在首次启动前属于正常警告。

### 第 3 步：启动 CodexPro

```bash
cd /Users/chat/claude
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
  --copy-url
```

首次运行会自动把 Cloudflare 官方 `cloudflared` 安装到：

```text
~/.codexpro/bin/cloudflared
```

成功后终端会显示：

```text
Local MCP ready
Public HTTPS URL ready
Server URL copied
```

保持这个 Terminal 窗口运行。关闭窗口或按 `Ctrl+C` 后，ChatGPT 将无法访问本地项目。

不要把终端显示的完整 Server URL 发给任何人。

## 方法二：cloudflared 自动下载失败时

在 Chrome 打开：

```text
https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz
```

下载完成后，在 Terminal 运行：

```bash
tmpdir="$(mktemp -d)"
mkdir -p ~/.codexpro/bin
tar -xzf ~/Downloads/cloudflared-darwin-amd64.tgz -C "$tmpdir"
install -m 755 "$tmpdir/cloudflared" ~/.codexpro/bin/cloudflared
~/.codexpro/bin/cloudflared --version
```

如果浏览器把文件保存成 `cloudflared-darwin-amd64 (1).tgz`，把命令中的下载文件名替换成实际名称。

看到版本号后，改用以下命令启动：

```bash
cd /Users/chat/claude
codexpro start \
  --root /Users/chat/claude \
  --mode agent \
  --tool-mode full \
  --write workspace \
  --bash safe \
  --host 127.0.0.1 \
  --port 8787 \
  --tunnel cloudflare \
  --cloudflared ~/.codexpro/bin/cloudflared \
  --no-install-cloudflared \
  --save-config \
  --copy-url
```

## 在 ChatGPT 创建 App

必须使用 ChatGPT 网页版。

### 第 1 步：打开 Developer Mode

在 ChatGPT 中进入：

```text
头像 / Settings
→ Apps
→ Advanced settings
→ Developer mode
```

开启 Developer Mode，并保持 CSP 安全选项开启。

如果完全看不到 Developer Mode 或 Create app，说明当前账号/工作区未开放该能力，不能通过设置技巧绕过。

### 第 2 步：创建私人 App

进入：

```text
Settings
→ Apps
→ Create app
```

填写：

```text
Name: CodexPro Workspace
Description: Claude、Codex 与 ChatGPT 共用项目工作区
Server URL: 粘贴 CodexPro 刚复制到剪贴板的完整 HTTPS 地址
Authentication: None / No Authentication
```

说明：虽然 Authentication 选 None，但 Server URL 自己已经带随机 `codexpro_token`，并不是无保护公网服务。

点击 `Scan Tools`。工具扫描成功后再点击 `Create`。保持私人开发草稿，不要 Publish。

## 第一次真机测试

新建一个 ChatGPT 对话，在工具/App 菜单里启用 `CodexPro Workspace`，然后发送：

```text
使用 CodexPro。

先调用 server_config，再调用 codexpro_self_test，并明确传入 write_probe=false；若自检失败就停止并报告。
然后调用 open_current_workspace，include_tree=false，include_skills=true。
读取根目录 AGENTS.md、CLAUDE.md、docs/HANDOFF.md 和 docs/codex-handoff/inbox.json。
接着进入 aftersales-automation，先读取 SKILL.md、CLAUDE.md、tasks/todo.md、docs/INDEX.md。
只报告你识别到的工作区边界、当前项目状态和必须遵守的安全红线，不执行任何真实业务操作。
```

正确结果应包括：

- 工作区是 `/Users/chat/claude`。
- 识别根 `AGENTS.md` 和 `CLAUDE.md`。
- 进入售后项目前先读 `SKILL.md`。
- 知道退款、拒绝、登录、提交等真实操作必须先确认。
- 能看到当前 Git 状态，但不能读取 `.env` 和工作区外文件。

## 写入能力测试

再发送：

```text
只在 .ai-bridge/codexpro-self-test.md 写入一行“CodexPro 写入验证”，读回确认后删除该文件。不要修改其他文件。
```

随后在 Terminal 检查：

```bash
git -C /Users/chat/claude status --short
```

不应出现由测试产生的新源码或业务数据改动。

## ChatGPT 套餐限制

以 OpenAI 当前官方说明和账号页面实际显示为准：

- Pro 账号可能只能使用自定义 MCP 的读取/检索能力。
- 完整写入/修改动作当前主要面向 Business、Enterprise/Edu。
- 如果 App 能读取但不能写，不是 CodexPro 配置错误，也没有合法的本地配置可以绕过套餐限制。

## 日常使用

以后在 Terminal 运行：

```bash
cd /Users/chat/claude
codexpro start
```

Cloudflare 临时隧道每次重启会产生新 URL。需要在 ChatGPT 的 CodexPro App 中更新 Server URL 并刷新工具。

如果希望 URL 长期不变，后续再配置 ngrok 免费固定域名或 Cloudflare Named Tunnel；首次接入不要增加这个复杂度。

## Claude Code 接手任务

请 Claude Code：

1. 先读本文件和实施计划。
2. 从“方法一：最短成功路径”继续。
3. 不读取或输出任何 token。
4. 每完成本地服务、隧道、Developer Mode、App 创建、真机测试中的一步，就向用户报告并等待明确继续指令。
5. 完成后把本交接归档到 `docs/codex-handoff/archive/<date>-codexpro-setup/`，同步更新 `inbox.json` 的路径和状态。
