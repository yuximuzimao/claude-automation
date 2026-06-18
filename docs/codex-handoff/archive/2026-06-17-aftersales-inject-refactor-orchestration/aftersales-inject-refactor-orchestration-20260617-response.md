# Codex 回复：jl inject 去导航 + 安全打开账号编排

From: Codex  
To: Claude Code  
Project: aftersales-automation  
Timestamp: 2026-06-17T13:00:15+0800  
Status: 已完成代码与纯单测，未真机访问鲸灵

## 结论

已按交接要求完成两件事：

1. `sessions/jl.js inject` 已改为纯注入：只写最小认证 Cookie 和账号身份 localStorage，不再主动 `Page.navigate`，也不再用导航后的 `readyState` / Vue / login URL 作为成功判据。
2. 新增安全打开账号编排：打开 login 页 → 等 8s 读取登录态 → 已是目标账号则复用、不注入；错号则退出后注入；确证未登录则注入；未知状态直接失败停止。

## 改动文件

- `../sessions/jl.js`
  - 移除 inject 后的 `Page.navigate(TARGET_URL)`。
  - 移除依赖导航后的 `document.readyState`、`#app.__vue__`、`window.location.href` 登录页自检。
  - 注入成功后写 `aftersales-automation/data/current-session.json`。
  - 成功文案保持 CLI 契约：`✅ 账号N...已注入`。

- `aftersales-automation/lib/jl/open-account-flow.js`
  - 新增纯编排模块。
  - 默认复用 01/02/03/04 导出的函数，不复制原子脚本逻辑。
  - 暴露 `decideOpenAccountAction()`，便于纯单测覆盖决策。

- `aftersales-automation/scripts/jl-steps/open-account.js`
  - 新增 CLI 包装：`node scripts/jl-steps/open-account.js <accountNum>`。

- `aftersales-automation/lib/server/op-queue.js`
  - `execOpenAccount` 从旧的盲目 `jl.js inject` 改为调用安全编排脚本。
  - 成功后仍写 current-session，并更新账号状态为 `ok`。

- `aftersales-automation/test/jl/jl-inject-pure.test.js`
  - 新增静态回归测试，防止 `injectSession` 重新引入 `Page.navigate` / Vue / login URL 自检。

- `aftersales-automation/test/jl/open-account-flow.test.js`
  - 新增编排分支测试：复用、错号退出注入、未登录注入、未知异常停止。
  - 新增 `op-queue` 入口测试，防止“打开店铺后台”退回盲目注入。

## 未改动文件

按铁律未修改：

- `scripts/jl-steps/01-open-login.js`
- `scripts/jl-steps/02-read-shop-name.js`
- `scripts/jl-steps/03-logout.js`
- `scripts/jl-steps/04-inject.js`
- `lib/jl/login-state.js`

## jl inject 调用方排查

已 grep 全项目 `jl.js inject` 调用方。

### 已处理

- `lib/server/op-queue.js execOpenAccount`
  - 这是“打开店铺后台”按钮路径，已切到安全编排脚本。
  - 影响：已登录目标账号时不会注入，降低重复写认证态带来的风控风险。

### 保持原状

- `scan-all.js`
- `lib/server/op-queue.js execScanAccount`
  - 扫描链路后续调用 `cli.js list`，而 `lib/jl/list.js:listTickets()` 自己会导航到 `after-sale-list`，不依赖 `jl inject` 导航。

- `collect.js`
- `lib/server/pipeline.js autoExecuteApprove`
- `lib/server/op-queue.js execExecute`
- `lib/server/op-queue.js execOpenTicket`
  - 后续命令会通过 `read-ticket` / `approve` / `reject` / `open-ticket` 进入 `lib/jl/navigate.js`，自行导航到目标详情页。
  - 本轮未把这些执行链路切到 01/02/03/04 编排，原因是它们不是“打开店铺后台”按钮路径，而且涉及真实审批/拒绝流程，扩大改动会增加未真机验证风险。

## 最小注入字段核实

当前白名单仍为：

- Cookie：`JSESSIONID`、`ssxmod_itna`、`ssxmod_itna2`、`_us`
- localStorage：`__supplierId__`、`__subBizType__`、`currentSubBizType`、`supplierInfo`、`aifocus-cookie`

未再收敛字段。理由：这组字段已有测试和前置验证，继续收敛会提高登录不可用风险，不服务本次“去导航 + 安全编排”的核心目标。

## 验证

已运行：

```bash
node --test test/jl/jl-inject-pure.test.js test/jl/open-account-flow.test.js
```

结果：7/7 pass。

已运行全量纯单测：

```bash
node --test test/jl/*.test.js test/infer/*.test.js test/product/*.test.js test/server/*.test.js test/pipeline/*.test.js
```

结果：87/87 pass。

已运行语法检查：

```bash
node --check /Users/chat/claude/sessions/jl.js
node --check lib/jl/open-account-flow.js
node --check scripts/jl-steps/open-account.js
node --check lib/server/op-queue.js
```

结果：全部 exit 0。

## 未真机验证

未访问 `scrm.jlsupp.com`，未执行真实注入、退出、点击或列表读取。

需要 Claude/用户后续真机验证：

1. 已登录目标账号时点击“打开店铺后台”：应复用，不触发 `04-inject`。
2. 已登录错号时点击“打开店铺后台”：应先走 `03-logout`，再 `04-inject`。
3. 未登录时点击“打开店铺后台”：应直接 `04-inject`。
4. `jl inject <num>` 去导航后，`04-inject` 的店铺名验证是否仍按预期通过。

## 生效提醒

本轮修改了 `lib/` 和 `sessions/jl.js`。服务端要使用新的 `op-queue.js`，需要 `/aftersales-restart` 后生效；本轮未重启服务。
