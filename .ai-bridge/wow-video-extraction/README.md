# 魔兽世界视频拆解检查点

该目录保存跨对话可恢复的逐集检查点。长期流程和证据规则位于：

```text
/Users/chat/claude/wow-quest-route/docs/video-extraction/README.md
```

当前进度位于：

```text
/Users/chat/claude/wow-quest-route/docs/video-extraction/CURRENT.md
```

命名：

- `episode-N-extraction.md`：人可读事实、证据、缺口、结束状态；
- `episode-N-events.json`：机器可合并事件；
- `progress.json`：机器恢复状态，必须与项目`CURRENT.md`同步；
- `CURRENT.md`：桥接目录的简要恢复副本，不得取代项目主`CURRENT.md`；
- `checkpoint-00-current-state.md`：开始视频拆解前的实时游戏状态，禁止混入逐集第一遍事实提取。

原始截图和OCR不在本目录，位于：

```text
/Users/chat/claude/wow-quest-route/.ai-bridge/video-epN/
```

NEAT阶段归档位于：

```text
/Users/chat/claude/wow-quest-route/docs/video-extraction/sessions/
```

截至2026-08-07 01:40（UTC+8），第13—34集已完成。下一集为第35集《北风苔原 70.9》，BVID `BV1EQiQBKEVC`，时长1:12:12；尚未处理。
