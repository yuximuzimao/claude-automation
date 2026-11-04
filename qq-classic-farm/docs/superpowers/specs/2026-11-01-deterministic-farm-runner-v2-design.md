# 农场 Deterministic Runner V2 设计

> **状态说明（2026-11-05）：旧方案，当前暂停。** 本文记录此前的技术设计，不代表当前批准的实现方向。坐标核对完成后，结合用户提出的新目标重新评估其中的设计、假设和代码映射；可以保留有价值的部分、局部改造或重写，不预设必须兼容旧方案，也不预设全部推倒。

更新时间：2026-11-02

## 1. 项目定义

本项目不是“AI 自动玩农场”，也不构建通用游戏视觉 Agent。

目标是：

> 用户与 ChatGPT 负责种植策略和活动选择；本地 Runner 只把已经确定的重复机械操作，压缩成类似按键精灵的固定流程。

Runner 面向两个固定环境：QQ 农场与微信农场。允许平台参数不同，不追求一套图像模板跨平台通用。

正常路径中，模型不参与鼠标级操作。

## 2. 设计原则

1. **固定流程优先于场景理解。** 游戏 UI 与操作流程本身是确定的，优先利用固定位置、相对坐标、已知页码关系和明确状态转换。
2. **视觉只做局部验票。** 只在已知 ROI 检查“是不是预期按钮 / 图标 / 土地模板 / 标志”，不分析整幅画面。
3. **状态来自 Runner 自己刚执行的动作。** Runner 成功种下四格作物后，直接记录对应四格已占用；不再从整田截图重新推断。
4. **正常路径只支持完整周期。** 不为“部分地已种、部分地未种”设计复杂恢复逻辑。
5. **异常立即 STOP。** 用户手动改地、进程中断、UI 与预期不符、模板不匹配时进入 DIRTY/UNKNOWN，等待重新同步。
6. **平台独立校准。** QQ 与微信可各自保存空地模板、锚点、按钮模板和偏移；共用流程算法，不强求共用图片。
7. **YAGNI。** 不为罕见异常构建通用视觉、事务恢复或语义证明系统。

## 3. 正常状态机

只保留以下主状态：

```text
EMPTY
  ↓
PLANTING
  ↓
GROWING
  ↓
MATURE
  ↓
HARVESTING
  ↓
EMPTY
```

额外异常态：

```text
DIRTY / UNKNOWN → STOP
```

DIRTY 不自动推理恢复，不尝试补洞，不猜“已经种了几格”。重新同步后再进入正常状态。

## 4. 画面与坐标模型

### 4.1 窗口

继续复用现有窗口发现、窗口恢复、window-local 坐标、Retina 映射和 CGEvent 安全门禁。

### 4.2 农田网格

4×6 土地仍使用固定仿射网格：

```text
center(u,v) = origin + u*u_step + v*v_step
```

QQ 与微信分别维护自己的：

- baseline window size
- origin / normalized origin
- u_step / v_step
- 土地等级布局
- 必要的小量校准偏移

正常运行不逐格找土地。

### 4.3 空地识别

每个平台维护自己的空地模板：

- purple-empty ROI
- gold-empty ROI
- 必要时其它土地等级模板

流程：

1. 找一个稳定农田/UI 锚点或确认窗口基线；
2. 算出 24 格固定位置；
3. 每格只检查预先选择的小 ROI；
4. ROI 匹配对应土地等级的空地模板，则该格为空；
5. 任何格既不像预期空地模板，也不满足当前阶段预期，则返回 UNKNOWN。

不再要求“理解整格作物语义”。

土地升级后重新采一次平台空地模板即可。

## 5. 种植流程

Planner 输入只包含：

- 平台
- 四格种子及 placement
- 普通种子及数量
- 成熟档 / 计划元数据

Runner 负责：

### 四格种植

```text
确认 EMPTY
→ 点击固定 placement 的 anchor
→ 打开 picker
→ 计算/验证目标 page + slot
→ 验证目标种子图标/数量
→ 选择种子
→ 检查固定 preview/确认 ROI
→ 确认
→ 将该 placement 对应4格写入本轮内存状态
```

不再要求从截图重新识别“四格到底落在哪四格”。

### 普通种植

```text
已知四格 placement 状态
→ 剩余空格数由计划直接计算
→ 打开任一合法普通空格
→ picker 定位目标
→ 验证图标/数量
→ 验证一键种植 ON
→ 选择种子
→ 局部/阶段结果检查
→ 进入 GROWING
```

不再要求每次执行前构建 24 格一般占用语义。

## 6. 收获流程

收获只利用游戏已经提供的交互标志：

1. 在固定/限定 ROI 检查四格作物“可摘”标志；
2. 若存在，按已知四格 placement 顺序点击对应可摘；
3. 再点击游戏的一键收获按钮；
4. 等待动画；
5. 使用空地 ROI 模板重新验证 24 格均恢复 EMPTY；
6. 通过则本轮结束；否则 DIRTY/UNKNOWN → STOP。

不需要识别每株作物种类。

## 7. Picker

以下现有能力继续保留：

- stable_order + quantities → visible_order
- 动态 page / slot 计算
- 页码 OCR
- 左右箭头固定 ROI
- 目标种子图标局部匹配
- 数量徽标读取
- picker y-shift 校准

Picker 是固定 UI 流程，不升级为通用视觉搜索。

## 8. 错误与恢复

保留以下类型的硬停止：

- WINDOW_NOT_FOUND
- WINDOW_SIZE_CHANGED
- WRONG_FRONTMOST_APP
- UNKNOWN_OVERLAY
- TARGET_SEED_NOT_FOUND
- SEED_SLOT_VERIFY_FAILED
- USER_INTERFERENCE
- DIRTY_FIELD
- UI_EXPECTATION_MISMATCH
- ACTION_UNCERTAIN

原则：

- 不确定就停；
- 不盲重试不可逆动作；
- 不自动换种；
- 不自动猜恢复点；
- 重新同步比复杂恢复系统优先。

## 9. 当前代码边界

V2 已完成旧路线清理。现役正常路径只依赖固定窗口/坐标、局部 ROI、Picker 验证与确定性事务。

现役核心包括：

- `window_registry.swift` / `open_qq_farm.swift` / `restore_wechat_main.swift`；
- `farm_capture.py` / `farm_geometry.py` / `farm_io.py`；
- `farm_click_batch.swift` / `farm_drag.swift`；
- `seed_order.py` / `farm_picker_vision.py` / `farm_text_ocr.swift` / `farm_plant_picker.py`；
- `farm_runner.py` / `farm_harvest*.py` / `farm_plant*.py`；
- `farm_qq_clean.py`：平台化的小 ROI `EMPTY / NOT_EMPTY / UNKNOWN` 检查器；
- `data/ui-layout.json`：窗口、4×6 网格、平台参数与 placement。

V1 的整田语义、三帧差分、场景重建与复杂 recovery 模块已经物理删除，不保留兼容壳。退役原因与删除清单见 `../../archive/2026-11-01-runner-v1-retired.md`；详细实验过程以 Git 历史为准。

## 10. 测试策略

测试重点是“固定 phase 能否按预期连续完成”，而不是增加通用视觉覆盖。

优先级：

1. 平台空地正例必须稳定返回 EMPTY；
2. 已种植/残留/遮罩负例不得误报 EMPTY；
3. picker page/slot/icon/count/one-key；
4. 四格 preview/confirm；
5. 普通 one-key 种植后目标格 occupied；
6. 收获后重新 EMPTY；
7. QQ / 微信各自完整跑通机械 phase；
8. 异常场景可靠 STOP。

测试数量不是里程碑。真实流程可连续执行并在异常时停止才是里程碑。

## 11. 进度与动态状态

本设计文件只维护稳定架构，不复制阶段进度。

- 当前实施顺序：`../../../IMPLEMENTATION_PLAN.md`
- 未完成事项：`../../../tasks/todo.md`
- 当前 QQ / 微信现场：`../../CURRENT.md`
- 阶段历史：`../../archive/README.md`

## 12. 成功标准

V2 第一阶段成功标准：

> 在固定 QQ / 微信农场环境中，本地 Runner 能从已知阶段连续完成机械操作；正常路径没有模型逐点击往返，阶段结果由小 ROI 验收，未知状态可靠 STOP。

Planner 只决定种植策略与时间窗口；Runner 不接管策略，不发展成通用游戏视觉 Agent。
