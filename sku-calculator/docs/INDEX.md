# SKU 库存计算器 — 操作规范

## §1 核心算法规则

**Phase M — SKU 保底预扣**（2026-05-23）：每个正常 SKU 至少 `coldFixed` 件（默认 5），从全量库存中预扣，**优先级高于赠品**。受限单品等比例缩减。

**Phase G — 赠品预扣**：赠品最多占单品库存的 `(1 - reserve)`（默认 80%），超出时等比例缩减所有使用该单品的赠品 SKU。受限单品保证正常 SKU 至少分到 stock × reserve（默认 20%）。

**Phase 0 — 预处理**：赠品+保底预扣完毕后，对剩余库存应用 reserve。零库存单品依赖的 SKU 归零移出。active（加购>0）/ cold（加购=0）分离。

**Phase A — 迭代"耗尽即锁定"**：每轮找最紧约束单品（`min(R[j] / D[j])`），锁定所有使用该单品的 SKU 并扣减库存，不影响其余 SKU。库存充足时建议库存可远超加购数。

**Phase B — 整数化 + LRM 回填**：floor 取整后按余数降序逐条 +1，每次立即扣减（防止组合超卖）。

**Phase C — cold SKU 保底**：零加购 SKU 取 Phase M 预扣值（无需额外分配）。

## §2 输出格式

三层：
1. SKU 明细行（货号 + 变体名 + 建议库存 + 加购数 + 当次发现的单品列）
2. 汇总行（合计 / 云仓库存 / 剩余库存 / 余量达标行）
3. 瓶颈分析 sheet（缩放系数 k + 瓶颈单品 + 各单品利用率）

输出为带联动公式的 xlsx：普通 SKU 建议库存（蓝色）可编辑，赠品 SKU 建议库存（绿色）为固定值 + 【满赠】标签。改动后总占用/剩余/达标自动重算。瓶颈分析 sheet 含赠品数量。

## §3 数据文件规范

**除 gift-sku-config.json 外，所有文件均为运行时产出，加入 .gitignore。**

| 文件 | 说明 | 生成命令 | 清空时机 |
|------|------|----------|---------|
| `data/gift-sku-config.json` | **手动维护**：满赠SKU固定分配配置 | `cli.js gift-config add` 或直接编辑 | 手动 |
| `data/product-columns.json` | 本次活动涉及的单品目录（ERP原名即displayName，按发现顺序排列） | `resolve-components` | 每次 resolve-components 开始时清空 |
| `data/sku-components.json` | SKU 组合明细（SKU → 各单品用量，含赠品SKU） | `resolve-components` | 每次 resolve-components 开始时清空 |
| `data/warehouse-stock.json` | 云仓库存（displayName → 数量） | `resolve-stock` | 每次 resolve-stock 开始时清空 |
| `data/cart-adds.json` | 本次加购数据（解析自鲸灵 Excel） | `parse` | 每次 parse 覆盖 |
| `data/allocation-result.json` | 分配结果（赠品SKU 标记 isGift） | `calculate` | 每次 calculate 覆盖 |

## §4 可配置参数

- `--reserve 0.2` — 库存余量比例（默认0.2即20%）
- `--cold-fixed 5` — 零加购 SKU 保底库存（默认5）
- `data/gift-sku-config.json` — 满赠SKU固定分配。支持两种格式：
  - **原始格式**（推荐）：`{"giftSkus": [{"huohao": "...", "fixedAllocation": N}]}`，只需货号，`resolve-components` 自动从对应表展开所有 SKU
  - **完整格式**：`{"giftSkus": [{"huohao": "...", "skuName": "...", "fixedAllocation": N}]}`，`resolve-components` 运行后自动写入
  - `calculate` 自动读取，`cli.js gift-config add/list/clear` 辅助维护
- `--cold-fixed 5` — 所有正常 SKU 保底件数（默认5），Phase M 从全量库存预扣，优先于赠品

## §5 ERP 接入（run-full 流程）

**正确步骤顺序**（resolve-components 必须先于 resolve-stock）：

```
parse --supplier-id <商家ID> → resolve-components → resolve-stock → calculate → report
```

**供应商ID验证**：`parse --supplier-id <id>` 会校验 Excel 中所有行的「供应商id」列是否与目标商家ID一致，任一不匹配立即中止。商家ID在 ERP 后台右上角可查（新供应商接入时需实时读取，不凭记忆）。

**店铺名自动推导**：`resolve-components` 自动从 `cart-adds.json _meta.supplierId` → 查共享模块 `../aftersales-automation/lib/erp/shop-map.js`（`getErpShopBySupplierId()`） → 得 ERP 店铺名。无需手动传 `--shop`。`--shop` 参数仅用于显式覆盖自动推导结果。

**反向验证硬门禁**：resolve-components 后若 `matchedSkus < totalSkus`，立即 `exit(1)` 并列出所有未匹配 SKU，不给错误数据进入 calculate 的机会。

原因：resolve-stock 依赖 product-columns.json 做 ERP 名→displayName 映射，而该文件由 resolve-components 动态生成。

模块依赖：
- `../product-mapping/lib/correspondence.js` + `../product-mapping/lib/archive.js` → 组合明细
- `../product-mapping/lib/cdp.js` → 库存状态页读取
- `../aftersales-automation/lib/erp/shop-map.js` → 供应商ID→店铺名映射（共享模块）
- 支持任意店铺（无需手动维护单品目录，ERP 原名自动成为 displayName）

## §6 已知坑位

- **resolve-components 和 resolve-stock 必须顺序执行**：两者共用同一个 ERP tab，不能并行（ERP 浏览器操作互斥）
- **product-columns.json 是临时产出**：每次 resolve-components 清空重建，不同店铺不相互污染
- **店铺名不能设默认值**：2026-05-22 事故——resolve-components 默认 shop=澜泽，但数据是共途的，读了错误店铺对应表。修复：店铺名从 `supplierId → shop-map.js` 自动推导，推导失败时报错不静默
- **新供应商接入第一步**：在 `aftersales-automation/lib/erp/shop-map.js` 对应条目补充 `supplierId` 字段
- **mergeStock 场景**：旧的 KGOS 配置里有将两个 ERP 名合并到同一 displayName 的模式（如玉米片两种口味），动态目录不支持这种合并；如需合并，未来可在 resolve-components 后加一个手动配置覆盖步骤
- **多项目 ERP 浏览器互扰**（2026-05-23 事故）：`aftersales-automation` 与 `sku-calculator` 共享同一 Chrome ERP tab，售后系统的 DOM 操作会破坏 resolve-components 的 Vue 状态（对应表`展开: 20/0`、档案V2 全量 `count=-1`）。跑 sku-calculator 前先停售后 server；失败后手动刷新对应表和档案V2两个页面
