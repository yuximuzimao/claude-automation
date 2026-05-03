# 商品匹配核查

## Session 启动（必做，按顺序）

1. **读 `SKILL.md`** — 运行时上下文入口，禁止跳过。禁止先 grep / glob / smart_search 再回来读
2. 读 `tasks/todo.md` — 确认当前待办和进度
3. 确认 Chrome 已打开鲸灵和快麦 ERP 两个标签页
4. 读 `docs/INDEX.md` — 操作规则，按需加载（SKILL.md 的 DO FIRST 会告诉你看什么）

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | **每次必读**：流程、视觉匹配规则、技术规范、坑位 |

## 命令速查

```bash
node cli.js match-one <货号> --shop <店铺> [--from 步骤]  # 单货号匹配（断点续跑）
node cli.js match-batch --shop <店铺>                      # 批量匹配
node cli.js check --shop <店铺>                            # 旧：扫描+标记
node cli.js targets                                        # 检查浏览器连通性
```

`--from` 合法值见 `docs/INDEX.md §2`

## 进入工作前确认（详细规则见 `docs/INDEX.md §1`）
- 写操作（新增匹配）必须人工确认
- ERP 命令串行，禁止并行
- 视觉匹配由我亲自执行，不写识别脚本

## Git 存档规则

改动验证通过后立即 commit + push，不攒到 session 结束。
暂存：`git add lib/ cli.js docs/ tasks/`
不提交：`data/`（sku-records.json / imgs/ / reports/ 等）

## 相关项目

鲸灵售后系统（`../aftersales-automation/`）与本项目操作**同一套 ERP 和鲸灵**：

| 我需要参考 | 去哪里找 |
|-----------|---------|
| ERP 完整登录恢复（session 过期/全退出） | `../aftersales-automation/lib/erp/navigate.js` 的 `recoverLogin()` |
| ERP 表格读 el-input-number 值 | `../aftersales-automation/tasks/lessons.md §7` |
| El-Select 下拉必须 cdp.clickAt | `../aftersales-automation/tasks/lessons.md §3` |
| 批量操作写入路径漏传参 → 静默错误 | `../aftersales-automation/tasks/lessons.md §16` |

售后项目参考本项目：el-table clearSelection / 多层 dialog 按钮 / 对应表图片懒加载 → `docs/INDEX.md §6`

