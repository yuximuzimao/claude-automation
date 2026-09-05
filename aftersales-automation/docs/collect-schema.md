# 售后采集数据 Schema（接口合约）

> 当前生产 `target-aware-collector`、兼容 `collect.js` 与 `infer.js` 之间的统一约定。
> **变更任一字段必须同步更新本文档和 infer.js 中对应读取路径。**

---

## 顶层结构（`sim.collectedData`）

```js
{
  ticket:         Object | null,   // 必填（read-ticket 失败时为 null，infer 会 escalate）
  platformStage:  Object,          // 必填，售后列表读取到的平台阶段观察；缺失也显式记录
  platformStageAssessment: Object | null, // 可选，命中观察期状态分支时保存原综合推理对照
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

### `platformStage` 字段（售后列表观察）

```js
{
  raw:        string | null, // 列表原始 `商家-*` 文案；未读取到时为 null
  observedAt: string,        // 本次列表读取时间（ISO）
  source:     'after-sale-list',
  readState:  'read' | 'missing',
}
```

该字段对所有进入 48 小时清单的工单保存。默认只用于前端展示和历史复盘，不参与推理。当前只有 `换货 + 商家-待商家二次发货` 命中观察期分支；命中时 `platformStageAssessment.baselineDecision` 保存完整原综合推理，最终决策固定为“无需处理、人工确认后手动归档”。重新采集时以本次列表定位读到的阶段为准，不沿用 queue 旧值。

人工确认归档后，queue 保存 `confirmedNoAction`（案例、阶段、确认时间）。后续扫描若仍是同一阶段，只更新 `platformStage.observedAt` 并跳过重复待确认；阶段变化后该确认自动失效，重新进入正常流程。

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

`returnTrackingMultiUse` 和 `returnTrackingUsedBy` 只来自平台详情提示，禁止通过扫描历史相同退货单号自行补充。关联号优先读取 Vue 物流结构中的 `logisticsUsedWorkOrderNumList`，缺失时读取「多次使用」按钮所引用悬浮层的 `textContent`；`document.body.innerText` 只用于确认页面出现了“多次使用”，不能作为关联号来源。

生产推理会在采集后生成顶层 `sharedReturnGroup`，其业务定义必须服从 `INDEX §3.4.1`。当前模式为 `combined_applications`：`workOrderNums` 只列本轮当前有效关联工单，主商品按每张工单自己的 `afterSaleNum` 累计；`expectedItems` 是本轮当前申请的逐规格应退数量，主子订单号相同也不去重，赠品按 `giftSubBizOrderId` 去重。历史核查仅在平台当前详情明确 `returnTrackingMultiUse=true` 且给出 `returnTrackingUsedBy` 时启用，并且只按平台点名的工单号查询：本轮 48 小时固定批次成员必须使用本轮新采集，尚未采集则返回 `missingWorkOrderNums` 延迟；不在本轮批次的关联号才查历史 simulation。历史记录只有 `decision.action=approve` 且存在 `executedAt` 才写入 `historicalConsumedItems` 并在 `historicalWorkOrders[].consumesReturnQty=true`，表示已经成功退款占用的退货实物；其他历史动作占用为 0。推理使用 `ERP 当前实收 - historicalConsumedItems` 与 `expectedItems` 比较。平台点名的关联工单若本轮 48 小时采集与历史记录都不存在，则 `sharedReturnGroup.mode=incomplete`，reason 必须显示缺失工单号并说明可能为历史记录缺失或特殊重复申请，禁止猜测。赠品去重跨历史已退款占用与本轮当前申请共同生效。

不同子订单合并核验复用严格退回证明：所有「卖家已收到退货」行必须有唯一 `erpOrderId`，`tracking` 必须与当前工单一致，`returnQty` 必须等于本行商品明细的 `qtyGood + qtyBad` 合计。任一条件不满足都不得用这些行凑综合总数。

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
      tab:  string,  // 包裹 tab 名，如“包裹1”；快递单号从 text 解析
      text: string,  // 当前 tab 的物流文本（用于单号提取和关键词检测）
      error?: string,
    }
  ],
  warnings: string[],
  closeErrors: Object[],
}
```

`warnings` / `closeErrors` 记录物流已经读取、但弹窗收尾失败的降级信息。推理仍可使用已采集的 `packages`，不能把关闭失败误报成“物流未读取”。

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
  type:       '0' | '1' | '2', // ERP 原始类型：普通商品/套件/组合装
  subItemNum: number,   // ERP 原值；普通商品通常为 0，套件/组合装大于 0
  title:      string,   // 商品标题
  subItems: [
    {
      name:     string,
      specCode: string,
      qty:      number,
    }
  ]
}
```

业务计算时普通商品 `subItemNum=0` 按 1 件处理；不得为了方便改写采集原值。

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
