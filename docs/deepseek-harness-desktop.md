# DeepSeek Harness Desktop 运行说明

## 定位

DeepSeek Harness Desktop 是个人非商业用途的辅助 Agent，和 Codex、Claude Code 并行使用。它只承担边界明确、可通过 Git diff 回看、失败后容易恢复的低风险任务，例如小型代码修改、测试、文档维护、魔兽实跑状态更新和对已准备材料的分析。

售后、审单、ERP、账号登录、平台提交、批量修改和其它真实业务写操作继续交给现有 Codex / Claude Code 流程。未经用户明确确认，不把群聊原文、账号资料、运行时私密数据或密钥发送给第三方模型 API。

## 当前安装

截至 2026-09-28：

- 应用：`/Applications/Deepseek Harness Desktop.app`
- 版本：`0.18.0`，Intel `x86_64`
- Harness 配置：`~/.dsh/`
- 桌面端状态与日志：`~/Library/Application Support/dsh-tauri/`
- 日志：`~/Library/Application Support/dsh-tauri/logs/desktop.log`
- CLI 启动脚本：`~/.local/bin/dsh`、`~/.local/bin/pnpm`
- 默认本地服务：`127.0.0.1:3080`

安装使用官方 Release 的完整 Bundle DMG。下载后 SHA-256 与 Release 元数据一致，首次启动前通过 Apple Developer ID 签名和公证验证。软件附加非商业使用条款，只用于用户已经确认的个人用途。

## 模型配置

入口：`设置 → 模型 → 添加模型提供方 → 自定义模型 API`。

| 用户拿到的信息 | 配置字段 |
| --- | --- |
| API 请求地址 | `Base URL`；若地址以 `/chat/completions` 或 `/responses` 结尾，通常只保留到 `/v1` |
| 官网链接 | 不填入模型配置，只用于核对提供方与协议 |
| 默认模型 | `Model ID`，按提供方给出的原始值填写 |
| API Key | `API Key`，只在本机页面填写 |

提供方 ID 使用本地稳定短名；创建后不要随意改名。接口支持 `/v1/responses` 时选 `OpenAI Responses`；只支持 `/v1/chat/completions` 时选 `OpenAI Chat Completions`。不凭模型名称猜协议，以提供方文档和实际连接测试为准。

当前自定义 GPT API 已完成连接验证。API 请求地址、模型名称和 API Key 不进入 Git、工作区文档或 Agent 记忆。凭据由 Harness 保存在 `~/.dsh/.credentials.yaml`，任何排障只确认文件与引用状态，不输出内容。

## 工作区规则继承

Harness 默认从最近的 Git 项目根到当前工作目录加载 `AGENTS.md`、`CLAUDE.md` 及本地覆盖文件。因此会话必须直接选择目标子项目，例如：

- `/Users/chat/claude/group-chat-analysis`
- `/Users/chat/claude/wow-quest-route`

`/Users/chat/claude/.git` 是当前项目根，所以会加载工作区根规则与目标项目规则；不会继续向上加载 `/Users/chat/AGENTS.md`。目标项目的 `CLAUDE.md` 已要求先读 `SKILL.md`，每次任务仍应在提示中明确要求按项目入口恢复上下文。

## 日常使用边界

1. 首次进入项目先做只读任务，确认模型能复述当前状态与安全边界。
2. 修改任务优先使用桌面端内置 Git Worktree；不要和 Codex、Claude Code 同时修改同一文件。
3. 交付只接受可审查的 diff；运行相应测试后再合并到主工作区。
4. 群聊项目默认只改代码、Schema、测试和规则；读取 `runtime/` 私密数据需要用户当次明确授权。
5. 魔兽项目的简单实跑恢复点可以直接更新；涉及 Task Card、Observation、Route Profile 或正式发布时，必须进入项目 Route Lifecycle SOP。

## 已知完整性边界

本机实测中，v0.18.0 首次初始化前通过 `codesign --verify --deep --strict` 与 `spctl`。初始化内置插件后，桌面端在应用包的 Harness `node_modules` 内增加 `dsh-tauri-*` 链接，并修改部分随包 Harness JavaScript；此后 `codesign` 报 `a sealed resource is missing or invalid`。

这些变化与首次启动日志记录的内置插件安装时间和路径一致，但结果是：Apple 对原始下载产物的签名验证，不能继续证明初始化后整个应用包逐文件未变化。当前因此保持以下边界：

- 只用于个人、非商业、低风险任务；
- 不授予售后、审单、ERP、账号和密钥目录；
- 升级后重新检查版本、签名与首次初始化后的变化；
- 异常时先查看 `desktop.log`，不要直接删除 `~/.dsh` 或覆盖现有凭据。

常用只读检查：

```bash
ps -axo pid,ppid,etime,command | rg -i 'deepseek-harness-desktop|dsh web'
lsof -nP -iTCP:3080 -sTCP:LISTEN
tail -120 "$HOME/Library/Application Support/dsh-tauri/logs/desktop.log"
```

