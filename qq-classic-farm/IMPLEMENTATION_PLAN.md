# 农场 Runner V2 实施计划

当前唯一现役实施计划。稳定架构定义见：
`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`。

## 已达到的基线

Runner 已完成 V2 方向切换：

```text
EMPTY → PLANTING → GROWING/MATURE → HARVESTING → EMPTY
DIRTY/UNKNOWN → STOP
```

现役原则：

- 固定窗口 + 固定 4×6 网格；
- 平台独立的小 ROI 找图/找色；
- Picker 只允许“验证哪个 seed/slot，就点击同一个 seed/slot”；
- 普通种植要求 one-key 明确 ON；四格种植要求 OFF；
- Phase 只从已验证 EMPTY 开始，Runner 自己维护 `known_occupied`；
- 异常不补洞、不盲重试、不推断崩溃进度；
- 正常 phase 不允许 Agent 单击级遥控。

截至 2026-11-02：

- QQ / 微信 `check-empty` 均已通过当前 1.16.1.6 真机正负样本；
- QQ 普通 one-key：EMPTY → 紫薇×24 → occupied 24/24 已真机通过；
- 微信普通 one-key：EMPTY → 黄金果×24 → occupied 24/24 已真机通过；
- 微信成熟普通整田：一键收获 → EMPTY 已真机通过；
- QQ 四格 preview/confirm 已离线校准并接入动作层；
- 全项目 170 项测试通过。

详细阶段历史见 `docs/archive/README.md`。

## 剩余里程碑

### 1. QQ 四格 + 普通混合种植

目标：

```text
EMPTY
→ 四格 placement（OFF picker → preview → confirm → 目标4格 occupied）
→ 普通 one-key 填剩余格
→ GROWING
```

验收：

- 四格确认后的目标 2×2 ROI 真机通过；
- 多个 placement 不互相覆盖；
- 普通剩余格数只由本轮 `known_occupied` 推导；
- 最终 24 格全部进入预期占用状态；
- 任一 UNKNOWN / 窗口漂移 / slot 不一致立即 STOP。

### 2. QQ 完整收获

目标：

```text
MATURE → 已知四格可摘 → 一键收获 → EMPTY
```

验收：

- 四格“可摘”只在本轮已知 placement 附近验证；
- 四格逐个收获后，只点一次游戏手形一键按钮；
- 等动画后 `check-empty --platform qq` 返回 EMPTY；
- 非 EMPTY / UNKNOWN 不继续补点。

### 3. 微信四格参数化

QQ 的四格状态机不变，只补微信自己的：

- preview ROI；
- confirm 按钮/偏移；
- 四格落地 occupied ROI；
- 安全 placement 真机验收。

### 4. 微信完整一轮

当前黄金果成熟后执行：

```text
MATURE → 一键收获 → EMPTY
```

该轮通过后，微信普通种植→成熟→收获→EMPTY 才算完整验收。

### 5. Planner / 库存

双平台机械闭环稳定后再接：

- 当前库存同步；
- 连续 3 轮计划；
- 已确认种植/购买后更新库存；
- 活动优先、8h/12h 成熟窗口继续由 Planner 决定。

### 6. 定时化

只在 Runner 稳定后重新评估：

- 定时任务只调用完成的 Runner；
- STOP 时只报告异常，不自主研发/改代码；
- 不恢复此前“每小时自主研发 Runner”的任务。

## 成功标准

第一阶段不是“测试更多”，而是：

> QQ 和微信都能在已知正常现场中，由本地 Runner 连续完成机械 phase；正常路径无需模型逐点击参与，异常则可靠 STOP。
