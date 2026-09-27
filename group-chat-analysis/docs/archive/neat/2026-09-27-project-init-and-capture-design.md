# 2026-09-27 — 项目初始化与采集方案阶段归档

## 阶段范围

本归档记录「群聊分析」从需求探索、QQ 只读采集可行性实验，到正式项目骨架与长期架构定型的阶段。

本阶段只解决“怎么安全、稳定地拿到文字，并让后续 GPT 有固定入口”。没有开始正式全量抓取，也没有建立每日自动化。

## 已完成

### 1. 安全路径收敛

- 官方 QQ 导出只能得到 BAK，无法直接作为当前机器可分析的数据入口。
- 放弃把非官方 QQ 协议、插件、数据库解密、进程注入、Hook、签名修改等路线作为正式方案。
- 正式方向收敛到官方 QQ UI + macOS 系统能力：安全窗口控制、像素捕获、Apple Vision 本地 OCR。

长期安全边界以 `../../rules/privacy-and-safety.md` 为唯一现役规则。

### 2. 本机只读采集实验

已在用户当前 macOS/黑苹果环境实际验证：

- QQ 可以被系统激活和定位。
- macOS Accessibility 树对 QQ 聊天正文暴露不足，不能作为正文主读取通道。
- 屏幕像素捕获能取得 QQ 画面，QQ 未阻止当前环境下的屏幕捕获。
- Apple Vision 本地 OCR 可以识别群名、昵称、时间和聊天正文。
- Page Up 受焦点影响，不适合作为正式翻页方式。
- 把鼠标移到聊天正文安全区域后仅发送系统滚轮事件，可以稳定向历史消息滚动。
- 相邻滚动页面存在可用重叠，可支持后续连续消息序列去重。
- 实验截图在验证后已删除，没有把真实群聊截图纳入项目或 Git。

正式采集规则以 `../../rules/capture.md` 为准。

### 3. Jev 思路吸收

调研 `jev-chat/jev-chat-jarvis` 及其相关实现后，只吸收数据采集层的设计思想：

- 采集层可替换；
- OCR 前先做图像变化检测；
- 尽量让内存图像直接进入 Vision，减少临时落盘；
- OCR 结果保留 bbox / confidence，用于后续消息重建。

没有引入其实时浮窗、自动回复、输入框回填、Android 伪装 Accessibility 等功能，也没有安装或运行 Jev 本体。

### 4. 项目正式建制

创建独立项目 `group-chat-analysis/`，中文名「群聊分析」，并注册工作区路由。

架构分为：

`Capture → Normalize → Store → Build Inbox → Analyze → Promote`

其中：

- 群聊真实原文、昵称、OCR结果、采集状态和分析报告统一属于 `runtime/` 私密运行数据，不进 Git。
- 规范化消息长期本地真值规划为 `runtime/messages/messages.jsonl`。
- GPT / CodexPro 的唯一默认日常分析入口规划为 `runtime/inbox/current.md`。
- v1 只保证文字信息；图片、语音、文件、表情暂不做语义提取。
- 群内说法只能成为线索，不能自动写入魔兽或其它项目的正式规则。

永久规则分别由 `../../rules/`、`../../ARCHITECTURE.md` 和 `../../../schemas/message-record.schema.json` 负责，本归档不作为执行入口。

### 5. 初始化验证

项目初始化阶段已验证：

- 中文项目别名可以路由到 `group-chat-analysis/`。
- 从空上下文可按 `SKILL → CLAUDE/todo/INDEX → CURRENT → 按需 rules` 恢复项目，不依赖聊天记忆。
- `runtime/` 会被 Git 忽略，项目文档不会被误忽略。
- `schemas/message-record.schema.json` 通过 JSON 语法校验。

## NEAT 收尾

2026-09-27 收尾时重新审查了全部活跃 Markdown 和 archive 索引，并做了以下职责修正：

- README / INDEX / src README / config README 移除阶段性“当前状态”描述，当前进度只由 `../../CURRENT.md` 负责。
- ARCHITECTURE / capture rule 移除会随环境过期的“当前已验证”措辞，实时可用性回到 CURRENT / 本机验证。
- Todo 顶部新增唯一“下一步”入口，并从阶段列表移除重复的全屏实验项。
- 阶段 0 状态更新为已完成。

## 下一窗口

只从 `../../../tasks/todo.md` 顶部的 **阶段 1-1：全屏窗口实验** 开始：

1. 用户把 QQ 切换成全屏。
2. 重新定位真实 QQ 渲染窗口。
3. 比较窗口级捕获与屏幕捕获 + 窗口几何裁剪。
4. 只定型捕获路径，不提前开始正式消息抓取。

完成实验后再更新 `../../CURRENT.md` 和 Todo。
