# Handoff

更新时间：2026-09-09
当前负责人：Codex（主力）/ Claude Code（低频辅助）
当前分支：main（唯一 trunk）
当前焦点：工作区存在多项目并行未提交改动，不设单一业务主线；各项目当前状态与待办以各自 `CURRENT.md` / `tasks/todo.md` 为准。本轮全局 AGENTS / Skills 指令审计已完成并归档，历史证据见 `docs/archive/2026-09-06-agents-skills-instruction-audit/`。

稳定能力：个人 Codex Skill `dispatching-workbuddy` 已完成安全派工与验证；仅可用于明确为 `non_sensitive` 的受限代码任务。权威规则、架构和验证记录见 `docs/superpowers/README.md`，严禁把它当作同一 macOS 用户下的进程级沙箱。

LKWJ 当前个人进度基线：果实 62/169；其他标签页与 2026-07-21 核对基线一致。`/api/save` 使用 ETag/If-Match 拒绝旧标签页整文件覆盖，428/409/200 路径均已在线验证。

魔兽祖达克：2026-09-07历程已同步到步骤20接取结束，本轮共享/攻略/炉石修订已完成，下一步从《猛犸的复仇》继续。唯一恢复点见 `wow-quest-route/docs/verified-routes/CURRENT.md`；此次没有修改其它地图路线。

魔兽日常：2026-09-07已记录祖达克起飞至日常结束的整轮实测，含两次死亡复活；计时证据见 `wow-quest-route/data/observations/route-timing-runs.json`。跨图经银色比武场进入时，《实战训练》可替换《爆炸油》，候选选择见 `wow-quest-route/tasks/todo.md`；不据此更改祖达克首组恢复点。

审单交接（2026-09-09）：本轮规划与资料已NEAT收口；后续GPT从 `order-review/SKILL.md` → `tasks/todo.md` / `docs/INDEX.md` → `docs/CURRENT.md` 进入。待执行计划保留在 `order-review/docs/2026-09-08-packing-simulator-plan.md`，本轮未开发页面或修改算法。阶段证据在 `order-review/docs/archive/2026-09-09-packing-simulator-planning/`；尺寸与原始活动笔记保持本地原件。

## 系统级配置（Codex 启动时注意）

- **工作区备份**：已移交 macOS launchd 管理，每周日 08:07 自动执行 `backup-workspace.sh`，默认按时间保留 8 份 `workspace-YYYYMMDD-HHMMSS-PID.tar.gz`。Codex **不需要**再调度或触发备份任务。审单案例或推荐事件异常时仍完成工作区归档，但健康状态为 `degraded`、退出码为 3；恢复排查同时查看归档内 `order-review-data/` 和 `/Users/chat/backups/order-review-health.txt`。
- **审单工具**：当前能力、验证范围和未提交工作区边界只见 `order-review/docs/CURRENT.md`，不在此重复旧测试数字或已过期的内存验收状态。
- **生图授权门禁**：所有图片生成和编辑默认只讨论，只接受用户当前消息中的一次性明确执行授权；每次调用后立即恢复讨论模式。禁止继承上一轮意图，也禁止切换到本机脚本或 CLI/API 备用生图路径。完整规则和事件归档见 `product-ad-studio/docs/INDEX.md` 与 `product-ad-studio/docs/archive/2026-07-31-image-generation-authorization.md`。
- **claude-mem**：已完全卸载（2026-07-15）。hooks 清空、插件禁用、数据已删除。Codex 无需关心 claude-mem 相关状态。
- **Codex ↔ Claude 协作**：handoff 协议（inbox.json）照常运作，不受上述变更影响。

## 协作规则

- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`

## CodexPro 固定地址（2026-07-15）

- `/Users/chat/claude` 已切换到 ngrok 账号固定 dev domain；GPT App Server URL 不再随 CodexPro 重启变化。
- 日常恢复：网络可用后在终端输入一次 `codexpro`。
- `codexpro` 当前以前台方式运行：运行它的终端需要保持开启；关闭终端会停止本地服务和 ngrok，但重新打开终端执行 `codexpro` 后仍复用同一个固定地址，GPT App 无需重建。
- 启动脚本会自动 TERM 当前用户残留的 CodexPro `dist/http.js`，但拒绝处理任何无法确认身份的 8787 端口占用者。
- 启动脚本会清除 shell 快捷函数注入的代理变量，避免 ngrok 免费 agent 触发 `ERR_NGROK_9009`，但不会修改用户的全局代理配置。
- ngrok authtoken 只保存在 ngrok 官方本机配置；CodexPro token 只保存在 `~/.codexpro` profile，文档和 Git 不记录真实值。
