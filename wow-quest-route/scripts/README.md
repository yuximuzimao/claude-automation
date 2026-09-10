# 现役脚本边界

`scripts/`只放仍属于当前实现链、能依据当前权威数据/规则重新计算结果的构建器、审计器和维护工具。

以下内容不得继续留在本目录：

- 只为某次阶段迁移服务的一次性脚本；
- 从固定Git提交、旧路线或旧P级方案恢复/覆盖当前路线的脚本；
- 已被现役规则替代的P0/P1/P2/P3/P4筛选、删除优先级或阶段性release脚本；
- 需要读取`docs/archive/`中的旧方案才能决定当前路线事实的脚本。

这些脚本如果仍有追溯价值，移到`docs/archive/scripts/`。历史脚本可以解释“当时为什么形成这个结果”，但不得被现役builder、默认audit、默认test或`cli.py`导入/执行。

现役脚本可以把一次性审计结果写入`docs/archive/analysis/`保存证据；“写历史输出”不等于“读取历史作为当前输入”。当前路线事实必须从CURRENT、现役rules、task foundation、observations、Journey和正式Route Atlas数据重新推导。

## 审计治理边界

审计架构的永久规则由 `docs/rules/state-and-validation.md` 唯一维护；本目录只落实该规则。`audit_route_atlas_*` 表示跨地图共享审计，地图专用命名表示真实地图特例或仍在建设期的临时门禁；后者职责被共享层/正式 builder 接管后应退役，不在这里复制第二份规则正文。跨地图审计确实需要的已验证地图/任务例外集中放 `data/route-atlas/route-atlas-audit-exceptions.json`；RouteState 类配置使用对应的显式数据文件，例如飞行审计的 `data/route-atlas/route-atlas-flight-state-config.json`。引擎只消费配置，不在代码里复制地图/任务事实。反过来，**负责选择/生成正式任务池的脚本必须命名为 builder，不得因为会输出差异报告就伪装成 audit**；灰熊 scope 已按此迁为 `build_grizzly_hills_scope.py → grizzly-hills-scope.json → build_grizzly_hills_foundation.py`，嚎风 scope 同样迁为 `build_howling_scope.py → howling-fjord-scope.json → build_howling_foundation.py`，祖达克 scope 也已迁为 `build_zuldrak_scope.py → zuldrak-scope.json → build_zuldrak_foundation.py`。灰熊旧 special-mechanism audit 也已退役：玩家机制由 `grizzly_semantic_steps.py` 唯一维护，已确认五开事实由 `fivebox-task-types.json` 维护，避免同一黄色状态在两张手工表之间漂移。

## 冰冠现役审计链

冰冠当前正式结构以 `icecrown-entry-route-draft.json → build_icecrown_route_structured.py → audit_icecrown_structured_candidate.py → publish_icecrown_route.py` 为主链。

- `audit_icecrown_route_dependency_order.py`：检查164项正式任务的前置顺序，并给 structured builder 提供首出现步骤映射；保留。
- `audit_icecrown_draft_readiness.py`：列出仍未闭合的五开实测/目标锚点风险；属于维护期 review queue；保留。
- `inspect_icecrown_repeat_clones.py`：只读核对首轮任务与后续日常/重复任务的名称、目标、前置和收益差异；属于 foundation 检查工具，不是审计门禁。旧 `audit_icecrown_repeat_clones.py` 已退役为 guard。
- `audit_icecrown_structured_candidate.py`：最终结构审计；同时负责覆盖闭合、接/做/交完整性、几何/交通、HUD备注发布、五开备注格式、任务日志容量、阻断任务泄漏和玩家可见文本卫生。
- 全局发布后再跑 `audit_route_atlas_player_text.py`、`audit_route_atlas_objective_anchors.py`、`audit_route_atlas_flight_state.py` 等跨地图审计。

旧 `audit_icecrown_final_publication.py` 的 61任务/16步/固定289分钟等历史常量已经失效；旧 `audit_icecrown_route_coverage.py` 的职责也已被 structured builder 自产 coverage + structured audit 取代。两者不得再作为现役审计依据；当前同名文件仅保留极短 `RETIRED` guard，防止旧命令被误执行时继续产出伪红灯，不再包含旧审计实现。
