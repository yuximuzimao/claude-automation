# Label Studio SAM Auto-Detect Runbook

## 目标

Label Studio 的 `Auto-Detect` 不是内置识物模型；它只是把用户在画布上的点选/框选作为 interactive prompt 发给 ML Backend。本项目用本机 `http://localhost:9090` 的 SAM backend 生成 `BrushLabels name="mask"` 轮廓建议，用户再修正 mask，并手动画 `RectangleLabels name="bbox"`。

## 当前运行态

- Label Studio：`http://localhost:8080`
- SAM ML Backend：`http://localhost:9090`
- launchd 服务：`com.chat.product-detect-sam-backend`
- plist：`/Users/chat/Library/LaunchAgents/com.chat.product-detect-sam-backend.plist`
- 工作目录：`/Users/chat/claude/product-detect`
- 日志：`/tmp/sam_backend.log`
- 数据根目录：`LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/Users/chat/claude/product-detect/datasets`
- V2 协议：`LABEL_STUDIO_ML_BACKEND_V2=true`

## 健康检查

```bash
curl --noproxy '*' http://localhost:9090/health
```

期望包含：

```json
{"status":"UP","v2":"true"}
```

确认 Label Studio 项目 4 的 backend 已开启 interactive：

```bash
sqlite3 "$HOME/Library/Application Support/label-studio/label_studio.sqlite3" \
  "select id,project_id,url,state,title,is_interactive from ml_mlbackend where url='http://localhost:9090';"
```

期望 `is_interactive=1`。

## 重启 backend

```bash
launchctl kickstart -k gui/501/com.chat.product-detect-sam-backend
launchctl print gui/501/com.chat.product-detect-sam-backend
tail -n 80 /tmp/sam_backend.log
```

如果 launchd 不可用，可临时前台运行：

```bash
bash start-sam-backend.sh
```

## 使用方式

1. 打开 Label Studio pilot 项目。
2. 确认右侧工具栏可见 `Auto-Detect`、`Key Point`、`Rectangle`。
3. 选择商品对应的 ERP 标准标签。
4. 用 `Auto-Detect` 里的 Key Point 在目标商品主体上点一下。
5. 等 backend 返回 mask 建议，检查是否贴合外轮廓。
6. 对粘连、误包含的区域用负点重试或用橡皮擦修正。
7. 对同一商品实例再手动画 `bbox`，不要把提示点当训练标签。
8. `Auto-Accept Suggestions` 保持关闭，人工确认后再保存。

## 排障

- 看不到 `Rectangle` / `Key Point` / `Auto-Detect`：先检查浏览器运行态 `window.Htx.autoAnnotation`；曾出现 `localStorage.autoAnnotation="false"` 导致智能工具被隐藏。
- 看得到图标但点了没有 mask：检查 9090 `/health`、Label Studio DB 的 `is_interactive=1`、`/tmp/sam_backend.log`。
- `/predict` 返回空：确认请求里有 `kwargs["context"]`，并且 context 来自 KeyPoint 或 Rectangle prompt。
- mask 合并相邻商品：增加负点、重新点选目标中心，必要时放弃该建议并手工修正。
- RLE 转换失败：当前 backend 返回的是 Label Studio brush RLE `list[int]`，不是 COCO RLE，也不是 base64 字符串。

## 已验证

2026-06-13 已用 `gift_001.jpg` 做 backend 级 smoke：

- `/setup` 成功。
- `/predict` 带 KeyPoint context 返回非空 `brushlabels`。
- 返回 label 为 `KGOS 三围尺 150cm`。
- mask 尺寸为 `1280x1280`。
- Label Studio 页面确认 `autoAnnotation=true`，`Auto-Accept Suggestions=false`。

剩余 pilot 门禁仍需在 UI 中完成：人工 bbox、原生 JSON 导出、YOLO-seg / YOLO-detect 转换、overlay 肉眼确认。
