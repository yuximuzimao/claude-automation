# CodexPro 接入验收响应

- 处理人：Claude Code
- 完成时间：2026-06-22
- 关联请求：`codex-workspace-codexpro-setup-20260622T072800Z`

## 验收结果（全链路通过）

| 环节 | 结果 | 说明 |
|---|---|---|
| 代理可用性 | ✅ | 7897 走 GitHub HTTP 200；直连超时，证明必须走代理 |
| `codexpro doctor` | ✅ | Ready with 2 warnings（profile none / cloudflared missing 均为首次正常态） |
| `codexpro start` 建隧道 | ✅ | 本地 8787 监听、隧道 URL 生成并复制；本地探测 HTTP 401（带 token 鉴权，健康） |
| ChatGPT Developer Mode + 私人 App | ✅ | 用户在网页端完成，Scan Tools 成功 |
| 读能力 | ✅ | GPT 可见全部项目文件夹 |
| 写能力 | ✅ | 写入 `.ai-bridge/codexpro-self-test.md` 并读回成功——**Pro 套餐可写，非只读** |
| 删除能力 | ⚠️ 设计如此 | `bash=safe` 拦截 `rm`，工具集不暴露删除工具；危险操作留本地把关 |
| 测试残留清理 | ✅ | 本地删除 `.ai-bridge/`，`git status` 无残留 |

## 修正记录

- 交接手册「方法一第 3 步」「方法二」使用了不存在的 flag `--no-open-chatgpt`，导致 `codexpro start` 报错 `Missing value for --no-open-chatgpt`。
- 根因：CodexPro 真实参数为 `--open-chatgpt`（主动打开），默认即不打开，无需否定式 flag。
- 已删除手册中两处 `--no-open-chatgpt` 行。

## 日常使用要点

- 启动：`cd /Users/chat/claude && codexpro start`（已 `--save-config`，省略参数即复用配置）
- Cloudflare 临时隧道每次重启换新 URL，需回 ChatGPT App 更新 Server URL 并刷新工具
- start 终端窗口必须常驻，关闭即断连
- URL 含私密 token，全程仅在用户侧流转，不经过 Claude
