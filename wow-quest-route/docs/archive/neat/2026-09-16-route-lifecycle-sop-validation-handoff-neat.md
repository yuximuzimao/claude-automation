# 2026-09-16 Route Lifecycle SOP 验证交接 NEAT

## 本轮范围

本轮从 Task Card 全量迁移收口继续推进到 Route Profile / Publisher 架构联动，随后按项目最终目标反查依赖关系，并建立 Route Lifecycle SOP 的 14-stage 可执行主干。阶段末发现一个关键流程偏差：在 Stage 3 Availability / Route Replay 尚未证明自身语义正确前，曾开始修改正式 Route Profile / Task Card 来减少 hard error。该做法会形成循环验证，因此本轮在此停止业务实现，转为 SOP 验证交接。

本文只保存阶段形成过程与恢复依据；当前执行顺序以 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` 和 `tasks/todo.md` 为准。

## 已确认完成或可复用的资产

- Task Card 机械迁移目标已经扩展并收口到 1082 张；精确 rewards 已验证，Questie Corrections 解析失败和 workbench task-id unresolved 均已清零，旧 review queue 已降为 0。
- 旧 fivebox 长备注和旧正式备注已先无损归属；`【需要单独修正优化】`备注专项继续延期到整条新 Publisher 链稳定以后。
- Candidate Publisher / Hellfire pilot、14 路线 candidate、Route UI 标签分层等已经形成迁移实验资产；它们证明过迁移/投影能力，但**不再视为新架构最终验收**。
- SOP 已做过正向与反向规则审计，过程中补出了此前隐藏的 Route Program、Economy owner、Character Profile、Dependency/Fingerprint 等上游概念/接口。
- `rebuild_route_profile.py` 已成为唯一总入口的实现骨架；Stage 1–3 已有不同程度的实现代码和契约测试，但本次收尾后统一降为“实现候选”，必须重新按 SOP §17.2逐层验收，不能沿用此前口头的“已完成”判断。
- Worktree 合回主干的门槛仍固定在 **Stage 4 真正完成后**；Stage 1–4 全部满足 SOP 完成定义以前继续留在 `feat/wow-architecture-migration`。

## 本轮关键纠偏

架构迁移期间，真实 Profile 的角色应先是**冻结验证 fixture**。正确顺序是：

1. 当前 stage 先闭合 owner、input/output contract、UNKNOWN/冲突语义和 freshness；
2. 先用通用契约测试证明 evaluator 的基础行为；
3. 再对真实 Profile 预先写出 expected outcome；
4. 真实样本差异必须先分类为：`实现缺陷 / 上游contract缺失 / 来源冲突 / 迁移保真问题 / 真实业务错误`；
5. 只有 stage 本身已经成立、并且独立证据证明是真实业务错误时，才重新进入普通 `TASK_FACT / PROFILE_*` 流程修正式真源；
6. 如果分类涉及用户路线取舍、与高优先级证据冲突，或 SOP / owner 语义本身存在疑问，**停止该分支并先问用户**。

禁止采用：`validator报错 → 修改正式路线直到变绿 → 用变绿证明validator正确`。

该失败模式已写入 `ERROR-BOOK.md` 错题028，并在 SOP §17 / §17.2 加入真实 Profile 冻结门禁。

## Stage 1–3 当前状态

### Stage 1 Dependency / Fingerprint

已有 `lib/route_dependencies.py`、task→profiles / profile→programs 反向索引和分区 fingerprint 基础。此前真实数据运行性能已优化，但下一会话仍需重新对照 §17.2 确认：输入集合、fingerprint 边界、消费者/stale 门禁是否完整，再决定是否正式标记完成。

### Stage 2 Profile / Route Program Contract

已有 Route Program schema/loader、Character Profile 机器配置、Profile/Program state contract 扩展。仍需从 Stage 3/4 真正需要的上游数据反查 contract 是否足够，不因已有代码直接判完成。

### Stage 3 Availability / Route Replay

已有 Availability / Replay 实现和契约测试，但**Stage 3 尚未完成**。本轮曾用真实 Profile hard error 驱动正式路线修改，因此下一会话必须先验证 Stage 3 evaluator 本身，而不是继续追求 hard error=0。

## Stage 3 期间留下的候选纠错

以下工作区修改暂时保留，不在本轮 NEAT 中回滚；除独立事实外，不把它们当成已批准的正式路线迁移结果：

- `storm-peaks-fivebox`
- `zuldrak-fivebox`
- `grizzly-fivebox`
- `sholazar-fivebox`
- `icecrown-fivebox`
- Task Card 13230 / 新增 13276 等相关修改

其中 `9498/9499《猎鹰岗哨》` 属于不同性质：用户当前兽人 DK 已实测可接，且本地数据库能证明 9498 是非血精灵部落分支、9499 是血精灵分支，因此这项可以作为独立 `TASK_FACT` 证据保留；它仍不能被用来证明 Stage 3 evaluator 整体正确。

## 下一会话唯一开发入口

先读：

- `docs/verified-routes/CURRENT.md`
- `tasks/todo.md`
- `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`

然后从**最早尚未满足 SOP §17.2完成定义的 stage**重新验收，严格按 Stage 1→14 顺序推进。每补一个 stage，都同时验证 SOP 本身是否仍正确；发现疑问先向用户确认，不自行修改正式路线、扩 schema 或放宽规则。

Candidate Publisher、Movement、Leatrix、Timing、XP、Economy等不得因“代码已经容易写”跳级。Leatrix importer 可以保留为独立 source importer，但只能到 Stage 7 正式接入；原始 zip 要等转换/绑定/Timing接入验收完成后再删除。

## 延后事项

- Publisher正式切换和旧写入口退役：等 SOP 对应 stages 真正 fresh 后再继续。
- 14张最终页面逐Step冷读：只读最终 fresh Publisher 输出，不读当前中间 candidate 冒充终局。
- `【需要单独修正优化】`备注内容专项：整条路线/Page转换系统稳定以后再做。
- 五开共享性 pending：继续随自然实跑验证，不为清账单独补跑。

## 版本控制状态

本轮仅做 NEAT / handoff 文档收口，不提交、不推送、不合并 worktree。Stage 4 真正完成前继续保留当前 worktree。