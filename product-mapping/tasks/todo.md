# 待处理优化项

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

## 已完成
- [x] 澜泽活动 107 SKU 全部完成 auto-match2（2026-04-22）
- [x] ERP 体验装口味错误 15 条套件子品已由人工修正（2026-04-22）
- [x] 跨项目知识共享机制建立（2026-04-22）
- [x] aftersales-automation 文档整理 + lessons.md 精简（2026-04-22）
- [x] 完整流程 5 项代码变更落地（2026-04-23）
