# 品牌建档 Preflight Checklist

> 开始品牌建档前，逐项确认。未通过的项目必须先处理，不能跳过。

---

## 数据隔离检查

- [ ] **data/imgs/ 是否干净？**
  - 验证：`ls data/imgs/ | wc -l` → 应为 0（或只含当前品牌图片）
  - 如有旧图片：先备份 `cp -r data/imgs data/imgs.bak.$(date +%Y%m%d)`，再清空 `rm -f data/imgs/*`

- [ ] **data/sku-records.json 是否已重置？**
  - 如果是新品牌/新店铺：删除或清空旧数据（保留 stage 字段结构即可）

- [ ] **data/products/{brand}/sku-map.json 是否已清空？**
  - 如果存在旧 sku-map：`echo '{}' > data/products/{brand}/sku-map.json`

---

## ERP 状态检查

- [ ] **Chrome 已打开 ERP tab（superboss.cc）**
  - 验证：`node cli.js targets` → erpId 有值

- [ ] **ERP 已登录**
  - 验证：navigateErp 不报登录错误

- [ ] **aftersales server 是否正在运行？**
  - 如果运行中：注意 ERP lock（product-mapping 操作 ERP 时会自动加锁）
  - 如果已停止：无需额外操作

---

## features.json 状态检查

- [ ] **data/products/{brand}/features.json 是否是该品牌的正确版本？**
  - 验证：查看 `_meta.brand` 字段是否与当前品牌一致
  - 如果是旧品牌的文件：不要覆盖，是新品牌则创建新文件

- [ ] **所有条目的 erpName 是否与 ERP 档案V2 精确一致？**
  - 执行 check 后从 archiveTitle 字段交叉验证

---

## 代码健康检查

- [ ] **querySelector("img") 取的是 td[3]（平台 SKU 图，左侧列）**
  - 已验证（2026-05-07）：`img[0]` 在 td index 3，parent class `el-image el-popover__reference`
  - 如果代码有改动：重新 inspect 验证

---

## 数据完整性门禁（建档完成后验证）

全部 7 条通过才算品牌建档完成：

| # | 验收项 | 验证方法 |
|---|--------|---------|
| 1 | ERP 活跃产品全部存在 sku-map | sku-map.json keys vs check 报告 products |
| 2 | sku-map 全部 platformCode 有图片 | 遍历 sku-map，`ls data/imgs/{platformCode}.jpg` |
| 3 | 随机 5+ 张图片人工 spot-check | Read 工具加载图片目视确认内容与名称一致 |
| 4 | features.json 产品数 = ERP 活跃产品数 | 数量对比 |
| 5 | 随机 5~10 个 SKU 实跑识图验证 | 对参考图执行识图，确认 features.json 可正确匹配 |
| 6 | 无跨品牌图片（imgs/ 只含当前品牌） | 抽查文件名对应的产品是否都属于当前品牌 |
| 7 | features.json 无 orphan 条目（每个条目有参考图） | 遍历 features.json，`ls data/products/{brand}/{name}.jpg` |

---

## 完整流程入口

详细流程见 `docs/INDEX.md §7 品牌建档 SOP`
