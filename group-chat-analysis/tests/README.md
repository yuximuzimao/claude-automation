# 测试策略

项目测试分三层，不能混成“一个全量测试脚本”。

## 1. 纯确定性单元测试

可用合成/脱敏 fixture，覆盖：

- Swift `capture-step` / `open-history` typecheck、正文区/MAD/dhash/Schema 纯函数回归；
- 安全切群纯门禁：左侧会话唯一候选、目标头部复核、`聊天记录` tooltip 精确确认；
- bbox 视觉行/消息/fragment 重建与媒体 OCR unknown 降级；
- 时间文本解析；
- 相邻屏最长连续重叠；
- OCR轻微差异下的受控锚点匹配；
- 不同真实重复消息不能被误删；
- 保守发送者匹配：相似昵称不归并、一侧昵称缺失不破坏性去重；
- `message_type` / `timestamp_text` 兼容性与两条最小重叠强锚点；
- capture 页“新→旧”到最终消息“旧→新”的方向转换；
- batch-state v3：`pending_capture`、每群 `capture_complete`、v2 迁移、页恢复点、状态转换和连续锚点门禁；
- 唯一 runner 的 pending/raw reconcile、stray raw 拒绝、pending scroll 硬停等故障注入；
- canonical messages 原子/幂等提交与 messages→completed→current 崩溃恢复；
- current.md 构建顺序；
- message-record 校验与 Schema 结构真值同步。

这类测试应该可重复、无需启动 QQ。

## 2. 本地采集适配器测试

只在用户当前 Mac/QQ 环境运行，验证：

- 正确识别 QQ/目标群；
- 聊天区定位；
- AX 设置/读回后 SCK 窗口几何真正稳定；
- 窗口级捕获（不使用整屏裁剪 fallback）；
- `dhash512` 同视口/异视口距离校准，滚动前连续性门禁；
- 滚轮只影响消息区；
- 图像变化检测、“变化后回到 baseline”拒绝及 `<=3px` SCK 尺寸漂移；
- Vision OCR；
- 不发生任何聊天写操作。

这不是 CI 真值；QQ UI 更新后要按实时环境重新验证。

## 3. 端到端 dry-run

用一个目标群的小范围历史：

`capture → normalize → store → current.md`

成功标准至少包括：

- 只从唯一 `run_capture.py` 入口推进 state；
- 没有其它应用/其它群内容；
- 消息方向正确；
- 相邻屏重复消除；
- 同文真实重复不被错误吞掉；
- 中断时保持 incomplete，pending/raw 语义可确定恢复或明确停止；
- completed 才生成 current.md，缺失 current 可纯本地重建且不触碰 QQ；
- analyzed 不覆盖已完成消息；
- runtime 文件确实不被 Git 跟踪。

GPT分析属于后续独立验收，不用“摘要看起来不错”代替采集完整性验证。
