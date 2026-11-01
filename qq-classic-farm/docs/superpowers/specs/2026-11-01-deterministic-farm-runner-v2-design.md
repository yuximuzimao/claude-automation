# 农场 Deterministic Runner V2 设计

更新时间：2026-11-01

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

## 9. 旧实现处置

### 保留并继续使用

- `window_registry.swift`
- `open_qq_farm.swift`
- `restore_wechat_main.swift`
- `farm_capture.py`
- `farm_geometry.py`
- `farm_io.py`
- `farm_click_batch.swift`
- `farm_drag.swift`
- `seed_order.py`
- `farm_picker_vision.py`
- `farm_text_ocr.swift`
- `farm_plant_picker.py`
- 已验证的 seed icons / UI anchors
- `data/ui-layout.json` 的固定网格与 placement 数据

### 重写/简化后继续使用

- `farm_runner.py`
- `farm_harvest.py`
- `farm_harvest_live.py`
- `farm_plant_cycle.py`
- `farm_plant_live.py`
- `farm_plant_special.py`
- `farm_plant_ordinary.py`
- `farm_qq_clean.py`：改造成平台化“小 ROI 空地模板检查器”，不再承担完整语义证明

### 降级为诊断/历史工具，退出正常 Runner

- `farm_field.py`
- `farm_scene.py`
- `farm_clean_field.py`
- `farm_clean_replay.py`
- `farm_field_delta.py`
- `farm_field_postcondition.py`
- `farm_qq_landing.py`

这些代码可暂时保留用于回放和校准，但不得成为 V2 正常流程的点击前置条件。实现稳定后再决定物理删除。

### 计划移除复杂恢复职责

- `farm_plant_recovery.py`

V2 不做“崩溃后自动推断种到第几颗并继续”。异常统一进入 DIRTY/STOP。若该文件仍有 confirmed-only 原子写盘能力可复用，则只提取最小写盘函数，其余事务恢复逻辑删除。

## 10. 测试策略

测试重点从“覆盖更多视觉边缘场景”改为“固定流程是否按预期运行”。

优先级：

1. 空地模板：QQ 当前土地 24/24 正例；
2. 已种植样本必须让关键 ROI 退出 empty；
3. 收获后再次恢复 empty；
4. picker page/slot/icon/count；
5. 四格 preview/confirm；
6. 一键 ON；
7. 一个完整 QQ 周期；
8. 参数化到微信；
9. QQ/微信各连续完整跑一轮。

测试数量不是里程碑。真实完整流程可运行才是里程碑。

## 11. 开发顺序

### V2-0 清理

- 让本文件成为新方案定义；
- 重写 IMPLEMENTATION_PLAN / CURRENT / todo 的现役部分；
- 旧研究检查点移入历史，不再作为启动必读上下文；
- 标记旧视觉研究模块为 diagnostic-only。

### V2-1 QQ 空田基准

当前用户确认 QQ 为全空田。

需要建立：

- QQ 当前土地版本的稳定锚点；
- purple-empty / gold-empty 小 ROI；
- 24 格固定位置；
- `check-empty qq` → EMPTY / NOT_EMPTY / UNKNOWN。

### V2-2 QQ 种植

复用现有 picker 和 CGEvent 能力，跑通：

```text
EMPTY → 四格种植 → 普通一键种植 → GROWING
```

### V2-3 QQ 收获

成熟后跑通：

```text
MATURE → 四格可摘 → 一键收获 → EMPTY
```

形成 QQ 第一个真正完整闭环。

### V2-4 微信参数化

微信独立采：

- 空地模板；
- 网格起点/偏移；
- 必要按钮模板。

复用同一状态机。

### V2-5 Planner / 库存

双平台机械闭环稳定后，再接每天3轮种植规划和库存更新。

### V2-6 定时化

只有 Runner 已经稳定后，定时任务才负责“调用 Runner”，不再承担持续自主研发。

## 12. 用户配合样本

默认由自动化自行制造样本。只有无法低成本制造时才请求用户。

近期可能需要的用户配合最多只有：

1. 暂时保持 QQ 当前空田，直到 V2-1 空地模板完成；
2. 如微信当前成熟，可保持现场供首次收获→空田基准；
3. 若四格 preview 样本不足，按明确指令只制造一次指定四格种植状态。

不会要求用户陪同反复截图或不断试错。

## 13. 成功标准

V2 第一阶段成功不是“更多测试通过”，而是：

> 在固定 QQ 农场环境中，一个本地命令能从已知 EMPTY 状态按计划连续种植；成熟后另一个本地阶段能连续收获并重新验证 EMPTY，正常路径无逐点击模型往返。

QQ 完成后再复制到微信。
