# Handoff

更新时间：2026-07-01
当前负责人：Claude Code
当前分支：**main**（唯一主干）
今天 commit 数：7（见下方）

## 🔴 2026-07-01 重大事故：git fast-forward merge 删除 211 个运行时数据文件

**根因**：fast-forward merge (cd555ae → ff9fe38) 时，老 main 里 data/ 文件仍被 git 追踪，目标分支里 ac377b1（5月29日）已通过 git rm 删除追踪。merge 时 git 为对齐工作目录，物理删除了磁盘上的实时数据文件。

**影响**：queue.json（1222条实时工单）、simulations.jsonl、cases.jsonl、feedback.jsonl、account-status.json 全部消失。

**恢复**：产品图片/配置从 git 恢复；queue.json 恢复到 6月8日备份（1026条）；6/9-7/1 新增数据永久丢失。

**铁律**（已写入 CLAUDE.md + lessons.md + memory）：
1. merge 前跑 `git diff --diff-filter=D <old> <new>`，删除列表含 data/ → 先备份再 merge
2. 两个分支追踪状态不一致 → 先 `git rm --cached` 对齐

## 今日 commit（7个，已全部 push）

| commit | 内容 |
|--------|------|
| `5a1dfbd` | fix: execOpenTicket 接入 openAccountFlow + readQueue 告警 |
| `e5c51cb` | docs: 事故教训写入 lessons.md + CLAUDE.md + memory |
| `d227104` | chore: lkwj/collections.json 安全取消追踪 |
| `163c441` | chore: lkwj 两个脚本恢复追踪 |
| `13f9de2` | refactor: execOpenAccount 模块化（spawnSync → 直接调用） |
| `443f4cb` | feat: 移除「生成洞察」按钮 + 周备份脚本 |
| `3278781` | fix: execOpenAccount 加 90s 超时 + 待洞察计数始终显示 |

## 代码恢复验证

- 代码文件：0 丢失
- 规则文档：全部完好（SKILL.md、INDEX.md、lessons.md 等）
- 211 个被删文件：全部从 git 恢复
- account-status.json：已重建，12 账号正常

## 系统审查

全部 5 组按钮/功能审查通过。6 个 CDP 账号切换操作点全部走 openAccountFlow 安全链路：
- execExecute（执行操作）
- execReprocessOne（采集推理）
- execReinfer（重新推理）
- execScan → processSingleAccountFixedBatch（扫描全部）
- execA1FixedBatch → processSingleAccountFixedBatch（处理工单）
- execOpenAccount（打开店铺后台，已模块化为直接调用）
- execOpenTicket（查看工单，今天修）

## 新增

- 工作区周备份：`~/backups/workspace-YYYYMMDD.tar.gz`，每周日 3:37 自动打包，只保留最新
  脚本位于 `backup-workspace.sh`，排除 product-detect、视频等大文件
- 洞察生成：改为手动（Claude Code / Codex），已移除前端按钮

## 当前分支

main = ff9fe38 + 7 commits = 3278781，已 push。data-model-restructure 保留为备份。
