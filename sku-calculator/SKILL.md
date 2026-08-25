# SKILL.md — SKU 库存计算器导航地图

## DO FIRST

1. 读 `tasks/todo.md` 确认当前进度
2. 读 `docs/INDEX.md` 了解操作规范
3. 核心算法在 `lib/allocate.js`，修改前必读
4. 数据文件在 `data/`，结构见 `docs/INDEX.md §3`

## ENTRY MAP

| 文件 | 用途 | 何时读 |
|------|------|--------|
| `README.md` | 人类使用入口、输入方式与安全边界 | 首次了解项目时 |
| `cli.js` | CLI 入口，所有命令的分发 | 执行命令时 |
| `lib/product-catalog.js` | 运行时产品目录读取（含 clearCache()） | 涉及单品名称时 |
| `lib/parse-cart-adds.js` | 读鲸灵加购 Excel → JSON | 解析输入数据时 |
| `lib/allocate.js` | 核心分配算法：Phase M保底预扣 + Phase G赠品80%上限 + 迭代"耗尽即锁定" + LRM回填 | 修改算法时 |
| `lib/write-report.js` | 生成输出 xlsx | 修改报告格式时 |
| `lib/resolve-components.js` | ERP 组合明细查询 + **满赠货号自动展开** + 动态生成 product-columns.json | 接入 ERP 时 |
| `lib/query-stock.js` | ERP 库存状态查询（依赖 product-columns.json 已生成） | 接入 ERP 时 |
| `lib/validate-supplier.js` | 供应商ID校验（parse 后执行，不匹配即中止） | 使用 --supplier-id 参数时 |
| `data/gift-sku-config.json` | 满赠SKU配置（只需货号，resolve-components 自动展开为完整SKU列表） | 有赠品需求时 |
| `../aftersales-automation/lib/erp/shop-map.js` | 供应商ID→ERP店铺名映射（共享模块，单一真相源） | 新增供应商时维护 |
| `data/product-columns.json` | **运行时生成**（resolve-components 写出，不手动维护） | 调试单品映射时 |
| `data/sku-components.json` | 组合明细（运行时生成） | 查询/调试时 |
| `data/warehouse-stock.json` | 云仓库存（运行时生成） | 查询/调试时 |
| `data/cart-adds.json` | 解析后的加购数据（运行时生成） | 查看/调试时 |
| `data/allocation-result.json` | 分配结果中间数据（运行时生成） | 调试算法时 |
| `docs/page-cart-scraping.md` | 鲸灵 SKU 明细页 → cart-adds.json 的字段、分页和验证契约 | 无 Excel、从页面读取加购数据时 |
| `docs/archive/README.md` | 历史批次索引；只用于追溯，禁止复用作下一轮输入 | 查历史批次时 |

## PATHS（git 变更时同步更新）

```
sku-calculator/
  README.md
  CLAUDE.md
  SKILL.md
  cli.js
  package.json
  lib/
    product-catalog.js
    parse-cart-adds.js
    allocate.js
    write-report.js
    resolve-components.js     # ERP 组合明细 + 动态生成 product-columns.json
    query-stock.js            # ERP 库存查询（依赖 resolve-components 先跑）
    validate-supplier.js      # 供应商ID校验（parse --supplier-id 参数）
  data/                       # 本地运行数据与输入配置，整个目录已加入 .gitignore
    gift-sku-config.json      # 手动编辑：满赠SKU固定分配配置（本地、不提交）
    product-columns.json      # resolve-components 生成（ERP原名即displayName）
    sku-components.json       # resolve-components 生成（含赠品SKU条目）
    warehouse-stock.json      # query-stock 生成
    cart-adds.json            # parse 生成
    allocation-result.json    # calculate 生成
  docs/
    INDEX.md
    page-cart-scraping.md
    archive/README.md
  tasks/todo.md
  tasks/lessons.md
  test/allocate.test.js
```
