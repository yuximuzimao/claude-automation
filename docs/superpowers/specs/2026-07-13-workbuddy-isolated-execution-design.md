# WorkBuddy 隔离执行与可回档设计

## 目标

把 WorkBuddy 限定为不受信任的代码执行器：它只能在一次性 Git worktree 中修改代码，不能操作浏览器、网页、MCP、桌面、外部业务系统或主工作区。Codex 负责派工、看门狗、验收、提交、合并和回滚。

用户只需说“把这个任务交给 WorkBuddy”，不需要手动创建分支或拼接命令。

## 核心决策

采用“独立 worktree + 临时最小权限 + Codex 合并门禁”，不采用原 Skill 的“直接在当前工作区改、最后靠 diff 回退”。

原因：回档不是发现问题后的补救，而是从一开始就让不受信任执行器没有机会污染主分支、未提交改动或个人目录。

## 执行拓扑

```text
用户任务
  -> Codex 检查主工作区干净、记录 base SHA
  -> Codex 创建 wb/<date>-<task> worktree
  -> WorkBuddy 在 worktree 中受限执行
  -> 本地看门狗写入状态，不打扰 Codex
  -> Codex 到预定时间读取状态、审阅 diff、运行验证
  -> 通过：Codex 自己提交并 --no-ff 合并
  -> 失败：不合并，保留 worktree、分支和 patch
```

WorkBuddy 没有 Git 写权限，不能 commit、merge、push、rebase、reset 或修改 `.git`。

## 任务准入

### 允许委派

- 多文件功能、跨模块缺陷修复、已有明确验收点的重构。
- 用户能提供目标仓库和至少一个验证命令；没有验证命令时，Codex 必须先识别项目现有测试或将任务降级为只产出补丁、不自动合并。

### 不允许委派

- 单文件小修、一次 commit 即可完成的改动。
- 真实业务操作、账号登录、网页点击、支付、提交、发布、发货、批量数据修改。
- 主工作区有未提交改动，且任务依赖这些改动。此时不能静默复制未提交状态；应要求用户先提交/暂存，或由 Codex 直接处理。
- 需要新依赖、联网下载、外部 API、浏览器或桌面自动化的任务，除非用户单独授权并重新设计权限边界。

## 每次运行的隔离规则

### 文件范围

包装器用 `pwd -P` 取得 macOS 的物理路径，并按该路径动态生成临时权限配置：

- 允许 `Write`、`Edit`、`MultiEdit` 分别匹配 `//<physical-worktree>/*` 与 `//<physical-worktree>/**/*`；每种编辑工具都必须有自己的物理路径规则。
- 工作区内 Read/Grep/Glob 可用；显式拒绝 `.env`、密钥、SSH、Git 元数据、CodeBuddy/WorkBuddy 配置与用户主目录敏感位置。
- 禁止 `Write` 泛化规则和 `--allowedTools Write`，因为它们会扩大为目录外写权限。
- 权限配置只作为本次 CLI 参数或运行状态文件存在，不写入用户的全局 WorkBuddy 配置。

### 工具与浏览器

本次 WorkBuddy 会话只暴露：`Read`、`Grep`、`Glob`、`Write`、`Edit`、`MultiEdit` 和受限 `Bash`。

同时执行以下防线：

1. `--tools` 不包含 `WebFetch`、`WebSearch`、`ToolSearch`、`Agent`、`Skill`、`Workflow`、图像/视频工具或桌面控制工具。
2. 使用空 MCP 配置和 `--strict-mcp-config`，阻断所有 MCP 工具。
3. 在临时 settings 中禁用 `agent-browser@codebuddy-plugins-official` 与 `playwright-cli@codebuddy-plugins-official`。
4. 设置 `CODEBUDDY_COMPUTER_USE_ENABLED=0`。
5. 权限 deny 同时包含 `WebFetch`、`WebSearch`、`ToolSearch`、`Agent`、`Skill`、`Workflow` 和 `mcp__*`。
6. Bash 只按派工单列出精确的测试命令；不得给 `Bash` 泛化放行，因此不能通过 `open`、`osascript`、curl、wget、git 或脚本绕过浏览器限制。

### Bash 沙箱

即使测试命令本身被精确放行，项目脚本也可能继续启动子进程。因此每次运行还必须启用 Bash 沙箱：

- `sandbox.enabled=true`，只读写 worktree；Bash 子进程不获得主工作区或 Home 写权限。
- `sandbox.allowUnsandboxedCommands=false`，禁止模型用 `dangerouslyDisableSandbox` 逃离沙箱。
- 不配置 `excludedCommands`，避免 Git、Docker、`open` 或其他命令退回宿主机。
- Bash 网络默认不放行；模型 API 连接由 WorkBuddy 主进程完成，不由沙箱中的测试命令完成。

因此“允许 `npm test`”不等于允许该脚本在用户机器上任意执行；它只能在 worktree 和无网络的 Bash 沙箱中运行。

模型连接本身仍会访问 Hy3 服务；禁止的是 WorkBuddy 作为智能体访问网页、浏览器、MCP 和桌面。

### 记忆与模型

- 默认模型：`hy3`；中型任务使用 `--effort high`，跨层大任务使用 `--effort max`。
- 每次委派设置 `CODEBUDDY_DISABLE_AUTO_MEMORY=1`，不加载或写入自动记忆，不改用户 GUI 的长期记忆设置。
- 使用 `-p` 和 `</dev/null`，避免交互 stdin 挂死。
- 不使用 WorkBuddy 原生 `--bg`，因为该模式会隐式跳过权限检查。

## 依赖与测试前提

WorkBuddy 不得安装依赖或下载构建产物。新 worktree 缺少测试依赖时，Codex 只能使用已经存在的离线、可复现依赖方案；否则把任务标记为“无法完成自动验证”，保留补丁但禁止自动合并。不能为让测试跑通而静默执行 `npm install`、`pip install`、`cargo fetch` 或类似联网命令。

## 派工单

每份派工单必须包含：

1. **上下文**：仓库、base SHA、工作区路径、允许改动的目录、关键类型/接口。
2. **任务**：可验证的模块级目标、允许变更的文件范围、禁止变更的文件范围。
3. **约束**：不联网、不浏览器、不 MCP、不 Git、不新增依赖、不读密钥、不碰业务系统。
4. **验证**：精确允许的测试命令、预期结果和 Codex 最终验收条件。

WorkBuddy 必须在最终输出中说明改了什么、跑了什么、失败项是什么；该输出不是验收依据，最终以 diff 与测试实证为准。

## 看门狗与状态

运行状态保存在 `~/.codex/state/workbuddy/<run-id>/`，不写入业务仓库。目录包含：

- `job.json`：目标分支、base SHA、worktree、允许命令、启动时间与下次检查时间。
- `output.jsonl` / `stderr.log`：本次进程输出。
- `status.json`：`running`、`stalled`、`finished`、`failed`、`cancelled`。
- `watchdog.log`：进程、日志、CPU、diff 的采样摘要。
- `patch.diff`：验收前保存的完整变更补丁。

看门狗在本地采样，不让 Codex 每分钟查询：

| 任务类型 | Codex 首查 | 后续查看 | 本地采样 | 卡死阈值 |
| --- | ---: | ---: | ---: | ---: |
| 中型（3–8 文件） | 18 分钟 | 每 25 分钟 | 10 分钟 | 两次无活动且累计 40 分钟 |
| 大型（跨层/9–20 文件） | 28 分钟 | 每 40 分钟 | 15 分钟 | 两次无活动且累计 60 分钟 |
| 超大任务 | 必须拆分 | 按大型子任务 | 15 分钟 | 同上 |

不能只因 stdout 为空杀进程；需要同时观察进程存活、日志/CPU 活动和 worktree diff。卡死后保存半成品、写状态并终止 WorkBuddy，不自动重派。

## Codex 验收与合并门禁

只有全部通过才自动合并：

1. 目标主工作区干净，且仍停在启动时记录的 base SHA。
2. WorkBuddy worktree 的 diff 只改允许范围；没有 `.git`、配置、密钥、浏览器、MCP、依赖或锁文件的意外变化。
3. `git diff --check` 通过。
4. 派工单指定的测试全部通过；无测试时只能输出补丁，不能自动合并。
5. Codex 完成 diff 审阅，确认实现与任务目标一致。

通过后由 Codex：

1. 在 WorkBuddy 分支创建提交。
2. 在原目标分支执行 `git merge --no-ff`。
3. 保存 merge commit、分支名和 patch 到运行状态。

任何一项失败、目标分支已前进或出现冲突时：不提交主分支、不自动 rebase、不自动解决冲突；保留 worktree 和分支，报告可继续检查的位置。

## 回档与清理

- 已合并：使用记录的 merge commit 执行 `git revert -m 1 <merge-commit>`；WorkBuddy 分支默认保留，不自动删除。
- 未合并：直接保留 worktree、分支和 `patch.diff`；用户可要求 Codex 继续修复或手动丢弃。
- 运行状态默认保留 14 天；清理只删除已合并且超过保留期的状态文件，不删除 Git 分支或 worktree，除非用户明确要求。

## 完成标准

1. 通过自然语言请求可以创建一次受限 WorkBuddy 任务。
2. WorkBuddy 不能看到或调用浏览器、网页、MCP、桌面、Git 或任意 Bash。
3. WorkBuddy 在 worktree 中能读写允许的根目录与嵌套文件，不能写入 Home 的受控探针目录。
4. 看门狗按任务量写出 `next_check_at`，不会出现一分钟轮询。
5. 验收通过后只有 Codex 能提交和合并；失败任务不会影响主分支。
6. 每次合并都能由记录的 merge commit 和 patch 回档。
