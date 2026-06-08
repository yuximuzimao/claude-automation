# Handoff

更新时间：2026-06-08
当前负责人：Codex
当前分支：data-model-restructure
当前焦点：工作区按项目拆分整理中；lkwj 已提交（果实143/任务1882/异色38，其中34条异色课题纳入任务，4个通行证异色无捕捉课题）；codex-monitor 项目推断误分类和 UI 刷新性能修复已完成验证

## 已完成
- codex-monitor 项目推断误分类已修复（2026-06-04）：
  - `reader_common.infer_project_from_handle()` 改为按事件类型加权投票，跳过 Codex `function_call_output`、`function_call`、`token_count`
  - 默认扫描窗口从 100 行提高到 200 行
  - 已补 `tests/test_reader_common.py` 覆盖工具输出路径噪声、用户消息权重、Claude Code 格式和边界场景
  - 验证：`python3 -m unittest discover -s tests -v` 40/40 通过，`python3 -m compileall app tests` 通过
- Codex 已审查 `codex-monitor` 项目推断误分类修复方案（2026-06-04）：
  - 请求文件：`docs/codex-handoff/codex-monitor-inference-fix-review.md`
  - 回复文件：`docs/codex-handoff/codex-monitor-inference-fix-review-response.md`
  - 收件箱：`docs/codex-handoff/inbox.json` 中 `2026-06-04-codex-monitor-inference-fix` 已移入 `processed`
  - 结论：方案方向通过；实施时需补 `reader_common` 回归测试，并建议将 `max_lines` 从 100 提高到 200
- Codex 已按用户原话重写 `lkwj` 数据修正计划审计回复（2026-06-02）：
  - 回复文件：`docs/codex-handoff/lkwj-data-plan-review-response.md`
  - 收件箱：`docs/codex-handoff/inbox.json` 中 `2026-06-02-lkwj-plan-review-response` 已移入 `processed`
  - 历史口径：当时任务只能来自 `课题进度` sheet 并排除 `异色`；2026-06-08 游戏更新后已局部覆盖为 `课题进度` 中 34 条 `异色` 行导入 `capture_shiny`，总任务数 1882
- `lkwj/SKILL.md` 与 `lkwj/docs/REVIEW_CHECKLIST.md` 已同步 fruit 任务口径：精灵果实课题任务为 96 条；果实图鉴是家族级记录，另算
- OpenClaw 已确认卸载并清理残留：`/Users/chat/.openclaw` 删除，`/Users/chat/.zshrc` 不再引用 OpenClaw 补全，登录 zsh 验证无报错
- Git 仓库边界优化：.gitignore 精确排除运行时数据，24 个运行时文件从索引移除（ac377b1）
- Codex ↔ Claude Code 双向协作收件箱协议落地（61473a3）
  - `docs/codex-handoff/` — 收件箱目录
  - `scripts/codex-inbox-check.cjs` — SessionStart hook 脚本
  - `~/.claude/settings.json` — hook 已注册
  - AGENTS.md 和 CLAUDE.md 已同步协议
- Codex Git 后续建议已审查回复（approved-with-notes，详见 `docs/codex-handoff/archive/2026-06-01/workspace-git-review-response.md`）
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
  - 回复文件：`docs/codex-handoff/archive/2026-06-01/codex-monitor-review-response.md`
  - 结论：方向批准，3 处必须修正（rate_limits 路径 / Codex token 字段 / Claude Code 多模型）
  - 用户决策：Python + tkinter 批准，视觉风格改为浅色（推翻 Codex 原深色方案）
  - 执行许可：修正 3 处后可开始阶段 0 + 阶段 1
- 线上仓库已同步：`data-model-restructure` 已推送到 `origin/data-model-restructure`
- product-detect 生成器已改为 KGOS 白底业务图规则（2026-05-31）：
  - `scripts/generate.py` 支持 `--profile train|business-val`
  - 训练场景固定为 20% 单品、35% 混放无遮挡、45% 混放遮挡
  - 遮挡后按最终可见 alpha mask 写 bbox，可见面积 <35% 的目标不写 label
  - `scripts/verify.py` 可用 `--dataset kgos_business_val --split val` 抽查业务验收集
  - 已新增 `tests/test_generate.py` 覆盖生成规则与 business-val 输出
- product-detect 新规则正式数据集已生成并读回验证（2026-06-01）：
  - `datasets/kgos/`：3400 train + 600 val
  - `datasets/kgos_business_val/`：600 val
  - 文件数、label 数、label 坐标范围、白底角点抽样、overlay smoke 均通过
  - 弱项类实例数相对普通类平均倍数：黑咖体验装 3.22x、酵素4.0体验装 3.54x、腰围卡尺 3.13x、冰霸杯 2.73x、KGO手提袋 2.72x
- product-detect 第 6 轮训练已由 Claude Code 启动并经 Codex 复核（2026-06-01 00:49）：
  - PID: 47371，命令：`python -u /tmp/kgos_train6_launcher.py`
  - 日志: `product-detect/runs/kgos_train6.log`
  - 输出目录: `product-detect/runs/kgos_yolov8s_train6/`
  - 日志已进入 epoch 1；`runs/kgos_yolov8s/weights/best.pt` 时间戳仍为 2026-05-31 19:13，旧第 5 轮未覆盖
  - 按 2026-06-01 00:52 日志速度估算 65-72 小时，预计 2026-06-03 晚至 2026-06-04 凌晨完成
  - 训练效果验收重点：默认 val 可小幅低于 train5，但 business-val 与真实白底混放图必须改善弱项 Recall、mAP50-95 和漏检率
- Codex Monitor 第一版已封板（2026-06-02）：
  - 功能范围：本地 Codex/Claude JSONL 读取、近 30 天聚合、Top 项目、tkinter 浮窗、折叠态、窗口位置持久化、macOS `.app` wrapper、LaunchAgent plist 生成、watchdog/轮询刷新 fallback
  - 用户确认：第一版可以封板；“本月”改“近 30 天”为用户确认口径
  - 验证：`python3.13 -m unittest discover -s tests -v` 27/27 通过，`python3.13 -m compileall app tests` 通过，`python3.13 main.py --smoke-aggregate` 通过
  - 协作材料归档：`docs/codex-handoff/archive/2026-06-02-codex-monitor-v1/`
- 工作区 Git 整理已完成（2026-06-02）：
  - `/Users/chat/claude` 已拆分并推送 5 个提交：product-detect 生成器、lkwj 核对说明、项目入口名、reviews 回顾索引、AGENTS memory context
  - 全局 Git ignore 已新增 `/Users/chat/.config/git/ignore`，排除 `.DS_Store`、`.codex-marketplace-install.json`、`.qclaw/`
  - `qclaw` 工作区仅做本地忽略，不删除内容
  - `.cc-switch/skills/web-access` 新增 CDP `/key` 键盘事件端点；原上游 `eze-is/web-access` 当前账号无写权限，已备份到 `yuximuzimao/claude-automation` 的 `backup/web-access-cdp-key-endpoint` 分支
  - 本地恢复文件：`/Users/chat/git-backups/0001-feat-cdp-add-key-dispatch-endpoint.patch`、`/Users/chat/git-backups/web-access-f2cac3b.bundle`

## 未完成
- Codex 未执行售后系统重启；如需要线上 server 立刻加载新 `lib/` 逻辑，仍需手动运行 `/aftersales-restart`
- product-mapping 品牌数据重构：图片 jpg→png 迁移，品牌目录整理
- product-detect/assets/ 16MB 训练素材已从 Git 排除，后续需决定外部存储位置
- product-detect 下一步：等待第 6 轮训练完成，并同时评估默认 val 与 `datasets/kgos_business_val/`；重点类为黑咖体验装、酵素4.0体验装、腰围卡尺、冰霸杯、KGO手提袋
- transfer/ 本地目录已从当前仓库忽略；如确认不再需要本地副本，再手动清理

## 新增协作规则
- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
