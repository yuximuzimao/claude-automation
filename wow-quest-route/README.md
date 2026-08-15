# 魔兽世界五开打金任务路线

面向国服泰坦重铸“时光”服的五开练级/任务路线项目。一个主控角色负责移动和战斗，另外四号持续跟随；逐号拾取、点击、技能、任务物等机制只按逐任务实测处理。

## 当前方向

当前唯一主线是**先把首组五个血精灵圣骑士连续练到80级**；死亡骑士资料保留但暂缓。

README不保存具体当前等级、地图和任务进度。继续实跑只读：

`docs/verified-routes/CURRENT.md`

当前Route Atlas唯一正式执行页：

`data/routes/route-atlas-workbench.html`

所有地图共用这一份HTML；复制到游戏电脑时同时复制同级 `data/routes/maps/` 目录即可离线使用。

## 项目怎么读

这是一个渐进式文档项目，不要一次加载全部历史。

1. Agent进入项目先读 `SKILL.md`。
2. 当前待办读 `tasks/todo.md`。
3. `docs/INDEX.md` 只做文档/数据导航，确定本次最小读取范围。
4. 当前首组状态读 `docs/verified-routes/CURRENT.md`。
5. 永久规则从 `docs/rules/README.md` 选择当前需要的子规则。
6. 真正生成/修订完整路线才读 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` 和 `ERROR-BOOK.md`。
7. 具体任务事实优先复用 `docs/task-library/` 和 `data/observations/`。
8. 历史资料统一从 `docs/archive/README.md` 定向查；日常不批量加载archive，只有CURRENT/当前问题需要时再读对应历史文件。

## 主要数据层

- **Questie基础事实**：任务ID、前置、NPC/物体/物品、静态坐标；原始数据不被实跑覆盖。
- **任务知识**：任务机制、地形、掉落来源、五开共享/个人行为和可复用任务卡。
- **当前状态**：最低号等级经验、任务进度、当前地图、交通等，只在CURRENT/Journey维护。
- **Route Atlas路线**：`data/route-atlas/workbench-routes.json` 保存当前有效路线数据。
- **实测观察**：`data/observations/` 保存本服五开共享、阻断和特殊机制。
- **历史档案**：`docs/archive/` 保存旧方案、一次性分析、NEAT和视频历史；只在需要考古时定向读取。

## 永久规则分层

总入口：`docs/rules/README.md`

- `leveling-and-selection.md`：经验预算、地图轴、任务取舍、随机掉落/护送。
- `execution-and-mechanics.md`：玩家攻略、任务备注、洞穴/楼层/道具/触发物、五开共享。
- `state-and-validation.md`：当前状态、完整性、Journey、NEAT/Git边界。
- `route-atlas-optimization.md`：Route Atlas数据、状态机、插入/裁剪、炉石、求解器。
- `route-atlas-ui-and-assets.md`：唯一HTML、逻辑步骤、HUD、底图、地图资源和离线复制。

永久规则只从 `docs/rules/README.md` 进入，不维护其它总规则入口。

## Route Atlas

长期产品契约：

- 唯一正式HTML：`data/routes/route-atlas-workbench.html`。
- 当前路线数据：`data/route-atlas/workbench-routes.json`。
- 构建：`scripts/build_route_atlas_workbench.py`。
- 地图资源池：`data/routes/maps/`。
- 几何停靠点可以很多，但玩家步骤按自然任务块合并。
- 地图默认全图；只有用户主动启用“跟随当前段”才自动裁剪。
- 有特殊执行机制的逻辑步骤显示“有备注”。
- Questie继续负责游戏内精确目标点，Route Atlas负责宏观路线、任务块顺序和需要额外记忆的机制。

## 安全与隐私边界

- 只离线读取用户提供的Questie/WTF数据；不修改游戏文件。
- 不注入客户端、不读内存、不抓包、不自动接交任务、不广播输入。
- 不保存账号名、服务器名、角色名、GUID或登录信息。
- 原始Questie/WTF/账号运行时数据不提交Git；只提交脱敏历程、结构化观察、路线和项目文档。
- 工作区根 `/sessions/` 是浏览器/账号会话，保持Git忽略；项目历史统一放 `docs/archive/`，正常commit/push但不参与日常默认读取。

## 旧生成器

项目仍保留早期圣骑士参考页、死亡骑士母版和world-candidate生成代码，用于历史召回或后续研究；它们不是当前首组执行真值。需要修改这些生成器时从 `SKILL.md` 的ENTRY MAP定位，不在README长期维护具体旧命令和旧等级阶段。

## 测试

Route Atlas改动按对应规则运行专项pytest、工作台构建和JavaScript语法检查。其它解析/生成代码按受影响模块运行测试；测试入口和文件定位从 `SKILL.md` 查，不在README重复维护易过期的命令清单。
