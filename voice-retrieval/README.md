# 语音取回

手机用豆包输入法语音输入，发送到公网 Worker；黑苹果按一个固定键，Hammerspoon 读取最新文本并用 `command+v` 粘贴到当前光标位置。也可以点击左下角小浮窗按钮，只把最新文本复制到剪贴板，适合远程控制电脑时使用。

项目正式名称是“语音取回”，项目目录是 `/Users/chat/claude/voice-retrieval`。Cloudflare Worker 的部署标识继续使用 `phone-voice-paste`，避免变更线上地址和 Durable Object 数据。

这个工具只保存一条 `latest`。没有轮询、没有队列、没有历史记录、没有 Workers KV。重复按固定键会重复粘贴同一条 latest，直到手机发送新文本覆盖它。

## 架构

- 手机：打开 Worker 页面，输入 token 和文本，点击发送。
- Cloudflare Worker：提供页面和 `/push`、`/latest` API。
- Durable Object：`VOICE_DO.idFromName("default")` 固定路由到同一个 `VoiceMailbox` 实例，保存一条 latest。
- 黑苹果：Hammerspoon 按键触发，请求 `/latest`，写剪贴板，然后模拟 macOS `command+v`。
- 远程控制：Hammerspoon 左下角浮窗按钮触发，请求 `/latest`，只写入剪贴板，不自动粘贴。

为什么不用 Workers KV：KV 是最终一致性，不适合“手机刚发送，电脑马上读取最新文本”的场景。Durable Object 单对象读写是这里最直接的强一致 latest 邮箱。

## 文件

- `src/index.js`：Worker、手机网页和 `VoiceMailbox` Durable Object。
- `wrangler.toml`：Worker 配置、`VOICE_DO` binding、SQLite-backed Durable Object migration。
- `hammerspoon/init.lua`：正式 Hammerspoon 配置。
- `hammerspoon/detect-key.lua`：按键检测脚本。
- `macos/com.chat.phone-voice-paste-hidutil.plist`：Calculator 键到 F13 的登录持久化配置。
- `test/worker.test.js`：Worker 行为测试。
- `docs/OPERATIONS.md`：这台机器当前生产配置、冒烟检查和故障排查。
- `.runtime/`：本机 token 和按钮位置，已由 `.gitignore` 排除。

## 当前本机配置

这台机器已经配置为：

- Worker URL：`https://phone-voice-paste.1366094310.workers.dev`
- Hammerspoon 主配置：`hammerspoon/init.lua`；`~/.hammerspoon/init.lua` 只是指向它的系统入口链接
- token 文件：`.runtime/phone-voice-paste-token`，权限应为 `600`
- 浮窗位置文件：`.runtime/phone-voice-paste-button-position.json`
- Calculator 键通过 `hidutil` 映射为 F13；配置真值在 `macos/`，`~/Library/LaunchAgents/` 只保留系统入口链接
- Hammerspoon 已设置为 macOS 登录后自动启动

不要把真实 token 写进仓库或文档。当前机器的运维检查见 `docs/OPERATIONS.md`。

## Cloudflare 部署

### 1. 准备 Wrangler

```bash
cd /Users/chat/claude/voice-retrieval
npm install
npx wrangler login
```

`npm install` 只用于安装 Wrangler。Worker 本身没有运行时依赖。

### 2. 确认 Durable Object 配置

项目已经配置好：

```toml
[[durable_objects.bindings]]
name = "VOICE_DO"
class_name = "VoiceMailbox"

[[migrations]]
tag = "v1"
new_sqlite_classes = ["VoiceMailbox"]
```

这里使用 `new_sqlite_classes`，因为 Workers Free plan 只能使用 SQLite-backed Durable Objects。Cloudflare 官方文档也建议新 Durable Object namespace 使用 SQLite storage backend。

### 3. 设置 SECRET

生成一个长 token，不要用弱口令：

```bash
openssl rand -base64 32
```

把生成的值写入 Worker secret：

```bash
npx wrangler secret put SECRET
```

按提示粘贴 token。这个 token 不会写进 `wrangler.toml`，Worker 代码里通过环境变量 `env.SECRET` 读取。

### 4. 部署 Worker

```bash
npx wrangler deploy
```

部署成功后，Wrangler 输出里会显示类似：

```text
https://phone-voice-paste.yourname.workers.dev
```

这个就是 `WORKER_URL`。也可以在 Cloudflare Dashboard 的 Workers & Pages 页面里点进 `phone-voice-paste` 查看 workers.dev 地址。

## Hammerspoon 安装与配置

### 1. 安装 Hammerspoon

下载并安装：

https://www.hammerspoon.org/

启动 Hammerspoon 后，打开：

`系统设置 -> 隐私与安全性 -> 辅助功能`

给 Hammerspoon 授权。没有这个权限时，`hs.eventtap.keyStroke` 无法正常模拟 `command+v`，也就不能自动粘贴。

### 2. 检测固定按键 keyCode

先用检测脚本找出你想用的固定键：

```bash
mkdir -p ~/.hammerspoon
ln -sfn /Users/chat/claude/voice-retrieval/hammerspoon/detect-key.lua ~/.hammerspoon/init.lua
```

在 Hammerspoon 菜单里点 `Reload Config`，然后按一下目标键。屏幕弹窗和 Hammerspoon Console 会显示：

```text
keyCode: 105
keyName: f13
```

记下 `keyCode`。如果按键没有任何弹窗，说明这个键可能被系统或键盘驱动拦截了。处理方式是在键盘驱动里把它映射成 F13、F14、F15 这类标准键，再重新检测。

### 3. 配置正式粘贴脚本

检测完成后恢复正式配置入口，并编辑项目源文件：

```bash
ln -sfn /Users/chat/claude/voice-retrieval/hammerspoon/init.lua ~/.hammerspoon/init.lua
```

编辑 `hammerspoon/init.lua` 顶部：

```lua
local WORKER_URL = "https://phone-voice-paste.yourname.workers.dev"
local TOKEN_FILE = os.getenv("HOME") .. "/claude/voice-retrieval/.runtime/phone-voice-paste-token"
local PASTE_KEY_CODE = 105
local PASTE_KEY_NAME = "f13"
```

推荐使用 `PASTE_KEY_CODE`。如果不想用 keyCode，可以把 `PASTE_KEY_CODE = nil`，再用 `PASTE_KEY_NAME = "f13"` 绑定标准键名。

保存后在 Hammerspoon 菜单里点 `Reload Config`。

脚本还带一个小浮窗按钮，当前尺寸是 `108 x 46`：

```lua
local FLOATING_BUTTON_ENABLED = true
local FLOATING_BUTTON_WIDTH = 108
local FLOATING_BUTTON_HEIGHT = 46
local FLOATING_BUTTON_MARGIN = 8
local FLOATING_BUTTON_LABEL = "语音取回"
```

点击这个按钮只会把 latest 复制到剪贴板，不会自动 `command+v`。这样远程控制电脑时，即使当前光标不在目标位置，也不会误粘贴；你可以自己切到目标窗口后再手动粘贴。

按钮可以直接拖动位置。拖动结束后，位置会保存到：

```text
/Users/chat/claude/voice-retrieval/.runtime/phone-voice-paste-button-position.json
```

下次重启 Hammerspoon 会自动恢复到上次的位置。轻点按钮是复制；按住移动是拖动，不会触发复制。

## 手机端使用

1. 用 iPhone Safari 打开 Worker 页面：`https://phone-voice-paste.yourname.workers.dev`
2. 第一次输入 token。
3. token 会保存到 Safari 的 `localStorage`，下次打开会自动填入。
4. 如果已有 token，页面加载后会自动 focus 到 textarea。
5. 在 textarea 里用豆包输入法语音输入。
6. 点“发送”。
7. 成功后页面显示“已发送”。

token 不会放在 URL 里，页面调用 `/push` 时使用：

```http
Authorization: Bearer <token>
```

## 电脑端使用

1. 把光标点到目标输入框或文档位置。
2. 按配置好的固定键。
3. Hammerspoon 执行 `POST {WORKER_URL}/latest`。
4. 如果有文本，写入 macOS 剪贴板并模拟 `command+v`。
5. 如果没有文本，弹窗显示“无文本”。
6. 如果 token 错，弹窗显示“Token 错误”。
7. 如果网络失败，弹窗显示“网络错误”。
8. 如果响应格式异常，弹窗显示“响应异常”。

远程控制时也可以点击“语音取回”按钮。按钮成功读取文本后会显示“已复制”，然后你自己按 `command+v` 粘贴。

## API

### `POST /push`

Headers：

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Body：

```json
{
  "text": "要粘贴的文本"
}
```

兼容 body token：

```json
{
  "token": "<token>",
  "text": "要粘贴的文本"
}
```

成功：

```json
{
  "ok": true,
  "createdAt": "2026-06-29T08:00:00.000Z"
}
```

### `POST /latest`

Headers：

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Body：

```json
{}
```

有文本：

```json
{
  "ok": true,
  "text": "要粘贴的文本",
  "createdAt": "2026-06-29T08:00:00.000Z"
}
```

无文本：

```json
{
  "ok": true,
  "text": null,
  "reason": "empty"
}
```

未授权：

```json
{
  "ok": false,
  "error": "unauthorized"
}
```

未授权响应不会返回文本内容。

## 本地测试

```bash
cd /Users/chat/claude/voice-retrieval
npm test
```

测试覆盖：

- `/push` 未授权不保存文本。
- `/push` 空文本返回明确错误。
- `/latest` 必须 POST。
- `/latest` 未授权不返回文本。
- 手机写入和电脑读取固定访问同一个 Durable Object 实例。
- JSON body token 兼容。
- 未知路由返回 JSON 错误。

## 安全说明

- 不要使用弱 token。
- token 不放 URL，避免浏览器历史、日志、Referer 泄露。
- Worker 不做公网自动粘贴；公网只保存和读取 latest。
- 只有本机 Hammerspoon 按键触发才会粘贴。
- 任何未授权响应都不会返回 latest 文本。
- Hammerspoon token 保存在项目的 `.runtime/phone-voice-paste-token` 文件里；该目录已被 Git 忽略，不要输出或强制提交。

## 官方参考

- Durable Objects getting started: https://developers.cloudflare.com/durable-objects/get-started/
- Durable Objects migrations: https://developers.cloudflare.com/durable-objects/reference/durable-objects-migrations/
- SQLite-backed Durable Object storage: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Durable Objects pricing / Free plan limits: https://developers.cloudflare.com/durable-objects/platform/pricing/
- Workers secrets: https://developers.cloudflare.com/workers/configuration/secrets/
