# 洛克王国 · 收集助手

本项目是一个本地运行的洛克王国世界收集进度工具，用于维护精灵图鉴、异色炫彩、精灵果实、多形态、家具/外观等收集项。

## 快速开始

```bash
cd /Users/chat/claude/lkwj
node server.js
```

浏览器访问：

```text
http://localhost:8899
```

人工核对工具：

```text
http://localhost:8899/review.html
```

## 核心文件

| 文件 | 作用 |
| --- | --- |
| `index.html` | 主界面：看板、精灵、异色炫彩、多形态、精灵果实和其他收集 Tab |
| `server.js` | 本地 HTTP 服务和 JSON 保存接口 |
| `data/pets.json` | 精灵静态定义：名称、系别、形态、标签、果实 |
| `data/tasks.json` | 世界图鉴课题任务定义，任务只来自 Excel `课题进度` sheet |
| `data/evolution-chains.json` | 进化链和进化条件 |
| `data/collections.json` | 用户进度：任务、形态、果实、异色和其他收集状态 |
| `SKILL.md` | Agent 入口地图和数据边界规则 |
| `docs/REVIEW_CHECKLIST.md` | 对照 Excel 做只读核对的清单 |

## 数据边界

- `pets.json` 保存世界定义，不能从用户进度反向生成。
- `tasks.json` 只保存世界图鉴课题任务，任务来源只能是 Excel `课题进度` sheet；`异色` 行作为 `capture_shiny` 任务纳入。
- `collections.json` 保存用户勾选进度，包括 `sprite_progress[petKey].forms_collected` 和 `fruit_acquired`。
- `confirm_forms.requiredForms` 只声明课题计入的形态；完整多形态收集独立显示在「多形态」Tab。
- `fruit` 任务是“精灵果实课题任务”，不是果实图鉴。有果实不代表有 fruit 任务。
- `shiny_progress` 是异色收集进度，不由任何 task 状态驱动。

## 当前关键数量

| 项目 | 数量 |
| --- | ---: |
| 精灵 | 373 |
| 课题任务 | 1882 |
| 精灵果实课题任务 | 96 |
| 果实图鉴记录 | 143 |
| 多形态收集项 | 143 |
| 有额外形态的精灵 | 57 |
| 异色标签 | 38 |
| 首领形态 | 27 |
| 进化链 | 165 |

## 验证

```bash
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
node scripts/validate-random-task-ui.js
node -e "for (const f of ['data/pets.json','data/tasks.json','data/collections.json']) JSON.parse(require('fs').readFileSync(f,'utf8')); console.log('json ok')"
```

如需验证本地服务：

```bash
node server.js
```

再访问 `http://localhost:8899`。
