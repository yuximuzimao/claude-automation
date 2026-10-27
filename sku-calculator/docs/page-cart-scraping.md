# 鲸灵页面加购数据抓取

适用于鲸灵「商品数据」页无法导出 Excel、但用户已经打开正确商家页面的场景。目标是生成与 `parse` 后相同语义的 `data/cart-adds.json`，再进入 ERP 查询流程。

## 开始前确认

1. 只读取用户已打开的 `scrm.jlsupp.com/.../dataCenter/goodsDetail` 页面，不切换账号或注入登录态。
2. 确认当前商家名称和商家 ID；商家 ID 写入 `_meta.supplierId` 和每条 SKU。
3. 确认视图为「SKU 明细」，并记录当前时间范围，如「今日」「近7天」「近30天」。不要擅自改成别的范围。
4. 先检查实际 DOM 表结构，再写提取逻辑。Element UI 可能把商品列和统计列拆到多个并行 `<table>`，不能假设一个 `tr` 包含全部字段。

## 读取规则

### 用户要求保持页面不动时

先检查可见 `.goods-detail-list` 的 Vue 数据及原查询方法。2026-10-27实测：`subModuleType=8` 为SKU明细，记录含独立 `specification` 和SKU ID；同一SPU可返回多条不同规格，不能因页面同时显示“SPU明细”文字而误判视图。

当原 `toSearch` 方法仅把结果写入 `this.tableList` / `this.pagination.totalCount` 时，可在隔离对象上复用该方法：复制当前筛选、时间与排序，使用自己的分页和结果容器，不调用真实组件的翻页、搜索或视图切换方法。读取后必须验证返回行数等于总数、SKU ID唯一，并对比真实组件的页码、筛选、时间、排序和当前行ID，确认完全未变。查询失败即停，不重复尝试。

2026-10-27同条件一次读取76条时，`pageSize=100`有效。该数值只是已验证的本次页面能力，不作为其他页面的固定上限。用户限定链接范围时，统计页缺失的链接或规格仍须从当次ERP对应表核实后补零；不能只处理出现过加购的规格。

### 常规分页读取

- 先读分页总数，用 `总条数 ÷ 每页条数` 推算总页数；最后一页的下一页按钮不一定禁用。
- 每页分别定位商品表（商品名称、货号）和 SKU 统计表（规格、加购人数、加购件数、支付件数、支付订单数）。
- 两张并行表按当前页行序一一配对；每页必须验证行数相同。
- 翻页后等待活动页码和表格内容都更新，再读取；不能只看到页码变化就立即取旧行。
- 规格名去掉分号后的平台后缀，例如 `果冻*5盒;KGOS` 保存为 `果冻*5盒`。
- `cartAddCount` 使用「加购件数」，不是「加购人数」。
- `paidItems > 0` 的 SKU 从本轮加购输入剔除，并写入 `_meta.excludedPaidItems` 留痕。
- 完成后恢复用户原来的页码，不关闭或导航用户标签页。

## `cart-adds.json` 契约

```json
{
  "_meta": {
    "sourceFile": "鲸灵商品数据页（SKU明细）",
    "sourceUrl": "https://scrm.jlsupp.com/.../goodsDetail",
    "parsedAt": "ISO时间",
    "dateRange": "近7天",
    "totalSkus": 50,
    "withCartData": 50,
    "supplierId": "43011",
    "excludedPaidItems": [],
    "note": "加购数据从鲸灵SKU明细页读取"
  },
  "skus": [
    {
      "key": "货号::规格名",
      "huohao": "货号",
      "skuName": "规格名",
      "productName": "商品名称",
      "cartAddCount": 100,
      "cartAddPeople": 90,
      "paidItems": 0,
      "paidOrders": 0,
      "skuId": null,
      "spuId": null,
      "supplierId": "43011"
    }
  ]
}
```

## 写入后验证

- 抓取总行数 = 页面显示总条数；
- `skus.length = _meta.totalSkus`；
- `key` 全部唯一；
- 每条 `supplierId` 与 `_meta.supplierId` 一致；
- `cartAddCount`、`cartAddPeople`、`paidItems` 都是非负数字；
- `excludedPaidItems` 与原始页面中 `paidItems > 0` 的行完全对应；
- 读回文件后再运行 `resolve-components`，匹配不足 100% 时停止，不手工忽略。

页面结构变化时先重新检查所有表头和首行单元格；不要沿用历史 tbody 下标硬读。
