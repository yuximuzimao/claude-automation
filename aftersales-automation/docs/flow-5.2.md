# 仅退款-未发货处理流程（5.2）

> 前置：已读 `docs/INDEX.md`，工单类型确认为「仅退款」，且 ERP 搜索显示未发货
> 核验重点：**ERP确认商品真的未发货，且主商品+赠品均未发货**

---

## 完整流程

### Step 1：读鲸灵工单详情

```bash
node cli.js read-ticket <工单号>
```

必须记录：
- `subBizOrderDetailDTO[0].subBizOrderId` — 主子订单号
- `giftSubBizOrderDetailDTO[0].subBizOrderId` — 赠品子订单号（如有）

### Step 2：ERP 确认主商品发货状态

```bash
node cli.js erp-search <主子订单号>
```

判断 ERP 状态：

| ERP 状态 | 含义 | 处理 |
|---------|------|------|
| 待审核 | 未发货 | ✅ 继续 |
| 待打印快递单 | 未发货 | ✅ 继续 |
| 待发货 | 打包中 | ⚠️ 上报人工（联系仓库确认） |
| 卖家已发货 | 已发货 | ❌ 转入 `docs/flow-5.3.md` |

### Step 3：若有赠品，ERP 确认赠品发货状态

```bash
node cli.js erp-search <赠品子订单号>
```

判断同 Step 2：
- 待审核/待打印 → ✅ 赠品未发货
- 待发货 → ⚠️ 上报人工
- 卖家已发货 → ❌ 不能直接同意，上报人工

### Step 4：主商品+赠品均确认未发货 → 同意退款

```bash
node cli.js approve <工单号>
```

---

## 决策快速参考

```
鲸灵读详情 → 主子订单号 + 赠品子订单号
  ↓
ERP搜主子订单号
  ├─ 待审核/待打印 → 未发货✅
  ├─ 待发货 → 人工确认
  └─ 已发货 → 转 flow-5.3.md
  ↓（主商品未发货）
有赠品 → ERP搜赠品子订单号 → 同上判断
  ↓
全部未发货 → 同意退款
```
