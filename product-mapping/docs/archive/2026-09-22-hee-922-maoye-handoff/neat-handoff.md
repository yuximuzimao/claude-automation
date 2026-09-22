# 悦希 9.22 跨店铺商品匹配 — 懋业最终归档

日期：2026-09-22

## 最终结果

- 店铺：杭州懋业电子商务有限公司。
- 品牌：HEE / 悦希。
- 本轮采用与蘅圆一致的固定活动范围：48 个货号 / 94 SKU。
- 该范围是本次跨店铺活动的一次性业务范围，不是新的通用 CLI 参数或长期规则。
- 最终 check：
  - recognitionDone = 94
  - comparisonMatch = 94
  - comparisonMismatch = 0
  - comparisonPending = 0
  - pendingVisualReview = 0
  - unmatchedAwaitingMatch = 0
  - fullyMatched = 48
  - partiallyMatched = 0
  - fullyUnmatched = 0
- 最终报告时间戳：`2026-09-21T22:21:36.065Z`。报告文件按 UTC 日期命名为 `check-懋业-2026-09-21.json`，业务实际完成日期为 2026-09-22。
- 结构化完成证据见 `final-check-summary.json`。

## 范围与识图复用

蘅圆已先完成同一活动的 48 货号 / 94 SKU，并保存：
`../2026-09-21-hengyuan-hee-922/recognition-snapshot.json`。

懋业本轮没有把当前鲸灵页面的临时活动列表当成最终范围，而是按用户确认的一次性规则，
固定使用蘅圆最终 48 个 productCode。识图只按 `productCode + platformCode` 精确身份复用，
没有复制蘅圆的 ERP 匹配状态。

首次完整 check 后：

- 25 个货号已完全匹配；
- 13 个货号部分未匹配；
- 10 个货号全部未匹配；
- 已匹配 58 SKU；
- 待匹配 36 SKU；
- recognitionDone = 94；
- comparisonMatch = 58；
- comparisonMismatch = 0；
- comparisonPending = 36。

因此 36 个 pending 均是“尚无 ERP 对应关系”，不是识图异常。

## 正式匹配

用户确认后对剩余 36 SKU 执行正式 match。

最终断点日志：

- done = 36
- failed = 0

执行过程中出现过数次 fail-fast，但后续实时 ERP 回读和最终 94/94 check 证明部分报错属于
“业务写入已经成功、脚本却误判失败”：

- `Radio button not checked after click`
- 搜索返回两个候选后报 `Search result not unique`

这些现象已记录到 `tasks/todo.md` 的 remap-single 边界待办。现行处理原则仍是：
先停、读实时 ERP 状态、确认是否已写入，再决定恢复方式；不能因脚本报错直接重复写入。

## 本轮代码修正

`cli.js` 修复了普通首次 `check` 对 `--skip-download` 的参数透传。

修复前：

`node cli.js check --shop <店铺> --brand <品牌> --skip-download`

虽然命令带参数，CLI 仍只把 `brand` 传给 `runCheck()`，因此会错误触发
`readAllCorrespondence()` 和“下载平台商品”。

修复后将 `skipDownload` 明确传入 `runCheck()`。本轮懋业使用 skip-download，
没有重复下载平台商品。

本轮曾短暂尝试把固定范围做成通用 `--scope-report` / `activeProducts` 能力，
确认这是单次业务需求后已完全回退，没有留下通用接口扩张。

## ChatGPT + CodexPro 执行教训

首次长 check 曾多次错误地由 CodexPro 前台 `bash` 承载，命中工具时限后被终止。
项目原有 `docs/chatgpt-codexpro-operations.md` 已明确规定长任务应由本机 Terminal /
本地 Codex 独立运行。本轮最终改为通过短命令只负责启动本机 Terminal，由本机 Node
进程自行跑完。

这说明现有规则虽然存在，但入口分层和可见性仍不足。已在 `tasks/todo.md` 保留 P1
“重构商品匹配项目的规则文档与分层”，本次 NEAT 不提前执行该治理任务。

## 临时工具

本轮为一次性固定 48 货号范围使用过 `.ai-bridge/run-maoye-initial-check.js`。
该脚本不是稳定业务入口，任务完成后已删除，不进入项目架构。

## 仍未完成的长期事项

本次业务轮次已经结束。仍保留的项目级待办以 `tasks/todo.md` 为准，包括：

- HEE 口红 09 古堡邂逅缺独立可用视觉图；
- 长批次 ERP 锁续租/租约问题；
- 规则文档与分层治理；
- remap-single 误报成功/失败分类边界；
- 其它既有 P1/P2/P3 回归项。
