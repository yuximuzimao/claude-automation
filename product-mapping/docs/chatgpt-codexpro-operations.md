# ChatGPT + CodexPro 商品匹配运行契约

本文是 **ChatGPT 对话模型通过 CodexPro 操作本地商品匹配项目时的唯一执行环境规则**。

它只回答“命令由谁启动、在哪里持续运行、什么时候重新介入、图片怎样进入当前对话”。业务流程、比较规则和完成门禁仍由 `docs/INDEX.md` 负责；ERP 中断恢复由 `docs/matching-stability.md` 负责。其它文档只能指向本文，不得再维护另一套 CodexPro/Terminal 执行策略。

## 1. 正式命令固定走本机 Terminal

不要再判断“这次 SKU 少不少年”“预计会不会超过 CodexPro 时限”。只按命令类型路由。

### 必须由本机 Terminal 持续运行

ChatGPT + CodexPro 模式下，以下正式商品匹配命令**禁止**用 CodexPro 前台 `bash` 承载业务进程：

- 首次 `node cli.js check --shop <店铺> --brand <品牌>`；
- 匹配前 / 匹配后的 `node cli.js check --shop <店铺> --reuse-active --skip-download`；
- `node cli.js match --shop <店铺>`；
- `node cli.js match-one ...`；
- 正式流程中的 `download-products`、`mark-suite`。

CodexPro 只允许执行一个很短的“启动动作”，把实际 Node 命令交给用户本机 Terminal。当前 macOS 工作区的固定方式是通过短 `osascript` 调用让 Terminal 执行 `cd /Users/chat/claude/product-mapping && <实际 Node 命令>`；CodexPro 只负责发起这一次 Terminal 命令，不用 `nohup`、后台 shell 或持续会话承载业务进程。Terminal 中的 Node 进程随后独立运行，不受 CodexPro 单次前台调用时限影响。

这是一条**命令类别规则**，不是“长任务建议”。即使只有少量 SKU，也不要把正式 `check/match` 改回 CodexPro 前台执行。

### 可以直接使用 CodexPro 的工作

- 读取、搜索、编辑项目文件；
- `node --check`、无业务运行态副作用的快速测试；
- `targets`、短只读探针和定向诊断；
- `preview-match`、`verify-table` 等短时间本地生成；
- 已结束任务的一次终态报告审计。

## 2. 启动后的交互方式

正式命令启动到本机 Terminal 后：

1. ChatGPT 只确认“命令已经在本机 Terminal 启动”，不能把启动成功说成业务完成。
2. 正常运行期间不轮询日志、DOM、`targets`、`auto-match-log.json` 或运行时 JSON；详细自治边界只看 `docs/INDEX.md §1`。
3. 用户自己观察 Terminal。只有用户明确说“完成了 / 停了 / 卡住了 / 中断了 / 看下状态”时，ChatGPT 才重新介入。
4. 重新介入时先读一次当前终态或故障状态；不得因为之前的进程已经结束就从头重跑。
5. 若是中断或异常，按 `docs/matching-stability.md §4` 从 ERP 当前可观察状态恢复。
6. 最终 `check --reuse-active --skip-download` 通过全部完成门禁后，CLI 会自动恢复售后系统；未通过或异常时售后保持停止。

正式流程开始前，用户需要先手动停止售后系统。CLI 会验证暂停状态；没有停止时拒绝进入正式商品匹配。

## 3. 为什么不再使用“预计时长”判断

CodexPro 的 `bash` 是前台调用，时限和进程持有能力由当前工具环境决定。真实 `check/match` 耗时受 ERP 页面、SKU 数量、网络和保存等待影响，事前无法可靠预测。

因此本项目不再保留：

- “50 个 SKU 才算长任务”；
- “少量 SKU 可以先试 CodexPro”；
- “快超时了再转本机”；
- “超时后再决定要不要换执行端”。

这些判断都会重新引入同一个错误入口。

## 4. 本地图片进入当前 ChatGPT 视觉通道

CodexPro 的文本读取不能把本地 JPG/PNG/WebP 像素直接交给当前 ChatGPT 视觉模型。用户要求由当前对话模型识图时，使用以下桥接：

1. 首次 check 完成后保留 `productCode + platformCode` 与原图映射。
2. 生成联系表；每格显示 `platformCode | productCode` 和 SKU 文案，同时生成 manifest。
3. 优先上传联系表；模糊项再补原图。
4. 只有用户明确允许后，才可把文件附加到当前 ChatGPT 输入框。
5. 附件操作前重新枚举 ChatGPT target，按当前 URL/标题确认，禁止复用旧 targetId。
6. 只附加并核对文件名/数量；不得点击发送或模拟 Enter。
7. 用户手动发送后，由当前 ChatGPT 视觉模型识图并写回 recognition。
8. OCR、本地 YOLO 或其它模型只能作为用户明确允许的辅助，不能冒充当前对话模型的识图结论。

`_sandbox/` 中的联系表和上传辅助脚本属于临时工具，不是稳定业务入口；使用前必须重新核对当前 ChatGPT DOM。

## 5. CodexPro 工具边界

- 打开工作区后持续复用同一个 `workspace_id`。
- 文件内容用 `read`，定位用 `search`，修改用 `edit/write`，审查改动用 `show_changes`。
- CodexPro `bash` 只用于短测试、短探针和“启动本机 Terminal”这一瞬时动作。
- 大型 JSON / DOM / base64 不直接整块返回；先统计，再定向读取。
- 浏览器 target 会变化；关键诊断前重新枚举并按 URL/标题核对。
- 诊断动作可能污染页面状态；正式续跑前必须清理诊断残留或重新建立干净页面状态。

## 6. 禁止事项

- 禁止用 CodexPro 前台 `bash` 直接跑正式 `check/match`，即使看起来这次可能很快。
- 禁止正常运行期间为了“看看进度”持续轮询。
- 禁止 CodexPro timeout 后不检查 ERP 中间状态就重跑写操作。
- 禁止把本地图片转 base64 文本冒充视觉输入。
- 禁止未授权附加文件、自动发送 ChatGPT 消息或复用过期 targetId。
- 禁止让诊断弹窗、筛选条件或页码残留进入正式写流程。

## 7. 启动前最小检查

ChatGPT + CodexPro 开始一次正式商品匹配时，只确认：

- 已读本文，正式 check/match 将固定交给本机 Terminal；
- 用户已手动停止售后系统；
- 首次 check 所需店铺 / 品牌 / JL 当前页面已明确；
- 如需当前 ChatGPT 识图，已提前规划图片桥接；
- 脚本正常运行后不监工，等待用户主动通知完成或异常。

历史实战证据见 `docs/archive/2026-09-22-hee-922-maoye-handoff/`。历史只说明规则来源，不再作为执行入口。
