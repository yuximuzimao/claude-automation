# 商品查询操作指南（ERP 商品对应表 + 档案V2）

> 适用场景：需要根据货号查规格商家编码，或根据规格商家编码确认单品/套件信息
> 这两个查询通常连续执行：对应表 → 规格编码 → 档案V2

---

## §1 商品对应表（货号 → 规格商家编码）

### 使用命令（推荐）

```bash
# 脚本自动处理：店铺切换、精确搜索模式设置、货号搜索、结果验证
node cli.js product-match <货号> "<attr1>" <ERP店铺名>
```

**参数说明**：
- `货号`：从鲸灵工单 `spuBarcode` 字段读取（如 `0401-2`）
- `attr1`：从鲸灵工单 `attribute1` 字段读取（如 `精华水 150ml*3`）
- `ERP店铺名`：从 `lib/erp/shop-map.js` 查得（见 INDEX §3.2）

**返回值解读**：

```json
// 成功匹配
{"success": true, "data": {"barcode": "0401-2", "attr1": "精华水 150ml*3", "specCode": "6979151090014"}}

// attr1 未精确匹配（命名/空格差异），返回所有规格
{"success": true, "data": {"barcode": "0401-2", "attr1": "...", "matched": false, "specCodes": [
  {"text": "精华水 150ml*3", "code": "6979151090014"},
  {"text": "精华水 50ml*1", "code": "6979151090015"}
]}}

// attr1 为空，返回所有规格
{"success": true, "data": {"barcode": "0401-2", "specCodes": [...]}}
```

**attr1 匹配失败的 3 种原因**：
1. ERP 页面中属性名含多余空格（脚本已自动归一化，但仍可能存在特殊字符差异）
2. 鲸灵 attr1 与 ERP 显示名不完全一致（如「生椰拿铁味咖啡*1盒」vs「生椰拿铁味1盒」）
3. attr1 为空（买家未选规格）

**处理**：
- 返回 `specCodes` 列表时，根据 attr1 语义人工判断选哪个 code → 上报人工确认
- 如果 specCodes 只有一条，可直接使用该 code

### 关键验证规则（脚本已处理，供排查用）

- 搜索模式必须为：**精确搜索** + **平台商家编码**（否则结果不可信）
- 店铺过滤器必须按账号切换（见 INDEX §3.2），不能硬编码
- 搜索结果必须唯一（共1条）且平台商家编码完全一致

---

## §2 商品档案V2（规格商家编码 → 单品/套件信息）

### 使用命令（推荐）

```bash
node cli.js product-archive <规格商家编码>
```

**返回值解读**：

```json
// 单品
{"success": true, "data": {
  "outerId": "6979151090014",
  "title": "甘油二酯咖啡固体饮料（生椰拿铁味）8g*12",
  "subItemNum": 0,
  "type": "0",
  "hasProduct": false,
  "subItems": []
}}

// 套件（subItemNum > 0）
{"success": true, "data": {
  "outerId": "0401-9",
  "title": "RITEKOKO海茴香精华×2瓶+面霜×1瓶",
  "subItemNum": 3,
  "type": "2",
  "subItems": [
    {"name": "精华水150ml", "specCode": "xxx001", "qty": 2},
    {"name": "面霜50ml", "specCode": "xxx002", "qty": 1}
  ]
}}
```

**关键字段说明**：
- `subItemNum`：套件内单品总数（0 = 单品，>0 = 套件）
- `subItems`：套件中每种单品的名称、编码、数量
- `type`：`"0"` 普通商品，`"1"` 套件，`"2"` 组合装

**已验证案例（2026-04-04）**：
| 规格商家编码 | subItemNum | 结论 |
|------------|-----------|------|
| `6979151090014` | 0 | 单品 |
| `0401-9` | 3 | 套件（3件：精华×2+面霜×1）|

---

## §3 应退单品数量计算

拿到 subItemNum 后，结合 afterSaleNum 计算应退数量：

```
应退主商品单品数 = subItemNum × afterSaleNum

单品时（subItemNum=0，按1计）：
  应退数 = 1 × afterSaleNum = afterSaleNum

套件时（如 subItemNum=3，afterSaleNum=2）：
  应退数 = 3 × 2 = 6件单品
```

---

## 已知坑位（商品查询）

- `[∞/永久保留]` **#7 禁止靠名字猜明细**：禁止靠记忆或商品名推断明细，必须查商品对应表+档案V2，用规格商家编码对比
- `[∞/永久保留]` **#20 档案V2 DOM 可能空白**：商品档案V2 DOM 表格可能不渲染，必须从 Vue `sv.dataList` 读数据，不能依赖 `.el-table__body tr`
- `[∞/永久保留]` **#21 禁止空条件搜索**：搜索结果为空时，禁止发空条件搜索"验证页面"——会清空已有结果
- `[∞/永久保留]` **#22 档案V2 Enter 被拦截**：档案V2 的 Enter 监听器检查 isTrusted，模拟键盘事件被拦截，必须用 Vue 组件 `sv.handleQuery()` 触发搜索
- `[∞/永久保留]` **#27 店铺过滤器识别**：禁止用 `span.el-select__tags-text.filter-single-label` 验证店铺（读到的是左侧树控件）；正确方式：找 tagText≠目标店铺 的 `.el-select.select-wrap` 来识别搜索栏过滤器
- `[∞/永久保留]` **#29 对应表搜索触发**：商品对应表搜索必须用回车（POST /key Enter）触发，禁止点按钮（容易命中弹窗"确定"）
- `[∞/永久保留]` **#30 搜索前三验证**：对应表搜索前必须验证：① 店铺已切换 ② 搜索模式=精确搜索 ③ 搜索字段=平台商家编码，三项全过才能搜索
- `[∞/永久保留]` **#33 档案V2 子商品数字定位**：子商品数字链接用 `a.ml_15`，过滤 `innerText.trim()==数字 && getBoundingClientRect().width>0`，不需要截图
- `[∞/永久保留]` **#42 店铺过滤器按账号切换**：商品对应表店铺过滤器必须按账号 note 查 `lib/erp/shop-map.js` 获取，禁止硬编码「杭州共途」

> 赠品数量始终1份，不随 afterSaleNum 倍增。
