# 鲸灵多账号 Session 管理

项目中文名：鲸灵多账号 Session 管理

## 用途

管理 `accounts.json` 中登记的鲸灵账号浏览器 Cookie，供 `aftersales-automation` 等工具复用。账号数量、编号、名称、手机号、启用状态均以 `accounts.json` 为准，不按连续编号或文档描述推断。
快麦（km）不在此管理，km 直接 `open -a "Google Chrome" <URL>` 即可。

## 常用命令

```bash
jl list              # 列出所有账号及状态
jl <编号>            # 注入账号 session 到 9222 自动化 Chrome
jl add <编号>        # 重新登录并保存 session（会自动填手机号）
jl inject <编号>     # 把 session 注入 9222 自动化 Chrome 并导航到售后列表
```

## 自动化 Chrome

自动化实例使用普通 Google Chrome，但必须以独立 profile 和 CDP 端口启动：

| 项 | 位置 / 值 |
|------|------|
| profile | `~/.chrome-automation-profile` |
| CDP 端口 | `9222` |
| 启动脚本 | `start-chrome-debug.sh` |
| 用户快捷方式 | `/Users/chat/Applications/自动化Chrome.app` |
| 开机启动 | `~/Library/LaunchAgents/com.jl.chrome-debug.plist` |
| 存储清理 | `~/Library/LaunchAgents/com.iroha.chrome-cleanup.plist` → `cleanup-chrome.js` |
| 启动日志 | `/tmp/chrome-debug.log`、`/tmp/chrome-launch.log` |

`自动化Chrome.app` 的入口是 `Contents/MacOS/applet` shell 脚本：调用 `start-chrome-debug.sh`，轮询 `http://127.0.0.1:9222/json/version`，再用 `open -a "Google Chrome"` 带到前台。不要再用 AppleScript `System Events` 查找 `first process whose name contains "Google Chrome"`；Chrome 已启动但进程列表未刷新时会触发“无效的索引”弹窗。

排障顺序：
1. `curl -fsS http://127.0.0.1:9222/json/version`
2. `tail -n 80 /tmp/chrome-launch.log`
3. `ps -axo pid,ppid,etime,pcpu,pmem,command | rg -i 'remote-debugging-port=9222|\\.chrome-automation-profile|Google Chrome for Testing'`

## jl add —— 重新登录流程

`jl add <编号>` 和后台 `--auto-save` 模式：
1. 用 Playwright 打开独立浏览器，自动跳到 `scrm.jlsupp.com/.../login`
2. 从 `accounts.json` 读取该账号的登录手机号 `phone`，自动填入手机号输入框（等 6 秒 input 出现）
3. 用户输入密码、完成登录、关闭教程弹窗
4. 在**售后系统网页**点击"确认保存"按钮（HTTP POST 触发 session 保存，浏览器自动关闭）

**禁止**用 Enter / stdin 触发保存——该模式靠 HTTP server（jl.js 内部在随机端口）等待前端请求。

`accounts.json.phone` 是登录账号本身，换登录账号时需要手动更新；它不等于 session 里的店铺/供应商联系人。`supplierInfo.supplierMobileList`、`contactMobile`、`supplierMobile` 可以在店铺信息不变时继续保留旧号码，禁止用这些字段自动覆盖登录手机号。重新登录保存只更新 session，并保留现有 `phone`。

## 文件说明

| 文件 | 用途 |
|------|------|
| `accounts.json` | 账号索引（编号→名称→登录手机号 `phone`→file 映射）。`phone` 独立维护，不从 `account{N}.json` 的 `supplierMobileList` / `contactMobile` / `supplierMobile` 反推 |
| `account*.json` | 各账号 Cookie（Playwright storageState 格式，以 `accounts.json` 为准；不要按连续编号推断） |
| `jl.js` | 主命令入口（已安装到全局 PATH） |
| `.relogin-port-<n>` | jl.js 写入的临时 HTTP confirm 端口文件（用后自动删除） |
