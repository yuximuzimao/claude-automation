# CodexPro 永久 Worktree 访问 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `scripts/start-codexpro-full.sh` 每次启动都允许 GPT 打开全部 Superpowers worktree，同时保留用户已确认的 `bash=full` 信任模式。

**Architecture:** 启动脚本继续以 `/Users/chat/claude` 为默认根，但固定传入唯一的附加允许根 `/Users/chat/.config/superpowers/worktrees`。ChatGPT 仍需通过 `open_workspace` 打开具体分支；文件工具会受该根约束，完整 Bash 的非隔离语义会被明确写入共享工作区设计文档。

**Tech Stack:** Bash、Node.js `node:test`、CodexPro 0.28.5。

---

### Task 1: 为启动边界建立回归测试

**Files:**
- Create: `test/workspace/codexpro-worktree-access.test.js`
- Read: `scripts/start-codexpro-full.sh`

- [ ] **Step 1: 写失败测试，锁定允许根和禁止项**

```js
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const launcherPath = path.resolve(__dirname, '..', '..', 'scripts', 'start-codexpro-full.sh');

test('CodexPro launcher permanently allows Superpowers worktrees only', () => {
  const launcher = fs.readFileSync(launcherPath, 'utf8');

  assert.match(
    launcher,
    /readonly SUPERPOWERS_WORKTREE_ROOT="\/Users\/chat\/\.config\/superpowers\/worktrees"/,
  );
  assert.match(
    launcher,
    /exec codexpro start\s+\\\s*\n\s*--allow-root "\$SUPERPOWERS_WORKTREE_ROOT"/,
  );
  assert.doesNotMatch(launcher, /--allow-home\b/);
  assert.doesNotMatch(launcher, /--allow-root\s+\/Users\/chat\/\.config\b/);
});
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```bash
node --test test/workspace/codexpro-worktree-access.test.js
```

Expected: FAIL，因为现有启动脚本尚未定义 `SUPERPOWERS_WORKTREE_ROOT`，也未传入 `--allow-root`。

### Task 2: 固化启动参数

**Files:**
- Modify: `scripts/start-codexpro-full.sh`
- Test: `test/workspace/codexpro-worktree-access.test.js`

- [ ] **Step 1: 在环境变量设置后定义唯一的 worktree 根**

```bash
# Keep every Claude/Codex isolated project worktree available to the ChatGPT MCP app.
# CodexPro profiles do not persist --allow-root, so this belongs in the launcher.
readonly SUPERPOWERS_WORKTREE_ROOT="/Users/chat/.config/superpowers/worktrees"
```

- [ ] **Step 2: 仅向启动命令增加附加根**

```bash
exec codexpro start \
  --allow-root "$SUPERPOWERS_WORKTREE_ROOT"
```

保留现有 `cd /Users/chat/claude`、搜索结果上限、环境继承默认值和 profile 中的 `mode/write/tool-mode/bash` 设置；不加入 `--allow-home`，不覆盖用户已选择的 `bash=full`。

- [ ] **Step 3: 运行定向测试和 Shell 语法检查**

Run:

```bash
node --test test/workspace/codexpro-worktree-access.test.js
bash -n scripts/start-codexpro-full.sh
```

Expected: 测试通过，Shell 语法检查无输出且退出码为 0。

### Task 3: 同步使用边界和切换流程

**Files:**
- Modify: `docs/superpowers/specs/2026-06-22-codexpro-shared-workspace-design.md`
- Read: `docs/superpowers/specs/2026-07-13-codexpro-permanent-worktree-access-design.md`

- [ ] **Step 1: 更新访问范围**

将原先“仅 `/Users/chat/claude`”替换为主根加附加 worktree 根；说明内置文件工具可通过 `open_workspace` 打开具体 worktree，而 `bash=full` 是用户接受的受信任本机代理模式，不是操作系统级目录沙箱。

- [ ] **Step 2: 更新开工流程**

在 `open_current_workspace` 之后增加：任务指向隔离分支时，先调用 `open_workspace` 打开目标 worktree，随后在所有调用中传递返回的 `workspace_id`。保留主工作区的原有启动流程。

- [ ] **Step 3: 更新运行配置和验收标准**

将命令模式说明与当前 `bash=full` 一致；在验收清单中增加 `server_config.allowedRoots` 与目标 worktree 可打开、可读取交接文件的检查，并保留 Cloudflare quick tunnel 重启后需在网页 Settings → Apps 更新或重建 Dev 连接的说明。

### Task 4: 完整验证、提交与网页验收说明

**Files:**
- Read: `scripts/start-codexpro-full.sh`
- Read: `test/workspace/codexpro-worktree-access.test.js`
- Read: `docs/superpowers/specs/2026-06-22-codexpro-shared-workspace-design.md`

- [ ] **Step 1: 运行完整静态验证**

Run:

```bash
node --test test/workspace/codexpro-worktree-access.test.js
bash -n scripts/start-codexpro-full.sh
git diff --check
git diff --name-only main...HEAD
```

Expected: 定向测试通过，Shell 无语法错误，diff 无空白错误，变更仅包含启动脚本、测试和相关文档。

- [ ] **Step 2: 提交实现**

```bash
git add scripts/start-codexpro-full.sh test/workspace/codexpro-worktree-access.test.js docs/superpowers/specs/2026-06-22-codexpro-shared-workspace-design.md docs/superpowers/plans/2026-07-13-codexpro-permanent-worktree-access.md
git commit -m "feat(workspace): allow CodexPro Superpowers worktrees"
```

- [ ] **Step 3: 合入主工作区前检查**

在 `/Users/chat/claude` 中先确认这四个路径没有用户未提交改动；仅当无重叠时把实现提交 cherry-pick 回 main，绝不覆盖用户现有变更。

- [ ] **Step 4: 交付网页侧验收步骤**

重启时使用更新后的 `scripts/start-codexpro-full.sh`。在 ChatGPT 网页的 `设置 → Apps` 中更新现有 Dev 连接的服务器地址；若当前界面不支持编辑 endpoint，则创建新的 Dev 连接，验证后再删除旧连接。随后调用 `server_config` 和 `open_workspace` 验证根与 worktree 可见性。
