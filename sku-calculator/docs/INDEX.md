# 库存计算文档与数据索引

入口顺序：`SKILL.md` → `tasks/todo.md` → 本索引；本页只导航，不保存分配规则或批次状态。

## 任务入口

| 需要什么 | 去哪里 |
|---|---|
| 人类使用入口、输入方式和输出位置 | [README](../README.md) |
| 尚未完成事项及ERP命令已知接口缺陷 | [当前待办](../tasks/todo.md) |
| 库存分配流程、算法、参数、数据契约、ERP接入与完成校验 | [操作手册](operations.md) |
| 从已打开的鲸灵SKU明细读取加购 | [页面加购读取](page-cart-scraping.md) |
| 未归类的新发现 | [临时教训](../tasks/lessons.md) |
| 历史批次与报告指纹 | [归档索引](archive/README.md) |

## 代码与数据位置

代码职责与函数入口见 [SKILL](../SKILL.md#entry-map)。

| 文件 | 内容 |
|---|---|
| `cli.js` | 命令分发 |
| `lib/allocate.js` | 分配算法 |
| `lib/write-report.js` | Excel生成 |
| `data/gift-sku-config.json` | 当前活动的手动满赠输入 |
| `data/cart-adds.json` | 加购输入 |
| `data/sku-components.json`、`data/product-columns.json` | ERP组合与动态单品目录 |
| `data/warehouse-stock.json`、`data/allocation-result.json` | 本次计算库存与分配结果 |
| `data/batches/` | 多活动的本地证据及副本，按当次归档定位 |
| `../aftersales-automation/lib/erp/shop-map.js` | 唯一共享店铺映射 |
| `../product-mapping/lib/` | 共享ERP读取模块 |

运行数据的字段、覆盖时机和使用边界见 [操作手册§3](operations.md#3-数据文件规范)；归档不能作为下一轮输入。
