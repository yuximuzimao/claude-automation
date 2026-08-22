# 祖达克对抗性审查

- 结论：**PASS**。
- 正式任务：104/104，missing=[]，unexpected=[]，defer={}。
- 任务日志显式生命周期峰值：9/25（余量16）；峰值点：达克索塔·布兰顿 / 鲁伯特 / 罗杰斯博士。
- 依赖顺序违规：0；五开检查未显式落玩家页：0。
- 系统飞行：5段，违规0，未知目的地0。
- 视频反审：PASS；共同明确完成=37；视频证明漏项=0；未解释逆序=0。
- 12974顺序：达拉然往返点66 → 接取点66 → 斗兽场交付点67 / 第一场接取点67。

## 长骑行边（≥18%地图尺度，人工挑战清单）

- 92→93 希姆托加·佐尔玛兹回收 → 古达克飞行点：36.5%；required_first_visit: 12721 is accepted only after the Zol'Maz tasks are turned in at Zim'Torga; Gundrak flight point is still unopened, so the first northbound leg must be ground travel.
- 99→100 哈克娅·诸神的指引 → 佐尔赫布召唤圈：36.5%；direct_ground_is_shorter: both Zim'Torga and Gundrak are open, but route-model comparison gives about 1.57 min direct versus 2.27 min via Zim'Torga taxi Gundrak; keep direct ride.
- 91→92 佐尔玛兹要塞·三任务 → 希姆托加·佐尔玛兹回收：25.1%；required_hub_unlock: 12707/12708/12709/12712 must be turned in at Zim'Torga to unlock 12721; cannot continue north before this hub return.
- 35→36 痛苦之匣·吹号最终 → 银色前沿·首次到达：24.7%；direct_ground_is_shorter: Voltarus is already closed locally with Stefan's Horn; direct Pain→Argent is about 1.09 min versus about 2.46 min by backtracking to Ebon then taking taxi.
- 85→86 哈克娅·奎丝鲁恩收尾 → 犸托斯祭坛：23.6%；strict_chain: 12675 turns in at Harkoa and directly unlocks 12684 at Mamtoth; no useful intermediate unlock exists on this edge.
- 86→87 犸托斯祭坛 → 哈克娅·死去神灵回收：23.6%；strict_chain_return: 12684 must return to Harkoa to unlock 12685; this is the mandatory reverse leg of the same deity chain.
- 64→65 西莱图斯先知·第二趟 → 银色前沿·巡逻总回收：23.3%；required_turnin: 12516 and 12596 both close at Argent Stand; no flight point exists at Sseratus and no newly unlocked cluster can replace the hub return.
- 57→58 药剂喷射器 → 希姆埃巴雕像·回程：22.2%；whole-loop_order_checked: the current Sprayer→Zim'Abwa→Argent→Basilisk ordering is about 213 yards shorter than Argent→Zim'Abwa→Basilisk using the same anchors.
- 97→98 希姆鲁克守卫者 → 奎丝鲁恩祭坛典狱官：20.5%；same_quest_two_sources: both are required essence sources for 12729; the long edge connects the two mandatory objectives before the single Harkoa turn-in.
- 80→81 哈克娅之爪·神圣符印 → 奎丝鲁恩之魂：20.0%；strict_chain: turning 12666 at Harkoa unlocks 12667, whose next required endpoint is Quetz'lun; no intermediary task is available to break the edge.
- 10→11 前线周边·女妖精华 → 黑锋入口·硅藻土：19.1%；intentional_cluster_bridge: these are the two material sources for 12914; diatomaceous earth is at the Ebon entrance, so this edge intentionally converts the Gymer material quest into the bridge to the Ebon chain.

## 硬失败

- 无。
