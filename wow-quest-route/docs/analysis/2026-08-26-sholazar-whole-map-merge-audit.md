# 索拉查盆地整图任务簇合并审查

- exact重复Spatial Instance：6；未解释=[]；harmful split=0。
- 最终玩家步骤需要主动合并的连续任务块：2。

- dorian_camp｜['W17', 'W18', 'W19']｜forced_internal_returns_merge_player_step｜12603完成后才开12607/58/81；12607送猛犸回营后才开12614。三次回营都是真前置，但最终前端合并为一个连续多里安任务块。
- frenzyheart_hill｜['W08', 'W09', 'W10', 'W11', 'W13']｜forced_hub_chain｜12528→12529/30→12533/34→12532→12531/35→12536逐层解锁，不能一次进场预做。
- mistwhisper_village｜['W12', 'W16', 'W19']｜forced_phase_and_objective_return｜W12是狂心阶段脚本到村；W16切神谕后才解锁12575/76；W19必须做完北部目标后回来交。
- nesingwary_camp｜['W01', 'W02', 'W03', 'W04', 'W05', 'W06', 'W07', 'W13']｜forced_hub_chain｜多条奈辛瓦里任务链必须回营地交前一环再解锁下一环；W13还承担已优化的延迟交12569/12645并接12595。
- rainspeaker_canopy｜['W14', 'W15', 'W16', 'W19', 'W21']｜forced_hub_chain｜12570后分层解锁12571/72→12573→12574，之后12577和12695又分别从北部/阿图里斯链回交。
- rivers_heart｜['W08', 'W16']｜optimized_delayed_turn｜W08首次开Hub并做维克/塔玛拉；12654故意延后到W16做12573时顺交，避免从匹奇区域专门折返。
- swindlegrins_dig｜['W03', 'W04']｜forced_prerequisite_repeat｜12525《工头斯温迪格林》只有12524回营交付后才能接，所以挖掘场必须二次进入；第一次已把零件、15杀、戒指、护送全部合并。
- final_east_campaign｜['W20', 'W21']｜merge_player_step_continuous_campaign｜苔行东部服务完必须回莫乌德交12579才能接12581；随后立即去阿图里斯，不离开东部任务区。最终玩家步骤合并展示，不能表现成两次独立远征。

## 本轮实际回插修正

- 多里安原候选把12607猛犸和12683多头蛇硬合并，机制核验后否决。
- 12683改入W17始祖龙/幼崽外圈；12607单独就近抓猛犸立即送回，再开12614母龙。
