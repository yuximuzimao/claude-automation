# Add Store Confirmation and Phone Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让新增店铺复用现有重新登录确认流程，并仅在首次新增保存后初始化登录手机号。

**Architecture:** 后端提取一个小型共享启动函数，让新增和重新登录使用相同的临时端口等待逻辑；新增入口额外传入 `--initialize-phone`。`jl.js` 保存 storageState 后只在该标记存在且账号没有手机号时，从 `supplierInfo.supplierMobileList[0]` 初始化手机号。

**Tech Stack:** Node.js、Express、Playwright、Node test runner

---

### Task 1: 共享登录会话启动逻辑

**Files:**
- Create: `lib/server/relogin-session.js`
- Create: `test/server/relogin-session-launcher.test.js`
- Modify: `lib/server/routes.js:638-687`

- [ ] **Step 1: 写失败测试**

测试共享启动函数会等待端口文件；新增模式追加 `--initialize-phone`，普通重新登录不追加。

- [ ] **Step 2: 运行测试确认 RED**

Run: `node --test test/server/relogin-session-launcher.test.js`

Expected: FAIL，因为 `lib/server/relogin-session.js` 尚不存在。

- [ ] **Step 3: 写最小实现**

实现：

```js
async function startReloginSession({ num, sessionsDir, initializePhone = false, fsImpl, spawnImpl, wait }) {
  const portFile = path.join(sessionsDir, `.relogin-port-${num}`);
  if (fsImpl.existsSync(portFile)) fsImpl.unlinkSync(portFile);
  const args = [path.join(sessionsDir, 'jl.js'), 'add', String(num), '--auto-save'];
  if (initializePhone) args.push('--initialize-phone');
  spawnImpl('node', args, { detached: true, stdio: 'ignore' }).unref();
  // 沿用当前 8 秒、200ms 轮询边界。
  // 端口未出现时抛出当前“登录窗口启动失败”错误。
}
```

将 `/accounts/add` 改为 `async`，创建账号后调用 `startReloginSession({ initializePhone: true })` 并返回 `num`；`/accounts/:num/relogin` 调用同一函数但不传首次标记。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `node --test test/server/relogin-session-launcher.test.js`

Expected: PASS。

### Task 2: 新增完成后进入现有确认状态

**Files:**
- Modify: `public/account-relogin-state.js`
- Modify: `public/app.js:2151-2161`
- Modify: `test/server/relogin-session.test.js`

- [ ] **Step 1: 写失败测试**

为 `registerCreatedAccountConfirmation(result, confirmSet)` 增加测试：合法 `result.num` 加入集合并返回账号编号；缺失编号时不修改集合。

- [ ] **Step 2: 运行测试确认 RED**

Run: `node --test test/server/relogin-session.test.js`

Expected: FAIL，因为函数尚未导出。

- [ ] **Step 3: 写最小实现**

```js
function registerCreatedAccountConfirmation(result, confirmSet) {
  const num = Number(result && result.num);
  if (!Number.isInteger(num) || num <= 0) return null;
  confirmSet.add(num);
  return num;
}
```

`addNewAccount()` 成功后调用该函数，再立即 `loadAccounts()`，从而复用已有“确认保存/取消”渲染。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `node --test test/server/relogin-session.test.js`

Expected: PASS。

### Task 3: 仅首次新增初始化手机号

**Files:**
- Modify: `lib/jl-account-config.js`
- Modify: `test/jl/account-config.test.js`
- Modify: `../sessions/jl.js:12,84-90,179-183`
- Data update: `../sessions/accounts.json` account 15

- [ ] **Step 1: 写失败测试**

测试 `extractInitialPhoneFromStorageState()` 能从 `scrm.jlsupp.com` 的 `supplierInfo.supplierMobileList[0]` 读取并转成字符串；测试 malformed/missing 返回空；测试 `buildSavedAccountConfig()` 有旧手机号时不覆盖、无旧手机号时接收首次手机号。

- [ ] **Step 2: 运行测试确认 RED**

Run: `node --test test/jl/account-config.test.js`

Expected: FAIL，因为提取函数和首次手机号参数尚不存在。

- [ ] **Step 3: 写最小实现**

在 `jl-account-config.js` 增加 storageState 提取函数，并让 `buildSavedAccountConfig(existing, fileName, num, { initialPhone })` 只在 `existing.phone` 为空时写入。

`jl.js` 识别 `--initialize-phone`；保存 storageState 后，仅在该标记存在时读取刚写入的 Session，提取手机号并传给配置合并函数。普通重新登录不带标记，因此不会重新提取或覆盖。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `node --test test/jl/account-config.test.js`

Expected: PASS。

- [ ] **Step 5: 补齐当前账号 15**

用相同提取函数从现有 `account15.json` 初始化 `accounts.json` 的账号 15 手机号，不打印原值；读回只验证手机号存在、格式合法，以及 name/note/file 映射未变化。

### Task 4: 回归验证与交付

**Files:**
- Verify all files above

- [ ] **Step 1: 运行定向测试**

Run: `node --test test/server/relogin-session-launcher.test.js test/server/relogin-session.test.js test/jl/account-config.test.js`

Expected: PASS。

- [ ] **Step 2: 运行完整测试**

Run: `npm test`

Expected: PASS。

- [ ] **Step 3: 静态检查和差异审查**

Run: `node --check ../sessions/jl.js && node --check lib/server/routes.js && git diff --check`

Expected: 全部退出码 0。

- [ ] **Step 4: 重启售后服务并验证进程**

按项目现有重启入口重启服务，使 `routes.js` 修改生效；只验证服务健康状态，不触发登录或店铺后台操作。
