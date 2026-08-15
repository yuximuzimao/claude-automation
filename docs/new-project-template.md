# 新项目开工规范

适用范围：准备长期维护、包含多个工作流/模块、需要跨Session恢复，或涉及高风险业务的独立项目。一次性脚本和很小的个人工具可以简化，但仍必须明确入口、持久数据位置、临时文件清理策略和安全边界。

本规范同时约束 Claude Code 与 Codex。初始化不是“先建代码目录，以后再补文档”；下方初始化门禁未通过前，不算项目建立完成。

## 1. 文档职责先于目录数量

每类信息只保留一个权威来源：

| 信息类型 | 权威位置 | 禁止行为 |
| --- | --- | --- |
| Agent怎么进入项目、该读什么 | `SKILL.md` | 在README/CLAUDE重复一整套文件地图 |
| 稳定Session启动、安全边界、相关项目 | `CLAUDE.md` | 塞当前等级、当前工单、当前任务进度等易变状态 |
| 人类快速理解项目 | `README.md` | 把README变成当前状态数据库或历史日志 |
| 文档/数据在哪里 | `docs/INDEX.md` | 默认把所有业务规则都堆进INDEX |
| 当前尚未完成的工作 | `tasks/todo.md` | 长期保留已经完成的阶段历史 |
| 尚未归类的新教训 | `tasks/lessons.md` | 稳定后继续和正式规则重复维护 |
| 持续变化的当前状态 | `CURRENT.md`（位置由项目决定） | 在CLAUDE/README/SKILL复制当前状态 |
| 跨批次长期规则 | `docs/rules/` 或小项目的少量INDEX规则 | 从NEAT/日期文档反推永久规则 |
| 历史/阶段证据 | `docs/archive/` | 让历史文档继续充当当前入口 |
| 单对象/单任务事实 | 专门知识库、observations等 | 塞进通用规则正文 |

核心原则：**导航、当前状态、永久规则、历史证据必须分层。**

## 2. 标准目录结构

长期项目默认：

```text
project/
  README.md                 # 推荐：人类项目概览；不存当前状态
  SKILL.md                  # 必须：Agent导航地图，进入项目第一步读
  CLAUDE.md                 # 必须：稳定Session启动/安全/协作边界
  <cli/server/main>         # 项目主入口，按语言实际选择
  lib/ or src/              # 核心模块
  docs/
    INDEX.md                # 必须：文档/数据导航
    rules/                  # 多规则域项目使用；小项目可暂不创建
      README.md             # 规则路由，只告诉Agent当前任务该读哪份
      <topic>.md            # 按业务/技术主题拆分
    archive/                # 历史阶段、NEAT、旧设计；默认不用sessions命名
  data/                     # 结构化持久数据；按项目Git边界决定是否版本化
  tasks/
    todo.md                 # 必须：当前待办
    lessons.md              # 推荐：临时教训收件箱
  tests/ or test/           # 有可测逻辑时建立
```

项目存在持续变化的真实状态时，再建立一个明确的 `CURRENT.md`。可以是 `docs/CURRENT.md`、`docs/verified-routes/CURRENT.md` 等，但必须在 `SKILL.md` 明确它是唯一当前真值。

## 3. 什么时候必须拆 `docs/rules/`

`docs/INDEX.md` 默认是导航，不天然是“所有规则正文”。满足任一条件就拆：

1. 已出现两个以上相互独立的工作流/规则域，例如“业务决策规则”和“前端/资源规则”；
2. 回答一个局部问题时，读取INDEX会加载大量完全无关的规则；
3. 同一文件同时混入当前状态、长期方法、技术实现约束和历史案例；
4. Agent需要靠搜索长文档才能找到应该先读哪一节；
5. 规则文件继续增长时已经出现重复、冲突、兼容入口或旧规则难以删除。

拆分方式固定：`docs/rules/README.md` 只保存最小公共规则 + 路由表，具体规则按主题拆文件。不要创建第二个“大总规则”替代第一个。

## 4. SKILL.md 必要职责

```markdown
# <项目名> SKILL.md

## DO FIRST
1. 读 `tasks/todo.md`
2. 读 `docs/INDEX.md`（只导航）
3. 若有 CURRENT，按当前工作流决定是否读取
4. 若涉及规则判断，从 `docs/rules/README.md` 只加载对应主题
5. 核心入口：`<cli/server/main>`

## ENTRY MAP
| 文件 | 用途 | 何时读 |

## CORE FLOWS

## FAILURE PATTERNS

## PATHS
```

要求：
- DO FIRST体现**最小上下文**，不要把所有历史、所有规则列成每次必读；
- 新增/删除/移动/重命名核心文件时同步ENTRY MAP/PATHS；
- 当前状态只指向CURRENT，不在SKILL复制具体数值/任务列表。

## 5. CLAUDE.md 必要职责

```markdown
# <项目名>

项目中文名：<中文名>

## Session 启动
1. 读 `SKILL.md`
2. 读 `tasks/todo.md`
3. 读 `docs/INDEX.md`
4. 按SKILL分流CURRENT / rules / 专项文档

## 稳定项目目标与安全边界

## 规则文档（渐进式）
| 文档 | 加载时机 |

## 教训沉淀流程
- `tasks/lessons.md`：只放未归类新发现
- 稳定后迁到 rules / error book / knowledge / observations / CURRENT / archive 的正确层级，并从lessons删除

## 相关项目

## Git / 数据边界

## 目录说明
```

CLAUDE只保存跨Session仍成立的东西。任何“当前是第几级/当前处理到第几单/当前实验R17”都不应长期复制在CLAUDE里。

## 6. README / INDEX / CURRENT 的边界

- README：让人30秒知道项目做什么、当前主入口在哪、怎么开始；不要复制业务状态和易过期命令清单。
- INDEX：告诉Agent“哪里有什么”，不要求把所有规则正文集中在这里。
- CURRENT：只有项目确实存在持续变化状态时创建；一旦创建，其状态信息不得同时在README/CLAUDE/SKILL维护第二份。

## 7. 教训、永久规则与NEAT

`tasks/lessons.md` 是收件箱，不是历史数据库。

稳定后按归属迁移：
- 跨批次方法 → `docs/rules/`
- 重复错误模式 → error book / known pitfalls
- 单任务/单SKU/单对象事实 → 专门知识库/observations
- 当前现场真值 → CURRENT
- 一次性分析/阶段闭合/形成过程 → `docs/archive/`

NEAT属于阶段归档。它可以记录“当时发生什么、为何这样决定、从哪里恢复”，但永久规则必须已经上提到正式规则层；下一窗口不能只靠日期NEAT恢复长期规则。

新项目默认使用 `docs/archive/` 或 `docs/archive/neat/`，避免和运行时 `sessions/` 混淆。已有项目若使用 `docs/**/sessions/` 保存Markdown历史可保留，但必须确保Git正常追踪，并在SKILL/INDEX写清语义。

## 8. 文件存放与Git边界

- 试错/原型脚本 → 工作区 `_sandbox/`，不在项目里再建一套sandbox。
- 运行日志 → 默认console；确需落盘时放明确运行时目录并Git ignore。
- `data/` 的提交策略必须项目初始化时明确：哪些是源码/静态资源，哪些是实时状态/隐私/日志。不能只凭目录名一刀切。
- 每次新建文件先问：30天后是否仍需要？不需要 → `_sandbox/` 或不落盘。
- 移植代码时注明来源。
- 运行时、账号、认证、cookie、session、原始WTF/用户私密输入不得因“归档”进入Git。

### `.gitignore` 范围硬规则

只想忽略仓库根目录时，使用根锚定：

```gitignore
/sessions/
/_sandbox/
```

不要写会匹配任意层级同名目录的：

```gitignore
sessions/
```

每次新增/修改ignore后必须检查：
1. 一个预期应被忽略的样本确实被忽略；
2. 一个子项目中同名但应该版本化的样本没有被误伤。

项目Markdown文档被ignore默认视为异常。正常项目文档不应依赖 `git add -f`。

## 9. 文件移动/删除/拆分门禁

当旧权威文档被拆成新结构时：

1. 建迁移清单，逐章节确认内容落到哪里；
2. 补回不能被“概括掉”的硬字段/状态机/验证约束；
3. 搜索当前入口、代码生成器、SOP、todo、README、SKILL、CURRENT里的旧引用；
4. 更新 `SKILL.md` ENTRY MAP/PATHS 和 `docs/INDEX.md`；
5. 确认无明确外部消费者后，**直接删除旧权威文件**；
6. 不默认保留兼容跳转壳。只有明确存在外部工具/用户书签依赖时才允许兼容层，并写清退役计划；
7. 历史archive/NEAT可以描述“旧文件当时存在”，但不得继续给出读取旧路径的当前指令。

## 10. 新项目初始化门禁

用户说“新项目 / 从零开始 / 初始化 / scaffold”时，完成以下全部项目才算初始化完成：

- [ ] 创建项目目录；
- [ ] 创建 `SKILL.md`；
- [ ] 创建 `CLAUDE.md`；
- [ ] 创建 `tasks/todo.md`；
- [ ] 创建 `docs/INDEX.md`；
- [ ] 需要人类长期使用时创建 `README.md`；
- [ ] 若已有多个规则域，直接创建 `docs/rules/README.md` + 主题规则，不先造大INDEX；
- [ ] 若有持续变化状态，创建CURRENT并指定唯一真值；
- [ ] 明确代码入口、数据目录、测试入口、安全/隐私边界；
- [ ] 在根 `docs/project-aliases.md` 注册中文项目名/触发词；
- [ ] 在根 `AGENTS.md` 子项目入口表登记真实存在的最小必读文件；
- [ ] 检查 `.gitignore` 对新目录的匹配范围；
- [ ] 从空上下文做一次冷启动演练：`SKILL → todo/INDEX → CURRENT或按需rules → 核心入口`；
- [ ] 检查Git状态，确认文档会正常被追踪、运行时/敏感数据不会进入Git。

任一未完成，都只能称“代码/目录已创建”，不能称“项目初始化完成”。

## 11. 旧项目升级原则

不要求一次性重构整个工作区。旧项目继续正常工作；但只要某次任务涉及以下任一项，就同时做一次骨架合规检查：

- 目录重构；
- 大规则拆分；
- CURRENT/历史归档体系变化；
- 新增主要工作流；
- 大量文件移动/删除；
- Git ignore或持久数据边界变化。

缺 `SKILL/CLAUDE/todo/INDEX` 的长期旧项目应在这类结构性维护时补齐，而不是继续制造新的例外。
