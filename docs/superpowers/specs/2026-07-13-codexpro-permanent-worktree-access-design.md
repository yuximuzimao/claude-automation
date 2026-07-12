# CodexPro 永久访问 Superpowers Worktree 设计

## 目标

让通过 CodexPro 连接的 GPT 在保留主工作区 `/Users/chat/claude` 的同时，能够永久打开和处理所有位于 `/Users/chat/.config/superpowers/worktrees/` 下的隔离 worktree。它不需要为每个新分支重新配置或复制 handoff、计划和待办文件。

人话：GPT 将能像本地 Codex 一样直接接手隔离分支，而不是只能看主分支的旧状态。

## 已确认的权限模型

- 默认工作区仍是 `/Users/chat/claude`。
- 额外允许根固定为 `/Users/chat/.config/superpowers/worktrees`，覆盖现有及未来的 Superpowers worktree。
- 不使用 `--allow-home`，也不把整个 `/Users/chat/.config` 作为长期授权根；后者目前多余，未来还会意外纳入非项目配置。
- 保持现有 `mode=agent`、`write=workspace`、`tool-mode=full` 和 `bash=full`。

`bash=full` 是用户明确接受的信任模式：CodexPro 的文件工具会受允许根约束，但完整 Bash 不构成操作系统级目录沙箱。因此该模式的含义是“允许 GPT 以本机受信任开发代理身份工作”，不是“工作区外绝对不可访问”。

## 方案

### 1. 启动入口固定追加 worktree 根

修改 `scripts/start-codexpro-full.sh`，每次执行时都向 `codexpro start` 传入：

```bash
--allow-root /Users/chat/.config/superpowers/worktrees
```

不能只修改 CodexPro profile：本机 0.28.5 的启动器不会从 profile 读取 `allowRoots`，而只读取本次命令行参数。因此启动脚本是稳定、可复用的配置边界。

### 2. GPT 切换到指定 worktree

GPT 在继续隔离分支任务时应：

1. 调用 `server_config`，确认 `allowedRoots` 同时包含主工作区和 worktree 根。
2. 调用 `open_workspace`，传入目标 worktree 的绝对路径，例如 `/Users/chat/.config/superpowers/worktrees/claude/aftersales-confidence-safety-v1`。
3. 在后续文件、搜索、写入和 Bash 工具调用中使用返回的 `workspace_id`。

`open_current_workspace` 仍只会打开主工作区，不能代替第 2 步。

### 3. 文档同步

更新既有 CodexPro 共享工作区设计，使日常启动和切换说明与实际配置一致，并明确 full-Bash 的授权语义。

## 不做的事

- 不修改 CodexPro 全局 profile 中的 token 或隧道设置。
- 不开放整个家目录，不使用 `--allow-home`。
- 不复制 worktree 内容、建立绕过真实路径检查的软链接，或把 handoff 当作代码访问的替代品。
- 不引入操作系统级 Bash 沙箱；如未来需要严格目录隔离，另立设计和验收。

## 影响与验收

- 现有 CodexPro 服务必须重启才会载入新的允许根。
- 当前使用 Cloudflare quick tunnel，重启会生成新的私人连接地址；需要在 ChatGPT 私人 App 中更新该地址。
- 重启后在 GPT 侧验证：`server_config` 显示 worktree 根；`open_workspace` 能打开目标分支；可读取本次问题中的 handoff、计划和 `tasks/todo.md`；主工作区仍可正常打开。
- 不应测试或访问真实业务系统、ERP、鲸灵或生产服务。

## 回滚

从启动脚本删除该单一 `--allow-root` 参数并重启 CodexPro，即恢复为仅允许 `/Users/chat/claude`。
