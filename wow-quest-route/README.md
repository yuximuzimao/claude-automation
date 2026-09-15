# 魔兽世界五开打金任务路线

面向国服泰坦重铸“时光”服的五开练级/任务路线项目。一个主控角色负责移动和战斗，另外四号持续跟随；逐号拾取、点击、技能、任务物等机制只按逐任务实测处理。

## 当前方向

当前阶段已经从首组五血精灵圣骑实跑切换到**第一组五兽人双手鲜血死亡骑士的重复打金路线验证**；首组圣骑嚎风不再继续清，具体恢复点、实验KPI和开跑前准备统一看`docs/verified-routes/CURRENT.md`。

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
4. 当前批次状态读 `docs/verified-routes/CURRENT.md`。
5. 永久规则只从 `docs/rules/README.md` 进入对应唯一owner。
6. 新建、修订、实跑写回、发布或架构迁移按 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` 调度。
7. 单任务当前事实只改对应 `data/task-cards/<task_id>.json`；旧observations/semantic/foundation只能作为证据或迁移兼容输入，不能继续作为新事实写入口。
8. 历史资料统一从 `docs/archive/README.md` 定向查；日常不批量加载archive。

## 主要数据层

- **Task Card**：`data/task-cards/`，单任务当前事实唯一真源；`docs/task-library/README.md`只定义字段语义。
- **Route Profile**：`data/route-profiles/`，某一具体正式路线的唯一真源。
- **CURRENT**：`docs/verified-routes/CURRENT.md`，当前批次runtime overlay / 恢复点，不是第二路线。
- **Observations**：`data/observations/`，保存实测证据、时间样本和兼容期旧观测；不是Task Card或Route Profile的平行真源。
- **Generated Product**：`data/route-atlas/workbench-routes.json`与`data/routes/route-atlas-workbench.html`等可删除重建产物，不直接人工维护业务真值。
- **历史档案**：`docs/archive/`，只用于定向考古。

## 永久规则

唯一注册表：`docs/rules/README.md`。README不复制子规则职责表；具体Mechanics、Selection、XP、Timing、Route Profile、Route Display、Task Presentation和UI规则均从该注册表渐进加载。

`docs/rules/state-and-validation.md`已经退出owner角色，只是旧引用兼容指针。

## Route Atlas

- 正式路线真源：`data/route-profiles/`。
- 聚合路线数据：`data/route-atlas/workbench-routes.json`，目标态为Publisher生成物/兼容产物。
- 唯一正式HTML：`data/routes/route-atlas-workbench.html`，属于Generated Product。
- HTML构建：`scripts/build_route_atlas_workbench.py`。
- 地图资源池：`data/routes/maps/`。
- Route Atlas只从结构化真源和规则单向生成玩家页面；不得从HTML/旧workbench反推任务事实或路线决策。

## 安全与隐私边界

- 只离线读取用户提供的Questie/WTF数据；不修改游戏文件。
- 不注入客户端、不读内存、不抓包、不自动接交任务、不广播输入。
- 不保存账号名、服务器名、角色名、GUID或登录信息。
- 原始Questie/WTF/账号运行时数据不提交Git；只提交脱敏历程、结构化观察、路线和项目文档。
- 工作区根 `/sessions/` 是浏览器/账号会话，保持Git忽略；项目历史统一放 `docs/archive/`，正常commit/push但不参与日常默认读取。

## 旧生成器

项目仍保留早期圣骑士参考页、死亡骑士母版和world-candidate生成代码，用于历史召回或后续研究；它们不是当前批次执行真值。需要修改这些生成器时从 `SKILL.md` 的ENTRY MAP定位，不在README长期维护具体旧命令和旧等级阶段。

## 测试

测试按`tests/README.md`分为永久不变量、当前地图/功能开发验证、路线快照/历史回归参考三类。先按本轮目标选择最小相关验证，再从`SKILL.md`定位对应规则和入口；不把全量pytest或历史快照跑绿当作通用收尾条件。
