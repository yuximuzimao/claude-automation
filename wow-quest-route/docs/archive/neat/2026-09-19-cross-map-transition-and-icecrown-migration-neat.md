# 2026-09-19 跨图转场合同 / Icecrown 迁移差异 NEAT

## 本轮范围

本轮继续在 `feat/wow-architecture-migration` worktree 中做 Stage 1–14 implementation 完成后的全 Profile 真实 artifact / 业务清债。用户明确指出：跨地图 NPC 传送、相位/灵魂视角/镜像空间等任务，玩家真正需要的是“触发什么 → 进入什么上下文 → 做什么 → 如何返回”，不应为了满足本地图坐标模型强造点；能可靠解决则直接解决，证据不足但会改变玩家操作/路线选择的问题必须留给最终人工裁决，不能为了全绿自行猜测。

## 一、本轮新增并已验证的通用合同

### 1. 非绘图执行上下文：`transition_context`

Stage 5 / Route Profile geometry 新增 `location_role`：

- 默认 `map_anchor`：玩家需要依赖本地图位置导航的真实点；坐标没有证据时保持 UNKNOWN。
- `transition_context`：NPC/任务传送、相位/镜像/灵魂视角等中间执行状态，只用于保持 visit / movement / 玩家操作顺序；玩家不需要在本地图按该点导航时允许 `x/y=null`，且“没有地图点”本身不再形成 requirement。
- 若玩家仍需在该上下文内自主移动/定位，禁止用 `transition_context` 逃避空间建模，必须回到 `map_anchor` 或保持 UNKNOWN。
- `transition_context` 若反而携带地图坐标，Stage 5/11 会报错，避免把“上下文”偷换成假地图点。

真实 Icecrown 中 `icecrown-p256-dalaran` 已改成 `transition_context`。因此《阿达尔的恩赐》“沙塔斯 → 达拉然”的中间态不再因为缺少达拉然落点坐标阻塞。

### 2. 最终人工决策 ledger

新增唯一 ledger：

`tasks/final-human-decisions.json`

只收**会改变玩家操作、路线选择或是否接受残余业务假设，且现有证据不足以可靠裁决**的问题；普通 Timing 参数、坐标缺口、经济输入等技术 UNKNOWN 仍由原 stage 自己保留，不把噪音推给用户。

允许状态：

- `open`
- `resolved`
- `accepted_unknown`（仅用户明确接受残余不确定性后使用）

项目级 `evaluate_project_final_audit()` 现在必须显式接收 human decisions；任意 `open` 项都会令项目保持 `requirements / cutover_ready=false`，即使所有 Profile 都已 pass。

当前两条 open：

1. `HD-001-icecrown-13082-post-adal-transfer`
   - 已确认阿达尔把玩家从沙塔斯传送到达拉然；
   - 当前旧路线随后写“炉石暗影拱顶 → 沉默墓地交《阿达尔的恩赐》”；
   - 用户明确表示已不记得当时实跑的精确过程，因此这段返回冰冠操作暂不升级为用户实测事实；
   - 最终只需用户确认/纠正传到达拉然后的实际返回操作，不需要提供坐标。

2. `HD-002-nagrand-to-borean-cross-continent-route`
   - 北风 reusable 入口明确从“飞艇刚抵达战歌要塞、未接未做”开始；
   - 现有历史资料没有恢复出纳格兰收尾后如何离开外域并到达该飞艇入口的完整玩家操作链；
   - 不允许用常见路线、地图顺序或 Program 顺序自动补“纳格兰 → 奥格瑞玛 → 飞艇”；
   - 最终若仍找不到证据，只需用户确认实际复用的玩家操作顺序。

### 3. Route Program 边界转场链

发现原 Route Program 只能表达：

- 来源 Profile 单条 exit movement；
- 两端共享同一 `handoff_ref`。

它无法诚实表达“外域 → 主城/中转 → 船/飞艇 → 下一地图”“任务传送 → 中转上下文 → 返回”等多段跨 Profile 操作。

已新增 Program-owned `boundary_transitions`：

- 只允许相邻两个 Profile；
- 只允许 `move / taxi / fixed_transport / quest_transport / use_hearth`；
- 不允许接/做/交任务，不复制 Profile geometry/stepGroups；
- operation chain 必须连续；
- 与来源 Profile exit movement 或共享 handoff 同时宣称同一边界真值时直接 blocked，禁止双真源；
- Stage 5 输出 `operation_kind=transition_chain`；
- Stage 7 逐 operation 计时：Program taxi 可复用 Leatrix Program binding，其余 operation 必须有 Program-level calibration；缺时长继续 requirements，不因操作链已知就伪造 Timing。
- `data/timing/profile-action-parameters.json` 和 `flight-edge-bindings.json` 已扩成同时支持 `programs`。

真实 Program 当前已写入两条证据足够的边界：

- `zangarmarsh-fivebox → nagrand-fivebox-67-68`
  - 已知 9797 / 莉萨奥营地 → 加拉达尔的跨图引导语义；
  - 已写 Program `move`；
  - 移动 mode 尚未证实，所以 Stage 5 保留 `move_action_mode_required`。

- `dragonblight-fivebox → dalaran-mainline-77`
  - Dragonblight 已携带 12791《魔法王国达拉然》；
  - 历史资料确认其作为免费达拉然传送能力实际使用过；
  - 当前 Program 链表达为“龙骨末点 → 阿格玛之锤的大法师艾萨斯·夺日者影像 → 12791 任务传送 → 达拉然紫罗兰之门”；
  - 返回影像的移动 mode 尚未证实，继续 UNKNOWN；传送结果不再当作普通地图边。

加入以上两条后，完整 Program 的 `program_boundary_transition_unproven` 从 **6 降到 4**。这不是追求全绿，而是把两条“完全不知道边界发生什么”降成“玩家操作链已知，仅剩 mode/Timing 输入缺失”。

当前仍完全未证明的 4 条：

- `nagrand-fivebox-67-68 → borean-fivebox`
- `storm-peaks-fivebox → icecrown-fivebox`
- `icecrown-fivebox → sholazar-fivebox`
- `zuldrak-fivebox → grizzly-fivebox`

其中 Nagrand→Borean 已进入 HD-002，暂不自动补。

## 二、Icecrown 新发现：这是迁移版本落后，不应由 Program 边界绕过

在继续核 `icecrown-fivebox → sholazar-fivebox` 时发现：

当前 `icecrown-fivebox.json` 的最后动作停在：

- 苦难高地《血毒的命运》交付；
- 最后 location 为 `icecrown-p270 / 苦难高地·狡诈者维雷斯`。

但项目较新的 2026-08-30 正式重排规则明确要求：

1. 跨图救治链先闭合；
2. 再做最终西南扫；
3. 《在恐惧之门前》后接《科雷萨的守卫者》《击破碎片》；
4. 科雷萨完成后才进入苦难高地后半；
5. 苦难高地收尾后**最后回奥格瑞姆之锤交《科雷萨的守卫者》《击破碎片》**；
6. 冰冠正式出口为奥格瑞姆之锤，承接索拉查。

更强证据：

- `docs/analysis/2026-08-30-icecrown-reordered-route-v1.md` 第38–40步/当前执行第5–7步明确写出该顺序；
- `scripts/build_icecrown_entry_route.py` 当前现役构建逻辑也已包含：
  - `科雷萨：守卫者 + 三碎片 → 回舰`
  - 最后 `奥格瑞姆之锤 → 交《科雷萨的守卫者》《击破碎片》`
  - “冰冠整图主路线在本段闭合”；
- 2026-08-28 Journey 归档还明确记载首组实际冰冠结束于奥格瑞姆之锤，并已携带 12521 承接索拉查。

当前 Route Profile 却仍把 13316/13328 objective+turnin 放在跨图救治链之前，并在后面继续瓦哈拉斯/苦难高地，说明 Profile 迁移时使用了较旧候选顺序，**没有完整吸收后来已经固化的正式重排**。

这不是“再加一条 Icecrown→Sholazar Program transition”就能解决的问题；若那样做会把错误 Profile 末端掩盖掉。

## 三、下一会话唯一恢复点

先处理 **Icecrown 受影响窗口的迁移保真修复**，不要开始新的全图优化：

1. 以当前现役 `scripts/build_icecrown_entry_route.py` + `docs/analysis/2026-08-30-icecrown-reordered-route-v1.md` + 已有 Journey/NEAT 为迁移证据；
2. 精确识别当前 Profile 中从科雷萨/跨图救治链到苦难高地/最终出口的旧顺序窗口；
3. 只把后来已经固化的正式重排无损迁回 `icecrown-fivebox.json`：
   - 不重新设计整个 Icecrown；
   - 不处理当前 DK raw live feedback；
   - 不因为冷读/Timing 方便而改变任务删留；
4. 修复后重新跑 Stage 3–7 / Program continuity + movement，确认 Icecrown 的真实出口恢复为奥格瑞姆之锤；
5. 再判断 `icecrown → sholazar` 是否已有足够证据闭合：
   - 旧审计曾给出“奥格瑞姆之锤 → K3借用双足飞龙自主飞回银色比武场 → 系统飞行达拉然 → 12521脚本进索拉查”；
   - 必须用修复后的正式出口和最新路线证据重新核，不能直接照抄旧转场。
6. 然后再继续剩余 `storm→icecrown`、`zuldrak→grizzly` 等 Program 边界清债。

## 四、本轮验证

本轮关键针对性回归：

- `transition_context + human-decision gate` 首轮：49/49；
- Program boundary transition + Stage 7 synthetic contracts：44/44；
- 归档前集中回归：
  `test_task_card_route_profile_schema.py`
  `test_route_program_contract.py`
  `test_route_movement.py`
  `test_route_timing.py`
  `test_route_display.py`
  `test_route_final_audit.py`
  → **71/71 passed**。

这些测试证明新合同与门禁实现稳定，不代表当前真实 Profile/Program artifact 已 ready。

## 五、NEAT 结构审查

本轮新增知识已回到现役 owner，而没有另起平行规则：

- `transition_context` → Route Profile/Movement owner；
- Program boundary transition → Route Program + Stage 5 Movement，Timing 参数只进 Stage 7；
- human-decision gate → Stage 14 Final Audit + 唯一 ledger；
- Icecrown 新问题按“迁移保真”分类，未另起特殊例外架构。

没有把历史 analysis 提升为新 owner；历史文档只作为迁移证据。没有覆盖正式 workbench，也没有切 Publisher。

## 六、版本控制状态

本轮按用户要求先做 NEAT / 恢复入口归档。继续保留整个 `feat/wow-architecture-migration` worktree：

- **不合并主干**
- **不提交**
- **不推送**
- **不覆盖正式 Route Atlas 页面**

下个会话从 Icecrown 受影响窗口迁移修复继续。
