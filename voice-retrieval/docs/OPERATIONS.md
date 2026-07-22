# 语音取回运维手册

最后核对日期：2026-07-22

这份文档记录当前这台机器的实际落地状态。README 讲通用安装和使用；这里讲“现在已经配置成什么样、坏了怎么查”。

## 当前状态

- Worker 已部署到生产：`https://phone-voice-paste.1366094310.workers.dev`
- Worker 使用 `VOICE_DO` Durable Object 保存一条 latest。
- Hammerspoon 主配置是项目内 `hammerspoon/init.lua`，`~/.hammerspoon/init.lua` 是指向它的系统入口链接。
- 本机 token 放在项目 `.runtime/phone-voice-paste-token`，权限应为 `600`，且 `.runtime/` 已由 Git 忽略。
- 左下角浮窗按钮已启用：轻点读取 `/latest` 并复制到剪贴板，不自动粘贴；拖动会移动按钮并保存位置。
- 浮窗位置保存到项目 `.runtime/phone-voice-paste-button-position.json`。
- 键盘 Calculator 键通过 `hidutil` 映射为 F13，Hammerspoon 绑定 F13 后读取 latest 并自动 `command+v` 粘贴。
- `hidutil` 配置真值是项目内 `macos/com.chat.phone-voice-paste-hidutil.plist`；`~/Library/LaunchAgents/` 保留指向它的系统入口链接，label 是 `com.chat.phone-voice-paste-hidutil`。
- Hammerspoon 已设置为 macOS 登录后自动启动。
- Karabiner-Elements 不是当前方案依赖；当前 Homebrew cask 只保留 Hammerspoon。

## 日常使用

手机端：

1. 打开 Worker 页面。
2. 输入 token，页面会保存到 Safari localStorage。
3. 用豆包输入法语音输入文本。
4. 点“发送”覆盖 latest。

电脑端：

1. 按键盘 Calculator 键：读取 latest、写剪贴板、自动粘贴到当前光标位置。
2. 远程控制时点“语音取回”浮窗：读取 latest、只写剪贴板，之后手动粘贴。

## 冒烟检查

不要在输出里复述 token。需要验证授权时，从 token 文件读取：

```bash
curl -s -X POST 'https://phone-voice-paste.1366094310.workers.dev/latest' \
  -H "Authorization: Bearer $(tr -d '\n' < /Users/chat/claude/voice-retrieval/.runtime/phone-voice-paste-token)" \
  -H 'Content-Type: application/json' \
  --data '{}'
```

期望结果：

- token 正确：返回 `{"ok":true,...}`。
- token 错误：返回 `{"ok":false,"error":"unauthorized"}`，且不会返回 latest 文本。

Hammerspoon 状态：

```bash
ps -axo pid,command | rg -i 'Hammerspoon|[h]ammerspoon'
/usr/bin/log show --predicate 'process == "Hammerspoon"' --last 2m --style compact
```

按键映射状态：

```bash
hidutil property --get UserKeyMapping
launchctl list | rg 'phone-voice-paste'
```

token 文件权限：

```bash
stat -f '%Lp %N' /Users/chat/claude/voice-retrieval/.runtime/phone-voice-paste-token
```

期望权限是 `600`。

## 维护规则

- 修改 Worker 行为后运行 `npm test`。
- 修改 Hammerspoon 配置后直接编辑项目内 `hammerspoon/init.lua`，再重启 Hammerspoon，并读日志确认没有 Lua 报错。
- 修改 token 时只写项目 `.runtime/phone-voice-paste-token` 和 Cloudflare `SECRET`，不要输出或提交真实值。
- 如果云端 latest 误存了 token，要立即用一段无敏感内容的测试文本覆盖 latest，再继续测试。
- 若 Calculator 键失效，先查 `hidutil` 映射和 LaunchAgent；不要优先回到 Karabiner 路线。
