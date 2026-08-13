# Codex 插件 SessionEnd 超时提示排障

## 快速结论

看到下面这类提示时：

```text
clamping SessionEnd hook timeout to 3s in /Users/chat/.codex/plugins/cache/openai-codex/codex/<version>/hooks/hooks.json
```

含义不是钩子执行失败，而是插件为 `SessionEnd` 配置了 5 秒超时，超过 Codex CLI 允许的 3 秒上限。Codex 自动把它压到 3 秒并打印提示。

最小修复：只把提示所指向的**已安装缓存文件**中 `SessionEnd` 的 `"timeout": 5` 改为 `"timeout": 3`。`SessionStart` 保持 5 秒，`Stop` 保持原值。

## 为什么这样处理

- 不禁用 `SessionEnd`：该钩子负责关闭 broker、清理当前会话任务和状态；禁用可能留下后台资源。
- 不长期修改 `.codex/.tmp/marketplaces/openai-codex/`：这是市场源码检出目录，留下本地差异可能干扰后续升级。
- 只修警告中明确给出的缓存路径：影响最小，立即消除当前安装版本的提示。

截至 2026-08-13，官方 `openai/codex-plugin-cc` 的 `main` 分支仍把 `SessionEnd` 写为 5 秒，因此这是上游兼容问题，不代表本机配置损坏：

<https://github.com/openai/codex-plugin-cc/blob/main/plugins/codex/hooks/hooks.json>

## 定位与修复

先从提示中复制真实路径，不要假定版本号。把它赋给专用变量后读出相关片段，确认只有 `SessionEnd` 需要修改：

```bash
HOOK_FILE_FROM_WARNING="/完整复制提示中的/hooks/hooks.json"
sed -n '1,40p' "$HOOK_FILE_FROM_WARNING"
```

目标状态：

```json
"SessionStart": [{ "hooks": [{ "timeout": 5 }] }],
"SessionEnd": [{ "hooks": [{ "timeout": 3 }] }]
```

编辑时必须用带 `SessionEnd` 命令上下文的补丁，不能只替换文件里第一个 `"timeout": 5`，否则会误改 `SessionStart`。示意补丁：

```diff
 "command": "node \"${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs\" SessionEnd",
-"timeout": 5
+"timeout": 3
```

## 验证

1. 验证 JSON 格式：

   ```bash
   python3 -m json.tool "$HOOK_FILE_FROM_WARNING" >/dev/null
   ```

2. 读回确认：`SessionStart = 5`、`SessionEnd = 3`。
3. 启动一个新 Codex 会话，确认不再出现 `clamping SessionEnd hook timeout`。
4. 如果验证启动了任何服务或后台进程，按测试前的精确进程清单复查并确保零新增残留。
5. 检查市场源码没有被改脏：

   ```bash
   git -C /Users/chat/.codex/.tmp/marketplaces/openai-codex status --short
   ```

## 升级后复发

插件重装或升级会重建版本缓存。如果官方版本仍配置 5 秒，提示可能再次出现：

1. 以新提示里的路径为准找到新版本缓存。
2. 重复上面的单行修复和验证。
3. 不要给旧版本路径写定时补丁，也不要把缓存文件设为不可变；这会阻碍正常升级并掩盖版本变化。

## 搜索关键词

`clamping SessionEnd hook timeout` · `SessionEnd timeout 3s` · `codex-plugin-cc hooks.json` · `Codex 插件超时提示`
