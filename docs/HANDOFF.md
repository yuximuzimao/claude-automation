# Handoff

更新时间：2026-07-01
当前负责人：Claude Code
当前分支：main（唯一 trunk）
当前焦点：售后核心操作已全量接入 A2 安全编排；自动执行已启用；系统正常运行

## 协作规则

- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
