# 售后采集数据 Schema（接口合约）

> 当前生产 `target-aware-collector`、兼容 `collect.js` 与 `infer.js` 之间的统一约定。
> **变更任一字段必须同步更新本文档和 infer.js 中对应读取路径。**

---

## 顶层结构（`sim.collectedData`）

```js
{
  ticket:         Object | null,   // 必填（read-ticket 失败时为 null，infer 会 escalate）
  erpSearch:      Object | null,   // 第一个主商品子订单结果（旧字段兼容）
  erpSearches:    Object[],        // 全部主商品子订单 ERP 搜索结果
  erpLogistics:   Object | null,   // 可选，仅退款-已发货补充物流源
  logistics:      Object | null,   // 可选，鲸灵发货物流
  erpAftersale:   Object | null,   // 退货退款/换货有 returnTracking 时必填
  productMatch:   Object | null,   // 可选，商品对应表结果
  productArchive: Object | null,   // 可选，商品档案V2
  giftErpSearch:  Object | null,   // 第一个赠品子订单结果（旧字段兼容）
  giftErpSearches: Object[],       // 全部赠品子订单 ERP 搜索结果
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
| `returnTracking` | string | 否 | 退货快递单号（退货退款或已进入退回验收阶段的换货可能有值） |
| `returnTrackingMultiUse` | boolean | 否 | 退货快递是否被多个工单共用 |
| `returnTrackingUsedBy` | string[] | 否 | 共用该快递的其他工单号列表 |
| `subOrders` | array | 是 | 子订单列表（至少1条） |
| `subOrders[].id` | string | 是 | 子订单号（纯数字） |
| `subOrders[].sku` | string | 否 | 商品货号 |
| `subOrders[].attr1` | string | 否 | 规格属性（颜色/尺寸等） |
| `subOrders[].afterSaleNum` | number | 是 | 申请售后数量（套数） |
| `gifts` | array | 否 | 赠品子订单列表 |
| `gifts[].id` | string | 是 | 赠品子订单号 |

当前只稳定采集工单级售后总金额，不采集每个子订单自己的支付金额。多子订单部分退款无法只靠本 Schema 计算推荐退款金额，必须交给人工核对；不得按商品数量自行均摊。

`returnTrackingMultiUse` 和 `returnTrackingUsedBy` 只来自平台详情提示，禁止通过扫描历史相同退货单号自行补充。生产推理会在采集后生成顶层 `sharedReturnGroup`：相同子订单标记为重复申请；不同子订单保存合并后的逐规格应退明细；平台列出的工单记录缺失时标记为 `incomplete` 并转人工。

---

## `erpSearches` / `giftErpSearches` 字段（erp-search 采集）

```js
[
  {
    subOrderId: string,
    rows: {
      rows: [
        {
          platformTradeText: string,   // 平台交易号原文，如 "756292468；756311711"
          platformOrderIds:  string[], // 拆分后的平台子订单号；每一行必须包含本次搜索号
          status:            string,   // "卖家已发货"/"交易成功"/"待审核"/"待打印快递单"/"待发货"
          tracking:          string,   // 快递单号（可选）
          trackings:         string[], // 多快递单号列表（可选）
        }
      ]
    }
  }
]
```

`erpSearch` 和 `giftErpSearch` 分别保留数组第一项，供旧快照和旧读取路径兼容。新推理必须优先合并数组中的全部子订单、全部行。

ERP 按子订单号搜索后，必须逐行核验“平台交易号”。合并订单可用中文或英文分号连接多个子订单号；只要其中包含本次搜索号，该行有效。任意一行缺失或不包含本次搜索号时，只重新执行一次搜索；第二次仍失败则整次采集失败，不能进入后续物流采集或推理。该重试只限本次 ERP 搜索，不重跑整张工单。

---

## `erpAftersale` 字段（erp-aftersale 采集）

```js
{
  rows: [
    {
      erpOrderId: string,    // ERP 售后工单号；已收货行必须存在且不得重复
      goodsStatus: string,   // "卖家已收到退货"/"在途"等
      tracking: string,      // ERP 退货单号；必须与鲸灵工单 returnTracking 一致
      returnQty: number,     // 本行实退总数；必须等于明细 qtyGood + qtyBad 合计
      items: [
        {
          name:    string,   // 商品名称
          specCode: string,  // 主商家规格编码；严格核对只认该字段
          qtyGood: number,   // 良品数量
          qtyBad:  number,   // 次品数量
        }
      ]
    }
  ]
}
```

严格退回证明只统计 `goodsStatus` 明确为“卖家已收到退货”的行。任一已收货行缺商品明细、售后工单号重复、退货单号冲突、`returnQty` 与明细合计不一致，或本次采集存在任何错误时，固定转人工。换货和商责即使严格证明通过，也只能推荐人工同意并禁止扫描中的无人自动执行；人工核对后，只有 `humanTriggeredExecutionAllowed: true` 且动作明确的工单才能使用系统单笔或人工发起的批量执行。

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
  results: [
    {
      rowIndex: number,
      tracking: string,
      logisticsText: string,  // 完整文本，用物流节点判断未揽收/已发货/已退回
    }
  ]
}
```

旧快照 `{ logisticsText: string }` 继续兼容。

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
