# SKU 库存计算器

根据加购数据 + SKU 组合明细 + 仓库库存，自动计算活动库存分配方案，输出 Excel 报告。

## Session 启动（必做，按顺序）

1. 读 `tasks/todo.md` — 确认当前待办和进度
2. 读 `docs/INDEX.md` — 操作规则权威入口

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | 任何操作前 |
| `SKILL.md` | 首次操作时 |
| `tasks/lessons.md` | 遇到问题时 |

## 教训沉淀流程

- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入，不在两处重复维护

## 相关项目

- `../product-mapping/` — 共享 ERP 操作能力（对应表读取、档案V2查询、CDP通信）
  - ERP 导航：`../product-mapping/lib/navigate.js`
  - 对应表读取：`../product-mapping/lib/correspondence.js`
  - 档案V2查询：`../product-mapping/lib/archive.js`
  - CDP通信：`../product-mapping/lib/cdp.js`
  - 单品目录：`../product-mapping/data/products/kgos/features.json`
- `../aftersales-automation/` — 共享同一套 ERP + 鲸灵系统

## 目录说明

| 目录 | 用途 |
|------|------|
| `lib/` | 核心模块 |
| `data/` | 持久数据：组合明细缓存、库存配置、列顺序配置 |
| `docs/` | 操作规范 |
| `tasks/` | 待办和教训 |
| `test/` | 单元测试 |

## 核心命令

```bash
node cli.js parse <excel文件>     # 解析加购 Excel
node cli.js calculate             # 执行库存分配算法
node cli.js report                # 生成 Excel 报告
node cli.js run <excel文件>       # 全流程一键执行
```
