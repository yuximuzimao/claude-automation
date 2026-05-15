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
├── index.html                 # 单页 App：看板/精灵图鉴/异色炫彩/背包 四标签
└── data/
    ├── collections.json       # 主数据：进度看板 + 异色炫彩收集列表（UI 读写此文件）
    ├── sprites.json           # 精灵任务库：347 精灵，1857 个任务，三层结构
    ├── sprites_raw.json       # 原始数据（Excel 导出，勿写入）
    ├── shops.json             # 商店清单：36 商店 × 6 货币，售卖物品待填充
    ├── wallet.json            # 用户货币持有量（dynamic，不提交 git）
    └── _待采集/                # 数据采集模板（交给其他模型填写）
        ├── README.md            #   采集需求说明文档
        ├── 外观图鉴.csv         #   空白模板
        ├── 家具图鉴.csv         #   空白模板
        ├── 异色炫彩完整列表.csv  #   152只精灵预填，待确认
        ├── 地区形态名称修正.csv  #   100个形态预填，待修正游戏内名称
        └── 其他类别统计.csv     #   空白模板
```

## 数据结构

### collections.json（UI 读写）

```json
{
  "meta": { "last_updated": "YYYY-MM-DD", "game": "洛克王国世界" },
  "categories": {
    "精灵": { "total": 347, "owned": 304 },
    "外观/家具/玩具/称号/星星/课题": { "total": null, "owned": null }
  },
  "regions": {
    "风眠省图鉴": { "total": 159, "owned": 143 },
    "洛克里安图鉴": { "total": 187, "owned": 164 }
  },
  "items": [
    {
      "id": "yise_001",
      "category": "异色炫彩",
      "name": "...",
      "status": "未完成|已完成",
      "limited": false,
      "limited_status": "可获取|赛季已过",
      "source_url": "",
      "source_type": "链接|视频|图文",
      "notes": ""
    }
  ],
  "activities": [ { "name": "...", "end_date": "YYYY-MM-DD" } ]
}
```

### sprites.json（三层只读）

```json
[
  {
    "id": 1,
    "name": "机械方方",
    "type": "机械",
    "forms": [
      {
        "formId": "1_base",
        "formName": "基础形态",
        "type": "base|regional|leader",
        "tasks": [
          {
            "type": "skill|capture20|destined_hero|leader_evolve|affection",
            "desc": "使用技能石·XX 10次",
            "done": false
          }
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
- `skill` — 使用技能石 N 次
- `capture20` — 捕捉 20 只（有果实字段的精灵）
- `destined_hero` — 命定勇者（lv40+ 单人挑战，非赛季活动才有）
- `leader_evolve` — 首领进化
- `affection` — 亲密度（目前仅迪莫）

## 已知数量

| 层级 | 数量 |
|------|------|
| 基础形态 | 347 |
| 地区形态 | ~89 |
| 首领形态 | ~24 |
| 任务总数 | 1857 |
| 异色炫彩（已录） | 5（机械方方/空空颅/贝瑟/粉星仔x2） |

## 待完成

- [x] sprites.json 三层结构接入 index.html — 2026-05-15 完成
- [x] 精灵图鉴 Tab：按精灵浏览 form→task，任务勾选同步进度 — 2026-05-15 完成
- [ ] 精灵果实图鉴（99条，sprites.json 已有果实名称）：待 UI 展示
- [ ] 家具图鉴（195条）：待采集原始数据到 `data/_待采集/家具图鉴.csv`
- [ ] 外观图鉴：待采集原始数据到 `data/_待采集/外观图鉴.csv`
- [ ] 服装图鉴：用户确认最低优先级，暂跳过
