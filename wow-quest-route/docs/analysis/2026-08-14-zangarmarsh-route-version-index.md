# 赞加沼泽增量路线版本索引

日期：2026-08-14
用途：保存每次插入前后的历史快照，最终全图完成后逐版回放审计。

## 范围与最终权威

- R1–R62主要记录当时角色状态下的局部增量插入、特殊机制、条件任务、跨图任务和排除项；它们是历史审计材料，不是当前最终路线。
- R63起开始补回当时角色已经完成、但从零可复用路线必须包含的任务；R63–R67属于最终复用结构恢复，R68–R71继续补齐副本模块归档。
- Rn快照只保存当时结论，最终路线权威文件为`docs/analysis/2026-08-14-zangarmarsh-final-reusable-route-v1.md`；任务边界权威文件为`docs/analysis/2026-08-14-zangarmarsh-complete-task-universe-audit.md`。

## 版本

### R1
文件：`docs/analysis/2026-08-14-zangarmarsh-r1-northeast-death-mire.md`

内容：第一目标簇/东北死亡泥潭候选；建立9773+9774东部湖区共刷、解锁9899+9771、尤尔巴处接9772但不在东北强刷。

### R2
文件：`docs/analysis/2026-08-14-zangarmarsh-r2-vashj-insert-snapshot.md`

内容：在R1中自由插入弗亚希王女簇；第二簇A/C/T分别进入R1前、中、后部；建立`C_full`与`C_partial`区别。

### R3
文件：`docs/analysis/2026-08-14-zangarmarsh-r3-mudclaw-with-hearth.md`

内容：插入泥爪毁坏者簇；首次加入炉石交通重置，当前版本在东部结束后炉石回萨布拉金。

### R4
文件：`docs/analysis/2026-08-14-zangarmarsh-r4-groak-insert-snapshot.md`

内容：插入格罗阿克簇及`9697→9701→9702→9708`依赖包；A9697插到全路线开头，A9820并入第一次萨布拉金停靠；格罗阿克与9708同营地合并；R4首次出现双炉石：炉石1东部→萨布拉金，炉石2泥爪区→萨布拉金。

### R5
文件：`docs/analysis/2026-08-14-zangarmarsh-r5-bloodscale-insert-snapshot.md`

内容：插入血鳞基础簇`9726→9727`。第一轮血鳞后回舒特解锁9727，第二轮不立即做，而是延后嵌入莉萨奥链→格罗阿克之间；T9727继续延后到炉石2回萨布拉金后的收尾段。两轮血鳞均只给9728增加局部进度。双炉石位置保持不变。

### R6
文件：`docs/analysis/2026-08-14-zangarmarsh-r6-angorosh-final-insert-snapshot.md`

内容：插入安葛洛什终局簇9709与9823，并加入9822桥接；保留R5双炉石结构，终局任务合并为一次区域清理。

### R7
文件：`docs/analysis/2026-08-14-zangarmarsh-r7-giants-insert-snapshot.md`

内容：插入巨人簇9743→9744，并在西南巨人区顺带完成9772；东北实例因掉率明显更差不再访问。巨人两代插入9701与9702之间；T9772保持READY_TO_TURNIN，等待后续东部簇吸收。双炉石位置保持不变。

### R8
文件：`docs/analysis/2026-08-14-zangarmarsh-r8-murlagsh-insert-snapshot.md`

内容：插入穆拉格什簇9903；A9903并入炉石2后的萨布拉金停靠，C9903延后到9822西北小环完成后，再与安葛洛什终局串联；T9903与T9823合并回萨布拉金交付。炉石仍为两次。

### R9
文件：`docs/analysis/2026-08-14-zangarmarsh-r9-haghaz-insert-snapshot.md`

内容：插入哈格哈兹王子簇9730；A9730并入塞纳里奥开场通缉布告，C9730插入沼泽鼠↔东部湖区小环，T9730并入前半段哈穆特停靠。9728仅继续获得局部进度，炉石仍为两次。

### R10
文件：`docs/analysis/2026-08-14-zangarmarsh-r10-blacksting-insert-snapshot.md`

内容：插入黑钉簇9898。黑钉固定点(49.75,60.06)最适合放在前半段哈穆特收尾之后、炉石1之前：`哈穆特T9817+T9730 → 黑钉C9898 → 炉石1→萨布拉金`。逐边比较后该插入只新增约106.1秒单程移动，优于其它前半插缝约107–206秒。9769《时尚无罪》仅记顺带进度，不让低掉率黑钉驱动该广域任务。T9898保持READY_TO_TURNIN，等待最后特殊/背景阶段再次经过东部时吸收。炉石1因此由哈穆特后移动到黑钉后；炉石2仍在泥爪后。

### R11
文件：`docs/analysis/2026-08-14-zangarmarsh-r11-swamp-lash-noop-snapshot.md`；范围说明：`docs/analysis/2026-08-14-zangarmarsh-r11-scope-note.md`

内容：处理沼泽之鞭簇后，因9895在当时角色状态中已经完成，9806/9807留待特殊/背景阶段，当前主体路线不新增动作；不为(82.07,71.39)制造无意义访问。炉石序列不变，主体空间簇处理完成。

### R12
文件：`docs/analysis/2026-08-14-zangarmarsh-r12-marshlight-bleeder-insert-snapshot.md`

内容：单独插入9841《清除沼光抽血者》。A并入炉石1后的萨布拉金停靠；C定义为`萨布拉金→舒特→血鳞第一轮`沿途服务窗口，路径附近已有足够刷新，不新增路线节点；T并入炉石2后的萨布拉金停靠。主体几何和双炉石位置均不变。

### R13
文件：`docs/analysis/2026-08-14-zangarmarsh-r13-marshfang-slicer-insert-snapshot.md`

内容：单独插入9842《最锋利的刀刃》。T9841后同停靠A9842；将炉石2后的`舒特→莉萨奥`西部切割者密集带定义为C9842服务走廊，完成后在下一次萨布拉金停靠T9842。主体几何与双炉石位置不变。

### R14
文件：`docs/analysis/2026-08-14-zangarmarsh-r14-fashion-is-no-crime-insert-snapshot.md`

内容：单独插入9769《时尚无罪》。A并入第一次玛加沙停靠；使用掉率最高的暗光钉刺者，在哈格哈兹→东部湖区之间建立C9769服务窗口；回到玛加沙时T9769。基本不改变跨区折线，只增加约1684秒服务时间。

### R15
文件：`docs/analysis/2026-08-14-zangarmarsh-r15-mature-spores-insert-snapshot.md`

内容：单独插入9806《成熟的孢子》。A并入炉石1后第一次孢子村停靠；血鳞第一轮回村后，在孢子村北/西北大型孢子蝠密集区完成C9806并回格沙弗T9806。采用本地大型孢子蝠而不是理论掉率略高但远在东部的沼泽阔步者，避免跨区移动。

### R16
文件：`docs/analysis/2026-08-14-zangarmarsh-r16-more-mature-spores-insert-snapshot.md`

内容：单独插入9807《更多成熟的孢子》。T9806时原地A9807；离开孢子村去莉萨奥/法恩森的自然路线上沿途击杀大型孢子蝠完成C9807；完成后不回头，等炉石2之后原路线再次经过孢子村时与T9727合并T9807。不增加新的跨区折线或Hub访问。

### R17
文件：`docs/analysis/2026-08-14-zangarmarsh-r17-brightcap-insert-snapshot.md`

内容：单独插入9808《亮顶蘑菇》。第一次孢子村A9808；炉石1后的西部主体路线全程背景拾取，泥爪前后不足则附近补齐；炉石2后再次孢子村时T9808。不建立独立采集中心。

### R18
文件：`docs/analysis/2026-08-14-zangarmarsh-r18-more-brightcap-insert-snapshot.md`

内容：单独插入9809《更多亮顶蘑菇》。T9808后原地A9809，在姆希菲附近5个最近刷新点做微型采集环，立即T9809，再继续莉萨奥。

### R19
文件：`docs/analysis/2026-08-14-zangarmarsh-r19-sporeling-trouble-insert-snapshot.md`

内容：单独插入9739《孢子人的困境》。A并入法恩森停靠；孢子囊刷新区与9701调查和西南巨人区重合，五轮采集的刷新等待被9743约20分钟巨人服务自然吸收；回法恩森时T9739。

### R20
文件：`docs/analysis/2026-08-14-zangarmarsh-r20-more-spore-sacs-insert-snapshot.md`

内容：单独插入9742《更多孢子囊》。T9739后原地A9742，下一次返回同一巨人/孢子囊区时拾5个完成，与9744同时服务，回法恩森合并T9742。

### R21
文件：`docs/analysis/2026-08-14-zangarmarsh-r21-burstcap-insert-snapshot.md`

内容：单独插入9814《爆顶蘑菇》。炉石1落地萨布拉金A9814；西部主体路线全程背景采集30枚，泥爪前后不足则附近补齐；炉石2落地萨布拉金T9814。

### R22
文件：`docs/analysis/2026-08-14-zangarmarsh-r22-murloc-cage-insert-snapshot.md`

内容：单独插入9816《你见过鱼人吗？》。炉石2落地萨布拉金T9814后原地A9816；先去匕潭村笼子点(26.81,22.60)，再去9822攻击计划(19.88,27.09)，把9816吸收到既有西北小环；后续下一次回萨布拉金时与T9822合并T9816。

### R23
文件：`docs/analysis/2026-08-14-zangarmarsh-r23-mummaki-insert-snapshot.md`

内容：单独插入10117《通缉：穆玛基酋长》。A并入炉石2萨布拉金停靠；第一次西北小环按`9816笼子→穆玛基→9822攻击计划`连续完成；下一次回萨布拉金T10117。

### R24
文件：`docs/analysis/2026-08-14-zangarmarsh-r24-daggerfen-lost-ones-insert-snapshot.md`

内容：单独插入10118《警告匕潭失落者》。因前置9822，必须第二次访问匕潭；比较后保留原孢子村/莉萨奥顺序更短约53秒。第二次匕潭C10118后不回城，直接穆拉格什→安葛洛什终局，最终回萨布拉金合并T10118。

### R25
文件：`docs/analysis/2026-08-14-zangarmarsh-r25-terrorclaw-insert-snapshot.md`

内容：单独插入9904《猎杀恐爪》。T9845后同停靠A9904；恐爪位于第一次西北小环从攻击计划回孢子村的自然回程附近，C9904插在攻击计划后、孢子村前；下一次萨布拉金T9904。

### R26
文件：`docs/analysis/2026-08-14-zangarmarsh-r26-feralfen-spirits-insert-snapshot.md`

内容：单独插入9846《蛮沼之灵》。利用本次“任务已接”状态，把C9846放在黑钉之后的相邻蛮沼区，完成后炉石1回萨布拉金T9846。正式从零攻略必须重新补A9846，不能直接照搬。

### R27
文件：`docs/analysis/2026-08-14-zangarmarsh-r27-spirit-alliance-insert-snapshot.md`

内容：单独插入9847《灵魂之盟？》。炉石1落地T9846后原地A9847；把博哈姆(44.36,66.01)尝试插入炉石1到炉石2之间各边后，最佳是`格罗阿克→博哈姆→泥爪`，约增加82.7秒；炉石2落地萨布拉金T9847。

### R28
文件：`docs/analysis/2026-08-14-zangarmarsh-r28-sporeggar-breadcrumb-insert-snapshot.md`

内容：插入9919《孢子村》；第一次自然经过法恩森时接取，炉石2后再次经过孢子村时交付，不增加移动、刷怪或独立停靠。

### R29
文件：`docs/analysis/2026-08-14-zangarmarsh-r29-crow-flight-fixed-script-snapshot.md`

内容：插入9718《乌鸦的飞翔》脚本机制；在塞纳里奥既有停靠内接取、执行脚本飞行并交付，不把飞行调查区误建成骑行目标。

### R30
文件：`docs/analysis/2026-08-14-zangarmarsh-r30-restore-balance-four-pumps-snapshot.md`

内容：插入9720《恢复平衡》；四个水泵分别挂入暗泽湖、环礁湖、毒蛇湖和沼光湖既有区域，禁止合并成虚构中心点。

### R31
文件：`docs/analysis/2026-08-14-zangarmarsh-r31-umbrafen-tribe-insert-snapshot.md`

内容：插入9747《暗泽部族》；当时角色已接取，目标并入9769南部服务带与9720暗泽湖泵附近清理；从零版需补A9747。

### R32
文件：`docs/analysis/2026-08-14-zangarmarsh-r32-cold-place-insert-snapshot.md`

内容：插入9788《阴冷之地》；T9747后接取，南部物品点并入前往黑钉前的暗泽南缘段，交付留最终东部收尾。

### R33
文件：`docs/analysis/2026-08-14-zangarmarsh-r33-protect-watcher-insert-snapshot.md`

内容：插入9894《保护观察者》；克拉其大王与9788物品点同属暗泽南缘局部范围，合并清理，交付留最终东部收尾。

### R34
文件：`docs/analysis/2026-08-14-zangarmarsh-r34-save-sporeloks-insert-snapshot.md`

内容：插入10096《拯救孢子人》；目标与9894/9788南部清理段重合，不新增独立路线节点，交付留最终东部收尾。

### R35
文件：`docs/analysis/2026-08-14-zangarmarsh-r35-missing-expedition-excluded-snapshot.md`

内容：审计9876《失踪的先遣队》；确认为盘牙副本引导，不插入赞加开放世界路线。

### R36
文件：`docs/analysis/2026-08-14-zangarmarsh-r36-turnin-jyobas-report-snapshot.md`

内容：补入9772《尤尔巴的报告》的最终东部交付，把此前READY_TO_TURNIN状态吸收到沼泽鼠收尾。

### R37
文件：`docs/analysis/2026-08-14-zangarmarsh-r37-turnin-respect-snapshot.md`

内容：补入9898《对我的教训》的最终东部交付，与T9772合并到沼泽鼠收尾。

### R38
文件：`docs/analysis/2026-08-14-zangarmarsh-r38-turnin-restore-balance-snapshot.md`

内容：补入9720《恢复平衡》的最终塞纳里奥交付，并固定莉萨奥→塞纳里奥→沼泽鼠的既有收尾顺序。

### R39
文件：`docs/analysis/2026-08-14-zangarmarsh-r39-turnin-cold-place-snapshot.md`

内容：把9788《阴冷之地》交付并入最终塞纳里奥收尾。

### R40
文件：`docs/analysis/2026-08-14-zangarmarsh-r40-turnin-protect-watcher-snapshot.md`

内容：把9894《保护观察者》交付并入最终塞纳里奥收尾。

### R41
文件：`docs/analysis/2026-08-14-zangarmarsh-r41-turnin-save-sporeloks-snapshot.md`

内容：把10096《拯救孢子人》交付并入最终塞纳里奥收尾。

### R42
文件：`docs/analysis/2026-08-14-zangarmarsh-r42-hearty-welcome-finish-snapshot.md`

内容：完成9728《热情的欢迎》背景计数；血鳞第二轮离开前检查五号30/30，缺少时在当前区域补齐，最终塞纳里奥交付。

### R43
文件：`docs/analysis/2026-08-14-zangarmarsh-r43-hearth-reset-three-uses-snapshot.md`

内容：记录第三次炉石重置；中间服务时间已超过30分钟，北部终局后炉石回萨布拉金，不等待冷却。

### R44
文件：`docs/analysis/2026-08-14-zangarmarsh-r44-fhwoor-escort-insert-snapshot.md`

内容：条件插入9729《弗沃尔发怒了！》；现场可见时执行并在护送经过时完成沼光湖泵，不可见时跳过护送、保留既有水泵挂点。

### R45
文件：`docs/analysis/2026-08-14-zangarmarsh-r45-escape-umbrafen-reusable-note.md`

内容：记录9752《逃离暗泽村》；当时角色已完成，局部版No-op，最终从零版恢复其暗泽村到塞纳里奥护送。

### R46
文件：`docs/analysis/2026-08-14-zangarmarsh-r46-withered-basidium-opportunistic-snapshot.md`

内容：审计9828《枯萎的孢芽》；1.53%低掉率机会任务，不主动建立刷取路线，获得时才在沼泽鼠交付。

### R47
文件：`docs/analysis/2026-08-14-zangarmarsh-r47-count-ungula-item-start-snapshot.md`

内容：插入9911《沼泽中的伯爵》；昂古拉位于9842服务走廊，见到即杀、继续主任务、不站等，五号取得任务物后在莉萨奥交付。

### R48
文件：`docs/analysis/2026-08-14-zangarmarsh-r48-spore-leaf-dungeon-excluded-snapshot.md`

内容：审计9717《孢子叶》；目标物来自幽暗沼泽副本，不插入开放世界路线。

### R49
文件：`docs/analysis/2026-08-14-zangarmarsh-r49-black-stalker-dungeon-excluded-snapshot.md`

内容：审计9719相关黑色阔步者目标；归入幽暗沼泽副本模块，不插入开放世界路线。

### R50
文件：`docs/analysis/2026-08-14-zangarmarsh-r50-warlords-hideout-dungeon-excluded-snapshot.md`

内容：审计9763《督军的末日》；归入蒸汽地窟副本模块，不插入开放世界路线。

### R51
文件：`docs/analysis/2026-08-14-zangarmarsh-r51-orders-vashj-dungeon-excluded-snapshot.md`

内容：审计9764《瓦丝琪女王的命令》及后续；来源和后续属于盘牙副本物品/声望体系，不插开放世界路线。

### R52
文件：`docs/analysis/2026-08-14-zangarmarsh-r52-plants-of-zangarmarsh-reusable-note.md`

内容：记录9802《赞加沼泽的植物》；当时角色已完成，最终版在开场接取并按自然库存条件交付，不为采集单独改线。

### R53
文件：`docs/analysis/2026-08-14-zangarmarsh-r53-identify-plants-conditional-snapshot.md`

内容：记录9784《鉴定植物》重复库存任务；仅自然满足时交付，不主动刷取。

### R54
文件：`docs/analysis/2026-08-14-zangarmarsh-r54-uncatalogued-species-conditional-snapshot.md`

内容：记录9875《未归类的植物》机会任务；只有随机获得起始物时才原地开启并交付。

### R55
文件：`docs/analysis/2026-08-14-zangarmarsh-r55-ogre-threat-carry-forward.md`

内容：记录9795《食人魔的威胁》跨地图携带；最后萨布拉金停靠现场可见才接，不增加赞加移动。

### R56
文件：`docs/analysis/2026-08-14-zangarmarsh-r56-zangarmarsh-visitor-carry-forward.md`

内容：记录9796《赞加沼泽的来客》跨地图携带；最终沼泽鼠收尾时接取并带往泰罗卡，当时局部版为No-op。

### R57
文件：`docs/analysis/2026-08-14-zangarmarsh-r57-garadar-support-carry-forward.md`

内容：记录9797跨地图携带；最后萨布拉金停靠接取并带往纳格兰，当时局部版为No-op。

### R58
文件：`docs/analysis/2026-08-14-zangarmarsh-r58-cenarion-thicket-carry-forward.md`

内容：记录9957《塞纳里奥树林出事了？》跨地图携带；最终塞纳里奥收尾接取并带往泰罗卡。

### R59
文件：`docs/analysis/2026-08-14-zangarmarsh-r59-rakoria-message-carry-forward.md`

内容：记录10105《给拉克妮亚的消息》跨地图携带；最后萨布拉金停靠现场可见才接，不增加赞加移动。

### R60
文件：`docs/analysis/2026-08-14-zangarmarsh-r60-strange-energy-terokkar-excluded.md`

内容：确认9968《奇怪的能量》属于泰罗卡后续，不在赞加执行。

### R61
文件：`docs/analysis/2026-08-14-zangarmarsh-r61-cenarion-expedition-inbound.md`

内容：记录9912《塞纳里奥远征队》进入赞加的条件breadcrumb；从地狱火携带时在开场塞纳里奥自然交付。

### R62
文件：`docs/analysis/2026-08-14-zangarmarsh-r62-report-to-zurai-inbound.md`

内容：记录10103《向祖莱报到》进入赞加的条件breadcrumb；携带时第一次自然到达沼泽鼠再交付，当时角色已完成。

### R63
文件：`docs/analysis/2026-08-14-zangarmarsh-r63-umbrafen-lake-reusable-opening.md`

内容：开始恢复最终从零可复用版；补回9716《暗泽湖的异常》，并让9752护送承担9716/9747回程，建立最终开场结构。

### R64
文件：`docs/analysis/2026-08-14-zangarmarsh-r64-marshfang-threat-reusable.md`

内容：补回9770《沼牙的威胁》；第一次沼泽鼠接取，东部沿途完成，首次回访交付并接9898。

### R65
文件：`docs/analysis/2026-08-14-zangarmarsh-r65-report-to-denga-reusable.md`

内容：补回9775《向暗影猎手德恩加报到》；第一次沼泽鼠接取，炉石1落地萨布拉金交付。

### R66
文件：`docs/analysis/2026-08-14-zangarmarsh-r66-blessing-of-ancients-reusable.md`

内容：补回9785《古树的祝福》；开场塞纳里奥Hub内完成两位古树祝福并立即交付，不形成地图级节点。

### R67
文件：`docs/analysis/2026-08-14-zangarmarsh-r67-disrupted-balance-reusable.md`

内容：补回9895《崩溃的平衡》；开场接取、东南既有服务段完成、中段自然回塞纳里奥交付。

### R68
文件：`docs/analysis/2026-08-14-zangarmarsh-r68-red-hibiscus-repeat-dungeon-excluded.md`

内容：审计9714《给我一棵灌木吧！》；红色木槿来自幽暗沼泽副本，不进入开放世界路线。

### R69
文件：`docs/analysis/2026-08-14-zangarmarsh-r69-red-hibiscus-repeat-dungeon-excluded.md`

内容：审计9715《我要红色木槿！》；归入幽暗沼泽重复副本模块，不进入开放世界路线。

### R70
文件：`docs/analysis/2026-08-14-zangarmarsh-r70-preparing-for-war-dungeon-excluded.md`

内容：审计9765《战争准备》；归入盘牙副本物品任务，不进入开放世界路线。

### R71
文件：`docs/analysis/2026-08-14-zangarmarsh-r71-coilfang-armaments-repeat-dungeon-excluded.md`

内容：审计9766《盘牙武器》；归入盘牙副本掉落与重复声望交付模块，不进入开放世界路线。

## 固定规则

- Rn一旦保存为历史快照，后续不得覆盖；
- 插入R(n+1)之前先确认Rn文件已存在或在版本索引中已有等价持久记录；
- 后续发现旧版本问题，只在新版本中修正并记录原因；
- 全部主体簇插完后按R1→Rn逐版回放；
- 每版记录本次新增簇、旧路线局部改动、炉石使用点及其冷却依据；
- 特殊/广域任务严格一个一个插入；沿途背景任务不制造假的中心点或新折线，只标注在真实经过的路段/停靠上；
- 炉石可一条路线多次使用，只要相邻两次之间累计路线时间≥30分钟且都有明确收益；
- 动态HTML预览不在每个Rn之间更新；一个地图的任务全部插入完成后统一生成和审图，可作为后续前端实现基础。
