# 当前状态

更新时间：2026-10-31（M0 已通过；M1 QQ 受控单击联调取得真实收获/遮罩证据，完整本地 phase 未验收；M2 真实只读 preflight 可用、种植未验收；171项离线测试通过）

## Runner 当前开发检查点

- **2026-10-31 17:35–17:45 CST 首次 QQ 真实收获受控 I/O（不是 M1 验收）**：先读五份文档，本机时钟处于许可区；QQ Stage Manager 缩略态经既有 `open_qq_farm.swift` 恢复，603×1111、window_id=6951、pid=53086。真实 mature screenshot 明确出现三个大型成熟特殊作物的「可摘」星标，窗口局部坐标约 **(342,524)、(262,566)、(342,609)**，旧 `safe_special_2x2` 种植锚点中心过滤把这三个**全部错误丢弃**；安全种植 placement 不能当作实际收获占用/星标归属。原 CGEvent helper 首次受控试击在0点击处 `WINDOW_OCCLUDED`：Mac 的 Dock（layer20）和 Notification Center（layer21）提供 alpha=1 的全屏透传系统表面。已在 Swift 只针对**已识别全屏系统层且 Accessibility 命中进程 PID=农场 PID**时允许透传；其他遮挡继续 STOP。新增 `--preflight` 模式真实检查窗口/前台/遮挡/本机时钟但0点击，负例错误 PID 返回 `WINDOW_NOT_FOUND`；Swift 编译成功。随后在逐次独立新截图、成熟星标+作物外观局部证据、2秒新鲜度、窗口身份及 preflight 通过后，**人工受控测试**依次发送3个星标单击，真实截图分别确认大型作物消失/残株；第三颗触发「比熊棉花糖」图鉴获得弹窗，随后还触发等级提升106弹窗。两层经现场核实「点击空白处关闭」后受控处理。确认3个特殊星标已消失、手形 NCC≈0.914 后发送1次全局手形；真实截图显示田地视觉上已清空，但触发「超变图鉴升级18」遮罩。尝试1次有前置证据的空白处关闭后遮罩仍在，**未盲重试**。本次总共发送3星标+1手形+3次已核实遮罩空白点击，helper 均返回已发送事件；**不把已发送当成游戏成功，也不把遮罩下可见空田当24格独立 clean-field 终验**。没有种植、买萝卜、使用化肥；QQ 当前仍停留在图鉴升级18遮罩，QQ/微信库存保持 `inventory_dirty=true`，`run-next=RUNNER_NOT_READY`。本机临时证据 `/tmp/farm-qq-before-hand-20261031.png`、`/tmp/farm-qq-after-hand-20261031.png`（后者被遮罩覆盖，不可作 clean 参考）、`/tmp/farm-qq-clean-20261031.png`（仍有遮罩），**不保证重启后存在**。代码修正：M1 FSM 要求已验证星标集合与独立特殊占用集合完全一致，防止漏星后直接点手；vision 保留全部低阈值**诊断候选**，不再因种植锚点不匹配而静默丢失，始终不授权点击。**171项全量离线测试通过**。**距离 M1 实机验收缩短的步骤**：真实 CGEvent 的前台/遮挡硬阻塞已排除并完成3星标+1手形的受控真实操作，确认两类真实奖励遮罩；剩余是可复用的本地占用/遮罩/24格终验及单命令 phase，微信仍未进独立农场。下一轮先只读核对 QQ 遮罩，安全明确地消除后获取无罩空田现场样本；不要盲点或把本轮逐次手动联调当 Runner 验收。M2 仍以真实 picker/预览/24格 observer 和库存同步为直接阻塞。

- **2026-10-31 15:42 CST M2 真实只读种植接口已接 QQ 实机（未验收种植）**：新增 `scripts/farm_plant_live.py`，复用已验证的 Mac 本地禁区门禁、窗口 registry→裁剪截图→窗口身份复核，生成带真实 `capture_id`/单调时间/窗口身份的 `OrdinaryPlantView`，并为 picker 提供独立新截图 `PickerView` 接口；尚无可信页面/图标/数量识别，`overlay=unknown`、`field_cells=None`、`preview_cells=None`、`one_key_planting=None`、picker 页码/图标/数量均未知，绝不把截图或静态24格几何提升为种植授权。预留复用 Swift CGEvent JSON 的安全传输层，但目前所有动作方法均结构化 STOP，`execute=True` 也不能触发点击。`farm_runner.py preflight-plant` 是只读入口。实机 QQ 初次探测因 Stage Manager 缩略态返回 `WINDOW_SIZE_CHANGED`；本机 15:42 CST（距16:00禁区有余量）经 `swift scripts/open_qq_farm.swift` 恢复已存在农场后，真实预检获得 603×1111、window_id=6951、capture_id，正确返回 `PLANT_OVERLAY`、0点击、0逐击 LLM 往返。新增6项隔离回归，**全量169项测试通过**，py_compile、dry-run通过，`run-next=RUNNER_NOT_READY`。没有收获、购买、种植或改变库存；QQ/微信 `inventory_dirty=true`。**距离 M2 验收缩短的步骤**：真实 QQ 窗口→种植视图的本地 I/O 通道已可调用并验证 STOP；剩余必须实机校准24格占用/遮罩/预览、picker页码/图标/数量、点击坐标并同步库存，再进行受控事务；M1 星标/clean-field 和微信独立农场仍待完成。下一轮优先真实局部 UI 识别与受控阶段验收，不再增加纯离线恢复机制。


- **2026-10-31 08:33 CST 离线 M2 持久化恢复检查点（实机禁区）**：本机时钟确认 08:33 CST，处于 08:00–09:00 禁止触碰 QQ/微信农场/前台的时段；本轮没有打开/切换农场窗口或发送鼠标键盘事件。为补齐真实种植前必须具备的崩溃恢复事实，新增 `scripts/farm_plant_recovery.py`：每个 plan/cycle/platform 独占创建 journal；每笔四格/普通事务在任何 UI 调用前以 fsync+原子写入 `in_flight`，独立终验成功后写 `checkpointed` 及已确认库存，全部成功后只标记 `phase_verified_uncommitted`，**不冒充 farm-state 已落盘**。任何旧 journal（包括崩溃、已完成但未与 farm-state 对账）均阻止自动重跑，须人工/可信现场 reconcile。`farm_plant_cycle.py` 新增 preaction callback，预写失败在零新动作前 STOP，部分动作保留已确认历史而不重放；包装入口 `run_plant_phase_with_recovery` 仍要求 `inventory_verified=True`，当前真实双平台 dirty，因此不能运行真实种植。新增7项持久化/崩溃/漂移/部分事务回归，**全量163项测试通过**，py_compile、dry-run 通过，`run-next` 继续 `RUNNER_NOT_READY`。这消除了 M2 真机接线前的一个必要安全阻塞，但**真实 picker/preview/24格 observer 与 CGEvent 仍未接入**；M1 真实星标/占用/遮罩/clean-field 校准也仍未完成。下一轮允许时段优先实机校准并接真实 UI，而非再扩展离线恢复功能。

- **2026-10-31 07:46 CST 微信主窗口恢复实机闭环（非农场）**：在 QQ 农场前台时，原 `restore_wechat_main.swift` 因 Stage Manager 微信缩略窗被遮挡返回 `WECHAT_TILE_OCCLUDED`。先只读确认唯一微信窗口身份及 owner PID；已修改 helper：缩略窗被遮挡时不点击其坐标，而通过 `NSRunningApplication(processIdentifier: tile.pid).activate(options: [])` 仅激活已确认的微信进程，再检查唯一完整微信主窗口。Swift typecheck 通过，真实从 QQ 前台触发返回 `WECHAT_MAIN_RESTORED_BY_PID`；此前 AppleScript 激活也已单次验证。**微信目前仅回到聊天主窗口，尚未按“发现→游戏→最近玩过”进入独立农场；没有农场点击、收获、种植。** 该恢复路径保留本地禁区门禁、唯一窗口身份和失败 STOP，不能把主窗口恢复算作 M1 验收。

- **2026-10-31 07:35–07:42 CST 本轮检查点（M2 首次单调用完整种植阶段离线贯通）**：Mac 本地时间允许操作，先从 Stage Manager 恢复 QQ 农场，`preflight-harvest --registry /tmp/farm_window_registry` 真实取得 603×1111 窗口、手形 score 0.913922，仍因 `UNKNOWN_OVERLAY` 安全返回0点击。新鲜现场截图仅保存于 Mac `/tmp/farm-qq-current.png`（未提交）。对同一张成熟田截图使用**只读**旧星标定位器阈值0.50，可见三个低置信候选 (262,566; 0.660)、(344,606; 0.614)、(342,525.5; 0.539)，原0.70阈值仍为0；候选与配置中2×2中心的14px门限不能建立可靠对应，**绝不把降阈值当点击授权**。没有任何游戏点击、收获、购买、种植。
- **M2 离线集成实质推进**：新增 `scripts/farm_plant_cycle.py`，一次调用按 Planner 原计划连续执行所有四格事务→普通一键事务，复用 M0 `preflight_cycle` 做整轮24格布局与总库存验证；每颗四格确认后更新**内存**库存，使特殊种子用尽后的普通种子 page/slot 自动左移；每笔已独立验收事务可调用注入式 `checkpoint` 保存恢复事实，失败返回已确认交易及数量，不盲重试、不擅自落盘；未验证库存直接 `INVENTORY_DIRTY`。独立验证结果还必须匹配指定平台、种子、状态和精确库存扣减，避免虚假成功污染后续事务。新增7项组合测试，**全量156项通过**，py_compile 和 M0 dry-run 通过。**尚未接 M2 真实 UI adapter，未获得任何 M1/M2 实机闭环验收，run-next 仍禁止执行。** 下一步应优先真实星标/2×2占用/遮罩/24格终验校准；M2 需要真实 picker/field/preview observer 与 CGEvent 接线、可信库存同步及可持久化恢复日志。正常 phase 仍零逐击模型往返.

- **2026-10-31 06:45 CST 最新检查点（M1 真实 observation adapter 首次联通，尚未收获）**：`scripts/farm_harvest_live.py` 已接 window registry→真实截图→同一窗口复核→本地手形/候选星标探测→`HarvestObservation`→FSM 只读预检；`farm_runner.py preflight-harvest --platform qq --registry /tmp/farm_window_registry` 真实返回 QQ window_id=6951、hand score=0.913922、`UNKNOWN_OVERLAY`、0点击、0模型逐击往返。微信只读预检返回 `WINDOW_NOT_FOUND`（独立农场未显示）。QQ 真实画面有大量成熟“可摘”，当前星标检测候选仍为0；2×2几何不能独立证明成熟特殊占用。Adapter 明确 `overlay=unknown`、`calibration_verified=false`、`occupied_special=None`、`empty_cells=None`，`execute=True` 也不能绕过门禁，严禁把0星标误当无特殊作物。已补 Mac 本地禁用时段及前2分钟 Python 门禁（Swift 逐击门禁保留）；新增10项隔离回归（含2秒预点击截图新鲜度与失败复拍清除旧授权），全量**149项测试通过**，py_compile、dry-run通过，`run-next=RUNNER_NOT_READY`。没有真实点击/购买/收获/种植。下一步：基于实时 QQ 场景校准特殊占用/星标与遮罩、24格 clean-field；微信恢复农场后同样验证；只有校准完成才受控执行 M1 点击。**M1/M2 均未实机验收。**

- **2026-10-31 04:41 CST M2 普通一键种植离线检查点**：新增 `farm_plant_ordinary.py`，复用 M2 picker 的 page/slot、图标与数量校验，严格要求当前一键种植已验证开启、24格占用完整可读、空格数量恰好等于本次 Planner 指定普通种植数量；选种一次→本地等待→新截图验证24格全占用，才返回库存扣减副本。任何漂移、部分填充、未知弹窗、截图过期或窗口变化均 STOP，不重试、不自动补洞。新增16项测试，**全量139项通过**，py_compile/dry-run 通过，`run-next=RUNNER_NOT_READY`；未接真实 observation/CGEvent，未进行真实点击。复看 QQ 成熟田实拍仍无法独立证明四格星标归属，M1 仍需真实校准。下一步优先接真实 I/O 与最小可验收收获链路，不再单独扩展离线统计。Mac 本地禁区保持有效。

- **2026-10-31 本轮实测/离线检查点**：本机 03:41 CST 为许可时段。编译只读 `window_registry.swift` 到 `/tmp/farm_window_registry` 后，发现 QQ Stage Manager 缩略窗 46×128 会被 registry 识别为同名窗口，`probe-harvest` 因尺寸拒绝（`WINDOW_SIZE_CHANGED`），并非农场程序丢失；既有 `open_qq_farm.swift` 恢复完整窗口后，只读探测成功（603×1111、手形 score 0.9139）。旧 QQ 成熟画面确有大量“可摘”，旧模板仍识别为零，真实四格占用/星标偏移未知，不允许点击。**M2 新增 `farm_plant_special.py` 离线四格事务**：目标四格空地→picker 已验证→预览覆盖精确四格→二次确认→24格独立终验→成功后仅返回扣减库存副本；失败结构化 STOP、禁止盲重试。新增17项测试，**全量123项通过**；未进行任何收获、种植或种子购买，`run-next` 仍拒绝真实执行。下一步 M1 真实星标与占用标定/clean-field 验收；M2 事务接真实 observation/CGEvent adapter，且在 M1 安全闭环前仅受控试种低级萝卜作为测试样本。


- **M0 离线验收已通过**：`scripts/seed_order.py`、`scripts/farm_runner.py dry-run`、`data/seed-order.json`、`data/farm-state.json`、RUN_PLAN schema/样例和 11 项单元测试均已落地；详情见 `runner-m0-verification.md`。
- **当前安全状态**：QQ/微信 `inventory_dirty=true`（历史快照非实时），`run-next` 返回 `RUNNER_NOT_READY`，尚未触发游戏点击。历史零库存候选的稳定插入点未验证，不会猜测。
- **M1 已推进但未验收**：只读 Swift 窗口注册、截图裁剪、window-local/Retina 坐标、进程内视觉和预编译批量 CGEvent helper 均已离线实现；四格可摘候选按已知 2×2 中心过滤并拒绝重复/无效候选。第7轮回归发现菱形布局单格中心距四格中心仅约21px，原22px门限误收单格星标，已收紧为**临时14px**并补充测试；真实星标偏移与四格占用未校准，绝不可据此点击。**全量94项单测通过，3个Swift程序typecheck通过**。`farm_capture.py` 已为真实新截图生成唯一 capture_id 和单调时间戳，`farm_harvest.py` 在点击后要求不同且更晚的截图来源，否则结构化 STOP；等待或复拍失败也停止，不重试。新增 `scripts/farm_harvest.py`：离线 mock 的本地单批收获状态机（星标批量→手形一次→等待3秒→24格空地终验），严格拒绝未知/未处理遮罩、未校准占地、部分批量结果与终验缺证据；**尚未接真实视觉或点击**。历史截图离线回放发现网格与静态基线存在平移（QQ约 -9/+18、微信约 -60/+1 logical px），新增 `farm_field.py` 紫地颜色分割与完整格点匹配，只返回只读 `field_alignment`，遮挡/成熟时拒绝推断；不能将平移诊断当作点击授权，成熟田对齐、星标/占地及 24 格空地分类仍待校准。此前 QQ/微信只读探测均 `WINDOW_NOT_FOUND`，没有真机截图或点击。新增加的 CGEvent helper 结构化 STOP 保留已发送点击数（非游戏成功数），`farm_io.parse_click_batch_result` 拒绝把验证模式当作执行，`farm_harvest` 不再丢弃已知部分计数；仅离线验收，尚未接真实 I/O。`run-next` 继续返回 `RUNNER_NOT_READY`。`farm_clean_field.py` + `farm_clean_replay.py` 只读比较独立对齐后的24格 RGB patch：两张真实 QQ 空田图各格原始 RGB 平均差异仍约20.7–33.5。本轮新增跨24格的每通道中位数全局色偏校正、校正后均值/中位数/P90及异常通道比例。真实 QQ 两张空田对比得出全局偏移 [0,0,0]，校正后均值不变，24格中位差0–9、P90约102.8–129、超过40的通道约15.5%–27.4%，提示差异并非简单全局色偏；**不能由此推断作物占用或空田**。仍只返回 `diagnostic_only`、`empty_cells=null`、`can_authorize_clicks=false`，不得接入点击许可。新增三处背景 ROI 只读配准后，已能在历史微信满田/四格占用截图紫地不可见时估计**参考图相对位移**，并回放真实负例；满田均值差55.43、部分四格占用20.06、另一张空田26.79，整体均值不可分。当前场景配准不等于独立地块校准，不能授权点击。本轮继续补充逐格 RGB 联合一致性（每个像素三个通道同时落在12/24容差内的比例），历史 QQ 双空田比例0.4188–0.7806，微信满田占用0–0.0513，部分四格占用0–1；跨平台及边缘占用比例仍交叉，**不得设置通用阈值或授权点击**。新增回归验证两张像素完全相同但窗口元数据宽高相差1 logical point的参考/当前图：旧 ROI 裁剪误复用当前图比例，QQ/微信×1x/2x 均产生15.0虚假RGB均值差；现已修复为每张图独立像素比例，回归差异归零，仍只读。下一步 M1：同平台独立 clean/occupied 证据、遮罩/星标与四格实机校准 → 本地收获状态机接线 → 受控联调；M2尚未开始。当前 `python` 缺 scipy，测试请用 `python3`。

- **最新 M1 安全检查点**：`run_harvest()` 终验截图必须在 CGEvent 批次结束、3 秒动画等待返回后才拍摄；新 ID 但拍摄时间早于等待完成仍返回 `HARVEST_STALE_POSTCONDITION`，时钟/复拍失败返回 `HARVEST_POSTCONDITION_UNAVAILABLE`，保留已发送点击数且不重试。新增2项离线回归，全量94项通过。临时编译只读窗口注册后 QQ/微信仍 `WINDOW_NOT_FOUND`；没有真机点击，`run-next` 保持禁用。

## 当前现场

- **2026-10-31 01:37–01:44 CST 真机只读/窗口恢复**：QQ 已通过 `swift scripts/open_qq_farm.swift` 打开独立农场；真实只读 probe：603×1111、window_id=6951、pid=53086、bounds=(979,101)，手形 NCC=0.9139。现场大量“可摘”星标，但旧模板 `pickables=[]`，成熟遮挡导致 `FIELD_ALIGNMENT_UNAVAILABLE`，**未收获、未购买、未种植，不得据此直接点手形**。现场截图仅临时存于 Mac `/tmp/farm-qq-live.png`。微信 Stage Manager 主窗口由新 `scripts/restore_wechat_main.swift` 成功恢复，registry 证实主窗口 995×974、bounds=(250,33)；当前仍在聊天页，尚未打开农场独立窗口。下轮需重新探测，不能复用本次窗口ID。
- **M2 picker 离线已启动**：`scripts/farm_plant_picker.py` 实现先观测当前页→有界批量翻页→再验页码、目标 icon/数量徽标；未知或漂移结构化 STOP，不点击目标、不扣库存。新增12项测试，全量106项通过，4个 Swift helper typecheck 通过。QQ 入口、CGEvent 批量 helper 与微信主窗口恢复均新增本机禁用时段保护；微信缩略窗恢复还会拒绝遮挡。下轮 QQ 优先真实星标/四格占用校准，微信按状态式入口恢复农场；若仍阻塞则推进 M2 本地 UI adapter 或四格事务。

- **2026-10-31 用户授权更新**：可主动恢复 QQ/微信农场做短暂受控实机验证（当前有未收获作物），不再仅因未人工开窗就长期离线空转。若需快速成熟测试样本：进入**游戏内普通种子商店、列表向上翻至最顶端，选择最低等级「萝卜」种子**；先现场确认所需游戏货币、价格、成熟时长和数量，仅少量购买/试种，禁止付费/高级资源消费、清理已有未成熟作物。QQ 未成熟可改微信、微信未成熟可改 QQ，记录播种和成熟等待；这类测试准备不能视为 M2 完成。**该 Mac 本地时间禁用任何可能影响农场/其他自动化前台的真机操作：08:00–09:00，12:00–13:00，14:00–14:05，16:00–17:00，20:00–21:00，00:00–01:00**；进入禁区前也应停在安全点。此时只做离线开发。执行纠偏：优先恢复窗口、接真实观察和单次收获链路；现场不具备条件则推进 M2 离线模块，不再无限精修视觉统计。

- **2026-10-29 实际现场**：QQ 第1轮已完成种植（3颗四格 + 12格普通），QQ 分享/商店福利/好友互动/每日任务已完成。微信第1轮已完成种植（2颗四格 + 16格普通）；后续用户已手动完成微信每日任务与商店每日福利，因此今天这两项**禁止重复执行**。
- **执行纠错**：曾错误进入 QQ“更多功能”而非使用既定直接入口。已改为固定调用 `scripts/open_qq_farm.swift`：脚本自行定位窗口并使用 `data/ui-layout.json` 的主窗口相对坐标 `(31,307)`，不再让 Agent 临场识别入口。四格种植预览随最初点击的土地确定；曾错误点到紫晶地，不能归因于游戏默认位置。继续种植前按实时画面核对目标 2×2 与点击落点。

- 用户已手动补齐上一轮异常留下的空地；上一轮 QQ / 微信种植结果存在混合成熟时间，不再作为后续标准路线样本。
- 当前下一步不再继续用 Agent 单击级方式实测；已启用每小时“检查点式自恢复续跑”，按根目录 `IMPLEMENTATION_PLAN.md` 从最近检查点持续推进 Runner 重构。默认由当前助手直接使用 CodexPro 本地工具完成，不默认调用 Codex CLI。
- 新执行架构：**Planner 只提供未来种植策略（种子名/数量/成熟档/四格 placement），Runner 根据 `stable_order + quantities` 动态计算当前 picker 位置并本地执行；异常才回 Agent。** 当前首要假设是“刚获取种子时可能临时插入，重新进入后恢复稳定顺序”，需由 Codex 真机验证。

## 收获规则已收敛

- 正常收获只分一个条件：是否存在属于 4 格植物的“可摘”星星。
- 无四格可摘：手形一键按钮一次 → 等约3秒 → 空地终验。
- 有四格可摘：一次探测全部候选 → 只保留落在已知 2×2 四格区域中心附近的星星 → 连续逐个点击 → 手形一键按钮一次 → 等约3秒 → 空地终验。
- 2026-10-28 实测后，混合成熟画面 QQ 可准确识别 3 个四格“可摘”、微信 2 个；未成熟种满画面均返回 0。

## 种植规则的当前正确口径

- 4 格种子必须逐颗完成：打开目标 2×2 → 选种 → 出现 2×2 预览 → 明确二次确认 → 验收真正落地。
- **预览未确认前禁止点击其它土地。** 上一轮 QQ 的主要错误就是把预览当成已经种下，随后继续点其它土地，导致预览位置被改变/取消。
- 普通一键种植后必须验收预期空地全部占用。上一轮曾出现 QQ 留 1 格紫地、微信紫地全空，当前仍按 bug 保留，不能推导为土地等级限制。

## 2026-10-28 实时仓库基线

完整快照：../data/inventory-live-2026-10-28.json

关键结论：

- **仓库 → 种子页的 row-major 当前顺序，就是土地 picker 当前顺序；仓库每行 5 个正好对应 picker 一页。**
- QQ 仓库第一行 4 / 4 / 24 / 5 / 16 与 picker 第一页完全一致。
- 微信仓库第一行 8 / 7 / 10 / 8 / 3 与 picker 第一页完全一致。
- 这一实测继续作为当前 picker 顺序模型的重要证据，但新 Runner 不再把某次仓库快照里的 page/slot 当长期真值。
- 新口径：维护 `stable_order + mutable quantities`，visible_order 每次由 stable_order 过滤当前数量>0得到。成功消费到0只改数量，不改 stable_order。已知种子0→positive时预期在下一次重新进入后回到稳定位置；若真机验证否定这个假设，再升级到 order_revision 模型。

本次补齐的新种子资料：

- **天山红枫种子**：QQ 30 / 微信 30；12小时、1季；QQ 4005经验/季，微信4414经验/季。
- **森野白桃种子**：QQ 64 / 微信 12；12小时、1季；QQ 3433经验/季，微信3784经验/季。
- **森野甜橙种子**：QQ 108 / 微信 108；12小时、1季；QQ 3433经验/季，微信3784经验/季。

## 旧 3 轮计划（仅历史参考）

`../data/next-cycle-plan.json` 是 2026-10-28 的旧执行方案。**不要再按其中写死的 page/slot 作为新 Runner 正常路径。** 新 Runner 的策略输入未来只写种子名/数量/成熟档/placement；page/slot 由当前 visible_order 动态计算。

### QQ

固定四格种子：**泡泡棉花糖**，第1页第3个，每轮 3 颗，占 gold_a / gold_b / gold_c 三个纯金地 2×2。

- 第1轮：泡泡棉花糖 ×3 + 天山红枫 ×12（红枫第4页第1个）
- 第2轮：泡泡棉花糖 ×3 + 天山红枫 ×12
- 第3轮：泡泡棉花糖 ×3 + 紫薇 ×12（紫薇第3页第3个）
- 3轮后：泡泡棉花糖 24→15；天山红枫 30→6；紫薇 76→64。
- 预计三轮经验：**306,471**。

### 微信

固定四格种子：**星语铃花**，第1页第3个，每轮 2 颗，占 purple_a / purple_b 两个完整紫晶 2×2。

- 第1轮：星语铃花 ×2 + 天山红枫 ×16（红枫第2页第5个）
- 第2轮：星语铃花 ×2 + 黄金果 ×16（黄金果第2页第1个）
- 第3轮：星语铃花 ×2 + 黄金果 ×16
- 3轮后：星语铃花 10→4；天山红枫 30→14；黄金果 94→62。
- 预计三轮经验：**330,052**。

旧方案刻意保持库存 >0 只是为了避免位置左移；**该限制已废弃**。新 Runner 必须正确处理库存归零后的动态左移，不得把“保留1个库存”当作规划前提。

## 下一次进入工作区

1. 按 SKILL.md 读取 Todo / INDEX / CURRENT / gameplay-rules。
2. 当前真实现场：QQ 与微信都已完成 2026-10-29 那一轮种植；QQ 当日日常已完成，微信每日任务与商城福利由用户后续手动完成。接手重点是 Runner 开发，不是继续旧式实时遥控。
3. M0 已完成离线验收。M1 当前 92 项离线测试通过，含四格候选几何过滤、收获状态机、点击后新截图来源/时序门禁与历史空田网格平移诊断；真实 QQ/微信农场窗口仍待校准，未进行真实点击。下次继续真实/历史截图回放、四格占用、遮罩与 clean-field 视觉验收，再接真实 I/O；默认使用 CodexPro。种子刚获取/重进顺序实验仍待真机验证，尚未证实。
4. M0 通过后做 M1/M2：本地连续收获与种植；四格仍保持 `预览→确认→落地` 事务，普通一键种植做 24 格阶段终验。
5. 在 M2 实机跑通前，不继续用 ChatGPT/CodexPro 单击级遥控农场，也不做定时化。

永久规则见 gameplay-rules.md；种子资料见 seed-catalog.md / ../data/seed-catalog.json；未完成事项见 ../tasks/todo.md。
