# Codex Monitor 待办

## 当前状态

- 当前稳定版本已覆盖：Codex/Claude Code 本地 JSONL 读取、滚动 30 天聚合、5 小时/周限额、项目 Top 10、Tk 浮窗、项目弹层、`.app` wrapper、LaunchAgent 和后台刷新。
- 2026-07-10 完成前景视觉修正、`order-review` 长会话归因修复和冷启动 30 天口径统一；阶段记录见 `docs/archive/2026-07-10-ui-attribution-and-window-consistency.md`。
- 当前 UI 继续使用 Tkinter 前景 + 独立 AppKit 磨砂 backing window。用户已确认现有视觉版本明显改善，本阶段不再继续微调材质。
- 最新验证：`python3.13 -m unittest discover -s tests -v` 97/97 通过；`python3.13 -m compileall app tests main.py` 和真实 `--smoke-aggregate` 通过。

## 未处理问题

- [ ] **P1：统计准确性继续观察**
  - 已修复共享目录误投票、长会话后段项目路径漏扫和新项目中文名元数据缺失。
  - 继续观察从工作区根目录启动的长规划会话；若再次异常，按完整结构化事件链路复核，不回退为中心化硬编码映射。

- [ ] **P2：日志规模增长后的性能与增量索引**
  - 触发条件：近 30 天重算明显变慢、LaunchAgent 空闲 CPU 异常、手动刷新卡顿，或 smoke aggregate 耗时不可接受。
  - 处理方向：设计增量索引/缓存，避免每次刷新重复解析已处理 JSONL；继续保持 UI 主线程不做 JSONL 读取或全树扫描。

## 后续可能优化

- **原生 macOS 材质 UI（暂不排期）**
  - 当前 Tkinter 前景与 AppKit 磨砂位于两条独立渲染链路，无法完全复现系统组件的 vibrancy、字体合成和动态材质。
  - 保留现有 Python reader/聚合层，未来优先评估 `NSPanel + SwiftUI/AppKit` 原生前端；只有需要真正桌面组件且接受系统限制时再评估 WidgetKit。
  - 详细边界、触发条件和验收标准见 `docs/FUTURE.md`。

- **HTTP quota（暂缓）**
  - 当前继续使用本地 `payload.rate_limits`，不读取 `.codex/auth.json`，不请求内部 quota 接口。
