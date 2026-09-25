# 视频取证辅助工具

这些工具只在需要重新核验B站原始画面时使用。日常路线规划优先读取`data/sources/video-extraction/`的逐集事实与`data/video-route/`派生索引。

| 工具 | 用途 |
| --- | --- |
| `bili-open-paused.js` | 在导航前注入禁止自动播放逻辑，再打开指定视频URL |
| `bili-open-paused-bvid.js` | 按BVID打开视频并保持暂停 |
| `bili-batch-screenshots.js` | 按时间点批量截图并写manifest |
| `bili-seek-screenshot.js` | 单时间点跳转截图 |
| `bili-query-collection-link.js` | 从合集页面查找目标视频链接 |
| `bili-query-season-state.js` | 从页面状态读取合集分集信息 |
| `cdp-eval.js` | 在指定CDP目标执行只读表达式 |
| `cdp-close-targets.js` | 精确关闭本轮打开的CDP标签页 |
| `ocr-directory.swift` | 用macOS Vision批量OCR截图目录 |
| `ocr-image.swift` | OCR单张图片 |
| `extract-game-region.py` | 从Vision OCR结果提取游戏画面区域文本 |
| `extract-ocr-text.py` | 把Vision OCR结果整理成逐帧文本 |
| `select-ocr-frames.py` | 按正则筛选相关OCR帧块 |

安全边界：打开视频后必须保持暂停，只允许显式seek取证；结束后按本次精确target关闭标签页，不遗留浏览器任务。
