# 工作区历史归档

本目录保存工作区级一次性分析、阶段闭合和已退出现役流程的历史材料。当前规则与当前任务不要从这里恢复，应读取实际 `AGENTS.md`、`CLAUDE.md`、各项目 `SKILL.md` / `CURRENT.md` / `tasks/todo.md`。

## 归档索引

- `2026-09-06-agents-skills-instruction-audit/` — 全局 AGENTS / Skills 自主性、批准与完成规则审计；包含最终验证摘要和历史审阅方案。
- `2026-09-13-workbuddy-governance/` — WorkBuddy 记忆、项目入口、Skill 与工作区治理收尾；记录最终架构、清理结果与冷启动验证。
- `2026-10-09-codex-ccswitch-deepseek-harness/` — DeepSeek Harness 与 CC Switch 升级、规则共享、Codex 官方账号/API 切换及 HTTP/HTTPS 连接根因归档；DeepSeek Harness 已于 2026-10-10 卸载，目录仅作历史证据。
- [2026-10-21-mac-reminders/](2026-10-21-mac-reminders/README.md) — 售后系统通知迁移、输入文件对齐小爪工作区、真机接收验证，以及跨项目提醒约定与记忆同步。
- [2026-10-23-codexpro-paged-read/](2026-10-23-codexpro-paged-read/README.md) — 大文件读取参数根因、分段读取修复、7 项回归与用户重启后的实际服务验证；本阶段已结束。
- [2026-11-01-codexpro-0302/](2026-11-01-codexpro-0302/README.md) — 0.30.2 分页补丁兼容、编号区间边界、8 项回归与实机配置核对、快捷启动请求日志，以及本轮 NEAT 审查和售后待办登记。
- [2026-11-06-review-gate-v2-handoff/](2026-11-06-review-gate-v2-handoff/README.md) — Review Gate V2 的阶段交接、三项 Important 修复、63 项回归、独立复审及最终隔离验收；当前操作规则见 `docs/review-gate/README.md`。
- [2026-11-06-review-gate-runtime-boundary/](2026-11-06-review-gate-runtime-boundary/README.md) — Review Gate 触发时点调整：开发阶段免审、首次无人监管运行完整审查、已运行项目只审查影响下一次执行的变更；含实现和回归记录。
- [2026-11-04-agent-autoloop-status-island/](2026-11-04-agent-autoloop-status-island/README.md) — Agent Autoloop 开源分析、共享桌面串行调度、无人监管自动化对抗性审查，以及将 Codex Monitor 扩展为 Status Island 的用户决定、助手建议和下一阶段设计待办。
- [2026-11-05-chatgpt-app-external-chrome/](2026-11-05-chatgpt-app-external-chrome/README.md) — ChatGPT 桌面 App 外部 Chrome Native Messaging 注册、Profile 识别修复，以及 Browser 插件读取/接管/DOM 验证；CUA 备用路径和设置页状态保留为未处理边界。
- [2026-11-06-autoloop-adapter-runtime-design/](2026-11-06-autoloop-adapter-runtime-design/README.md) — Autoloop 适配层与统一桌面调度运行模型的两阶段讨论结论、项目职责边界、队列规则及下一阶段顺序修正。
- [2026-11-09-status-island-dual-device-design/](2026-11-09-status-island-dual-device-design/README.md) — Status Island 双设备部署模型、黑苹果人工操作与 Mac mini 自动执行分工、售后登录 / Session 同步、方案 B 双向 WebSocket、心跳与自动重连、长期离线提醒及任务恢复规则。

- [2026-11-11-review-gate-concurrent-scope/](2026-11-11-review-gate-concurrent-scope/README.md) — Review Gate 无关并发范围修复：89 项回归、24 项新增用例、两项独立审查 finding 修复及最终空 findings；保留原农场 blocked 证据，不重置 Work。
- [2026-11-13-scheduling-timezone-standard/](2026-11-13-scheduling-timezone-standard/README.md) — 建立工作区统一定时任务时间规范，复用农场 datetime/zoneinfo 与 next_run_at 读回经验；核验农场现役任务，记录群聊 heartbeat 时区事故与离线边界测试。
