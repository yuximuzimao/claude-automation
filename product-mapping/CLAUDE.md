# 商品匹配核查

## Session 启动（必做，按顺序）

1. 读 `tasks/todo.md` — 确认当前待办和进度
2. 确认 Chrome 已打开鲸灵和快麦 ERP 两个标签页
3. 读 `docs/INDEX.md` — 所有操作规则的权威入口

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | **每次必读**：流程、视觉匹配规则、技术规范、坑位 |

## 命令速查

```bash
# 新架构（树状分支，优先使用）
node cli.js match-one <货号> --shop <店铺> [--from <步骤>]  # 单货号匹配（7步闭环，支持断点）
node cli.js match-batch --shop <店铺>                        # 批量匹配（整店）

# --from 合法值：download / read_skus / recognize / annotate / match / read_erp / verify

# 旧命令（check 流程独立，仍有效）
node cli.js check --shop <店铺>             # 扫描+标记（含下载平台商品+档案查询）
node cli.js visual-pending --shop <店铺>    # 列出待识图 SKU
node cli.js visual-ok <平台编码> "<描述>"   # 记录识图确认
node cli.js visual-flag <平台编码> "<描述>" # 记录识图不符
node cli.js km-archive <编码>               # 查商品档案V2（单条）
node cli.js targets                         # 检查浏览器连通性
```

**match-one 流程见 `tasks/todo.md §当前任务`；完整规则见 `docs/INDEX.md §2`**

## 进入工作前确认（详细规则见 `docs/INDEX.md §1`）
- 写操作（新增匹配）必须人工确认
- ERP 命令串行，禁止并行
- 视觉匹配由我亲自执行，不写识别脚本

## 教训沉淀流程

- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入永久坑位，不在两处重复维护

## 相关项目

鲸灵售后系统（`../aftersales-automation/`）与本项目操作**同一套 ERP 和鲸灵**：

| 我需要参考 | 去哪里找 |
|-----------|---------|
| ERP 完整登录恢复（session 过期/全退出） | `../aftersales-automation/lib/erp/navigate.js` 的 `recoverLogin()` |
| ERP 表格读 el-input-number 值 | `../aftersales-automation/tasks/lessons.md §7` |
| El-Select 下拉必须 cdp.clickAt | `../aftersales-automation/tasks/lessons.md §3` |
| 批量操作写入路径漏传参 → 静默错误 | `../aftersales-automation/tasks/lessons.md §16` |

售后项目参考本项目：el-table clearSelection / 多层 dialog 按钮 / 对应表图片懒加载 → `docs/INDEX.md §6`

## 目录说明

| 目录 | 用途 |
|------|------|
| `lib/` | 核心模块（jl-products / correspondence / archive / check 等） |
| `docs/` | 操作规则权威文档，规则只在此维护 |
| `data/products/` | 商品参考图库 + features.json |
| `data/imgs/` | 核查下载的 SKU 图片，按 platformCode 命名 |
| `data/reports/` | 核查报告输出（JSON + Markdown） |
| `data/auto-match-log.json` | auto-match2 进度状态（done/failed） |
| `tasks/` | `todo.md`（当前待办）/ `lessons.md`（临时教训）|
