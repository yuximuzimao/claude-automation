# Codex 任务：A2 安全打开后台——前置「鲲灵 tab 数量门」

发起人：Claude Code（主驾驶）｜执行人：Codex｜审查人：Claude Code
日期：2026-06-17｜分支：`data-model-restructure`（直接在此分支改，勿开 worktree）

---

## 0. 一句话目标

在现有 A2「安全打开账号编排」**前面**加一道 tab 数量门：保证操作前鲲灵 tab 收敛到**唯一一个**，再读店铺/决策。消除「多个鲲灵 tab 时 `find` 命中错 tab」的风控隐患，并避免每次点按钮就新开 tab 累积。

## 1. 背景与现有链路（必读，勿重新摸索）

「店铺管理 → 打开店铺后台」按钮链路：
```
按钮 → routes API → lib/server/op-queue.js execOpenAccount(op)
     → spawnSync scripts/jl-steps/open-account.js <num>
     → lib/jl/open-account-flow.js openAccountFlow(num)
        → 01 openLogin（★每次都新开一个 tab）
        → 02 readShopName(targetId) 读登录态（内部等 8s）
        → decideOpenAccountAction → reuse / inject / logout-inject / error
        → 03 logout(targetId) / 04 inject(num)
```

关键事实（已读源码确认）：
- `scripts/jl-steps/01-open-login.js` **总是 `cdp.createTarget` 新开 tab**，不复用、不导航现有 tab。
- `sessions/jl.js` injectSession：`targets.find(t=>url.includes(scrm域名))` —— **找现有鲲灵 tab，命中就用，没有才新建**。
- `scripts/jl-steps/04-inject.js`：注入后也是 `find` 现有鲲灵 tab 读登录态验证。
- `scripts/jl-steps/03-logout.js logout(targetId)`：作用在传入的 targetId。
- `lib/cdp.js` **当前没有关闭 tab 的原语**（只有 ws.close 是关 websocket）。createTarget=`PUT /json/new?url`，activateTarget=`POST /json/activate/{id}`，getTargets=`GET /json`，均走本地 Chrome HTTP（port 9222）。

→ 推论：只要先把鲲灵 tab 收敛到唯一，jl.js inject 的 `find`、04 的 `find`、03 的 targetId 全部稳定命中同一个 tab，链路天然自洽。

## 2. 用户指定的流程分支（不可改）

打开店铺后台时，先数鲲灵 tab：
- **count == 0**：走原有流程 —— 01 openLogin 新开平台页 → 等待加载 → 02 检测店铺。
- **count == 1**：**不新开、不导航**，直接复用这唯一 tab → 02 检测店铺（02 内部已等 8s）。
- **count > 1**：关闭鲲灵 tab 到**只剩 1 个** → 复用剩下那个 → 02 检测店铺。

拿到登录态后，后续 decideOpenAccountAction（复用/退出注入/注入/异常）**保持不变**。

## 3. 交付物

### 交付物 1 — cdp 原语 + 2 个原子脚本

**(a) `lib/cdp.js` 新增 `closeTarget(targetId)`**
- 实现：`GET http://localhost:{CHROME_PORT}/json/close/{targetId}`（Chrome DevTools HTTP 端点）。
- 与 createTarget/activateTarget 同风格（Promise + timeout + error/timeout 处理）。
- 加入 `module.exports`（cdp 是单对象导出，挂上即可）。

**(b) `scripts/jl-steps/05-count-jl-tabs.js`**
- 导出 `async function countJlTabs()` → `{ success:true, count:N, tabs:[{id,url,title}] }`。
- 实现：`cdp.getTargets()` 过滤 `type==='page' && url.includes('scrm.jlsupp.com')`。
- 纯读取，无页面操作，无风控风险。失败返回 `{success:false,error}`。
- 带 CLI 入口（`node scripts/jl-steps/05-count-jl-tabs.js` 打印单行 JSON，success?0:1）。

**(c) `scripts/jl-steps/06-close-extra-jl-tabs.js`**
- 导出 `async function closeExtraJlTabs()` → `{ success:true, count:原数量, closed:[ids], keptTargetId }`。
- 逻辑：调 countJlTabs。
  - count==0 → `{success:true,count:0,closed:[],keptTargetId:null}`（无可关、无可留）。
  - count==1 → 不关，`keptTargetId = tabs[0].id`，closed=[]。
  - count>1 → **保留 tabs[0]**，对 tabs[1..] 逐个 `cdp.closeTarget(id)`，每个之间 sleep ~300ms；keptTargetId=tabs[0].id。
- 关 tab 报错即停（**不重试**），把已关的记进 closed 后返回 `{success:false,error,closed,...}`。
- 带 CLI 入口。

### 交付物 2 — 流程串联（`lib/jl/open-account-flow.js`）

新增前置解析函数并接入 openAccountFlow：

```
async function resolveJlTab(steps):
  const c = await steps.countJlTabs()
  if !c.success → return {success:false,error}
  if c.count === 0:
      const opened = await steps.openLogin()   // 新开
      if !opened.success → return {success:false,error}
      return {success:true, targetId: opened.targetId, opened:true}
  if c.count === 1:
      return {success:true, targetId: c.tabs[0].id, opened:false}   // 复用，禁导航
  // count > 1
  const closed = await steps.closeExtraJlTabs()
  if !closed.success → return {success:false,error}
  return {success:true, targetId: closed.keptTargetId, opened:false} // 复用，禁导航
```

- `openAccountFlow` 用 `resolveJlTab` 拿 targetId 替换原来「直接 steps.openLogin()」那段；其余（02→decide→reuse/inject/logout-inject）**完全不动**。
- `loadDefaultSteps()` 增加 `countJlTabs`(05) 与 `closeExtraJlTabs`(06)，便于单测 mock。

### 交付物 3 — 重启

**Codex 不要重启。** 只交付代码 + 单测 + 自测结果。重启 server 加载新逻辑由 Claude Code 审查通过后执行 `/aftersales-restart`（避免加载未审查代码）。

## 4. 风控铁律（违反即返工）

- `scrm.jlsupp.com` 行为操作**报错即停、绝不重试**（maxRetries=0）。
- **复用现有 tab 时绝不 `navigate`/`reload`**（把已登录后台页导回 login 正是风控异常行为）。count==1/count>1 分支只读、只关多余 tab，绝不导航保留的那个。
- 关 tab 走本地 Chrome HTTP，单次执行、报错即停。
- **不真机测试**（不连真 Chrome 跑 05/06/flow），只写单测。真机端到端由用户手动做。

## 5. 单测要求（`node --test`，mock cdp/steps，不连真 Chrome）

- `test/jl/count-jl-tabs.test.js`：mock `cdp.getTargets`，验证过滤鲲灵 page + 计数（0/1/多、含非 page、含非鲲灵 url 干扰项）。
- `test/jl/close-extra-jl-tabs.test.js`：mock getTargets+closeTarget，验证 count<=1 不调 closeTarget、count>1 只关 tabs[1..] 且 keptTargetId=tabs[0].id、closeTarget 报错即停。
- 扩展 `test/jl/open-account-flow.test.js`：mock steps，断言三分支——count0 调 openLogin、count1 **不调** openLogin 直接用 tabs[0].id、count>1 **不调** openLogin 调 closeExtraJlTabs 用 keptTargetId；之后仍正确进入 readShopName/decide。

## 6. 验收标准

1. `npm test` 全绿（原 87 不回归 + 新增全过）。
2. `node -e "require('./lib/jl/open-account-flow'); require('./scripts/jl-steps/05-count-jl-tabs'); require('./scripts/jl-steps/06-close-extra-jl-tabs'); require('./lib/cdp')"` 无报错。
3. 不改动 01/02/03/04 原子步内部逻辑（除非接口必需，需说明）。
4. 完成后在本文件末尾追加「## Codex 执行报告」：列改动文件、单测结果（贴 `npm test` 末尾统计）、任何偏离本 spec 的决定及原因。

## 7. 注意

- 直接在 `data-model-restructure` 分支改，勿开 worktree（最终要 server 真机加载，隔离反而坏事）。
- 改完**先别 commit**，等 Claude Code 审查；审查通过由 Claude 统一 commit + 重启。

## Codex 执行报告

改动文件：
- `lib/cdp.js`：新增 `closeTarget(targetId)`，调用本地 Chrome `GET /json/close/{targetId}`，请求错误/超时/HTTP 4xx+ 均返回失败。
- `scripts/jl-steps/05-count-jl-tabs.js`：新增只读统计鲲灵 tab 原子脚本，过滤 `type === 'page'` 且 URL 含 `scrm.jlsupp.com`。
- `scripts/jl-steps/06-close-extra-jl-tabs.js`：新增关闭多余鲲灵 tab 原子脚本，保留第一个，逐个关闭其余 tab，失败即停不重试。
- `lib/jl/open-account-flow.js`：新增并导出 `resolveJlTab()`，在 `openAccountFlow()` 读店铺名前先执行 tab 数量门；count==1/count>1 分支复用 targetId，不调用 `openLogin()`。
- `test/jl/count-jl-tabs.test.js`、`test/jl/close-extra-jl-tabs.test.js`、`test/jl/cdp-close-target.test.js`：新增单测。
- `test/jl/open-account-flow.test.js`：扩展 count==0/count==1/count>1 三分支单测。
- `SKILL.md`：同步新增 05/06 原子脚本入口和 PATHS。

验证结果：
```text
> aftersales-automation@1.0.0 test
> node --test test/**/*.test.js

1..62
# tests 98
# suites 17
# pass 98
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 325.932394
```

附加验收：
- `node -e "require('./lib/jl/open-account-flow'); require('./scripts/jl-steps/05-count-jl-tabs'); require('./scripts/jl-steps/06-close-extra-jl-tabs'); require('./lib/cdp')"` 通过。
- `node --check` 覆盖本轮改动源码和测试文件，通过。

偏离说明：
- 未真机测试、未重启 server、未 commit，按 spec 执行。
- `closeExtraJlTabs()` 增加可选 `{ sleepMs }` 参数，仅用于单测跳过 300ms 等待；默认行为仍为每次关闭后等待 300ms。
