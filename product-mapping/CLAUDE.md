# 商品匹配核查

项目中文名：商品匹配

## Session 启动（必做，按顺序）

1. **读 `SKILL.md`** — 运行时上下文入口，禁止跳过。禁止先 grep / glob / smart_search 再回来读
2. 读 `tasks/todo.md` — 确认当前待办和进度
3. 若当前由 ChatGPT 通过 CodexPro 操作，先读 `docs/chatgpt-codexpro-operations.md`，提前确定图片桥接和长任务交接方式
4. 按命令确认浏览器依赖：首次 `check` 需要鲸灵+ERP；`match` 和后置 `check --reuse-active` 只需要 ERP
5. 读 `docs/INDEX.md` — 操作规则，按需加载（SKILL.md 的 DO FIRST 会告诉你看什么）

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | **每次必读**：流程、视觉匹配规则、技术规范、坑位 |
| `docs/matching-stability.md` | 自动匹配、断点恢复、页面异常时必读：状态机、故障优先级、恢复顺序 |
| `docs/chatgpt-codexpro-operations.md` | 仅 ChatGPT + CodexPro 模式必读：图片桥接、有限前台时长（本轮 180 秒）、target 刷新和本地 Codex 交接 |

## 命令速查

```bash
node cli.js match-one <货号> --shop <店铺> --brand <品牌> [--from 步骤] # 单货号匹配（品牌必填）
node cli.js match-batch --shop <店铺>                      # 批量匹配
node cli.js check --shop <店铺> --brand <品牌>             # 首次核查（品牌必填，扫描+下载+生成报告）
node cli.js check --shop <店铺> --reuse-active --skip-download # 匹配后核查（复用已确认范围，不下载平台商品）
node cli.js match --shop <店铺> [--limit N]                # 自动匹配（组合装套件+单品，异常停止）
node cli.js verify-table                                   # 仅自动核对异常时生成图片+ERP明细人工诊断表
node cli.js targets                                        # 检查浏览器连通性
```

`--from` 合法值见 `docs/INDEX.md §2`

## 进入工作前确认（详细规则见 `docs/INDEX.md §1`）
- 写操作（新增匹配）必须人工确认
- ERP 命令串行，禁止并行
- 品牌在首次 check 时明确指定并写入本轮记录；preview/match/后置 check 必须继承同一品牌，禁止 kgos/hee 静默兜底
- 视觉匹配由我亲自执行，不写识别脚本
- 若用户已手动打开并筛选好鲸灵商品列表，只读当前页面，不自动开页/注入账号；需要 AI 自动开页或注入登录态时，先按 `docs/INDEX.md §2 Step 0` 的 targetId 边界处理
- 识图必须覆盖本次报告全部 SKU，`recognition` 为空但 ERP 有明细必须判为 mismatch，不能归入 pending
- 档案V2 主商家编码查不到时，先按规格商家编码回退查询，再判断是否无明细
- 浏览器自动化通用约束（querySelector可见性/Element UI弹窗/实时验证）→ 见根目录 `CLAUDE.md` 浏览器操作约束区

## Git 存档规则

改动验证通过后立即 commit + push，不攒到 session 结束。
暂存：`git add AGENTS.md README.md CLAUDE.md SKILL.md lib/ cli.js docs/ tasks/`
默认不提交：`data/`（sku-records.json / imgs/ / reports/ 等）
例外：用户明确确认“一轮商品匹配已完成，可以归档”时，`data/sku-records.json` 可单独提交；仍禁止提交 `data/imgs/`、`data/reports/` 等运行时产物。

## 相关项目

鲸灵售后系统（`../aftersales-automation/`）与本项目操作**同一套 ERP 和鲸灵**：

| 我需要参考 | 去哪里找 |
|-----------|---------|
| ERP 完整登录恢复（session 过期/全退出） | `../aftersales-automation/lib/erp/navigate.js` 的 `recoverLogin()` |
| 浏览器自动化通用红线：querySelector 只选可见元素、禁止 DOM 移除 Element UI 弹窗 | 根目录 `CLAUDE.md` 浏览器操作约束；售后归档见 `../aftersales-automation/docs/INDEX.md #60/#61` |
| Element UI 多弹窗并存时必须按 title 精确匹配，不能取第一个可见 wrapper | `../aftersales-automation/docs/INDEX.md #70` |
| 代码生成后必须自读，清除 placeholder/dead code（如 clickAt(null) 草稿残留） | `../aftersales-automation/docs/INDEX.md #69` |

售后项目参考本项目：el-table clearSelection / 多层 dialog 按钮 / 对应表图片懒加载 → `docs/INDEX.md §6`

商品匹配本项目的连续 SKU、Vue 隐藏选择和中断恢复规则 → `docs/matching-stability.md`
