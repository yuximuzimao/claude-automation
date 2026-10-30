# 本地农场 Runner 实施计划

> **用途：给后续执行者（自恢复任务 / 当前助手 / 本地 Codex）接手开发。**
>
> 本文件不是“下一轮种什么”的运行计划，也不是脚本的日常输入；它是**如何把 QQ / 微信《QQ经典农场》重构成可反复使用、本机高速执行器**的开发计划、进度表与验收标准。
>
> 后续执行者应以本文件为第一执行依据。开发过程中直接维护本文的任务状态与验证结果；默认由当前助手通过 CodexPro 本地工具推进，不默认依赖 Codex CLI；不要再回到“Agent 看一张图、点一下、再看一张图”的遥控方式。

---

## 1. 第一目标

本次重构的第一目标只有一个：

> **已经跑通过的机械流程，必须在本机连续、流畅地执行；正常路径里大模型不参与鼠标级操作。**

排序如下：

1. **用户可感知的流畅度**：连续动作，不再每几秒停下来思考。
2. **确定性与安全**：不种错、不乱点、不误消费付费/高级资源；异常宁停勿猜。
3. **游戏策略效率**：升级经验优先，QQ / 微信尽量保持同成熟窗口。
4. 通用性、漂亮架构、全自动重规划、定时运行都排在后面。

如果一项改造让内部判断更复杂、更“智能”，但用户看到鼠标仍然一步一卡，则不算改进。

---

## 2. 架构结论

旧架构：

```text
ChatGPT / Agent
  ↓
CodexPro 工具调用
  ↓
截图 / 单击脚本
  ↓
返回 Agent
  ↓
再推理下一步
```

最大问题：每一个本来几十毫秒的本地动作，都被模型推理、工具往返、截图传输放大到秒级。

新架构：

```text
Planner（ChatGPT / Codex）
  ↓ 只生成策略输入
RUN_PLAN（种什么、多少、成熟档、四格 placement）
  ↓
Local Runner（一个长运行进程）
  ├─ 读取本地库存/顺序状态
  ├─ 计算 picker 当前 page/slot
  ├─ 本地图像校验
  ├─ CGEvent 连续操作
  ├─ 本地阶段验收
  └─ 更新事实状态 / 运行进度
        ↓
只有异常才返回 Codex / ChatGPT
```

**正常路径必须做到：一个 cycle 一次启动，Runner 自己跑完。**

---

## 3. 三类数据必须分开

这是本次重构最重要的数据边界。

### 3.1 稳定机制 / 配置

由项目维护，不随每轮种植变化。

建议最终文件：

```text
data/ui-layout.json        # 现有：窗口基线、24格网格、2x2 placement
data/ui-anchors.json       # 现有：动态按钮视觉锚点
data/seed-catalog.json     # 现有：种子属性、图标、成熟时间、经验
data/seed-order.json       # 新：每个平台重新进入后校准的 stable_order；若重进重置假设被否定，再扩展 revision
data/runner-config.json    # 新：联系人、日常固定规则、等待参数等
```

### 3.2 可变事实状态

建议新建：

```text
data/farm-state.json
```

它只保存**事实**，不保存策略。例如：

- QQ / 微信当前每种种子的数量。
- inventory revision / last synced time。
- 当前平台 `stable_order` / `stable_order_verified_at`；`visible_order` 每次由 stable_order + quantities 临时计算，不长期保存。
- 当日分享 / 商店福利 / 每日任务是否已完成。
- 上一次成功 cycle。
- 用户或未知奖励导致的 inventory_dirty。
- 当前窗口已验证的布局版本。

Runner 可以修改事实状态。

### 3.3 运行策略输入

以后再建立，例如：

```text
RUN_PLAN.md
```

它是 Planner 给 Runner 的输入，只保存“要做什么”，例如：

- cycle 1：
  - QQ：泡泡棉花糖 ×3，placement gold_a/b/c；天山红枫 ×12；12h。
  - 微信：星语铃花 ×2，placement purple_a/b；黄金果 ×16；12h。
- cycle 2……
- 是否启用普通化肥模式。
- 本轮目标成熟档 / 下次方便操作窗口。

**RUN_PLAN 不保存 picker page/slot。**

page/slot 是 UI 派生结果，必须由 Runner 根据 `stable_order + quantities` 动态计算当前 visible_order 后得到；RUN_PLAN 不关心位置。

---

## 4. 种子位置算法：优先验证“新获取临时插入，重新进入后恢复稳定顺序”

用户提出的核心判断是正确的：**种子用到 0 后，位置左移只是一个本地数组问题，不需要 AI。**

历史数据里微信曾出现两套相对顺序，但现在**不能直接下结论为“活动永久改序”**。更符合现有操作过程的首要假设是：

> **新获得种子时，当前会话的 picker 可能临时插入/调整；关闭或重新进入农场后，picker 会按稳定的正常顺序重新生成。**

这与现有证据并不冲突：
- 历史顺序可能采集于“刚获得森野白桃”的同一会话。
- 2026-10-28 的完整仓库快照来自重新进入后的正常现场，因此更可能代表 fresh-entry 稳定顺序。
- 我们每一轮自动流程本来就是重新进入/恢复农场后开始，并且神秘商人、任务、奖励都安排在**种植完成之后**；因此即便新种子刚获得时临时插入，也不会影响本轮已经完成的种植。

所以第一目标下先采用更简单的模型，并把“是否真会重置”列为 Codex 必须验证的假设。

### 4.1 正常模型：fresh-entry order + quantities

维护：

```text
stable_order     # 重新进入农场后确认的稳定完整相对顺序；可包含当前数量为0但历史已校准的已知种子
quantities       # 当前数量事实
stable_order_verified_at
```

当前 picker 位置：

```python
visible_order = [
    seed for seed in stable_order
    if quantity.get(seed, 0) > 0
]

index = visible_order.index(target_seed)
page = index // 5 + 1
slot = index % 5 + 1
```

Runner 确认成功消费后：

```python
quantity[target_seed] -= used
```

如果数量变 0，下一次计算自然过滤掉；后面的种子自动左移。

**这一过程完全不需要 AI，也不需要为了位置稳定保留 1 个库存。**

### 4.2 数量变化按最简单规则处理

1. `>0 → >0`：只改数量；顺序不变。
2. `>0 → 0`：下次 visible_order 过滤掉；自动左移。
3. 本轮在种植完成后获得新种子：更新数量事实，但本轮不再需要 picker，因此不为临时顺序做任何额外处理。
4. 下一轮重新进入后：
   - 已知种子：按 stable_order + quantities 计算预期位置，并用目标图标做小 ROI 校验；若它此前为0，现在重新出现，也会自然回到稳定位置。
   - 真正全新种子：需要一次 fresh-entry 顺序校准，确定它在 stable_order 中的位置。

### 4.3 Codex 必须验证的“重进重置”假设

不要把微信历史顺序差异直接编码成 order revision 常态机制。

优先做一次可复现实验：

1. 找一个能明确观察“刚获得种子”的时机；记录获得前 fresh-entry 顺序。
2. 获得种子后，不退出农场，立即读取 picker/仓库顺序，记为 `session_order_after_acquire`。
3. 关闭/退出农场并按正常入口重新进入。
4. 再读取顺序，记为 `fresh_order_after_reopen`。
5. 比较：
   - 如果重新进入后恢复稳定历史顺序：确认“临时插入模型”。
   - 如果重新进入后仍保持新相对顺序：才升级为真正的 `order_revision` 模型。

在没有完成这个实验前：
- 2026-10-28 fresh-entry 仓库序列作为当前运行基线。
- 微信历史 `森野白桃/艾草` 顺序差异只记录为**待解释证据**，不能宣称是永久改序。

### 4.4 如果临时插入模型验证成立

数据模型进一步简化：

- 正常运行只需要 `stable_order + quantities`。
- Runner 自己把种子用到 0：visible_order 计算时过滤即可，不修改 stable_order。
- 已知种子 0→positive：重新进入后按 stable_order 自动恢复到稳定位置。
- 商人/奖励在种植后新增种子：本轮只更新数量，不处理临时插入顺序。
- 只有真正全新 seed 第一次进入稳定顺序时，重进后做一次本地校准并插入 stable_order。

这种方案最符合第一目标：**把低频校准留给异常路径，正常每轮不扫描整个仓库、不维护复杂 revision。**

### 4.5 如果假设被实测否定

只有在“重新进入后仍保持不同顺序”被真机证明后，才启用更复杂的：

`visible_order + order_revision + order_dirty`

机制。

也就是说，revision 模型是**验证失败后的备选方案，不是当前默认架构**。

---

## 5. 比纯算法更稳的方案：算法定位 + 本地图标校验

单靠 inventory 算位置很快，但用户可能手动种过、奖励可能改变数量，因此推荐使用**混合 fast path**。

### Fast path

1. 根据当前 `visible_order` 直接算出 expected page/slot。
2. Runner 用本地 page indicator/有界翻页逻辑到目标页；**不得未经验证假设 picker 每次都从第1页打开**。
3. 用 `assets/seeds/<target>.png` 在该 slot 的小 ROI 内做本地图标匹配。
4. 对本轮需要多颗的目标，在同一 slot 小 ROI 内读数量徽标；确认 `visible_quantity >= planned_use_remaining`。数字识别可用本地 digit template/OCR，不能交给 LLM。
5. 图标与数量前置条件都正确 → 点击。

这一步不需要 OCR、不需要上传截图、不需要 Agent。

### Local fallback

expected slot 图标不匹配时：

1. Runner 在 picker 各页本地快速搜索 target seed icon。
2. 找到：
   - 说明 inventory/order state 有漂移。
   - 可以记录实际 page/slot。
   - 若 target 本身仍足够完成本轮，可选择：
     - **MVP：停止并标记 STATE_DRIFT**；
     - 稳定后：自动 reconcile 后继续。
3. 找不到：
   - STOP `TARGET_SEED_NOT_FOUND`。

第一版优先“发现漂移就停”，不要一开始做过强的自修复。

### 为什么推荐混合方案

它同时解决：

- 正常路径：直接从 visible_order 算位置，最快。
- Runner 自己把数量用到0：数组删除，自动左移，无需 AI。
- 用户手动消耗：图标校验能发现。
- 活动新增/0→positive/顺序 revision：本地同步一次 visible_order。
- 不需要为了位置稳定强行保证所有种子 >0。

---

## 6. 运行计划应该写什么、不写什么

未来 `RUN_PLAN.md` 只放策略，不放 UI 派生信息。

### 应该写

示意：

```yaml
cycle: 1
maturity_target: 12h
qq:
  special:
    seed: 泡泡棉花糖种子
    count: 3
    placements: [gold_a, gold_b, gold_c]
  ordinary:
    - seed: 天山红枫种子
      count: 12
wechat:
  special:
    seed: 星语铃花种子
    count: 2
    placements: [purple_a, purple_b]
  ordinary:
    - seed: 黄金果种子
      count: 16
```

### 不应该写

- page 4 slot 1。
- 截图坐标。
- 屏幕绝对坐标。
- “如果没找到就自己换某某种子”。
- 临场经验排序逻辑。

这些都不属于策略输入。

---

## 7. 已踩坑清单 → Runner 硬约束

### 7.1 禁止 Agent 微操作

正常 cycle 内不得出现：

```text
截图 → 模型判断 → 单击 → 截图 → 模型判断
```

正常 phase 中模型 round-trip 必须为 0。

### 7.2 坐标体系必须唯一

过去多次误点的直接原因：截图像素坐标、裁图坐标、放大图坐标、macOS CGEvent 逻辑坐标混用。

Runner 内唯一权威：

```text
window-local logical coordinate
```

点击：

```text
screen_x = current_window_x + local_x
screen_y = current_window_y + local_y
```

视觉识别输出必须在模块内部转换为 window-local 后才返回 Runner。

禁止外层代码拿截图像素直接点击。

### 7.3 每次使用当前窗口位置

窗口可以移动。

每个跨应用 phase 或窗口恢复后：

- 重新枚举目标窗口。
- 重新读 origin / size。
- 重新计算 screen coordinate。

禁止复用旧的 screen absolute coordinate。

### 7.4 QQ 入口

已验证：

- QQ 主窗口约 1239×928。
- 左侧固定农场入口相对主窗口约 (31,307)。
- 正常路径：定位主窗口 → 固定相对坐标 → 打开农场。
- **禁止失败后改走“更多功能”。**

现有 `scripts/open_qq_farm.swift` 可作为实现参考或直接复用。

### 7.5 微信入口

固定恢复链：

```text
微信主窗口
→ 发现
→ 游戏
→ 最近玩过
→ QQ经典农场
```

若独立农场窗口已经存在，直接恢复，不重复走入口。

### 7.6 四格种植是事务

错误历史：

- 出现 2×2 预览 ≠ 已种下。
- 点击另一块土地会移动/改变预览。
- 预览位置取决于最初点击的土地。

Runner 每颗必须原子执行：

```text
placement anchor
→ open picker
→ choose seed
→ preview geometry check
→ confirm
→ landed check
```

未 landed 前禁止开始下一颗。

### 7.7 四格土地等级

- 跨紫晶 + 金地会按低档金地算。
- QQ：固定使用 3 个纯金 2×2。
- 微信：固定使用 2 个纯紫晶 2×2。

placement 已存在 `data/ui-layout.json`。

Runner 不临场“看哪块顺眼”。

### 7.8 普通一键种植

- 用户默认勾选“一键种植”。
- 选择普通种子后应填满剩余空格。
- 过去出现过漏紫晶格 bug，因此普通种植后必须一次做 24-cell occupancy postcondition。
- 不满 24：STOP，不自行选择另一种补洞。

### 7.9 收获

普通 1 格：

- 全局手形一键收获。

四格：

- “可摘”星标必须逐个点。
- 全部可摘一次识别后连续点完。
- 然后全局手形一次处理普通作物 + 四格残株。
- 等动画后只做一次 clean-field 验收。

禁止每摘一个就回 Agent。

### 7.10 多季作物

普通多季作物：

- 第一季收获后继续生长。
- 第二季/最后一季再收获并清理。

普通化肥：

- **每个生长阶段一次**。
- 新一季重新获得一次普通肥机会。

Runner 状态必须按 growth_stage，而不是把整株植物记成“普通肥已用过”。

### 7.11 化肥

- 普通肥：当前 stage 最多一次。
- 高级肥：可多次。
- 一键施肥 toggle 按 QQ / 微信独立保存，不能跨平台假设。
- 微信出现过首次化肥确认弹窗：确认弹窗 ≠ 实际施肥成功。

**实施顺序上化肥后置**，不能让它拖慢 M1/M2。

### 7.12 务农

- 未成熟时才可能出现“一键务农”。
- 有就一次处理。
- 如果后续要展开化肥菜单，必须先务农，否则菜单结构可能多一个动作、相对位置变化。

### 7.13 神秘商人 / 仓鼠

长期规则：

> 气泡出现就购买（种子或化肥）。

如果 Runner 能识别购买物品和数量：

- 直接更新 farm-state inventory。

如果第一版无法可靠识别：

- 完成购买。
- 标记 `inventory_dirty=true`。
- 在下次需要依赖库存位置计算前触发一次本地 inventory sync。

不要让 Agent每次看商人截图。

### 7.14 好友交互

稳定链：

- 可交互好友优先。
- 进入后出现“一键偷取 / 一键务农”哪个点哪个。
- 下一位还有标志继续。
- 第一位没有可交互或下一位无按钮即停止。
- 回家。

不识别头像身份，只识别稳定按钮/气泡。

### 7.15 分享

固定目标：

- 微信：**咩不是咩是喵**
- QQ：**灬🐈‍⬛、御汐。**

必须用搜索框精确搜索。

跨应用差异：

- 微信分享联系人窗口仍在微信体系内。
- QQ 分享会把焦点带到 QQ 主程序，发送后要显式恢复 QQ 农场。

跨应用后必须重新读农场 window bounds。

### 7.16 商城每日福利

确定性链：

```text
商城 → 礼包商城 → 每日福利 → 免费 → 奖励 → 返回农田
```

只点免费，不碰其它付费入口。

### 7.17 每日任务

登录 / 采摘 / 好友互动是当前已验证三类。

同一天已经完成后不重复打开任务书。

日期判断是普通 deterministic logic，不属于“AI 决策”。

### 7.18 焦点问题

过去有点击/滚动发给 Chrome/Finder。

每个 action phase 前：

- target window owner/name 必须匹配。
- action point 必须在 target bounds 内。
- 跨程序后重新定位。

不满足直接 STOP。

---

## 8. Runner 状态机

一次命令建议：

```bash
python3 scripts/farm_runner.py run-next
```

Runner 自己执行完整 cycle。

### Phase 0 — PRECHECK

- 读取 RUN_PLAN。
- 取第一个 pending cycle。
- 读取 farm-state。
- 锁文件，禁止重复 runner。
- 检查当前 plan/state revision 兼容。
- dry-run 时只输出动作，不点击。

### Phase 1 — OPEN

分别恢复 QQ / 微信农场窗口。

每个平台完成后记录：

- window owner/name。
- window origin。
- window size。
- layout version。

### Phase 2 — HARVEST

本地一次 screenshot/probe：

- 识别 special pickables。
- 批量连续点击。
- 全局 hand 一次。
- 等动画。
- clean field postcondition。

未知遮罩 → STOP 或已知 overlay 白名单恢复一次。

### Phase 3 — PLANT SPECIAL

按 RUN_PLAN placements 顺序逐颗事务执行。

每颗：

1. placement → local plot anchor。
2. 打开 picker。
3. 用当前 `visible_order` 算 expected page/slot。
4. 本地到目标页；expected slot 图标校验 + 数量徽标校验（至少足够完成当前剩余 special count）。
5. 选 seed。
6. preview geometry 校验。
7. confirm。
8. landed 校验。
9. 数量 -1；若变0，立即从内存 visible_order 删除，**后续 ordinary 的位置必须重新计算**。
10. 写内存 state；本轮成功后统一落盘。

这里允许每颗局部截图/视觉校验，但全部在 Runner 本机，不返回模型。

### Phase 4 — PLANT ORDINARY

1. 打开剩余空地 picker。
2. 用最新 visible_order 计算 target seed expected position（special 若刚好用到0，这里必须使用删除后的新顺序）。
3. 图标校验 + 数量徽标校验，确认库存至少覆盖计划普通格数。
4. 选择种子，一键种植。
5. 24-cell occupancy 验收。
6. 按实际成功用量扣库存；如果目标种子变0，从 visible_order 删除。

如果计划要求 12 颗但结果不是 12 格：

- 不猜。
- STOP。

### Phase 5 — MAINTENANCE

MVP：

- 一键务农。
- 仓鼠气泡购买。

化肥先作为独立后续模块。

### Phase 6 — DAILY

用 farm-state 的 last_daily_date：

新日期首轮：

- 分享。
- 商城福利。
- 好友互动。
- 每日任务领奖。

同日期后续：

- 跳过分享/商城/任务。
- 好友互动仍可执行。

### Phase 7 — FINALIZE

- 最终回自己的农田。
- 24 格 / 页面状态验收。
- 写 farm-state 数量。
- RUN_PLAN cycle → complete。
- 写 duration / metrics / run log。
- 解锁。

---

## 9. 本地视觉与执行层

### 9.1 不允许每个动作单独启动 Swift 解释器

过去使用：

```bash
swift click.swift x y
```

每次都会有进程/解释编译开销。

正确方式：

- 一个长运行 Python Runner。
- 一个预编译 CGEvent helper，或 Runner 能直接调用的常驻本地桥。
- 连续动作 batch 发送。

Codex 可以自由选择最小实现，但不得退回“每一击一个 swift 命令”。

### 9.2 Picker 页导航

- 不假设 picker 每次打开都在第1页，除非真机连续验证后把该行为写成稳定规则。
- 第一版可采用：读取小 ROI 页码/页指示器，或最多 N 次向左归一到第一页再向右到目标页；全部本地执行。
- 选择完一种 seed 后下一次打开 picker 的页状态要重新验证，不能继承上一次内存页码盲点。
- page navigation 也必须记录 duration；如果归一翻页成为明显瓶颈，再优化缓存。

### 9.3 视觉逻辑 in-process

现有：

- `anchor_locator.py`
- `pickable_locator.py`
- `ui_probe.py`
- `seed_picker_locator.py`

应提取为 importable module，例如：

```text
scripts/farm_vision.py
```

Runner import 函数。

正常识别不要为每一次状态检测再启动一个 Python subprocess。

### 9.4 截图

macOS 15 下旧 CoreGraphics window image API 不可用。

MVP：

- 读取 window bounds。
- `screencapture -x -R...`
- 本地 PIL/Numpy 读取。

如果未来截图本身成为性能瓶颈，再换 ScreenCaptureKit；**MVP 不先做**。

### 9.5 小 ROI 优先

正常 phase：

- 种子 slot：只看 slot ROI。
- confirm：只看 confirm ROI。
- hand / one-key：只看按钮区。
- hamster：只看左下小区域。
- friend：只看底栏。

只有异常保存/显示整页。

---

## 10. farm-state 设计要求

建议结构（Codex 可调整字段名，但语义必须保留）：

```json
{
  "schema_version": 1,
  "inventory_revision": 1,
  "platforms": {
    "qq": {
      "quantities": {
        "泡泡棉花糖种子": 21,
        "天山红枫种子": 18
      },
      "inventory_dirty": false,
      "last_daily_date": "2026-10-29"
    },
    "wechat": {
      "quantities": {},
      "inventory_dirty": false,
      "last_daily_date": "2026-10-29"
    }
  }
}
```

原则：

- successful landed / one-key planting 后再扣。
- 点击已发送但未验收，不扣。
- 本轮中途异常，已确认成功的实际消耗要保存到 recovery log，不能假装没发生。
- state 写盘使用 atomic replace，避免崩溃写坏 JSON。

---

## 11. RUN_PLAN 设计要求

Codex 在 Runner 基础完成后建立样板即可，**不要现在替 Planner 决定未来种什么。**

必须满足：

- 人类可读。
- 机器可解析。
- 有 plan_id/revision。
- cycle 有 pending/running/complete/error。
- 只写策略输入。
- 不写 page/slot。
- 不写屏幕坐标。
- 可写预计成熟时长和 next-run window。
- Runner 只能更新进度字段，不能修改种子策略。

---

## 12. 错误协议

Runner 遇异常必须返回结构化 error。

示意：

```json
{
  "status": "stopped",
  "code": "SEED_SLOT_VERIFY_FAILED",
  "platform": "qq",
  "phase": "PLANT_SPECIAL",
  "target_seed": "泡泡棉花糖种子",
  "expected_page": 1,
  "expected_slot": 3,
  "artifact": "runs/.../error.png"
}
```

核心错误码至少包括：

- WINDOW_NOT_FOUND
- WINDOW_SIZE_CHANGED
- WRONG_FRONTMOST_APP
- UNKNOWN_OVERLAY
- TARGET_SEED_NOT_FOUND
- SEED_SLOT_VERIFY_FAILED
- INVENTORY_DIRTY
- ORDER_CONFLICT
- SPECIAL_PREVIEW_MISMATCH
- SPECIAL_CONFIRM_FAILED
- ORDINARY_FILL_MISMATCH
- DAILY_FLOW_MISMATCH
- USER_INTERFERENCE

错误规则：

- 停止后不继续点。
- 保存截图 + phase + plan revision + state revision。
- 不自行换种。
- 不自行换入口。
- 不自行“试几个坐标”。

---

## 13. Codex 开发阶段

### M0 — 清理旧控制方式 + 数据模型

当前初始化事实（用于 dry-run，不等于未来 RUN_PLAN）：

- 2026-10-28 仓库快照是最近一次“重新进入后的正常现场”完整可见顺序，优先作为当前 stable_order 校准证据。
- 2026-10-29 已知 Runner/Agent 实际消费没有让任何目标种子归零，因此当前可见顺序预计仍与 10-28 fresh-entry 序列一致。
- 已知数量增减至少包括：QQ 泡泡棉花糖 `24→21`、天山红枫 `30→18`；微信星语铃花 `10→8`、天山红枫 `30→14`，并通过神秘商人购买哈哈南瓜 `7→8`。这些只是 farm-state 初始化 delta，Codex 不应把它们写成新的种植策略。

任务：

- [x] 禁用 Agent 单击级正常执行入口：新 Runner 只开放离线 dry-run，`run-next` 明确返回 `RUNNER_NOT_READY`；旧脚本仅作为诊断工具保留。
- [x] 建 `data/seed-order.json`，保存每个平台 `stable_order + verified_at + evidence`；没有启用 revision。
- [x] 用 2026-10-28 fresh-entry warehouse sequence + 历史 `picker-order.json` 初始化。历史仅有的零库存候选单独存为 `historical_zero_candidates_uncalibrated`，不猜插入位置；微信 `森野白桃/艾草` 差异仅作为待验证假设。
- [x] 建 `data/farm-state.json`；应用 2026-10-29 已记录数量变化，但真实库存尚未重新验证，双平台 `inventory_dirty=true`。
- [x] 实现 `compute_visible_order(stable_order, quantities)` 和 `compute_picker_position(platform, seed, stable_order, quantities)`。
- [x] 单元测试库存从 >0 → 0：stable_order 不变，visible_order 自动过滤，所有后续 page/slot 正确左移。
- [x] 单元测试已知种子 0 → >0：stable_order 不变，visible_order 自动重新包含该种子并回到稳定位置。
- [x] 设计并记录“刚获取 → 不退出读取顺序 → 重新进入 → 再读顺序”的真机验证步骤；**实际真机实验仍待 M1/M2 后验证，不得把假设写成已证实。**
- [x] 定义未来 RUN_PLAN schema 和 EXAMPLE-ONLY 样例（不做真实长期策略）。
- [x] Runner dry-run 框架，11 项离线单测通过；完整验收见 `docs/runner-m0-verification.md`。

**M0 离线验收：2026-10-30 已通过。** 仅代表数据模型与 dry-run 已完成；M1/M2 的真机执行、目标图标与数量校验尚未开始。下一次直接进入 M1，不要重复 M0。

验收：

- 不打开游戏也能用 stable_order + quantities 算出任意可见种子的 picker page/slot。
- 将任意一个种子数量扣到 0 后，无需修改 stable_order，所有后续位置自动正确左移。
- 将一个历史已知种子从 0 改为 >0 后，自动回到 stable_order 定义的位置。
- 微信历史差异被保留为待验证假设，系统不会提前把它编码成永久改序机制。
- 不需要 Agent。

### M1 — 本地 I/O + 收获

任务：

- [ ] window registry：已新增只读 `scripts/window_registry.swift`（含 window_id/pid），Swift 编译通过；`scripts/farm_io.py` 已接入 Runner 的 `probe-harvest` 只读命令，按 owner/title/尺寸/ID 唯一验证。2026-10-29 本轮 QQ/微信均 `WINDOW_NOT_FOUND`，实机窗口联调仍待完成。
- [x] window-local → screen 唯一坐标：`scripts/farm_geometry.py` 纯逻辑转换、Retina screenshot pixel → local logical → screen、越界/尺寸/owner fail-closed；6 项离线单测通过，实际 CGEvent 联调仍待后续。
- [x] screenshot/crop **离线实现**：`scripts/farm_capture.py` 按实时 window bounds 调用 `screencapture -x -R`，严格检查 crop/Retina 比例，统一转换 window-local；实机窗口截图待验证。
- [x] in-process vision **离线实现及几何安全回归通过**：`scripts/farm_vision.py` 直接 import 现有 NCC/pickable 模块，返回 window-local logical 点；已修正 Retina 2x 模板尺度、pickable 去重半径，并按 `safe_special_2x2` 几何中心筛选候选，重复/无效候选结构化 STOP。43 项离线测试通过；实际农场星标偏移与四格占用仍待真机校准，probe 永不授权点击。
- [ ] batch CGEvent：`scripts/farm_click_batch.swift` 已可编译并通过无点击 validation-mode 测试；每击检查 window ID/PID、前台、尺寸及遮挡。**尚未实机发送 CGEvent、尚未接 harvest phase**。
- [ ] QQ / 微信窗口恢复。
- [ ] harvest phase：已新增 `scripts/farm_harvest.py` 纯本地可注入 I/O 的确定性阶段状态机（单批 special stars → hand → 3s → 24-cell clean-field 验收），18 项 mock 回归通过；**尚未接真实视觉/CGEvent**，占地/星标/遮罩与 24 格空地识别均待真机校准，不能视为可执行。
- [ ] known overlay 处理。

验收：

- 一个命令完成“成熟农田 → clean field”。
- 中途无模型参与。
- phase duration 有日志。

**2026-10-29 第7轮 M1 检查点：** 已核对前轮保存的 `farm_vision.py` / `farm_io.py` 四格候选过滤改动，并新增 `tests/test_special_pickables_m1.py`（QQ/微信、Retina 2x、普通单格星标、越界、重复、无效布局、只读 probe）。回归测试揭示关键几何误判：菱形 2×2 的某些单格中心距整体中心仅约 **21 logical px**，原临时 22px 门限会误收普通单格星标；已收紧为 **14px 临时门限**，但真实星标偏移可能仍造成误收/漏收，**不能当作已校准或可执行依据**。无效候选现在返回 `INVALID_PICKABLE_CANDIDATE`，重复归属返回 `AMBIGUOUS_PICKABLES`。累计 **43 项单元测试全部通过**，`farm_click_batch.swift` / `window_registry.swift` / `open_qq_farm.swift` 均 Swift typecheck 通过。只读实机 probe：QQ、微信均 `WINDOW_NOT_FOUND`（独立农场窗口当前未显示），没有截图或点击。`run-next` 仍硬停止 `RUNNER_NOT_READY`。**下一步**：先在可用农场窗口或已知历史画面回放中校准星标偏移与四格占用，完成遮罩检测、clean-field postcondition、收获状态机及批量动作受控联调；未经这些验证不得解锁执行。

**2026-10-30 第9轮 M1 检查点：** CodexPro 连接正常。本轮新增 `scripts/farm_harvest.py` 与 `tests/test_harvest_phase_m1.py`，以注入式本地 adapter 模拟单次收获 phase；已覆盖已空田零点击、四格星标批量+全局手形、普通收获、未知/已知遮罩拒绝、未校准拒绝、占地与星标冲突、点击越界、批量部分成功不重试、缺失/不完整 24-cell 终验、clean-field 与占地矛盾等。**全量 61 项单元测试通过**；3 个 Swift helper typecheck 通过。新状态机仅离线 mock，不接真实点击，`run-next` 仍硬停止。下一步：取得真实/历史农田画面，验证星标偏移、特殊 2×2 占用和 24-cell 空地分类，再把本地 observation adapter/overlay 识别接入 FSM 并受控验收；不能用单纯“星标消失”宣称 clean field。对抗式审查：未增加策略决策，未恢复逐击模型调用，未知弹窗/部分点击均停止；**特别注意 postcondition 必须来自新截图及相同窗口身份**。

**2026-10-30 第10轮 M1 检查点：** 对抗式审查确认上一轮状态机只检查窗口身份，**没有证明点击后的 clean-field 结论来自新截图**；若 adapter 意外复用旧截图，可能将旧观察误作终验。本轮在 `farm_capture.py` 给真实截屏附加唯一 `capture_id` 与 `monotonic_ns`，模拟截图默认不具备可信来源；`HarvestObservation` 明确携带这两项。`run_harvest()` 点击前验证来源，点击后要求新 ID 且时间严格递增，拒绝重复/倒序截图（`HARVEST_STALE_POSTCONDITION`），等待或复拍异常统一结构化 STOP（`HARVEST_POSTCONDITION_UNAVAILABLE`），均记录已发送点击数且禁止重试。新增回归覆盖无来源、重复/倒序、截图/等待异常与两次真实 capture mock 产生不同来源；**65 项单测通过，3 个 Swift helper typecheck 通过，`run-next` 仍返回 `RUNNER_NOT_READY`**。没有实机点击，也没有用假截图宣称 clean-field。下一步仍是取得真实或可信历史农田截图，完成星标偏移、实际 2×2 占用、遮罩及 24 格空地视觉分类校准；之后把真实 capture 的 ID/时间一路传入本地 observation adapter，再受控接线批量 CGEvent。对抗式审查：本轮只加强 I/O 安全，不涉及种植策略、定时化或逐击 LLM。

**2026-10-30 第11轮 M1 检查点：** 已修复收获后 `_clean(after)` 对格式错误的 24 格数据抛出 `INVALID_FIELD_OBSERVATION` 时丢失 `clicks_sent` 的问题；同时拒绝非列表/元组的字段，保证部分执行后的结构化恢复记录不会被清零。发现父工作区 `_sandbox/` 中有历史真实截图，离线重放揭示 **同样接近基线尺寸的截图，固定网格原点仍可能明显平移**：QQ `qq-after-harvest-today.png` / `qq-final-clean.png` 相对现有 `ui-layout.json` 约 **(-9,+18) logical px**；微信 `wechat-cleared-final.png` 约 **(-60,+1) logical px**。这说明仅检查窗口尺寸不足以授权地块点击；不能把历史静态中心直接当作实时坐标。新增 `scripts/farm_field.py`：对露出的紫晶土壤进行颜色分割、组件筛选、完整格点一致性校验，输出 **只读诊断** `field_alignment.offset_local`，不返回点击许可；部分遮挡/成熟覆盖/颜色证据不足即 `FIELD_ALIGNMENT_UNAVAILABLE`。`farm_capture.py` 同时保留 RGB 供局部颜色校准，`probe-harvest` 输出该诊断。历史回放：QQ 两张完整空田与微信一张完整空田均获得一致平移；QQ 成熟/遮罩与微信成熟/残株样本拒绝校准；微信紫地露出而金地已种的样本也能估计平移，**这不代表 24 格空地已被验证**。新增 6 项离线测试，加上异常回归 1 项，**全量 72 项通过，3 个 Swift helper typecheck 通过**；`run-next` 仍返回 `RUNNER_NOT_READY`。QQ/微信只读窗口探测均 `WINDOW_NOT_FOUND`，未实机点击。下一步：用现场窗口校验画布平移及星标相对 2×2 的真实偏移；为成熟田设计不依赖露出紫地的可靠对齐/占用证据，再做遮罩与 24 格 clean-field 视觉分类；**未完成这些前不得把该诊断用于执行授权**。未增加策略、定时化或逐击 LLM。


**2026-10-30 第12轮 M1 检查点：** 对抗式审查发现 CGEvent 批量 helper 在第 N 次点击前若窗口移动、遮挡或焦点变化，旧错误 JSON **没有已发送点击数**，而 Python 收获状态机也会在 adapter 抛异常时丢弃已知部分计数，妨碍安全恢复。本轮修改 `scripts/farm_click_batch.swift`：所有运行中 STOP 均返回 `click_count`（仅表示已 post 的 CGEvent，不代表游戏落地），包括窗口枚举/身份/尺寸/焦点/遮挡/事件构造失败；新增 `scripts/farm_io.py::parse_click_batch_result` 严格区分 `validated_no_click` 与 `clicks_sent_unverified`，解析非零退出时保留可信范围内的部分计数，格式错误则按未知计数停止；`farm_harvest.py` 保留 adapter 报出的部分发送数，任何失败都禁止重放。新增批量协议与恢复回归，**全量 78 项单测通过、3 个 Swift helper typecheck 通过**；`run-next` 仍硬停止 `RUNNER_NOT_READY`。这是离线 I/O 可靠性改进，**尚未完成成熟田对齐、四格真实占用、遮罩及 24 格空地视觉分类，未执行真实点击**。下一步继续这些 M1 视觉证据与受控联调；不因 helper 改进提前解锁。对抗式审查：没有将种植策略塞入 Runner，没有逐击 LLM 往返，也没有引入定时/化肥扩展。

### M2 — 种植（最高价值）

任务：

- [ ] picker page navigation（不盲假设起始页）。
- [ ] expected position algorithm。
- [ ] target icon slot verification。
- [ ] target quantity badge local verification，至少防止 ordinary 库存不足造成半填充。
- [ ] local fallback target search。
- [ ] special transaction。
- [ ] ordinary one-key planting。
- [ ] 24-cell postcondition。
- [ ] successful consumption 更新 farm-state。

验收：

- QQ / 微信各连续完整种一轮。
- 不手工修地。
- 种子为 0 导致的左移无需重规划。
- 用户看起来是连续操作，不是一点一停。

### M3 — 日常

按独立模块逐个实现：

- [ ] hamster merchant。
- [ ] shop daily free。
- [ ] share。
- [ ] friend interaction。
- [ ] daily tasks。

每个模块单独有 precondition/postcondition。

不要把日常写成一条长盲点宏。

### M4 — 化肥

在 M2/M3 稳定后：

- [ ] one-key farm。
- [ ] normal fertilizer stage tracking。
- [ ] advanced fertilizer loop。
- [ ] WeChat first-confirm behavior。
- [ ] fertilizer inventory/state。

### M5 — 调度

最后：

- [ ] 根据 RUN_PLAN/成熟时间触发。
- [ ] 打开 → 执行 → 关闭/退出。
- [ ] 异常通知。

M2 稳定前禁止做 M5。

---

## 14. 性能验收

至少记录：

- total_duration_ms
- phase duration
- screenshot count
- click count
- fallback count
- local vision count
- LLM round trips

正常路径硬指标：

- **LLM round trips = 0**
- 不上传中间截图。
- 不按 click 粒度启动外部解释器。
- special 允许逐颗本地验收。
- 其它 phase 以阶段验收为主。
- 用户肉眼看到连续操作。

不要先写死“必须 10 秒”，先用真实数据建立基线；但如果 Runner 依旧隔几秒才动一次，就直接判失败。

---

## 15. 对抗式审查

### A. 用户手动改了库存

风险：

farm-state 不准 → 算错 page/slot。

防御：

- expected slot 做 icon verify。
- mismatch 不盲点。
- local fallback 搜 target。
- 第一版发现 drift 就 STOP，让 Planner 同步事实。

### B. Runner 自己把种子用到 0

这不是异常。

- successful consumption 扣到 0。
- 下一次 visible list filter。
- page/slot 自动重算。
- 不要求规划时留 1 个。

### C. 奖励/商人让已知 0 库存种子重新出现

当前首要假设：刚获取时可能临时插入，但重新进入后恢复 stable_order。

- qty 0→positive：只更新数量。
- 因为商人/奖励位于本轮种植之后，本轮不再依赖 picker，不处理临时插入位置。
- 下一轮重新进入后按 stable_order + quantities 直接计算，并用 expected-slot 图标校验。
- 若校验失败，再触发一次 fresh-entry 顺序同步并记录证据。

不需要 AI。

### D. 全新活动种子首次出现

- 本轮获得后只记录“unknown stable position”，不在已经完成种植的同一轮处理。
- 下一轮重新进入后做一次本地顺序同步，确定它在 stable_order 的稳定位置并写入。
- 如果“重新进入仍不稳定”被真机证明，才升级到 order_revision 备选模型。
- 若本地同步无法唯一识别顺序，则 STOP `ORDER_SYNC_FAILED`。

### E. target 数量不足但 icon 还存在

位置算法不够。

第一版：

- 依赖 farm-state planned quantity。
- 选择后 ordinary fill postcondition。
- 不足则 STOP，不补其它种。

后续可增加数字 OCR 校验，但不是 M0/M1 阻塞项。

### F. 图标相似/模板误匹配

- expected slot ROI 小范围校验。
- 阈值必须回放验证。
- fallback 搜索后仍需唯一高置信匹配。
- 多个近似候选 → STOP。

### G. 窗口移动 / Stage Manager / Retina

- 每个 phase 读 current bounds。
- window-local 为唯一坐标。
- 截图像素不出 vision module。
- bounds 变化不影响 relative clicks。

### H. 未知弹窗

- known overlay 白名单。
- 未知不点空白试错。
- STOP + screenshot。

### I. 用户和 Runner 同时抢鼠标

- run lock。
- 关键状态突然改变 → USER_INTERFERENCE。
- 不尝试“抢回来”。

### J. 为了速度删掉太多验收

不能。

正确优化是：

> 每个 phase 少验收，但验收关键 postcondition。

而不是完全不验收。

### K. Runner 变成第二个“会思考的 Agent”

禁止。

Runner 只允许：

- 条件判断。
- 状态机。
- 数学计算。
- 图像匹配。
- 有限重试。
- 数据更新。

任何“该换什么种子”“今天种8h还是12h”“库存不足该拿什么替代”都必须由 Planner 写入 RUN_PLAN。

---

## 16. 后续执行者接手时的顺序

后续执行者只修改当前 `qq-classic-farm` 项目；父仓库中其它项目与 `.ai-bridge` 的未提交文件与本任务无关，不清理、不重置、不提交。

每次恢复后：

1. 读本文件。
2. 读 `SKILL.md` / `tasks/todo.md` / `docs/CURRENT.md`。
3. 读 `docs/gameplay-rules.md`。
4. 读：
   - `data/picker-order.json`
   - `data/inventory-live-2026-10-28.json`
   - `data/ui-layout.json`
   - `data/ui-anchors.json`
   - `data/seed-catalog.json`
5. **M0 已于 2026-10-30 完成离线验收；下次从 M1 继续。** 详见 `docs/runner-m0-verification.md`，不要重复 M0。
6. **M1/M2 仍先 mock/dry-run 和单元测试，再做真机操作。**
7. M0 的验收证据已记录：
   - 新数据模型。
   - 当前任意 5 个可见种子的计算 page/slot。
   - 将一个种子 qty 置 0 并从 visible_order 删除后自动左移的测试。
   - 微信历史顺序与 2026-10-28 fresh-entry 顺序的差异说明，并明确列出“刚获取临时插入、重进恢复 stable_order”的真机验证步骤。
8. 用户已授权无人值守自恢复续跑，M0 后按验收条件继续 M1/M2；遇到需用户输入/授权的阻塞才暂停报告。
9. M2 真机跑通前，不碰定时化。

---

## 17. 本轮不做的事情

Codex 不要在接手第一轮做：

- 未来 3 天的真实种植策略。
- 自动选最优种子。
- 高级化肥最优化。
- 定时启动。
- 通用游戏视觉 Agent。
- ScreenCaptureKit 大重构。
- 全仓 OCR 重建。
- UI 面板。

这些都不是第一目标。

---

## 18. 开发完成的判定

真正的成功不是“脚本多了”，而是用户说一句：

> 执行这一轮。

然后本地 Runner：

- 自己找到窗口。
- 自己收获。
- 自己根据 RUN_PLAN 找到种子。
- 库存变 0 后自己算新位置。
- 自己种完。
- 自己做稳定日常。
- 自己验收。
- 正常情况下不中断、不问 AI。

只有异常才把一张截图和结构化错误交回 Codex / ChatGPT。

**这才算完成本次重构。**
