# Handoff

更新时间：2026-10-30
当前负责人：Codex（主力）/ Claude Code（低频辅助）
当前分支：main（唯一 trunk）
当前焦点：无工作区级未完成交接；各项目当前状态与待办以各自`CURRENT.md` / `tasks/todo.md`为准。

审单收口（2026-10-30）：逐包复制组合公式、自动化回归和浮窗重启记录已归档到 `order-review/docs/archive/2026-10-30-package-formula-copy/neat-handoff.md`；当前能力与使用方式只见项目 `docs/CURRENT.md` / `docs/usage.md`。

库存计算（2026-10-28）：悦希账号17已按用户纠正的18+30共48SPU重算，81个现有SKU、近7天有效加购2902；rx-1已不存在的兰花油规格25件历史加购经鲸灵当前数字SKU ID核实后排除，ERP缺统计的1个规格补零。十品各扣200，33种实体商品无超分配，桌面新报表与独立XML验收指纹见 `sku-calculator/docs/archive/2026-10-28-yuexi-48-spu-recalculation/`；该结果替代旧悦希范围报告。春堂御品账号13原结果未改动，双活动历史与知识审查仍见 `sku-calculator/docs/archive/2026-10-28-yuexi-chuntang-allocation/`。现役规则见 `sku-calculator/docs/operations.md`，焕颜水乳3.0身份边界见 `order-review/docs/archive/2026-10-28-yuexi-identity-neat/`；售后及原ERP路由/选中店铺已恢复，临时标签/代理均已清理。未完成事项仅保留在各项目Todo。

KGOS账号4（2026-10-28）：库存计算已完成，37个销售SKU按本场用户决定等权分配，4档满赠因各500不足改为各300；报表已放桌面并独立核验无超分配。库存读取的末页残留问题已修复、真实201/201复验通过，售后已恢复；完整事实与指纹见 `sku-calculator/docs/archive/2026-10-28-kgos-account4-allocation/`。

提醒事项迁移已完成并经用户确认收到。跨项目接入统一从 `docs/reminders.md` 进入；阶段证据归档于 `docs/archive/2026-10-21-mac-reminders/README.md`。

CodexPro 大文件读取修复已生效并结束本阶段；现役入口见 `docs/superpowers/README.md`，问题与验证证据归档于 `docs/archive/2026-10-23-codexpro-paged-read/README.md`，无待重启或继续实施事项。

QQ经典农场辅助（2026-10-24）：已跑通并固化化肥催熟（普通肥每阶段1次，高级肥可连续使用，一键施肥状态按平台独立）、4格特殊作物精确收获链（点“可摘”星标→黑色残株→点残株→铲子→裸地）和活动种子配地。当前 QQ 为 1 个金地 2×2 森野黄金芽 + 20 格森野甜莓，库存黄金芽5/甜莓24；微信为 2 个紫晶 2×2 森野黄金芽 + 16 格森野白桃，库存黄金芽1/甜莓0/白桃92。森野白桃已确认基础12小时、1季并新增图标 seed-044。若不再施肥，两边合并下次建议 10/25 05:55 后处理。微信本轮为避开置顶 ERP 窗口临时移到屏幕左侧；实际操作必须避开 ERP 覆盖区。当前现场、下一轮计划和待办只看 `qq-classic-farm/docs/CURRENT.md` / `qq-classic-farm/tasks/todo.md`。

稳定能力：个人 Codex Skill `dispatching-workbuddy` 已完成安全派工与验证；仅可用于明确为 `non_sensitive` 的受限代码任务。权威规则、架构和验证记录见 `docs/superpowers/README.md`，严禁把它当作同一 macOS 用户下的进程级沙箱。

LKWJ 当前个人进度基线：果实 62/169；其他标签页与 2026-07-21 核对基线一致。`/api/save` 使用 ETag/If-Match 拒绝旧标签页整文件覆盖，428/409/200 路径均已在线验证。

魔兽当前状态：当前执行组为第二组兽人双手鲜血DK×5，正在继续北风苔原第二次实跑。2026-10-08 00:15已在牦牛村完成集中交接并暂停，下一步回菲兹兰克泵站执行现役Profile `step-40`，完成《修修补补》《机械副官》《击败机甲专家》。唯一真值见 `wow-quest-route/docs/verified-routes/CURRENT.md`，后续只按Journey和现场反馈修受影响任务簇。

魔兽工程收尾（2026-09-11）：赞加步骤10/13的《多头蛇之王》《猎杀恐爪》条件交付已重新物化到正式Route Atlas JSON/HTML；生成器中《赞加沼泽的植物》《枯萎的孢芽》条件语义也已收口。Python 3.13隔离环境可安装`test` extra，指定player-text pytest已通过；原`tasks/codex-handoff.md`已归档到项目`docs/archive/neat/`。

售后线下换货（2026-10-26）：开发和 NEAT 文档收口已完成，阶段证据见 [归档交接](../aftersales-automation/docs/superpowers/archive/2026-10-offline-exchange/neat-handoff.md)。现役规则从 `aftersales-automation/docs/flow-5.4.md §线下换货` 进入；后续生产观察与未完成事项只见 `aftersales-automation/tasks/todo.md`。

售后自动化统计修正（2026-10-10）：用户确认将平台售后类型“快递无物流记录”固定归入推理和统计的商责人工分支 `merchant_fault.logistics_no_record.manual`，不得继承仅退款物流候选或自动门禁；统计分支页的卡片继续以“分支条件 → 处理结果”为主，新增“平台工单类型”辅助辨认。最近30天分支统计已改为合并窗口内 `simulations.jsonl` 与 `cases.jsonl`，按工单号取最新观察记录，再用自动执行 journal 作为成功证据；旧记录缺少结构化类型时从决策步骤“工单类型”回退读取。相关代码、测试和口径见 `aftersales-automation/lib/constants.js`、`lib/infer.js`、`lib/server/after-sales-branch-history.js`、`public/app.js`、`docs/automation-policy.md`。

快递行动统一化（2026-10-11）：用户确认分支只输出结构化 `decision.courierActions`，快递行动页面统一过滤明确已退回、已签收和未知状态，按运单号去重并保留关联工单；已自动处理工单仍可展示未揽收/在途/驿站行动并标记“已自动处理”。行动类型保留 `intercept` 与 `return_wait`，取消拦截不纳入新模型；赠品进入退回链路但未全部入库不进入快递行动。初次交付漏掉时效充足的退货待入库分支，导致4张等待工单消失；已补新推理及旧记录/空数组的显示映射并重启，使用服务实际脚本和API数据核验4张明细、徽章和关联工单跳转。错误原因和强制“修改前预测、修改后实数对照”验收方法已写入 `aftersales-automation/tasks/lessons.md`、`aftersales-automation/docs/ops-testing.md`；新增回归在 `aftersales-automation/test/server/courier-actions-display.test.js`。

## 系统级配置（Codex 启动时注意）

- **工作区备份**：已移交 macOS launchd 管理，每周日 08:07 自动执行 `backup-workspace.sh`，默认只保留最新 1 份 `workspace-YYYYMMDD-HHMMSS-PID.tar.gz`，新备份成功后替换上一份。Codex **不需要**再调度或触发备份任务。审单案例或推荐事件异常时仍完成工作区归档，但健康状态为 `degraded`、退出码为 3；恢复排查同时查看归档内 `order-review-data/` 和 `/Users/chat/backups/order-review-health.txt`。
- **Codex 供应商切换**：CC Switch 的账号订阅/自定义 API 职责、切换步骤和连接排查统一见 `docs/codex-provider-switching.md`。当前自定义网关的 8080 端口只接受 HTTP；不要在未验证 TLS 的情况下把地址改成 HTTPS。DeepSeek Harness 已于 2026-10-10 卸载，历史配置只保留在 `docs/archive/2026-10-09-codex-ccswitch-deepseek-harness/`。
- **审单工具**：当前能力、验证范围和未提交工作区边界只见 `order-review/docs/CURRENT.md`，不在此重复旧测试数字或已过期的内存验收状态。
- **生图授权门禁**：所有图片生成和编辑默认只讨论，只接受用户当前消息中的一次性明确执行授权；每次调用后立即恢复讨论模式。禁止继承上一轮意图，也禁止切换到本机脚本或 CLI/API 备用生图路径。完整规则和事件归档见 `product-ad-studio/docs/INDEX.md` 与 `product-ad-studio/docs/archive/2026-07-31-image-generation-authorization.md`。
- **claude-mem**：已完全卸载（2026-07-15）。hooks 清空、插件禁用、数据已删除。Codex 无需关心 claude-mem 相关状态。
- **Codex ↔ Claude 协作**：handoff 协议（inbox.json）照常运作，不受上述变更影响。

## 协作规则

- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`

## CodexPro 固定地址（2026-07-15）

- `/Users/chat/claude` 已切换到 ngrok 账号固定 dev domain；GPT App Server URL 不再随 CodexPro 重启变化。
- 日常恢复：网络可用后在终端输入一次 `codexpro`。
- `codexpro` 当前以前台方式运行：运行它的终端需要保持开启；关闭终端会停止本地服务和 ngrok，但重新打开终端执行 `codexpro` 后仍复用同一个固定地址，GPT App 无需重建。
- 启动脚本会自动 TERM 当前用户残留的 CodexPro `dist/http.js`，但拒绝处理任何无法确认身份的 8787 端口占用者。
- 启动脚本会清除 shell 快捷函数注入的代理变量，避免 ngrok 免费 agent 触发 `ERR_NGROK_9009`，但不会修改用户的全局代理配置。
- ngrok authtoken 只保存在 ngrok 官方本机配置；CodexPro token 只保存在 `~/.codexpro` profile，文档和 Git 不记录真实值。
