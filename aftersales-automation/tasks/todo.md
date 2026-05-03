# 待处理问题台账（2026-05-03 更新）

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

- [x] **A4.1** 移除"ERP发货行数 vs 申请套数"错误规则 → 已替换为"发货行数 vs 采集到的包裹数"完整性校验（见 A4.6）
- [x] **A4.2** 商责关键词补全：`MERCHANT_FAULT_REASONS` 加 `'少件'`、`'缺件'`
- [x] **A4.3** 终态识别补全：加 `'已取消'`、`'用户已取消'`、`'客服-已同意'`、`'客服-已拒绝'`

### P1：流程准确性

- [x] **A4.4** 超期退货检测（补全）：售后原因=`其他`/`质量问题` + remark 含超期关键词 + 物流签收时间距今>7天 → 拒绝 ✅ 已验证（签收时间从物流文本解析，三重校验）
- [x] **A4.5** 驿站待取件判断修正：仅退款已发货 + 物流"驿站待取件" → 拒绝+拦截提醒
- [x] **A4.6** 物流采集完整性：erp-logistics-all 遍历所有ERP行读物流，infer.js 兼容多行数据，不再只采 rowIndex=0
- [x] **A4.10** 物流状态逐包裹判断：SIGNED_KEYWORDS 增加门口投递关键词（放置门口/投递门口/放门口），覆盖家门口签收场景

### P2：数据层

- [x] **A4.7** 赠品数量计算：应退总数 = 主品(afterSaleNum×subItemNum) + 赠品数量，入库总数统一比较 ✅ 已验证
  > 剩余问题：部分案例 ticket.gifts=[]（赠品未被采集到），属采集阶段 bug，非推理问题
- [x] **A4.8** 重复归档防护：processOne/reprocessOne 已有 prevExecuted 检查，已覆盖
- [x] **A4.9** 重新采集保留评价字段：collect.js 重采时继承 feedbackStatus/groundTruth

### P3：系统健壮性

- [x] **A4.11** 工单页面找不到时误报：read-ticket.js + approve.js 已加反查列表逻辑，区分"已处理"vs"详情页加载失败"
- [x] **A4.12** ERP未登录/标签页缺失自动恢复：read-logistics.js 加登录检查，navigateErp 加 recoverLogin 重试
- [x] **A4.13** 时效显示精度：UI改为总小时数保留1位小数（如38.5h），infer.js去掉"充足/紧张"定性描述

---

## Phase B：架构深度重构（Phase A 稳定后）

- [ ] **B1** Phase 2 无痕浏览器隔离（自动化脚本与手动浏览完全隔离）
- [ ] **B2** collect-schema.md 正式文档化（A1.1 已完成后在此补充完整字段说明）

---

## Claude Code 优化项目（2026-05-03 完成 Phase 0+1）

> 详见 workspace plan: `.claude/plans/shimmering-skipping-dolphin.md`

### Phase 0：语义对齐层 ✅

- [x] **P0-1** aftersales-automation/SKILL.md（6区块：DO FIRST/ENTRY MAP/CORE FLOWS/NON-STANDARD PATTERNS/FAILURE PATTERNS/PATHS）
- [x] **P0-1** product-mapping/SKILL.md（同上结构）
- [x] **P0-2** 20 个核心 lib 文件补齐 WHAT/WHERE/WHY/ENTRY 文件头
- [x] **P0-3** 防过时机制：PATHS 读时验证 + CLAUDE.md 同步铁律 + pre-commit hook

### Phase 1：CI + 流程测试 + 三刀防失效 ✅

- [x] **P1-0** 3个CLAUDE.md 加入强制入口规则（Session第一步读SKILL.md）
- [x] **P1-1** CORE FLOWS 加 function anchor，smart_search 可校验
- [x] **P1-2** test/fixtures/decision-regression.json（20条 frozen 推理场景）
- [x] **P1-3** test/flow-test.js（纯逻辑回归测试，20/20通过，7ms）
- [x] **P1-4** .github/workflows/test.yml（CI 自动跑 flow-test + pm L1）

### Phase 2（按需）：Worktree 强制规则

- [x] workspace CLAUDE.md 加 worktree 强制触发条件（≥3文件/改流程结构/涉及shared）
