# CodexPro Worktree 访问归档

**状态：** 2026-07-13 已完成；用户已通过裸 `codexpro` 快捷命令重启并确认可用。

## 最终实现

- 既有 `codexpro` 快捷函数保持不变，仍调用 `scripts/start-codexpro-full.sh`。
- 启动脚本固定进入 `/Users/chat/claude`，并只在原有启动命令后追加：

  ```bash
  --allow-root /Users/chat/.config/superpowers/worktrees
  ```

- GPT 处理具体隔离分支时，用 `open_workspace` 打开目标 worktree 的绝对路径；`open_current_workspace` 仍指向主工作区。
- `bash=full` 是用户选择的受信任本机代理模式，不是操作系统级目录沙箱。

## 本次复盘

- 先确认真实快捷入口和运行时允许根，不能仅依据 `ps` 的显示推断启动参数。
- 目录白名单需求默认保持最小差异；环境变量加固、回归测试和额外安全策略必须单独确认。
- 本机长期服务应由用户实际终端的快捷命令启动；不要由一次性代理执行环境接管其生命周期。
