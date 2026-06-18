# Codex 任务交接：jl.js 注入重构（去导航）+ 安全注入流程编排

发起方：Claude Code
日期：2026-06-17
项目：aftersales-automation（鲸灵售后自动化）
分支：data-model-restructure

---

## 背景（必读）

鲸灵售后自动化重构第二步：实现「打开店铺后台」的**安全注入路径**，替代旧的危险注入（旧路径导致百浩账号 3 点打开后台时 IP 被封）。

旧危险注入的根因：注入复用停在旧账号的已登录 tab、不清旧态再 reload，页面先发旧店铺请求再跳新店铺 = 风控眼里的"多账号跳跃式切换"。

新安全路径的底层逻辑：**先检测能否复用，已登录目标账号就跳过注入直接用；错号才退出登录（走平台正规登出）→ 注入 → 验证**。

Claude Code 已在用户**逐步真机指挥**下完成 5 个原子模块并全部真机验证通过（见下"已完成且禁止改动"）。现在交给 Codex 做两个动作。

---

## ⚠️ 铁律（违反即风控封 IP / 破坏已验证成果）

1. **鲸灵域名（scrm.jlsupp.com）操作报错即停，绝不重试**。`lib/wait.js` 有 FORCE_NO_RETRY_DOMAINS。
2. **禁止在「已登录且店铺名匹配目标账号」时执行注入**（lesson #56）。注入是写操作，重复注入是风控异常信号。复用是常态，注入是例外。
3. **尽量不改动已测试通过的脚本**（01/02/03/04 + lib/jl/login-state.js），避免已验证成果失效。确需改动必须重新真机验证。
4. **不能真实访问鲸灵试错**。真机操作由用户指挥，Codex 只写代码 + 纯单测，不自行真机执行注入/点击。
5. 改 lib/ 或 sessions/jl.js 后需 `/aftersales-restart` 才在 server 生效（但本任务不要求 Codex 重启，交回 Claude/用户）。

---

## 已完成且禁止改动（已真机验证）

| 文件 | 职责 | 验证状态 |
|------|------|---------|
| `lib/jl/login-state.js` | 共享判据：`judgeLoginState`（三条件登录态）+ `matchShopName`/`shopKeyword`（关键字匹配）+ `READ_LOGIN_STATE_JS` | 单测 13/13 |
| `scripts/jl-steps/01-open-login.js` | 打开 login 页（像点收藏夹，新开标签直达，不注入不导航现有 tab） | 真机✓ |
| `scripts/jl-steps/02-read-shop-name.js` | 读登录态（等8s + 三条件判据 + 退出坐标常量） | 真机✓ + 单测 |
| `scripts/jl-steps/03-logout.js` | 退出登录（悬停展开下拉 + 真实左键点击 + 等8s三条件确证登出） | 真机✓ |
| `scripts/jl-steps/04-inject.js` | 注入账号 + 等8s + 店铺名关键字匹配验证 | 真机✓ |
| `test/jl/login-state.test.js` | 13 单测 | 全绿 |

### 关键已验证事实（编排和重构都要依赖）

- **登录态判据**（lib/jl/login-state.js `judgeLoginState`）：
  - 已登录：右上角店铺名 `<p class="readonly">` innerText 有值（**任何后台页面都存在，与所在页面无关**）
  - 未登录确证：读不到店铺名 **且同时**含 "商家登录" + "未注册的手机号登录成功后将自动注册"
  - 其它（不满足任一）：未知错误，报异常停止
- **店铺名匹配**（`matchShopName`）：note 取 `-` 前核心词（"百浩-RITEKOKO"→"百浩"），页面工商全称（"合肥百浩创展贸易有限公司"）includes 该核心词。已验证百浩/共途。
- **固定坐标**（真机验证，窗口尺寸不变时稳定）：
  - 退出登录悬停触发点（右上角店铺区 div.user 中心）：**(1358, 28)**
  - 退出登录按钮（菜单展开后）：**(1328, 244)**
- **等待规则**：打开页面/注入/退出后，统一**等 8 秒**再读取状态（平台登录态跳转是异步的，读早了落在 login 页读不到店铺名）。
- 鼠标移动用 `Input.dispatchMouseEvent`，每个动作后加 ~200ms 延迟稳定（不需要分段模拟轨迹）。
- 真实点击 = mousePressed + mouseReleased（button:'left', clickCount:1）。

---

## 动作 1：重构 sessions/jl.js inject — 去导航，纯注入

### 现状（sessions/jl.js injectSession，约 249-383 行）
- **最小注入已实现**（无需改动注入字段）：
  - Cookies：`filterAuthCookies` 白名单（4 个认证 cookie），跳过设备/网络指纹
  - localStorage：`filterIdentityLocalStorage` 白名单（5 个身份字段）+ GUIDE_DISMISSED 引导标记，保留本机设备/风控字段
- **要去掉的导航**（第 357 行）：`await send('Page.navigate', { url: TARGET_URL }, sid)` — 注入后主动导航到 after-sale-list 工单页。这违背 A2"停在注入后页面不主动导航别处"的本意（lesson #57）。
- **连带影响**：357 行之后的 readyState 轮询、Vue 初始化轮询、login URL 检测（约 358-381 行）都**依赖导航后的页面**来判断注入成功。去掉导航后这套自检失效。

### 要做的
1. **去掉第 357 行的 `Page.navigate`**（及其后依赖导航的 readyState/Vue/login 检测逻辑）。注入完成后**不主动导航任何页面**，停在当前 tab（注入只搬认证态，跳转交给平台/编排层）。
2. **替换成功判据**：去掉导航后，jl.js inject 不再靠"导航后 URL 是否 /login"判断成功。注入成功与否改由**编排层用 04 的店铺名判据**负责（jl inject 只要 setCookie + localStorage 注入无报错即返回成功）。
3. **保持 CLI 契约**：`jl inject <num>` 成功 exit 0 + 打印 `✅ 账号N已注入`；失败 exit 1。
4. **保留 saveSessionState**（坑#22：注入成功后写 data/current-session.json）。
5. **核实最小注入**：确认 filterAuthCookies/filterIdentityLocalStorage 白名单字段确实是最小必要集（当前看已是，若有冗余可收敛，但不要为了收敛破坏登录）。

### 风险与约束
- **`04-inject.js` 调用 `jl.js inject`**。改 jl.js 后 04 行为会变（注入后停平台默认页而非工单页）。但 **04 验证用店铺名判据、与页面无关**，理论上不受影响——Codex 改完必须用纯单测/逻辑确认 04 不受影响，**真机重测 04 由用户/Claude 做**，Codex 不真机。
- 旧系统是否还有别处调用 jl inject 依赖"注入后跳工单页"？需 grep 确认（scan-all.js / op-queue.js execScanAccount 等）。若有，要么这些调用方自己补导航，要么评估影响。**这是关键，去导航不能破坏 A1 扫描链路**（A1 注入后确实要去工单页）。
  → 建议：jl inject 去导航后，**A1 扫描链路在注入后自己导航到工单页**（导航与注入解耦）。Codex 需排查所有 jl inject 调用方并给出处理。

---

## 动作 2：编排 01→02→03→04 成完整安全注入流程

### 目标
新建编排模块（建议 `scripts/jl-steps/open-account.js` 或 `lib/jl/open-account-flow.js`），把已验证的原子步串成"统一前置进账号"流程：

```
输入：accountNum（目标账号）
1. 01 打开 login 页（新开标签直达，不注入）
2. 等 8s
3. 02 读登录态
   ├─ 已登录 + matchShopName(店铺名, note) 匹配 → 复用，不注入，结束（success: reuse）
   ├─ 已登录 + 店铺名不匹配（错号）→ 03 退出登录 → 等8s确证登出 → 04 注入目标账号 → 等8s验证 → 结束
   ├─ 未登录确证 → 04 注入目标账号 → 等8s验证 → 结束
   └─ 未知状态 → 报异常停止
4. 任一步鲸灵操作报错 → 报异常停止（不重试）
```

### 约束
- **复用 decideReuseOrReinject 思路**（计划里的纯函数判定，可新写也可用 login-state 现有函数组合）。
- **禁止已登录目标账号时注入**（铁律2）。
- **尽量直接调用已验证的 01/02/03/04 模块函数**（require 它们导出的 openLogin/readShopName/logout/inject），不要复制粘贴它们的逻辑，不要改它们。
- 编排层要有纯单测：mock 各原子步返回值，验证四个分支（复用/错号退出注入/未登录注入/未知异常）的调用顺序和决策正确。
- 真机端到端由用户指挥，Codex 只交付代码 + 纯单测。

---

## 交付要求
1. 动作1：改后的 jl.js + 所有 jl inject 调用方的影响排查与处理说明。
2. 动作2：编排模块 + 纯单测（覆盖4分支）。
3. 不动 01/02/03/04 + login-state.js（如必须动，说明原因 + 重测）。
4. 回写本文档同目录的 response 文件，列出：改了哪些文件、jl inject 调用方排查结果、编排分支测试结果、未真机验证的部分（留给用户）。
5. 全程不真机访问鲸灵。

完成后 Claude Code 检查 → neat 归档。
