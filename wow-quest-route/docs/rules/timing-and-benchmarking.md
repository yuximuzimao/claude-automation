# 路线墙钟模型与实跑基准

用途：这是项目中**墙钟时间如何分解、计算、校准和保存实跑样本**的唯一规则owner。Task Card只通过`timing_rule_ref`引用这里定义的计算规则/规则族，Route Profile提供真实路线顺序与空间状态；本模型输出步骤/任务块/路线时间，不决定任务删留，也不定义HUD放在哪里。

任务是否值得做见`leveling-and-selection.md`；任务机制分类见`execution-and-mechanics.md`；路线排序见`route-atlas-optimization.md`；时间结果怎样显示见Route Atlas展示/UI规则。

## 1. 时间模型的输出

对任一可执行Route Profile，至少可以计算：

- 每个自然任务块/stepGroup的中心时间；
- 合理下界/上界；
- 整段/整图总时间；
- 各成本分项；
- 不确定来源；
- 模型版本与使用的Task Card事实版本；
- 有可靠实跑时的预测偏差。

时间结果是**上下文派生值**：不写进Task Card固有事实。

## 2. 固定分解模型

统一使用：

`T_total = T_move + T_objective_service + T_accept_turnin + T_wait + T_special`

### `T_move`

玩家在当前Route Profile真实顺序中发生的移动：

- 步行/地面坐骑/游泳；
- 角色自主飞行；
- 系统飞行；
- 炉石；
- 船/飞艇/固定交通；
- 任务传送/脚本移动；
- 因地形必须产生的绕路。

系统交通必须使用**该路线时点真实可用的RouteState**，不能拿整图最终飞行网络倒推早期时间。

### `T_objective_service`

真正推进任务目标的服务时间，例如：

- 击杀；
- 掉落收集；
- 固定物交互；
- 使用任务物；
- 探索/对话目标；
- 与其它任务共享目标后剩余的真实新增服务量。

### `T_accept_turnin`

五号接取/交付/连续对话及Hub切号时间。

同一NPC/同一Hub批量动作共享基础成本，禁止给每个任务重复计完整Hub开销。

### `T_wait`

无法通过主动执行消除的等待：

- 命名怪刷新；
- 固定物刷新；
- 事件重置/波次间隔；
- 随机掉落方差带来的额外击杀/等待；
- 服务器竞争。

没有可靠证据时必须保留区间/不确定性，不伪造精确秒数。

### `T_special`

不适合归入普通移动/目标服务的固定或高方差成本：

- 护送；
- 防守/波次事件；
- 载具；
- 特殊脚本；
- 洞穴/复杂楼层带来的稳定额外导航成本；
- 五号逐号定位/重组；
- 可预期的断跟随/失败重试成本。

## 3. 共享成本不能重复收费

时间模型必须在**当前Route Profile上下文**计算边际墙钟，而不是把每张Task Card的独立样本直接相加。

以下成本按实际共用次数计：

- 同一转场；
- 同一路段；
- 同一Hub批量接交；
- 同一批怪；
- 同一洞穴进入；
- 同一脚本事件；
- 同一返回/离图。

多个任务共享一次战斗/移动时，背景任务只计真实新增边际成本。

## 4. Task Card如何选择时间规则

Task Card不再把任务拆成fivebox stages或objective/mechanic类型供Timing消费。它只提供`timing_rule_ref`，指向本文或机器配置中已经定义的一个计算规则/规则族。

规则：

- `timing_rule_ref = null`表示这个任务尚未完成Timing分类；模型不得从guide、玩家备注或`fivebox.status`自由猜一个精确公式。
- `fivebox.status`只负责玩家执行分类；`shared / not_shared / sequential_loot / special / pending`不是完整的时间模型。
- 同一类真实任务反复出现后，可以在Timing owner中定义一个可复用规则，再让对应Task Card引用它。
- mixed/条件型任务可以引用一个专门的组合规则；不需要把任务本身重新拆成stage。
- 若现有规则无法表达真实任务，先扩Timing owner/模型配置，再写新的`timing_rule_ref`。

旧模型中的`shared_kill / personal_drop / same_corpse_multi_character_loot / per_character_interaction`等细分名称，如果仍有计算价值，应作为**Timing规则族**保留，而不是重新变成Task Card fivebox机器事实。

当`timing_rule_ref`尚未填写、且其差异足以显著影响总时间时，当前预测必须保留不确定范围或暂不产出精确任务级估时，不能为了凑完整结果擅自解析guide。

### 4.1 Timing机器输入解析合同

`timing_rule_ref`只回答“使用哪一个可复用规则族”，它本身不携带目标数量、掉率、交互次数、事件固定时长或职业速度等全部参数。Derived Timing必须通过一个统一的**Timing Input Resolution**阶段解析规则实际需要的参数，任何地图Builder不得自己另选来源。

输入身份固定分为：

1. **Task Card结构化事实**：规则实际需要且Task Card已经有稳定机器字段的值，直接读取当前Task Card；
2. **Effective Quest Source Adapter**：Task Card没有为Timing保存结构化副本时，可以按稳定`task_id`从当前有效Questie/数据库适配器读取机械基础量（例如标准目标数量/实体关系），并把源版本/hash计入fingerprint；这只是避免为了Timing复制一套Task Card objectives schema，不是让Questie凌驾于用户实测；
3. **Timing Input Config / task-id parameter**：当前服务器实测、特殊脚本或高优先级证据已经证明基础源不适用时，用版本化Timing配置保存该规则真正需要的机器参数、适用scope和source refs；不得把任务中文名写进代码分支；
4. **Profile/global calibration params**：职业/Profile击杀速度、切号成本、Hub成本、移动能力等当前校准参数；
5. **Timing Observations**：只按本文件的scope/precision/clean规则参与校准或直接锚定可隔离成本，不自动覆盖任务事实；
6. **Movement外部静态输入**：例如Leatrix系统飞行表，必须通过canonical movement/flight-point registry绑定具体edge并记录源版本/hash。

解析优先级不是“后读文件覆盖前读文件”的自由合并。固定原则：

- 已有高优先级当前服务器事实时，显式Timing Input Config必须承接它，Questie只能作为旧基础证据；
- Task Card已有结构化当前事实时，不允许另一个Timing脚本复制不同值；
- Questie adapter只补**尚无更高优先级结构化Timing输入**的基础量；
- Observation是测量/校准证据，不因一次样本自动改写掉率、目标数量等任务事实；需要提升为长期参数时先经人工/规则核验写入版本化Timing配置；
- 任一来源冲突而没有明确当前值时返回`UNKNOWN_INPUT`，不得从guide/备注或旧页面文本猜值。

每个Derived Timing fingerprint至少包含：当前Profile/version、引用Task Cards及`timing_rule_ref`、Timing规则注册表版本、实际使用的source-adapter hash、task-id Timing输入配置版本、Profile/global参数版本、匹配Observation集合、movement/Leatrix版本。它用于审计“这份Timing由哪些输入生成、是否串版本”；Timing输入或算法变化时只重算真实受影响的Profile/Program Timing，fingerprint不负责自动决定impact范围。

## 5. 随机掉落模型

随机掉落任务至少需要：

- 对应`timing_rule_ref`定义的计算口径；
- 规则需要的需求量/掉率/单尸件数等模型参数；
- 目标密度/刷新；
- 平均击杀周期；
- 是否与其它任务共享战斗/移动；
- 拾取/切号操作成本。

这些参数来自Timing模型配置、Questie基础数据或Timing Observations；不得为了计算方便重新把Task Card guide拆成另一套objective/fivebox schema。

### 期望值不是唯一输出

低掉率/小样本可能有明显右尾；除了中心值，必须给合理区间或方差来源。

首次实跑因不知道高密度刷点而产生的学习时间不能直接写成任务固有随机长尾；攻略事实或Timing规则/参数修正后，重新计算clean baseline。

## 6. 固定物模型

固定物/容器/场景交互至少考虑：

`T_interact = 操作次数 × 单次交互/切号成本 + 必要刷新等待 + 实际路线偏移`

如果同一对象可五号连续点击，移动成本只算一次；如果每次点击后消失，则按刷新机制增加等待/移动。

## 7. 战斗模型

普通战斗使用当前职业/Profile对应的校准参数，而不是在Task Card保存统一“每只怪X秒”。

模型至少区分：

- 普通怪；
- 精英/命名Boss；
- 多目标AOE；
- 载具战斗；
- 当前只有主控真正输出的五开执行模式。

任务怪等级、目标数量和Boss特殊机制属于任务攻略事实；Timing若需要机器计算，只能通过`timing_rule_ref`对应规则及其模型输入消费，不能重新解析Task Card自由文本。

若职业/Profile变化，战斗参数可以变化，但Task Card不改。

## 8. 当前校准参数的身份

参数分两类：

### 全局/Profile模型参数

例如：

- 当前职业普通怪平均击杀周期；
- 切号基础成本；
- 固定物单次交互成本；
- Hub基础+每任务附加成本；
- 地面坐骑速度/移动能力。普通自主地面移动不要求路线数据区分骑马/步行；粗算默认按当前角色可用的100%地面坐骑速度处理。当前圣骑Profile可使用其已知职业移动加速校准，其它没有额外移动加速的职业按普通100%坐骑校准；最终仍由同Profile/同版本的段落实跑Observation覆盖粗算；
- 地图实际世界尺寸（yard）。当项目中的 `zone_id` 不能唯一对应玩家地图/Route Profile时，尺寸必须按 `profile_id` 保存和读取，不能为了复用一个zone id把不同地图共用同一尺寸；只有zone id本身已证明唯一时才允许使用zone级后备。旧Timing中已有且来源明确的地图尺寸可以作为基础模型参数保真迁移，不能要求重新实跑才能使用。

它们属于模型配置，可由后续实跑重新校准，不是游戏永久常数。跨地图自主转场只作为Program/地图间过渡上下文保存，不计入任一单地图Profile的墙钟/G小时；若未来需要统计全程端到端墙钟，可单列transition overhead，不反写地图基线。

### 任务级实测参数

例如：

- 某事件固定3分42秒；
- 某Boss平均1分20秒；
- 某固定物刷新约45秒。

这类时间数据进入Timing Observations或Timing模型配置，并按task_id/规则引用关联；Task Card本身只保存`timing_rule_ref`，不再保存timing samples。

旧模型中曾使用的`普通怪15秒/只`、`个人尸体拾取9秒/具`、`固定物7秒/角色/次`、`Hub 0.65分钟 + 0.16分钟×任务条数`等数值属于**当前历史校准参数**，迁移时必须进入显式模型配置并带版本；不能继续散落在脚本/规则中成为不可追踪常量。

本次文档治理不擅自修改这些数值，只改变它们的归属方式。

## 9. 移动模型

地面/飞行距离必须使用真实地图比例和路线几何；洞穴、水下、山体不能只用二维直线。

Route Optimization提供：

- 当前路径；
- 当时可用飞行点；
- 炉石状态；
- 交通方式；
- route geometry/地形路径。

Timing只负责把这些动作换算成墙钟。

如果实测证明某段系统鸟绕路比自主飞行慢，更新交通/Route Profile选择后再算时间；Timing不自行修改路线。

## 10. clean baseline与实跑时间

### clean baseline

默认预测口径：

- 正常刷新；
- 无明显竞争；
- 无死亡/迷路；
- 已知正确入口/机制；
- 按当前已知最佳合法执行方法。

### 实跑异常单列

至少区分：

- 学习/找入口；
- 操作失误；
- 死亡/重跑；
- 断跟随；
- 服务器竞争；
- 随机掉率/刷新；
- 路线本身结构问题。

不能把第一次迷路永久烙进任务固有时间，也不能把真实随机长尾都当“玩家失误”删掉。

## 11. Timing Model / Observations / Derived Timing 三种身份

时间系统只分三种身份，不再把它们混在一个文件里：

1. **Timing Model**：公式、参数定义、校准方法。规则owner是本文；机器需要的参数应进入独立模型配置，而不是写进Task Card或实跑记录。
2. **Timing Observations**：真实发生过的墙钟样本。统一保存在`data/observations/route-timing-runs.json`等观测层，是可持续追加的历史证据。
3. **Derived Timing**：把当前Task Card + Route Profile + Timing Model + 可用Observations计算出来的步骤/整图时间。它是可重建派生结果，不是Task Card或Route Profile真值。

### 11.1 多任务阶段实测属于Observations

如果用户实际记录的是“这一段连续做了A/B/C几个任务共18分钟”，**不能为了方便把18分钟拆写进三张Task Card**。

这条样本应保持原始范围，至少记录：

- `profile_id`与当时的`profile_version`；跨Profile样本同时记录`program_id/program_version`与经过的Profile边界；
- 起止范围（start/end action、step或可复核的人类锚点）；
- 当时覆盖的任务集合快照，仅用于解释历史样本，不反向定义当前Route Profile；
- 原始开始/结束墙钟或原始总分钟；
- 明确扣除的暂停/脏时间窗口；
- 有效墙钟；
- `exact / approximate / journey_derived / mixed`等精度；
- 是否包含学习、迷路、死亡、竞争、错误操作；
- 是否可用于模型校准；
- 来源（Journey / 用户记录 / 其它可复核证据）。

这类阶段样本的价值是比较同一路线迭代前后的真实效率，也可用于校准任务块/路线模型；除非后来能独立隔离某个任务自身的固定服务时间，否则不要反推成单任务固有耗时。

### 11.2 单任务隔离样本也属于Timing Observations

例如某任务固定事件从触发到结束稳定约3分42秒，且可与移动/Hub/其它任务完全分离，可以作为按task_id关联的高质量Timing Observation或模型校准输入，但不写回Task Card。

整图、step、多个任务共同推进、共享移动/共享战斗得到的墙钟同样留在Timing Observations，只是scope和精度不同。

### 11.3 当前兼容状态

旧`data/observations/route-timing-runs.json`仍作为历史原始来源保留，其中`model / long_term_targets`等字段不再拥有Timing Model规范权。其中24条`runs`已经完整迁入纯Observation投影`data/observations/route-timing-observations.json`，并保存原始记录与源hash；迁移工具已归档。

- 自动校准资格要求同时满足：`clean`、精确Profile/version、稳定action范围；缺任一项都保留为历史证据但`calibration_eligible=false`；
- 当前24条旧run没有一条满足完整新合同，因此**0条**会被Stage 7静默套到当前Profile/Program；
- 以后新增可校准样本必须直接绑定现役Profile/Program版本和稳定action范围，不再依赖旧`route_key`/step号推断；
- Route Atlas旧页面仍可保留历史展示快照，但它不是Observation/Derived Timing owner。

旧Route Atlas估时CLI及其Timing snapshot写入链已经归档，不再属于当前执行路径。现役Timing算法owner是`lib/route_timing.py`；`scripts/rebuild_route_profile.py`只在显式完整诊断时调用Timing owner，不是日常Timing更新入口。

## 12. 重叠时间样本不能直接相加

日常或批量任务若同批接取、同时推进、集中交付，每条任务`接取→完成`区间会重叠。

因此：

- 独立任务速度优先用独立/小批次样本；
- 一整批的真实效率用“批次开始→最后交付”的墙钟；
- 只有单任务样本之和与同集合批次墙钟基本闭合时，才允许把它们当可独立相加的稳定成本。

## 13. 预测与实跑比较

同一Route Profile/相同终点比较：

`delta = actual_wall_clock - clean_baseline`

继续拆为：

- 路线可优化；
- 执行熟练度/失误；
- 随机刷新/掉率；
- 竞争/服务器环境；
- 模型参数误差。

不能用一次`XP/h`、任务数、步骤比例线性外推不同任务块。

## 14. 与Task Selection的边界

Timing只回答：

- 这个动作/任务包/路线预计多久；
- 时间分解是什么；
- 不确定性在哪里。

它不回答：

- 这个任务值不值得做；
- 应该现在做还是80后做；
- 应该删除哪一个任务。

这些由Task Selection把时间结果与奖励/XP/后续链一起比较。

## 15. 与玩家前端的边界

Timing不定义：

- HUD第二行长什么样；
- 右上状态卡放哪里；
- “预计总时间”字体/颜色；
- 没有实测时是否显示占位。

模型只提供结构化值；Route Display决定语义呈现，UI & Assets决定容器/CSS。

## 16. 失效与传播边界

Timing Model只定义“哪些输入会使现有时间派生值失效”，例如：

- Task Card的`timing_rule_ref`变化；
- Route Profile顺序、交通、动作或共享成本结构变化；
- Timing规则/模型参数或对应Observations变化；
- 原本未分类任务获得可用的timing_rule_ref；
- Timing公式/解析器实现变化。

Task Card或Route Profile输入变化后，通过`task_id → Route Profile`引用关系重新生成受影响路线的Timing派生结果；不维护第二套`x-impact`传播分类。

Timing结果是否形成Selection Review条件只读Review Trigger / Selection owner；Timing结果变化本身不得自动修改任务集合。

## 17. 可机械验证的不变量

至少检查：

- 显式`做`任务不会漏出objective service；
- 同一共享战斗/移动不重复收费；
- 任务时间规则只读`timing_rule_ref`，不解析guide/玩家备注，也不把fivebox状态当完整时间公式；
- `timing_rule_ref=null`时保留不确定边界，不擅自猜规则；
- Route Profile每个需要发布的stepGroup都有Timing结果/或明确`includeInTotal=false`；
- 实跑样本scope与当前Route Profile/version匹配；
- 模型公式/参数有版本，不存在地图Builder各自复制一套公式。

## 18. 正式Timing操作

- 单Profile Timing：`python3 scripts/build_route_timing.py <profile_id>`。
- Program没有合法Timing基线，或Program级Timing输入/合同改变：`python3 scripts/build_program_timing.py <program_id>`。
- 已有合法Program Timing基线，仅指定成员Timing受影响：`python3 scripts/update_program_member_timing.py <program_id> <profile_id>`；其它成员结果原样复用。
- Timing只消费当前fresh Movement / Service Context与Timing输入；缺少必要输入时返回`requirements`，不得从旧页面总分钟或历史快照补值。
