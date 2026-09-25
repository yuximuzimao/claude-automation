# Route Lifecycle 最终审计规则

用途：这是 Route Lifecycle **Stage 14 Mechanical Audit + Player Cold Read** 的唯一规则 owner。它只回答“Stage 1–13 是否形成同一条可验证、可发布的派生链，以及最终玩家产物是否存在明显执行可读性问题”，不重新计算前 13 层业务规则，也不修改 Task Card、Route Profile 或 Route Program。

## 1. 输入边界

当明确执行**完整单Profile诊断**时，最终审计只消费该次 `rebuild_route_profile.py` 诊断运行生成的：

- Stage 1–13 stage records（implementation/evaluation + Stage 1 root fingerprint）；
- Stage 11 Display reports；
- Stage 12 Publisher payloads；
- Stage 13 player-assets report 与 player-view；
- 当前现役消费者源码/脚本注册表，仅用于检查旧通道是否重新进入新链。

禁止重新读取最终 HTML、旧 `workbench-routes.json`、旧 semantic 文案来恢复任何业务事实。Stage 14 不拥有 Availability、Movement、Timing、XP、Economy、Selection、Display 等算法，只检查它们的既有机器结果和链路身份。

## 2. Implementation 与 Artifact 必须分离

Stage 14 implementation 完成表示：

- Stage 1–13 顺序和 implementation 状态可机械核验；
- Stage 11 → 12 → 13 fingerprint 链可机械核验；
- 现役新链是否重新依赖旧 Publisher/workbench/actionHtml/noteHtml 可机械核验；
- 最终 player-view 有独立冷读诊断；
- 项目级切换有显式完整 Profile 集合门禁。

它不要求某条当前 Route Profile 已经业务全绿。若 Stage 1–13 中仍有 `requirements/blocked`，Stage 14 必须原样汇总，并使当前 Profile `publishable=false`；不得通过修改真源消灭诊断来证明 Stage 14 正确。

## 3. 机械审计

至少检查：

1. Stage 1–13 名称与顺序完整；
2. 13 层 `implementation_status=implemented`；
3. 每层当前 `evaluation_status` 原样传播：`blocked` 为最终硬阻断，`requirements` 保持未证明；
4. Stage 1 root fingerprint 与本次 rebuild 根 fingerprint 一致；
5. Stage 12 `stage11_input_fingerprint` 必须对应同 Program 上下文的 Stage 11 report；
6. Stage 13 `publisher_fingerprints` 必须与本次 Stage 12 payload 顺序一致；
7. 新生命周期现役消费者不得读取旧 `workbench-routes.json`、旧 `route_publisher.build_route_payload`、`actionHtml/noteHtml` 作为业务输入；
8. 已退出当前正式链的旧builder/player-view/candidate publisher不得被现役消费者调用；本次迁移仍需用于对拍的工具只能作为明确的migration-only工具存在，cutover后必须完成反向审计并归档；
9. Stage 13 已负责离线地图存在性与正式写入门，Stage 14只消费其结果，不再建立第二套资产算法。

任何接口缺失、串版本、现役旧旁路复活均 fail closed。

## 4. Player Cold Read 与迁移语义对拍

冷读只读 Stage 13 直接从 Publisher payload 生成的 player-view。

数据模型/Route Profile/Publisher 架构迁移还必须额外做**旧/新玩家表达逐句语义对拍**（玩家视角语义对拍）。这不是字符串 diff，也不能由 schema/validator 通过代替。对每一个实际改变玩家可见表达或动作结构的迁移窗口，都要把旧正式路线/旧 candidate 中玩家看到的原表达，与新 player-view 同一窗口并排检查，至少逐项确认：

- 接/交/做/使用/飞行/炉石/传送等动作语义一致；
- NPC、目标、任务名、起点/终点一致；
- 动作先后顺序与“先…再…”关系一致；
- “共享/不共享/依次拾取/仅一号操作/等待/前置”等限定条件没有丢失或扩大；
- 新结构拆 visit、拆 transport 时不得把旧句中的一次复合动作改成另一种玩家行为；
- 仅允许不改变玩家含义的格式化、拆行、去 HTML、结构化标签变化。

每个受影响窗口必须给出 `same`、`changed_intentionally` 或 `mismatch`。`same` 表示表达方式可不同但玩家执行含义等价；`changed_intentionally` 必须有独立真源/用户授权说明为什么新含义应覆盖旧路线；`mismatch` 必须回对应 owner 修正，不能进入正式切换。无法判断就保持requirements；也就是无法确认时按 `requirements` 保留，不得默认等价。

自动可检查：

- 内部 `A/C/T` 等任务动作 token 不得泄漏；
- `【需要单独修正优化】`、旧 workbench 字段、HTML 标签等内部标记不得泄漏；
- “已验证/经审计/已实测/测试结果/为什么这样排序”等形成过程语言进入玩家文案时标记 review；
- 单步骤动作正文明显超过约 10 行时标记 `cold_read_step_overlong_review`。

“约 10 行”只是人工报警信号，不是自动拆步骤规则。Stage 14 不得据此重排/拆分 Route Profile，也不得从最终文本反推 Task Card 或路线事实。

## 5. 单 Profile 与项目级切换是两层门禁

`evaluate_profile_final_audit()` 只回答某一个 Profile/Program 上下文的最终链是否可发布。

正式项目切换必须额外调用 `evaluate_project_final_audit()`，显式给出本次要求覆盖的完整 `required_profile_ids`：

- 项目全部未完成事项只读`tasks/todo.md`；会改变玩家动作、路线选择或对未证业务假设的接受、且阻止正式切换的事项，直接在同一未完成Todo项上标记`[CUTOVER-BLOCKER:<稳定ID>]`；
- 旧/新语义对拍、Player Cold Read、人工逐图验收或其它review发现新的未裁决blocker时，必须写入Todo，不能建立第二份decision/review ledger；
- 任一未勾选`[CUTOVER-BLOCKER:...]` → 项目`requirements`，即使所有Profile本身都pass；
- 用户/证据完成裁决后，更新真实业务owner并关闭对应Todo；如果用户明确接受残余不确定性，也以Todo关闭记录这项决定，不再维护独立状态枚举；
- 缺任一要求 Profile 报告 → `requirements`；
- 任一 Profile业务诊断`blocked` → 项目业务`status=blocked`；任一Profile业务诊断`requirements` → 项目业务`status=requirements`，这些字段继续如实反映Timing/XP/Review等动态未成熟输入；
- **迁移切换门禁与业务诊断状态分开**：只有要求集合完整、Todo中没有未关闭cutover blocker，且每个Profile Stage 14均为`cutover_status=pass + cutover_publishable=true`，才允许`cutover_ready=true`。合法动态`requirements`可以令普通`status/publishable`保持未证明，但只要不属于cutover硬错误，就不得被误当成架构替代 blocker；`blocked`是否同时阻塞cutover由Profile Final Audit的cutover分类负责，Project层不重新解释。

不得因为一个 pilot Profile 通过而推断“全项目已迁完”。

## 6. 输出身份

Stage 14 结果是可删除重建的 workflow audit，不是业务真源。

- `profile_final_audit`：单 Profile 最终门禁与冷读诊断；
- `project_final_audit`：完整 Profile 集合的切换门禁。

两者都只能触发“可以发布 / 需要补输入 / 需要回对应 owner 处理”的流程，不直接写 Task Card/Profile/Program。

## 7. 正式Final Audit操作

- 当前全部正式Profile的项目级cutover机械审计：`python3 scripts/audit_generated_cutover.py`。该脚本只审计，不重算业务owner、不写正式页面。
- Review Trigger属于Selection owner；Final Audit只消费已经生成的review结果，不维护第二套Review操作入口。

## 8. 失败恢复

- 上游`requirements/blocked`：回真正owner处理，再按`route-profile-and-lifecycle.md`的跨owner传播原则刷新明确下游；完整诊断需要时另行显式运行。
- fingerprint mismatch：禁止手修Generated Product；定位真实变化/串版本owner，按同一传播原则刷新。fingerprint本身不决定执行范围。
- 现役链命中已退出当前流程的历史consumer：切断引用；仍有真实能力需求就迁入当前唯一owner/工具，否则归档旧consumer，不保留兼容入口。
- player-view可读性review：回Route Display / Task Presentation / Profile stepGroups对应owner人工判断；Final Audit不自动改路线。
- 项目Profile集合不完整：补齐缺失Profile的完整报告，不用已有Profile结果代替。
