# 鲸灵售后自动化

鲸灵平台（scrm.jlsupp.com）售后工单辅助系统，通过 CDP 直连 Chrome 操作鲸灵 SCRM 和快麦 ERP。定时扫描已恢复（每天 5 次），按店铺开关过滤。

## 快速启动

```bash
npm install
npm test                # 运行全量单元测试
open http://localhost:3457  # 打开由 launchd 管理的 Web 面板
```

> 店铺管理支持单店铺扫描开关（`scanEnabled`），定时扫描和手动「扫描工单」均遵守此开关。安全账号打开走店铺管理按钮或 `scripts/jl-steps/open-account.js`。

**server.js 由 launchd 管理**（`~/Library/LaunchAgents/com.heizong.aftersale-server.plist`），Mac 启动时自动拉起，崩溃自动重启；旧 `com.jl.server.plist` 已改名为 `.disabled`。手动重启用 `/aftersales-restart` skill。

```bash
# 手动重启（用 skill，不要直接 kill）
# /aftersales-restart
```

Web 面板功能：工单队列管理、推理结果确认、历史记录、统计复盘、店铺管理。
店铺管理中的重新登录会先保存 session；已保存但未单账号验证的账号显示为「未扫描」。账号状态通过“打开店铺后台”的安全编排或后续新 A1 单账号流程验证，已删除批量刷新状态功能。

## CLI 命令

```bash
node cli.js list                              # 读工单列表（≤48h 倒计时）
node cli.js read-ticket <工单号>               # 读单条工单详情
node cli.js logistics <工单号>                 # 读鲸灵物流信息
node cli.js erp-search <子订单号>              # ERP 订单搜索+状态解析
node cli.js erp-logistics [行号]              # 读 ERP 物流追踪
node cli.js erp-aftersale <退货快递单号>        # ERP 售后工单搜索
node cli.js product-match <货号> <attr1> <店铺> # ERP 商品对应表查询
node cli.js product-archive <规格编码>          # ERP 商品档案V2查询
node cli.js approve <工单号>                   # 同意退款（自动处理三层弹窗）
node cli.js reject <工单号> <原因> <详情> [图片] # 拒绝退款（含物流截图上传）
node cli.js add-note <工单号> <备注>            # 添加内部备注
node cli.js remind <工单号> <账号> <原因>        # 创建 Mac 提醒事项
node cli.js reset-circuit                        # 人工确认后清除风控熔断
```

## 架构

当前目标链路：

```text
安全打开账号 → 固定导航售后列表 → 排序/读取 48h 固定清单
            → 逐单定位工单 → 打开详情 tab → target-aware 采集
            → inferDecision → shouldAutoExecute + executionJournal 门禁
            → 命中自动执行范围则 approve/reject，否则写入待确认/等待重查
            → 写回原 queue/simulation/三标签页 → 关闭详情 tab → 账号收尾
```

legacy `collect.js` / `scan-all.js` / 旧 pipeline 文件仍保留，但不作为当前 A1/前端采集处理入口；当前扫描、重采、执行、固定清单处理统一走 op-queue 的 A1 安全链路。

- **Pipeline**（`lib/server/pipeline.js`）：保留 collect → infer → execute 的历史兼容能力；当前生产入口以 op-queue + A1 安全链路为准
- **Op-queue**（`lib/server/op-queue.js`）：全局操作队列，串行化浏览器操作
- **CDP**（`lib/cdp.js`）：直连 Chrome port 9222，物理点击/JS eval/页面导航
- **JL session state**（`lib/jl-session-state.js`）：记录当前 SCRM tab 实际账号，避免多账号扫描后跳过必要注入
- **安全账号编排**（`lib/jl/open-account-flow.js`）：匹配账号则复用；切换时清理并复查认证 Cookie，将同一 `targetId` 交给注入步骤
- **A1 列表入口**（`scripts/jl-steps/11-prepare-after-sale-list.js`）：固定导航售后列表，不依赖首页菜单或首页弹窗
- **A1/A2 固定清单编排**（`scripts/jl-steps/14-process-single-account-fixed-batch.js`）：当前生产入口为 `POST /api/accounts/:num/a1-fixed-batch` → `op-queue` → `processSingleAccountFixedBatch`。入口固定单账号 + 48h 清单；前端“处理工单”按钮只在账号 session ok 时显示，点击后二次确认。Step14 严格串行逐单处理，写回原 queue/simulation；命中 `shouldAutoExecute` 且通过 `executionJournal` 安全门时会真实 approve/reject，否则进入待确认/等待重查。
- **自动执行恢复账本**（`lib/server/auto-execution-journal.js`、`lib/server/auto-execution-recovery.js`）：`executionJournal` 已作为自动执行安全门使用，记录 `auto_executing/auto_executed/failed/manually_resolved` 和 phase，防重复执行并 fail-closed。`auto-execution-recovery` 只是本地状态收口能力，尚无外部 CLI/API/UI recovery 入口；当前实际处理中断工单通常走两条路：重新采集推理覆盖旧状态，或用户手动处理后在页面归档。归档只表示系统不再处理该工单，不代表系统知道平台真实执行结果。
- **工具**（`lib/helpers.js`）：共享工具函数（已发货快递单号提取等）
- **常量**（`lib/constants.js`）：扫描时间点、安全边际(8h)、重试上限等共享配置

## 文档

| 文档 | 说明 |
|------|------|
| [SKILL.md](SKILL.md) | AI Agent 运行时上下文入口（必读） |
| [docs/INDEX.md](docs/INDEX.md) | 处理规则、错误分级、已知坑位 |
| [docs/flow-5.1.md](docs/flow-5.1.md) | 退货退款流程 |
| [docs/flow-5.2.md](docs/flow-5.2.md) | 仅退款-未发货流程 |
| [docs/flow-5.3.md](docs/flow-5.3.md) | 仅退款-已发货（含拦截）流程 |
| [docs/flow-5.4.md](docs/flow-5.4.md) | 换货流程 |
| [docs/erp-query.md](docs/erp-query.md) | ERP 商品对应表/档案V2 操作规范 |
| [docs/ops-tech.md](docs/ops-tech.md) | ERP 操作报错/技术排查 |
| [A1 用户确认计划](docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md) | 历史确认计划，仅用于追溯固定清单口径和早期门禁；当前状态以 README/SKILL/tasks/todo 为准 |
| [A1 账号14整账号批次交接](docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md) | 历史 no-auto 验证阶段交接；当前 fixed-batch 生产入口已继续推进并运行 |
| [Live 店铺筛选交接](docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md) | 待确认/等待重查店铺筛选、批量 scope 加固和仍有效的作用域边界 |
| [自动执行 journal recovery 设计](docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md) | 自动执行账本状态机、设计期人工收口规则和 recovery 外部入口未开放边界；实际运营以重采覆盖或手动处理后归档为主 |
| [前端按钮加载/只读冒烟计划](docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md) | 历史按钮加载/只读冒烟计划；当前前端按钮已是正式“处理工单”入口 |
