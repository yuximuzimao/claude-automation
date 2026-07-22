# 语音取回项目规则

请始终用中文交流。

## 项目边界

- 这个项目解决的是“手机公网语音输入 -> 本机按键或浮窗读取 latest”的最短链路，不做历史记录、队列、轮询或多设备同步。
- `CLAUDE.md` 顶部的 `项目中文名：语音取回` 和 `项目历史路径：/Users/chat/phone-voice-paste` 是用量统计元数据；迁移目录时必须同步更新，不能删除后在监控项目里写死映射。
- Cloudflare Worker 只暴露 `GET /`、`POST /push`、`POST /latest`；`/latest` 必须保持 POST-only。
- latest 存在同一个 Durable Object 实例：`VOICE_DO.idFromName("default")`。不要改用 Workers KV，KV 的最终一致性不适合刚写马上读。
- 认证只用 `SECRET`。token 优先走 `Authorization: Bearer <token>`，兼容 JSON body 的 `token` 字段；未授权响应不能返回文本内容。

## 本机配置红线

- 项目唯一真值目录是 `/Users/chat/claude/voice-retrieval`；不要在其他位置维护第二份源码、文档或运行状态。
- 真实 token 不写进代码、README、docs 或对话输出；本机 token 文件是 `.runtime/phone-voice-paste-token`，权限应保持 `600`，整个 `.runtime/` 必须保持 Git 忽略。
- `hammerspoon/init.lua` 是实际配置；`~/.hammerspoon/init.lua` 只允许作为指向它的系统入口链接。
- 当前按键方案是 `hidutil` 把键盘 Calculator 键映射为 F13，再由 Hammerspoon 绑定 F13。配置真值是 `macos/com.chat.phone-voice-paste-hidutil.plist`，`~/Library/LaunchAgents/` 只允许保留入口链接。
- Karabiner-Elements 不是当前依赖；不要把它写成必要步骤。若未来重新引入，先说明为什么 `hidutil` 不够用。

## 验证命令

```bash
cd /Users/chat/claude/voice-retrieval
npm test
```

本机状态检查：

```bash
ps -axo pid,command | rg -i 'Hammerspoon|phone-voice-paste'
hidutil property --get UserKeyMapping
launchctl list | rg 'phone-voice-paste'
stat -f '%Lp %N' /Users/chat/claude/voice-retrieval/.runtime/phone-voice-paste-token
```
