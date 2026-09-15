# Route Lifecycle SOP：路线新建、修订、发布与实跑写回

用途：这是项目唯一的**流程调度器**。它只回答“发生某类变化后，按什么顺序调用哪些权威owner、传播到哪里、何时验收”。

它不定义任务机制、XP公式、Timing公式、任务删留算法、路线排序算法、前端颜色/备注模板或测试断言；这些必须回各自owner。

## 0. 先分类，再动手

任何修改先明确：

1. 用户授权范围；
2. 本次改变的权威对象；
3. 变更类型；
4. 是否会向其它Profile/生成物传播。

变更类型：

- `TASK_FACT`：单任务事实变化；
- `TASK_PRESENTATION`：人工推荐备注、标签映射或其它纯展示变化，Task Card机器事实不变；若`fivebox.status`等机器状态值改变，属于`TASK_FACT`；
- `PROFILE_STEPS`：某Profile动作/步骤/顺序变化，任务集合基本不变；
- `PROFILE_TASK_SET`：正式增删/延后/恢复任务；
- `NEW_PROFILE`：新建正式Route Profile；
- `CURRENT_RUNTIME`：当前角色进度/暂停/异常，只影响runtime overlay；
- `UI_ENGINEERING`：页面、地图、控件、CSS、资源；
- `MODEL_OR_RULE`：公共规则/模型/算法变化；
- `REPUBLISH_ONLY`：业务真源不变，只重新物化生成物；
- `ARCHITECTURE_MIGRATION`：真源/schema/消费者迁移。

一次请求可以命中多个类型；按真实依赖组合流程，不强迫只选一个。

## 1. 公共前置

### 1.1 找到唯一真源

按需确认：

- task：稳定`task_id`与Task Card；
- route：`profile_id`与当前Profile版本/status；
- runtime：`CURRENT.md`；
- rule/model：`docs/rules/README.md`指向的唯一owner；
- generated product：只能追溯来源，不能直接当业务真源修改。

如果只能定位到“HTML/workbench里这段文字”，先追到Task Card / Route Profile / Rule owner再改。

### 1.2 最小读取

- 当前现场：`CURRENT.md`；
- 单任务事实：对应Task Card；
- 正式路线：对应Route Profile；
- 规则：只读命中的owner；
- 历史错误：定向检索`ERROR-BOOK.md`相关案例；
- 测试：最终按`tests/README.md`选最小组合。

禁止为了局部问题全文加载全部rules、ERROR-BOOK或archive。

### 1.3 授权边界

- 未受影响的已验证Profile部分默认冻结；
- 测试失败、顺手发现其它问题都不能自动扩大业务修改；
- 额外问题先报告或留todo，除非用户已授权同类/整图/架构范围。

## 2. `TASK_FACT`

固定流程：

1. 按Task Card schema修改当前有效事实，并保存证据/适用范围；
2. 旧错误值进入证据/纠错历史，不继续占当前字段；
3. 更新/关闭相关open question；
4. 通过`task_id → Route Profile`反向索引找到全部现役/可复用Profile；
5. 从Task Card + Profile + 对应Rule/Model重新生成这些Profile的派生结果；
6. 若重新计算后的结果满足Selection触发条件，再进入Selection Review；
7. 按Tests Registry运行最小验证；
8. 若玩家可见结果变化，只冷读受影响窗口。

不要先在Route Profile、semantic脚本或HTML里写自由文本“记住这个事实”。

## 3. `TASK_PRESENTATION`

先判断：

- 单任务特殊表达 → Task Card `presentation.note_override`；
- 同类通用规律 → Task Presentation owner；
- 如果其实改变了任务机制事实 → 退回`TASK_FACT`。

然后：

1. 通过稳定task_id找适用Profile；
2. 重新投影Presentation；
3. 不改任务集合/顺序；
4. 按Tests Registry跑Presentation + 最小publisher/build验证；
5. 只冷读受影响任务/步骤。

## 4. `PROFILE_STEPS`

1. 只修改目标Route Profile的结构化动作/stepGroups；
2. 若顺序会改变RouteState，调用Route Optimization处理受影响窗口；
3. 从更新后的Profile重新生成其Timing/XP/Display/Presentation等可重建派生结果；
4. 未受影响前后缀与其它Profile保持冻结；
5. 按Tests Registry运行Profile/Route Display/真实受影响模型的最小组合；
6. 冷读受影响步骤窗口。

如果修改过程中发现原因为任务事实错误，先转`TASK_FACT`，不要把事实硬编码进Profile。

## 5. `PROFILE_TASK_SET`

1. 候选任务必须先有足够Task Card事实；
2. 调用Task Selection做正式删留/延后决策；
3. 修改目标Route Profile的任务集合；
4. 调用Route Optimization重新组织真实受影响窗口；
5. 从更新后的Task Card + Profile重新生成XP/Timing/Display/Presentation派生；
6. 运行Tests Registry对应组合；
7. 单任务增删只冷读受影响窗口，整图任务集重构才做整Profile冷读/薄审查。

Selection理由留内部decision/analysis，不进Task Card和玩家页面。

## 6. `NEW_PROFILE`

固定顺序：

1. 定义`profile_id / scope / character_profile / entry_state_contract / goal`；
2. 建立候选任务集合与Task Card覆盖；
3. 必要时调用Task Selection；
4. 调用Route Optimization生成正式结构化动作/步骤；
5. 调用XP/Timing等适用模型；
6. Route Display + Task Presentation生成玩家语义；
7. Publisher生成聚合数据/HTML；
8. 按Tests Registry执行该Profile完整契约组；
9. 从最终玩家视图完整冷启动复走。

任何缺失的任务事实先补Task Card，不在Profile里临时补机制。

## 7. `CURRENT_RUNTIME`

如果只是一次现场状态：

- 更新CURRENT/实跑观测；
- 不自动修改正式Route Profile。

如果现场反馈证明了长期事实或正式路线错误：

- 任务事实 → `TASK_FACT`；
- 路线顺序 → `PROFILE_STEPS`；
- 任务集合 → `PROFILE_TASK_SET`。

CURRENT只保存当前Profile/version、执行位置、等级经验、关键runtime差异、暂停/异常和下一恢复动作，不复制整张路线或Task Card攻略。

可靠计时样本交Timing observations；脏时间/学习/异常按Timing owner定义处理。

## 8. `UI_ENGINEERING`

1. 只读UI & Assets owner；
2. 只改页面/资源实现；
3. 按Tests Registry运行UI/build/JS/资源验证；
4. 若字段结构同时改变Route Display或Task Presentation，则升级为多类型变更。

没有业务语义变化时，不跑Selection/XP/整图路线审计。

## 9. `MODEL_OR_RULE`

1. 先确认唯一owner；
2. 只在owner修改规则/模型；
3. 通过稳定引用关系确定真实消费者范围，并重新生成受影响派生结果；
4. 更新必要实现与测试；
5. 不趁机改无关Task Card/Profile；
6. 顶层路由只有在owner/实现稳定后才同步。

Task Card变化涉及多个Profile时，只通过task_id反向索引找到引用Profile并重新生成，不建设第二套字段传播表。

## 10. `REPUBLISH_ONLY`

1. 从当前Task Cards + Route Profiles + Rules/Models生成聚合数据；
2. 生成唯一HTML；
3. 跑publisher/build技术验证；
4. 检查生成前后是否出现非预期业务差异。

若重新发布产生业务变化，追溯真源/生成实现；禁止手工修Generated Product。

## 11. 玩家冷读触发

只要玩家可见语义/步骤实际变化，就进行人工冷读。

范围：

- 局部修改 → 受影响任务/step及必要上下文；
- 传播到多个step → 完整受影响窗口；
- 新Profile/整图重构 → 全Profile；
- 数据模型迁移 → 机械全量对账 + 关键/受影响Profile冷读。

冷读标准由Route Display / Task Presentation / UI各owner定义；SOP不复制它们的具体规则。

## 12. ERROR-BOOK

ERROR-BOOK只回答“过去同类操作怎样失败过”。

流程：

1. 按本次风险定向检索；
2. 读取现象/根因/复发条件；
3. 当前正确做法回唯一owner；
4. 只有具备未来复发价值的新错误才追加；
5. 不把新规则正文复制进错题本。

## 13. `ARCHITECTURE_MIGRATION`

真源/schema/消费者迁移固定顺序：

1. 建迁移矩阵和退出条件；
2. 建立新owner/schema；
3. 从旧源迁入，不先删旧源；
4. 新旧全量对账；
5. 切消费者；
6. 禁止旧源继续人工写入；
7. 旧源降为compatibility projection或archive；
8. 运行架构对抗式验收；
9. 最后同步`rules README → INDEX → SKILL → CLAUDE/项目入口`；
10. 再做与迁移无关的业务清债。

兼容期任何重复数据都必须明确：哪一处authoritative、哪一处是projection、projection如何生成、何时退出。两个位置不能同时允许人工独立修改。

## 14. 收尾归属

- 任务当前事实 → Task Card；
- 正式路线任务/动作/顺序 → Route Profile；
- 当前角色执行状态 → CURRENT；
- 实跑样本 → observations；
- 通用方法/模型 → 对应rule owner；
- 历史复发案例 → ERROR-BOOK；
- 待办 → todo；
- Generated Product → publisher输出；
- NEAT/archive → 仅在用户要求或既定归档流程触发。

一句话：**SOP只负责把变更送到正确owner、调用传播和验收；任何业务算法在这里完整出现，都说明职责又开始回流。**
