# SKU 库存计算器 — 操作规范

## §1 核心算法规则

- 库存按加购比例分配，全局统一缩放系数 `k = min(1, min(available[j] / baseDemand[j]))`
- k 封顶为 1，不超额备货
- 零加购 SKU 走 Phase B 保底（默认5件），不参与比例计算
- LRM 回填：每次 +1 立即扣减 remaining，防止组合超卖

## §2 输出格式

三层：
1. SKU 明细行（货号 + 变体名 + 建议库存 + 加购数 + 当次发现的单品列）
2. 汇总行（合计 / 云仓库存 / 剩余库存 / 余量达标行）
3. 瓶颈分析 sheet（缩放系数 k + 瓶颈单品 + 各单品利用率）

输出为带联动公式的 xlsx：建议库存（蓝色）改动后，总占用/剩余/达标自动重算。

## §3 数据文件规范

**所有文件均为运行时产出，加入 .gitignore，不手动维护。**

| 文件 | 说明 | 生成命令 | 清空时机 |
|------|------|----------|---------|
| `data/product-columns.json` | 本次活动涉及的单品目录（ERP原名即displayName，按发现顺序排列） | `resolve-components` | 每次 resolve-components 开始时清空 |
| `data/sku-components.json` | SKU 组合明细（SKU → 各单品用量） | `resolve-components` | 每次 resolve-components 开始时清空 |
| `data/warehouse-stock.json` | 云仓库存（displayName → 数量） | `resolve-stock` | 每次 resolve-stock 开始时清空 |
| `data/cart-adds.json` | 本次加购数据（解析自鲸灵 Excel） | `parse` | 每次 parse 覆盖 |
| `data/allocation-result.json` | 分配结果 | `calculate` | 每次 calculate 覆盖 |

## §4 可配置参数

- `--reserve 0.2` — 库存余量比例（默认0.2即20%）
- `--cold-fixed 5` — 零加购 SKU 保底库存（默认5）

## §5 ERP 接入（run-full 流程）

**正确步骤顺序**（resolve-components 必须先于 resolve-stock）：

```
parse → resolve-components → resolve-stock → calculate → report
```

原因：resolve-stock 依赖 product-columns.json 做 ERP 名→displayName 映射，而该文件由 resolve-components 动态生成。

模块依赖：
- `../product-mapping/lib/correspondence.js` + `../product-mapping/lib/archive.js` → 组合明细
- `../product-mapping/lib/cdp.js` → 库存状态页读取
- 支持任意店铺（无需手动维护单品目录，ERP 原名自动成为 displayName）

## §6 已知坑位

- **resolve-components 和 resolve-stock 必须顺序执行**：两者共用同一个 ERP tab，不能并行（ERP 浏览器操作互斥）
- **product-columns.json 是临时产出**：每次 resolve-components 清空重建，不同店铺不相互污染
- **mergeStock 场景**：旧的 KGOS 配置里有将两个 ERP 名合并到同一 displayName 的模式（如玉米片两种口味），动态目录不支持这种合并；如需合并，未来可在 resolve-components 后加一个手动配置覆盖步骤
