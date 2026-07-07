# 洛克王国 · 收集助手 SKILL.md

> 导航地图，先读地图再走路。

## ENTRY MAP

| 目标 | 入口 |
|------|------|
| 启动本地服务 | `node server.js`（端口 8899） |
| 打开界面 | 浏览器访问 `http://localhost:8899` |
| 人类快速接入 | `README.md` |
| 修改收集进度 | 直接编辑 `data/collections.json` 或通过 UI 勾选 |
| 后续待办 | `tasks/todo.md` |
| **人工核对任务/宠物数据** | 浏览器访问 `http://localhost:8899/review.html` |
| 多形态数据/UI 验证 | `node scripts/validate-multiform-data.js` + `node scripts/validate-multiform-ui.js` |
| 宠物定义 | `data/pets.json`（对象 key="pet_N"；数量以 `README.md` 当前关键数量和 JSON 实测为准） |
| 任务定义 | `data/tasks.json`（按 pet ID 索引，form-independent；数量以 `README.md`/JSON 实测为准） |
| 进化链 | `data/evolution-chains.json`（链数量和覆盖率以 `README.md`/JSON 实测为准） |
| 家具定义 | `data/furniture.json`（数组；名称、舒适度、灵感值） |
| 服装定义 | `data/clothing.json`（对象；`sets[]` 保存套装共享信息，`pieces[]` 保存单件收集项） |
| 称号定义 | `data/titles.json`（数组；名称分段、获取方式） |
| 遗迹副本定义 | `data/dungeons.json`（数组；副本名称、位置、资源数量、特殊掉落、精灵蛋孵化属性） |
| 用户进度 | `data/collections.json`（sprite_progress + shiny_progress + furniture_progress + clothing_progress + title_progress + dungeon_progress） |
| 商店与货币 | `data/shops.json`（36 商店+6 货币）+ `data/wallet.json` |
| 标注数据 | `data/annotations.json`（append-only ops 日志，Claude 批量处理用） |
| 数据采集需求 | `data/_待采集/README.md`（只保留仍需补齐的服装、称号、商店商品、地区形态名称、通用品类） |
| 数据修正 | `scripts/fix-shiny-and-chains.js`（异色/炫彩标签修正、进化链传播） |

## DO FIRST

进入本项目时：
1. 确认 server 是否已运行：`lsof -ti :8899`（有输出=已运行）
2. 若未运行：`node server.js &`
3. 核心数据文件：`data/pets.json` + `data/tasks.json` + `data/evolution-chains.json` + `data/furniture.json` + `data/clothing.json` + `data/titles.json` + `data/dungeons.json` + `data/shops.json` + `data/collections.json`

## PATHS

```
lkwj/
├── README.md                  # 人类快速接入：运行方式、数据边界、验证命令
├── server.js                  # HTTP 服务器，端口 8899
├── index.html                 # 单页 App：看板 + 精灵图鉴 + 异色炫彩 + 多形态 + 精灵果实 + 家具 + 服装 + 称号 + 星星 + 遗迹 + 支线 + 扭蛋 + 音乐；全部收集类 Tab 布局统一（标题→统计→搜索→筛选→内容）
├── review.html                # 人工核对工具：精灵/任务/形态标注 + 进化链核对，两栏布局
├── scripts/
│   ├── fix-shiny-and-chains.js       # 异色/炫彩标签修正 + 进化链传播
│   ├── validate-multiform-data.js    # 多形态 requiredForms / forms 数据约束验证
│   ├── validate-multiform-ui.js      # 多形态 Tab / 随机模块静态结构验证
│   ├── validate-furniture-ui.js      # 家具独立数据模型 + UI 验证
│   ├── validate-clothing-ui.js       # 服装单件模型 + UI 验证
│   ├── validate-title-ui.js          # 称号模型 + UI 验证
│   └── validate-dungeon-ui.js        # 遗迹副本模型 + UI 验证
│   └── data-compare-report.html      # Excel vs JSON 数据对比报告（2026-07-02）
└── data/
    ├── pets.json              # 宠物定义：形态 + 标签 + 元素数组（数量以 README.md/JSON 实测为准）
    ├── tasks.json             # 任务定义：form-independent，desc 不含宠物名（数量以 README.md/JSON 实测为准）
    ├── evolution-chains.json  # 进化链：独立于形态（链数量/覆盖率以 README.md/JSON 实测为准）
    ├── furniture.json         # 家具定义：数组，保存名称/舒适度/灵感值
    ├── clothing.json          # 服装定义：对象，sets[] 保存套装共享信息，pieces[] 保存单件收集项
    ├── titles.json            # 称号定义：数组，保存名称分段/获取方式
    ├── dungeons.json          # 遗迹副本定义：数组，保存名称/位置/资源数量/特殊掉落/精灵蛋孵化属性
    ├── collections.json       # 用户进度：sprite_progress + shiny_progress + furniture_progress + clothing_progress + title_progress + dungeon_progress
    ├── shops.json             # 商店清单：36 商店 × 6 货币
    ├── wallet.json            # 用户货币持有量（dynamic，不提交 git）
    ├── annotations.json       # 标注日志（append-only ops，不提交 git）
    └── _待采集/               # 仍需人工补齐的数据模板；已导入 JSON 的旧模板不保留
```

## 数据模型

### pets.json — 宠物定义（静态）

```json
{
  "pet_18": {
    "name": "雪绒鸟",
    "element": ["翼"],
    "forms": {
      "basic":  { "formName": "本来的样子", "obtainMethods": ["商店街周边"] },
      "spring": { "formName": "春天的样子", "obtainMethods": [] },
      "summer": { "formName": "夏天的样子", "obtainMethods": [] },
      "autumn": { "formName": "秋天的样子", "obtainMethods": [] }
    },
    "tags": {
      "shiny": { "tagName": "异色", "limitedTime": "第一赛季" },
      "chromatic": { "tagName": "炫彩" },
      "boss": { "tagName": "首领" }
    },
    "pinyin": { "full": "xuerongniao", "initial": "xrn" },
    "fruit": { "name": "雪绒鸟果实", "acquired": false, "obtainMethod": "捕捉20只岚鸟", "obtainType": "课题任务" }
  }
}
```

字段说明：
- `name` — 宠物中文名
- `element` — 元素数组（支持双元素），如 `["光"]` 或 `["幽", "恶"]`
- `forms` — 形态定义，使用语义键名（`basic`, `spring`, `summer`, `autumn`, `winter`, `molting`, `leader`, `variant_N`）
- `tags` — 稀有度标签（`shiny`, `chromatic`, `boss`）。标签独立于形态，进化时保留
- `pinyin` — 拼音（全拼 + 首字母），用于搜索
- `fruit` — 果实信息（可选，143 只精灵有此字段，7 只无果实家族不含）
  - `name`: 果实名称
  - `acquired`: 是否已获得（boolean）
  - `obtainMethod`: 具体获取方式（来自 Excel 果实进度 D 列）
  - `obtainType`: 获取方式分类（课题任务/智慧树苗/剧情任务/通行证契约礼券/赛季作业/限时活动）
  - `exclusiveGroup`（可选）: 互斥组 ID（starter_gen1/2, pass_s{N}）——同赛季通行证二选一，御三家三选一
- `destined_hero` — 命定勇者标记（可选）
- `notes` — 备注

### tasks.json — 任务定义（静态）

```json
{
  "pet_20": [
    { "type": "capture", "desc": "捕捉1只" },
    { "type": "capture_gifted", "desc": "捕捉1只了不起天分的" },
    { "type": "skill", "desc": "使用", "skillName": "龙卷风", "count": 3 },
    { "type": "fruit", "desc": "捕捉20只精灵" },
    { "type": "confirm_forms", "desc": "确认4种不同样子的岚鸟", "count": 4, "requiredForms": ["本来的样子", "秋天的样子", "春天的样子", "夏天的样子"] },
    { "type": "leader_evolve", "desc": "进化为首领形态" }
  ]
}
```

任务类型（11 种）：`capture`, `capture_gifted`, `capture_chromatic`(炫彩突变), `capture_shiny`(异色突变), `fruit`(精灵果实课题任务：捕捉 20 只获得果实，仅课题任务类型的果实有此任务), `skill`, `evolve`, `leader_evolve`, `destined_hero`, `affection`, `confirm_forms`

关键规则：
- 任务是**形态无关**的——同一宠物所有形态共享同一份任务进度
- 任务只来自 Excel `课题进度` sheet；`异色` 行作为 `capture_shiny` 任务纳入；`果实进度`、`多形态进度`、`forms.*.obtainMethods` 只能补已有任务的达成方式，不能反向生成任务
- `desc` 不含宠物名，前台拼接（如 "岚鸟" + "使用" + "龙卷风" + "3" + "次"）
- skill 类任务额外提供 `skillName` 和 `count`
- `confirm_forms.requiredForms` 只表示课题计入形态；全形态收集状态独立保存在 `collections.sprite_progress[petKey].forms_collected`
- `capture_chromatic` 对应炫彩突变捕捉（所有精灵除迪莫外都有炫彩），与异色（tags.shiny）无关
- `fruit` 说人话是“精灵果实课题任务”，不是“果实图鉴”。有果实不代表有 fruit 任务；有 fruit 任务一定有果实

### evolution-chains.json — 进化链（静态）

```json
{
  "chainId": 41,
  "baseSpeciesId": "pet_41",
  "nodes": {
    "pet_41": { "evolvesTo": [{ "toSpeciesId": "pet_42", "condition": { "type": "level", "level": 16 } }] },
    "pet_42": { "evolvesTo": [{ "toSpeciesId": "pet_43", "condition": { "type": "level", "level": 32 } }] },
    "pet_43": { "evolvesTo": [] }
  }
}
```

- 链数量、覆盖率和幽灵节点检查以 JSON 实测/README 当前关键数量为准；改 `pets.json` 或 `evolution-chains.json` 后必须同步验证
- 条件类型：`level`（等级，含可选 `note` 字段描述附加条件如"使用15次流星火雨"）
- 空 `evolvesTo` = 链终点

### Excel → JSON 数据映射规则（AI 模型必读）

> **从 Excel「图鉴课题进度表」更新 JSON 数据时必须遵守的对应关系。违反任一条都会产生数据错位。**

#### 1. Excel 解析规则：用名称列做分组边界

Excel 的 `精灵编号`(A列) 在合并单元格错位时会显示错误编号（如 pet_348 区域的 N.349/N.350 错位），**必须以 `精灵名称`(B列) 作为分组边界**。

```
正确做法：当 B列出现非空名称时 → 新宠物开始
错误做法：用 A列精灵编号 forward-fill 分组（合并单元格会产生编号错位）
```

#### 2. 进化条件归属规则

Excel `课题进度` sheet 中，pet_X 的「进化」任务 + `备注`列 = **pet_X 进化到 pet_X+1 的条件**。

```
Excel: pet_348 钨丝贝贝 → [进化] 备注="28级+精灵成长至1星进化"
JSON:  evolution-chains.json → nodes["pet_348"].evolvesTo[0].condition
      { "type": "level", "level": 28, "note": "精灵成长至1星" }
      目标: toSpeciesId = "pet_349" (辉光幕机)
```

**条件属于进化前的宠物，不属于进化后的宠物。**

#### 3. 最终形态判断

进化链末端的宠物 **没有进化任务**。判断方法：
- 该宠物在 Excel 课题进度 sheet 中无「进化」类型的行 → 最终形态
- evolution-chains.json 中 `evolvesTo: []` → 链终点

```
例: pet_350 机幕方舟 → 无进化任务 (最终形态)
例: pet_353 凡鹰 → 无进化任务 (最终形态)
```

#### 4. 进化条件 note 与形态数据的边界

`cond.note` **只放进化机制本身的条件**（等级、击败次数、使用技能、道具等）。形态相关的描述放在 `pets.json` 的 `forms` 中。

```
❌ 错误: cond.note = "(4形态随机)" → 形态信息应放在 pet_34 化蝶的 forms 数据中
❌ 错误: cond.note = "(睁闭眼看时间)" → 形态信息应放在 pet_55 暗影灵面的 forms 中
✅ 正确: cond.note = "击败光系精灵3次" → 这是进化机制条件
✅ 正确: cond.note = "精灵成长至1星" → 这是进化机制条件
```

#### 5. 已知数据错位模式

| 模式 | 案例 | 修复 |
|------|------|------|
| 条件误挂到下一级 | pet_328 有"使用3次勾魂"但实际属于 pet_327 | 核对 Excel 备注，条件归位到正确宠物 |
| 进化链拆分 | pet_15→pet_16 和 pet_16→pet_17 分属不同 chain | 同一进化链的宠物应合并到一条 chain |
| 分支进化条件全覆盖 | pet_280 全部3个分支用同一 note | 每个分支独立设 note 描述该分支条件 |

#### 6. 前端渲染对应

前端 3 处渲染进化条件，都必须包含 `cond.note`：

| 位置 | 格式 |
|------|------|
| 精灵卡片进化链 | `(Lv28, 击败光系精灵3次)` |
| 进化任务获取方式 | `28级击败光系精灵3次进化为No.324 XXX` |
| 捕捉来源进化描述 | `28级击败光系精灵3次进化获得` |

#### 7. 数据校验清单

更新进化数据后必须验证：
- [ ] 有「进化」任务的 pet_X 在 evolution-chains.json 中有 `evolvesTo` 且 condition.level > 0
- [ ] 无「进化」任务的 pet_X 在 evolution-chains.json 中 `evolvesTo` 为空
- [ ] condition.level 数值与 Excel 备注中的等级一致
- [ ] condition.note 不含形态相关信息（如"随机"、"样子"等形态描述词）
- [ ] 同一进化链的三段（如有）在同一 chain 内，非独立 chain
- [ ] 分支进化的每个分支有其独立的 condition

### collections.json — 用户进度（动态）

```json
{
  "meta": { "last_updated": "2026-05-21", "game": "洛克王国世界" },
  "categories": { "精灵": { "total": 347, "owned": 304 }, ... },
  "items": [...],
  "sprite_progress": {
    "pet_1": { "tasks": { "0": true, "1": true } },
    "pet_18": { "forms_collected": ["basic", "spring"] }
  },
  "shiny_progress": { "pet_5": true, "pet_18": false },
  "furniture_progress": { "furniture_1": true },
  "clothing_progress": { "clothing_1": true },
  "title_progress": { "title_1": true },
  "dungeon_progress": { "dungeon_1": true }
}
```

- `sprite_progress` — 按 pet ID 索引，`tasks` 为任务完成状态，`forms_collected` 为已收集形态，`fruit_acquired` 为果实已获得状态（boolean）
- `shiny_progress` — 按 pet ID 索引的异色收集状态（0/1）
- `furniture_progress` — 按 furniture ID 索引的家具收集状态（boolean）
- `clothing_progress` — 按 clothing ID 索引的单件服装收集状态（boolean）
- `title_progress` — 按 title ID 索引的称号收集状态（boolean）
- `dungeon_progress` — 按 dungeon ID 索引的遗迹副本完成状态（boolean）
- `items[]` — 星星、支线任务、扭蛋机、音乐的通用品类收集项，家具/服装/称号/遗迹不走此字段

### furniture.json — 家具定义（静态）

```json
[
  { "id": "furniture_1", "name": "木质衣柜", "comfort": 300, "inspiration": 1200 }
]
```

- `id` — 稳定主键，格式 `furniture_N`，新增家具只追加不复用 ID
- `name` — 游戏内家具名称
- `comfort` — 舒适度数值，未知时填 `0`
- `inspiration` — 灵感值数值，用于前端统计未收集家具还差多少灵感值；顶部不展示总灵感值
- 第一版不保存分类、来源、尺寸；后续确有需要再扩展静态定义，不写入进度数据

### clothing.json — 服装定义（静态）

```json
{
  "sets": [
    {
      "id": "clothing_set_1",
      "name": "木之本樱魔法装扮",
      "hasEffect": true,
      "pairedPetName": "小可",
      "obtainMethod": "洛克王国 x 魔卡少女樱联动活动；待游戏内图鉴核对"
    }
  ],
  "pieces": [
    {
      "id": "clothing_1",
      "collectionType": "set",
      "setId": "clothing_set_1",
      "pieceName": "发型"
    },
    {
      "id": "clothing_6",
      "collectionType": "single",
      "pieceName": "独立服装样例",
      "hasEffect": false,
      "pairedPetName": "",
      "obtainMethod": "待补充"
    }
  ]
}
```

- `sets[].id` — 套装稳定主键，格式 `clothing_set_N`，新增套装只追加不复用 ID
- `sets[].name` — 套装名称
- `sets[].hasEffect` — 套装是否带特效
- `sets[].pairedPetName` — 套装带特效时对应配对精灵名称；没有或未知可留空
- `sets[].obtainMethod` — 套装获取方式，未知时填 `待补充`
- `pieces[].id` — 单件稳定主键，格式 `clothing_N`，新增单件只追加不复用 ID
- `pieces[].collectionType` — `set` 表示套装部件，`single` 表示独立单件
- `pieces[].setId` — 所属套装 ID；`collectionType` 为 `single` 时不填
- `pieces[].pieceName` — 单件服装名称或部件名称
- 独立单件可直接在 `pieces[]` 写 `hasEffect`、`pairedPetName`、`obtainMethod`
- 前端以单件为最小勾选单位；套装信息只在套装标题下显示，不在每个部件行重复显示

### titles.json — 称号定义（静态）

```json
[
  { "id": "title_1", "upper": "百分之零", "lower": "魔法师", "obtainMethod": "待补充" }
]
```

- `id` — 稳定主键，格式 `title_N`，新增称号只追加不复用 ID
- `upper` — 称号前段，用于和 `lower` 拼成页面主名称
- `lower` — 称号后段，用于和 `upper` 拼成页面主名称
- `obtainMethod` — 获取方式，未知时填 `待补充`
- 前端只显示一条主称号，格式为 `upper · lower`；不单独展示分段统计

### dungeons.json — 遗迹副本定义（静态）

```json
[
  {
    "id": "dungeon_1",
    "name": "遗迹副本样例",
    "location": "风眠省",
    "rewards": ["地之钥"],
    "resources": {
      "gameCoins": 22,
      "spiritEggs": 1,
      "owlStars": { "color": "blue", "amount": 1 },
      "chests": 1,
      "searchPoints": 1,
      "prismaticCrystals": 120,
      "regionalCurrency": { "name": "独角兽银币", "amount": 150 }
    },
    "eggHatches": [
      {
        "petName": "精灵名",
        "bloodline": "冰",
        "appearance": "外观名",
        "nature": "固执",
        "natureEffect": "+攻击-魔攻",
        "growths": ["生命", "攻击", "速度"]
      }
    ]
  }
]
```

- `id` — 稳定主键，格式 `dungeon_N`，新增副本只追加不复用 ID
- `name` — 副本名称
- `location` — 副本所在位置；只有地区、没有具体坐标时先填地区名，如 `风眠省`
- `rewards` — 特殊掉落文本数组，只放钥匙等不适合做数值汇总的非精灵蛋项目；精灵蛋数量写入 `resources.spiritEggs`，孵化信息写入 `eggHatches`
- `resources.gameCoins` — 游戏币数量
- `resources.spiritEggs` — 精灵蛋数量
- `resources.owlStars` — 眠枭之星数量与颜色，`color` 为 `blue` 或 `yellow`
- `resources.chests` — 宝箱数量
- `resources.searchPoints` — 翻找点数量
- `resources.prismaticCrystals` — 分光水晶数量，包含宝箱来源
- `resources.regionalCurrency` — 地区货币；风眠省为 `独角兽银币`，洛克里安为 `王国徽记`
- `eggHatches` — 精灵蛋孵化属性数组；一个副本/精灵蛋有多种血脉、外观或成长组合时写多条
- `eggHatches[].petName` — 孵化精灵名
- `eggHatches[].bloodline` — 血脉获取标注，可选；不是物种形态
- `eggHatches[].appearance` — 外观形态/颜色补充，可选
- `eggHatches[].nature` — 性格名称
- `eggHatches[].natureEffect` — 性格数值倾向，如 `+攻击-魔攻`
- `eggHatches[].growths` — 成长项数组；`双防` 拆为 `物防`、`魔防`
- 第一版不拆奖励完成状态；前端按副本整体勾选

## 核心设计原则

### 形态 (form) = 同一物种的外观变体
- 季节形态、地区形态、蜕皮形态属于 forms，不是进化链
- 语义键名列表：`basic`, `spring`, `summer`, `autumn`, `winter`, `molting`, `leader`
- `leader` = 首领进化形态，formName 为首领名（如"鸭吉吉国王"）
- 迁移阶段的中文占位键名需在游戏中确认后改为语义键
- 新增 form key 前先在本文档约定

### 标签 (tag) = 稀有度标记
- `shiny`(异色)、`chromatic`(炫彩)、`boss`(首领)
- 多标签可共存（如异色+炫彩+首领）
- 标签独立于形态

### ★ 进化继承规则 ★
> **进化仅改变 speciesId，form 与 tag 默认继承。**
> 异色奇丽草进化 → 异色奇丽叶。首领奇丽草进化 → 首领奇丽叶。
> 这是整个系统最核心的世界规则。

### 数据源不交叉
- `collections.json` = 进度状态（有/没有）
- `pets.json` = 世界观定义（静态数据）
- `furniture.json` = 家具定义（静态数据）
- `clothing.json` = 服装定义（静态数据）
- `titles.json` = 称号定义（静态数据）
- `dungeons.json` = 遗迹副本定义（静态数据）
- `shops.json` = 商店入口和货币定义（静态数据，商品明细待补）
- **禁止从 collection 反向生成定义数据**

### 获取方式
- `obtainMethods` 只写直接获取方式，禁止"由 XX 进化"
- 进化来源在 evolution-chains.json 中
- `obtainMethods` 是任务达成方式，不是任务来源；只能补到已存在于 `课题进度` 的任务上

## 数据约束

- **捕捉类任务获取方式（引用机制）**：capture/capture_gifted/capture_chromatic/capture_shiny/fruit 五种任务的 obtainMethods **不存在 tasks.json 中**，前端通过 `getCaptureObtainMethods(petKey)` 动态解析，链路：`pets.json forms.basic.obtainMethods` → 进化链上游兜底（`No.{num} {name} {level}级进化获得`）。改获取方式只需改 pets.json 一处。覆盖率 372/373（仅 pet_353 凡鹰无捕捉任务，不适用）
- **evolve 类任务归属**：leader_evolve/evolve 只需挂在进化前的 pet 上（form-independent）
- **capture_chromatic ≠ capture_shiny**：`capture_chromatic` 是炫彩突变捕捉任务（所有精灵除迪莫外都有），`capture_shiny` 是 Excel `课题进度` 中 `异色` 行对应的异色突变捕捉任务
- **异色炫彩展示**：由 `pets.json` 的 `tags.shiny` 驱动，仅展示进化最终形态（标签随进化传递）
- **异色炫彩进度**：独立统计于 `collections.shiny_progress`，不由任何 task 状态驱动
- **异色必有限定时间**：`tags.shiny.limitedTime` 不可为"可获取"，异色均为赛季/通行证/活动限定
- **炫彩标签**：所有精灵（除迪莫外）均有 `tags.chromatic`
- **随机任务排除**：`destined_hero`、`fruit`、`confirm_forms` 任务类型不出现在随机池
- **随机任务进化约束**：capture 任务需先完成，fruit(原 capture20) 需 capture 先完成
- **果实任务边界**：fruit 任务以 `课题进度` sheet 的“果实”课题行为准；`果实进度` 是家族级果实记录/获取方式来源，不是任务清单
- **多形态收集边界**：`pets.forms` 保存全部可收集形态；前端「多形态」Tab 独立勾选 `forms_collected`；`confirm_forms` 任务只引用 `requiredForms` 自动判断是否完成
- **家具收集边界**：`furniture.json` 保存名称/舒适度/灵感值；`collections.furniture_progress` 只保存是否已收集。Tab 支持关键词搜索 + 全部/未收集/已收集筛选，顶部显示总件数、已收集件数和未收集家具剩余灵感值；第一版不建来源、分类、尺寸字段。
- **服装收集边界**：`clothing.json` 的 `sets[]` 保存套装共享信息（获取方式、特效、配对精灵），`pieces[]` 保存最小收集单位。`collections.clothing_progress` 只保存单件是否已收集。Tab 采用精灵卡片模式：套装=可展开卡片（显示部件进度 N/M），单品=简单行；套件和单品混合展示，支持关键词搜索 + 套装/单件类型筛选 + 进度筛选。
- **称号收集边界**：`titles.json` 保存名称分段和获取方式；`collections.title_progress` 只保存是否已收集。Tab 支持关键词搜索 + 全部/未收集/已收集筛选，页面显示 `上段 · 下段` 格式主称号。
- **遗迹副本边界**：`dungeons.json` 保存副本名称、位置、资源数量、特殊掉落和精灵蛋孵化属性；`collections.dungeon_progress` 只保存副本是否完成。Tab 支持关键词搜索 + 全部/未收集/已收集筛选，第一版不拆奖励单项收集。
- **通用品类边界**：星星、支线任务、扭蛋机、音乐复用 `collections.items[]`；当前只有 Tab 结构，真实条目从 `data/_待采集/通用品类收集项.csv` 导入。通用外观、玩具尚未建立独立数据模型。

## 当前数据状态

| 状态 | 数据 |
|------|------|
| 已整理可用 | 精灵、课题任务、进化链、异色炫彩、多形态、精灵果实、家具、遗迹 |
| 结构可用但明细待补 | 商店/货币（36 商店 + 6 货币，商品明细缺失） |
| 只有示例/占位 | 服装、称号 |
| 有通用结构但无数据 | 星星、支线任务、扭蛋机、音乐 |
| 未建独立结构 | 通用外观、玩具 |

## 已知数量

数量统计不在 SKILL 内重复维护；以 `README.md` 的「当前关键数量」和 JSON 实测为准。修改数据后先运行 README 的验证命令，再同步 README。

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/pets` | 宠物定义 |
| `GET /api/tasks` | 任务定义 |
| `GET /api/evolution-chains` | 进化链 |
| `GET /api/furniture` | 家具定义 |
| `GET /api/clothing` | 服装定义 |
| `GET /api/titles` | 称号定义 |
| `GET /api/dungeons` | 遗迹副本定义 |
| `GET /api/game-data` | 合并数据（pets+tasks+chains+furniture+clothing+titles+dungeons+progress） |
| `GET /api/data` | 原始 collections.json |
| `POST /api/save` | 保存 collections.json |
| `GET /api/wallet` | 钱包数据 |
| `POST /api/wallet` | 保存钱包 |
| `GET /api/annotations` | 标注日志（返回 `{meta,ops[]}`，文件不存在则返回空结构） |
| `POST /api/annotations` | 保存标注日志（body = 完整 JSON 替换写入） |

## 待完成

待办不在 SKILL 内重复维护；当前未完成项以 `tasks/todo.md` 为准。历史完成记录只在需要追溯时查 git 历史或相关变更文档。
