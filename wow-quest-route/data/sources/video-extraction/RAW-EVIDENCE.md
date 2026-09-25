# 视频原始截图证据退役记录

2026-09-25，用户确认删除视频拆解阶段产生的原始截图、OCR文本和截图manifest。已删除内容约27.2 GiB，覆盖第1—53集。

继续保留的正式结果：

- `episode-N-extraction.md`：53集人可读事实、证据判断与缺口；
- `episode-N-events.json`：53集机器事件；
- `data/video-route/`：全集事件、地图顺序、邻接与跨集边界索引；
- `docs/video-extraction/`：取证方法、证据边界和完成状态；
- `scripts/video-extraction/`：暂停打开、显式seek截图、OCR和文本筛选工具。

如果以后必须重新核验画面，先从单集检查点取得BVID和时间范围，再按`../../../scripts/video-extraction/README.md`重新取证；临时截图统一写入`_sandbox/video-extraction/video-epN/`，结论写回正式检查点后删除临时文件。

删除时，2026-08-23至2026-09-20的多份工作区周备份仍包含旧位置的原始证据；这些备份会按保留8份的策略逐周轮换，不作为长期现役入口。
