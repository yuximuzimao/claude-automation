# SKILL.md — SKU 库存计算器导航地图

## DO FIRST

1. 读 `tasks/todo.md` 确认当前进度
2. 读 `docs/INDEX.md` 了解操作规范
3. 核心算法在 `lib/allocate.js`，修改前必读
4. 数据文件在 `data/`，结构见 `docs/INDEX.md §3`

## ENTRY MAP

| 文件 | 用途 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，所有命令的分发 | 执行命令时 |
| `lib/product-catalog.js` | 19个单品目录，erpName ↔ 显示名映射 | 涉及单品名称时 |
| `lib/parse-cart-adds.js` | 读鲸灵加购 Excel → JSON | 解析输入数据时 |
| `lib/allocate.js` | 核心分配算法（全局缩放+LRM） | 修改算法时 |
| `lib/write-report.js` | 生成输出 xlsx | 修改报告格式时 |
| `lib/resolve-components.js` | Phase 2: ERP 组合明细查询 | 接入 ERP 时 |
| `data/product-columns.json` | 列顺序配置 | 修改列结构时 |
| `data/sku-components.json` | 组合明细缓存 | 查询/更新 SKU 配比时 |
| `data/warehouse-stock.json` | 云仓库存输入 | 更新库存数据时 |
| `data/cart-adds.json` | 解析后的加购数据 | 查看/调试时 |
| `data/allocation-result.json` | 分配结果中间数据 | 调试算法时 |

## PATHS（git 变更时同步更新）

```
sku-calculator/
  CLAUDE.md
  SKILL.md
  cli.js
  package.json
  lib/
    product-catalog.js
    parse-cart-adds.js
    allocate.js
    write-report.js
    resolve-components.js     # Phase 2
  data/
    product-columns.json
    sku-components.json
    warehouse-stock.json
    cart-adds.json            # 运行时生成
    allocation-result.json    # 运行时生成
  docs/INDEX.md
  tasks/todo.md
  tasks/lessons.md
  test/allocate.test.js
```
