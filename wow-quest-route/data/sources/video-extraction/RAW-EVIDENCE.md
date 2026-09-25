# 视频原始截图证据

`raw-evidence/video-ep1`至`video-ep53`保存视频拆解时生成的原始截图、OCR文本和截图manifest，用于必要时离线复核单集事实。

- 规模：约27.2 GiB、29,000余个文件；53集齐全。
- 日常入口：路线研究优先读取同目录的`episode-N-extraction.md`、`episode-N-events.json`以及`data/video-route/`派生索引，不默认加载原始截图。
- 使用条件：只有逐集事实与派生索引不足以裁决具体画面时，才进入对应`raw-evidence/video-epN/`。
- 可重建性：视频仍在线时，可依据检查点保存的BVID与manifest时间重新截图；外部视频失效后，这里是唯一的本地像素级证据。
- Git：原始证据体积过大，按精确目录规则忽略，不提交仓库。
- 备份：工作区周备份精确排除本目录，避免每周重复复制约27GB；2026-09-20及更早的现有工作区备份仍包含旧位置的原始证据。

视频取证工具见`../../../scripts/video-extraction/README.md`。
