# 赞加 task-profile / solver-input audit 职责迁移（2026-09-11）

## 结论

原 `audit_zangarmarsh_task_profiles.py` 与 `audit_zangarmarsh_global_solver_input.py` 都混入了正式数据生产职责，不应继续把 CLI 作为“审计入口”使用。

### task profiles

`audit_zangarmarsh_task_profiles.py` 会读取基础 `zangarmarsh-task-profiles.json`，应用永久 task overrides、组件修正、人工耗时与 eligibility / route policy，并把结果直接写回正式 profile；同时另存 `zangarmarsh-task-classification-audit.json` 作为诊断侧车。因此它本质上是 profile refinement/materialization stage，而不是纯只读 audit。

迁移后现役入口为 `scripts/refine_zangarmarsh_task_profiles.py`。由于当前 CodexPro 没有原子 rename/move 能力，为避免复制约500行实现引入差异，旧模块暂时保留内部 `main()` 实现供新入口调用，但旧 `audit_*.py` CLI 已明确拒绝直接运行。以后有安全原子重命名能力时，可再把实现物理迁出旧文件；本次不为文件名整洁重写算法。

2026-09-11 基线重跑：98 个 profile、0 个低置信度、58 个可用优化耗时模型。第一次在本工作区执行 refinement 后 profile 哈希更新为 `e1ca2e557faa65a82f33e152043c934e8fd4116f7c5a68632920658c4f7b42a1`；再次执行保持同一哈希，确认当前物化结果幂等稳定。

### global solver input

`audit_zangarmarsh_global_solver_input.py` 的完整 JSON 被 `solve_zangarmarsh_first_run_v1.py`、`solve_zangarmarsh_global_core43.py` 和 `estimate_route_atlas_timing.py` 直接消费，因此它实际是 solver-input builder。所谓 `hard_blockers` 不是项目审计失败，而是候选任务缺本地接交点/服务点/成本，表示这些任务不能进入当前优化模型。

当前过滤结果为：54 个候选，11 个不可建模项，43 个 solver-ready；这正是后续 core43 的数据边界。不能把“hard_blockers > 0”改成项目 FAIL。

迁移后：

- 现役入口：`scripts/build_zangarmarsh_global_solver_input.py`；
- 正式产物：`data/route-atlas/zangarmarsh-global-solver-input.json`；
- 三个消费者全部改读新产物；
- 旧 `zangarmarsh-global-solver-input-audit.json` 退役为指引；
- 旧 `audit_*.py` CLI 拒绝直接运行，内部实现暂供新 builder 调用。

新 builder 生成的完整 JSON 与迁移前旧 audit 产物逐对象相等，确认本次只调整职责/命名，不改变候选过滤和 solver 输入。
