# 待处理优化项

## 当前任务：模块化测试（match-one 流水线）

> 计划文件：`~/.claude/plans/peppy-dancing-mango.md`
> 测试店铺：杭州共途（不是澜泽）
> ERP 标签页锁定：`1F46BAA92728117C35DD6845CB85FB33`

### Phase 0: 前置条件
- [x] 0.1 升级 `lib/navigate.js` — session 缓存 + 自动登录恢复 + 页面轮询等待
- [x] 0.2 CDP 健康检查 + fallback 直连 9222
- [x] 0.3 结构化日志（navigate.js 已含 VERBOSE 日志）

### Phase 1: 测试基础设施
- [x] 1.1 `test/helpers/browser.js` — resetErp/resetJl + 连接锁定
- [x] 1.2 `test/helpers/fixtures.js` — 数据工厂 + 备份恢复 + assertErpState
- [x] 1.3 `test/helpers/assertions.js` — 文件/数据/日志断言
- [x] 1.4 `test/helpers/cdp-mock.js` — L1 层 mock
- [x] 1.5 `test/schemas.js` — 步骤定义
- [x] 1.6 `test/run.js` — CLI 测试运行器（--fast / step / all）

### Phase 2: L1 单元测试（不需要浏览器）
- [x] L1-safe-write: 4 用例 × 3 次 = 12/12 ✓
- [x] L1-annotate: 6 用例 × 3 次 = 18/18 ✓
- [x] L1-match-one-logic: 3 用例 × 3 次 = 9/9 ✓

### Phase 3: L2 基础设施测试（需要 Chrome）
- [x] L2-targets: 5/5 ✓（2026-04-30）
- [x] L2-cdp: 5/5 ✓（2026-04-30）
- [x] L2-navigate: 4/5 ✓（2026-04-30，1次 flaky）

### Phase 4: L2 对应表页面操作测试
- [x] L2-ensure-corr-page: 3/3 ✓（2026-04-30）
- [x] L2-read-table-rows: 3/3 ✓（2026-04-30）
- [x] L2-download-products: 1/1 ✓（2026-04-30，破坏性预检）

### Phase 5: L2 SKU 读写测试
- [x] L2-read-skus: 3/3 ✓（2026-04-30，修复搜索输入框选择器后）
- [x] L2-read-erp-codes: 3/3 ✓（2026-04-30）

### Phase 6: L2 匹配操作测试（下次从这里开始，全部重跑）
- [ ] L2-remap-single: 4 用例 × 5 次
- [ ] L2-create-suite: 5 用例 × 5 次
- [ ] L2-verify-archive: 5 用例 × 3 次

### Phase 7: L2 编排器测试
- [ ] L2-match-one: 11 用例 × 3 次

---

### 已修复的关键 bug（2026-04-30 session）
1. **搜索输入框选择器错误**：主页面搜索输入框是 `.el-input-popup-editor input`，不是 `form-item[4]`（那是下拉框）
2. **`_setMainPageSelect` 索引错误**：精确搜索=index 4，平台商家编码=index 5（不是 2/3）
3. **`readTableRows` 首行校验时机**：waitFor 只检查 `count > 0`，应等首行编码匹配
4. **已修复 5 个模块**：read-skus, read-erp-codes, ensure-corr-page, remap-sku, create-suite

### 知识库清理（2026-04-30 neat-freak）
- memory/project_km_product_mapping.md — 更新：测试店铺→杭州共途、ERP tab 锁定、Phase 0-5 进度
- docs/INDEX.md §6 — 新增搜索输入框选择器坑位
- tasks/lessons.md — 清空过期待办（已全部完成或迁入 todo.md）
- `_setMainPageSelect` 下拉框选择后未关闭 — 待修复

### ERP 页面布局（form-item 索引）
| idx | 元素 | 说明 |
|-----|------|------|
| 2 | `El-select-shop` | 店铺选择器 |
| 3 | `el-select` | 平台商品 |
| 4 | `el-select` | **精确搜索** |
| 5 | `el-select` | **平台商家编码** |
| 6 | `el-input-popup-editor` | **搜索输入框**（真正的搜索框！） |
| 7 | `el-select` | 商品状态 |
| 8 | button | 查询按钮 |
| 9 | button | 下载平台商品 |

---

### 旧任务存档（架构重构，已完成）
- [x] 1-13. 树状分支架构重构（match-one 7步闭环）全部完成

### 数据契约快查

sku-records.json 新格式：`{ stage, shopName, productCode, skus: { [platformCode]: {...} } }`

stage 状态机：`skus_read → images_done → annotated → matched → verified`

matchStatus 四态：`unmatched / matched-original / matched-ai / failed-ai`

---

## P1 人工操作
- [x] 0326zp-9 / 0225zp-4 核查完成（2026-04-22）：实际为青柑普洱味，ERP 映射无误，recognition 已修正回普洱味
- [x] 260422-73 核查完成（2026-04-22）：子品正确（美式×7+生椰×7+礼袋×2），匹配无误

## P2 架构优化
- [x] check.js 完成后自动更新 sku-records scope 字段（2026-04-22）
- [x] sku-records.json 已补全 scope 字段：107 active / 39 history（2026-04-22）
- [x] 完整流程实现（2026-04-23）：5 个变更已代码落地，等待实际测试验证

## P3 技术验证（下次会话逐步测试）

### 须逐步测试，每步单独验证后再继续

- [ ] **T1: ERP「下载平台商品」按钮**
  - 运行 `node cli.js check --shop <店铺>` 看第一步是否能找到按钮
  - 若报错"未找到按钮"→ 看错误信息中的可见元素，修改 `correspondence.js` 的 candidates 列表
  - 若找到但弹窗结构不对 → 调整弹窗选店铺/全量勾选逻辑

- [ ] **T2: check.js 报告格式验证**
  - 确认报告 JSON 包含 `recognition`、`comparisonResult`、`comparisonDetail` 字段
  - 确认 summary 包含 `recognitionDone`、`comparisonMatch`、`comparisonMismatch`

- [ ] **T3: match 命令可访问**
  - `node cli.js match --shop 澜泽 --limit 0`（limit=0 不实际操作）验证命令连通

- [ ] **T4: stop-on-error 行为验证**
  - 故意制造匹配错误（或观察首次真实错误），确认 match 立即停止而非继续

- [ ] **T5: el-table clearSelection() 方案测试**
  - 在 _sandbox/ 写独立测试脚本，验证 `el-table.__vue__.clearSelection()` 能否清除 Vue 状态
  - 通过后更新 auto-match2.js 并记录到 docs/INDEX.md §6

## 架构重构 Ticket

### TICKET: 品牌作用域隔离重构

**触发条件**：第二个品牌（非 kgos、非 hee）建档开始前，必须先完成此重构。

**当前问题**：所有品牌数据混在全局目录（`data/imgs/`、`data/sku-records.json`），品牌切换依赖人工清空。

**目标架构**：
```
data/brands/{brand}/
  imgs/              ← 该品牌 SKU 图片（隔离）
  sku-records.json   ← 该品牌 SKU 元数据
  sku-map.json       ← 货号→platformCode 映射台账
  check-report.json  ← 最新 check 快照
  ref-imgs/          ← 参考图（原 data/products/{brand}/）
```

**影响文件**：`lib/visual.js`（imgPath 函数）、`lib/check.js`（SKU_RECORDS_PATH）、`lib/correspondence.js`、所有读写 `data/imgs/` 的模块（6+ 个文件）。

**sku-map 自动生成**（Step 2 自动化）：第三个品牌建档时，同步实现从 check 报告自动生成 sku-map.json 的脚本。

---

## 已完成
- [x] 澜泽活动 107 SKU 全部完成 auto-match2（2026-04-22）
- [x] ERP 体验装口味错误 15 条套件子品已由人工修正（2026-04-22）
- [x] 跨项目知识共享机制建立（2026-04-22）
- [x] aftersales-automation 文档整理 + lessons.md 精简（2026-04-22）
- [x] 完整流程 5 项代码变更落地（2026-04-23）
