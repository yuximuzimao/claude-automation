# 2026-07-24～2026-07-25 澜泽商品匹配归档

> 这是一次实战证据归档，不是当前运行手册。当前规则以
> `docs/matching-stability.md`、`docs/INDEX.md` 和代码为准。

## 范围与结果

| 项目 | 数量 |
|---|---:|
| 活动产品 | 20 |
| 活动 SKU | 64 |
| 原已匹配 SKU | 14 |
| 本轮新匹配 SKU | 50 |
| 新匹配套件 | 41 |
| 新匹配单品 | 9 |
| 最终识图完成 | 64 |
| 最终自动比对一致 | 64 |
| 不一致 / 待比对 / 待识图 | 0 / 0 / 0 |

用户在匹配前已经确认核对页全部正确，因此匹配后以脚本自动比对为最终验收，不再要求人工重复核对。

## 本轮暴露的问题

| 现象 | 根因 | 已采取的防护 |
|---|---|---|
| `match` 因鲸灵 tab 不存在而不能启动 | CLI 按外层入口统一取两个 target，没有按动作的真实依赖拆分 | `match` 改为只解析 ERP target |
| “套件处理”点了没有菜单 | Element UI 下拉由 hover 触发，JS `.click()` 不等于真实鼠标交互 | 使用 `cdp.clickAt()`，并验证“复制为套件”出现 |
| 重跑时目标 checkbox 被反向取消 | 代码默认 checkbox 初始未选中 | 标记前清空全部展开行选择，再精确选择一个并验证数量 |
| 第二个 SKU 带入第一个 SKU 的子品 | 弹窗 `v-show` 保留 Vue `multipleSelection`，DOM 看不到隐藏选择 | `clearSelection()` + `updateCheckRows([])`，验证选择数为 0 |
| 中断后再次标记套件失败 | 第一次已经完成标记，只在配置子品阶段失败 | 识别“复制为套件”中间态并跳过重复标记 |
| 命令完成后进程长时间不退出 | ERP lock 获取后没有在批量入口释放 | CLI 用 `try/finally` 释放锁 |
| 后置核查仍要求鲸灵和平台下载 | 旧 `check` 只有完整刷新模式 | 新增 `--reuse-active --skip-download`，并校验活动范围 |
| 纯读取对应表读到 0/1 条或错误页 | 筛选重置会重建输入框，页码和旧搜索仍残留 | 重查 DOM、清搜索、回第 1 页、按总数计算页数并逐页验证 |
| 报告误报 64 个待视觉核查 | `pendingVisualReview` 统计条件错误 | 改为统计 `!recognition` |

## 为什么跑过多次仍会遇到新问题

1. ERP 是有状态的 Vue/Element UI 页面。关闭弹窗不等于清空组件内部状态。
2. 失败可能发生在写流程中间。过去的代码主要覆盖“从头成功”，没有完整描述“中断后从哪里恢复”。
3. 快速测试偏重匹配与比较的纯逻辑，无法覆盖连续两个 SKU、隐藏 Vue 状态和真实 hover 行为。
4. 套件操作分散在多个实现中，一处修复不会自动传播到所有入口。
5. ERP 前端行为会变化。2026-05-27 的搜索字段观察与本轮实测相反，历史经验必须服从当前页面证据。

stop-on-error 在本轮发挥了正确作用：每次异常都发生在最终 ERP 确认前，批量立即停止，没有把不确定状态当成功继续写。

## 验证证据

- `data/auto-match-log.json` 当轮结果：`doneCount=50`、`failedCount=0`。
- 后置 check：20 个产品全部完全匹配，64 个 SKU 全部识图完成且自动比对一致。
- 快速测试：L1-safe-write、L1-annotate、L1-match-one-logic 各 3 次，共 9/9 通过。
- 比较测试：`node --test test/compare.test.js`，3/3 通过。
- 语法检查与 `git diff --check` 通过。
- 修复提交：`67eea69 fix(product-mapping): harden live match and post-check`。

## 当轮代码落点

- 目标依赖和锁释放：`cli.js`、`lib/targets.js`
- 套件标记和恢复：`lib/auto-match2.js`、`lib/mark-suite.js`、`lib/ops/create-suite.js`
- 弹窗隐藏选择清理：`lib/copy-as-suite.js`
- 对应表筛选/分页：`lib/correspondence.js`
- 后置自动核查：`lib/check.js`
