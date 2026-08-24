# 诺森德全任务卡宇宙（血精灵圣骑士）

- Questie：11.34.0
- 总任务卡：1596
- 第一轮直接可做：950
- 条件待路线状态确认：74
- 当前角色/户外规则排除：572
- 已有任务自身服务时间：1471；仍需专项机制估时：125。
- 当前不学寒冷天气飞行策略直接/递归阻断：17张。
- 同名候选组：161；Journey已选定服务器一次性版本5组；普通→日常生命周期组24组；日常轮换组1组；仍有0组一次性服务器版本待确认。
- 人类可执行性/隐藏机制：已明确需要备注582张、已明确无需额外备注537张；当前仍可能入线但待审0张，其中高风险信号0张。
- 已确认存在洞穴/楼层/上下层/水下/悬崖/脚本交通等非平面执行约束：238张。所有未完成人工执行审计的任务默认禁止仅凭平面坐标自动判定顺路。
- 每张卡已固定80级XP折金字段；与练级期直接金币分开。
- 11591《钢腭的车队》是当前唯一用户明确批准可自然消失的单任务例外；不得类推。

## 区域卡数

- 冬拥湖: 28
- 冰冠冰川: 279
- 北风苔原: 252
- 嚎风峡湾: 219
- 洛斯加尔登陆点: 1
- 灰熊丘陵: 170
- 祖达克: 134
- 索拉查盆地: 105
- 达拉然: 9
- 风暴峭壁: 159
- 龙骨荒野: 240

## 人类可执行性 / 空间风险待审

- `reviewed_note_required`：已查清特殊完成方式，后续玩家任务备注必须复用这些事实。
- `reviewed_no_extra_note`：已人工审过，任务名 + 正常目标定位足够，不强行写废话备注。
- `review_required_*`：尚未完成这一层人工审计；无论平面坐标多近，路线层都不得据此自动判定真实顺路。
- 完整待审队列：`data/route-atlas/northrend-execution-review.json`。

## 条件任务

- 11411《冬蹄营地》 req=68：exclusive_availability_condition；exclusiveTo=[12566]
- 11574《危在旦夕》 req=69：exclusive_availability_condition；exclusiveTo=[11587]
- 11591《钢腭的车队》 req=68：exclusive_availability_condition；exclusiveTo=[11592, 11593, 11594]
- 11977《牦牛人中的牛头人》 req=71：exclusive_availability_condition；exclusiveTo=[11979]
- 11979《牦牛人和牛头人》 req=71：exclusive_availability_condition；exclusiveTo=[11977]
- 11981《找到库伦！》 req=72：exclusive_availability_condition；exclusiveTo=[12074]
- 12074《新的盟友》 req=73：exclusive_availability_condition；exclusiveTo=[11981]
- 12181《给它一个名字》 req=71：exclusive_availability_condition；exclusiveTo=[12188]
- 12189《笨蛋加白痴！》 req=71：exclusive_availability_condition；exclusiveTo=[12182]
- 12501《巡逻员》 req=74：calendar_rotation_condition, exclusive_availability_condition；exclusiveTo=[12563, 12587]
- 12502《巡逻员：战旗飘扬》 req=74：exclusive_availability_condition；exclusiveTo=[12564, 12588]
- 12509《巡逻员：鼓舞士气》 req=74：exclusive_availability_condition；exclusiveTo=[12568, 12591]
- 12519《巡逻员：你想要勋章？》 req=74：exclusive_availability_condition；exclusiveTo=[12585, 12594]
- 12563《巡逻员》 req=74：calendar_rotation_condition, exclusive_availability_condition；exclusiveTo=[12501, 12587]
- 12564《巡逻员：止痛药》 req=74：exclusive_availability_condition；exclusiveTo=[12502, 12588]
- 12566《增援冬蹄营地》 req=68：exclusive_availability_condition；exclusiveTo=[11411]
- 12568《巡逻员：阵亡者的尊严》 req=74：exclusive_availability_condition；exclusiveTo=[12509, 12591]
- 12582《狂心氏族的勇士》 req=76：exclusive_availability_condition；exclusiveTo=[12689]
- 12585《巡逻员：温暖的篝火》 req=74：exclusive_availability_condition；exclusiveTo=[12519, 12594]
- 12587《巡逻员》 req=74：calendar_rotation_condition, exclusive_availability_condition；exclusiveTo=[12501, 12563]
- 12588《巡逻员：挖挖看？》 req=74：exclusive_availability_condition；exclusiveTo=[12502, 12564]
- 12591《巡逻员：扔手雷》 req=74：exclusive_availability_condition；exclusiveTo=[12509, 12568]
- 12594《巡逻员：清理场地》 req=74：exclusive_availability_condition；exclusiveTo=[12519, 12585]
- 12629《无处可藏》 req=74：exclusive_availability_condition；exclusiveTo=[12643]
- 12631《某种邀请……》 req=74：exclusive_availability_condition；exclusiveTo=[12633]
- 12633《黑暗的召唤》 req=74：exclusive_availability_condition；exclusiveTo=[12631]
- 12637《幸免于难》 req=74：exclusive_availability_condition；exclusiveTo=[12638]
- 12638《侥幸逃脱》 req=74：exclusive_availability_condition；exclusiveTo=[12637]
- 12643《一线希望》 req=74：exclusive_availability_condition；exclusiveTo=[12629]
- 12648《乔装打扮》 req=74：exclusive_availability_condition；exclusiveTo=[12649]
- 12649《乔装打扮！》 req=74：exclusive_availability_condition；exclusiveTo=[12648]
- 12651《湖边着陆场》 req=76：exclusive_availability_condition；exclusiveTo=[12654]
- 12652《喂饱食尸鬼》 req=74：exclusive_availability_condition；exclusiveTo=[12713]
- 12663《久别重逢》 req=74：exclusive_availability_condition；exclusiveTo=[12648, 12664]
- 12664《黑暗的地平线》 req=74：exclusive_availability_condition；exclusiveTo=[12649, 12663]
- 12689《神谕者之手》 req=76：exclusive_availability_condition；exclusiveTo=[12582]
- 12692《巫妖猎手归来》 req=76：reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart
- 12695《友善的干燥皮肤朋友》 req=76：reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles
- 12703《卡塔克的愤怒》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12759, 12760]
- 12705《泰坦的意志》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12761, 12762]
- 12726《风与水之歌》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12735, 12736, 12737]
- 12732《日灼之力》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12734, 12741, 12758]
- 12734《雷耶克：第一滴血》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12732, 12741, 12758]
- 12735《净化之歌》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12726, 12736, 12737]
- 12736《沉思之歌》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12726, 12735, 12737]
- 12737《丰饶之歌》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12726, 12735, 12736]
- 12741《雷雨之力》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12732, 12734, 12758]
- 12758《英雄的头盔》 req=77：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12732, 12734, 12741]
- 12759《战争的工具》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12703, 12760]
- 12760《狂心氏族的秘密武器》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=狂心氏族:9000；branch=sholazar_tribe_choice:frenzyheart；exclusiveTo=[12703, 12759]
- 12761《掌握水晶》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12705, 12762]
- 12762《造物主的力量》 req=76：exclusive_availability_condition, reputation_condition_needs_route_state；minRep=神谕者:9000；branch=sholazar_tribe_choice:oracles；exclusiveTo=[12705, 12761]
- 12763《前线告急》 req=74：exclusive_availability_condition；exclusiveTo=[12789, 12792, 12793]
- 12789《前往圣光据点！》 req=74：exclusive_availability_condition；exclusiveTo=[12763, 12792, 12793]
- 12792《紧急事务》 req=74：exclusive_availability_condition；exclusiveTo=[12763, 12789, 12793]
- 12793《地平线上的硝烟》 req=74：exclusive_availability_condition；exclusiveTo=[12763, 12789, 12792]
- 12929《奥杜尔的土灵》 req=77：exclusive_availability_condition；exclusiveTo=[12930]
- 12966《你不会找不到他》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:0
- 12985《雷铸徽记》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:3000
- 12987《放置霍迪尔之盔》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:3000
- 12994《猎杀间谍》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:9000
- 13001《打造霍迪尔之矛》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:9000
- 13006《粘滞清洁》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:3000
- 13011《斩除尤卡塔尔》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:3000
- 13046《喂饱安格里姆》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:21000
- 13106《黑色观察站》 req=77：exclusive_availability_condition；exclusiveTo=[13119, 13120]
- 13372《聚焦之虹的钥匙》 req=80：external_item_start_required
- 13374《炸翻天！》 req=77：server_version_availability_needs_confirmation
- 13375《英雄聚焦之虹的钥匙》 req=80：external_item_start_required
- 13420《永冻之冰》 req=77：reputation_condition_needs_route_state；minRep=霍迪尔之子:3000
- 13845《密封的毒药瓶》 req=70：external_item_start_required
- 24431《被浸透的配方》 req=70：external_item_start_required
- 24442《克瓦迪尔的进攻计划》 req=77：external_item_start_required
- 24554《残破的剑柄》 req=80：external_item_start_required

## 尚未由当前Journey选定的一次性服务器版本组

- 无。

## 普通任务 → 日常/重复生命周期组

- 首轮=13264《你的憎恶伙伴》；后续日常/重复ID=[13276]
- 首轮=13352《从天而“降”》；后续日常/重复ID=[13353]
- 首轮=13356《重新考验》；后续日常/重复ID=[13357]
- 首轮=13358《活动窃听器》；后续日常/重复ID=[13365]
- 首轮=13367《片刻不得安宁》；后续日常/重复ID=[13368]
- 首轮=12029《净化天灾巨魔》；后续日常/重复ID=[12038]
- 首轮=12820《亲密接触》；后续日常/重复ID=[12833]
- 首轮=12906《训诫》；后续日常/重复ID=[13422]
- 首轮=12925《维持传统》；后续日常/重复ID=[13425]
- 首轮=12971《迎接挑战者》；后续日常/重复ID=[13423]
- 首轮=12997《进入利齿之坑》；后续日常/重复ID=[13424]
- 首轮=13420《永冻之冰》；后续日常/重复ID=[13421]
- 首轮=12532《鸡飞狼跳！》；后续日常/重复ID=[12702]
- 首轮=12565《希姆埃巴的祝福》；后续日常/重复ID=[12567]
- 首轮=12572《神祗喜欢亮闪闪的东西》；后续日常/重复ID=[12704]
- 首轮=11866《敌人的耳环》；后续日常/重复ID=[11867]
- 首轮=11919《猎龙》；后续日常/重复ID=[11940]
- 首轮=12615《希姆托加的祝福》；后续日常/重复ID=[12618]
- 首轮=13413《展翅高飞！》；后续日常/重复ID=[13414]
- 首轮=12655《希姆鲁克的祝福》；后续日常/重复ID=[12656]
- 首轮=13092《占命卜运》；后续日常/重复ID=[13093]
- 首轮=13239《爆炸油》；后续日常/重复ID=[13261]
- 首轮=12433《寻找溶解剂》；后续日常/重复ID=[12434]
- 首轮=13279《化学常识》；后续日常/重复ID=[13281]

## 日常轮换同名组

- 12501《巡逻员》 / 12563《巡逻员》 / 12587《巡逻员》

## 技能 / 法术 Availability 门槛

- 12561《信任危机》：skill=None；spell=54197；specialization=None；ranks=None；status=impossible_or_excluded；reasons=['cold_weather_flying_excluded_by_route_policy']
- 12803《自然的力量》：skill=None；spell=54197；specialization=None；ranks=None；status=impossible_or_excluded；reasons=['cold_weather_flying_excluded_by_route_policy']
- 12888《E型检修员》：skill={1: 202, 2: 400}；spell=None；specialization=None；ranks=None；status=impossible_or_excluded；reasons=['requires_profession_or_skill']
- 12889《原型机控制台》：skill={1: 202, 2: 400}；spell=None；specialization=None；ranks=None；status=impossible_or_excluded；reasons=['requires_profession_or_skill']

## 日常 / 重复版本统计

- repeatable=151；daily=111；weekly=28；monthly=0。
- 宇宙层只生成首轮任务卡，不生成第二轮循环；同名版本由server_variant_audit单独去重/待确认。
