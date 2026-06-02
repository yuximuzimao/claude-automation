# Codex Monitor 阶段 6 后续任务

**来源：** Claude Code  
**时间：** 2026-06-01  
**优先级：** 用户反馈，阶段 6 收尾

---

## 任务 1：先手动启动验证，暂不执行 launchctl bootstrap

用户决定先手动跑 `python3.13 main.py --ui` 验证 UI 正常，再执行开机自启命令。

**无需代码改动。** 等用户确认手动启动无问题后再执行：
```
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.codex-monitor.plist
```

---

## 任务 2：替换 app 图标

用户希望 `Codex Monitor.app` 有好看的图标，不用默认空白图标。

要求：
- macOS 风格，圆角矩形底色
- 主题：监控/仪表盘，颜色建议蓝紫色系（与 UI 配色 `#007AFF` / `#AF52DE` 一致）
- 格式：`icns`，放到 `app/assets/AppIcon.icns`
- `packaging.py` 的 `build_app_bundle()` 把 icns 复制到 `.app/Contents/Resources/AppIcon.icns` 并在 `Info.plist` 里加 `CFBundleIconFile: AppIcon`

实现方式建议：
- 用 Python `Pillow` 生成程序化图标（蓝紫渐变圆角矩形 + 白色简洁图形），转 `icns`
- 或者生成 `png` 后用 `iconutil` 打包成 `icns`

---

## 任务 3：提供折叠/展开截图（给用户看）

用户还没见过 UI 实际效果，需要看折叠和展开两个状态。

请执行：
```bash
python3.13 main.py --demo
```

截图展开状态和折叠状态（点击"折叠"按钮后），截图保存到 `docs/screenshots/` 目录，并在收件箱通知 Claude Code，由 Claude Code 展示给用户。
