# 洛克王国 · 收集助手

本项目是一个本地运行的洛克王国世界收集进度工具，用于维护精灵图鉴、异色炫彩、精灵果实、多形态、家具、服装、称号、遗迹和通用品类收集项。

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
| `index.html` | 主界面：看板 + 精灵 + 异色炫彩 + 多形态 + 精灵果实 + 家具 + 服装 + 称号 + 星星 + 遗迹 + 支线 + 扭蛋 + 音乐；全部收集类 Tab 含搜索和筛选 |
| `server.js` | 本地 HTTP 服务和 JSON 保存接口 |
| `data/pets.json` | 精灵静态定义：名称、系别、形态、标签、果实 |
| `data/tasks.json` | 世界图鉴课题任务定义，任务只来自 Excel `课题进度` sheet |
| `data/evolution-chains.json` | 进化链和进化条件 |
| `data/furniture.json` | 家具静态定义：名称、舒适度、灵感值 |
| `data/clothing.json` | 服装静态定义：套装共享信息 + 单件收集项 |
| `data/titles.json` | 称号静态定义：名称分段、获取方式 |
| `data/dungeons.json` | 遗迹副本静态定义：副本名称、位置、资源数量、特殊掉落、精灵蛋孵化属性 |
| `data/shops.json` | 商店和货币静态定义：商店入口、货币类型、待核对商店 |
| `data/collections.json` | 用户进度：任务、形态、果实、异色和其他收集状态 |
| `data/_待采集/` | 仍需人工补齐的数据模板；已导入 JSON 的旧模板不再保留 |
| `SKILL.md` | Agent 入口地图和数据边界规则 |
| `docs/REVIEW_CHECKLIST.md` | 对照 Excel 做只读核对的清单 |

## 数据边界

- `pets.json` 保存世界定义，不能从用户进度反向生成。
- `tasks.json` 只保存世界图鉴课题任务，任务来源只能是 Excel `课题进度` sheet；`异色` 行作为 `capture_shiny` 任务纳入。
- `collections.json` 保存用户勾选进度，包括 `sprite_progress[petKey].forms_collected` 和 `fruit_acquired`。
- `confirm_forms.requiredForms` 只声明课题计入的形态；完整多形态收集独立显示在「多形态」Tab。
- `fruit` 任务是“精灵果实课题任务”，不是果实图鉴。有果实不代表有 fruit 任务。
- `shiny_progress` 是异色收集进度，不由任何 task 状态驱动。
- `furniture.json` 保存家具定义；`collections.furniture_progress` 只保存是否收集，不能把舒适度/灵感值写进进度。
- 家具 Tab 顶部只展示总件数、已收集件数和未收集家具的剩余灵感值；舒适度和单件灵感值只在列表行展示。
- `clothing.json` 分为 `sets[]` 和 `pieces[]`：套装获取方式、特效、配对精灵只写在 `sets[]`；`pieces[]` 只保存最小勾选单元和 `setId`。`collections.clothing_progress` 只保存单件是否收集。
- `titles.json` 保存称号定义；页面按 `上段 · 下段` 显示一条称号，并展示获取方式；`collections.title_progress` 只保存是否收集。
- `dungeons.json` 保存遗迹副本定义、资源数量、钥匙类特殊掉落和精灵蛋孵化属性；`collections.dungeon_progress` 只保存是否完成。
- `shops.json` 已保存商店入口和货币类型；商品明细尚未建入 JSON，待 `data/_待采集/商店与货币.csv` 补齐。
- `collections.items` 是星星、支线任务、扭蛋机、音乐的通用收集项入口；当前为空。

## 当前关键数量

| 项目 | 数量 |
| --- | ---: |
| 精灵 | 375 |
| 课题任务 | 1894 |
| 精灵果实课题任务 | 96 |
| 果实图鉴记录 | 143 |
| 多形态收集项 | 137 |
| 家具 | 183 |
| 家具已收集 | 125 |
| 家具未收集 | 58 |
| 家具剩余灵感值 | 1506950 |
| 服装单件 | 6 |
| 称号 | 1 |
| 遗迹副本 | 26 |
| 遗迹孵化属性 | 26 |
| 商店入口 | 36 |
| 商店货币类型 | 6 |
| 通用品类收集项 | 0 |
| 有额外形态的精灵 | 51 |
| 异色标签 | 38 |
| 首领形态 | 27 |
| 进化链 | 165 |

## 当前数据状态

| 状态 | 标签 / 数据 | 说明 |
|------|-------------|------|
| 已整理可用 | 精灵、课题任务、进化链、异色炫彩、多形态、精灵果实、家具、遗迹 | 已有真实数据和对应前端展示；可继续日常勾选 |
| 结构可用但明细待补 | 商店/货币 | 36 个商店和 6 种货币已入库，商品明细未采集 |
| 只有示例/占位 | 服装、称号 | 前端和 JSON 结构已搭好，但 `clothing.json` / `titles.json` 仍主要是示例数据 |
| 有通用结构但无数据 | 星星、支线任务、扭蛋机、音乐 | Tab 使用 `collections.items`，当前 0 条 |
| 未建独立结构 | 通用外观、玩具 | 只有旧 `collections.categories` 总量占位；服装不等于完整外观图鉴 |

当前仍需人工采集的模板见 `data/_待采集/README.md`。

## 验证

```bash
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
node scripts/validate-random-task-ui.js
node scripts/validate-furniture-ui.js
node scripts/validate-clothing-ui.js
node scripts/validate-title-ui.js
node scripts/validate-dungeon-ui.js
node -e "for (const f of ['data/pets.json','data/tasks.json','data/evolution-chains.json','data/furniture.json','data/clothing.json','data/titles.json','data/dungeons.json','data/shops.json','data/collections.json']) JSON.parse(require('fs').readFileSync(f,'utf8')); console.log('json ok')"
```

如需验证本地服务：

```bash
node server.js
```

再访问 `http://localhost:8899`。
