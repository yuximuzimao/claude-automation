# CodexPro 共享工作区设计

## 目标

通过 CodexPro 把 ChatGPT 网页版连接到主工作区 `/Users/chat/claude`，并允许它按需打开 `/Users/chat/.config/superpowers/worktrees` 下的 Superpowers 隔离 worktree。这样 ChatGPT 能和 Claude Code、Codex 共享同一套项目规则、源代码、Git 状态、交接文档和已安装 Skills。

这种“分身”共享的是文件和显式上下文，不会共享隐藏对话、模型内部记忆、账号额度或正在运行的 Claude/Codex 会话。

## 访问范围

- 默认工作区根目录：`/Users/chat/claude`。启动脚本仍先进入此目录，所以 `open_current_workspace` 打开的始终是主工作区。
- 附加允许根：`/Users/chat/.config/superpowers/worktrees`。它覆盖现有和未来的 Superpowers worktree；处理具体隔离分支时，GPT 必须用 `open_workspace` 打开该分支的绝对路径。
- 启动入口会清除 `CODEXPRO_ROOT`、`CODEBASE_BRIDGE_REPO_ROOT`、`CODEXPRO_ALLOW_HOME` 和 `CODEBASE_BRIDGE_ALLOWED_ROOTS`，防止调用者遗留环境覆盖默认根或与允许根合并。
- 内置文件工具受上述允许根约束；CodexPro 默认仍会屏蔽 `.env`、私钥、`.git` 内部文件、依赖目录、构建缓存，以及指向允许根外部的软链接。
- 不使用 `--allow-home`，也不把整个 `/Users/chat/.config` 作为允许根，避免未来把无关配置自动纳入访问范围。

用户明确保留 `bash=full`。因此这是“受信任的本机开发代理”模式，而不是操作系统级目录沙箱：内置文件工具会遵守允许根，完整 Bash 则不应被理解为对工作区外路径的绝对隔离。启动入口清除根环境变量只锁定 CodexPro 内置文件工具的根配置，不改变完整 Bash 的系统权限。

## 每次开工时如何获得上下文

ChatGPT 开始工作时按以下顺序执行：

1. 调用 `server_config` 和 `codexpro_self_test`，确认连接和安全配置正常；`server_config.allowedRoots` 应同时包含主工作区和 Superpowers worktree 根。
2. 调用 `open_current_workspace`，载入主工作区和可用 Skills，不展开庞大的完整文件树。
3. 如果任务指向隔离分支，调用 `open_workspace` 打开该 worktree 的绝对路径；后续文件、搜索、写入和 Bash 调用都传递返回的 `workspace_id`。主工作区任务继续使用第 2 步的工作区。
4. 在当前任务的工作区中读取根目录的 `AGENTS.md`、`CLAUDE.md`、`docs/HANDOFF.md` 和协作收件箱。
5. 进入具体子项目后，按照根规则读取该项目的 `SKILL.md`、`CLAUDE.md`、`tasks/todo.md` 和 `docs/INDEX.md`。
6. 调用 `codex_context` 获取目标路径适用的规则、`.ai-bridge` 交接信息和当前 Git 状态。
7. 只有任务需要时才通过 `load_skill` 加载项目或全局 Skill。

CodexPro 会自动识别 `AGENTS.md` 类文件。`CLAUDE.md` 不会被自动当成系统指令，因此根 `AGENTS.md` 和开场提示会明确要求 GPT 主动读取它。

## 运行配置

- 工作模式：直接处理项目
- 工具范围：完整工具集
- 写入权限：工作区写入；内置文件工具的允许根为主工作区和 Superpowers worktree 根
- 启动覆盖防护：固定 `/Users/chat/claude` 为启动 cwd，清除四个根覆盖环境变量后只传入 worktree 附加根
- 命令权限：`bash=full`（用户已确认的受信任本机代理模式，不是路径沙箱）
- 公网连接：Cloudflare quick tunnel 提供的带随机密钥 HTTPS 隧道
- 本地监听：仅 `127.0.0.1`
- 默认端口：`8787`，被占用时再更换

退款、拒绝、账号登录、提交确认等真实业务操作继续遵守工作区规则，必须先获得用户明确确认。

## ChatGPT App

在 ChatGPT 网页版的“设置 → Apps”中创建或维护一个名为 `CodexPro Workspace` 的私人 Dev 连接。连接地址会包含私密 CodexPro 密钥，不得写入项目文档、Git 提交或发送给其他人。

Cloudflare quick tunnel 重启后会生成新的连接地址；在网页 Settings → Apps 中编辑现有 Dev 连接的地址。若当前界面没有编辑入口，则新建同用途 Dev 连接，验证后再删除旧连接。该连接不发布给团队或公开市场。

## 完成标准

只有以下检查全部完成，才算真正可用：

1. CodexPro 本地服务和带密钥的 HTTPS 隧道健康。
2. ChatGPT 成功扫描并显示 CodexPro 工具。
3. `server_config.allowedRoots` 显示 `/Users/chat/claude` 与 `/Users/chat/.config/superpowers/worktrees`，且不包含 `--allow-home` 或整个 `/Users/chat/.config`；带污染根环境变量启动时也必须得到同样结果。
4. ChatGPT 能打开 `/Users/chat/claude` 并识别根 `AGENTS.md`。
5. ChatGPT 能通过 `open_workspace` 打开目标 worktree，并读取其中的交接文档、计划和 `tasks/todo.md`。
6. ChatGPT 进入售后项目前先读取 `aftersales-automation/SKILL.md` 和 `CLAUDE.md`。
7. ChatGPT 能报告当前 Git 状态，同时无法读取默认屏蔽的敏感文件。
8. ChatGPT 只在 `.ai-bridge/` 内完成一次无害的写入、读回和清理验证；如果当前 ChatGPT 套餐不提供 MCP 写入，则明确记录实际限制。
9. 验证结束后不留下意外的源码或业务数据改动。

## 已知限制

- GPT 无法继承 Claude/Codex 的隐藏对话和模型内部记忆。
- 实际读写能力取决于 ChatGPT 套餐和 OpenAI 当前开放范围；可能只能读取，不能直接修改。
- 使用期间必须保持 CodexPro 服务和隧道运行。
- Cloudflare quick tunnel 重启后地址会变化；需要在网页 Settings → Apps 更新现有 Dev 连接，或新建并验证替代连接。
