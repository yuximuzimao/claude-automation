# Handoff

更新时间：2026-05-31 23:15
当前负责人：Codex（按审计修正后开始实现）
当前分支：data-model-restructure
当前焦点：Codex Monitor 阶段 0 + 阶段 1 实现（已收到 Claude Code 正式审计）

## 已完成
- Git 仓库边界优化：.gitignore 精确排除运行时数据，24 个运行时文件从索引移除（ac377b1）
- Codex ↔ Claude Code 双向协作收件箱协议落地（61473a3）
  - `docs/codex-handoff/` — 收件箱目录
  - `scripts/codex-inbox-check.cjs` — SessionStart hook 脚本
  - `~/.claude/settings.json` — hook 已注册
  - AGENTS.md 和 CLAUDE.md 已同步协议
- Codex Git 后续建议已审查回复（approved-with-notes，详见 `docs/codex-handoff/workspace-git-review-response.md`）
- 售后物流弹窗关闭超时容错已提交（09978b1）
- 剩余仓库资产分类已提交（ee356b2）
  - 纳入：品牌参考图、lkwj 标注成果、复盘资料、Claude 审查回复
  - 忽略：product-detect/assets、lkwj WIP CSV、product-mapping reports/visual-verdicts、return-inbound/input.html、sku-calculator/data、transfer/
- Codex handoff #1 已处理：快递行动退货待入库分类改用结构化字段判断（bf20ff0）
  - `public/app.js` 新增 `isReturnWaitingAction()` helper
  - 两处调用点（loadActionBadge + loadActionList）已统一
- 重启流程规则已同步：`/aftersales-restart` 只报告状态，不自动重跑；是否重采由用户手动选择
- 售后系统未提交改动已收尾验证：
  - `executedAt` 不再阻止 live 工单重新入队或重处理；仅保留自动执行防重复边界
  - flow-5.3 `INTERCEPT_TIMEOUT` 用户可见拒绝原因改为固定平台模板
  - 取消类工单测试口径已同步为 `wait_archive`
  - `npm test` 结果：44/44 通过
- Codex Monitor 计划 Claude Code 正式审计完成（2026-05-31 23:15）：
  - 回复文件：`docs/codex-handoff/codex-monitor-review-response.md`
  - 结论：方向批准，3 处必须修正（rate_limits 路径 / Codex token 字段 / Claude Code 多模型）
  - 用户决策：Python + tkinter 批准，视觉风格改为浅色（推翻 Codex 原深色方案）
  - 执行许可：修正 3 处后可开始阶段 0 + 阶段 1
- 线上仓库已同步：`data-model-restructure` 已推送到 `origin/data-model-restructure`

## 未完成
- Codex 未执行售后系统重启；如需要线上 server 立刻加载新 `lib/` 逻辑，仍需手动运行 `/aftersales-restart`
- Codex Monitor：Codex 需按审计修正 3 处后，开始阶段 0（项目初始化）+ 阶段 1（reader_codex.py）
- product-mapping 品牌数据重构：图片 jpg→png 迁移，品牌目录整理
- product-detect/assets/ 16MB 训练素材已从 Git 排除，后续需决定外部存储位置
- transfer/ 本地目录已从当前仓库忽略；如确认不再需要本地副本，再手动清理

## 新增协作规则
- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
