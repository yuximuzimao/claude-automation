# 群聊分析架构

## 1. 设计目标

这个项目解决的不是“实时聊天助手”，而是：

> 以最低必要权限，从指定群聊完整取得文字消息，可靠保存，再交给 GPT 做离线分析。

架构必须优先保护三个长期性质：

1. **采集实现可替换**：QQ UI/窗口模型变化时，只改采集适配器。
2. **原文与分析解耦**：消息保存格式不能依赖某个 GPT 模型或 Prompt。
3. **运行时隐私与版本化知识分离**：群聊原文永不进入 Git；规则、Schema、代码可以版本化。

## 2. 分层

```text
官方 QQ
   ↓
[Capture]
窗口/聊天区定位 → 安全滚动 → 捕获像素 → 变化检测 → Apple Vision OCR
   ↓
[Normalize]
OCR block + bbox + confidence
→ 识别昵称/时间/正文
→ 重建消息
→ 相邻屏连续序列去重
→ 时间顺序
   ↓
[Store]
runtime/messages/        规范化消息库
runtime/state/           采集锚点/批次状态
   ↓
[Build Inbox]
生成 runtime/inbox/current.md
   ↓
[Analyze]
CodexPro 读取 current.md
→ GPT 筛选、归类、摘要
→ runtime/reports/
   ↓
[Promote]
只有经用户确认/独立核验的信息，才允许进入魔兽或其它项目
```

## 3. 模块边界

### capture

只负责“看到什么”。

输入：官方 QQ 当前 UI、目标群配置、上次采集状态。

输出：符合 `schemas/capture-page.schema.json` 的单页 raw record；页级保存 batch/group/page/window 元数据，blocks 保留 text / bbox / confidence。capture 只提供可验证的视觉/OCR事实，不承担发送者身份猜测。

不得：
- 判断哪些魔兽信息重要；
- 全局去重业务消息；
- 调用 GPT；
- 写其它项目。

### normalize

只负责“这些 OCR block 组成了哪些消息”。

输入：OCR blocks 与所属 page 的 batch/group/page 几何上下文。

输出：符合 `schemas/message-record.schema.json` 的消息记录。v1 不做相似昵称身份归并；证据不足时保留重复，不在 Normalize 层猜测发送者身份。

确定性优先；所有规则都必须可测试。活跃人员明细不在 normalize 层按发言数推断，交由 Analyze 阶段结合消息的信息价值、证据质量和后续关注价值判断。

### store

只负责“可靠保存与恢复”。

必须支持：
- 首次全量采集；
- 失败后从安全位置恢复；
- 后续增量采集；
- 批次级原子性或明确的 completed/incomplete 状态；
- 批次级严格递进的页恢复位置，以及每群的连续增量锚点；
- completed 前禁止生成 `current.md`，analyzed 不覆盖 completed 消息；
- 不因分析失败而丢采集结果。

状态契约由 `schemas/batch-state.schema.json` 定义，正式实现位于 `src/store/batch_state.py`，确定性转换测试位于 `tests/test_batch_state.py`；真实 QQ 端到端 dry-run 仍是进入首次全量前的门禁。

### inbox builder

只负责把“本批待分析消息”生成稳定 Markdown 文档。

固定路径：`runtime/inbox/current.md`。

该文档是 GPT/CodexPro 的唯一默认分析输入；GPT 不需要知道截图、bbox、滚动等采集细节。

### analyze

只负责把完整聊天转成“第一次值得用户看一眼的信息”，并维护之后可检索的知识状态；不替用户做最终价值裁决。

分析采用“宽松召回 → Topic Card候选索引 → Silver规范化知识单元（跨日语义聚类、实体对齐、去重、字段化、证据挂接）→ 与已阅/资料库/项目已有事实比对 → 首次阅读队列/资料库/动态专题投影”的链路。Topic Card 不直接作为用户阅读单元。只出现一次的具体游戏事实也可以进入队列；封测或尚待版本核验不等于无效。讨论次数/参与人数只作为后台证据支持度，不因为可信度升级就重新占用户阅读队列。

默认重点召回：
- 魔兽时光服/无限服的具体机制、规则和玩法变化；
- 职业配置、数值阈值、装备限制与操作技巧；
- 任务机制、BUG、共享性、路线坑点；
- 副本/Boss的具体打法、替代方案和排雷；
- 专业、插件、防诈骗、经济与打金等可复用信息；
- 当前未使用、但以后可能影响行为认知的游戏特异事实。

展示前尽量补齐最小必要身份，例如任务地图/名称/ID/目标、Boss所属副本和顺序、职业专精/版本/具体阈值、装备正式名/ID/来源。需要额外网络研究才能补足的内容只标“可补全”，不阻塞本批其它信息。

同一讨论里的互补事实优先收进一个话题容器；跨批次完全相同的旧结论不再显示。新增机制、条件、数字、操作、例外、替代方案或真正纠错才重新进入队列。AI扩展只在多个事实组合后能产生具体、可验证、可能改变做法的新判断时出现；事实与推断始终分开。

用户终审只有“没用 / 存资料库”。两者都进入已阅去重；只有“存资料库”进入长期知识。当前无限服额外维护动态专题档案，把零散封测观察逐渐综合成练级发展、经济打金、专业资源、规则风险、职业玩法和服务器生态的当前认知。

### promote

不是自动流程。

从群聊分析写入 `wow-quest-route` 或其它项目，必须满足至少一个：
- 用户明确确认；
- 用户自己的实测；
- 单独联网/数据源核验后确认。

## 4. 运行时文件设计

### `runtime/messages/messages.jsonl`

普通 full / incremental 的本地规范化消息库，append-oriented。每条消息遵循 message-record schema；允许后续新增版本字段，但不得静默改变旧字段语义。

### `runtime/history-days/YYYY-MM-DD/`

单日历史补采使用独立 runtime root，每个自然日自带 `raw/`、`messages/`、`inbox/`、`state/`。这样旧历史不会被追加到日常增量消息库尾部；总历史分析后续从 completed 日包构建输入。

### `runtime/inbox/current.md`

“当前这一批全部待分析文字”的稳定入口。

建议内容：

```text
# 群聊分析输入

batch_id:
captured_at:
groups:
message_count:
range:

## 群 A
[时间] [成员标识] 正文
...

## 群 B
...
```

v1 默认保留群内显示昵称，因为判断连续讨论、多人共识需要发送者一致性；不主动保存 QQ 号等账号标识。

### `runtime/state/batch-state.json`

只存采集状态，不存规则：
- last_completed_batch
- 每群最后完成锚点
- 上次成功采集时间
- 当前 incomplete batch（如有）

## 5. 首次全量 vs 每日增量

### 首次全量

从当前最新位置逐屏向历史方向滚动，直到达到用户指定历史边界/可获取边界。

每页：
1. 捕获聊天区低成本图像指纹。
2. 未变化：等待/有限重试/判断到边界。
3. 变化：Vision OCR。
4. 重建消息。
5. 和相邻页做连续序列去重。
6. 持久化后再继续。

### 单日历史补采

由 `run_capture --history-date` 先用只读日期筛选把目标群定位到指定自然日，再复用同一个 full-capture 状态机向历史方向滚动到连续两次 `NO_CHANGE`。日期选择本身不是第二套采集流程；已有 durable 页的 incomplete batch 恢复时不重新选择日期。finalization 前额外校验已恢复的日期/绝对时间没有跨出目标日。

如果发生 `pending scroll + raw 缺失`，单日历史不猜测故障现场究竟移动了几屏，也不直接晋升当前屏。正式 runner 把当前屏作为 probe，向较新方向有限回退；只有连续两张 probe 唯一匹配连续两个 durable 页时才重新建立锚点，然后逐页向历史方向回放并核对直到最后 durable 页。确认回到已知安全视口后才撤销原 pending，再由正常状态机重新读取失败目标页；重锚定失败时原 state/canonical 保持不变并停止。

### 后续每日增量

从最新位置向历史方向滚动，直到可靠命中“上次完成锚点”。

只把锚点之后的新消息加入本批 inbox。

不得只靠“今天/昨天”视觉文本作为唯一停止条件。

## 6. 正文采集实现

当前唯一正式正文主路径是 **ScreenCaptureKit 精确 QQ 历史窗口捕获**：先验证唯一目标窗口，再对该窗口像素做变化检测与 Vision OCR。现役代码不维护第二套“全屏截图 + 几何裁剪”正文实现。

底层 Vision 请求只有一个 owner：`capture/VisionTextRecognizer.swift`，统一识别语言、候选抽取和方向 bbox 映射；正文采集、日期选择和会话切换只维护各自业务门禁，不再各复制一套 Vision 实现。所有正式 Swift target 的 source 依赖由 `app/swift_sources.py` 唯一定义，生产编译与测试共用，避免新增基础文件时出现部分入口漏依赖。

Accessibility 正文读取仅可作为辅助信息源，不作为正文主路径。若未来 macOS/QQ 变化导致当前窗口级捕获不可用，任何替代方案都必须先重新验证安全边界和完整性，再进入正式代码；不得把未验证 fallback 当成自动降级路径，更不得为了更直接的数据访问升级到进程注入/数据库解密。

## 7. OCR与图像

正式路径优先：

`CGImage/像素 → 图像变化检测 → Apple Vision → 内存释放`

不默认：

`截图PNG → 磁盘 → OCR`

只有诊断场景允许临时落盘，必须进入 `runtime/diagnostics/` 并受清理策略约束。

## 8. v1明确不做

- 实时浮窗。
- 自动回复。
- 输入框回填。
- AI实时判断是否回复。
- 图片内容理解。
- 语音转写。
- 文件解析。
- 表情语义分析。
- QQ数据库/协议/API逆向。
- 自动把群聊结论写入魔兽规则。

这些以后是否加入必须重新评估，不视为当前架构欠债。
