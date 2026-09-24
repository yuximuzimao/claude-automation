# 新项目开工规范

适用范围：准备长期维护、包含多个工作流/模块、需要跨Session恢复，或涉及高风险业务的独立项目。一次性脚本和很小的个人工具可以简化，但仍必须明确入口、持久数据位置、临时文件清理策略和安全边界。

本规范同时约束 Claude Code 与 Codex。初始化不是“先建代码目录，以后再补文档”；下方初始化门禁未通过前，不算项目建立完成。

## 1. 文档职责以根CLAUDE为准

项目文档与工具的职责、SKILL/SOP/Owner关系、README/INDEX/Todo/CURRENT/Archive边界、渐进式披露、现役/历史二分和无兼容层原则，**唯一以工作区根`CLAUDE.md §项目结构与文档职责`为准**。

本模板只负责初始化骨架，不维护第二套职责定义。若本模板的任何示例与根CLAUDE冲突，以根CLAUDE为准并修正本模板。

## 2. 标准目录结构

长期项目默认：

```text
project/
  README.md
  SKILL.md
  CLAUDE.md
  <cli/server/main>
  lib/ or src/
  docs/
    INDEX.md
    <domain-sop-or-owner-files-as-needed>
    archive/
  data/
  tasks/
    todo.md
    lessons.md                # 可选：尚未归类的新教训收件箱
  tests/ or test/
```

项目存在持续变化的真实状态时，再建立一个明确的 `CURRENT.md`。可以是 `docs/CURRENT.md`、`docs/verified-routes/CURRENT.md` 等，但必须在 `SKILL.md` 明确它是唯一当前真值。

## 3. 什么时候拆SOP / Owner

不要为了统一目录样式强制创建`docs/rules/README.md`。

- 某个复杂领域存在多个相似但定义不同的输入，需要先分类再进入具体业务时，建立该领域专项SOP。
- 某个业务职责已经明确，就建立一个唯一owner入口；规则与正式操作默认放在同一owner。
- owner内容较小就保持单文件；只有信息量已经影响AI准确读取时，才在owner内部拆成README + 子文档。
- 外层SKILL/SOP只指向owner入口，不依赖owner内部是否拆成1个还是多个文件。
- `docs/INDEX.md`始终只做文件导航，不因为项目变大而升级成规则路由器。

## 4. SKILL.md 必要职责

```markdown
# <项目名> SKILL.md

## DO FIRST
1. 读 `tasks/todo.md`
2. 读 `docs/INDEX.md`（只导航）
3. 若有 CURRENT，按当前工作流决定是否读取
4. 若涉及语义分类或规则判断，按SKILL进入对应专项SOP或唯一owner
5. 核心入口：`<cli/server/main>`

## ENTRY MAP
| 文件 | 用途 | 何时读 |

## CORE FLOWS

## FAILURE PATTERNS

## PATHS
```

要求：
- SKILL沉淀高频、成熟、低歧义流程和项目一级入口；
- 同一关键词可能落到多个相似业务定义时，只分流到专项SOP，不在SKILL继续判断；
- DO FIRST体现最小上下文，不把所有历史、所有规则列成每次必读；
- 新增/删除/移动/重命名核心文件时按实际导航关系同步ENTRY MAP/PATHS；
- 当前状态只引用CURRENT，不复制具体状态。

## 5. CLAUDE.md 必要职责

```markdown
# <项目名>

项目中文名：<中文名>

## Session 启动
1. 读 `SKILL.md`
2. 读 `tasks/todo.md`
3. 读 `docs/INDEX.md`
4. 按SKILL分流CURRENT / 专项SOP / owner

## 稳定项目目标与安全边界

## 专项SOP / Owner（渐进式）
| 文档 | 加载时机 |

## 教训沉淀流程
- `tasks/lessons.md`：只放未归类新发现
- 稳定后迁到唯一owner / Error Book / knowledge / Observations / CURRENT / Archive的正确层级，并从lessons删除

## 相关项目

## Git / 数据边界

## 目录说明
```

CLAUDE只保存跨Session仍成立的东西。任何“当前是第几级/当前处理到第几单/当前实验R17”都不应长期复制在CLAUDE里。

## 6. README / INDEX / Todo / CURRENT

具体职责只读根`CLAUDE.md §项目结构与文档职责`。本模板只检查这些入口是否按项目需要建立，不在这里重新定义一遍。

## 7. 教训、永久规则与NEAT

`tasks/lessons.md` 是收件箱，不是历史数据库。

稳定后按归属迁移：
- 跨批次方法 → 对应唯一owner（可按需位于`docs/rules/`）
- 重复错误模式 → error book / known pitfalls
- 单任务/单SKU/单对象事实 → 专门知识库/observations
- 当前现场真值 → CURRENT
- 一次性分析/阶段闭合/形成过程 → `docs/archive/`

NEAT属于阶段归档。它可以记录“当时发生什么、为何这样决定、从哪里恢复”，但永久规则必须已经上提到正式规则层；下一窗口不能只靠日期NEAT恢复长期规则。

新项目默认使用 `docs/archive/` 或 `docs/archive/neat/`，避免和运行时 `sessions/` 混淆。archive是**版本化历史档案，不是日常活跃知识**：NEAT每次全文审查活跃区，但历史区默认只读archive索引、本轮新增/修改/移动的历史文件，以及CURRENT/当前任务明确需要回溯的最近历史。只有明确做历史考古时才全读archive。旧方案、被替代设计稿和一次性分析一旦退出当前工作流，应迁入archive，不继续和现行规则混在顶层docs。

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
5. 对仍被当前正式流程需要的能力/引用，先迁入新的唯一现役入口；
6. 迁移完成后，旧文件/工具只允许归档或删除，**不保留新旧兼容入口**；
7. 外部消费者若仍真实存在，就把它当作当前正式契约纳入现役owner/SOP并完成迁移，而不是继续依赖旧壳；
8. 历史archive/NEAT可以描述“旧文件当时存在”，但不得继续给出读取旧路径的当前指令。

## 10. 新项目初始化门禁

用户说“新项目 / 从零开始 / 初始化 / scaffold”时，完成以下全部项目才算初始化完成：

- [ ] 创建项目目录；
- [ ] 创建 `SKILL.md`；
- [ ] 创建 `CLAUDE.md`；
- [ ] 创建 `tasks/todo.md`；
- [ ] 创建 `docs/INDEX.md`；
- [ ] 需要人类长期使用时创建 `README.md`；
- [ ] 若存在需要语义分类的复杂领域，建立专项SOP；若存在长期业务规则/操作，建立对应唯一owner；是否拆目录按信息量决定；
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
