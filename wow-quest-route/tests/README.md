# 测试分层与选择

用途：本目录只负责**验证现役规则和机器契约**。测试不是业务真值，也不是第二份架构文档；不能因为旧测试失败就反向修改Task Card、Route Profile、CURRENT或用户实测。

## 1. 三类测试

### A. 永久契约测试

只保护跨地图、跨Profile长期稳定的业务/数据契约。

例如：

- Task Card的机器schema与禁止字段；
- Route Profile必须使用稳定task_id、不得复制Task Card事实；
- stepGroups必须完整覆盖动作且保持顺序；
- `presentation.note_override`只控制人工推荐备注、不能改机器事实或fivebox状态；
- Timing/XP等模型的公式与输入输出契约；
- Publisher只能从现役真源生成正式产物；
- archive/旧脚本不能重新成为现役写入口。

**只有对应的总规则/机器契约真的变化时，才修改这类测试。**

普通数据变化、单任务纠正、单Profile重排不应为了“让测试通过”去改永久测试脚本；它们只需要用现有永久契约验证新数据是否合法。

### B. 当前功能 / 当前迁移验证

只保护当前明确进行中的开发或架构迁移。

例如：

- 当前`hellfire-dk-speed`从旧Builder迁到Task Card + Route Profile；
- 一次性规范化脚本是否幂等；
- 迁移后10208不再从旧Builder硬编码长备注；
- 新旧路线逐action语义对账。

这类测试可以包含具体task_id、具体Profile和具体迁移脚本。对应迁移结束后，测试应一并删除或归档，**不得因为曾经发生过一次bug就升级为永久业务契约。**

当前：


### C. 快照 / 历史参考

固定点数、步骤数、某任务位于某一步、整段精确中文、某版本总分钟数等，默认属于快照。

快照用于说明“这次改了什么”，不是永久真值。用户批准的新事实/规则/路线使快照失效时，更新或退役快照，禁止为了跑绿恢复旧业务结果。

## 2. 永久测试按稳定契约边界组织

不按每个视觉元素或每个task_id建永久测试。稳定边界当前分为：

- **Task Card Contract**：schema、字段语义、unknown/partial/verified、禁止route决策、机器事实与guide/presentation的边界。
- **Dependency / Fingerprint Contract**：稳定ID反向索引、Profile输入集合、规则/配置/Observation/source版本参与fingerprint；真实输入变化必须使相关派生stale，无关字段变化不得误伤全部模型。
- **Route Profile Contract**：稳定task_id、动作结构、条件、最小`entry_requirements`、step覆盖、禁止任务事实副本、禁止人工exit state、status/version与schema边界。
- **Route Program Contract**：有序`profile_ids`、Program scope/goal/真实`entry_state_contract`/version/status、profile_id反向索引；不得复制成员Profile内部路线，也不得用`display.order`替代业务执行顺序。
- **Availability / Route Replay Contract**：唯一Replay从Program/上一Profile/CURRENT/冷启动提供的实际RouteState + Task Card结构化Availability + Profile actions重放active/completed/条件任务、任务栏、炉石、飞行点及当前启用的其它RouteState；Profile `entry_requirements`只核最低要求，不冒充完整入口；不得从guide/HTML/中文动作猜合法性。
- **Cross-Profile Continuity Contract**：Stage 4只按Route Program顺序把上一Profile fresh Replay输出喂给下一Profile并核其`entry_requirements`/外部要求，不实现第二套状态转移；版本不匹配不得静默承接。
- **Canonical Spatial / Movement Contract**：真实space/visit与原子movement唯一；复合旧point可拆多edge；UI投影坐标、旧`location.transport`不得成为第二业务真源。
- **Service Context Contract**：Target Cluster / Spatial Instance / Background/service coverage中可派生部分可删除重建；只有规则允许的最小route-only原子可持久化，UNKNOWN足以影响成本时阻止精确Timing。
- **Timing Contract**：`timing_rule_ref`→统一Input Resolution→move/objective/hub/wait/special→step/route Derived Timing；输入优先级、Observation适用、Leatrix绑定、fingerprint/stale必须可测，不解析guide/备注。
- **XP Contract**：结构化entry等级/经验 + Profile真实turnin顺序 + Task Card XP + 版本化参数→等级时间线/衰减/上下界；不得从标题/subtitle猜起点。
- **Economy Contract**：Task Card rewards + fresh Derived XP/Timing + Economy policy/Observation→gross/known cost/net/Gh；满级折金口径、choice数量、partial/unknown与fingerprint必须可测。
- **Review Trigger Contract**：Selection/Optimization触发诊断只报告`no_review / selection_review / optimization_review / blocked_unknown`等状态；`build_route_review_trigger.py`必须能从现有Stage 3/4–9 artifacts独立物化Profile/Program `review-trigger`，Stage 14消费该artifact；不得依赖完整rebuild、更不得静默改正式Profile。
- **Observation / CURRENT Contract**：profile/version/range绑定、污染/precision、历史样本保留与当前适用性；Observation/CURRENT不得成为第二正式路线真源。
- **Task Presentation Contract**：显式`fivebox.status`→标签、`presentation.note_override`→备注、override scope；不测试具体任务文案。
- **Route Display Contract**：Route Profile→地点/NPC/接做交/步骤结构；不测试Task Card机制。
- **Publisher / Generated Product Contract**：只接受fresh上游派生；统一payload可重建workbench/HTML/player-view，生成物不能成为反向写入口。
- **UI / Offline Asset Contract**：唯一工作台、地图配准/相对资源、JS/HUD/控件与离线`HTML + maps/`完整性；UI不重造业务语义。
- **Registry / Archive Contract**：规则owner、脚本注册、Tests Registry、旧消费者与archive边界。

这些边界与`docs/rules/`的现役owner一致。若owner规则没有改变，不应因为一次具体数据修改去改永久测试定义。

## 3. 修改后跑什么

先看本轮真正改了哪个owner/数据，再组合最小测试。

先由`ROUTE-DESIGN-PROCESS.md`完成信息分类，再由对应业务owner确定本次规则/操作；跨owner传播只按`route-profile-and-lifecycle.md`的直接消费者原则。本文件只把已经确定的受影响owner映射到最小测试组合，不重新定义传播规则。

- Task Card事实变化：运行Task Card契约 + 真实受影响的Availability/Timing/XP/Economy/Presentation契约；不因为`TASK_FACT`三个字全跑所有模型。
- Presentation变化：Task Card/Task Presentation/Display/Publisher相关最小契约；不跑XP/路线优化。
- Route Profile actions/task set/contract变化：Profile契约 + 按各owner依赖实际命中的Replay/Continuity/Movement/Service/Timing/XP/Economy/Display/Publisher子集。
- Profile display变化：Route Profile + Display/Publisher/UI/asset契约；不跑Timing/XP/Economy。
- Timing/XP/Economy规则变化：对应永久owner契约 + `route-profile-and-lifecycle.md`定义的真实直接下游消费者。
- CURRENT/Observation变化：对应版本/scope契约 + 真正引用它的Derived模型。
- UI工程：UI/Publisher/asset相关测试；业务语义不变时不跑Task Mechanics/Selection。
- `ARCHITECTURE_MIGRATION`：测试范围由该次独立迁移计划决定；必须覆盖新owner合同、真实迁移样本和旧消费者清零，不从永久SOP复制固定Stage模板。

默认不使用`pytest tests`作为日常门禁。只有公共规则/架构大改或明确最终验收时，才扩大到完整相关契约组。

## 4. 人工冷读

以下不能由自动测试代替：

- 备注是否真的有执行价值；
- Questie已经显示的信息是否重复；
- step是否过长；
- 页面是否能一眼看到下一动作；
- UI遮挡/滚动是否影响实跑。

局部改动只冷读受影响窗口；新Profile或整图重构才完整复走。

## 5. 当前文件治理

- `test_task_card_route_profile_schema.py`：A类，必须只使用合成/通用样本验证Task Card和Route Profile稳定机器契约，不绑定10208业务内容。
- `test_task_presentation_contract.py`：A类，验证通用Task Presentation规则，不绑定具体地图/任务。
- `test_task_card_rewards.py`：A类，验证Task Card精确奖励读取的稳定输入/汇总契约；批量读取必须与单task读取一致。
- `test_task_evidence_index.py`：A类，验证当前Task Evidence Index的通用查询契约：Questie有效前置字段解析、当前Task Card/奖励证据聚合和查询缓存行为；不得重新读取旧workbench或迁移期账本。
- `test_questie_effective_corrections.py`：A类，验证Questie WotLK corrections解析支持双参数`l10n`与`profKeys`等有效命名空间。
- `test_route_dependencies.py`：A类，验证Stage 1 Dependency/Fingerprint通用契约：canonical hash稳定、Task Card/Profile/Route Program分区hash可精确失效、schema/Character Profile缺失fail-closed、`profile_id → programs`反向索引机械生成、未知Program Profile引用必须显式暴露而不是猜测。
- `test_route_program_contract.py`：A类，验证Stage 2 Route Program稳定合同：只保存严格`profile_ids`顺序与Program scope/entry/goal/version/status，不复制成员Profile内部路线；成员Profile必须存在并匹配game variant/character profile，现役Program不得引用retired Profile。
- `test_character_profile_contract.py`：A类，验证Stage 2 `scope.character_profile`必须解析到独立机器配置；当前普通五开绑定血精灵圣骑、DK绑定兽人死亡骑士，Character Profile只保存Availability静态身份，不承载等级/声望/天赋等runtime/model状态。
- `test_route_replay.py`：A类，验证Stage 3唯一Route Replay/Availability通用合同：任务栏上界、条件任务、静态身份、动作时点前置/互斥、炉石/飞行点，以及**实际入口RouteState**可选字段“省略=UNKNOWN、显式空/null=已知为空/未绑定”的三态语义；Profile `entry_requirements`只核最低要求，不承载完整入口状态；XP/等级门槛只登记`deferred`并交Stage 8解析。
- `test_route_movement.py`：A类，验证Stage 5 Canonical Spatial/Movement永久合同：physical place≠visit occurrence、`map_anchor`与非绘图`transition_context`分工、相邻visit只有一条canonical incoming edge、显式移动action只引用不复制kind、`cross_zone`由两端zone派生、旧`transport`特殊线型不能自动造玩家动作、多段movement必须拆visit；跨Profile边界可由唯一离图动作、共享`handoff_ref`或Program-owned `boundary_transitions`证明，且Program链必须连续并拒绝与Profile出口形成双真源。
- `test_route_service_context.py`：A类，验证Stage 6 Service Context永久合同：每条结构化`objective`默认独立服务，同visit不自动等于共享；只有显式`shared_service`才能声明同visit零/共享服务；Background只保存稳定action范围与`carry_if_incomplete / fill_if_incomplete / covered_complete`三种收口策略；Stage 6 fingerprint必须随route-only service决策变化。
- `test_route_timing.py`：A类，验证Stage 7永久Timing合同：UNKNOWN不得默认补时、Hub按真实visit批量计费、shared/background不双收费、条件接交只消费Stage 4 `action_execution`、Profile/Program canonical movement分别计费、Leatrix binding、partial known cost、range来源与精确fingerprint；不得解析guide/旧step总时长。
- `test_questie_timing_source.py`：A类，验证共享Effective Quest Source adapter：历史foundation与Stage 7共用同一objective数量解析；只有无歧义count可成为机器输入，多余数字/多掉落来源保持review，Questie源缺失时不得回退旧foundation或guide。
- `test_route_xp.py`：A类，验证Stage 8永久XP合同：唯一模型配置、任务XP衰减/取整、机器化entry state、五号独立推进、Stage 3 deferred等级门槛、跨Profile传播、保证下界/风险上界与UNKNOWN语义；禁止从标题/goal或旧预算猜等级经验。
- `test_route_economy.py`：A类，验证Stage 9永久Economy合同：实际交付等级决定未满级/满级任务金币；满级折金复用Stage 8基础XP公式且不乘服务器练级倍率；`NO_MONEY_FROM_XP`、choice/fixed卖店价值、成本覆盖、fresh Timing/G-hour、Profile/Program Economy Observation、市场估值及UNKNOWN/fingerprint都必须fail-closed且不可反写Task Card。
- `test_route_economy_observation_recording.py`：A类，验证Economy Observation唯一记录入口：Profile/Program精确版本绑定、原始金币差/资产数量保真、clean与污染项互斥、重复ID拒绝。
- `test_route_review_trigger.py`：A类，验证Stage 10永久Review Trigger合同：Selection八类稳定触发ID、Optimization十四个Hard Validator ID、Profile/Program精确version、完整coverage、上游freshness、`no_review / selection_review / optimization_review / blocked_unknown`路由及fingerprint；缺Review Context绝不能默认`no_review`，任何诊断都不得自动决定now/later/never、删任务或改Profile。
- `test_route_display.py`：A类，验证Stage 11永久Display/Presentation合同：Profile原子actions/stepGroups/geometry→结构化地点/NPC/接做交/交通/step语义；Task Card identity/fivebox/note override单向附着；只有complete fresh Timing可显示精确分钟；上游blocked/requirements只允许诊断投影；禁止HTML、旧workbench/semantic/route-model fallback；地点把NPC或交通句当display name时只报requirement不自动改Profile。
- `test_route_publisher_payload.py`：A类，验证Stage 12永久Publisher Payload合同：只接受Stage 11 `route_display` + profile-bound Route UI；原样透传steps/Task Presentation/Timing语义，保留Profile/version/Program上下文与fingerprint；地图只允许离线`maps/`路径；Stage 11 requirements/blocked只可生成`publishable=false`诊断payload；禁止旧points/actionHtml/noteHtml与其它业务fallback。
- `test_route_player_assets.py`：A类，验证Stage 13永久HTML/player-view/offline合同：两类输出只读Stage 12 Publisher payload；HTML内嵌payload且运行时无网络/项目JSON依赖，具备Profile切换、上一/下一段、当前/剩余播放、跟随和HUD收起；player-view不经HTML round-trip；本地map缺失或Publisher非publishable时正式写入门fail closed。
- `test_route_final_audit.py`：A类，验证Stage 14永久最终审计合同：严格核对Stage 1–13顺序/implementation/evaluation、Stage 1 root fingerprint、Stage 11→12→13 fingerprint链、新链旧消费者清零、player-view内部token/过程话术/过长步骤冷读，以及显式完整Profile集合的项目级`cutover_ready`门禁。
- `test_rule_routing.py`：A类，验证项目结构契约：SOP只保留14类信息分类、关键边界与停止条件；正式操作只在对应唯一owner出现且不得跨owner重复；项目CLAUDE服从工作区根CLAUDE；`docs/rules/README.md`只做目录；Todo是唯一未完成事项真源；已经退出的治理/中央执行/decision/state中间层不得复活；迁移历史不得回流永久SOP。

其它地图测试默认属于对应Profile开发验证或快照，除非逐条确认它保护的是公共永久契约。

## 6. 测试环境

项目依赖声明在`pyproject.toml`。使用项目虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest <本轮最小相关测试>
```

不要修改系统Python，也不要依赖全局环境。

## 7. 失败处理

失败先分类：

1. 现役规则/数据真的错 → 修权威源；
2. 公共实现错 → 修实现；
3. 当前迁移兼容错 → 修B类迁移层；
4. 旧快照过期 → 更新/退役快照；
5. 与本轮无关 → 记录，不扩大当前修改。

一句话：**永久测试保护稳定契约；迁移测试保护当前切换；快照只记录历史形态。三者不能混。**
