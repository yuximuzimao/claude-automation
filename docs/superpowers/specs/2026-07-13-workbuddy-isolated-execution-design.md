# WorkBuddy 最小投影执行与可回档设计

## 目标

把 WorkBuddy 限定为不受信任的**补丁生成器**，而不是可以接触完整项目或主工作区的执行器。它每次只能看到 Codex 按任务生成的一小组 Git 已跟踪文件，并只能在该投影副本中修改代码。

Codex 负责创建真实隔离分支、生成最小投影、启动本地看门狗、审查补丁、运行验证、提交、合并和回滚。用户只需说“把这个任务交给 WorkBuddy”；不需要手动创建分支、选模型或拼接命令。

## 审查结论与核心决策

原先的“WorkBuddy 直接在完整 Git worktree 中修改、再靠路径权限限制”的方案不够严。

实测发现：

1. Hy3 可以通过本机 WorkBuddy CLI 调用。
2. CLI 在 `HOME` 换成空目录后失去登录状态；单独设置 `CODEBUDDY_CONFIG_DIR` 也不能恢复认证。因此本机已登录 Home 是 CLI 宿主进程的必要可信边界。
3. 即使使用 `--setting-sources none`，CLI 仍会自动注入当前目录祖先中的 `AGENTS.md`。若 worktree 位于 `/Users/chat` 下，会把工作区级说明暴露给 WorkBuddy。
4. CLI 的 `--tools`、权限规则与 Bash 沙箱能约束模型可调用的能力，但不能把“完整工作区已经摆在它面前”变成最小可见集。

因此采用“双层隔离 + 最小文件投影 + Codex 补丁导入”，不采用“直接给完整 worktree”的方式：

```text
用户任务
  -> Codex 检查源分支干净、记录 base SHA
  -> Codex 在 /private/tmp 创建真实 integration worktree（仅 Codex 可用）
  -> Codex 从 allowlist 生成最小 projection；源仓库 .git 不复制，临时 baseline 元数据对 WorkBuddy 不可见
  -> WorkBuddy 只改 projection，不能运行 Bash、Git、浏览器、MCP 或子代理
  -> 本地 watchdog 写状态与补丁，不轮询 Codex
  -> Codex 校验并把补丁应用到 integration worktree
  -> Codex 审阅、测试、提交并 --no-ff 合并；否则保留补丁
```

这让“权限规则失效”时的最坏后果从“能看到完整工作区”收缩为“仍只能看到本次投影的文件”。

## 信任边界

### WorkBuddy 被视为不受信任

- 它的模型输出、工具调用、完成声明和退出码都不能作为验收依据。
- 它不能看到主工作区、真实 integration worktree、未跟踪文件、忽略文件、用户桌面或其他项目。
- 它不能运行 Git、Shell、浏览器、网页、MCP、桌面控制、插件、子代理、工作流或外部业务操作。

### CLI 宿主进程是最小可信计算基

本机 WorkBuddy CLI 必须使用真实 `HOME=/Users/chat` 才能读取已有登录状态。包装器会以 `env -i` 清空父进程环境，只保留 `HOME`、Node 所需 `PATH`、`TMPDIR`、语言环境和本次显式安全变量；不会把调用 Codex 的 token、代理、云账号或其他环境变量传入。

这不等于 WorkBuddy 二进制本身获得了“零权限”。任何以用户身份运行的第三方桌面 CLI 都属于可信计算基。若未来要把这个边界再降低到“即使 WorkBuddy 二进制被攻陷也不能读 Home”，必须使用独立 macOS 用户或外部容器；这不在本 Skill 中自动创建或修改。

模型层的实际能力由最小投影、无 Bash、严格工具白名单、空 MCP、关闭插件和路径权限共同约束。

## 每次任务的文件边界

### 两个目录，职责完全分开

| 目录 | 内容 | 可访问者 |
| --- | --- | --- |
| `/private/tmp/codex-workbuddy/integrations/<run-id>/repo` | 完整 Git integration worktree、真实分支和最终测试环境 | 仅 Codex |
| `/private/tmp/codex-workbuddy/projections/<run-id>/workspace` | 本次 allowlist 内的 Git 已跟踪文件、选定的项目 `AGENTS.md`、临时 baseline Git 元数据 | WorkBuddy 仅能通过受限工具访问 |

两个目录都是在 `/private/tmp` 下新建，父目录由包装器创建且不含 `AGENTS.md`。因此 WorkBuddy 不会继承 `/Users/chat/AGENTS.md` 或主工作区的其他祖先规则。

### 可见集与可写集

每份派工单必须有两个相对路径 allowlist：

- `read_paths`：WorkBuddy 可以读取的文件或目录。
- `write_paths`：WorkBuddy 可以改动或新建的文件或目录；它必须是 `read_paths` 的子集。

Codex 在启动前执行以下规则：

1. 将路径规范化，拒绝绝对路径、`..`、空路径和符号链接。
2. 只从 `git ls-files` 取 Git 已跟踪文件；不复制未跟踪、忽略或 Home 文件。
3. 永远排除 `.git`、`.mcp.json`、`.codebuddy/`、`.env`、密钥和认证文件；即使路径被误写入 allowlist 也拒绝任务。
4. 默认复制目标项目中位于 `read_paths` 内的 `AGENTS.md` / `AGENTS.mdc`，以保留项目编码约定；这些规则文件永远不在 `write_paths` 中。
5. 不复制其他工作区级文件、父目录规则、WorkBuddy 设置、插件、会话、记忆或依赖缓存。
6. 若任务需要符号链接、子模块、未跟踪生成物、额外依赖或未列入范围的文件，停止自动委派，改由 Codex 处理或让用户扩展 allowlist。

投影目录内会由 Codex 建一个临时 baseline Git 提交，只用于生成二进制安全补丁。WorkBuddy 没有 Bash 和 Git 工具，且其权限明确拒绝读取或写入 `.git`。

### 补丁导入

WorkBuddy 结束后，Codex：

1. 检查投影的变更路径全部属于 `write_paths`，并拒绝所有异常新增、删除、重命名、符号链接和 Git 元数据变更。
2. 从投影 baseline 导出 `patch.diff`；新文件先以 intent-to-add 纳入补丁。
3. 对真实 integration worktree 执行 `git apply --check --whitespace=error`，成功后才应用。
4. 再次检查 integration worktree 的 diff 范围、`git diff --check`、任务验收测试和人工代码审阅。

补丁不干净、范围越界、无法应用、测试失败或审阅不通过时，主分支完全不变；保留投影、integration 分支和 `patch.diff` 以便继续调查。

## WorkBuddy 会话能力

### 工具只允许代码读写

本次会话只暴露：

```text
Read, Grep, Glob, Write, Edit, MultiEdit
```

默认**不暴露 Bash**。代码编辑不需要 Shell；测试、格式化、Git、构建和依赖安装全部由 Codex 在补丁导入后执行。这样不会出现“允许一个测试命令，项目脚本又启动任意子进程”的旁路。

临时权限配置按 `pwd -P` 得到的物理 projection 路径生成：

- `Read`、`Grep`、`Glob` 只允许 `read_paths` 对应的物理路径。
- `Write`、`Edit`、`MultiEdit` 分别只允许 `write_paths` 对应的物理路径。
- 显式拒绝 `.git`、`.env`、密钥、Home、WorkBuddy 配置、AGENTS 写入和投影外的所有路径。
- 不使用泛化 `Write` 规则，也不使用 `--allowedTools Write`，因为它们实测会扩大为目录外写权限。

### 浏览器、网页、MCP 与扩展彻底关闭

每次都同时使用多层拒绝：

1. `--tools` 只列出六个代码文件工具，不含 `Bash`、`WebFetch`、`WebSearch`、`ToolSearch`、`Agent`、`Skill`、`Workflow` 或桌面/图像工具。
2. `--disallowedTools` 再次拒绝上述工具以及 `mcp__*`。
3. 使用空 `mcpServers` 配置和 `--strict-mcp-config`。
4. 设置 `CODEBUDDY_COMPUTER_USE_ENABLED=0`、`CODEBUDDY_DISABLE_WORKFLOWS=1`、`CODEBUDDY_DISABLE_CRON=1` 和 `CODEBUDDY_SKIP_BUILTIN_MARKETPLACE=1`。
5. 使用 `--setting-sources none`，并由 `--settings` 提供一次性设置：`disableAllHooks=true`、`disableWorkflows=true`、`agent-browser@codebuddy-plugins-official=false`、`playwright-cli@codebuddy-plugins-official=false` 和最小权限规则。
6. 不传 `--channels`、`--plugin-dir`、`--serve`、`--open`、`--remote-control`、`--bg`、`--swarm` 或 `-y`。

没有 Bash 意味着模型不能通过 `open`、`osascript`、curl、wget、Git、Node 或项目脚本绕过浏览器限制。

### 记忆、模型和 stdin

- 默认模型为 `hy3`；中型任务用 `--effort high`，大型任务用 `--effort max`。
- 设置 `CODEBUDDY_DISABLE_AUTO_MEMORY=1`、`CODEBUDDY_MEMORY_ENABLED=0`、`CODEBUDDY_TYPED_MEMORY_ENABLED=0`、`CODEBUDDY_TEAM_MEMORY_ENABLED=0`，不加载或写入自动记忆。
- 使用 `-p`、`--output-format stream-json`、`--max-turns` 和 `</dev/null`，避免交互 stdin 挂死。
- 不使用原生 `--bg`；本 Skill 自己在受控包装器中后台运行前台 CLI。

## 任务准入与派工单

### 允许委派

- 多文件功能、跨模块缺陷修复、已有明确验收点的重构。
- Codex 能在任务开始前列出最小 `read_paths`、`write_paths`，并能明确最终验证命令。

### 不允许委派

- 单文件小修、一次 Codex 编辑即可完成的改动。
- 真实业务操作、账号登录、网页点击、支付、提交、发布、发货、批量数据修改。
- 源分支有未提交改动且任务依赖这些改动。
- 需要新增依赖、联网下载、浏览器、桌面、MCP、Shell、未跟踪文件、符号链接或子模块。
- 无法形成最小可见集，或没有可执行验收方法。

每份派工单必须包含：

1. 仓库、base SHA、integration 分支与 projection 路径。
2. `read_paths`、`write_paths`、允许新增文件名和明确禁止范围。
3. 任务目标、关键接口、完成标准与项目 `AGENTS.md` 是否纳入。
4. 不联网、不浏览器、不 MCP、不 Bash、不 Git、不新增依赖、不读密钥、不触及业务系统。
5. Codex 的最终验证命令和合并门槛。

## 看门狗与状态

运行状态存放在 `~/.codex/state/workbuddy/<run-id>/`，权限为仅当前用户可读写，且不写入业务仓库：

- `job.json`：base SHA、分支、allowlist、投影、integration worktree、启动时间、模型和计划检查时间。
- `policy.json`、`mcp-empty.json`、`prompt.md`：每次生成的会话材料。
- `output.jsonl`、`stderr.log`：CLI 输出。
- `status.json`：`running`、`stalled`、`finished`、`failed` 或 `cancelled`。
- `watchdog.log`：进程、日志长度、输出时间和 projection diff 的采样摘要。
- `patch.diff`：导入前的完整补丁。

看门狗是本地后台进程，不会让 Codex 每分钟轮询。它只按以下节奏采样并在满足“进程存活但日志、输出和 diff 都持续无活动”时终止：

| 任务类型 | 首次建议查看 | 后续建议查看 | 本地采样 | 卡死阈值 |
| --- | ---: | ---: | ---: | ---: |
| 中型（3–8 文件） | 18 分钟 | 每 25 分钟 | 10 分钟 | 两次无活动且累计 40 分钟 |
| 大型（跨层/9–20 文件） | 28 分钟 | 每 40 分钟 | 15 分钟 | 两次无活动且累计 60 分钟 |
| 超大任务 | 必须拆分 | 按大型子任务 | 15 分钟 | 同上 |

Codex 不能在没有会话时主动唤醒自己，因此 `next_check_at` 是“用户下一次询问或本会话继续时的最低检查时点”，不是承诺自动发消息。用户随时说“看 WorkBuddy 状态”都能读取状态；不满一分钟时只返回最近一次本地采样，不触发额外轮询。

## Codex 验收、合并与回档

只有全部通过才能合并：

1. 目标分支干净，且仍停在记录的 base SHA。
2. 投影补丁和 integration diff 都只改 `write_paths`；没有设置、密钥、浏览器、MCP、依赖或锁文件的意外变化。
3. `git diff --check`、补丁应用检查和指定测试全部通过。
4. Codex 完成 diff 审阅，确认实现与目标一致；没有测试时只能交付补丁，不能自动合并。
5. Codex 在 integration 分支创建提交，再在目标分支执行 `git merge --no-ff`。

任何一项失败、目标分支已前进或有冲突时：不提交主分支、不自动 rebase、不自动解冲突；保留 integration 分支、projection 和 patch。

已合并任务会把 merge commit、分支名、base SHA 和 patch 写入运行状态。回档使用：

```bash
git revert -m 1 <merge-commit>
```

默认保留分支、worktree 和状态 14 天；不自动删除 Git 分支或工作目录，除非用户明确要求。

## 完成标准

1. 自然语言请求能创建一个最小投影 WorkBuddy 任务。
2. 每次任务都有独立 `read_paths` / `write_paths`，且投影不含主工作区的其他文件。
3. WorkBuddy 能看到选定的项目 `AGENTS.md`，但不能继承 `/Users/chat` 父目录规则或其他工作区内容。
4. WorkBuddy 不能调用浏览器、网页、MCP、桌面、插件、子代理、工作流、Bash 或 Git。
5. WorkBuddy 只能在 projection 的允许路径读写；无法写入 Home 的受控探针。
6. 看门狗按任务量采样，不会出现 Codex 每分钟查一次的行为。
7. 只有 Codex 能把已验证补丁导入、提交和合并；失败任务绝不影响目标分支。
8. 每次合并能由记录的 merge commit 和 patch 回档。
