# 2026-09-15 架构治理冻结 NEAT

## 本阶段结论

本轮只解决一个长期复发问题：项目规则、任务事实、路线决策和玩家页面曾经存在多个可独立维护来源，导致用户已经纠正的新规则会被旧Builder、observations、semantic脚本、workbench或旧文档重新覆盖。

架构治理现已冻结。第一目标仍是：**把“任务路线”作为独立打金方式做成可长期复用的高净金币 / 玩家真实墙钟系统。**

最终职责：

- Task Card：单任务当前事实唯一机器真源；
- Rule Docs：计算、判断和展示规则的唯一owner；
- Route Profile：具体正式路线的唯一真源；
- CURRENT：当前批次runtime overlay / 恢复点；
- Observations：实测证据与样本，不是Task Card/Profile平行真源；
- Generated Product：workbench/HTML等可重建输出，不接受反向人工维护业务真值。

冻结契约只读：

- `docs/analysis/2026-09-15-architecture-governance-acceptance.md`
- `docs/analysis/2026-09-15-architecture-governance-migration-matrix.md`

## 关键冻结决定

- Fivebox玩家状态由Task Card显式`fivebox.status`唯一提供：`shared / not_shared / sequential_loot / pending`。
- Fivebox标签与人工推荐备注独立；`presentation.note_override.text=""`表示用户已经明确判断无需备注。
- 事实/完整攻略、机器状态、人工推荐备注可以同时描述同一任务，但职责不同；程序只能消费结构化机器字段做判断，不能解析guide/备注反推事实。
- Route Profile只保存task_id、原子action、NPC/location/transport、stepGroups、必要condition和最小entry/exit；不保存可由这些原子重建的完整中文执行句。
- 条件动作使用普通action + `when`，不建设`conditional_*`taxonomy。
- 不建设`x-impact`/六分类Propagation Engine；Task Card事实变化后通过task_id反向索引找到引用Profile并重新生成派生结果，Profile路线决策不自动改变。
- 不建设庞大RouteState；只在出现真实跨Profile需求时增加最小状态。
- Timing分为Timing Model / Timing Observations / Derived Timing；多任务共同实跑墙钟保留原始scope，不强拆成虚假单任务时间。

## 机器契约与样本状态

最终复验：

- 当前Task Card：59张，全部通过最终schema/validator；`fivebox.status`分布为`pending=49 / shared=7 / not_shared=3`，缺失0；
- 10208《阻断援军》：完整机制事实保留，`fivebox.status=shared`，人工推荐备注明确为空字符串；
- `lib/task_presentation.py`已删除stage→badge的`_derived_badge()`回退；
- 当前Route Profile：`hellfire-dk-speed`通过严格schema、跨卡引用、step覆盖和状态闭环；当前为59 tasks / 227 actions / 11 steps / 6条件动作，exit carry为10103；
- Route action schema已要求当前kind所需的最小可渲染原子；
- Scripts Registry：顶层143个`.py`与注册表双向一致；
- 相关测试：永久契约24项 + 当前迁移验证3项 = **27/27 PASS**；
- `normalize_hellfire_task_cards_v1.py`重复运行：`changed=[] / count=0`；
- 旧`route-profile-and-propagation.md`不再作为现役owner；未引入新的registry/taxonomy/Propagation/RouteState层。

## 双模型最终审查

独立外审先发现并修复了4组真实契约问题：活跃入口回流旧真源、字段字典/SOP与schema漂移、fivebox.status存在第二标签路径、Route action原子门禁过松。

修复后的最终Delta复审：

- Codex：`PASS WITH NON-BLOCKING CLEANUP`；4组Blocking全部CLOSED，无新Blocking；
- DeepSeek：`PASS`；上一轮问题与Codex 4组Blocking全部闭合，无新Blocking、无新增过度设计。

Codex剩余两处措辞清理已在NEAT前处理：Task Presentation docstring不再提badge override；rules registry明确“人工备注/标签映射”与修改`fivebox.status`机器事实的区别。

结论：**Blocking=0，架构治理完成并冻结。**

## 下一会话唯一主线：P1–P7

不要重新讨论架构。下一会话直接从`tasks/todo.md`最高优先项开始：

1. 先把旧Task/fivebox/note/semantic/route独有信息全部迁到Task Card / Route Profile / Timing Observations / Evidence等正确新真源；
2. 对旧信息逐条做归属审计，达到`unclassified=0`，需要用户确认的备注也必须归零；
3. 信息完整后才生成独立候选Publisher/workbench/HTML，不覆盖当前正式页面；
4. 新旧页面按每个Step做语义对账，不做机械HTML字符串diff；
5. 差异只分为：预期改进 / 数据迁移遗漏 / 转换实现bug / 结构化表达缺口；
6. 只有“真实业务无法由当前Task Card / Route Profile / Rule模型表达”的可复现缺口，才允许重开架构；普通中文生成错误、漏字段、迁移器解析错误只修转换/数据层；
7. 确认无损替代后再切正式Publisher、禁止旧写入口并退役兼容源/迁移脚本；最后再做全地图前端规则审计。

## 当前实跑恢复点

第一组五兽人双手鲜血DK已进入地狱火DK速度路线。有效计时暂停在开始10629《肮脏的工作》时；之后操作均为脏时间，恢复计时前不计入本轮墙钟。10230《战斗的号角》曾误删除，用户会在恢复后补接，不把这次误操作当路线设计问题。

拍卖行准备方面，2026-09-14实查后当前只有奥杜尔的圣物有足够库存可按稳定预购方案保护；赞加三种原计划预购物和其它材料以后均按当时真实库存重新判断。

## 收尾边界

- 当前游戏状态以`docs/verified-routes/CURRENT.md`为准；
- 当前待办以`tasks/todo.md`为准；
- 本NEAT只记录阶段冻结结果，不承担现役规则正文；
- 未执行commit或push。
