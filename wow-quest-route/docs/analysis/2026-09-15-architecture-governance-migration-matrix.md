# 2026-09-15 魔兽项目架构治理：17份核心文档最终迁移矩阵

状态：**文档/测试契约迁移完成；后续只剩数据与Publisher转换验证。**

用途：固定本轮架构治理最终职责，避免下一会话重新根据历史讨论猜设计。旧规划过程由Git历史保存，本文件只保留最终迁移结果。

## 1. 本轮只解决的根问题

同一条任务事实、路线决策或玩家呈现规则不能在多个位置独立维护，导致旧规则覆盖新规则。

最终四层：

1. **Task Card**：单任务事实唯一真源。
2. **Rule Docs**：计算、验证、路线设计、玩家呈现规则唯一owner。
3. **Route Profile**：具体正式路线唯一真源。
4. **Generated Product**：可删除重建的workbench/HTML等产物。

CURRENT是运行时overlay，不是第五个路线真源；Observations是证据/实测，不是Task Card或Route Profile副本。

## 2. 本轮最终关键决策

### 2.1 稳定性优先于绝对去重

Task Card允许同一现实存在三种不同职责表达：

- 机器结构化事实；
- 完整guide/攻略；
- 用户确认的人工推荐备注。

只有机器事实参与程序判断；guide和备注不得被程序反解析成事实。

### 2.2 Fivebox标签与备注独立

Task Card的fivebox机器状态负责：

- 共享；
- 不共享；
- 依次拾取；
- 待实测。

人工推荐备注是另一层，可以明确为空。标签变化不自动生成备注；备注文字也不反推标签。

### 2.3 Route Profile只存原子结构

Route Profile保存task_id、动作kind、NPC/location/transport、顺序、stepGroups、最小entry/exit等原子。可由这些原子生成的完整中文执行句不长期保存。

Route Display按固定转换规则产生中文，例如：

- task + accept + NPC → `NPC → 接《任务》`；
- objective → `↳ 做《任务》`；
- taxi + from/to → 系统飞行文本。

### 2.4 不建设复杂Propagation层

Task Card事实变化后：

`task_id反向索引 → 找引用Profile → 从当前真源重新生成派生结果`

不维护`x-impact`六分类或第二套字段传播真源。重新计算结果若满足Selection触发条件，才进入Selection Review；不自动重排路线。

### 2.5 条件动作保持简单

普通action + 可选`when`，不复制`conditional_accept/conditional_turnin/...`整套动作类型。

### 2.6 Entry / Exit按真实需求增长

只保存当前确实需要跨Profile传递的状态，不预建RouteState God Object。

### 2.7 Timing分三种身份

- Timing Model：公式/参数；
- Timing Observations：真实阶段/多任务/整段实跑墙钟；
- Derived Timing：从当前真源重新计算的结果。

多任务阶段实测不能硬拆进单任务Task Card。

### 2.8 迁移先完整，再测试替代

旧体系迁移到新体系必须：

`迁入 → 信息完整性审计 → unclassified=0 → 才允许新旧Publisher替代测试`

不能边生成页面边发现Task Card/Route Profile漏信息，否则会把“迁移不完整”误判为“新架构能力不足”。

## 3. 17份核心文档最终职责与迁移结果

| # | 文档 | 最终职责 | 结果 |
| --- | --- | --- | --- |
| 1 | `SKILL.md` | 用户请求→最小真源/owner/SOP路由 | PASS；不再枚举全部子规则 |
| 2 | `CLAUDE.md` | 项目宪章：第一目标、授权/影响/历史/安全边界 | PASS；规则目录和详细流程已退出 |
| 3 | `docs/INDEX.md` | 纯路径/资产导航 | PASS；不再承担行为路由/证据规则 |
| 4 | `docs/verified-routes/README.md` | verified-routes目录导航 | PASS；Route Profile标正式路线，workbench标生成/兼容产物 |
| 5 | `docs/rules/README.md` | 唯一规则owner注册表 + 核心名词 | PASS；不复制子规则正文 |
| 6 | `leveling-and-selection.md` | now/later/never删留决策 | PASS；不再拥有XP/Timing/传播表 |
| 7 | `timing-and-benchmarking.md` | Timing模型、观测、派生时间边界 | PASS；多任务实测独立Observations |
| 8 | `execution-and-mechanics.md` | Task Mechanics分类与核验 | PASS；fivebox待实测状态与open question分离 |
| 9 | `state-and-validation.md` | 旧引用兼容指针 | PASS；明确不再是owner，最终可删除/归档 |
| 10 | `route-atlas-optimization.md` | 路线排序/状态/交通/局部重放算法 | PASS；不拥有前端/Task事实 |
| 11 | `route-atlas-player-contract.md` | 前端三owner的极短总路由 | PASS；不再是巨型前端规则 |
| 12 | `route-atlas-ui-and-assets.md` | 页面壳、地图、CSS、控件、资源工程 | PASS；不定义任务备注/路线业务 |
| 13 | `ROUTE-DESIGN-PROCESS.md` | Route Lifecycle调度器 | PASS；不再维护impact传播表/第二算法手册 |
| 14 | `ERROR-BOOK.md` | 历史失败/根因/复发条件/当前owner入口 | PASS；历史修复方式显式历史化 |
| 15 | `docs/task-library/README.md` | Task Card字段字典/三层表达/unknown语义 | PASS；取消template/impact双分类，fivebox标签与备注独立 |
| 16 | `scripts/README.md` | 现役脚本注册表与退役边界 | PASS；143个顶层脚本全部登记，迁移脚本有退出条件 |
| 17 | `tests/README.md` | 永久契约/当前迁移/快照三类测试治理 | PASS；测试不再是第二业务规则源 |

### 3.1 17份之外的活跃入口门禁

17份是本轮最初冻结的核心职责矩阵，不因为后续审查发现额外入口就机械改成18份。但任何仍会被新会话直接读取、并能指导写入位置的活跃文档都必须服从同一架构，不能成为矩阵外的旁路真源。

当前额外门禁至少包括：

- 根`README.md`：只能把模型导向SKILL、rules registry、SOP以及Task Card / Route Profile / CURRENT / Observations / Generated Product的正确身份；不得把workbench或observations描述为长期事实/路线写入口；
- 当前职业/实跑说明（目前包括`docs/verified-routes/DK-STARTING-ZONE-NOTES.md`）：新的任务事实必须先走`TASK_FACT`写Task Card，旧fivebox等兼容文件只能作为证据/兼容投影。

这些入口由永久Registry测试覆盖；以后新增同类活跃入口时也必须纳入该门禁，而不是扩展第二套规则目录。

## 4. 迁移后新增/拆出的唯一owner

这些是17份旧文档职责迁移的落点，不增加平行真源：

- `docs/rules/xp-model.md`：XP唯一owner；
- `docs/rules/route-profile-and-lifecycle.md`：Route Profile定义/生命周期；
- `docs/rules/route-atlas-route-display.md`：结构化Route Profile→动作中文/步骤；
- `docs/rules/route-atlas-task-presentation.md`：Task Card→fivebox标签/人工备注；
- `data/task-cards/schema.json`：Task Card机器shape；
- `data/route-profiles/schema.json`：Route Profile机器shape。

JSON Schema负责shape；Python validator只负责跨字段/跨文件/状态闭环，不能再维护第二套required/enum。

## 5. 测试体系迁移结果

### 永久契约

当前永久架构测试保护：

- Rules Registry唯一入口与渐进式路由；
- scripts顶层登记完整性；
- archive脚本不得回流；
- state旧文档只允许作为兼容指针；
- Task Card / Route Profile JSON Schema与语义边界；
- Route Profile稳定task_id、step覆盖、状态闭合；
- fivebox状态是标签真源；
- 待实测不由open question副作用产生；
- 人工推荐备注与标签独立，且允许明确为空。

### 当前迁移测试

具体task_id、旧Builder、一次性normalize/migrate脚本只属于当前迁移验证；消费者切换完成后随兼容层退役，不升级为永久业务规则。

### 快照

固定点数、固定步骤、精确旧中文、当前某版总分钟数等仍属于地图/Profile快照。下一阶段Publisher替代时用于差异定位，但不得反向逼新架构恢复旧脏数据。

## 6. 本轮文档迁移完成，不等于Publisher已经完成

本轮在此冻结的是**职责和测试契约**。

后续实现/转换阶段仍需：

1. 按最终Task Card字段把旧独有事实/备注/fivebox状态完整迁入；
2. 按最终Route Profile原子模型迁完整路线；
3. 做旧信息归属审计，要求`unclassified=0`；
4. 再生成候选workbench/HTML；
5. 逐step做语义对账，而不是字符串diff；
6. 差异分类为：预期改进 / 数据迁移遗漏 / 转换实现bug / 真正架构表达缺口；
7. 只有确认可无损替代后才切正式Publisher并退役旧写入口。

下一阶段若只发现中文转换/模板组合问题，不需要重新讨论本轮17份文档架构；只有出现“当前结构化真源无法表达真实业务”的实例，才回到架构层。

## 7. 本轮迁移审计门禁

本轮归档前必须全部满足：

- 17/17职责与上表一致；
- active顶层路由无旧`route-profile-and-propagation.md`引用；
- 不存在现役`x-impact`传播owner；
- Task Presentation明确“事实/标签/人工备注”三层；
- `待实测`由fivebox状态变量决定；
- Route Display明确原子→中文固定转换；
- Tests Registry不再列旧Propagation测试体系；
- 永久架构测试通过；
- scripts顶层登记无缺项；
- 编译/Markdown引用基础检查通过。

## 8. 下一会话的唯一入口

下一会话不要重新设计架构。直接读取：

1. `docs/analysis/2026-09-15-architecture-governance-acceptance.md`；
2. 本文件；
3. `tasks/todo.md`中的“数据完整迁移→Publisher替代测试”任务；
4. 具体转换阶段命中的Task Card / Route Profile / owner。

目标是验证转换实现，而不是重新讨论17份文档职责。
