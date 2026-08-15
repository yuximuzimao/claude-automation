# 魔兽世界任务路线 SKILL.md

## DO FIRST

1. 先读 `tasks/todo.md`，只确认当前工作流和下一步，不加载历史。
2. 读 `docs/INDEX.md`，它只负责文档/数据入口导航，不承载完整规则。
3. **继续当前首组实跑**：读 `docs/verified-routes/CURRENT.md`；只有CURRENT明确要求阶段背景时，再定向读 `docs/archive/neat/` 中对应的最近NEAT，不批量读历史。
4. **生成/修订/审计任务路线**：读 `docs/rules/README.md`，只加载当前任务对应规则；再读 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`、`ERROR-BOOK.md` 和相关任务卡。
5. **Route Atlas路线数据/裁剪/优化**：读 `docs/rules/route-atlas-optimization.md`；只有同时改玩家任务备注时加读 `execution-and-mechanics.md`。
6. **Route Atlas HTML/地图/UI**：读 `docs/rules/route-atlas-ui-and-assets.md`；不要为了前端改动加载全部路线优化历史。
7. **视频拆解**：只读 `docs/video-extraction/README.md`、`docs/video-extraction/CURRENT.md` 和上一集检查点；历史NEAT只从 `docs/archive/video/` 定向读取。
8. **DK 55—80母版**：只在处理DK路线时读 `docs/DK_55_80_WORLD_TASKS.md` 和对应生成数据，不加载首组历史路线。
9. 代码/数据生成入口是 `cli.py`；Route Atlas工作台构建入口是 `scripts/build_route_atlas_workbench.py`。纯攻略修订不先运行生成器，也不让脚本替代人工判断。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `docs/INDEX.md` | 文档/数据导航索引，不承载完整规则 | 进入项目时读，确定后续最小读取范围 |
| `docs/verified-routes/CURRENT.md` | 当前等级/现场状态/唯一恢复点 | 继续当前实跑时第一份业务文档 |
| `docs/rules/README.md` | 永久规则路由，不存当前状态 | 任何路线规则问题先从这里选子规则 |
| `docs/rules/leveling-and-selection.md` | 经验预算、地图轴、任务取舍、随机掉落/护送价值 | 规划/估时/筛任务时 |
| `docs/rules/execution-and-mechanics.md` | 玩家攻略格式、隐藏机制、掉落触发、五开共享、洞穴/楼层 | 写攻略/补备注/处理任务机制时 |
| `docs/rules/state-and-validation.md` | 当前/从零路线分离、Journey、完整性、NEAT/Git边界 | 裁路线/审计/归档时 |
| `docs/rules/route-atlas-optimization.md` | Route Atlas数据层、状态机、插入/裁剪、炉石、求解器 | 改路线数据/优化逻辑时 |
| `docs/rules/route-atlas-ui-and-assets.md` | 唯一HTML、逻辑步骤、HUD、地图资源、离线契约 | 改前端/底图/地图资源时 |
| `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` | 完整路线设计/修订SOP | 真正新建或重算路线时 |
| `docs/verified-routes/ERROR-BOOK.md` | 历史失败模式和发布前复查 | 生成/修订/审计路线前 |
| `docs/task-library/README.md` | 单任务事实、证据、纠错写回 | 复用或核验具体任务时 |
| `data/observations/fivebox-task-types.json` | 五开共享/个人机制实测 | 用户反馈任务行为时 |
| `data/observations/blocked-tasks.json` | 本服阻断/不可做任务 | 接不到、交不了、位面异常时 |
| `data/route-atlas/workbench-routes.json` | 所有地图当前Route Atlas路线数据 | 改地图步骤/坐标/备注时 |
| `data/routes/route-atlas-workbench.html` | 唯一Route Atlas正式执行HTML | 实跑/审图/复制到游戏电脑 |
| `scripts/build_route_atlas_workbench.py` | 将路线数据嵌入唯一工作台 | 修改Route Atlas数据/UI后构建 |
| `docs/archive/README.md` | 历史档案总入口；旧方案、一次性分析、NEAT和视频历史 | 只有需要考古/回溯时按主题进入 |
| `docs/archive/neat/` | 日期化NEAT阶段存档 | 只按CURRENT/索引需要读一份，不批量加载 |
| `docs/video-extraction/README.md` | 视频拆解方法 | 处理视频时 |
| `docs/video-extraction/CURRENT.md` | 视频下一集恢复点 | 继续视频时 |
| `cli.py` | 项目命令入口 | 运行生成/解析命令时 |
| `lib/questie_source.py` | Questie任务/中文名/经验数据加载 | 更换插件来源或字段时 |
| `lib/questie_lua.py` | Questie Lua解析 | 解析失败/扩字段时 |
| `data/journey/current-paladin.json` | 脱敏人物历程 | 对比首组实际顺序时 |

## CORE FLOWS

### 当前首组实跑
`用户现场反馈/Questie → CURRENT真值 → 只打开受影响局部路线 → 修执行稿 → observations/任务卡 → 必要时NEAT`

### 新建或修订路线
`CURRENT → rules路由 → ROUTE-DESIGN-PROCESS → ERROR-BOOK → task-library/Questie → 玩家冷启动复走 → 发布`

### Route Atlas
`任务事实/当前状态 → workbench-routes.json → 逻辑步骤/备注审计 → build_route_atlas_workbench.py → 唯一route-atlas-workbench.html → 测试/JS检查`

### 人物历程
`QuestieConfig.char[*].journey → 脱敏事件 → 与当前路线对比 → 定位遗漏/折返/漏交 → 只修受影响窗口`

### 视频拆解
`视频事实 → 单集检查点 → video CURRENT → 全集结束后再整合；不与当前角色路线混算`

## FAILURE PATTERNS

- 不把自动候选、Questie区域分类或当前日志当完整覆盖证明。
- 不把Questie平面坐标当道路/楼层/洞穴导航。
- 不把击杀共享推断到拾取、点击、任务物或技能。
- 不按任务类型整类保留/排除；逐任务比较真实剩余成本。
- 不从日期化NEAT反推永久规则；永久规则只读 `docs/rules/`。
- `docs/archive/` 是历史考古区，不属于日常活跃知识；除非CURRENT/索引明确指向、当前任务需要回溯，或本轮刚修改了其中某文件，否则不批量读取。
- 不一次性加载全部规则、全部NEAT、全部任务卡；按当前任务渐进式读取。
- 不把临时教训长期堆在 `tasks/lessons.md`；稳定后迁到规则/错题/任务卡/observations。
- 不提交原始Questie/WTF/账号登录数据；先脱敏。
- 视频第一遍只提事实，不把剪辑缺口补成路线事实。

## PATHS

| 路径 | 说明 |
| --- | --- |
| `lib/` | 可复用解析/生成逻辑 |
| `scripts/` | Route Atlas和审计脚本 |
| `data/route-atlas/` | Route Atlas结构化路线/基础数据 |
| `data/routes/` | 生成路线；Route Atlas只允许一份正式工作台HTML |
| `data/routes/maps/` | 可离线复制的地图资源池 |
| `data/observations/` | 当前服务器实测修正 |
| `data/journey/` | 脱敏人物历程 |
| `docs/rules/` | 分主题永久规则；按需加载 |
| `docs/verified-routes/` | CURRENT、SOP、错题本、仍有效/可复用的已验证路线 |
| `docs/archive/` | 旧方案、一次性分析、NEAT、视频历史；默认不进入日常全文加载 |
| `docs/task-library/` | 单任务知识 |
| `docs/video-extraction/` | 当前视频事实提取工作流 |
| `tasks/` | 当前待办 + 尚未迁移的临时教训 |
| `tests/` | 自动测试 |
