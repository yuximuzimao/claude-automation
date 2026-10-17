# Codex / CC Switch / DeepSeek Harness 配置收尾

归档日期：2026-10-09

本归档保存本轮系统工具升级与连接排障的历史证据。当前操作方法以 `docs/codex-provider-switching.md` 和实际配置为准。

## 已完成

- DeepSeek Harness Desktop 从 `0.18.0` 更新到官方 `0.22.4`；安装包摘要与 GitHub 发布资产一致，Apple Developer ID、公证、安装后签名和启动进程均验证通过。
- CC Switch 从 `3.16.1` 更新到官方 `4.0.5`；安装包摘要、签名和公证验证通过，数据库从 v10 迁移到 v20，`PRAGMA integrity_check` 返回 `ok`。
- CC Switch 升级前数据库与设置保存在 `~/.cc-switch/backups/manual-pre-4.0.5-20261009-150110/`；临时 DMG、挂载目录和旧应用副本已清理。
- 建立 `~/.dsh/AGENTS.md -> /Users/chat/AGENTS.md` 符号链接，并用目标路径与内容摘要确认一致；以后只维护 Codex 总规则源文件。
- 2026-10-09 的主工作方式：Codex 作为主要执行框架；CC Switch 只负责在 OpenAI 官方账号与自定义 API 之间切换；DeepSeek Harness 暂作为低风险备用工作台。

## 连接故障根因

- CC Switch 实际写入 Codex 的自定义 API 地址使用 HTTPS；DeepSeek Harness 的同一服务配置使用 HTTP。
- 无密钥探测显示 HTTP 能到达服务并返回 `401`，HTTPS 在 TLS 握手阶段失败、状态为 `000`。
- 两边 API Key 的 SHA-256 短指纹一致，协议均为 OpenAI Responses，因此根因不是密钥或 wire protocol，而是 URL scheme。
- 把 CC Switch 卡片中的基础地址恢复为服务端实际支持的 HTTP 后，Codex 已成功连接。

## 安全与后续边界

- 本归档不记录网关 IP、API Key、OAuth Token 或任何凭据原文。
- 公网 HTTP 会明文传输凭据与请求；可用不等于安全，长期应由服务端提供 HTTPS。
- `OpenAI Official` 是切回 ChatGPT 账号订阅的明确入口；升级前导入的 `default` 卡片不作为官方身份真值。
- 任何后续切换都要读取 `~/.codex/config.toml` 验证实际生效状态，不能只信 CC Switch 卡片的“使用中”。

## 后续退役

- 2026-10-10 已卸载 DeepSeek Harness Desktop 0.22.4。
- 已删除应用本体、`~/Library/Application Support/dsh-tauri`、`~/Library/Caches/dsh-tauri`、`~/.dsh`、`~/.local/bin/dsh` 及残留临时套接字；桌面进程、Node 后台服务和 LaunchServices 任务均已停止并复查不存在。
- 当前入口不再依赖 Harness；本目录继续保留为升级、连接排障和卸载的历史证据。
