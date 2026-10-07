# 本机配置

本目录只保存可版本化的配置说明/示例。

真实目标群名、窗口偏好等本机配置写入：

`config/local.json`

该文件已被项目 `.gitignore` 忽略。

当前最小结构：

```json
{
  "window": {"x": 0, "y": 0, "width": 1200, "height": 800},
  "scroll_pixels": 630,
  "groups": [
    {
      "group_key": "stable-local-key",
      "conversation_prefix": "会话列表中可唯一识别的前缀",
      "header_contains": "选中后聊天头部必须包含的稳定片段",
      "history_title": "聊天记录窗口的精确标题"
    }
  ]
}
```

成员人数等会变化的数据不作为长期身份配置；可以在诊断时作为额外证据，但不能因为人数变化就把同一目标群判成另一群。
