# 洛克王国 · 收集助手 SKILL.md

> Agent 导航地图。详细模型规则在 `docs/DATA_MODEL.md`，当前数量和验证命令在 `README.md`，未完成事项只看 `tasks/todo.md`。

## ENTRY MAP

| 目标 | 入口 |
| --- | --- |
| 启动本地服务 | `node server.js`（端口 8899） |
| 打开主界面 | `http://localhost:8899` |
| 打开人工核对工具 | `http://localhost:8899/review.html` |
| 人类快速接入 | `README.md` |
| 文档索引 | `docs/INDEX.md` |
| 数据模型与边界 | `docs/DATA_MODEL.md` |
| 未完成事项 | `tasks/todo.md` |
| Excel 只读核对 | `docs/REVIEW_CHECKLIST.md` |
| 用户进度 | `data/collections.json` |
| 服装定义 | `data/clothing.json` |

## DO FIRST

进入本项目时按顺序执行：

1. 读 `tasks/todo.md`，确认当前数据补录范围。
2. 检查服务：`lsof -ti :8899`。
3. 未运行时在项目目录执行 `node server.js`。
4. 修改前读对应静态 JSON 和 `docs/DATA_MODEL.md` 的相关章节。
5. 修改后运行 `README.md` 中对应验证命令。

## 项目结构

```text
lkwj/
├── README.md                  # 运行方式、当前数量、数据状态、验证命令
├── CLAUDE.md                  # Session 启动规则
├── SKILL.md                   # 本入口地图
├── server.js                  # 本地 HTTP 服务，端口 8899
├── index.html                 # 主界面
├── review.html                # 人工数据核对工具
├── docs/
│   ├── INDEX.md               # 文档索引
│   ├── DATA_MODEL.md          # 数据模型和边界
│   ├── REVIEW_CHECKLIST.md    # Excel 只读核对清单
│   └── archive/               # 已完成阶段归档
├── tasks/
│   └── todo.md                # 唯一待办入口
├── scripts/                   # 数据和 UI 校验脚本
└── data/
    ├── pets.json
    ├── tasks.json
    ├── evolution-chains.json
    ├── furniture.json
    ├── clothing.json
    ├── titles.json
    ├── dungeons.json
    ├── shops.json
    ├── collections.json
    ├── wallet.json            # 动态，不提交 Git
    └── annotations.json       # 动态，不提交 Git
```

## 必守边界

### 静态定义与进度分离

- 静态定义写入对应 `data/*.json`；个人完成状态只写入 `data/collections.json`。
- 禁止从 collection 进度反向生成精灵、任务、套装或其他世界定义。
- 稳定 ID 只追加，不复用、不重排。

### 精灵、任务和进化

- 形态是同一物种的外观变体；标签是异色、炫彩、首领等稀有度标记。
- 进化只改变物种 ID，形态和标签默认继承。
- 任务只来自 Excel `课题进度` sheet；同一宠物所有形态共享任务。
- `fruit` 是果实课题任务，不得从果实图鉴反向生成。
- `capture_chromatic` 与 `capture_shiny` 不能混用。
- `confirm_forms.requiredForms` 只表示课题计入形态；完整形态收集使用 `forms_collected`。
- 获取方式只写直接来源，禁止写“由某精灵进化”。

### 服装

- `data/clothing.json` 使用 `definitions + sets[] + pieces[]`。
- `requiredPieceCount` 是华丽魔法必需部件总数；付费额外组件不包含在内。
- `obtainType="standard"` 才是个人收集目标；`paid` 只展示，不可勾选，也不得写入 `clothing_progress`。
- 所有付费额外组件通过积分卡解锁。
- 获取方式未知时保留 `待补充`，前端隐藏占位文本。
- 套装名称匹配且必需件数吻合后才能归套装，禁止仅按近似名称合并。
- 服装侧使用“魔草巫灵”；异色套装统一保留“印象”后缀。
- “追忆”和“回忆”可能是不同单品。
- `初始发型1` 至 `初始发型3`、`面妆1` 至 `面妆8` 是正式名称，属于系统默认新手独立单品。
- 随机商店部件只录入用户实际看到的名称；只有明确购买后才修改收集进度。

### 其他收集项

- 家具定义只保存名称、舒适度、灵感值；进度只保存是否收集。
- 称号按 `upper · lower` 展示；单段称号写入 `upper`。
- 遗迹按副本整体勾选，不拆奖励单项进度。
- 星星、支线任务、扭蛋机、音乐复用 `collections.items[]`。
- 商店商品、通用外观和玩具的未完成建模只维护在 `tasks/todo.md`。

## 验证速查

```bash
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
node scripts/validate-random-task-ui.js
node scripts/validate-furniture-ui.js
node scripts/validate-clothing-data.js
node scripts/validate-clothing-ui.js
node scripts/validate-title-ui.js
node scripts/validate-dungeon-ui.js
```

服装校验中，已知部件名称少于 `requiredPieceCount` 会输出 warning；warning 表示资料待补。结构错误必须退出失败。

## API 端点

| 端点 | 说明 |
| --- | --- |
| `GET /api/pets` | 精灵定义 |
| `GET /api/tasks` | 任务定义 |
| `GET /api/evolution-chains` | 进化链 |
| `GET /api/furniture` | 家具定义 |
| `GET /api/clothing` | 服装定义 |
| `GET /api/titles` | 称号定义 |
| `GET /api/dungeons` | 遗迹副本定义 |
| `GET /api/game-data` | 合并静态定义与用户进度 |
| `GET /api/data` | 原始 `collections.json` |
| `POST /api/save` | 保存 `collections.json` |
| `GET /api/wallet` | 钱包数据 |
| `POST /api/wallet` | 保存钱包 |
| `GET /api/annotations` | 标注日志 |
| `POST /api/annotations` | 保存标注日志 |

## 状态来源

- 当前数量与可用状态：`README.md`
- 未完成补录和规划：`tasks/todo.md`
- 历史阶段决策：`docs/archive/`
- 更完整字段规则：`docs/DATA_MODEL.md`
