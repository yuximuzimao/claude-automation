# ChatGPT 通过 CodexPro 操作商品匹配的运行手册

本文只描述 **ChatGPT 对话模型通过 CodexPro 连接本地工作区** 时的交互层限制和规避流程，不替代商品匹配业务规则。

业务流程仍以 `docs/INDEX.md` 和 `docs/matching-stability.md` 为准；本地 Codex 直接在终端执行时，不需要套用本文中专属于 ChatGPT/CodexPro 的图片桥接和前台调用限制。

## 1. 开始前先确认执行模式

每次任务开始先明确由谁负责哪一段：

| 工作 | 推荐执行者 |
|---|---|
| 阅读规则、审计方案、与用户确认识图和写入范围 | ChatGPT |
| AI 视觉识图 | 当前对话中具备视觉能力的模型 |
| 大批量、长时间浏览器写操作 | 本地 Codex / 本地终端 |
| 小范围只读探针、文件修改、短命令验证 | ChatGPT + CodexPro |
| 匹配后的结构化自动核对 | 任一执行端，结果必须落到同一份报告 |

不要默认 ChatGPT + CodexPro 与本地 Codex 拥有相同的文件、图片和进程交互能力。

## 2. 本地图片不能直接进入 ChatGPT 视觉通道

### 已验证事实

- `codexpro.read` 适合读取文本文件，不会把本地 JPG/PNG/WebP 的像素交给 ChatGPT 视觉模型。
- CodexPro 命令输出主要是文本；把整张图片转成 base64 再分块返回，体积大、容易截断，也不会自动变成可供视觉理解的图片附件。
- 本地路径存在不代表当前 ChatGPT 对话可以直接看到该图片。
- OCR 或本地视觉模型只能作为用户明确允许的辅助，不能在用户要求“由当前模型亲自识图”时替代视觉判断。

### 标准图片桥接流程

1. 首次 `check` 完成后，保留原图和 `platformCode` 映射。
2. 生成联系表，建议每张 2×4：
   - 每格必须显示 `platformCode | productCode`；
   - 保留 SKU 文案；
   - 同时生成 `manifest.json`，记录 sheet、格位和原图路径。
3. 图片较多时先上传联系表；只有模糊项再补原图，不要一开始上传几十张散图。
4. 让用户明确授权“把图片附加到当前 ChatGPT 输入框但不发送”。
5. 重新枚举 Chrome target，精确确认当前会话 URL/标题，不能复用旧 targetId。
6. 找当前页面的文件输入框，例如 `#upload-photos` 或 `input[type=file]`，通过 CDP 附加文件。
7. 只读核对附件文件名和数量；**不得点击发送、不得模拟 Enter**。
8. 用户手动发送后，由当前 ChatGPT 视觉模型逐格完成 AI 识图，并按 manifest 写回 `recognition`。
9. 联系表无法确认的 SKU 单独补原图，再判断；禁止凭缩略图猜测。
10. 生成 `preview-match` 时展示“最终匹配明细”：AI 识图商品与自动注入配件放在同一张表中，配件只换字体颜色；用户确认覆盖两者的商品名称和数量。

### 本轮可复用的临时工具

本次曾在 `_sandbox/` 中使用：

- `make-contact-sheets.py`
- `make-master-sheet.py`
- `inspect-chatgpt-upload.js`
- `upload-contact-sheets-to-chatgpt.js`
- `verify-chatgpt-attachments.js`

这些脚本是实战辅助，不是稳定业务入口。使用前必须重新检查 ChatGPT DOM 和 targetId，不能假设页面结构永久不变。

## 3. CodexPro 前台命令有时间和输出边界

### 时间边界

CodexPro 的单次 `bash` 调用是前台、有限时长执行。本轮工具配置的上限为 180 秒；未来必须以当时的工具 schema / server config 为准，不能把 180 秒视为永久常量。大批量 ERP 写入通常仍可能超过单次调用时长。

因此：

- 50 个 SKU 之类的长任务优先交给本地 Codex/终端持续执行；
- ChatGPT + CodexPro 只适合短批次，且脚本必须具备可靠的断点续跑；
- 不要承诺后台继续运行；工具调用结束或超时后，进程可能已经被终止。

### 超时不等于业务操作完全失败

命令被 `SIGTERM` 或工具超时终止时，可能已经：

- 输出了完整或部分读取结果；
- 完成了某些页面状态变化；
- 写入了部分 SKU；
- 卡在 ERP 写流程中间状态。

重新执行前必须检查：

1. stdout/stderr 已输出到哪里；
2. `auto-match-log.json` 的 done/failed/scope；
3. 目标 SKU 当前是否已有 `erpCode`；
4. 是否已经出现“复制为套件”；
5. 是否存在残留弹窗或勾选状态。

禁止把“CodexPro 返回 timeout”直接解释为“什么都没发生”，也禁止不检查状态就从头重跑。

### 输出边界

大型 JSON、完整 DOM、base64 和全量报告容易超过工具返回上限。应采用：

- 先统计、再定向读取；
- 按 platformCode 或货号过滤；
- 大文件分行读取；
- DOM 只返回目标行、按钮、可见弹窗和关键 Vue 状态。

### 工具使用边界

ChatGPT 侧应优先使用 CodexPro 的结构化工具，而不是把本地 Codex 的终端习惯原样搬过来：

- 开始时打开/确认 workspace，并持续复用同一个 `workspace_id`；
- 文件内容用 `read`，定位用 `search`，精确修改用 `edit`/`write`，改动审查用 `show_changes`；
- `bash` 用于受控的测试、脚本和短探针，不用 shell `cat`/重定向代替文件工具，也不把交互式终端当作稳定后台会话；
- 工具返回被截断时缩小范围继续读取，不根据半段输出补猜其余内容；
- CodexPro 工具能力和允许的命令可能由当前服务器配置决定，调用前以本轮实际 schema 为准。

## 4. 浏览器 target 和页面状态不是固定资源

- Chrome targetId 会因关闭、重开、刷新或代理映射而变化。
- 每次关键动作前重新枚举 target，按 URL 精确确认 ERP、鲸灵和当前 ChatGPT 会话。
- `match` 和后置 `check --reuse-active --skip-download` 只依赖 ERP；若外层 CLI 因鲸灵 tab 缺失而阻塞，应修正依赖边界，不要临时打开错误鲸灵页面。
- 诊断动作也可能改变页面：打开“换”弹窗、输入搜索条件、翻页都会污染后续自动化状态。诊断结束必须关闭弹窗、清筛选或强制走 `navigateErp()` 重新建立干净状态。
- 记录时要区分“业务脚本自动点击”和“ChatGPT 为诊断主动打开”。本轮“换对应商品”是诊断操作，不是匹配脚本误点。

## 5. 长批量任务的推荐交接方式

当 ChatGPT 已完成识图并得到用户确认后，交给本地 Codex 的 handoff 至少包含：

- 店铺和品牌；
- 当前活动 SKU 总数、已匹配数、待匹配数；
- 已确认的 `sku-records.json` 不得重做识图；
- 是否已经下载平台商品；
- 是否允许写 ERP；
- stop-on-error 要求；
- 中断恢复规则；
- 最终执行命令；
- 完成门禁。

示例完成门禁：

```text
recognitionDone = SKU总数
comparisonMatch = SKU总数
comparisonMismatch = 0
comparisonPending = 0
pendingVisualReview = 0
未匹配 SKU = 0
```

本地 Codex 完成后，ChatGPT 只需审计结构化报告和异常项；自动核对全部通过时，不再要求用户人工重复检查 ERP 组合。

## 6. 禁止事项

- 禁止反复尝试用 base64 把本地图片“塞进”CodexPro 文本输出。
- 禁止在未授权时把文件附加到用户当前 ChatGPT 输入框。
- 禁止自动点击 ChatGPT 的发送按钮。
- 禁止把 OCR、本地 YOLO 或其他模型结果冒充当前对话模型的 AI 识图结论。
- 禁止用一个 180 秒前台调用承载整批长时间 ERP 写入，然后假设会持续运行。
- 禁止在 CodexPro 超时后直接重跑写操作而不检查 ERP 中间状态。
- 禁止复用过期 targetId。
- 禁止让诊断用弹窗、搜索条件或页码残留进入正式写流程。

## 7. ChatGPT + CodexPro 预检清单

在开始下一轮商品匹配前确认：

- [ ] 已读 `SKILL.md`、`docs/INDEX.md`、`docs/matching-stability.md` 和本文；
- [ ] 已决定长批量由本地 Codex执行，还是由具备断点续跑的短批 CodexPro 调用执行；
- [ ] 如需由当前对话模型完成 AI 识图，已提前规划联系表和 manifest，而不是任务中途再尝试图片传输；
- [ ] 已明确用户是否允许将图片附加到当前 ChatGPT 输入框；
- [ ] 当前 ERP / 鲸灵 / ChatGPT target 均已在关键动作前重新枚举并按 URL/标题核对；
- [ ] 识图结果、品牌和活动范围已落到共享文件，可由本地 Codex直接继承；
- [ ] 后置核查使用结构化自动比较，只有自动核对异常才进入人工复核。

## 8. 实战来源

本手册来源于 `docs/archive/2026-07-25-lanze-match/chatgpt-codexpro-session.md`。历史记录描述当时发生了什么；本文描述下次应怎么做。
