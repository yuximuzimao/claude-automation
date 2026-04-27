# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

## 待处理问题汇总（2026-04-22）

| 优先级 | 类型 | 内容 | 状态 |
|---|---|---|---|
| P1 | 人工操作 | 0326zp-9/0225zp-4 ERP 套件体验装口味核查 | 待人工 |
| P1 | 人工操作 | 260422-73 套件子品核查（早期宽松匹配） | 待人工 |
| P2 | 架构优化 | check.js 图片下载限活动在售范围 | 代码待改 |
| P2 | 架构优化 | sku-records.json 加 scope 字段 | 代码待改 |
| P3 | 技术验证 | el-table clearSelection() 替代 DOM click | 待独立测试 |

---

## [2026-04-22] el-table clearSelection() 待验证

**问题**：手动 click checkbox 取消勾选只更新 DOM，不更新 Vue reactive state。product type Vue emit 触发 data refresh 时，el-table 从 Vue state 恢复旧勾选，导致已选数量不对。

**待做**：独立测试 `el-table.__vue__.clearSelection()` 替代 DOM click 方案。通过后更新 auto-match2.js + 迁入 §6。

---

> 已稳定的历史教训均已迁入 `docs/INDEX.md §6`。
