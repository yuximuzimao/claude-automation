# 群聊分析交接

## 当前完成

阶段 2 已收口为单一正式链：

- `src/app/run_capture.py`：唯一正式运行入口，兼容固定页数诊断、`--full` 首次全量与 `--incremental` 每日增量，独占 batch state 推进与恢复判断。
- `src/app/full_capture.py`：双群安全串行基础编排，首次全量使用双 no-change 边界与每轮安全页预算。
- `src/app/incremental_capture.py`：复用同一状态机；新 batch 每群强制重开历史窗口刷新快照，命中上一 completed `start_anchor` 后停止；分片恢复已有 durable 页时不重开。
- `src/app/capture-step.swift`：内部单步执行器，只负责 current/scroll 一次捕获；无变化通过专用退出码交回 Python 状态机。
- `src/capture/`：AX/SCK/Vision、正文区、安全滚轮、MAD、`dhash512` 视口连续性门禁、raw 原子写入。
- `src/normalize/`：bbox 重建、fragment 保留、媒体 OCR unknown、相邻页保守去重与顺序转换。
- `src/store/`：batch-state v4；保留 `pending_capture` / 每群 `capture_complete`，新增 `batch_kind`、incremental `start_anchor`、v2/v3 确定性迁移、canonical messages 与 finalize 崩溃恢复。
- `src/inbox/`：completed/analyzed → current.md。

旧批量 Swift CLI 已删除，避免第二入口；旧 capture worktree 已不再是运行依赖。

阶段 3 的安全切群也已实机往返验证：`src/capture/ConversationSwitcher.swift` + `src/app/open-history.swift` 只在“左侧会话 OCR 唯一命中 → 选中后头部复核 → tooltip 精确为 `聊天记录` → 历史窗口标题精确匹配”全部成立时执行。两个目标历史窗口标题已确认，真实成员数只作为当次额外证据，不进入长期身份配置。

两群首次全量编排已经完成并通过真实长跑：`first-full-20261008` 最终得到第一群 891 页 / 5700 条 canonical、第二群 256 页 / 1593 条 canonical，合计 1147 页 / 7293 条。全 batch 共用递增 page_index；每群只有连续两次独立 `NO_CHANGE` 才 `capture_complete`；默认每轮最多新增 20 页，并且只在 durable raw + `pending_capture=null` 的安全点返回 incomplete。已有 durable 页的未完成群恢复时不主动重开历史窗口；状态冲突、群集合变化、`pending scroll + raw 缺失` 都在任何 QQ UI 动作前硬停。

## 当前关键契约

- 错误成本：**漏真实消息 > 多保留重复消息**。
- 状态推进顺序固定为 **pending intent → Swift 单步 → raw durable → record_page**。
- `pending current + raw 缺失` 可安全重试；`pending scroll + raw 缺失` 必须硬停，禁止猜当前位置再次滚动。
- 没有 matching pending，`record_page()` 不能推进；没有 pending 却出现 next raw 也硬停。
- 滚动前必须用上一份 durable raw 的 `dhash512` 验证当前视口。阈值 `<=20`；该指纹只验证视口连续性，不参与昵称/消息身份去重。
- MAD 只容忍 `<=3px` SCK 尺寸漂移并比较共同尺寸；更大漂移停止。
- QQ 单页视觉上→下是新→旧；Normalize 最终输出旧→新。
- 相似昵称不归并；一侧 sender 缺失不做破坏性去重；证据不足宁可重复。
- `messages.jsonl` 先 durable，之后才能 completed；current.md 是可重建派生物。
- completed 前要求所有群 `capture_complete=true`；达到每轮页预算只返回 incomplete，不等于历史完成。

## 验证

`python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **96/96 通过**。

真实验证包括：
- 唯一 runner 实跑 3 页并 completed；
- 同一未滚动视口 6 次 dHash 校准：`18,0,0,0,0`；三个不同页距离 `46/49/31`，因此阈值收紧为 20；
- `pending + raw 已存在` 可不触发 capture 直接恢复；
- `pending scroll + raw 缺失` 保留状态并停止，不再次滚动；
- completed 后删除 current.md 可纯本地重建，不触碰 QQ；
- MAD 回弹、SCK 小尺寸漂移、bbox/assembly、message store/finalize 均有确定性回归；
- 两个目标群正式 `open-history` 往返成功，系统窗口标题分别精确匹配目标；
- 正文消息包含“表情”时不再误截工具栏，真实页 content_region 高度由错误约 `0.192` 恢复到约 `0.852`；
- 两群同 batch、双 NO_CHANGE 边界、20 页安全分片、已有 durable 页恢复不重开历史窗口、状态冲突 UI 前硬停均有确定性回归；
- v2/v3 batch-state 可确定性迁移到 v4 `capture`，不猜成 incremental；真实 v3 completed state 副本迁移后，两群尾部 anchor 可精确复制到新 incremental `start_anchor`；
- 首次全量真实 1147/1147 页逐页 reconstruct `bad=0`；全局 page 0–1146 连续无缺页/重复；canonical 共 7293 条，两个群 sequence 各自连续，无未知 group、无重复 record_id；
- header-only 异常页保守降级为 fragment，不生成伪正文；低运动滚屏模糊区通过 OCR Jaccard 二次证据补判；
- incremental 确定性回归覆盖：双群新 batch 各重开一次历史窗口、分片恢复不重开、anchor 后裁剪、0/1 新消息、completed 本地重建、历史边界先于 anchor 硬停；真实 baseline 两组 anchor 均只在 canonical 尾部命中并裁剪为 0；
- 第一次真实增量 `incremental-20261009-001` 已 completed：95 个 raw pages，最终新增 611 条 canonical（第一群 609 / 第二群 2）；旧 anchor 均未重复入库，sequence 连续、record_id 无重复、新 completed anchor 正确前滚；
- 真实增量继续校准了部分滚动页和消息头高度：OCR Jaccard 模糊区上限保守放宽到 0.85，header 高度门槛调整为 `1.05×body`；全套 **96/96** 通过；
- 第一版报告已按当前魔兽项目重排为 `runtime/reports/2026-10-09-incremental-001-v2.md`，同时生成简洁页面 `runtime/reports/2026-10-09-intel-v1.html`；首轮评审已完成：重点发现只放真实有效信息，“没有发现/不触发修改”只作状态总结；删除“全部信息”一级页；“当前项目”暂保留；黑话继续保留“解释 + 原文”但必须支持同词多语境/多含义；
- 首次全量 `first-full-20261008` 的 7293 条 canonical 只完成采集/审计，尚未做完整语义分析；历史覆盖策略尚未决定是否直接分析现有基线，或尽可能从“入群至今”重新补采。
- 本阶段已归档到 `docs/archive/neat/2026-10-09-first-full-incremental-analysis-page-review.md`。

## 下一步

按 `tasks/todo.md` 顶部进入阶段 4：重新设计分析页面 v2。先参考数字生命卡兹克的 AIHOT 热点总结页面，讨论价格/版本/热点/职业/任务/打金等有效信息如何更精细分层和倾向化排序；同时决定历史覆盖策略。方案未定前不要直接重跑大规模历史采集。
