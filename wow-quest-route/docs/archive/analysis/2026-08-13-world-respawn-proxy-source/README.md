# World respawn proxy extraction archive

本目录保存 2026-08-13 赞加沼泽 CMaNGOS 刷新代理提取的可复现历史材料；它不进入 Route Atlas 运行时或当前计算输入。

## 固定数据源

- WotLK-DB：`7d3ffab46ed8805678355fbdf77ccfaafb30c2ab`
- TBC-DB：`3f7f8f34067bf3c00c6fca8277f6f04f1ae6d12f`

## 文件

- `replay_world_spawns.py`：从 Full DB 导入四张出生相关表并按官方顺序重放仓库更新。
- `build_deliverables.py`：由两库最终原始行生成正式 JSON 与审计报告。
- `wotlk-final-raw.json` / `tbc-final-raw.json`：固定 commit 重放后的目标原始行。
- `wotlk-replay-audit.json` / `tbc-replay-audit.json`：重放文件数、语句数、受影响 entry 与解析告警。

正式运行时文件仍在：

- `data/route-atlas/world-respawn-proxy.json`
- `lib/world_respawn_proxy.py`

正式协议与人类审计仍在：

- `docs/archive/analysis/2026-08-13-world-respawn-proxy-contract.md`
- `docs/archive/analysis/2026-08-13-zangarmarsh-respawn-proxy-audit.md`

## SHA-256

```text
4a4ba71ffab5326fa5898cf56eb3065c01028d13c300a60f3a5434a9cfe11c60  replay_world_spawns.py
023224b706cebb1bc46dfd937e95ef446abb00a60bcb00d0ae39895e5e8880e9  build_deliverables.py
0213ba4d13acf5d578256f8fc46c9dc6290fd35ef258d5bcee6533788ef66505  wotlk-replay-audit.json
94b1fe6c63a8e2896c109eee74ed00c637dbd843ddfd1211e5018835b4de4177  tbc-replay-audit.json
ededf13771f064ec1d4e753c3fdc1a8722dbdb8bc296eb517562eead066adfb7  wotlk-final-raw.json
a9edf49393f78d3698c7e05ca92cd56616a3e4753e66dde7e3ce58c715db5d7f  tbc-final-raw.json
```

完整数据库 clone 与 SQLite 投影不归档；它们体积约 596 MB，可由上述 commit 和重放器重新生成。
