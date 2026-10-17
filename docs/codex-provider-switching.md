# Codex 账号订阅与自定义 API 切换

本手册用于通过 CC Switch 在 Codex 的 ChatGPT 账号订阅与自定义 API 之间切换，并排查“接口可用但 Codex 连不上”的问题。这里只记录配置职责和诊断顺序，不记录真实 API Key、Access Token 或服务地址。

## 配置职责

| 位置 | 职责 |
| --- | --- |
| `~/.cc-switch/cc-switch.db` | CC Switch 的供应商卡片、模型与密钥配置；不要直接编辑 |
| `~/.codex/config.toml` | Codex 当前实际生效的模型、提供方、协议和自定义 API 地址 |
| `~/.codex/auth.json` | OpenAI 官方 ChatGPT 登录缓存；不存第三方 API Key |

CC Switch 卡片上的“使用中”只代表它记录的选择。排障必须读取 `~/.codex/config.toml` 和认证文件确认实际状态，不能只看卡片名称。

## 自定义 Responses 提供方

Codex 的直连配置应具备以下形态：

```toml
model_provider = "custom"
model = "<服务端真实支持的模型>"

[model_providers.custom]
name = "custom"
base_url = "<服务端公布的 API 根地址>"
wire_api = "responses"
requires_openai_auth = false
```

- API Key 在 CC Switch 的供应商表单中维护；直连时由 CC Switch 写入提供方作用域的 `experimental_bearer_token`，不要手工写入文档。
- `base_url` 的 `http://` / `https://` 必须与服务端监听方式完全一致。端口能通不等于 TLS 能握手。
- `wire_api = "responses"` 要求上游支持 `POST /v1/responses`。只有 Chat Completions 时，在 CC Switch 选择“Chat Completions（需要路由）”并启用 Codex 本地路由，不要把当前 Codex 的 `wire_api` 手改为旧协议。
- `requires_openai_auth = true` 只用于需要 OpenAI 官方认证的提供方；第三方 Key 直连应为 `false`。
- 不复制旧配置里的废弃字段。保存后可用 `codex --strict-config doctor` 检查当前 Codex 是否仍接受全部字段。

## 切换流程

### 切回 ChatGPT 账号订阅

1. 在 CC Switch 的 Codex 页面选择 `OpenAI Official`，不要把升级前自动导入的 `default` 卡片当成官方入口。
2. 完全退出并重新打开 Codex；只关窗口不一定会重载后台 daemon。
3. 若官方登录未恢复，执行 `codex login`。

### 切到自定义 API

1. 在 CC Switch 设置中启用“直接切换时保留官方登录”，让官方 OAuth 留在 `auth.json`，第三方模型流量由 `config.toml` 决定。
2. 在供应商卡片中填写 API Key、基础地址、模型和上游格式。
3. 切换后完整重启 Codex，再读取 `~/.codex/config.toml` 验证实际写入结果。
4. 首次验证先使用已经在另一客户端成功调用的同一模型，连通后再切换新模型。

## 故障排查顺序

1. **实际配置**：读取 `~/.codex/config.toml`，确认模型、`base_url`、`wire_api`、认证方式和 bearer token 是否存在；输出时只报告存在性或指纹。
2. **地址协议**：分别对 HTTP 和 HTTPS 的 `/v1/models` 做无密钥连接测试。HTTP 返回 `401` 说明服务已到达；HTTPS 在 TLS 阶段返回状态 `000`，通常说明端口不是 TLS 服务。
3. **API 协议**：确认上游是 Responses 还是 Chat Completions。Codex 工具调用应优先走 Responses。
4. **凭据一致性**：只比较 SHA-256 短指纹，不显示原值。
5. **模型一致性**：先与已知可用客户端使用同一模型，再测试新模型名。
6. **日志**：最后查看 Codex daemon、CC Switch 用量页和上游服务错误，避免在地址层尚未通过时追模型参数。

## 本机已知约束

- 2026-10-09 验证：当前自定义网关的 `:8080` 端口接受 HTTP，不接受 HTTPS；强制 HTTPS 会在 TLS 握手阶段失败。若网关地址或部署方式变化，必须重新验证，不要永久假设。
- HTTP 会明文传输 API Key 和请求内容。当前配置虽然能工作，长期方案仍应由服务端提供 HTTPS。
- DeepSeek Harness 已于 2026-10-10 卸载；其配置、凭据和运行时不再是本机现役切换链路。历史连接排障记录见 `docs/archive/2026-10-09-codex-ccswitch-deepseek-harness/`。
