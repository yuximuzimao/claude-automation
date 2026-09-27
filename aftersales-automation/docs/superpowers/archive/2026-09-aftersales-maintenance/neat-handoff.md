# 2026-09 售后维护完成交接

> 历史完成记录，仅供追溯。当前规则以 `docs/INDEX.md`、`docs/erp-query.md`、`docs/collect-schema.md`、`docs/ops-erp.md`、`SKILL.md` 和生产代码为准。

## 本轮收口内容

### 1. 「无需处理」分支样式补齐

2026-09-05 工单 `100001788353201502945` 暴露前端视觉映射缺失：业务层已经支持 `decision.action='skip'`，但 `public/style.css` 没有 `.decision-tag.skip` / `.decision-box.skip`，导致该分支与其他决策卡片样式不一致。

最终只补对应 CSS 映射，不改业务分支；长期防错规则已写入 `SKILL.md` failure pattern #36。

### 2. 悦希商品档案V2固定规格字段例外

工单 `100001788495930493676` 的商品对应表能正确得到悦希水、乳、面霜等 ERP 编码，但部分历史悦希单品无法按商品档案V2「主商家编码」找到。核对后确认以下 4 个固定编码实际登记在档案V2「规格商家编码」字段：

- `6940079096228` → `yx005` 悦希舒缓焕颜精华乳100ml
- `6940079096211` → `yx004` 悦希舒缓焕颜精粹水100ml
- `6975183893203` → `yx003` 悦希氨基酸表活焕颜洁面膏100g
- `6975183893197` → `yx002` 悦希玻色因抗皱紧致焕颜面霜50g（1.0旧款）

实现采用固定白名单，不做通用「主编码查不到再查规格编码」回退。只有这 4 个编码走「规格商家编码」查询，其余商品保持原「主商家编码」路径。

### 3. 修复查询条件残留

首轮补丁后再次重采同一工单时，悦希乳先走特殊规格字段查询，紧接着普通 2.0 面霜 `6950328262755` 走主编码查询。上一轮「规格商家编码」没有清空，导致两个条件同时存在，正常 2.0 面霜被误报 `dataList 为空`。

最终规则：

- 特殊查询：先清空主/规格两个字段，再只填「规格商家编码」。
- 普通查询：先清空可能残留的「规格商家编码」，再只填「主商家编码」。
- `6950328262755`（焕颜面霜2.0）仍是普通主编码商品，不加入白名单。

### 4. 查询键与退货核对编码分离

neat 审计时发现，特殊商品的条码型编码只负责在档案V2里定位记录；ERP 已收货明细实际使用档案返回的 `outerId`（如 `yx005`、`yx004`）进行核对。

因此特殊单品查到后保留 ERP 原始 `outerId`，并保持普通单品既有的 `subItems=[]`。严格退货证明继续按单品规则用 `title + outerId + qty=1` 构造应退项。没有把查询条码写入 `subItems.specCode`，避免普通推理按名称能匹配、严格编码门禁却不一致。

### 5. ERP Hash 路由查询参数兼容

2026-09-24 工单 `100001789395328690402` 在前置采集均正常后，连续停在 ERP 售后页导航校验。系统期望 `#/aftersale/sale_handle_next/`，页面实际为同一路由加正常上下文参数：

```text
#/aftersale/sale_handle_next/?from=trade&tid=766654801
```

旧实现完整比较 `window.location.hash`，因此把正确页面误判成导航失败。最终修复只比较 `?` 前的完整路由：同一路由允许保留查询参数，不同路由和相似前缀仍然拒绝。长期规则已写入 `docs/INDEX.md` #81 和 `docs/ops-erp.md`，实现由 `lib/erp/navigate.js` 的 `matchesErpRoute()` 统一承载。

### 6. 顺丰运单跳过百度物流补证

2026-09-25 确认顺丰物流在百度搜索中需要额外验证，无法为售后推理提供有效补证。继续打开百度页只会浪费时间，还会把无意义的验证结果记成查询失败。

最终规则：

- `SF` 开头的快递单号在创建百度标签页前直接跳过，不区分大小写。
- 候选中只有顺丰时，整次百度补证标记为“未尝试”，不生成失败记录，不触发重新推理。
- 顺丰与其他快递混合时，只查询非顺丰单号，`skippedTrackings` 保留跳过记录供审计。
- 跳过顺丰不改变鲸灵＋ERP 双源得出的原安全结论。

实现在 `lib/external-logistics-baidu.js`；业务真值已写入 `docs/flow-5.3.md`，数据字段已写入 `docs/collect-schema.md`。

### 7. 退货退款未发货赠品不再要求退回

2026-09-27 工单 `100001790128606330655` 暴露了退货退款赠品判断缺口：赠品子订单 `766627714` 在 ERP 为「待打印快递单」且没有快递单号，实际没有发出；旧 `inferRefundReturn()` 仍因存在赠品商品档案，把赠品子品无条件加入应退集合，导致主品 12 件已全部良品入库后仍被误报为赠品缺失。

最终统一为一条保守规则：

- 只有每个赠品子订单都成功查到 ERP，且全部 ERP 行都属于「待审核 / 待打印快递单 / 待发货」、完全没有快递单号，才能证明赠品未发货，并从退货退款的应退清单中排除。
- 只要赠品出现快递单号、已发货类状态，或任一赠品子订单缺少完整 ERP 搜索结果，就不能按未发货排除，继续保留原来的严格核对或人工分支。
- 未发货状态集合统一由 `lib/gift-shipment-status.js` 提供；`lib/infer.js` 的仅退款与退货退款、`lib/return-item-proof.js` 的严格证明、`lib/return-tracking-group.js` 的共用退货单汇总都复用同一判定，避免再次分叉。

### 8. 共用退货单应退规格复用普通退货归一口径

2026-09-28 工单 `100001790389913108938` 与 `100001790408060598463` 共用退货单号 `YT2594352836222`。ERP 实际有 3 条已收货记录，共 15 件良品、0 次品，和两张当前有效申请的实际销售商品完全对应；旧结果却上报“退货数量不足”。

根因不是关联组业务定义错误，而是 `lib/return-tracking-group.js` 在构造合并后的 `expectedItems` 时没有继续复用普通退货核对的两条既有规则：

- 套件里的悦希印花礼盒、印花礼袋、雪梨纸本来属于免退包装配件，普通退货核对会排除；关联组却重新计入了 3 套包装。
- 套件子品中的悦希洁面仍带查询条码 `6975183893203`，ERP 入库实际核对编码是固定映射后的 `yx003`；关联组直接按原始 `subItems.specCode` 汇总，导致洁面也被误报为 0 件。

最终采用最小修复，不改重复退货单号的当前/历史语义：

- `return-tracking-group.js` 直接复用 `EXEMPT_ACCESSORY_KEYWORDS`，主品和赠品汇总时都先排除免退包装。
- `lib/product/archive.js` 将原有 4 个悦希固定历史例外从“只判断是否特殊查询”收口为同一张查询码→ERP核对码映射，并导出 `normalizeArchiveReturnSpecCode()`；普通编码原样返回。
- 关联组汇总套件子品时统一经过上述编码归一，不做商品名称模糊匹配，也不新增通用 fallback。
- 当前业务规则已补到 `docs/flow-5.1.md`，4 个编码的唯一映射仍由 `docs/erp-query.md` 维护。

## 验证

- `node --test test/product/archive-subitems.test.js`：6/6 通过；新增用例覆盖特殊规格查询、1.0旧款、特殊→普通连续查询，以及 `yx005` 严格退货编码核对。
- 全量 `npm test` 在最终代码收口前已通过；归档前再次运行最终全量回归确认。
- `lib/` 修改均按 `/aftersales-restart` 规则在 op-queue 空闲时重启；重启不自动重新采集现有工单。
- Hash 路由修复新增正反边界测试，并在主工作区完成 `496/496` 全量回归；关键生产状态文件测试前后校验值一致。
- 服务重启后，用户对工单 `100001789395328690402` 重新采集：ERP 售后入库成功读取 1 条已收货记录，3 件均为良品，`collectErrors=[]`；推理结果为高置信 `approve`，既有自动门禁执行成功，queue 最终状态为 `auto_executed`。
- 顺丰跳过修复先通过 8 项百度物流定向测试，再通过 `499/499` 全量回归；生产缓存测试前后校验值一致。服务在 op-queue 空闲后安全重启，未自动重跑现有工单。代码提交为 `b46812f`。
- 未发货赠品修复的关键回归 `51/51`、全量回归 `513/513` 全部通过；实际工单 `100001790128606330655` 重新推理时识别 `766627714` 为「待打印快递单 + 无快递单号 → 未发货」，只核对主品 12 件并得到 `approve`。修复提交为 `d46ec3b`，合入主干后按 `/aftersales-restart` 在空闲队列下重启服务；2026-09-28 用户完成实际复测并确认成功。
- 共用退货单归一修复新增定向回归后，`test/return-tracking-group.test.js` 15/15、`test/infer/refund-return-shared-tracking.test.js` 12/12、商品档案既有测试 6/6 均通过，最终全量 `npm test` 为 `514/514`。用两张目标工单的当前生产采集数据只做本地重新计算，两张均从误报 `escalate` 变为严格核对通过的 `approve`，且仍保持 `requiresHumanReview=true`、`autoExecutionBlocked=true`、`humanTriggeredExecutionAllowed=true`；未自动执行退款。修复提交为 `be49cb8`，服务在 op-queue 空闲时从 PID `27127` 安全重启到 `34224`。随后用户实际复测确认通过。

## 当前权威入口

- 商品档案V2字段选择、4个固定例外、清场规则：`docs/erp-query.md`
- `productArchive` 返回字段与单品编码口径：`docs/collect-schema.md`
- 实现：`lib/product/archive.js`
- 回归测试：`test/product/archive-subitems.test.js`
- `skip` 视觉状态防错规则：`SKILL.md` failure pattern #36
- ERP Hash 路由匹配规则：`docs/INDEX.md` #81、`docs/ops-erp.md`
- ERP 路由实现与回归：`lib/erp/navigate.js`、`test/server/erp-scan-readiness.test.js`
- 顺丰跳过百度补证的业务规则：`docs/flow-5.3.md`
- 百度补证数据合约：`docs/collect-schema.md`
- 百度补证实现与回归：`lib/external-logistics-baidu.js`、`test/external-logistics-baidu.test.js`
- 赠品未发货的当前业务规则：`docs/INDEX.md` §3.3、`docs/flow-5.1.md`
- 赠品未发货的统一事实判定：`lib/gift-shipment-status.js`
- 共用退货单当前/历史关联语义与汇总规则：`docs/INDEX.md §3.4.1`、`docs/flow-5.1.md`
- 悦希 4 个特殊查询码与最终 ERP 核对码映射：`docs/erp-query.md`
- 退货退款应用位置：`lib/infer.js`、`lib/return-item-proof.js`、`lib/return-tracking-group.js`
- 回归测试：`test/infer/refund-return-gift-shipment.test.js`、`test/infer/refund-return-shared-tracking.test.js`、`test/return-item-proof.test.js`、`test/return-tracking-group.test.js`
