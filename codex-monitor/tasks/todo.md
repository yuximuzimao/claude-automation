# Status Island 待办

## 当前状态

- 当前稳定版本已覆盖：Codex/Claude Code 本地 JSONL 读取、滚动 30 天聚合、5 小时/周限额、项目 Top 10、Tk 浮窗、项目弹层、`.app` wrapper、LaunchAgent 和后台刷新。
- 2026-07-10 完成前景视觉修正、`order-review` 长会话归因修复和冷启动 30 天口径统一；阶段记录见 `docs/archive/2026-07-10-ui-attribution-and-window-consistency.md`。
- 当前 UI 继续使用 Tkinter 前景 + 独立 AppKit 磨砂 backing window。用户已确认现有视觉版本明显改善，本阶段不再继续微调材质。
- 2026-07-22 完成 Codex 按轮次归属、真实工作树唯一映射、子代理父项目继承和 neat 单项目收尾纠正；从主目录启动不再要求一个窗口固定一个项目。
- 2026-07-22 继续完成新版嵌套 `exec` 路径、项目自声明历史路径和 Claude 单项目确认区间回填；`voice-retrieval` 已显示为“语音取回”，旧 `phone-voice-paste` 用量随项目迁移。
- 最新验证：`python3.13 -m unittest discover -s tests -v` 114/114 通过；`python3.13 -m compileall app tests main.py`、`git diff --check` 和真实 `--smoke-aggregate` 通过；真实“其他”由本轮优化前约 16.4% 降至约 11.7%。
- 2026-11-04：项目确认在保留现有用量统计和限额倒计时的基础上扩展为桌面状态岛；初始方向与开源研究见 `../../docs/archive/2026-11-04-agent-autoloop-status-island/README.md`。
- 2026-11-06：已完成并确认第 1 阶段“适配层”和第 2 阶段“统一桌面调度运行模型”的架构讨论；尚未安装 Autoloop、修改代码或改变生产运行方式。原阶段结论见 `../../docs/archive/2026-11-06-autoloop-adapter-runtime-design/README.md`。
- 2026-11-09：已确认 Status Island 双设备部署方向和售后人工 / 自动操作边界。黑苹果保留用量统计、主端状态岛和人工 Chrome；Mac mini 运行售后业务服务、自动化 Chrome 和独立状态岛。两台设备各有本地队列，只协调真实冲突资源。尚未部署、配置网络或修改代码；详细结论见 `../../docs/archive/2026-11-09-status-island-dual-device-design/README.md`。

## 未处理问题

- [ ] **P1：第 3 阶段——任务入口与触发源映射（进行中）**
  - 当前进度：售后入口第一轮只读盘点及双设备职责边界已确认；2026-11-11 已确认黑苹果登录 / 重新登录 / 完整 Session 保存、最小认证信息同步到 Mac mini、两端账号数据归属及登录资源锁正常释放条件；本阶段尚未完成。
  - 下一项讨论：Mac mini 统一售后网页如何调用黑苹果本地浏览器入口 / 登录桥接服务，明确启动、确认、取消指令的传递与黑苹果离线反馈。
  - 剩余事项：跨设备任务请求的接收确认、幂等和断网恢复；限时许可与售后定时任务撞时的处理；售后剩余入口映射。
  - 售后入口确认完成后，再按既定顺序逐个讨论其他项目；本轮不提前展开农场、群聊的具体接入方案。
  - 本阶段只做入口映射与讨论，不安装 Autoloop、不修改生产入口。
  - 第 3 阶段完成后，再讨论停止 / 失联 / 恢复 / 崩溃安全；随后确定项目状态反馈协议和逐项目验收；最后进入 Status Island 产品形态与 UI 技术选型。
  - 双设备设计与详细恢复点见 `../../docs/archive/2026-11-09-status-island-dual-device-design/README.md`；此前两阶段结论见 `../../docs/archive/2026-11-06-autoloop-adapter-runtime-design/README.md`。

- [ ] **P1：统计准确性继续观察**
  - 已修复共享目录误投票、整段 session 单项目误归属、无效任务名抢占、工作树临时名、子代理不继承父项目和 neat 收尾无法回填未知用量。
  - 已补充嵌套本地工具参数、项目自声明旧路径、Claude 单项目确认区间回填；继续观察真正的跨项目/纯讨论会话、第三方 CodexPro/Skills 工具维护和 Claude Code 工作区根会话。无法形成唯一证据时仍归入“其他”，不回退为中心化硬编码或名称前缀猜测。

- [ ] **P2：日志规模增长后的性能与增量索引**
  - 触发条件：近 30 天重算明显变慢、LaunchAgent 空闲 CPU 异常、手动刷新卡顿，或 smoke aggregate 耗时不可接受。
  - 处理方向：设计增量索引/缓存，避免每次刷新重复解析已处理 JSONL；继续保持 UI 主线程不做 JSONL 读取或全树扫描。

## 后续可能优化

- **UI 技术选型（Status Island 设计子项）**
  - 下一阶段在产品交互设计后，对比继续扩展 Tkinter + AppKit 与 `NSPanel + SwiftUI/AppKit`；不预设重写。
  - 保留现有 Python reader / 聚合 / 归因 / 限额逻辑。若决定迁移，先做原型并满足 `docs/FUTURE.md` 中的成本与验收边界。

- **HTTP quota（暂缓）**
  - 当前继续使用本地 `payload.rate_limits`，不读取 `.codex/auth.json`，不请求内部 quota 接口。
