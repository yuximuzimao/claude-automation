# SKU 库存计算器 — 操作规范

## §1 核心算法规则

- 库存按加购比例分配，全局统一缩放系数 `k = min(1, min(available[j] / baseDemand[j]))`
- k 封顶为 1，不超额备货
- 零加购 SKU 走 Phase B 保底（默认5件），不参与比例计算
- LRM 回填：每次 +1 立即扣减 remaining，防止组合超卖

## §2 输出格式

三层：
1. SKU 明细行（货号 + 变体名 + 建议库存 + 加购数 + 19个单品的用量和总占用）
2. 汇总行（合计 / 云仓库存 / 剩余库存）
3. 瓶颈解释（缩放系数 k + 瓶颈单品 + 利用率）

## §3 数据文件规范

| 文件 | 说明 | 来源 |
|------|------|------|
| `data/product-columns.json` | 19个单品的列顺序和显示名 | 手动维护 |
| `data/sku-components.json` | SKU 组合明细缓存 | Phase 1: 手动; Phase 2: ERP 自动 |
| `data/warehouse-stock.json` | 云仓库存 | Phase 1: 手动; Phase 2: ERP 自动 |
| `data/cart-adds.json` | 本次加购数据（解析自鲸灵 Excel） | cli.js parse 命令生成 |
| `data/allocation-result.json` | 分配结果（中间数据） | cli.js calculate 命令生成 |

## §4 可配置参数

在 `cli.js run` 命令中可通过参数调整：

- `--reserve 0.2` — 库存余量比例（默认0.2即20%）
- `--cold-fixed 5` — 零加购 SKU 保底库存（默认5）

## §5 Phase 2 接入 ERP（待实现）

ERP 操作必须通过 `../product-mapping/lib/` 的现有模块：

- 组合明细：`readCorrWithoutDownload()` → `querySubItems()`
- 库存状态：待用户提供操作方式后实现

## §6 已知坑位

（运行中发现后补入）
