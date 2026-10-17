# KK平台限时活动扫雷助手 SKILL.md

## DO FIRST
1. 先读 `README.md`；它是玩法规则、运行方式和安全边界的唯一说明。
2. 项目已完成且默认不维护；只有用户明确要求修复、重建或重新启用时才改动。
3. 若要改动，再读 `CLAUDE.md`、`tasks/todo.md` 和 `docs/INDEX.md`。
4. Windows 运行入口：`START.bat`；求解器验证入口：`test_solver.py`。

## ENTRY MAP
| 文件 | 用途 |
| --- | --- |
| `README.md` | 项目用途、规则、运行和诊断说明 |
| `app.py` | Qt 浮窗、截图、自动鼠标执行 |
| `vision.py` | 18×18 棋盘视觉识别 |
| `solver.py` | Z3 确定性约束求解 |
| `test_solver.py` | 求解规则自测 |
| `build_windows.bat` | Windows 单文件 EXE 构建入口 |

## CORE FLOW
- 自动模式只执行 100% 确定格，不做概率猜测。
- 同批点击间隔至少 200ms；整批完成后等待 3 秒，再截图并重新计算。
- 识别低置信度、约束冲突或没有确定格时停止。

## PATHS
- 运行时设置/诊断：Windows `%LOCALAPPDATA%\KBaoHelper\`
- 项目无长期数据目录；临时调试产物不进入项目。
