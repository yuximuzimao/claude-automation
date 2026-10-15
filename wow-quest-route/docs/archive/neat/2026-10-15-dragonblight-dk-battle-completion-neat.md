# 2026-10-15 第二组DK龙骨荒野收尾 / 幽暗城之战闭合 NEAT

## 本阶段状态

第二组兽人双手鲜血DK×5已完成龙骨荒野路线尾段的《幽暗城之战》，任务完成时间为2026-10-15 04:15。完成后已经按正式路线使用炉石回到阿格玛之锤；本轮NEAT结束时的唯一恢复点是：**阿格玛之锤 → 大法师艾萨斯·夺日者的影像 → 12791《魔法王国达拉然》任务传送 → 达拉然**。

当前运行状态仍只以`docs/verified-routes/CURRENT.md`为准；本NEAT保存本阶段已经闭合的实跑事实、路线修正、Timing口径和恢复机制，不作为下一次游戏执行入口。

## 本轮Fivebox闭合

本阶段补齐并回写龙骨荒野最后一批机制事实：

- `12017《鱼钩上的肉》`：用户实跑确认共享。
- `13267《幽暗城之战》`：属于全程跟随萨尔/希尔瓦娜斯推进的脚本事件，不需要额外设计fivebox专项实测，`fivebox.status = not_applicable`。
- 连同此前本轮已经确认的《翡翠龙泪》《强大的猛犸人》《奥雷托斯的羽毛》《暴虐的酋长》《毫不留情》《先发制人》《毁灭的力量》《黑暗的骚动》等事实，龙骨荒野`tasks/fivebox-pending.md`现为0。

这意味着龙骨荒野Fivebox机制清单已经自然实跑闭合，不再为该地图保留专项补测任务。

## 《幽暗城之战》相位异常与已验证恢复方式

本次现场出现了一个可复用的相位异常：幽暗城外入口长期只有沃金和希尔瓦娜斯，萨尔缺失。

实跑结果明确区分了无效与有效处理：

- 无效：站在原地通过时间线NPC切回正常时间线，再立刻切回战役相位；现场没有变化。
- 有效：**切回正常时间线 → 真正离开幽暗城/提瑞斯法区域 → 返回幽暗城外 → 再通过时间线NPC切回战役相位**；本次执行后萨尔重新出现。
- 不需要放弃任务，也不要在萨尔缺失时自行进入幽暗城。

该恢复方式已经写入`13267` Task Card的guide / presentation，并以2026-10-15用户现场实跑作为证据。以后若复现同样状态，优先直接使用这一恢复流程，不再重复原地等待或原地来回切相位。

## 《幽暗城之战》Timing口径

本轮最终采用的唯一有效口径是脚本事件本体：

- 03:34:45：会话系统时间戳对应用户发送“完整离区重进一次有用，萨尔出现了”；用户随后明确确认发送这条消息时就是点击萨尔“准备好了”的时刻。
- 04:15：用户确认《幽暗城之战》完成。
- 因此脚本事件实测约**40分15秒（40.25分钟）**。
- 启动后约4分04秒时，用户曾反馈萨尔仍未移动；本次最终仍正常完成，因此开场存在数分钟脚本等待，不应过早判断为再次卡死。

用户明确要求废弃此前“02:24到达入口 → 04:15完成”的111分钟口径。该时间段包含等待萨尔、相位排查、原地切换失败与离区恢复，不再保存为dirty timing样本，也不再计入任何累计或后续估时。

按当前保留口径：第二组DK到《幽暗城之战》入口的既有四段记录合计约13小时35分44秒（117.733 + 305 + 182 + 211分钟）；再追加本次40分15秒脚本事件后，**保留的实跑统计片段合计约14小时15分59秒**。这里不宣称为连续整图墙钟或clean baseline；被用户明确抛弃的故障排查窗口完全不参与计算。

## 龙骨路线尾段正式化

`dragonblight-fivebox`现为version 3。正式尾段保持一条完整玩家动作链：

`《黑暗的骚动》 → 库卡隆先锋营地 → 系统飞行战歌要塞 → 奥格瑞玛任务传送 → 幽暗城外 → 《幽暗城之战》 → 炉石阿格玛之锤 → 艾萨斯影像 → 12791任务传送达拉然`

其中《幽暗城之战》依旧属于同一个龙骨尾段，而不是另开一张地图；奥格瑞玛/幽暗城动作都显式展示。当前实跑已经走完到“炉石阿格玛之锤”，最后的12791传送达拉然留到下一次继续。

## 当前恢复点

本轮停止时：

- 《幽暗城之战》已完成；
- 已经炉石回到阿格玛之锤；
- 下次第一动作不是再处理幽暗城，而是直接找**大法师艾萨斯·夺日者的影像**；
- 使用仍保留的`12791《魔法王国达拉然》`任务传送进入达拉然；
- 进入达拉然后再继续后续路线。

## NEAT审计边界

本次审查当前活跃知识区及本轮实际改动：项目入口、CURRENT/Todo、现行rules、Task Card、Fivebox Observation、Timing Observation、Dragonblight Route Profile/Program、pending清单、Route Lifecycle派生产物和当前索引。历史NEAT保持只读，不反向覆盖当前真值。

`docs/analysis/`现存47份日期化分析仍按2026-10-08 NEAT已确认的边界处理：它们不在SKILL/INDEX默认读取链，但仍有专项脚本输出路径和Task Card `source_ref`引用，故本轮不做盲目搬移；其内容只作形成过程证据，不能覆盖Task Card、Route Profile、CURRENT或rules真值。

本轮没有创建worktree；也不处理工作区其它项目的未提交改动。用户只要求NEAT归档，**不自动commit/push**。

## 验证

- 5个本轮关键JSON真源/观察文件全部解析通过：Timing Observation、Fivebox Observation、13267 Task Card、Dragonblight Route Profile、Route Program。
- `build_route_timing.py dragonblight-fivebox`：`pass`。本次40分15秒Observation本身因尚未绑定稳定action_id范围/现役Timing规则，明确保持`calibration_eligible=false`，不让Stage 7自动套用；它仍是有效的13267单任务脚本事件实测参考。
- `update_program_member_timing.py horde-fivebox-full-clear dragonblight-fivebox`：Program级仍为`requirements`，原因来自整套Program既有的跨Profile边界/交通Timing未闭合项；不把这些更大范围问题伪装成本次龙骨实测失败。Dragonblight→Dalaran边界也暂不因当前尚未实际进入达拉然而补造handoff，等下一次真实到达后再闭合。
- Dragonblight Display：`pass`；Publisher：`pass / publishable=true`；玩家资源渲染：`pass / publishable=true`。
- 相关契约/生命周期测试共**167 passed**，覆盖Task Card/Profile schema、Task Presentation、Program、Replay、Movement、Service Context、Timing、XP、Economy、Display、Publisher、Player Assets和Rule Routing；最终清理13267玩家备注中的形成过程措辞后，又复跑Presentation/Display/Publisher/Assets等**50 passed**，且生成的龙骨玩家页已无“本次实跑”过程词泄漏。
- 用户明确废弃的02:24→04:15 111分钟口径已从Timing Observation真源删除；当前活跃文档不再把它作为dirty样本或累计依据。
