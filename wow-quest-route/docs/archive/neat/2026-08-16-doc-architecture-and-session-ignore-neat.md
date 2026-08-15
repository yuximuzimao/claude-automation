# NEAT阶段归档：2026-08-16 文档渐进式加载与sessions Git边界修复

状态：本次不改变北风苔原任务路线与玩家现场进度，只修复项目文档架构和Git持久化边界。长期永久规则已从两份超长总规则拆成按主题渐进式加载；根`.gitignore`中的`sessions/`误匹配已修成只忽略仓库根`/sessions/`，此前未被Git追踪的魔兽项目NEAT历史将补入版本库。

## N — 当前状态

- 当前首组实跑真值仍以`docs/verified-routes/CURRENT.md`为准，本归档不复制新的游戏进度。
- `docs/verified-routes/RULES.md`原约234行、`docs/ROUTE_ATLAS_RULES.md`原约290行，长期存在“一次加载过多不同主题规则”的问题。
- 根`.gitignore`原写`sessions/`，本意是保护仓库根浏览器/账号运行时`/sessions/`，但Git会把任意层级同名目录一起忽略，误伤：
  - `wow-quest-route/docs/verified-routes/sessions/`
  - `wow-quest-route/docs/video-extraction/sessions/`
- 修复前两个项目文档目录共33份Markdown，只有8月16日北风NEAT被人为`git add -f`追踪；其余32份长期只在本机。

## E — 本轮证据与修正

### 1. Git ignore范围修正

根`.gitignore`从：

` sessions/ `

改为：

` /sessions/ `

验证结果：

- `sessions/account1.json`仍由根`/sessions/`规则正确忽略；
- `wow-quest-route/docs/verified-routes/sessions/...`不再命中ignore；
- 原本未追踪的32份项目历史由31份verified-route文档和1份video-extraction文档组成；
- 对这32份Markdown执行邮箱、IPv4、API key/token/password/cookie、GUID样式扫描，未命中敏感模式。

因此今后NEAT不再依赖`git add -f`。根运行时session继续私有，项目Markdown session正常commit/push。

### 2. 永久规则改为渐进式路由

新增`docs/rules/README.md`作为永久规则唯一总入口，只负责最小公共规则和“当前任务该读哪份”的路由。

拆分主题：

- `leveling-and-selection.md`：经验预算、地图轴、任务取舍、随机掉落/护送/固定拾取。
- `execution-and-mechanics.md`：玩家执行文本、逐任务隐藏机制、人类可执行性、怪掉物触发、五开共享、洞穴/楼层/交通。
- `state-and-validation.md`：当前/从零路线分离、Journey、完整性审计、反馈写回、CURRENT/NEAT/rules边界、Git sessions边界。
- `route-atlas-optimization.md`：Route Atlas数据分层、Target Cluster/Spatial Instance、Hard Validator、插入/裁剪、声望、炉石、经验截止、优化器。
- `route-atlas-ui-and-assets.md`：唯一工作台、逻辑步骤、HUD、备注、缩放/播放、地图底图、中文标签和离线资源。

后续复审认为保留兼容入口仍会制造失效/漂移风险：项目内引用已迁移到`docs/rules/`后，旧`docs/verified-routes/RULES.md`与`docs/ROUTE_ATLAS_RULES.md`直接删除，不再维护兼容文件。

### 3. 阶段状态不得混入永久规则

本轮拆分时再次确认：

- 当前等级、任务栏、地图进度只在CURRENT；
- 某次R快照/局部顺序/服务器阶段数据只在NEAT/analysis/observations；
- “下一批1—57低随机掉落实验”仍是阶段实验，保留在CURRENT/todo/VETERAN材料，不写成永久硬规则；
- 服务器具体经验倍率从当前已验证证据读取，不在永久规则硬编码。

### 4. 项目入口按工作区习惯重新分工

- `SKILL.md`：Agent导航地图；DO FIRST固定为`todo → INDEX → 按工作流加载CURRENT或对应rules子文档`。
- `CLAUDE.md`：只保留稳定项目目标、Session启动、规则路由、数据/Git边界，不复制当前等级和旧阶段路线。
- `README.md`：人类项目概览、当前唯一入口、主要数据层和Route Atlas产品边界；删除“当前不使用HTML”“55级后切DK”等过期说明和大量易过期旧命令。
- `docs/INDEX.md`：文档/数据导航，不再重复整套规则正文。
- `tasks/todo.md`：只保留仍会改变下一步工作的事项。
- `tasks/lessons.md`：恢复为真正的临时教训收件箱；稳定内容迁入rules/ERROR-BOOK/task-library/observations/NEAT后删除。
- `ROUTE-DESIGN-PROCESS.md`：仍保留完整长SOP，但只在真正新建/修订路线时按需加载。
- `ERROR-BOOK.md`：仍保留专项错题本，只在路线生成/修订/审计时加载。

## A — 本阶段判断

### 1. “长文档”本身不是问题，默认加载过多才是问题

`ROUTE-DESIGN-PROCESS.md`与`ERROR-BOOK.md`继续保持专项完整性，因为它们类似售后项目的flow文档，只在对应工作流加载。永久通用规则必须分主题，不能让每个局部问题都先吞下全部路线、Route Atlas、前端和地图资源规则。

### 2. README、SKILL、CLAUDE、INDEX职责必须分离

- README给人类快速理解项目；
- SKILL告诉Agent从哪里开始、什么情况读什么；
- CLAUDE保存稳定会话/数据边界；
- INDEX做文档和数据导航；
- CURRENT只保存现在；
- rules只保存长期方法；
- NEAT保存阶段证据与恢复点。

任何当前状态被复制到多个入口都会产生漂移，应优先删除重复而不是同步更多副本。

### 3. 项目文档sessions是历史归档，不是运行时session

魔兽`docs/**/sessions/`目录名继续保留，不必为了避开Git规则改成archive；真正问题是根`.gitignore`范围过宽。修正为`/sessions/`后语义已清晰，历史引用也无需大规模改名。

## T — 下一恢复点

1. 进入魔兽项目先读`SKILL.md`、`tasks/todo.md`、`docs/INDEX.md`。
2. 继续玩家实跑时直接读`docs/verified-routes/CURRENT.md`，不因本次文档重构加载全部rules。
3. 遇到路线规则问题先读`docs/rules/README.md`，只加载当前主题子文档。
4. 新增跨地图永久规则时写对应`docs/rules/*.md`；阶段实验/当前状态继续留CURRENT/todo/NEAT，不回流到总规则。
5. 新NEAT可直接正常Git add/commit，不再使用`git add -f`。
