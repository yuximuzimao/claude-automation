# 2026-09-15 魔兽项目架构治理：第一目标、验收清单与结果

状态：**第一目标与验收标准冻结。实现不得为了方便修改标准。**

用途：让本轮架构治理不再依赖某个模型“觉得差不多了”。本文件是下一会话继续转换实现时的最高验收基线。

---

## 1. 第一目标

本轮治理只解决一个根问题：

> **同一条任务事实、路线决策或玩家呈现规则不能在多个位置独立维护，导致旧规则重新覆盖新规则。**

典型触发是《阻断援军》：完整任务知识必须保留，但旧Builder/旧备注不能再次把证据过程和冗长说明带回玩家页面。

最终必须满足：

- Task Card = 单任务事实唯一真源；
- Rule Docs = 计算、验证、路线设计、玩家呈现规则唯一owner；
- Route Profile = 某一具体正式路线唯一真源；
- CURRENT = 当前批次运行时overlay，不是第二路线；
- Observations = 实测证据/样本，不是事实或路线副本；
- Generated Product = 可删除重建，不能人工作为业务真源；
- 修改事实不需要手工同步第二份事实；
- 修改路线不需要手工同步第二份中文路线；
- 玩家展示只能从结构化真源单向生成，不能反向推断事实；
- 本轮不借机重做已验证路线算法、任务删留等无关业务。

### 1.1 稳定性优先于绝对去重

Task Card允许同一现实存在不同职责表达：

1. **机器事实**：唯一参与程序判断；
2. **完整攻略/guide**：供人/模型理解，不被程序反解析；
3. **人工推荐备注**：用户确认后的玩家呈现决策，只控制展示。

它们不是三个事实真源，因为只有第1类拥有机器决策权。

### 1.2 Fivebox标签与备注独立

fivebox机器状态负责玩家标签：

- shared / 共享；
- not_shared / 不共享；
- sequential_loot / 依次拾取；
- pending / 待实测。

人工推荐备注是独立字段，可以明确为空。标签不能自动生成长备注，备注不能反推标签。

### 1.3 结构化路线与中文生成结果

Route Profile只存task_id、动作kind、NPC/location/transport、顺序、stepGroups、条件、最小entry/exit等原子。

完整中文执行句属于生成结果：

`Task Card + Route Profile + Route Display + Task Presentation → Publisher → HTML`

Route Profile不得长期保存可由原子重建的整句中文。

### 1.4 重新生成代替复杂Propagation

不建设独立`x-impact`/六类传播系统。

Task Card变化后：

`task_id反向索引 → 找引用Profile → 重新生成这些Profile的派生结果`

Profile路线决策不自动改变；若重新计算后的时间/XP等满足Selection触发条件，再进入复核。

### 1.5 Timing身份分离

- Timing Model：公式/参数；
- Timing Observations：真实实跑窗口；
- Derived Timing：当前模型计算结果。

多个任务一起跑的阶段墙钟留Observations，不强拆到Task Card。

---

## 2. 本轮“17份文档 + 测试体系迁移”完成标准

这部分必须在本会话完成，完成后即可NEAT归档并换新会话。

### D1 17份职责唯一

以`2026-09-15-architecture-governance-migration-matrix.md`最终表为准，17/17都只有一个明确职责；任何文件单独读就能重新定义另一个owner完整规则则FAIL。

### D2 新拆owner唯一

XP、Route Profile Lifecycle、Route Display、Task Presentation只各有一个现役owner；旧`state-and-validation.md`只能是兼容指针。

### D3 顶层路由一致

SKILL、CLAUDE、INDEX、rules README、verified README、SOP不得重新提升旧workbench/fivebox/Propagation为长期真源。

### D4 Task Card三层定义一致

Task Card字段规范、Task Mechanics、Task Presentation必须一致承认：机器事实 / fivebox标签状态 / 人工推荐备注相互独立；guide不能参与机器判断。

### D5 Route Profile原子化定义一致

Route Profile和Route Display必须一致承认：路线真源存原子语义，中文完整句为可重建输出；地点/NPC/任务/交通不能混成自由文本主数据。

### D6 无复杂字段传播owner

现役规则不允许重新维护`x-impact`六分类传播系统。跨Profile只通过task_id反向索引定位并重新生成。

### D7 Timing Observation边界一致

多任务/step/整图实跑墙钟不写回单任务Task Card；Timing规则、Task Card规范、SOP对此无冲突。

### D8 Tests不成为第二真源

Tests Registry明确永久契约 / 当前迁移 / 快照三类；永久测试只随稳定规则/机器契约变化；具体task_id迁移bug不升级为永久业务规则。

### D9 永久架构测试通过

至少覆盖：规则owner路由、script registry、archive回流、Task Card/Route Profile schema与语义、fivebox标签/备注独立。

### D10 Scripts Registry完整

顶层所有`.py`均登记；一次性迁移脚本有明确退出条件。

### D11 旧owner/旧术语扫描通过

现役入口不得引用旧`route-profile-and-propagation.md`作为owner；旧`x-impact`只能出现在明确否定/历史语境，不得成为当前规则。

### D12 文档基础完整性通过

现役Markdown引用的核心owner路径存在；Python迁移/contract文件可编译；没有明显半写/损坏文件。

---

## 3. 下一阶段“数据完整迁移 + Publisher替代验证”标准

这部分**不要求在本会话完成**。下一会话只做实现/转换，不重新讨论本轮架构，除非发现结构化模型真实表达不了业务。

### P1 旧信息先完整归属

旧Task/fivebox/note/semantic/route数据的每条有效信息必须归入：

- Task Card机器事实；
- Task Card完整guide；
- Task Card fivebox状态；
- Task Card人工推荐备注；
- Route Profile原子动作/路线信息；
- Timing Observation；
- History/Evidence；
- 明确批准丢弃；
- 需要用户确认。

开始Publisher替代测试前必须`unclassified = 0`，需要用户确认项必须处理完成。

### P2 Task Card完整后才测页面

不能边生成新页面边发现Task Card漏攻略/待实测/备注，否则无法区分“数据没迁完”和“架构不能表达”。

### P3 Route Profile语义完整

旧路线必须转成正确的原子动作，不能只做数量对账；尤其要验证地点/NPC/交通/接做交/条件/carry语义。

### P4 候选Publisher不污染正式页面

先生成独立候选输出，不覆盖当前正式页面。

### P5 逐Step语义对账

不做机械HTML字符串diff。每step比较：地点、NPC、动作、任务、交通、条件、标签、备注、step边界和玩家顺序。

### P6 差异必须分类

每个差异只能属于：

1. 预期改进/旧脏数据不应迁回；
2. 新数据迁移遗漏；
3. 转换/Publisher实现bug；
4. 当前结构化模型真实表达缺口。

只有第4类才允许重新打开架构设计。

### P7 无损替代后再切换

候选页面确认可替代后：切正式Publisher → 禁止旧写入口 → Generated Product可删除重建 → 退役兼容源/迁移脚本。

---

## 4. 最终双模型审查要求

用户已确定：第一目标、实际验收清单、最终验收结果都要再分别交给Codex和DeepSeek独立只读审查。

规则：

- 两边先不看对方报告；
- 重点检查是否背离第一目标、是否出现第二真源、是否过度设计；
- 两边共同命中的Blocking优先；
- 对“为了未来可能需求再加一层抽象”的建议默认不采纳，除非能指出当前真实失败案例；
- DeepSeek偏向简单性审查；Codex/Sol的复杂化建议必须额外警惕过度设计。

---

## 5. 本轮实际结果

验收日期：2026-09-15

### 5.1 第一轮独立外审

- DeepSeek：`PASS WITH NON-BLOCKING CLEANUP`。主要提醒为Task Card字段字典与schema命名漂移，以及显式`fivebox.status`完成后应删除stage→badge兼容回退。
- Codex：`BLOCKED BY ARCHITECTURE CONTRACT ISSUE`。提出4组最小Blocking：活跃入口仍指向旧真源；SOP/Task Card字段字典与schema不一致；`fivebox.status`尚非唯一标签真源；Route action schema未保证最小可渲染原子。
- 交叉判断：上述4组均属于当前冻结契约的真实落实问题，不是P1–P7或需要重开架构的问题，因此接受并按最小改动修复；未采纳任何新增registry/taxonomy/Propagation/RouteState抽象。

### 5.2 Blocking修复后的当前结果

- **17份核心文档职责：17/17 PASS。** 同时补审根`README.md`与现役DK写回入口，避免17份矩阵之外的活跃文档重新引导旧真源。
- **D1–D12：12/12 PASS（内部复验）。** 根README明确Task Card / Route Profile / Observations / Generated Product身份；DK出生区实测写回先走`TASK_FACT`；SOP与Task Card字段字典已对齐schema。
- **永久架构测试：24/24 PASS。** `test_rule_routing.py + test_task_card_route_profile_schema.py + test_task_presentation_contract.py`。新增永久断言只覆盖本次已证实的通用契约：根入口不提升旧真源、现役DK写回不直写旧fivebox、scripts registry双向一致、Task Card缺status必须失败、Route action缺最小原子必须失败。
- **当前迁移验证：3/3 PASS。** `test_dk_task_card_presentation_migration.py`仍为B类，兼容层退役时一并退役。
- **合计相关测试：27/27 PASS。** 最后一次运行耗时约1.01秒。
- **Scripts Registry：PASS。** 顶层143个`.py`与README注册表双向差集均为空；当前迁移脚本仍标`MIGRATE`并保留退出条件。
- **旧owner/旧术语扫描：PASS。** 旧`route-profile-and-propagation.md`不再被活跃路由使用；`x-impact`只存在于明确“不要建设”的否定语境。
- **Task Card机器契约：PASS。** `fivebox.status`现为schema必填；当前59张卡全部显式有值：`pending=49 / shared=7 / not_shared=3`。无结果即`pending`，不再用“字段缺失”表达未知。
- **Task Presentation：PASS。** 已删除`_derived_badge()`及stage→badge兼容反推；标签只读显式`fivebox.status`。人工推荐备注继续只读`presentation.note_override`，10208保持`shared + note=""`。
- **Route Profile机器契约：PASS。** action schema按kind要求当前真实需要的最小原子：task动作含task/location；accept需NPC/target/condition之一；turnin需NPC/target；transport需from/to；交互/炉石/飞行点等要求相应原子。当前`hellfire-dk-speed`通过schema、跨卡引用和状态闭环。
- **迁移脚本契约：PASS。** Task Card迁移器不再生成`knowledge_status/direct_followups/impact`等旧shape，并直接生成显式fivebox.status；Route Profile迁移器可在严格action schema下dry-run通过（59任务、227 actions、11 steps、6条件动作、exit carry=10103）。
- **规范化脚本幂等：PASS。** 写入58张缺失status后再次dry-run为`changed=[] / count=0`。
- **编译：PASS。** 核心lib、两份迁移器、normalizer与4组相关测试`py_compile`通过。

### 5.3 本轮未完成但明确属于下一阶段，而不是本轮Blocking

以下全部按P1–P7留到下一会话：

1. 把其它旧Task/fivebox/note/semantic/route独有信息迁入最终Task Card / Route Profile / Timing Observations等新真源；
2. 旧信息归属审计达到`unclassified=0`并处理全部需要用户确认的备注；
3. 生成独立候选Publisher/workbench/HTML；
4. 逐step语义对账；
5. 修转换实现bug或数据遗漏；
6. 确认无损替代后切正式Publisher、禁止旧写入并退役兼容源/迁移脚本；
7. Publisher切换后再做全地图玩家前端规则审计。

### 5.4 最终独立复审与冻结结论

- Codex最终Delta复审：`PASS WITH NON-BLOCKING CLEANUP`；第一轮4组Blocking全部`CLOSED`，永久测试假绿问题`CLOSED`，没有新的架构契约Blocking。
- DeepSeek最终Delta复审：`PASS`；上一轮C1/C2与Codex 4组Blocking全部闭合，没有新的当前契约Blocking，也没有发现新过度设计。
- Codex仅提出两处非阻塞措辞清理（Task Presentation docstring残留badge override措辞、rules registry把“共享标签”与机器状态可能混淆），已在NEAT前同步修正。

**最终状态：Blocking=0。本轮“17份核心文档 + 新owner + schema + 机器契约 + 测试契约 + 顶层路由”正式冻结，可以NEAT归档并换新会话。**

下一会话不得因为普通数据迁移或中文转换bug重新讨论本轮架构；只有出现可复现的“真实业务无法用当前Task Card / Route Profile / Rule模型表达”的案例，才允许重新打开架构设计。

### 5.5 用户确认后的Task Card契约Delta（2026-09-15）

后续真实迁移审查证明原Task Card把任务攻略拆成`objectives / mechanics / fivebox stages / verification.open_questions`过度结构化，且要求先建立一套当前并不存在、也无必要的全任务类型taxonomy。用户确认这是实际业务表达偏差，因此按上述“真实业务无法用当前模型自然表达”例外做最小契约修正，不重开Route Profile/Publisher总体架构。

当前有效Delta：

- Task Card继续以稳定`task_id`为唯一单任务真源；Questie/数据库适合机器消费的身份、Availability、奖励保持结构化；
- 任务目标、NPC/入口/楼层、任务物、Boss/事件/载具、掉落和混合五开细节统一进入完整`guide`事实层，不再拆`objectives / mechanics / fivebox stages`；
- `fivebox.status`固定为`shared / not_shared / sequential_loot / special / pending`五类；混合/条件型任务用`special`，细节读guide；
- 五开未知直接用`pending`，不再维护Task Card通用open-question机器层；
- 当前正式页面备注迁移阶段先按task_id无损进入`presentation.note_override`，备注精简另做后续专项审计；
- Task Card只通过`timing_rule_ref`选择Timing规则，时间样本继续属于Timing Observations，不为Timing重新拆任务攻略；
- 旧信息迁移改为逐task_id闭合；批量工具只收集证据、搬运无歧义数据库字段、校验和报冲突，不自动解释自然语言并批量落库。

现有59张地狱火Task Card已完成shape转换并通过幂等规范化；当前fivebox分布为`pending=49 / shared=5 / not_shared=3 / special=2 / sequential_loot=0`。这只是现有种子卡契约转换，不代表P1全量任务信息迁移完成。
