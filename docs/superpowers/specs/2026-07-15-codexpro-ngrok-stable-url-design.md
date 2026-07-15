# CodexPro ngrok 固定地址设计

## 目标

把 CodexPro 当前每次重启都会变化的 Cloudflare Quick Tunnel 地址，切换为 ngrok 账号分配的固定 dev domain。完成后，电脑断网期间允许服务不可用；网络恢复后用户只需在终端输入一次 `codexpro`，GPT 网页端继续使用原来的应用和 Server URL。

## 当前问题

- `/Users/chat/claude` 的 CodexPro profile 当前使用 `tunnel: cloudflare`，公网地址属于 `trycloudflare.com` 临时隧道。
- 临时隧道重建会产生新 hostname，GPT 应用保存的旧 Server URL 因而失效。
- 隧道退出后，本地 `dist/http.js` 进程可能继续占用 `127.0.0.1:8787`；此时再次运行 `codexpro` 会在端口可用性检查阶段失败。

## 方案选择

采用 ngrok 免费账号自动分配的 dev domain，不采用 Cloudflare Named Tunnel：

- ngrok 不要求用户已有域名，满足个人本地工具的最短可靠路径。
- CodexPro 0.28.5 原生支持 `--tunnel ngrok --hostname <domain>`，并会从工作区 profile 复用 hostname 和 CodexPro token。
- Cloudflare Named Tunnel 同样能固定地址，但需要自有域名和额外 DNS 配置，不符合本次最省事的目标。

## 运行架构

日常启动链路保持不变：

1. 用户输入 shell 函数 `codexpro`。
2. `~/.zshrc` 调用 `/Users/chat/claude/scripts/start-codexpro-full.sh`。
3. 启动脚本进入 `/Users/chat/claude`，加载该工作区保存的 CodexPro profile。
4. 启动脚本清除 shell 快捷函数注入的 HTTP/SOCKS 代理变量，避免 ngrok 免费 agent 触发 `ERR_NGROK_9009`；其他带参数的 CodexPro 子命令仍保留原代理行为。
5. CodexPro 在 `127.0.0.1:8787` 启动 MCP 服务，并通过保存的 ngrok dev domain 暴露固定 HTTPS 地址。
6. GPT 应用始终连接同一个 `https://<dev-domain>/mcp?codexpro_token=<stable-token>`。

断网期间不增加后台重连、launchd 常驻或自动开机启动。网络恢复后，用户主动输入一次 `codexpro` 即可恢复，避免引入不需要的长期进程管理。

## 一次性配置

1. 安装官方 ngrok CLI。
2. 用户在 ngrok 完成注册或登录；账号操作由用户本人确认。
3. 将 ngrok authtoken 写入 ngrok 自己的本机配置，不写入仓库、文档或聊天记录。
4. 从 ngrok Dashboard 读取账号自动分配的 dev domain。
5. 对 `/Users/chat/claude` 执行 `codexpro settings set --tunnel ngrok --hostname <dev-domain>`，保留现有 CodexPro 鉴权 token。
6. GPT 网页端最后一次创建或更新应用，填入固定的完整 Server URL。

## 残留进程处理

启动脚本在启动 CodexPro 前检查 `127.0.0.1:8787`：

- 端口未占用：正常启动。
- 端口由当前用户的 CodexPro `dist/http.js` 占用：先发送 `TERM`，在有限时间内等待端口释放，再启动。
- 端口由其他程序占用，或无法确认进程身份：立即停止并显示 PID/命令提示，不自动杀进程。
- `TERM` 后仍未退出：不自动使用 `KILL`，停止并提示用户，避免误伤或掩盖异常。

这使“再次输入 `codexpro`”具备明确的重启语义，同时把自动清理范围严格限制在可证明属于当前用户的 CodexPro 本地服务。

## 安全边界

- 复用当前工作区已有的 48 位 CodexPro token，切换隧道时不重新生成。
- ngrok authtoken 只进入 ngrok 官方配置文件；任何命令输出、测试 fixture、Git diff 和设计文档都不得包含真实 token。
- CodexPro 保持只监听 `127.0.0.1`，公网访问继续由带 token 的 HTTPS MCP URL 保护。
- 只在无参数日常启动链路中清除 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及其小写形式；不修改用户全局代理配置。
- 保留现有工作区根目录、额外 worktree 根目录、工具模式和环境继承限制，不扩大 GPT 的文件或命令权限。

## 错误反馈

- 未安装或未认证 ngrok：终端给出一次性配置提示，不回退到会变地址的 Cloudflare Quick Tunnel。
- ngrok 报 `ERR_NGROK_9009`：启动脚本必须清除继承的代理变量后再启动，不要求用户购买付费代理能力。
- 固定域名无法连通：启动失败并保留 hostname 配置，用户修复网络后再次运行 `codexpro`；不创建临时替代 URL。
- 端口被非 CodexPro 程序占用：停止并报告具体占用者，不自动处理。

## 验证标准

1. 单元测试证明启动前清理只识别目标 CodexPro 进程，并拒绝处理其他端口占用者。
2. 启动脚本语法检查通过，现有 CodexPro 工作区参数没有丢失。
3. ngrok 本地鉴权有效，CodexPro profile 显示 `tunnel: ngrok` 和固定 hostname，真实 token 全程脱敏。
4. 第一次启动后记录完整 Server URL 的摘要；停止全部本次 CodexPro/ngrok 进程后再次启动，第二次 URL 与第一次逐字节一致。
5. 从公网访问固定 `/healthz` 或 MCP 入口能够到达本机服务，并且无 token 请求继续返回未授权。
6. 最终日常命令仍然是无参数的 `codexpro`。

## 非目标

- 不保证断网期间可用。
- 不创建云端常驻中继、VPS 或自有域名。
- 不增加开机自启、后台守护或断线自动重试。
- 不修改 CodexPro npm 包源码；只使用其公开的 ngrok/profile 能力，并在工作区启动脚本处理本地残留进程。
