# 2026-08-25 永久规则一致性审计

## 目的

本次不是继续追加“遇到一个问题补一条提醒”，而是检查当前活跃规则体系本身是否满足长期维护要求：真正跨地图/跨批次、唯一权威、互不冲突、符合项目第一目标，并且规则与代码/测试一致。

## 审计范围

- `docs/rules/README.md`
- `docs/rules/leveling-and-selection.md`
- `docs/rules/execution-and-mechanics.md`
- `docs/rules/state-and-validation.md`
- `docs/rules/route-atlas-optimization.md`
- `docs/rules/route-atlas-ui-and-assets.md`
- `docs/rules/timing-and-benchmarking.md`
- `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`
- `docs/verified-routes/ERROR-BOOK.md`固定复查清单
- 项目稳定入口`CLAUDE.md`、`SKILL.md`与工作区`AGENTS.md`的职责边界
- 与规则直接对应的Route Atlas估时回归测试

## 审计前发现的结构性问题

1. **当前阶段策略泄漏进永久规则。** 例如“不学寒冷天气飞行 + K3借鸟”、首组/当前五开措辞、具体阶段等级切换数字等。这些应由CURRENT/RouteState承载。
2. **单任务案例被写进永久规则正文。** 具体任务ID及其特殊结论虽然当时用于纠错，但长期应归task-library/observations/ERROR-BOOK，而不是继续作为全局规则的一部分。
3. **历史形成过程冒充产品契约。** semantic HUD曾用“龙骨第45步”作为来源说明；真正永久的应是`semantic-hud-v45`契约本身，而不是历史样板。
4. **阶段基准硬编码。** 老手某一等级段的具体小时数写进永久估时规则，与“外部基准数字属于observations”冲突。
5. **真正的目标冲突。** SOP仍以`经验/完整墙钟`作为路线主要比较指标，并把经验闭合/衰减门禁普遍应用；当前项目第一目标已经是整组任务打金周期的净金币/真实墙钟，且路线可跨越满级。满级路线继续执行经验截止会产生错误重排。
6. **旧阶段发布清单残留。** ERROR-BOOK/SOP仍有“55闭合”“外域全清”一类历史阶段专用门禁。
7. **规则已写但实现未同步。** `timing-and-benchmarking.md`要求玩家动作中显式`做《任务》`不得漏进估时，但`timingTaskNames`存在时估时器提前返回，导致龙骨第43步《日常计划》被漏计。

## 本次统一后的权威模型

| 内容 | 唯一owner | 其它位置允许什么 |
| --- | --- | --- |
| 项目第一目标、永久规则准入/冲突治理 | `docs/rules/README.md` | 入口文档只摘要并链接 |
| 任务取舍、经验/满级经济原则 | `leveling-and-selection.md` | SOP只规定何时执行 |
| 玩家文案与任务机制 | `execution-and-mechanics.md` | UI规则只定义如何渲染这些语义 |
| 当前状态裁剪、证据与归档边界 | `state-and-validation.md` | SOP调用，不复制第二套定义 |
| RouteState、任务簇插入、交通/依赖优化 | `route-atlas-optimization.md` | state文档只说明当前状态如何重放 |
| HUD/HTML/地图资源产品契约 | `route-atlas-ui-and-assets.md` | execution文档只定义内容语义 |
| 时间模型、预测/实跑、经济计时边界 | `timing-and-benchmarking.md` | 其它规则引用，不另建参数体系 |
| 当前角色/当前地图/阶段策略 | `CURRENT.md` | 永久规则不得复制 |
| 单任务/本服事实 | task-library / observations | ERROR-BOOK可保存错误案例，不成为规则owner |
| 流程顺序和发布门禁编排 | `ROUTE-DESIGN-PROCESS.md` | 具体规则回指`docs/rules/` |

## 已完成的修正

- `README`新增“永久规则准入、归属与一致性门禁”：跨批次、方法/契约、唯一owner、第一目标一致、规则与实现一致。
- 新增**触发式一致性检查**：以后只要新增/修改/提升一条永久规则，本轮收尾前必须审查受影响规则邻域；不再只追加新提醒。只有规则架构大改、明显膨胀或用户明确要求时才做全量规则审计，避免反向过度工程化。
- 将寒冷天气/K3等当前交通策略从永久规则泛化为“移动能力 vs 任务硬技能Availability”方法；具体策略继续由CURRENT/RouteState承载。
- 删除永久规则中的单任务ID案例，改成“单任务事实不得升级成全局例外”的方法规则。
- 所有典型阶段数字/历史样板引用从永久规则清除；满级机制统一写“满级”，具体当前等级仍由CURRENT给出。
- SOP明确分流：**未满级做经验/等级闭合，满级做任务经济闭合**；满级不再执行经验衰减门禁。
- 任务删除的反向替代测试也分流：未满级有经验缺口才要求替代经验任务；满级直接比较收益、后续链、回访与节省墙钟。
- 大规模旧路线终审规则泛化为任何批量迁移/重构都适用的“改前对比 → 用户冷读”。
- `semantic-hud-v45`保留为产品契约，历史“第45步样板”从永久规则移除。
- 外部速度基准具体数值迁出永久规则逻辑，只允许在observations作为墙钟参照。
- 修正估时实现：`timingTaskNames`只能作为结构种子，不能覆盖玩家显式执行任务扫描。
- ERROR-BOOK固定清单与SOP发布门禁同步成未满级/满级两套闭合逻辑，并加入永久规则一致性门禁。
- `CLAUDE.md`稳定项目目标改为任务打金系统本身，不再硬编码某一批角色“练到80”的阶段目标。

## 审计后结论

- 当前`docs/rules/`中对典型补丁痕迹的反扫：`K3 / 14小时 / 第45步 / 11591 / 12791 / 58→68→80 / 55闭合 / 首组 / 当前五开`均为0命中。
- 当前`docs/rules/`中5位任务ID为0命中；单任务事实已退出永久规则正文。
- 现有重复内容中，保留的是**不同职责层的摘要**，不再视为平行权威：例如execution定义玩家内容语义、UI定义渲染；route optimization定义RouteState算法、state定义恢复/裁剪时如何调用。`README`已明确冲突时先找owner，不用“更新更晚/写得更具体”覆盖。
- 本轮没有发现仍需保留的硬冲突。后续任何新规则都必须走触发式一致性检查，因此不再允许默认采用“补丁式追加”。

## 实现验证

- 修正前：Route Atlas timing回归发现龙骨第43步显式`做《日常计划》`未进入估时目标。
- 修正后：`tests/test_route_atlas_workbench.py + tests/test_route_atlas_timing_ui.py`共29项全部通过。
- 相关Python脚本`py_compile`通过。
- 冰冠覆盖重新验证仍为`163/163`、未覆盖0；规则治理修正未改变冰冠任务集合。

## 后续使用方式

以后出现新的长期经验时，先判断归属：单任务事实→task-library/observations；重复失败→ERROR-BOOK；当前策略→CURRENT；只有跨地图/跨批次方法才进入rules。若进入rules，必须在同一轮完成受影响规则邻域和实现/测试一致性检查。