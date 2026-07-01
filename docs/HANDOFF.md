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

---

以下为历史积累的铁律、待办和协作规则，保留给接手者。

## 执行铁律

- 鲸灵操作报错即停绝不重试；不能真机试错；真机"找/确认/点"三步分离由用户指挥
- server 由 LaunchAgent `com.heizong.aftersale-server` 守护+单实例锁，重启用 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`，禁手动 kill+nohup（lesson #34/#55）
- 改 `lib/` 决策逻辑后必重启 server 加载；改 `lib/infer.js` 必跑 `node test/flow-test.js`
- worktree 用 `git worktree add ... <当前分支>` 手动指定基线（lesson #54）
- commit 排除 `data/`、`*.log`、`_sandbox/`；含文件增删移必同步 SKILL.md PATHS+ENTRY MAP
- **merge 前跑 `git diff --diff-filter=D <old> <new>`（2026-07-01 事故铁律）**

## 核心铁律（接手必读，血泪换来）

- **切账号禁用"退出登录"**（破坏性，让原账号服务端 session 失效）→ 改清cookie（lesson #58）
- **清cookie必须显式覆盖全 jlsupp 子域**：真凭证 JSESSIONID 在 `seller-portal.jlsupp.com/merchant`，`getCookies({})` 看不到→漏清→混账号。用 `getCookies({urls:[...]})`（lesson #58）
- **注入后禁止 Page.reload 继承旧 URL**：统一 `cdp.navigate` 到售后列表再校验店铺名
- 已登录目标账号禁止重复注入（lesson #56）
- 判"清干净"看 JSESSIONID/_us 全域清零，不数 cookie 条数
- 注入失败若报"仍未登录"且账号 session 是旧的→是 session 过期需 `jl add` 重登，不是流程 bug

## 已知坑/约束（对话里才知道，文件看不出）

- **多账号切换 = 多次登录操作，必须串行 + 间隔≥10秒**（lesson #56 风控红线）
- **每个鲸灵操作报错即停绝不重试**（不只是技术异常，可能是风控信号）
- 切账号前确认前一账号 tab 已关或确认完成
- 验证数据读实时源头（ERP页面/cli.js list），禁止分析 jsonl 历史快照

## 遗留待办

- 6 个账号(1/3/4/6/11/13)缺 phone 配置 → 重新登录不自动填手机号
- product-mapping 品牌数据重构：图片 jpg→png 迁移，品牌目录整理
- product-detect/assets/ 16MB 训练素材已从 Git 排除，后续需决定外部存储位置
- transfer/ 本地目录已从当前仓库忽略；如确认不再需要本地副本，再手动清理

## 新增协作规则

- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
