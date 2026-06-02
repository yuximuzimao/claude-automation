# Git 仓库边界优化后续建议

来源：Codex  
时间：2026-05-29 23:30 +08:00  
请求：请 Claude Code 审查这份后续建议，确认是否符合用户的真实目标。

## 背景

用户的核心目标不是单纯让仓库“干净”，而是希望 AI 改坏售后系统或其他项目时，可以通过 Git 对比、定位问题、恢复文件或回档。

Claude Code 已完成一轮仓库边界优化，最新提交为：

- `ac377b1 refactor(workspace): 优化git仓库边界 — 排除运行时数据`

Codex 只读核对后的结论：

- `.gitignore` 已排除 `aftersales-automation/data/`、`product-mapping/data/imgs/`、`product-mapping/data/auto-match-log.json`、模型权重 `*.pt`、Codex 内部缓存等。
- `aftersales-automation/data/queue.json`、`product-mapping/data/auto-match-log.json`、`product-detect/yolov8s.pt` 等本地文件仍在。
- 被移出索引的运行时/采集文件不再污染普通 `git status`。
- 当前本地分支比远端 `origin/data-model-restructure` ahead 2。

## Codex 的判断

这轮优化方向正确，符合“保留 Git 作为回档和审计工具”的目标。它解决了最关键的问题：运行队列、ERP session、模型权重、采集图片等高噪音内容不再混进主历史。

但需要注意：`ac377b1` 不是一个纯粹的“只改 Git 边界”的提交。它同时包含了不少其它源码/文档/任务文件变更，例如售后逻辑、`product-detect` 脚本、`sku-calculator`、`lkwj` 等。它可以作为当前恢复点使用，但不适合作为“边界优化最小提交”的范例。

## 后续建议

1. 保留当前 `.gitignore` 方向，不回退。
2. 继续把 Git 当作 AI 修改恢复点，而不是只当代码发布仓库。
3. 后续大改前，至少执行一次明确的 checkpoint 行为：
   - 先看 `git status --short`
   - 如果当前状态值得保留，先 commit 一个恢复点
   - 不强制每次 tag；只有跨天、跨项目、风险高的大改才考虑 tag
4. 后续提交尽量按目的拆分：
   - 售后系统逻辑改动单独提交
   - 文档/规则同步单独提交
   - 数据边界或 `.gitignore` 调整单独提交
   - 商品图片/品牌参考数据迁移单独提交
5. 对当前剩余 untracked 文件继续分类：
   - `docs/codex-handoff/`、`AGENTS.md`、`docs/HANDOFF.md`：属于协作/规则文件，可考虑纳入 Git。
   - `product-mapping/data/products/` 下品牌参考图：若它们是稳定参考数据，保留进 Git；若来自批量采集且可再生成，应转为外部资产或忽略。
   - `product-detect/assets/`：如果用于训练/验证且体积可控，可保留；如果是可再生成训练素材，建议忽略或外部存储。
   - `lkwj/data/_待采集/*.csv`、`annotations.json`、`review.html`：需要 Claude 判断是业务配置、人工标注成果，还是临时采集产物。
   - `reviews/weekly`、`reviews/monthly`：如果是长期复盘资料，建议纳入 Git；否则放归档目录。
   - `transfer/`：如果已独立项目，需要确认是否作为子项目提交、子模块、还是完全从该仓库剥离。

## 对 checkpoint tag 的看法

Codex 不认为 tag 工作流必须立即上。对用户当前目标，最低成本规则是：

> 大改前先确认 Git 状态；必要时 commit 一个 checkpoint；验证后再做正式提交。

这比“每次都打 tag”更轻，用户成本更低。未来如果出现跨多天重构、售后系统高风险改动、或多 Agent 并行修改，再加 tag 规则也不迟。

## 希望 Claude 审查的问题

1. 当前 `.gitignore` 是否有误伤：例如 `aftersales-automation/data/` 全忽略后，是否会遗漏必要的脱敏 fixture 或默认示例数据？
2. `ac377b1` 混入大量非边界变更，是否需要拆分或补一个说明提交？
3. 当前剩余 untracked 文件里，哪些应进 Git，哪些应继续忽略？
4. 是否要把“AI 大改前 checkpoint”写进 `CLAUDE.md` / `AGENTS.md` 作为硬规则？
5. `transfer/` 独立后，在当前仓库里应保留什么形式的引用？

