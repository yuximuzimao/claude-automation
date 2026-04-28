# 待处理问题台账（2026-04-28 更新）

> 按执行顺序排列。Phase A 修点，Phase B 架构重构。

---

## Phase A-0：文档引用清理 ✅

- [x] lib/ 中 6 处 `见 RULES X.X` 注释 → 已更新为 docs/ 实际路径
- [x] RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，此条目已关闭

---

## Phase A-1：脚本架构拆分 ✅

- [x] **A1.1** 定义采集数据 Schema → `docs/collect-schema.md`
- [x] **A1.2** infer.js 入口加数据完整性校验（validateCollectedData）
- [x] **A1.3** infer.js 四个 flow 拆分为独立函数（inferRefundReturn / inferRefundOnly）

---

## Phase A-2：店铺管理 UI 修复 ✅

- [x] **A2.1** scan-all.js：写 ok 状态时整条覆盖（清除残留 error 字段）
- [x] **A2.2** UI：`error` 状态账号也显示"重新登录"按钮
- [x] **A2.3** UI：店铺管理页新增"新增店铺"按钮
- [x] **A2.4** UI：每个账号行新增"打开店铺后台"按钮（调用 jl <num> 打开鲸灵）

---

## Phase A-3：虚假工单扫描修复

- [x] **A3.1** 排查账号2（展宏妍）崩溃：防御性修复 `out.data.urgent` undefined crash
- [x] **A3.2** 账号12顺链18个工单：queue 现已全部 done，A3.3 修复后可防止再发生
- [x] **A3.3** 修复 list.js 筛选：读工单前先点击"待商家处理"筛选标签

> 并发竞争根因（A3.1）：两个批次同时扫同账号，cli.js 通过 CDP 接收到脏数据导致 out.data undefined；防御性修复已加；待实际扫描验证无复发

---

## Phase A-4：判断逻辑修复

### P0：资金安全

- [x] **A4.1** "ERP主商品发货行数 vs 申请套数"比较 → 架构重构时已自然消除
- [x] **A4.2** 商责关键词补全：`MERCHANT_FAULT_REASONS` 加 `'少件'`、`'缺件'`
- [x] **A4.3** 终态识别补全：加 `'已取消'`、`'用户已取消'`、`'客服-已同意'`、`'客服-已拒绝'`

### P1：流程准确性

- [x] **A4.4** 超期退货检测：售后原因 `'其他'` + remark 含超期关键词（`未拆封`/`没拆开`）→ 拒绝
- [x] **A4.5** 驿站待取件判断修正：仅退款已发货 + 物流"驿站待取件" → 拒绝+拦截提醒
- [x] **A4.6** 物流采集完整性：ERP 发货行数 ≠ 采集到的包裹数 → escalate（已在重构时实现）

### P2：数据层

- [ ] **A4.7** 赠品数量计算：赠品子订单商品数单独核算，不混入主品 subItemNum
  > 复杂度高，需真实案例验证，暂缓
- [x] **A4.8** 重复归档防护：processOne/reprocessOne 已有 prevExecuted 检查，已覆盖
- [x] **A4.9** 重新采集保留评价字段：collect.js 重采时继承 feedbackStatus/groundTruth

---

## Phase B：架构深度重构（Phase A 稳定后）

- [ ] **B1** Phase 2 无痕浏览器隔离（自动化脚本与手动浏览完全隔离）
- [ ] **B2** collect-schema.md 正式文档化（A1.1 已完成后在此补充完整字段说明）
