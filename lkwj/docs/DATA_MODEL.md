# 洛克王国收集助手数据模型

本文档描述静态定义、用户进度和前端展示之间的边界。修改数据前先确认目标文件，不得从用户进度反向生成世界定义。

## 数据文件总览

| 文件 | 内容 | 数据性质 |
| --- | --- | --- |
| `data/pets.json` | 精灵名称、元素、形态、标签、果实 | 静态定义 |
| `data/tasks.json` | 世界图鉴课题任务 | 静态定义 |
| `data/evolution-chains.json` | 进化目标和条件 | 静态定义 |
| `data/furniture.json` | 家具名称、舒适度、灵感值 | 静态定义 |
| `data/clothing.json` | 服装规则、套装和部件 | 静态定义 |
| `data/titles.json` | 称号上下段和获取方式 | 静态定义 |
| `data/dungeons.json` | 遗迹副本、资源和孵化属性 | 静态定义 |
| `data/shops.json` | 商店入口和货币 | 静态定义 |
| `data/collections.json` | 用户任务、形态和收集进度 | 动态进度 |
| `data/wallet.json` | 用户货币持有量 | 动态数据，不提交 Git |
| `data/annotations.json` | 人工核对操作日志 | 动态数据，不提交 Git |

## 精灵、形态与标签

### `pets.json`

- 对象 key 使用 `pet_N`。
- `element` 必须是数组，双元素使用两个完整名称。
- `forms` 表示同一物种的外观变体，不表示进化阶段。
- 推荐形态键：`basic`、`spring`、`summer`、`autumn`、`winter`、`molting`、`leader`、`variant_N`。
- `tags` 保存 `shiny`（异色）、`chromatic`（炫彩）和 `boss`（首领）。标签与形态独立，可以共存。
- `obtainMethods` 只写直接获取方式，禁止写“由某精灵进化”。进化来源只写入 `evolution-chains.json`。
- `fruit` 是果实图鉴记录，不等于课题任务。

### 进化继承

进化只改变物种 ID，形态和标签默认继承。异色、炫彩或首领状态不得因为进化而丢失。

## 课题任务

### `tasks.json`

- 任务只来自 Excel 的 `课题进度` sheet。
- 同一宠物的所有形态共享任务进度，任务不按形态复制。
- `desc` 不包含宠物名称，名称由前端拼接。
- 支持的主要类型：`capture`、`capture_gifted`、`capture_chromatic`、`capture_shiny`、`fruit`、`skill`、`evolve`、`leader_evolve`、`destined_hero`、`affection`、`confirm_forms`。
- `capture_chromatic` 表示炫彩突变捕捉；`capture_shiny` 对应课题表中的异色行，两者不能混用。
- `fruit` 表示“捕捉指定数量获得果实”的课题任务。是否存在该任务只以 `课题进度` 为准，不能从果实图鉴反向生成。
- `confirm_forms.requiredForms` 只表示课题计入形态；完整形态收集由 `forms_collected` 独立维护。
- `destined_hero`、`fruit`、`confirm_forms` 不进入随机任务池。

### Excel 分组规则

Excel 合并单元格可能导致编号列错位。解析时必须以精灵名称列出现非空值作为新宠物分组边界，不能对编号列直接 forward-fill。

进化任务的条件属于进化前的宠物。没有进化任务的宠物应当是对应进化链的终点。

## 进化链

### `evolution-chains.json`

- 每条链包含 `chainId`、`baseSpeciesId` 和 `nodes`。
- `nodes[petId].evolvesTo` 保存目标物种和条件。
- 空 `evolvesTo` 表示链终点。
- `condition.note` 只写进化机制条件，例如技能次数、击败次数或成长星级；形态说明必须写入 `pets.forms`。
- 同一连续进化家族应位于同一条链；分支进化的每个分支必须保存自己的条件。

## 用户进度

### `collections.json`

- `sprite_progress[petKey].tasks`：课题完成状态。
- `sprite_progress[petKey].forms_collected`：完整形态收集状态。
- `sprite_progress[petKey].fruit_acquired`：果实是否获得。
- `shiny_progress`：异色收集状态，不由任务状态驱动。
- `furniture_progress`：家具是否收集。
- `clothing_progress`：服装标准部件是否收集。
- `title_progress`：称号是否收集。
- `dungeon_progress`：遗迹副本是否完成。
- `items[]`：星星、支线任务、扭蛋机和音乐的通用收集项。

静态定义中的数值、名称和规则不得写入进度对象。

## 家具

### `furniture.json`

- `id` 使用稳定的 `furniture_N`，只追加，不复用。
- `comfort` 为舒适度，未知时填 `0`。
- `inspiration` 为灵感值，用于计算未收集家具仍需灵感值。
- 第一版不保存来源、分类和尺寸。

## 服装

### 顶层结构

```json
{
  "definitions": {},
  "sets": [],
  "pieces": []
}
```

- `definitions` 保存华丽徽章和华丽魔法规则说明。
- `sets[]` 保存套装共享信息。
- `pieces[]` 保存最小勾选单位和付费参考组件。

### 套装字段

- `id` 使用稳定的 `clothing_set_N`，新增时只追加。
- `name` 使用游戏内名称。
- `requiredPieceCount` 是解锁华丽魔法所需的必需部件总数，以用户提供的游戏数值为准。
- 可解锁的付费组件数量不包含在 `requiredPieceCount` 内。
- `gorgeousMagicPetName` 为空表示当前资料未声明对应精灵。
- `obtainMethod` 未知时保留 `待补充`；前端不会显示该占位文本。

### 部件字段

- `id` 使用稳定的 `clothing_N`，新增时只追加。
- `collectionType="set"` 表示套装部件；`single` 表示独立单品。
- 套装部件必须提供 `setId`；独立单品不得提供 `setId` 和 `setRole`。
- `setRole="magic_required"` 表示华丽魔法必需部件；`optional` 表示不计入解锁件数的额外组件。
- `obtainType="standard"` 表示个人收集目标；`paid` 表示付费非目标资料。
- 所有付费额外组件通过积分卡解锁，只用于浏览，不进入目标数量、完成率或 `collections.clothing_progress`。
- `hasEffect` 只有明确为 boolean 时才显示“有/无”；字段缺失表示未知。

允许的分类：

- `玩偶服/连衣`
- `上衣`
- `下装`
- `头饰/帽子`
- `发型`
- `手饰`
- `面饰`
- `鞋子`
- `袜子`
- `背包`
- `包挂饰`
- `法杖`
- `华丽徽章`

### 已确认命名规则

- 服装侧使用“魔草巫灵”，不与果实阶段名称联动。
- 异色套装统一保留“印象”后缀。
- “追忆”和“回忆”可能是不同单品，不按近似名称自动合并。
- `初始发型1`、`初始发型2`、`初始发型3`、`面妆1` 至 `面妆8` 就是正式名称，均为系统默认新手独立单品。
- 不能仅凭名称近似自动归套装；套装名称匹配且必需件数吻合后才能归并。

### 日常补录流程

随机商店未刷新时只能知道套装总件数，不能猜测具体部件。用户提供刷新出的部件名称后：

1. 根据名称归入已存在套装或独立单品。
2. 新部件默认 `obtainType="standard"`、`setRole="magic_required"`。
3. 只有用户明确说明购买时才更新 `collections.clothing_progress`。
4. 运行服装数据和 UI 校验。
5. 同步 README 数量和 `tasks/todo.md` 的缺件状态。

## 称号

### `titles.json`

- `id` 使用稳定的 `title_N`。
- 页面按 `upper · lower` 显示。
- 单段称号全部写入 `upper`，`lower` 留空。
- `collections.title_progress` 只保存是否收集。

## 遗迹副本

### `dungeons.json`

- `id` 使用稳定的 `dungeon_N`。
- `resources` 保存可汇总的资源数量。
- `rewards` 只保存钥匙等非数值特殊掉落。
- 精灵蛋数量写入 `resources.spiritEggs`，孵化属性写入 `eggHatches`。
- `eggHatches` 可保存血脉、外观、性格、性格效果和成长项。
- 前端按副本整体勾选，不拆奖励单项进度。

## 商店和通用品类

- `shops.json` 当前保存商店入口和货币类型，商品明细仍待补。
- 星星、支线任务、扭蛋机和音乐复用 `collections.items[]`。
- 通用外观和玩具尚未建立独立模型。

## 验证

所有验证命令统一维护在项目 `README.md`。服装必需部件名称少于 `requiredPieceCount` 时会输出 warning；这是资料待补状态，不是结构错误。结构错误必须以非零退出码阻止提交。
