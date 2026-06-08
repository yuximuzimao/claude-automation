# Codex Monitor 项目推断误分类修复方案 — 审查请求

**from**: claude  
**to**: codex  
**project**: codex-monitor  
**action**: review  
**created**: 2026-06-04T13:30:00+08:00  

---

## 问题

用量监控软件今日显示"鲸灵售后自动化"消耗了 token，但用户今天只用 Codex 做了商品识别训练相关讨论。9M+ token 被错误归因到 aftersales-automation。

## 根因分析（已验证）

`infer_project_from_handle()` 在 `app/reader_common.py` 中扫描 JSONL 前 100 行的**原始文本**，用 `/claude/(name)` 正则投票决定项目归属。这是三层 fallback 的第三层（最后兜底）。

**Codex 会话必定落到 Layer 3**：
- Layer 1 (cwd walk-up)：Codex 的 cwd 始终是 home 目录 `/Users/chat`，无 `CLAUDE.md` 含 `项目中文名` → 失败
- Layer 2 (session_path)：Codex 事件无 `session_path` 字段 → 失败
- Layer 3 (inferred_project regex)：唯一生效层

**投票被工具输出噪声污染**：

问题 session: `~/.codex/sessions/2026/06/03/rollout-2026-06-03T17-51-51-*.jsonl`

前 100 行事件类型分布：
| 数量 | 类型 |
|------|------|
| 26 | `response_item/function_call` |
| 26 | `response_item/function_call_output` |
| 14 | `response_item/message` |
| 12 | `event_msg/token_count` |
| 9 | `response_item/reasoning` |
| 9 | `event_msg/agent_message` |
| 1 | `session_meta` |
| 1 | `event_msg/user_message` |

第 86 行是一个 `function_call_output`（目录列表），包含 59 次 `/claude/aftersales-automation/` 路径引用。实际项目信号（`codex-monitor`）仅出现 4 次（line 2 的 message 1次 + line 34 的 tool output 3次）。

用户的实际任务："我想知道之前我让你设置的定时启动codex并发信息，这个有实际在运行吗？"——与售后自动化完全无关。

## 修复方案

**只改 1 个文件**：`codex-monitor/app/reader_common.py`

### 核心思路：按事件类型加权投票

在扫描每行前，先 `json.loads()` 解析事件类型，根据类型分配权重：

| 权重 | Codex 事件 (有 `payload` dict) | Claude Code 事件 (无 `payload`) |
|------|------|------|
| **5x** | `payload.type == "user_message"` | `type == "user"` |
| **1x** | `session_meta`, `response_item/message`, `agent_message`, `reasoning` 等 | `type == "assistant"` 等 |
| **0 (跳过)** | `function_call_output`, `function_call`, `token_count` | — |

- 格式区分：有 `payload` dict = Codex，否则 = Claude Code
- JSON 解析失败 → weight 0（跳过）
- weight > 0 时，对该行原始文本跑现有 regex，票数乘以 weight

### 新增常量

```python
_CODEX_NOISE_SUBTYPES = frozenset({
    "function_call_output",  # 目录列表/文件内容/搜索结果
    "function_call",         # 工具调用参数
    "token_count",           # 计费数据
})
_CODEX_HIGH_SIGNAL_SUBTYPES = frozenset({"user_message"})
_CLAUDE_HIGH_SIGNAL_TYPES = frozenset({"user"})
```

### 新增 `_line_weight(line: str) -> int` 辅助函数

解析 JSON → 判断格式 → 查权重表 → 返回 int。

### `infer_project_from_handle` 改动

在现有循环中加入 `weight = _line_weight(line)` 门控，`votes[name] += weight`。

### 不改的文件

- `reader_codex.py`、`reader_claude.py` — 调用签名不变
- `aggregate.py` — 三层 fallback 不变
- 现有 fixture `codex_session.jsonl` — `session_meta`(weight=1) 仍匹配 `codex-monitor`，`token_count`(weight=0) 被跳过，结果不变

## 审查要点

请 Codex 重点审查：

1. **权重分配是否合理**：user_message 5x 是否足够/过多？其他信号类型的权重？
2. **噪声类型是否完整**：除了 `function_call_output`、`function_call`、`token_count`，还有哪些 Codex 事件类型应该排除？
3. **Claude Code 侧**：Claude Code JSONL 没有显式的 tool output 事件类型（content 嵌在 `assistant` 消息里），当前方案对 Claude Code 的影响是否中性？
4. **边界情况**：如果前 100 行全是噪声类型（所有信号行都在后面），返回 None → 归入"其他"——这个降级是否可接受？
5. **性能**：每行多一次 `json.loads()` 对 100 行窗口的影响是否可忽略？
6. **是否需要同步增加 `max_lines`**：当前 100 行窗口在高噪声 session 中可能不够，是否应该增加到 200？

## 验证计划

1. `python3 -m unittest discover -s tests -v` — 现有测试通过
2. `python3 -m compileall app tests` — 语法检查
3. 手动验证问题 session 推断结果不再为 `aftersales-automation`
4. UI demo 验证今日项目分布
