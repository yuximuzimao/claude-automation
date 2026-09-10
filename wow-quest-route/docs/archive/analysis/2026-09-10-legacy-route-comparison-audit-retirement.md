# legacy route comparison audit 退役说明（2026-09-10）

## 结论

`scripts/audit_legacy_route_comparison.py` 是 2026-08-24 semantic-hud-v45 大重构期间的旧稿回归候选生成器。当时它的用途合理：比较重构前后路线，人工复核漏任务、动作角色、旧备注和交通变化。

但该实现没有固定历史 baseline，而是每次运行动态读取当前 Git `HEAD` 中的 `workbench-routes.json`，同时又把 2026-08-24 当时人工分类结论直接硬编码在脚本正文。随着 HEAD 前进，这两部分已经不再属于同一轮比较。

2026-09-10 复运行已现场证明失真：机器部分以当前 HEAD `258e142` 为所谓“重构前”基线，仅得到 hard candidates=0 / review candidates=2；报告后半段却仍自动写入当年北风26项误识别、祖达克/赞加等旧人工结论。继续使用会生成“当前差异 + 历史解释”的混合报告，具有误导风险。

项目内没有现役 builder、audit 或 test 消费该报告。2026-08-24 原终审过程和结论已由 `docs/archive/neat/2026-08-24-legacy-route-atlas-closure-neat.md` 等历史记录保留。

## 处理

- `scripts/audit_legacy_route_comparison.py` 退役为 RETIRED guard。
- 当前 `docs/analysis/2026-08-24-legacy-route-old-vs-new-audit.md` 改为 RETIRED 指引，避免再次被误认为当前审计结果。
- 历史审查证据保留在 archive / Git history。

如果未来再次进行大规模路线重构，应建立新的对比任务，并把 baseline 明确固定为具体提交/快照，再按当次变更重新人工分类；不要复用这份绑定 semantic-hud-v45 历史结论的脚本。