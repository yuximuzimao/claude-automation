# 待处理问题台账（2026-04-28 更新）

> 按执行顺序排列。Phase A 修点，Phase B 架构重构。

---

## Phase A-0：文档引用清理 ✅

- [x] lib/ 中 6 处 `见 RULES X.X` 注释 → 已更新为 docs/ 实际路径
- [x] RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，此条目已关闭

---

## Phase A-1：脚本架构拆分（最高优先，先做）

> 当前问题：collect.js 改字段名 → infer.js 无声失败（字段 undefined → 走错默认分支）。
> 改一处影响全链路，是后续所有修复产生连锁反应的根本原因。

- [ ] **A1.1** 定义采集数据 Schema（列出 infer.js 所有读取字段，明确必填/可选，写入 `docs/collect-schema.md`）
- [ ] **A1.2** infer.js 入口加数据完整性校验（必填字段缺失 → 立即 escalate，禁止走 else 默认分支）
- [ ] **A1.3** infer.js 四个 flow 拆分为独立函数
  - `inferRefundReturn(data)` → flow-5.1 退货退款
  - `inferRefundOnly(data)` → flow-5.2/5.3 仅退款
  - `inferExchange(data)` → flow-5.4 换货
  - 每个函数只接受明确声明的参数，禁止隐式访问外层变量

---

## Phase A-2：店铺管理 UI 修复

- [ ] **A2.1** scan-all.js：写 ok 状态时覆盖整条记录（清除残留 error 字段）
- [ ] **A2.2** UI：`error` 状态账号也显示"重新登录"按钮（当前只有 expired 显示）
- [ ] **A2.3** UI：店铺管理页新增"新增店铺"按钮
- [ ] **A2.4** UI：每个账号行新增"打开店铺后台"按钮（打开鲸灵对应 URL）

---

## Phase A-3：虚假工单扫描修复

- [ ] **A3.1** 排查账号2（展宏妍）崩溃：`Cannot read properties of undefined (reading 'workOrderNum')`
- [ ] **A3.2** 确认账号12（顺链-肺腑）18个工单来源（queue存量 vs list.js误读）
- [ ] **A3.3** 修复 list.js 筛选：确保只读"待商家处理"过滤后的工单，不混入其他状态

---

## Phase A-4：判断逻辑修复

### P0：资金安全

- [ ] **A4.1** 删除"ERP主商品发货行数 vs 申请套数"比较（行数≠套数，该比较无意义且导致大量误判）
- [ ] **A4.2** 商责关键词补全：`MERCHANT_FAULT_REASONS` 加 `'少件'`、`'缺件'`
- [ ] **A4.3** 终态识别补全：加 `'已取消'`、`'用户已取消'`、`'客服-已同意'`、`'客服-已拒绝'` → 触发自动归档

### P1：流程准确性

- [ ] **A4.4** 超期退货检测：售后原因 `'其他'` + remark 含超期关键词（`未拆封`/`没拆开`） → 拒绝
- [ ] **A4.5** 驿站待取件判断修正：仅退款已发货 + 物流"驿站待取件" → 拒绝+拦截提醒（当前有误判）
- [ ] **A4.6** 物流采集完整性：ERP 发货行数 ≠ 采集到的包裹数 → escalate（不用少量包裹推断全部退回）

### P2：数据层

- [ ] **A4.7** 赠品数量计算：赠品子订单商品数单独核算，不混入主品 subItemNum
- [ ] **A4.8** 重复归档防护：processOne/reprocessOne 执行前检查历史 sim 是否已有 `executedAt`
- [ ] **A4.9** 重新采集保留评价字段：重采时 merge 原 `feedbackStatus`/`groundTruth`，不整条覆盖

---

## Phase B：架构深度重构（Phase A 稳定后）

- [ ] **B1** Phase 2 无痕浏览器隔离（自动化脚本与手动浏览完全隔离）
- [ ] **B2** collect-schema.md 正式文档化（A1.1 已完成后在此补充完整字段说明）
