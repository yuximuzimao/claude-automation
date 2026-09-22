# 群聊分析

项目中文名：群聊分析

## Session 启动

1. 先读 `SKILL.md`。
2. 读 `tasks/todo.md`。
3. 读 `docs/INDEX.md`。
4. 继续当前开发时读 `docs/CURRENT.md`。
5. 只按当前任务从 `docs/rules/README.md` 加载对应规则。
6. 跨模块设计/实现才读 `docs/ARCHITECTURE.md`。

## 稳定项目目标

把指定群聊中的文字消息，以尽可能低风险、可重复、可审计的方式采集到本地，并形成一个稳定的 GPT 分析入口。

采集、存储、分析三层必须解耦：未来即使 QQ UI、OCR实现或分析模型变化，也不能要求整体重构。

## 安全与隐私边界

- 官方 QQ 客户端是唯一消息来源。
- 禁止注入 QQ、进程 Attach、Hook、修改签名、协议逆向、数据库解密、密钥读取、NapCat/LiteLoader 等非必要路径。
- 自动化默认只允许：激活窗口、定位、滚动、截图/窗口捕获、OCR；禁止发送消息、编辑输入框、修改群设置。
- Apple Vision OCR 在本机完成。
- 截图默认内存处理；除非诊断明确需要，否则不落盘。
- `runtime/` 保存群聊原文、昵称、采集锚点、分析输入/输出等私密数据，永不提交 Git。
- GPT 分析意味着 `runtime/inbox/current.md` 中选定文字会提供给模型；捕获阶段本身不上传。
- v1 仅处理文字。图片/语音/文件等只允许记录占位类型，不做内容语义提取。
- 群消息只能作为线索/证据候选；不得自动覆盖其它项目的已验证事实。

## 规则文档（渐进式）

| 文档 | 加载时机 |
| --- | --- |
| `docs/rules/capture.md` | QQ定位、捕获、滚动、OCR |
| `docs/rules/storage.md` | 私密数据、文件生命周期、分析入口 |
| `docs/rules/normalization.md` | 消息重建、排序、去重 |
| `docs/rules/analysis.md` | GPT读取、筛选、输出及跨项目边界 |
| `docs/rules/privacy-and-safety.md` | 权限、安全、禁止路径、隐私 |

## 教训沉淀

- `tasks/lessons.md` 只放尚未归类的新发现。
- 稳定采集/存储/分析方法迁入对应 `docs/rules/`。
- 当前实现阶段和验证状态只进 `docs/CURRENT.md`。
- 一次性实验、被替代方案和阶段结论进 `docs/archive/`。
- 迁移完成后删除 lessons 中重复项。

## 相关项目

- `wow-quest-route/`：当前最主要的信息消费方之一，但群聊信息不得自动写入其规则/observations。
- 其它未来消费方必须通过“分析结果 → 用户确认/独立核验 → 目标项目”路径接入，不允许采集层跨项目写入。

## Git / 数据边界

版本化：代码、Schema、规则、测试、架构文档。

不版本化：`runtime/` 下的群聊原文、昵称、OCR结果、采集状态、分析包、分析结果、诊断截图。

## 目录说明

以 `docs/ARCHITECTURE.md` 和 `SKILL.md#PATHS` 为准，不在本文件复制更细目录树。
