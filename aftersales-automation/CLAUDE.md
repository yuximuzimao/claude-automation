# 鲸灵售后自动化

项目中文名：鲸灵售后自动化

## Session 启动（必做，按顺序）

1. **读 `SKILL.md`** — 运行时上下文入口，禁止跳过。禁止先 grep / glob / smart_search 再回来读
2. 读 `tasks/todo.md` — 确认当前待办和进度
3. 只有处理真实工单时才运行 `node cli.js list` 获取实时列表；文档、单测和静态审查不得为此主动访问平台
4. 读 `docs/INDEX.md` — 处理规则，按需加载（SKILL.md 的 DO FIRST 会告诉你看什么）

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | **每次必读**：错误处理、红线、工单路由、通用规范 |
| `docs/flow-5.1.md` | 工单类型 = 退货退款 |
| `docs/flow-5.2.md` | 工单类型 = 仅退款（未发货） |
| `docs/flow-5.3.md` | 工单类型 = 仅退款（已发货） |
| `docs/flow-5.4.md` | 工单类型 = 换货 |
| `docs/erp-query.md` | 涉及退货核验，需查商品对应表/档案V2 |
| `docs/ops-tech.md` | 技术排查总入口（再按鲸灵、ERP、测试、队列分流） |
| `docs/automation-policy.md` | 当前自动执行授权、执行前证明与统计口径 |

> 工单类型确认后只加载对应 flow 文档，不全量加载。

## 进入工作前确认（开工前过一遍，详细规则见 `docs/INDEX.md §1.2`）

- ERP 命令必须 `&&` 串行，禁止 `&` 并行
- 赠品子订单号禁止推算，必须从 `giftSubBizOrderDetailDTO.subBizOrderId` 读取
- 截图只用于上传凭证，禁止截图判断操作结果
- 鲸灵行为操作报错即停（maxRetries=0，域名自动识别）；被动等待（导航）最多重试 1 次（共执行 2 次）。风控信号 → 全局熔断持久化到 `data/circuit-breaker.json`，需人工 `node cli.js reset-circuit`
- 多账号扫描/采集/队列任一路径成功注入鲸灵账号后，必须同步 `data/current-session.json`；实际 tab 账号和缓存账号不一致会导致跳过注入、读空工单、误改 queue 状态。
- 安全切换账号必须经过 `openAccountFlow`：清理后 `verified === true` 才能注入；注入必须绑定同一个 `targetId`，随后固定导航售后列表，禁止 `Page.reload` 继承旧工单详情 URL。
- 平台拒绝原因是“工单类型 × 业务分支”的已确认枚举，禁止为了复用而跨分支统一成一个常量。推理说明与平台写入字段必须分层；安全关键分支由 `decision` 提供唯一写入值，执行层禁止被路由参数覆盖，字段缺失时 fail-closed。

## 相关项目

商品匹配核查（`../product-mapping/`）与本项目操作**同一套 ERP 和鲸灵**：

| 我需要参考 | 去哪里找 |
|-----------|---------|
| ERP 对应表/档案V2 操作规范 | `../product-mapping/docs/INDEX.md §5` |
| el-table Vue state 恢复问题（clearSelection vs DOM click） | `../product-mapping/docs/INDEX.md §6` |
| 多层嵌套 dialog 确定按钮查找（getBoundingClientRect） | `../product-mapping/docs/INDEX.md §6` |
| 对应表图片列 class 动态变化（懒加载处理方式） | `../product-mapping/docs/INDEX.md §5` |

## Git 存档规则

改动验证通过后立即 commit + push，不攒到 session 结束。
暂存：`git add lib/ cli.js server.js public/ tasks/ docs/ test/`；旧 `collect.js` / `scan-all.js` 只有明确修复 legacy 行为时单独暂存，日常 A1 入口不走它们
不提交：`data/`、`*.log`、`.server.lock`

## 代码生效铁律

**修改 `lib/` 下任何决策逻辑文件后，必须执行 `/aftersales-restart` 重启 server**。
原因：server 启动时加载模块到内存，不重启新逻辑不生效。当前定时扫描已恢复，由 `server.js` `scheduleNextScan` → `opQueue scan` 触发，并遵守账号 `scanEnabled`；真实处理入口仍由用户点击“处理工单”或队列操作触发，所有浏览器操作必须经 op-queue 串行。

触发文件清单（任一即触发）：`lib/infer.js` · `lib/constants.js` · `lib/server/pipeline.js` · `lib/server/relogin-session.js` · `lib/jl/*.js` · `lib/jl-session-state.js` · `lib/jl-account-config.js` · `lib/erp/*.js`

## 反馈洞察归档

统计页的洞察由 Claude Code / Codex 手动处理。规则或代码处理完成后，必须调用 `lib/server/data.js` 的 `markFeedbackInsighted(ids)` 给对应反馈写入 `insightedAt`，再读回确认“有具体说明且未洞察”的数量已经减少；禁止删除反馈原文，也不要为了清零后端计数批量标记没有说明的普通反馈。操作命令见 `docs/ops-tech.md §3`。

## 单元测试

| 测试 | 命令 | 何时必跑 |
|------|------|----------|
| 推理回归 | `node test/flow-test.js` | 改 `lib/infer.js` 后 |
| JL 账号/会话/重登 | `node --test test/jl/account-config.test.js test/jl/session-state.test.js test/server/relogin-session.test.js test/server/relogin-session-launcher.test.js` | 改 `lib/jl-account-config.js` / `lib/jl-session-state.js` / `lib/server/relogin-session.js` / `lib/server/routes.js` 后 |
| 全量回归 | `npm test` | 改账号切换、CDP、A1 编排或共享模块后 |

**注意**：`node --test` 不接受目录路径，必须逐文件列出。
