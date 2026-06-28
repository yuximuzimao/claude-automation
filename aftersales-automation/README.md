# 鲸灵售后自动化

鲸灵平台（scrm.jlsupp.com）售后工单辅助系统，通过 CDP 直连 Chrome 操作鲸灵 SCRM 和快麦 ERP。当前运行在纯手动模式：旧自动扫描、自动入队和批量执行入口已停用，新 A1 逐账号扫描闭环正在重建。

## 快速启动

```bash
npm install
npm test                # 运行全量单元测试
open http://localhost:3457  # 打开由 launchd 管理的 Web 面板
```

> `scan-all.js`、旧 `/api/scan` 和批量执行链路仅保留为待迁移代码，禁止作为当前入口运行。安全账号打开必须走店铺管理按钮或 `scripts/jl-steps/open-account.js`。

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
安全打开账号 → 固定导航售后列表 → 排序/读取 → 精确打开目标工单
            → 单工单完整采集验证 → 最小整账号固定清单批次验证
            → 后端 op-queue/API 入口 + 前端 no-auto 按钮（代码已接入，未重启加载）
            → live 三标签店铺筛选 + 批量 scope 加固（代码已接入，未重启加载）
            → auto-execution journal recovery Phase 1 本地状态基础（代码已接入，未开放 CLI/API/UI）
```

旧 `scan-all.js → queue → collect → infer → auto-execute` 链路尚未完成安全迁移，不代表当前可用入口。

- **Pipeline**（`lib/server/pipeline.js`）：保留 collect → infer → execute 能力；旧 scan/auto-execute 入口停用，等待新 A1 接管
- **Op-queue**（`lib/server/op-queue.js`）：全局操作队列，串行化浏览器操作
- **CDP**（`lib/cdp.js`）：直连 Chrome port 9222，物理点击/JS eval/页面导航
- **JL session state**（`lib/jl-session-state.js`）：记录当前 SCRM tab 实际账号，避免多账号扫描后跳过必要注入
- **安全账号编排**（`lib/jl/open-account-flow.js`）：匹配账号则复用；切换时清理并复查认证 Cookie，将同一 `targetId` 交给注入步骤
- **A1 列表入口**（`scripts/jl-steps/11-prepare-after-sale-list.js`）：固定导航售后列表，不依赖首页菜单或首页弹窗
- **A1 固定清单编排**（`scripts/jl-steps/14-process-single-account-fixed-batch.js`）：业务口径已确认；2026-06-26 已验证单工单完整采集、推理和模拟写回；2026-06-26/27 已验证账号 14 茗瑞-KGOS 关闭自动执行的最小整账号固定清单批次；后端入口 `POST /api/accounts/:num/a1-fixed-batch` 已接入 `op-queue` 且默认关闭自动执行，前端单账号 no-auto 按钮代码已接入但未重启加载，auto-execution journal recovery Phase 1 已具备本地状态机/人工归档服务基础但无 CLI/API/UI，自动执行真实工单仍未交付
- **自动执行恢复账本**（`lib/server/auto-execution-journal.js`、`lib/server/auto-execution-recovery.js`）：已实现 `auto_executing/auto_executed/failed/manually_resolved`、phase 门禁和本地人工收口服务；`auto_executed` journal 即使 simulation 缺失也阻断重复自动执行。当前只用于本地安全基础，不代表已开放自动 approve/reject、CLI、API 或 UI 恢复入口。
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
| [A1 用户确认计划](docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md) | 固定清单已确认业务口径、原系统数据流要求和未闭合质量问题 |
| [A1 账号14整账号批次交接](docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md) | 账号14最小整账号批次验证、后端入口状态和仍禁止事项 |
| [Live 店铺筛选交接](docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md) | 待确认/等待重查店铺筛选、批量 scope 加固和仍禁止事项 |
| [自动执行 journal recovery 设计](docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md) | 自动执行账本状态机、人工收口规则和 Phase 1 代码边界 |
| [前端按钮加载/只读冒烟计划](docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md) | A1 no-auto 按钮加载后的只读 smoke 范围和禁止事项 |
