# ChatGPT 桌面端外部 Chrome 接入修复

归档日期：2026-11-05。本阶段已完成并停止继续排查。外部 Chrome 已能被 Codex 会话中的官方 Browser 插件发现、读取、接管并获取 DOM；当前日常使用优先走 Browser 插件 API。旧 CUA 标签页读取路径仍有超时，用户决定暂不继续处理。

## 目标与环境

目标是在不重装 ChatGPT、Chrome 或扩展、不迁移自动化 Profile、不影响售后系统的前提下，让统一的 ChatGPT 桌面 App 使用外部自动化 Chrome。

- ChatGPT 桌面 App：`/Applications/ChatGPT.app`，版本 `26.1029.61003`；Codex 与 ChatGPT 已是同一个桌面 App。
- Google Chrome：正式版 x86_64，版本 `156.0.8078.80`。
- 自动化 Profile：`~/.chrome-automation-profile`，Profile 名称 `Default`。
- Chrome 扩展 ID：`hehggadaopoacecdllhhajmbjkdcmajg`。
- Chrome 扩展版本：`1.26.1102.11740`。
- Native Host：`com.openai.codexextension`。
- Codex 官方插件：`chrome@openai-bundled`，版本 `26.1029.61003`。
- Browser 官方插件：`browser@openai-bundled`，版本 `26.1029.61003`。

此前已将内置 Browser 对 `https://scrm.jlsupp.com` 的 Browse 权限设为 Block。本轮没有修改该规则，也没有扩大为全局限制。

## 根因与修复

### 1. APP 与自动化 Profile 的识别路径不一致

扩展实际安装在 `~/.chrome-automation-profile/Default`。APP 默认检查的却是 Chrome 默认用户数据目录，因此没有发现自动化 Profile 中的扩展。

将当前 macOS 登录会话的启动环境变量设为：

```bash
launchctl setenv CODEX_CHROME_USER_DATA_DIR "$HOME/.chrome-automation-profile"
```

当前核验值为 `~/.chrome-automation-profile`。官方扩展检测脚本在显式指定自动化 Profile 后返回 `installed=true`、`enabled=true`。

### 2. 安装 APP 自带的 Chrome 插件

Chrome 插件已随 ChatGPT App 的 `openai-bundled` 插件市场提供，不需要从 GitHub 或第三方市场下载。通过官方本地插件市场安装：

```bash
codex plugin add chrome@openai-bundled --json
```

安装后 `chrome@openai-bundled` 已启用。Browser 插件 `browser@openai-bundled` 原本也在同一官方 bundled marketplace 中。

### 3. 为自动化 Profile 补充 Native Messaging Host 入口

标准 Native Messaging 注册目录中的原始 Host 清单位于：

```text
~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.openai.codexextension.json
```

原始清单存在，Host 名称、扩展授权 ID 和可执行文件路径均通过官方检查。Native Host V2 注册记录也存在于：

```text
~/Library/Application Support/OpenAI/Codex/chrome-native-hosts-v2.json
```

本机实际观察到：仅有默认目录中的清单时，使用自定义 `--user-data-dir` 的 Chrome 没有启动 Native Host。在自动化 Profile 下创建了指向原始清单的符号链接：

```text
~/.chrome-automation-profile/NativeMessagingHosts/com.openai.codexextension.json
  -> ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.openai.codexextension.json
```

创建后 Chrome 自动启动了 `ChatGPT for Chrome` Native Host，进程父级为自动化 Chrome，并建立了 `/tmp/codex-browser-use/` 下的本地通信 Socket。这个结论是本机实测结果，不将其泛化为所有 Chrome 版本或所有平台的通用注册规则。

曾因找不到旧式 `extension-host-config.json` 而怀疑 Host 配置缺失；后续确认当前版本使用 Native Host V2 注册记录，不能把该文件缺失当作故障。

## 验证结果

### 静态与启动检查

2026-11-05 收尾复核：

- `CODEX_CHROME_USER_DATA_DIR` 仍指向 `~/.chrome-automation-profile`。
- Profile 内符号链接存在，目标为标准注册目录中的原始 Host 清单。
- 官方 `check-native-host-manifest.js --browser chrome --json` 返回 `correct=true`，`missingExpectedOrigins=[]`。
- 官方 `check-extension-installed.js --browser chrome --json` 指定自动化 Profile 后返回 `installed=true`、`registered=true`、`enabled=true`、`disabled=false`，识别到版本 `1.26.1102.11740`。
- `codex plugin list --json` 确认 `chrome@openai-bundled`、`browser@openai-bundled` 均已安装并启用。
- Native Host x64 二进制的代码签名验证通过。

### 实际 Browser API 验证

- 修复前，`agent.browsers.list()` 只有 `mcpapps` 和 `iab`，没有 Chrome。
- 修复后，清单出现 `Chrome`，`type=extension`、`family=chrome`。
- `browser.user.openTabs()` 成功列出 5 个现有标签页。
- 对“群聊情报”执行 `browser.user.getTabContext(tab)` 成功：`kind=text`、`textLength=70869`、`truncated=false`。
- `browser.user.claimTab(tab)` 成功，随后 `tab.playwright.domSnapshot()` 成功，返回 `snapshotLength=16943`。

这证明 Browser 插件已经具备外部 Chrome 的标签页发现、页面上下文读取、标签页接管和 DOM Snapshot 读取能力。

## 未解决但暂不处理的边界

1. 旧 CUA 路径 `cua.getTab()` 曾分别在 30 秒和 20 秒后超时，并出现 `js execution timed out; kernel reset`。Browser 插件 API 已验证可用，因此不为修复备用 CUA 路径继续扩大改动。
2. Computer Use 设置页是否仍显示“未安装浏览器扩展程序”，修复后没有再次单独核验；不能据此声称设置页提示已恢复。
3. ChatGPT 普通聊天输入框没有出现 `@chrome` 候选项；Chrome 插件在 Codex 会话中可见并可实际调用。不要把普通 Chat 输入框候选项与 Codex Browser 后端可用性混为一谈。
4. 用户点击“立即试用”后，首次后端清单仍只有 `mcpapps` 和 `iab`；该操作本身没有完成 Chrome Native Host 注册。

用户决定：本轮到此收口；只有以后再次遇到实际问题时，才继续检查 CUA 超时或 Computer Use 设置页提示。

## 下次复查顺序

如外部 Chrome 再次不可用，先检查现有配置，不要直接重装：

1. `launchctl getenv CODEX_CHROME_USER_DATA_DIR` 是否仍指向 `~/.chrome-automation-profile`。
2. `~/.chrome-automation-profile/NativeMessagingHosts/com.openai.codexextension.json` 是否仍是指向默认 NativeMessagingHosts 清单的符号链接。
3. 运行 APP 自带的 `check-native-host-manifest.js` 和 `check-extension-installed.js`，后者指定自动化 Profile。
4. 用 `codex plugin list --json` 检查 `chrome@openai-bundled` 与 `browser@openai-bundled`。
5. 在 Codex 会话中调用 `agent.browsers.list()`；发现 Chrome 后，依次验证 `browser.user.openTabs()`、`getTabContext()`、`claimTab()` 和 `playwright.domSnapshot()`。

优先使用已经验证成功的 Browser 插件 API。不要因为 CUA 超时而重装扩展、迁移 Profile、绕过 CDP 安全限制，或改动售后系统。

## 回滚

本轮新增的系统级文件只有自动化 Profile 下的符号链接。若明确需要撤销，可删除该链接：

```bash
rm "$HOME/.chrome-automation-profile/NativeMessagingHosts/com.openai.codexextension.json"
```

如同时需要撤销 APP 的自定义 Profile 环境变量，可执行：

```bash
launchctl unsetenv CODEX_CHROME_USER_DATA_DIR
```

不要删除默认目录中的原始 Native Host 清单或 Native Host 可执行文件。移除符号链接会使本轮已验证的自动化 Profile Native Host 启动路径失效。

## 本轮未触及

- 未重新安装 ChatGPT App、Chrome 或 Chrome 扩展。
- 未修改 Chrome 自动化 Profile 内容或迁移 Profile。
- 未修改 `scrm.jlsupp.com` 的 Browse → Block 设置。
- 未修改售后系统、ERP、群聊分析、农场或其他业务项目。
- 未安装第三方 Browser Use 插件。
- 未使用 CDP 绕过浏览器安全限制。
- 未修改工作区代码、运行数据或项目业务配置。
