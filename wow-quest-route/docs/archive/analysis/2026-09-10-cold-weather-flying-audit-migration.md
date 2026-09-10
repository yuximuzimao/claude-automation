# 寒冷天气飞行 gate audit → derived-state builder 迁移说明（2026-09-10）

## 结论

`scripts/audit_cold_weather_flying_gates.py` 名义上是 audit，实际根据当前“不学习寒冷天气飞行、仅使用 K3 借鸟满足物理飞行”的路线策略，递归计算哪些任务因 learned-skill gate 或其唯一依赖链而不可进入正式任务池。

`build_sholazar_foundation.py` 直接读取这份结果并据此排除索拉查任务，所以它属于正式输入的 derived-state builder，而不是对既有结果的独立审计。

## 迁移

- 现役实现：`scripts/build_cold_weather_flying_gate_state.py`
- 现役输出：`data/route-atlas/cold-weather-flying-gate-state.json`
- `build_sholazar_foundation.py` 改读新 state 文件。
- `test_no_cold_weather_flying_route_excludes_skill_gates()` 改读新 state 文件。
- 旧 `audit_cold_weather_flying_gates.py` 与旧 `cold-weather-flying-gate-audit.json` 仅保留 RETIRED 指引。

## 等价验证

迁移前旧脚本基线：

- all direct gates：12561、12803、12862、13060、13418、13419；
- Horde paladin direct gates：12561、12803、13060、13419；
- blocked total：17；
- 风暴1、冰冠1、索拉查15、达拉然0。

新 builder 运行后，新旧 JSON 整份结构完全相等：`cold-weather gate state migration exact PASS`。

随后索拉查 foundation 实际改读新 state 后重建：formal 66、cold blocked 15、dependency hard gap 0、unknown service 0；目标测试直接调用 PASS。

本次只纠正职责、命名和输入路径，不改变寒冷天气飞行策略、被阻断任务集合或路线内容。