# collect.js 采集数据 Schema（接口合约）

> collect.js 与 infer.js 之间的唯一约定。
> **变更任一字段必须同步更新本文档和 infer.js 中对应读取路径。**

---

## 顶层结构（`sim.collectedData`）

```js
{
  ticket:         Object | null,   // 必填（read-ticket 失败时为 null，infer 会 escalate）
  erpSearch:      Object | null,   // 仅退款必填；退货退款不需要
  erpLogistics:   Object | null,   // 可选，仅退款-已发货补充物流源
  logistics:      Object | null,   // 可选，鲸灵发货物流
  erpAftersale:   Object | null,   // 退货退款必填（有 returnTracking 时）
  productMatch:   Object | null,   // 可选，商品对应表结果
  productArchive: Object | null,   // 可选，商品档案V2
  giftErpSearch:  Object | null,   // 可选，赠品 ERP 搜索结果
  intercepted:    Object | null,   // 可选，已拦截记录
  collectErrors:  string[],        // 必填（可为空数组），各步骤错误信息
}
```

---

## `ticket` 字段（read-ticket 采集）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `workOrderStatus` | string | 是 | 工单状态，如"处理中"/"已退款"/"用户已取消" |
| `afterSaleReason` | string | 是 | 售后原因，如"多拍/拍错/不想要"/"商品漏发" |
| `buyerRemark` | string | 否 | 买家售后说明 |
| `images` | array | 否 | 买家上传图片列表 |
| `returnTracking` | string | 否 | 退货快递单号（退货退款类型时有值） |
| `returnTrackingMultiUse` | boolean | 否 | 退货快递是否被多个工单共用 |
| `returnTrackingUsedBy` | string[] | 否 | 共用该快递的其他工单号列表 |
| `subOrders` | array | 是 | 子订单列表（至少1条） |
| `subOrders[].id` | string | 是 | 子订单号（纯数字） |
| `subOrders[].sku` | string | 否 | 商品货号 |
| `subOrders[].attr1` | string | 否 | 规格属性（颜色/尺寸等） |
| `subOrders[].afterSaleNum` | number | 是 | 申请售后数量（套数） |
| `gifts` | array | 否 | 赠品子订单列表 |
| `gifts[].id` | string | 是 | 赠品子订单号 |

---

## `erpSearch` / `giftErpSearch` 字段（erp-search 采集）

```js
{
  rows: {
    rows: [
      {
        status:    string,   // "卖家已发货"/"交易成功"/"待审核"/"待打印快递单"/"待发货"
        tracking:  string,   // 快递单号（可选）
        trackings: string[], // 多快递单号列表（可选）
      }
    ]
  }
}
```

---

## `erpAftersale` 字段（erp-aftersale 采集）

```js
{
  rows: [
    {
      goodsStatus: string,   // "卖家已收到退货"/"在途"等
      items: [
        {
          name:    string,   // 商品名称
          qtyGood: string,   // 良品数量（字符串，需 parseInt）
          qtyBad:  string,   // 次品数量（字符串，需 parseInt）
        }
      ]
    }
  ]
}
```

---

## `logistics` 字段（鲸灵物流，logistics 采集）

```js
{
  packages: [
    {
      num:  string,  // 快递单号
      text: string,  // 完整物流文本（用于关键词检测）
    }
  ]
}
```

---

## `erpLogistics` 字段（ERP物流文本，仅退款-已发货时采集）

```js
{
  logisticsText: string,  // 完整文本，用 RETURN_KEYWORDS 检测退回状态
}
```

---

## `productMatch` 字段

```js
{
  matched:   boolean,   // attr1 是否精确匹配
  specCode:  string,    // 规格商家编码（ERP编码）
  specCodes: [{ code: string }],  // 所有候选编码
}
```

---

## `productArchive` 字段

```js
{
  type:       string,   // "单品"/"套件"
  subItemNum: number,   // 套件子商品数（单品=1）
  title:      string,   // 商品标题
  subItems: [
    {
      name: string,
      qty:  number,
    }
  ]
}
```

---

## `intercepted` 字段（快递拦截记录）

```js
{
  tracking:     string,  // 已拦截快递单号
  workOrderNum: string,  // 首次创建拦截的工单号
  executedAt:   string,  // 拦截操作时间 ISO 字符串
}
```

---

## `collectErrors` 约定

- 格式：`"<step>: <原因>"`
- step 前缀：`read-ticket`, `erp-search`, `erp-search(gift)`, `logistics`, `product-match`, `product-archive`, `erp-aftersale`, `erp-logistics`
- `read-ticket:` 或 `erp-search:` 前缀 → infer.js 视为关键错误，立即 escalate
- 其余前缀 → infer.js 视为非关键错误，降级处理

---

## 变更规范

1. collect.js 新增/改名字段 → 更新本文档对应行
2. collect.js 删除字段 → 更新本文档 + 确认 infer.js 无引用
3. infer.js 新增读取字段 → 确认 collect.js 已产出 + 更新本文档
