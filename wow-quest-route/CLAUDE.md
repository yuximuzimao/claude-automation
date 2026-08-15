# 魔兽世界任务路线

项目中文名：魔兽世界五开打金任务路线

## 稳定项目目标

- 当前主线是把首组五个血精灵圣骑士连续练到80级；死亡骑士路线暂缓，80级后再评估。
- **具体当前等级、地图、任务状态不得复制到本文件长期维护**，统一以 `docs/verified-routes/CURRENT.md` 为唯一当前真值。
- 路线目标：当前任务中心尽量闭环、最少重复横穿、自然衔接下一地图；不能为兑现老手口述等级在已清空地图无任务刷怪。
- 用户实跑反馈优先于桌面模型；确认后先修当前执行稿，再写observations/任务卡，跨地图长期有效才进入 `docs/rules/`。
- 死亡骑士历史母版保留为后续资料，不驱动当前首组路线。
- 接不到、进不去、交不了、服务器位面异常的任务记录到 `data/observations/blocked-tasks.json` 并绕过，不能阻塞1—80主目标。

## Session 启动（必做，按工作流分流）

1. 进入项目先读 `SKILL.md`。
2. 读 `tasks/todo.md`，确认当前工作流，不加载历史。
3. 读 `docs/INDEX.md`，只做文档/数据导航，确定本次最小读取范围。
4. 继续当前实跑：读 `docs/verified-routes/CURRENT.md`；只有CURRENT明确要求阶段背景时，才定向读 `docs/archive/neat/` 中对应的最近NEAT；需要旧执行版本时从 `docs/archive/routes/` 定向读取。
5. 新建/修订/审计路线：读 `docs/rules/README.md`，按任务选择子规则；再读 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`、`ERROR-BOOK.md` 和相关任务卡。
6. Route Atlas数据/优化与Route Atlas HTML/UI分开加载规则，具体路由以 `SKILL.md` 和 `docs/rules/README.md` 为准。
7. 视频拆解：只读 `docs/video-extraction/README.md`、`CURRENT.md` 和上一集检查点，不加载当前角色路线和Route Atlas历史。
8. 攻略成稿后从玩家起点冷启动复走；发现问题先改执行稿，不保留错误正文等待解释。

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
| --- | --- |
| `docs/rules/README.md` | 永久规则总路由；先看它决定读哪一份 |
| `docs/rules/leveling-and-selection.md` | 经验预算、地图轴、任务取舍、随机掉落/护送 |
| `docs/rules/execution-and-mechanics.md` | 玩家攻略、任务备注、洞穴/楼层/任务物/五开共享 |
| `docs/rules/state-and-validation.md` | 当前路线裁剪、Journey、完整性审计、NEAT/Git边界 |
| `docs/rules/route-atlas-optimization.md` | Route Atlas路线数据、状态机、插入/裁剪、炉石、求解器 |
| `docs/rules/route-atlas-ui-and-assets.md` | Route Atlas HTML、逻辑步骤、HUD、底图和离线资源 |
| `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` | 真正新建/重算/系统修订路线时 |
| `docs/verified-routes/ERROR-BOOK.md` | 路线发布前对抗复查 |
| `docs/task-library/README.md` | 复用或补充单任务人工事实 |
| `docs/JOURNEY_EXPORT.md` | 导出/分析Questie人物历程 |
| `docs/video-extraction/README.md` | 视频事实提取 |

禁止为了一个局部问题一次性加载全部永久规则、全部任务卡或整个 `docs/archive/`。archive只在需要考古、CURRENT明确指向或本轮刚修改历史文件时定向读取。

## 教训沉淀流程

- `tasks/lessons.md`：只放尚未确定归宿的Session级新发现。
- 稳定方法 → `docs/rules/`。
- 重复失败模式 → `docs/verified-routes/ERROR-BOOK.md`。
- 单任务事实 → `docs/task-library/` / `data/observations/`。
- 阶段状态/证据 → `docs/archive/neat/` NEAT。
- 迁移后从 `tasks/lessons.md` 删除，不重复维护。

## 数据边界

- Questie插件与WTF均为只读输入，不修改游戏文件。
- 不保存账号名、服务器名、角色名、GUID、登录信息。
- 原始Questie压缩包、WTF和临时解析产物不提交；只提交脱敏历程、结构化观察、路线和项目文档。
- `data/routes/` 保存可复用路线/HTML；`data/observations/` 保存实测修正；`data/journey/` 只保存脱敏人物历程。
- Route Atlas目标电脑只需要 `data/routes/route-atlas-workbench.html + data/routes/maps/`。

## Git / 历史边界

- 工作区根 `/sessions/` 是浏览器/账号运行时会话，必须被根 `.gitignore` 忽略。
- 项目历史统一放 `docs/archive/`，必须正常commit/push；archive只是退出日常默认读取，不是Git忽略区。
- 项目Markdown不靠 `git add -f` 作为正常流程。

## 目录说明

| 目录 | 用途 |
| --- | --- |
| `lib/` | Questie解析、路线数据和生成逻辑 |
| `scripts/` | Route Atlas构建/审计/地图资源脚本 |
| `data/route-atlas/` | Route Atlas当前结构化路线与基础数据 |
| `data/routes/` | 生成路线与唯一Route Atlas工作台 |
| `data/observations/` | 五开机制、阻断、实测修正 |
| `data/journey/` | 脱敏人物历程 |
| `docs/rules/` | 分主题永久规则，渐进式加载 |
| `docs/verified-routes/` | CURRENT、SOP、错题本、仍有效/可复用的已验证路线 |
| `docs/archive/` | 旧方案、一次性analysis、NEAT和视频历史；默认不进入日常加载 |
| `docs/task-library/` | 单任务可复用知识 |
| `docs/video-extraction/` | 当前视频事实提取工作流 |
| `tasks/` | 当前待办与临时教训收件箱 |
| `tests/` | 自动测试 |
