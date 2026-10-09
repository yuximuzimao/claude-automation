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

只负责“完整整理有意义的话题，再判断个人价值”。

分析采用先召回、后排序的两阶段：先从全部文字消息中宽松提取话题、事实线索、攻略、经验、趋势、机会与黑话，再做全局归组、价值分级和可信度标记。讨论次数/参与人数不作为核心价值分；只出现一次的短消息也可成为高价值待核验线索。

主要关注：
- 新服/版本/开放时间等时效信息；
- 魔兽时光服/无限服具体机制；
- DK/职业配置、五开技巧；
- 任务机制、BUG、共享性、路线坑点；
- 经济、金币、拍卖行、打金方式；
- 多人形成的明显共识或明显争议；
- 当前未使用、但以后可能产生收益或节省时间的攻略、经验和机会线索。

每条实质信息固定先显示来源事实与群聊原文，再显示明确标注的 AI 扩展分析；事实、经验、趋势推断和项目影响不得混写。纯黑话只进入持续词典，不重复生成普通话题卡。完整展示与重点排序同时存在：本期重点优先阅读，低优先级有效内容仍可从按机制分类的话题总览中找到。

### promote

不是自动流程。

从群聊分析写入 `wow-quest-route` 或其它项目，必须满足至少一个：
- 用户明确确认；
- 用户自己的实测；
- 单独联网/数据源核验后确认。

## 4. 运行时文件设计

### `runtime/messages/messages.jsonl`

本地规范化消息库，append-oriented。

每条消息遵循 message-record schema。允许后续新增版本字段，但不得静默改变旧字段语义。

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

### `runtime/state/state.json`

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

### 后续每日增量

从最新位置向历史方向滚动，直到可靠命中“上次完成锚点”。

只把锚点之后的新消息加入本批 inbox。

不得只靠“今天/昨天”视觉文本作为唯一停止条件。

## 6. 采集实现优先级

1. **窗口级捕获**：若全屏实验能稳定解析真实 QQ 渲染窗口，则优先。
2. **屏幕捕获 + AX窗口几何裁剪**：作为窗口级捕获不可用时的 fallback；可用性以实时环境验证为准。
3. Accessibility 正文读取仅可作为辅助信息源，不作为正文主路径。
4. 禁止为了更直接的数据访问升级到进程注入/数据库解密。

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
