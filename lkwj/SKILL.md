# 洛克王国 · 收集助手 SKILL.md

> 导航地图，先读地图再走路。

## ENTRY MAP

| 目标 | 入口 |
|------|------|
| 启动本地服务 | `node server.js`（端口 8899） |
| 打开界面 | 浏览器访问 `http://localhost:8899` |
| 修改收集进度 | 直接编辑 `data/collections.json` 或通过 UI 勾选 |
| 精灵任务数据 | `data/sprites.json`（只读，完整三层结构） |
| 精灵图鉴（合并进度） | GET `/api/sprites`（sprites.json + sprite_progress 合并） |
| 数据采集需求 | `data/_待采集/README.md`（外观/家具/异色/地区形态修正模板） |
| 商店与货币数据 | `data/shops.json`（36 商店+6 货币）+ `data/wallet.json`（用户持有量） |
| 查看精灵原始数据 | `data/sprites_raw.json`（由 Excel 生成，已废弃，保留备查） |

## DO FIRST

进入本项目时：
1. 确认 server 是否已运行：`lsof -ti :8899`（有输出=已运行）
2. 若未运行：`node server.js &`
3. 核心数据文件：`data/collections.json`（看板/异色/进度）和 `data/sprites.json`（精灵任务库）

## PATHS

```
lkwj/
├── server.js                  # HTTP 服务器，端口 8899，GET /api/data + /api/sprites + POST /api/save
├── index.html                 # 单页 App：看板+11品类标签（精灵/异色炫彩/果实/家具/服装/称号/星星/遗迹/支线/扭蛋/音乐）
└── data/
    ├── collections.json       # 主数据：进度看板 + 异色炫彩收集列表（UI 读写此文件）
    ├── sprites.json           # 精灵任务库：347 精灵，1834 个任务，三层结构，含 pinyin 字段
    ├── sprites_raw.json       # 原始数据（Excel 导出，勿写入）
    ├── shops.json             # 商店清单：36 商店 × 6 货币，售卖物品待填充
    ├── wallet.json            # 用户货币持有量（dynamic，不提交 git）
    └── scripts/
        ├── build-sprites-pinyin.js  # 为 sprites.json 生成 pinyin 字段
        └── migrate-leader-evolve.js # 删除 leader form 冗余任务前迁移进度
    └── _待采集/                # 数据采集模板（交给其他模型填写）
        ├── README.md            #   采集需求说明文档
        ├── 外观图鉴.csv         #   空白模板
        ├── 家具图鉴.csv         #   空白模板
        ├── 异色炫彩完整列表.csv  #   152只精灵预填，待确认
        ├── 地区形态名称修正.csv  #   100个形态预填，待修正游戏内名称
        ├── 商店与货币.csv       #   空白模板（36店×6货币，售卖物品待填充）
        └── 其他类别统计.csv     #   空白模板
```

## 数据结构

### collections.json（UI 读写）

```json
{
  "meta": { "last_updated": "YYYY-MM-DD", "game": "洛克王国世界" },
  "categories": {
    "精灵": { "total": 347, "owned": 304 },
    "外观": { "total": null, "owned": null }
  },
  "items": [
    {
      "id": "yise_001",
      "category": "异色炫彩",
      "name": "...",
      "status": "已完成|未完成",
      "limited": false,
      "limited_status": "第一赛季|第二赛季|活动|通行证|可获取",
      "source_url": "",
      "source_type": "链接|视频|图文",
      "notes": ""
    }
  ],
  "sprite_progress": { "1": { "collected": false, "forms": { "0": { "collected": false, "tasks": { "0": true } } } } },
  "activities": []
}
```

> 异色炫彩统计以 sprites.json capture_shiny 为准，items[] 仅存储季节/攻略等元数据。

### sprites.json（三层只读，运行时合并 sprite_progress）

```json
[
  {
    "id": 1,
    "name": "迪莫",
    "element": "光",
    "pinyin": { "full": "dimo", "initial": "dm" },
    "fruit": null,
    "forms": [
      {
        "type": "base",
        "label": "基础形态",
        "tasks": [
          { "type": "capture", "desc": "捕捉1只迪莫", "done": false },
          { "type": "capture_gifted", "desc": "捕捉1只了不起天分的迪莫", "done": false }
        ]
      }
    ]
  }
]
```

## 数据约束

- **evolve 类任务归属规则**：leader_evolve/evolve 任务只能挂在 source form（进化前形态），禁止 target form（进化后形态）出现同名 evolve 任务。sprites.json 导入/更新时必须校验此约束。
- **迁移脚本**：`scripts/migrate-leader-evolve.js` — 删除 leader form 的 leader_evolve 前同步用户进度。

**任务类型说明**：
- `capture` — 捕捉 1 只
- `capture_gifted` — 捕捉 1 只了不起天分
- `capture_shiny` — 捕捉 1 只炫彩突变（152 只精灵有此任务）
- `capture20` — 捕捉 20 只（有果实字段的精灵，需 capture 先完成）
- `skill` — 使用技能石 N 次
- `evolve` — 进化一次
- `leader_evolve` — 进化为首领形态（24 只，仅挂 base form）
- `destined_hero` — 命定勇者奖牌（144 只，依赖限时活动，不出随机池）
- `affection` — 亲密度（仅迪莫）
- `fruit` — 果实获取
- `confirm_forms` — 确认地区形态（56 只）

## 已知数量

| 层级 | 数量 |
|------|------|
| 基础形态 | 347 |
| 地区形态 | ~89 |
| 首领形态 | ~24 |
| 任务总数 | 1834（已删 24 条 leader form 冗余 leader_evolve） |
| 异色炫彩 items | 27（S1赛季21+通行证2+活动1+可获取3） |
| capture_shiny 精灵 | 152 只（sprites.json） |

## 待完成

- [x] sprites.json 三层结构接入 + 精灵图鉴 Tab — 2026-05-15
- [x] 拼音搜索 + 分页 + 状态筛选（全部/未完成/已完成）— 2026-05-15
- [x] 12 品类标签 + 随机任务看板 + 关联任务 — 2026-05-15
- [x] 精灵果实 Tab（99条）— 2026-05-15
- [x] S1 赛季异色导入（27 items）+ 赛季分类体系 — 2026-05-15
- [x] 商店货币架构（shops.json + wallet.json + 商店与货币.csv）— 2026-05-15
- [ ] 家具图鉴：待采集 CSV → 导入 items[]
- [ ] 外观图鉴（服装）：待采集 CSV → 导入 items[]
- [ ] 称号/星星/遗迹/支线/扭蛋/音乐：待采集数据
- [ ] 地区形态名称修正：待 CSV 确认
- [ ] sprites.json region 字段注入 + 地区统计恢复
