# 洛克王国 · 收集助手 SKILL.md

> 导航地图，先读地图再走路。

## ENTRY MAP

| 目标 | 入口 |
|------|------|
| 启动本地服务 | `node server.js`（端口 8899） |
| 打开界面 | 浏览器访问 `http://localhost:8899` |
| 修改收集进度 | 直接编辑 `data/collections.json` 或通过 UI 勾选 |
| 宠物定义 | `data/pets.json`（355 宠物，对象 key="pet_N"） |
| 任务定义 | `data/tasks.json`（按 pet ID 索引，form-independent） |
| 进化链 | `data/evolution-chains.json`（162 链，含 9 分支链） |
| 用户进度 | `data/collections.json`（sprite_progress + shiny_progress） |
| 商店与货币 | `data/shops.json`（36 商店+6 货币）+ `data/wallet.json` |
| 数据采集需求 | `data/_待采集/README.md` |
| 迁移脚本 | `scripts/migrate-*.js`（从 sprites.json 迁移到新格式） |

## DO FIRST

进入本项目时：
1. 确认 server 是否已运行：`lsof -ti :8899`（有输出=已运行）
2. 若未运行：`node server.js &`
3. 核心数据文件：`data/pets.json` + `data/tasks.json` + `data/evolution-chains.json` + `data/collections.json`

## PATHS

```
lkwj/
├── server.js                  # HTTP 服务器，端口 8899
├── index.html                 # 单页 App：看板 + 精灵图鉴 + 异色炫彩 + 精灵果实 + 7 品类标签
├── scripts/
│   ├── migrate-to-pets.js            # sprites.json → pets.json 迁移
│   ├── migrate-to-tasks.js           # sprites.json → tasks.json 迁移
│   ├── migrate-to-evolution-chains.js # sprites.json → evolution-chains.json 迁移
│   ├── migrate-collections.js        # collections.json 格式迁移 + pets.json 回填
│   ├── build-sprites-pinyin.js       # 拼音字段生成（适配新格式）
│   └── migrate-leader-evolve.js      # 已过时，保留备查
└── data/
    ├── pets.json              # 宠物定义（355 只）：形态 + 标签 + 元素数组
    ├── tasks.json             # 任务定义（355 组）：form-independent，desc 不含宠物名
    ├── evolution-chains.json  # 进化链（162 链）：独立于形态，支持分支
    ├── collections.json       # 用户进度：sprite_progress + shiny_progress
    ├── sprites.json           # DEPRECATED: 旧单文件格式，保留备查
    ├── sprites_raw.json       # 原始数据（Wiki 抓取，勿写入）
    ├── shops.json             # 商店清单：36 商店 × 6 货币
    ├── wallet.json            # 用户货币持有量（dynamic，不提交 git）
    └── _待采集/               # 数据采集模板
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
    "fruit": { "name": "雪绒鸟果实", "acquired": false }
  }
}
```

字段说明：
- `name` — 宠物中文名
- `element` — 元素数组（支持双元素），如 `["光"]` 或 `["幽", "恶"]`
- `forms` — 形态定义，使用语义键名（`basic`, `spring`, `summer`, `autumn`, `winter`, `molting`, `variant_N`）
- `tags` — 稀有度标签（`shiny`, `chromatic`, `boss`）。标签独立于形态，进化时保留
- `pinyin` — 拼音（全拼 + 首字母），用于搜索
- `fruit` — 果实信息（可选，99 只精灵有此字段）
- `destined_hero` — 命定勇者标记（可选，144 只）
- `notes` — 备注
- `_todo_rename` — 标记形态键名待确认（88 个形态）

### tasks.json — 任务定义（静态）

```json
{
  "pet_20": [
    { "type": "capture", "desc": "捕捉1只" },
    { "type": "capture_gifted", "desc": "捕捉1只了不起天分的" },
    { "type": "skill", "desc": "使用", "skillName": "龙卷风", "count": 3 },
    { "type": "fruit", "desc": "捕捉20只" },
    { "type": "leader_evolve", "desc": "进化为首领形态" }
  ]
}
```

任务类型（10 种）：`capture`, `capture_gifted`, `capture_chromatic`(炫彩突变), `fruit`(原 capture20), `skill`, `evolve`, `leader_evolve`, `destined_hero`, `affection`, `confirm_forms`

关键规则：
- 任务是**形态无关**的——同一宠物所有形态共享同一份任务进度
- `desc` 不含宠物名，前台拼接（如 "岚鸟" + "使用" + "龙卷风" + "3" + "次"）
- skill 类任务额外提供 `skillName` 和 `count`
- `capture_chromatic` 对应炫彩突变捕捉（所有精灵除迪莫外都有炫彩），与异色（tags.shiny）无关

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

- 162 条链（100 条多节点 + 62 条单节点），9 条分支链
- 条件类型：`level`（等级）, `bloodline`（血脉）, `defeat_monster`（打怪），可复合
- 空 `evolvesTo` = 链终点

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
  "shiny_progress": { "pet_5": true, "pet_18": false }
}
```

- `sprite_progress` — 按 pet ID 索引，`tasks` 为任务完成状态，`forms_collected` 为已收集形态
- `shiny_progress` — 按 pet ID 索引的异色收集状态（0/1）
- `items[]` — 非宠物类收集项（家具、外观等）

## 核心设计原则

### 形态 (form) = 同一物种的外观变体
- 季节形态、地区形态、蜕皮形态属于 forms，不是进化链
- 语义键名列表：`basic`, `spring`, `summer`, `autumn`, `winter`, `molting`
- 迁移阶段的 `variant_N` 占位需在游戏中确认后改为语义键（标记 `_todo_rename: true`）
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
- **禁止从 collection 反向生成定义数据**

### 获取方式
- `obtainMethods` 只写直接获取方式，禁止"由 XX 进化"
- 进化来源在 evolution-chains.json 中

## 数据约束

- **evolve 类任务归属**：leader_evolve/evolve 只需挂在进化前的 pet 上（form-independent）
- **capture_chromatic ≠ 异色**：`capture_chromatic` 是炫彩突变捕捉任务（所有精灵除迪莫外都有），与 `tags.shiny`（异色标签，仅限时获取精灵有）完全独立
- **异色炫彩展示**：由 `pets.json` 的 `tags.shiny` 驱动，仅展示进化最终形态（标签随进化传递）
- **异色炫彩进度**：独立统计于 `collections.shiny_progress`，不由任何 task 状态驱动
- **异色必有限定时间**：`tags.shiny.limitedTime` 不可为"可获取"，异色均为赛季/通行证/活动限定
- **炫彩标签**：所有精灵（除迪莫外）均有 `tags.chromatic`
- **随机任务排除**：`destined_hero`、`fruit`、`confirm_forms` 任务类型不出现在随机池
- **随机任务进化约束**：capture 任务需先完成，fruit(原 capture20) 需 capture 先完成

## 已知数量

| 层级 | 数量 |
|------|------|
| 宠物总数 | 355 |
| 形态：basic | 355 |
| 形态：季节/蜕皮/地区 | 100 |
| 首领标签 | 24 |
| 异色标签 | 61（32 基础形态 + 29 进化传播；S1限定 + S2限定 + 通行证 + 活动） |
| 炫彩标签 | 354（所有精灵除迪莫外都有炫彩） |
| 任务总数 | 1763（form-independent） |
| 进化链 | 162（100 多节点 + 62 单节点，9 分支） |
| 精灵果实 | 99 种 |
| S2 新精灵 | 8 只（小丑豆豆~小鼓象） |

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/pets` | 宠物定义 |
| `GET /api/tasks` | 任务定义 |
| `GET /api/evolution-chains` | 进化链 |
| `GET /api/game-data` | 合并数据（pets+tasks+chains+progress） |
| `GET /api/data` | 原始 collections.json |
| `POST /api/save` | 保存 collections.json |
| `GET /api/wallet` | 钱包数据 |
| `POST /api/wallet` | 保存钱包 |

## 待完成

- [x] 4 文档体系重构（pets + tasks + evolution-chains + collections）— 2026-05-21
- [x] 形态语义化键名 + 标签系统 + 进化链独立
- [x] UI 适配新数据模型（全部 Tab 通过）
- [ ] 家具图鉴：待采集 CSV → 导入 items[]
- [ ] 外观图鉴：待采集 CSV → 导入 items[]
- [ ] 称号/星星/遗迹/支线/扭蛋/音乐：待采集
- [ ] 地区形态名称修正：variant_N → 语义 key
- [ ] S2 新精灵完整任务数据补充
- [ ] 炫彩（chromatic）数据采集与录入
