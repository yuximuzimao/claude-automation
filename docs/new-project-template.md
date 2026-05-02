# 新项目开工规范

## 标准目录结构

```
project/
  CLAUDE.md           # Session 启动 + 目录说明 + 相关项目引用 + 教训沉淀流程
  cli.js              # 主命令入口
  lib/                # 核心模块（从其他项目移植时，文件头注明来源）
  docs/
    INDEX.md          # §分节规则文档，§6 为已知坑位（格式见售后/商品匹配项目）
  data/               # 结构化持久数据（禁止放日志/临时文件）
  tasks/
    todo.md           # 当前待办（每次 session 启动必读）
    lessons.md        # 临时教训（稳定后迁入 docs/INDEX.md §6）
  package.json
```

## 文件存放铁律

- **试错/原型脚本** → 工作区 `_sandbox/`，不在项目内建 _sandbox/
- **运行日志** → console 输出，不落盘；调试需要时放 `_sandbox/`
- **data/ 只放**：结构化持久数据（JSON/图片/报告），禁止放日志、临时文件
- **每次新建文件必问**：30天后还有用吗？没用 → _sandbox 或不落盘
- **移植代码**：文件头注明来源，如 `// 移植自 aftersales-automation/lib/erp/navigate.js`

## CLAUDE.md 必要段落

```markdown
# <项目名>

## Session 启动（必做，按顺序）
1. 读 `tasks/todo.md` — 确认当前待办和进度
2. <项目特有的启动命令>
3. 读 `docs/INDEX.md` — 所有操作规则的权威入口

## 规则文档（渐进式，按需加载）
| 文档 | 加载时机 |

## 教训沉淀流程
- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入，不在两处重复维护

## 相关项目
- `../other-project/` — 说明共享的系统/操作，及关键文档位置

## 目录说明
| 目录 | 用途 |（只列实际存在的目录）
```
