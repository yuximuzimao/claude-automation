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
| `SKILL.md` | Agent 入口地图、命令速查和必须遵守的边界 |
| `docs/INDEX.md` | 项目文档索引 |
| `docs/DATA_MODEL.md` | 静态定义、用户进度和各收集品类的数据边界 |
| `docs/REVIEW_CHECKLIST.md` | 对照 Excel 做只读核对的清单 |
| `docs/archive/` | 已完成阶段的决策与数据基线归档 |
| `tasks/todo.md` | 所有尚未补齐、待核对和待规划的数据任务 |

## 数据边界

- `pets.json` 保存世界定义，不能从用户进度反向生成。
- `tasks.json` 只保存世界图鉴课题任务，任务来源只能是 Excel `课题进度` sheet；`异色` 行作为 `capture_shiny` 任务纳入，并固定挂在最终进化形态。存在异色标签不代表自动存在异色任务，通行证异色没有 `capture_shiny`。
- `collections.json` 保存用户勾选进度，包括 `sprite_progress[petKey].forms_collected` 和 `fruit_acquired`。
- `confirm_forms.requiredForms` 只声明课题计入的形态；完整多形态收集独立显示在「多形态」Tab。精灵任务行提供“去多形态”跳转，会自动筛选、展开并定位对应精灵。
- `fruit` 任务是“精灵果实课题任务”，不是果实图鉴。有果实不代表有 fruit 任务。
- `shiny_progress` 是异色收集进度，不由任何 task 状态驱动。异色多形态精灵只按实际可收集形态拆分，`basic` 不额外计数；无额外形态时使用 `petKey`，形态项使用 `petKey::formKey`。旧多形态 `petKey` 进度需人工确认后迁移。
- 异色页沿用现有赛季筛选：S3 常驻/奇遇使用 `S3「铅字幻梦」`，通行证使用 `S3通行证`。
- 精灵、多形态、遗迹和服装套装在搜索与其他筛选后只剩一个卡片时自动展开；多结果保持折叠。
- `furniture.json` 保存家具定义；`collections.furniture_progress` 只保存是否收集，不能把舒适度/灵感值写进进度。
- 家具 Tab 顶部只展示总件数、已收集件数和未收集家具的剩余灵感值；舒适度和单件灵感值只在列表行展示。
- `clothing.json` 分为 `definitions`、`sets[]` 和 `pieces[]`：规则说明写在 `definitions`，套装必需部件数、华丽魔法对应精灵和套装获取方式写在 `sets[]`，最小收集单元及其分类、套装角色、获取类型和获取方式写在 `pieces[]`。
- 服装个人目标只包含 `obtainType="standard"` 的部件；`obtainType="paid"` 的积分卡额外组件可以浏览，但不进入目标数量、完成进度或 `collections.clothing_progress`。
- `requiredPieceCount` 以游戏内套装件数为准，不包含 `setRole="optional"` 的付费额外组件；华丽魔法进度只根据 `magic_required` 必需部件自动计算。
- 套装名称匹配且必需件数吻合后才能归套装。随机商店补录先对本次输入去重，再按完整名称全局查重；主号和小号信息合并，不记录账号来源。新部件默认未收集，只有明确购买/已收集时才更新指定进度，已有部件未被指定时保留原状态。
- 服装页的“信息缺失”筛选显示已记录必需部件数少于 `requiredPieceCount` 的套装；这些套装也保留在“未收集”筛选中，便于集中查找和补录。完整流程见 `docs/DATA_MODEL.md`。
- 缺失 `hasEffect` 表示资料未知，不能显示为“无特效”。完整服装命名和补录规则见 `docs/DATA_MODEL.md`。
- `titles.json` 保存称号定义；页面按 `上段 · 下段` 显示一条称号，并展示获取方式；`collections.title_progress` 只保存是否收集。
- `dungeons.json` 保存遗迹副本定义、资源数量、钥匙类特殊掉落和精灵蛋孵化属性；`collections.dungeon_progress` 只保存是否完成。
- `shops.json` 已保存商店入口和货币类型；商品明细尚未建入 JSON，后续补充要求统一维护在 `tasks/todo.md`。
- `collections.items` 是星星、支线任务、扭蛋机、音乐的通用收集项入口；当前为空。

## 当前关键数量

| 项目 | 数量 |
| --- | ---: |
| 精灵 | 439 |
| 课题任务 | 1895 |
| 精灵果实课题任务 | 96 |
| 果实图鉴记录 | 143 |
| 多形态收集项 | 143 |
| 家具 | 191 |
| 家具已收集 | 133 |
| 家具未收集 | 58 |
| 家具剩余灵感值 | 1506950 |
| 服装套装 | 85 |
| 服装部件 | 432 |
| 服装个人目标 / 已拥有 | 284 / 257 |
| 服装付费非目标 | 148 |
| 必需部件名称待补套装 | 53 |
| 称号 | 1 |
| 遗迹副本 | 26 |
| 遗迹孵化属性 | 26 |
| 商店入口 | 36 |
| 商店货币类型 | 6 |
| 通用品类收集项 | 0 |
| 有额外形态的精灵 | 53 |
| 异色最终形态标签 | 48 |
| 异色收集项（含形态拆分） | 49 |
| 首领形态 | 27 |
| 进化链 | 191 |

## 当前数据状态

| 状态 | 标签 / 数据 | 说明 |
|------|-------------|------|
| 已整理可用 | 既有精灵课题、异色炫彩、多形态、精灵果实、家具、遗迹 | 已有真实数据和对应前端展示；可继续日常勾选 |
| 基础资料已入库、任务待补 | S3 三批图片资料 | 第一批录入 18 只、第二批录入 16 只、第三批录入 30 只，共新增 64 只精灵；第三批另给梦游补“穿星星睡衣的样子”，给丢丢、卡卡虫、卡瓦重补“火山附近的样子”。第二、三批暂按 `pet_440–485` 连续占位，等待最新 Excel 统一核对正式编号、课题、精确进化条件、果实和个人进度 |
| 真实数据可用、明细持续补充 | 服装 | 已导入 85 套、432 个部件；284 个个人目标中已拥有 257 个，148 个积分卡组件仅展示。53 套尚缺完整必需部件名称，随机商店刷新后继续按实际名称补录 |
| 结构可用但明细待补 | 商店/货币 | 36 个商店和 6 种货币已入库，商品明细未采集 |
| 只有示例/占位 | 称号 | 前端和 JSON 结构已搭好，但 `titles.json` 仍主要是示例数据 |
| 有通用结构但无数据 | 星星、支线任务、扭蛋机、音乐 | Tab 使用 `collections.items`，当前 0 条 |
| 未建独立结构 | 通用外观、玩具 | 只有旧 `collections.categories` 总量占位；服装不等于完整外观图鉴 |

所有未完成的数据补录与规划统一见 `tasks/todo.md`；项目不再维护 `_待采集` CSV 模板目录。

## 验证

```bash
node scripts/validate-s3-partial-pets.js
node scripts/validate-s3-image-batch2.js
node scripts/validate-s3-image-batch3.js
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
node scripts/validate-shiny-ui.js
node scripts/validate-search-expand-ui.js
node scripts/validate-random-task-ui.js
node scripts/validate-furniture-ui.js
node scripts/validate-clothing-data.js
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
