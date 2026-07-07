# Handoff

更新时间：2026-07-07
当前负责人：Claude Code
当前分支：main（唯一 trunk）
当前焦点：售后文档状态已收口，主线转为 LKWJ 数据补齐和商品匹配下次实战复核。LKWJ 需补齐 `data/_待采集/README.md` 中列出的采集项，并清理 `clothing.json` / `titles.json` 的 `待补充`；商品匹配需按当前有效待办推进 HEE v2 复核、L2 实战覆盖项和低优先级技术验证。

## 协作规则

- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
