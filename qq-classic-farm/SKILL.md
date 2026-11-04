# QQ经典农场辅助 SKILL.md

## DO FIRST

1. 当前阶段是坐标制作与用户逐点核对：先读 docs/CURRENT.md 和 tasks/todo.md，再打开工作区根目录 _sandbox/farm-coordinate-review.html。
2. 读 docs/INDEX.md，按当前场景只加载所需规则和资料。
3. 真机观察前读 docs/CURRENT.md；有游戏操作时再读 docs/gameplay-rules.md。
4. 选种/库存/成熟时间问题：读 docs/seed-catalog.md 与 data/seed-catalog.json。
5. IMPLEMENTATION_PLAN.md 与 Runner V2 设计属于此前自动化路线的旧材料，当前暂停，不据此启动开发。坐标核对完成后，需结合用户提出的新目标，对项目文档、规则、配置、计划、脚本和测试整体重新盘点；届时再决定旧材料哪些保留、改造、删除或重写。
6. 历史只在考古或 NEAT 收尾时进入 docs/archive/；历史不得驱动当前坐标核对。

## 当前阶段

当前只做 QQ / 微信农场 UI 坐标制作与逐点核对，尚未进入自动化实施阶段。此前助手设计/实现的自动化方案已被用户推翻。后续脚本是否复用、局部改造或重写，等用户逐步确认坐标和需求后再决定。

工作方式：
- 用户逐步指挥页面、场景和点位；助手负责截图/标注/坐标整理与文档同步。
- 唯一坐标核对页是工作区根目录 _sandbox/farm-coordinate-review.html，所有场景共用。
- 候选点只有用户明确确认后才成为正式点位。
- 坐标核对阶段只标点，不点击有业务副作用的按钮。
- 不从旧脚本、历史截图、拖动 preview 或未验证公式推导正式坐标。
- 当前坐标核对阶段不主动开展代码重构、自动化验收或定时化；发现旧代码疑点先登记 Todo。此为阶段性暂缓。坐标核对完成并进入新脚本设计后，必须按用户新需求重新评估旧代码，可保留、改造、删除或重写，不预设兼容或全量重写。

## 坐标规则

- QQ 标准窗口：603×1111；微信标准农场画布：625×1155。
- 土地网格等场景层使用已验证的 scene 换算；首页贴窗口边缘的固定控件使用 fixed_ui 轴向比例换算。
- picker、弹窗、动态按钮、preview、确认按钮等未分类控件必须有直接样本验证，不能套用 scene / fixed_ui 公式。
- 窗口或场景不符合标准基线时，不得直接复用标准坐标。
- 结构化坐标事实保存在 data/ui-layout.json 和 data/ui-anchors.json；pending 候选不是正式坐标。

## ENTRY MAP

| 文件 | 用途 |
| --- | --- |
| docs/CURRENT.md | 当前阶段、已确认坐标范围、现场与操作边界 |
| tasks/todo.md | 当前坐标核对待办及旧代码延后问题 |
| docs/INDEX.md | 文档导航 |
| 工作区根 _sandbox/farm-coordinate-review.html | QQ / 微信统一坐标核对页 |
| data/ui-layout.json | 土地网格、标准窗口和坐标层 |
| data/ui-anchors.json | 固定 UI、已确认点与待确认候选 |
| docs/gameplay-rules.md | 游戏玩法事实；其中 Runner/自动化实现描述不代表当前已批准方案 |
| docs/seed-catalog.md / data/seed-catalog.json | 种子资料 |
| IMPLEMENTATION_PLAN.md | 已暂停的旧 Runner V2 计划，仅供未来评估 |
| docs/archive/ | 历史阶段归档 |

## 安全边界

- 坐标核对只标点；收获、种植、施肥、购买、领取奖励、发送分享等有业务副作用的按钮不点击。
- 仓鼠气泡只在自然出现时采集，不主动等待或制造出现条件。
- 好友农场只在用户明确授权的坐标核对或正常日常互动中观察，不主动单独进入。
- 当前坐标核对阶段如需真机输入，必须取得当前 Chat 中用户对本次操作的明确授权；本阶段不执行有业务副作用的动作。未来自动化的授权方式、执行器和定时任务边界，留到新方案设计时重新讨论，不从历史会话或旧任务推定授权。
- 候选坐标、历史截图位置和脚本常量都不能替代用户确认。
- 不默认沿用现有 Runner / 脚本；未来实现方式由用户在坐标核对完成后决定。

## PATHS

- 当前阶段：docs/CURRENT.md
- Todo：tasks/todo.md
- 坐标核对页：工作区根目录 _sandbox/farm-coordinate-review.html
- 网格与坐标层：data/ui-layout.json
- UI 点位：data/ui-anchors.json
- 玩法事实：docs/gameplay-rules.md
- 种子资料：docs/seed-catalog.md、data/seed-catalog.json
- 历史：docs/archive/
