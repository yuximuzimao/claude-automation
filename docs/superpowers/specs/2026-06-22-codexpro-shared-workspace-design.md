# CodexPro 共享工作区设计

## 目标

通过 CodexPro 把 ChatGPT 网页版连接到 `/Users/chat/claude`，让 ChatGPT 和 Claude Code、Codex 共享同一套项目规则、源代码、Git 状态、交接文档和已安装 Skills。

这种“分身”共享的是文件和显式上下文，不会共享隐藏对话、模型内部记忆、账号额度或正在运行的 Claude/Codex 会话。

## 访问范围

- 工作区根目录：`/Users/chat/claude`
- GPT 只能写入这个工作区内部
- CodexPro 默认阻止读取 `.env`、私钥、`.git` 内部文件、依赖目录、构建缓存，以及指向工作区外部的软链接
- `/Users/chat/claude` 之外的个人文件和系统文件不在授权范围内

选择整个共享工作区是用户明确确认的方案。这样 GPT 可以处理其中的所有项目，但不能访问用户主目录的其他内容。

## 每次开工时如何获得上下文

ChatGPT 开始工作时按以下顺序执行：

1. 调用 `server_config` 和 `codexpro_self_test`，确认连接和安全配置正常。
2. 调用 `open_current_workspace`，载入工作区和可用 Skills，不展开庞大的完整文件树。
3. 读取根目录的 `AGENTS.md`、`CLAUDE.md`、`docs/HANDOFF.md` 和协作收件箱。
4. 进入具体子项目后，按照根规则读取该项目的 `SKILL.md`、`CLAUDE.md`、`tasks/todo.md` 和 `docs/INDEX.md`。
5. 调用 `codex_context` 获取目标路径适用的规则、`.ai-bridge` 交接信息和当前 Git 状态。
6. 只有任务需要时才通过 `load_skill` 加载项目或全局 Skill。

CodexPro 会自动识别 `AGENTS.md` 类文件。`CLAUDE.md` 不会被自动当成系统指令，因此根 `AGENTS.md` 和开场提示会明确要求 GPT 主动读取它。

## 运行配置

- 工作模式：直接处理项目
- 工具范围：完整工具集
- 写入权限：仅限共享工作区
- 命令权限：安全模式
- 公网连接：带随机密钥的 HTTPS 隧道
- 本地监听：仅 `127.0.0.1`
- 默认端口：`8787`，被占用时再更换

安全命令模式允许查看文件、运行测试、构建、检查代码和执行只读 Git 命令，同时阻止破坏性命令、任意联网命令和危险 Git 操作。退款、拒绝、账号登录、提交确认等真实业务操作继续遵守工作区规则，必须先获得用户明确确认。

## ChatGPT App

在 ChatGPT Developer Mode 中创建一个名为 `CodexPro Workspace` 的私人开发 App。连接地址会包含私密 CodexPro 密钥，不得写入项目文档、Git 提交或发送给其他人。

本次只创建私人草稿 App，不发布给团队或公开市场。

## 完成标准

只有以下检查全部完成，才算真正可用：

1. CodexPro 本地服务和带密钥的 HTTPS 隧道健康。
2. ChatGPT 成功扫描并显示 CodexPro 工具。
3. ChatGPT 能打开 `/Users/chat/claude` 并识别根 `AGENTS.md`。
4. ChatGPT 进入售后项目前先读取 `aftersales-automation/SKILL.md` 和 `CLAUDE.md`。
5. ChatGPT 能报告当前 Git 状态，同时无法读取默认屏蔽的敏感文件。
6. ChatGPT 只在 `.ai-bridge/` 内完成一次无害的写入、读回和清理验证；如果当前 ChatGPT 套餐不提供 MCP 写入，则明确记录实际限制。
7. 验证结束后不留下意外的源码或业务数据改动。

## 已知限制

- GPT 无法继承 Claude/Codex 的隐藏对话和模型内部记忆。
- 实际读写能力取决于 ChatGPT 套餐和 OpenAI 当前开放范围；可能只能读取，不能直接修改。
- 使用期间必须保持 CodexPro 服务和隧道运行。
- Cloudflare 临时隧道重启后地址会变化；稳定地址可以在后续用 ngrok 或 Cloudflare 固定隧道实现。
