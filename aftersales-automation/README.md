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

Web 面板功能：工单队列管理、推理结果确认、退货入库、历史记录、统计复盘、店铺管理。
店铺管理中的「新增店铺」和「重新登录」都会在登录完成后显示「确认保存/取消」；首次新增保存会从认证数据初始化手机号，后续重新登录只保留已有手机号。确认保存成功后账号标为正常；批量刷新状态功能已删除。

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
node cli.js remind <工单号> <账号> <原因>        # 快捷指令创建5分钟后提醒的待办
node cli.js reset-circuit                        # 人工确认后清除风控熔断
```

## 架构

当前目标链路：

```text
安全打开账号 → 固定导航售后列表 → 排序校验（瞬时乱序仅刷新一次）/读取 48h 固定清单
            → 逐单定位工单 → 打开详情 tab → target-aware 采集
            → inferDecision → 平台阶段观察覆盖 → shouldAutoExecute + executionJournal 门禁
            → 命中已授权最小案例则自动 approve，否则写入待确认/等待重查
            → 写回原 queue/simulation/三标签页 → 关闭详情 tab → 账号收尾
```

legacy `collect.js` / `scan-all.js` / 旧 pipeline 文件仍保留，但不作为当前 A1/前端采集处理入口；当前扫描、重采、执行、固定清单处理统一走 op-queue 的 A1 安全链路。

- **Pipeline**（`lib/server/pipeline.js`）：保留 collect → infer → execute 的历史兼容能力；当前生产入口以 op-queue + A1 安全链路为准
- **Op-queue**（`lib/server/op-queue.js`）：全局操作队列，串行化浏览器操作
- **CDP**（`lib/cdp.js`）：直连 Chrome port 9222，物理点击/JS eval/页面导航
- **JL session state**（`lib/jl-session-state.js`）：记录当前 SCRM tab 实际账号，避免多账号扫描后跳过必要注入
- **安全账号编排**（`lib/jl/open-account-flow.js`）：匹配账号则复用；切换时清理并复查认证 Cookie，将同一 `targetId` 交给注入步骤
- **A1 列表入口**（`scripts/jl-steps/11-prepare-after-sale-list.js`）：固定导航售后列表，不依赖首页菜单或首页弹窗；排序值正确但列表乱序时，只等待 2 秒并刷新当前列表一次，重新就绪后复核，不重复点击排序
- **A1/A2 固定清单编排**（`scripts/jl-steps/14-process-single-account-fixed-batch.js`）：当前生产入口为 `POST /api/accounts/:num/a1-fixed-batch` → `op-queue` → `processSingleAccountFixedBatch`。入口固定单账号 + 48h 清单；前端“处理工单”按钮只在账号 session ok 时显示，点击后二次确认。Step14 严格串行逐单处理，写回原 queue/simulation；当前只有命中 `shouldAutoExecute` 且通过 `executionJournal` 安全门的已授权同意分支会真实 approve，其余进入待确认/等待重查。
- **平台阶段观察**（`lib/after-sales-platform-stage.js`）：所有 48 小时工单保存售后列表原始阶段。当前只有“换货＋商家-待商家二次发货”覆盖为“无需处理、人工确认后归档”；不会执行平台按钮或写备注。同工单同阶段确认后只刷新观察时间，阶段变化才重新进入待确认。
- **已授权自动分支**：授权粒度与统计复盘中的最小 `caseId` 一致，不按单号或粗场景放开。当前开放三个分支：七天无理由（不喜欢/不合适）的退货退款严格精确退回；多拍/拍错/不想要的仅退款主品赠品全部无单号未发货；同原因仅退款中全部运单明确未揽收或已退回。三者执行前都按 [当前自动处理政策](docs/automation-policy.md) 重新证明事实。
- **人工确认执行边界**：换货及商责分支始终设置 `requiresHumanReview + autoExecutionBlocked`，不会进入扫描中的无人自动执行。退回规格、数量、良次品严格一致并给出明确 approve/reject 动作时，人工核对后仍可点击单笔“执行操作”或主动发起批量执行；换货由 `execute-decision.js` 精确分派到“同意换货/拒绝换货”，找不到对应类型按钮即停止，不会借用退款按钮。
- **自动执行恢复账本**（`lib/server/auto-execution-journal.js`、`lib/server/auto-execution-recovery.js`）：`executionJournal` 已作为自动执行安全门使用，记录 `auto_executing/auto_executed/failed/manually_resolved` 和 phase，防重复执行并 fail-closed。`auto-execution-recovery` 只是本地状态收口能力，尚无外部 CLI/API/UI recovery 入口；当前实际处理中断工单通常走两条路：重新采集推理覆盖旧状态，或用户手动处理后在页面归档。归档只表示系统不再处理该工单，不代表系统知道平台真实执行结果。
- **工具**（`lib/helpers.js`）：共享工具函数（已发货快递单号提取等）
- **常量**（`lib/constants.js`）：扫描时间点、安全边际(8h)、重试上限等共享配置

统计页的售后分支按“已授权自动 → 可评估自动化 → 仅人工”展示。只进入采集和归类完整的固定分支；资料缺失、未登记等异常历史仍保留在原始记录中，但不参与自动化评估。“执行操作”“手动归档”“确认无需处理”分别计数，自动处理不混入前两项。历史会在打开页面、切回页面或收到现有实时事件时重新读取，无需人工定期更新，也不会根据次数自动开放权限。

### 反馈洞察闭环

统计页的“待洞察反馈”只展示填写了具体说明、且尚未写入 `insightedAt` 的反馈。洞察由 Claude Code / Codex 手动分析；规则或代码处理完成后，必须使用 `lib/server/data.js` 的 `markFeedbackInsighted(ids)` 标记对应反馈，并读回确认页面可见待洞察数量已经减少。该操作只增加归档时间，不删除反馈原文或工单关联。具体命令见 [docs/ops-tech.md](docs/ops-tech.md#3-反馈洞察归档)。

## 文档

| 文档 | 说明 |
|------|------|
| [SKILL.md](SKILL.md) | AI Agent 运行时上下文入口（必读） |
| [docs/INDEX.md](docs/INDEX.md) | 处理规则、错误分级、已知坑位 |
| [docs/automation-policy.md](docs/automation-policy.md) | 当前自动处理授权、执行前证明与统计口径 |
| [docs/flow-5.1.md](docs/flow-5.1.md) | 退货退款流程 |
| [docs/flow-5.2.md](docs/flow-5.2.md) | 仅退款-未发货流程 |
| [docs/flow-5.3.md](docs/flow-5.3.md) | 仅退款-已发货（含拦截）流程 |
| [docs/flow-5.4.md](docs/flow-5.4.md) | 换货流程 |
| [docs/collect-schema.md](docs/collect-schema.md) | queue/simulation 采集字段与平台阶段数据合约 |
| [docs/erp-query.md](docs/erp-query.md) | ERP 商品对应表/档案V2 操作规范 |
| [docs/ops-tech.md](docs/ops-tech.md) | 技术排查总入口与常见问题速查 |
| [docs/ops-jingling.md](docs/ops-jingling.md) | 鲸灵页面、CDP、备注与账号 Session |
| [docs/ops-erp.md](docs/ops-erp.md) | ERP 导航、登录恢复、物流弹窗与凭证上传 |
| [docs/ops-testing.md](docs/ops-testing.md) | CLI 与采集链路的分步测试规范 |
| [docs/ops-queue.md](docs/ops-queue.md) | 队列停止恢复、验证与定时扫描状态窗 |
| [历史设计归档](docs/superpowers/archive/README.md) | 已完成设计、计划与阶段交接，仅供追溯，不作为当前实施依据 |
