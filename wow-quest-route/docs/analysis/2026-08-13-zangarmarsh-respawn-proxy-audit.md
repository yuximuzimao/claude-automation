# 赞加沼泽 Route Atlas world respawn proxy 审计

## 结论

本次产物是 **CMaNGOS WotLK/TBC 开源世界数据库代理**，不是 TitanReforged 真实刷新时间。正式 Route Atlas 数据以 WotLK-DB 为主，TBC-DB 只用于交叉验证；后续 Titan 现场观测具有更高优先级。

- WotLK-DB commit：`7d3ffab46ed8805678355fbdf77ccfaafb30c2ab`
- TBC-DB commit：`3f7f8f34067bf3c00c6fca8277f6f04f1ae6d12f`
- WotLK GameObject 覆盖：17/18（94.44%），1034 个出生行
- WotLK Creature 覆盖：352/395（89.11%），7210 个出生行
- 两版本刷新范围集合一致：137 个 entry
- 两版本刷新范围集合不一致：6 个 entry
- TBC 无对应出生数据：270 个 entry
- 无目标 SQL 被静默跳过；存在一个 contract 表示层限制，详见“刷新范围语义”。

## 请求范围与覆盖

目标 ID 由 `data/route-atlas/zangarmarsh-task-profiles.json` 自动遍历全部 `quests[*].components[*].sources[*]` 得到：`kind == object` 进入 GameObject，`kind == npc` 进入 Creature，然后去重。没有维护手工 ID 清单。

| 类型 | 请求 | WotLK 找到 | WotLK 缺失 | WotLK 出生行 | TBC 找到 |
| --- | ---: | ---: | ---: | ---: | ---: |
| GameObject | 18 | 17 | 1 | 1034 | 17 |
| Creature | 395 | 352 | 43 | 7210 | 126 |

WotLK 缺失 GameObject：`185497`。

WotLK 缺失 Creature（43 个）：`17894`, `18045`, `18047`, `18152`, `18154`, `18185`, `19885`, `19886`, `19887`, `19888`, `19889`, `19890`, `20091`, `20122`, `20164`, `20168`, `20169`, `20183`, `20184`, `20185`, `20188`, `20190`, `20620`, `20621`, `20622`, `20623`, `20624`, `20625`, `20626`, `21558`, `21842`, `21843`, `21914`, `22992`, `23035`, `24214`, `24846`, `26801`, `27206`, `27272`, `31665`, `31671`, `31681`。

TBC 缺失 GameObject：`185497`。TBC 缺失 Creature 共 269 个；完整状态已逐 entry 写入 JSON 的 `secondary_crosscheck.status`，不在报告重复铺开 269 个 ID。

## 数据库结构与 entry 解析

实际出生实例不在 template 描述表中：

| 类型 | 主表 | GUID | 直接 entry | 地图 | 坐标 | 刷新范围 |
| --- | --- | --- | --- | --- | --- | --- |
| Creature | `creature` | `guid` | `id` | `map` | `position_x`, `position_y`, `position_z` | `spawntimesecsmin`, `spawntimesecsmax` |
| GameObject | `gameobject` | `guid` | `id` | `map` | `position_x`, `position_y`, `position_z` | `spawntimesecsmin`, `spawntimesecsmax` |

另外解析了 `creature_spawn_entry(guid, entry)` 与 `gameobject_spawn_entry(guid, entry)`。CMaNGOS 会让一个出生 GUID 通过这两张表关联候选 entry；只查主表 `id` 会漏数据。WotLK 最终输出中，Creature 有 7009 个直接出生行和 201 个 spawn-entry 关联行；GameObject 有 368 个直接出生行和 666 个 spawn-entry 关联行。相同 `entry + guid` 已去重。

## 最终状态还原方式

本机没有 MySQL/MariaDB，因此未接触用户现有数据库。采用了隔离的 SQLite 投影重放：

1. 从压缩 Full DB 读取并完整导入 `creature`、`gameobject`、`creature_spawn_entry`、`gameobject_spawn_entry` 四张表；不是对 17 MB SQL 做 grep。
2. 严格复刻 `InstallFullDB.sh` 的仓库内容顺序：先 `Updates/[0-9]*.sql`，再 `Updates/Instances/[0-9]*.sql`，文件名按 shell glob 的字典序。
3. WotLK 共处理 94 个普通 update + 78 个 instance 文件，共执行 696 条出生表变更及其必要的临时表辅助 SQL；TBC 共处理 3 个普通 update + 55 个 instance 文件，重放 212 条四张目标表变更语句，并执行 6 条临时表生命周期语句，共 218 条。后 6 条用于快照及清理实例 GUID，不直接生成出生行，但属于官方实例覆盖流程的必要步骤。
4. 支持 `INSERT`、`INSERT ... SELECT`、`REPLACE`、`UPDATE`、`DELETE`、`@CGUID/@OGUID + N`、临时表和子查询。每个文件前后对目标 entry 做完整出生行指纹差分；任何目标表 SQL 执行错误都会中止。
5. `dev/` 默认 `DEV_UPDATES=NO` 且当前没有可应用 SQL；`archive/` 不属于正式安装流程。两个 DB 仓库自带的 ACID、locales、custom 不修改这四张出生相关表。

本报告中的“最终状态”严格指上述两个固定 commit 的 **DB 仓库内容状态**。`InstallFullDB.sh` 还可在之后读取调用者另行配置的 CMaNGOS core 仓库更新；本任务的数据源没有指定或固定对应 core SHA，因此未将外部 core SQL 混入，也不把结果表述为某个未固定 core checkout 的完整安装状态。

Full DB 基线分别是 WotLK `content_5771_c.22418` 与 TBC `content_0741_spillover_core_sync`。普通更新中的 `9999_Final_Misc_Cleanup_Queries.sql` 也按安装脚本实际执行。

WotLK `Updates/Instances/631_icecrown_citadel.sql` 有一处未定义变量 `@COGUID+1`。MySQL 会将其算为 NULL 并触发 `gameobject.guid` AUTO_INCREMENT；重放器按该语义处理。该行 entry 为 `201872`，不在本次请求集合，文件前后目标指纹未变化，因此不造成目标数据不确定。

临时重放器 SHA-256：`4a4ba71ffab5326fa5898cf56eb3065c01028d13c300a60f3a5434a9cfe11c60`。

## 后续 update SQL 对目标的影响

WotLK 普通 `Updates/*.sql` 没有改变目标出生行。`Updates/Instances/000_setup.sql` 会先删除实例地图中的旧数据，命中 75 个目标 Creature entry 与 2 个目标 GameObject entry；随后下列 instance 文件重建最终数据：

| WotLK update 文件 | GameObject entry | Creature entry |
| --- | --- | --- |
| `Updates/Instances/545_steamvault.sql` | `181278` | `17721`, `17722`, `17798`, `17800`, `17801`, `17802`, `17803`, `17805`, `21694` |
| `Updates/Instances/546_underbog.sql` | `181278`, `182054` | `17723`, `17724`, `17725`, `17770`, `17871`, `17882`, `17885`, `18105` |
| `Updates/Instances/547_slave_pens_WoTLK.sql` | `181278` | `17890`, `17893`, `17938`, `17957`, `17958`, `17959`, `17960`, `17961`, `21126`, `21127` |
| `Updates/Instances/548_serpentshrine_cavern.sql` | 无 | `21218`, `21220`, `21221`, `21224`, `21225`, `21226`, `21227`, `21228`, `21229`, `21230`, `21231`, `21232`, `21251`, `21263`, `21298`, `21299`, `21301`, `21339`, `21863` |
| `Updates/Instances/553_botanica.sql` | 无 | `17975` |
| `Updates/Instances/555_shadow_labyrinth.sql` | `181278` | 无 |
| `Updates/Instances/556_sethekk_halls.sql` | `181278` | 无 |
| `Updates/Instances/557_mana_tombs.sql` | `181278` | 无 |
| `Updates/Instances/558_auchenai_crypts.sql` | `181278` | 无 |
| `Updates/Instances/574_utgrade_keep.sql` | 无 | `23956`, `23960`, `23961`, `24069`, `24078`, `24079`, `24080`, `24082`, `24084`, `24085`, `28419` |
| `Updates/Instances/576_nexus.sql` | 无 | `26727`, `26728`, `26729`, `26734`, `26735` |
| `Updates/Instances/600_draktharon_keep.sql` | 无 | `26626`, `26635`, `26830` |
| `Updates/Instances/619_ahn_kahet.sql` | 无 | `30111`, `30179`, `30276`, `30277`, `30278`, `30285`, `30286`, `30287`, `30319` |

TBC 的同类重建影响 47 个目标 Creature entry 与 2 个目标 GameObject entry：

| TBC update 文件 | GameObject entry | Creature entry |
| --- | --- | --- |
| `Updates/Instances/545_steamvault.sql` | `181278` | `17721`, `17722`, `17798`, `17800`, `17801`, `17802`, `17803`, `17805`, `21694` |
| `Updates/Instances/546_underbog.sql` | `181278`, `182054` | `17723`, `17724`, `17725`, `17770`, `17871`, `17882`, `17885`, `18105` |
| `Updates/Instances/547_slave_pens.sql` | `181278` | `17890`, `17893`, `17938`, `17957`, `17958`, `17959`, `17960`, `17961`, `21126`, `21127` |
| `Updates/Instances/548_serpentshrine_cavern.sql` | 无 | `21218`, `21220`, `21221`, `21224`, `21225`, `21226`, `21227`, `21228`, `21229`, `21230`, `21231`, `21232`, `21251`, `21263`, `21298`, `21299`, `21301`, `21339`, `21863` |
| `Updates/Instances/553_botanica.sql` | 无 | `17975` |
| `Updates/Instances/555_shadow_labyrinth.sql` | `181278` | 无 |
| `Updates/Instances/556_sethekk_halls.sql` | `181278` | 无 |
| `Updates/Instances/557_mana_tombs.sql` | `181278` | 无 |
| `Updates/Instances/558_auchenai_crypts.sql` | `181278` | 无 |

## WotLK / TBC 交叉验证

比较依据是每个 entry 的唯一 `(spawntimesecsmin, spawntimesecsmax)` 集合，而不只比较 contract 中的单个标量。Creature 中 126 个两边都有数据的 entry 全部一致；6 个差异全部来自 GameObject：

| 类型 | entry | WotLK 范围（出生行） | TBC 范围（出生行） |
| --- | ---: | --- | --- |
| gameobjects | `181800` | 7200 (48 rows) | 600 (73 rows) |
| gameobjects | `181802` | 7200 (47 rows) | 600, 3600–7200 (82 rows) |
| gameobjects | `182031` | 300 (15 rows) | 180–300 (40 rows) |
| gameobjects | `182053` | 181, 600 (54 rows) | 180, 181, 600 (56 rows) |
| gameobjects | `182095` | 181, 300 (30 rows) | 180–300 (30 rows) |
| gameobjects | `182256` | 300 (25 rows) | 180–300 (40 rows) |

正式输出仍保留 WotLK 值，不因 TBC 看起来更“合理”而覆盖。

## 刷新范围语义

现有 contract 要求每个 spawn 有数值型 `respawn_seconds`，但 CMaNGOS 实际保存最小/最大两列。为同时满足读取接口与“保留原始值”：

- `respawn_seconds` 明确映射到原始 `spawntimesecsmin`，没有自行计算平均值或中位数；
- 每行额外保存 `respawn_seconds_min` 与 `respawn_seconds_max`，因此原始范围无损；
- TBC crosscheck 额外保存 `ranges_seconds`；`status` 按完整范围对比较，而非只看 minimum。

WotLK 中存在范围的目标行如下：

| 类型 | entry | 范围行数 | 原始范围（秒） |
| --- | ---: | ---: | --- |
| gameobjects | `181871` | 111 | 300–600 |
| gameobjects | `181872` | 111 | 300–600 |
| gameobjects | `181873` | 111 | 300–600 |
| gameobjects | `181874` | 111 | 300–600 |
| gameobjects | `181875` | 111 | 300–600 |
| gameobjects | `181876` | 111 | 300–600 |
| creatures | `22095` | 50 | 240–360 |
| creatures | `24015` | 4 | 60–120 |
| creatures | `25660` | 3 | 30–60 |

这不是 SQL 无法解析，而是现有单标量 contract 无法直接表达随机刷新范围。当前 Route Atlas 读取器会消费 `respawn_seconds`，因此这些范围行暂以最小值进入代理模型；上界仍完整保留，可供后续 contract 升级。所有输出标量均为数值且不小于 0。

## 抽查

- 成熟的孢子囊（GameObject `182069`）：WotLK 11 个出生点，全部 map 530，刷新 181 秒；TBC 同为 11 个、181 秒，状态 `same`。
- 暗泽鳗鱼（Creature `18138`）：WotLK 69 个出生点，全部 map 530，刷新 300 秒；TBC 同为 69 个、300 秒，状态 `same`。
- 蒸汽泵零件（GameObject `181871`）：主表 `id=0`，通过 `gameobject_spawn_entry` 解析出 111 个 map 530 出生点，范围 300–600 秒；证明 spawn-entry 联表不可省略。
- 盘牙工程师（Creature `17721`）：实例重建后 WotLK/TBC 均为 12 个 map 545 出生点、7200 秒。

## 复现命令与验收

```bash
git clone --depth 1 https://github.com/cmangos/wotlk-db.git /private/tmp/wotlk-db
git clone --depth 1 https://github.com/cmangos/tbc-db.git /private/tmp/tbc-db
git -C /private/tmp/wotlk-db rev-parse HEAD
git -C /private/tmp/tbc-db rev-parse HEAD

# 解析器从 task profiles 自动取 ID，导入 Full_DB 四张表，随后按 InstallFullDB.sh 顺序重放：
# sorted(Updates/[0-9]*.sql) + sorted(Updates/Instances/[0-9]*.sql)
# 最终查询：主表 id = target UNION spawn_entry.entry = target，再按 entry+guid 去重。

python3 -m json.tool data/route-atlas/world-respawn-proxy.json >/dev/null
python3 -m pytest -q tests/test_world_respawn_proxy.py
```

验收脚本另行核对：来源目标集合与输出 entry 集合完全相等、所有 `respawn_seconds >= 0`、无重复 `entry + guid`、coverage 计数一致，并抽查上述四个对象。
