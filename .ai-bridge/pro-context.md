# UnGoro full-clear route data

Generated: 2026-08-08T16:58:03.694Z
Workspace: /Users/chat/claude
Workspace ID: ws_cf6c701a0778888530eb4ae9
Write mode: workspace
Bash mode: full
Tool mode: full

Purpose: paste this bundle into a high-context ChatGPT model when that model cannot call the CodexPro MCP tools directly.
Instruction for ChatGPT: use this as repository context, produce a narrow Codex execution plan, and avoid inventing files or runtime facts not shown here.

## Repository Tree

.
├── _exports/
├── _sandbox/
├── aftersales-automation/
├── codex-monitor/
├── docs/
├── douyin-workout/
├── lkwj/
├── order-review/
├── product-ad-studio/
├── product-detect/
├── product-mapping/
├── return-inbound/
├── reviews/
├── scripts/
├── sessions/
├── sku-calculator/
├── tasks/
├── test/
├── transfer/
├── voice-retrieval/
├── wow-quest-route/
├── AGENTS.md
├── backup-workspace.sh
├── CLAUDE.md
├── package-lock.json
└── package.json

## Git Status

```text
## main...origin/main
 D .ai-bridge/diary-2026-W30-raw.md
 D .ai-bridge/diary-2026-W31-raw.md
 M AGENTS.md
 M docs/HANDOFF.md
 M order-review/AGENTS.md
 M order-review/CLAUDE.md
 M order-review/README.md
 M order-review/docs/2026-07-22-approximate-recommendation-direction.md
 M order-review/docs/2026-07-23-package-rule-foundation.md
 M order-review/docs/archive/README.md
 M order-review/src/order_review/app.py
 M order-review/src/order_review/audit_dialog.py
 M order-review/src/order_review/audit_execution.py
 M order-review/src/order_review/audit_probe.py
 M order-review/src/order_review/audit_runner.py
 M order-review/src/order_review/case_backup.py
 M order-review/src/order_review/case_replay.py
 M order-review/src/order_review/case_repository.py
 M order-review/src/order_review/case_validation.py
 M order-review/src/order_review/erp_reader.py
 M order-review/src/order_review/package_equivalence.py
 M order-review/src/order_review/package_workflow.py
 M order-review/src/order_review/recommendations.py
 M order-review/src/order_review/ui.py
 M order-review/tests/test_audit_dialog.py
 M order-review/tests/test_audit_execution.py
 M order-review/tests/test_audit_probe.py
 M order-review/tests/test_audit_runner.py
 M order-review/tests/test_case_replay.py
 M order-review/tests/test_case_repository.py
 M order-review/tests/test_case_safety.py
 M order-review/tests/test_erp_reader.py
 M order-review/tests/test_package_equivalence.py
 M order-review/tests/test_package_workflow.py
 M order-review/tests/test_recommendation_events.py
 M order-review/tests/test_ui_interaction.py
 M product-ad-studio/CLAUDE.md
 M product-ad-studio/README.md
 M product-ad-studio/SKILL.md
 M product-ad-studio/docs/INDEX.md
 M product-ad-studio/tasks/todo.md
 M product-mapping/data/sku-records.json
 M reviews/weekly/2026-W30.md
 M reviews/weekly/2026-W31.md
 M wow-quest-route/CLAUDE.md
 M wow-quest-route/README.md
 M wow-quest-route/SKILL.md
 M wow-quest-route/data/observations/fivebox-task-types.json
 M wow-quest-route/docs/INDEX.md
 M wow-quest-route/docs/JOURNEY_EXPORT.md
 M wow-quest-route/docs/NEAT_SIMPLE_LEVELING_ROUTE.md
 M wow-quest-route/docs/NEXT_CHAT_HANDOFF.md
 M wow-quest-route/docs/proposed-routes/2026-08-03-30-35-thousand-needles-complete-route-v1.md
 M wow-quest-route/docs/proposed-routes/2026-08-03-30-35-thousand-needles-full-clear-audit-v1.md
 M wow-quest-route/docs/verified-routes/CURRENT.md
 M wow-quest-route/docs/verified-routes/FLIGHT-POINTS.md
 M wow-quest-route/docs/verified-routes/PALADIN-COMBAT-NOTES.md
 M wow-quest-route/docs/verified-routes/README.md
 M wow-quest-route/docs/verified-routes/RULES.md
 M wow-quest-route/docs/verified-routes/segments/24-25-stonetalon-capitals-tarren.md
 M wow-quest-route/tasks/lessons.md
 M wow-quest-route/tasks/todo.md
?? .ai-bridge/Questie.lua
?? .ai-bridge/agent-status.md
?? .ai-bridge/codex-status.md
?? .ai-bridge/current-plan.md
?? .ai-bridge/decisions.md
?? .ai-bridge/execution-log.jsonl
?? .ai-bridge/implementation-diff.patch
?? .ai-bridge/open-questions.md
?? .ai-bridge/session-log.jsonl
?? .ai-bridge/wow-video-extraction/
?? "lkwj/\345\233\276\351\211\264\350\257\276\351\242\230\350\277\233\345\272\246\350\241\250\357\274\210\345\217\246\345\255\230\346\210\226\345\255\230\344\270\272\345\211\257\346\234\254\344\275\277\347\224\250\357\274\211.xlsx"
?? order-review/docs/CURRENT.md
?? order-review/docs/archive/2026-07-29-mixed-split-v1/
?? order-review/docs/archive/2026-07-30-memory-and-composition/
?? order-review/docs/archive/2026-07-30-mixed-split-and-audit/
?? order-review/docs/archive/2026-08-03-save-plan-and-case-correction/
?? order-review/docs/archive/2026-08-05-split-scroll-and-direct-review/
?? order-review/docs/archive/2026-08-06-split-result-stability/
?? order-review/src/order_review/memory_diagnostics.py
?? order-review/src/order_review/split_dry_run.py
?? order-review/src/order_review/split_probe.py
?? order-review/src/order_review/split_result.py
?? order-review/src/order_review/split_runner.py
?? order-review/tests/test_memory_diagnostics.py
?? order-review/tests/test_split_dry_run.py
?? order-review/tests/test_split_probe.py
?? order-review/tests/test_split_result.py
?? order-review/tests/test_split_runner.py
?? product-ad-studio/docs/archive/2026-07-31-image-generation-authorization.md
?? product-ad-studio/jobs/
?? reviews/monthly/2026-07.md
?? tasks/
?? wow-quest-route/data/observations/task-efficiency-corrections.json
?? wow-quest-route/data/route-specs/35-55-speedrun-constraints.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-candidates.csv
?? wow-quest-route/data/routes/horde/blood-elf/35-55-candidates.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-cost-model.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-optimizer-input.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-overlap-blocks.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-overlap-graph.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-priority-task-audit.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-route-solutions.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation-enriched.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation.csv
?? wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation.json
?? wow-quest-route/data/routes/horde/blood-elf/35-55-transport-edges.json
?? wow-quest-route/data/routes/horde/blood-elf/35-current-available-tasks.csv
?? wow-quest-route/data/routes/horde/blood-elf/39-55-a-route-task-details.json
?? wow-quest-route/data/routes/horde/blood-elf/39-55-eastern-kingdoms-candidate.json
?? wow-quest-route/data/routes/horde/blood-elf/39-55-evidence-budget-draft.json
?? wow-quest-route/data/routes/horde/blood-elf/39-55-zero-purchase-budget.json
?? wow-quest-route/data/routes/horde/blood-elf/39-55-zero-purchase-zone-pool.json
?? wow-quest-route/data/routes/horde/blood-elf/current-route-task-evidence.json
?? wow-quest-route/docs/analysis/2026-08-04-35-55-data-contract-and-requirements.md
?? wow-quest-route/docs/analysis/2026-08-04-35-55-fastest-route-feasibility-v1.md
?? wow-quest-route/docs/analysis/2026-08-04-35-55-optimizer-audit.md
?? wow-quest-route/docs/analysis/2026-08-04-35-55-overlap-block-audit.md
?? wow-quest-route/docs/analysis/2026-08-04-35-55-priority-task-audit.md
?? wow-quest-route/docs/analysis/2026-08-04-35-55-task-foundation-review.md
?? wow-quest-route/docs/analysis/2026-08-05-video-34-37-level-band-and-route-difference.md
?? wow-quest-route/docs/analysis/2026-08-06-a-route-task-coordinate-summary.md
?? wow-quest-route/docs/analysis/2026-08-06-current-route-static-evidence-matrix.md
?? wow-quest-route/docs/analysis/2026-08-06-fivebox-video-independent-zero-purchase-optimization.md
?? wow-quest-route/docs/analysis/2026-08-06-level39-55-task-by-task-web-audit-v1.md
?? wow-quest-route/docs/analysis/2026-08-08-northrend-daily-quests-unverified-source.md
?? wow-quest-route/docs/proposed-routes/2026-08-04-35-43-dustwallow-desolace-feralas-tanaris-full-route-v1.md
?? wow-quest-route/docs/proposed-routes/2026-08-05-35.5-37-stv-video-aligned.md
?? wow-quest-route/docs/task-library/
?? wow-quest-route/docs/verified-routes/ERROR-BOOK.md
?? wow-quest-route/docs/verified-routes/ROUTE-DESIGN-PROCESS.md
?? wow-quest-route/docs/verified-routes/VETERAN-LEVELING-BACKBONE.md
?? wow-quest-route/docs/video-extraction/
?? wow-quest-route/scripts/
?? wow-quest-route/tests/test_35_55_overlap_blocks.py
```

## Recent Commits

```text
e340fd8 (HEAD -> main, origin/main, origin/HEAD) feat: add wow quest route project
2d42115 docs(workspace): W31 周回顾 + 原始日记归档至 .ai-bridge
997ca15 docs(aftersales): archive list recovery guidance
25233b4 fix(aftersales): recover transient list sort mismatch
b7ac31a docs(product-ad-studio): 按 neat 归档基础阶段
7048bd7 chore(product-ad-studio): 归档钥黑案例素材
a28e099 docs(workbuddy): 固化临时目录边界
d959054 fix(aftersales): wait for list DOM readiness
```

## Selected Files

Changed files detected: .ai-bridge/diary-2026-W30-raw.md, .ai-bridge/diary-2026-W31-raw.md, AGENTS.md, docs/HANDOFF.md, order-review/AGENTS.md, order-review/CLAUDE.md, order-review/README.md, order-review/docs/2026-07-22-approximate-recommendation-direction.md, order-review/docs/2026-07-23-package-rule-foundation.md, order-review/docs/archive/README.md, order-review/src/order_review/app.py, order-review/src/order_review/audit_dialog.py, order-review/src/order_review/audit_execution.py, order-review/src/order_review/audit_probe.py, order-review/src/order_review/audit_runner.py, order-review/src/order_review/case_backup.py, order-review/src/order_review/case_replay.py, order-review/src/order_review/case_repository.py, order-review/src/order_review/case_validation.py, order-review/src/order_review/erp_reader.py, order-review/src/order_review/package_equivalence.py, order-review/src/order_review/package_workflow.py, order-review/src/order_review/recommendations.py, order-review/src/order_review/ui.py, order-review/tests/test_audit_dialog.py, order-review/tests/test_audit_execution.py, order-review/tests/test_audit_probe.py, order-review/tests/test_audit_runner.py, order-review/tests/test_case_replay.py, order-review/tests/test_case_repository.py, order-review/tests/test_case_safety.py, order-review/tests/test_erp_reader.py, order-review/tests/test_package_equivalence.py, order-review/tests/test_package_workflow.py, order-review/tests/test_recommendation_events.py, order-review/tests/test_ui_interaction.py, product-ad-studio/CLAUDE.md, product-ad-studio/README.md, product-ad-studio/SKILL.md, product-ad-studio/docs/INDEX.md, product-ad-studio/tasks/todo.md, product-mapping/data/sku-records.json, reviews/weekly/2026-W30.md, reviews/weekly/2026-W31.md, wow-quest-route/CLAUDE.md, wow-quest-route/README.md, wow-quest-route/SKILL.md, wow-quest-route/data/observations/fivebox-task-types.json, wow-quest-route/docs/INDEX.md, wow-quest-route/docs/JOURNEY_EXPORT.md, wow-quest-route/docs/NEAT_SIMPLE_LEVELING_ROUTE.md, wow-quest-route/docs/NEXT_CHAT_HANDOFF.md, wow-quest-route/docs/proposed-routes/2026-08-03-30-35-thousand-needles-complete-route-v1.md, wow-quest-route/docs/proposed-routes/2026-08-03-30-35-thousand-needles-full-clear-audit-v1.md, wow-quest-route/docs/verified-routes/CURRENT.md, wow-quest-route/docs/verified-routes/FLIGHT-POINTS.md, wow-quest-route/docs/verified-routes/PALADIN-COMBAT-NOTES.md, wow-quest-route/docs/verified-routes/README.md, wow-quest-route/docs/verified-routes/RULES.md, wow-quest-route/docs/verified-routes/segments/24-25-stonetalon-capitals-tarren.md, wow-quest-route/tasks/lessons.md, wow-quest-route/tasks/todo.md, .ai-bridge/Questie.lua, .ai-bridge/agent-status.md, .ai-bridge/codex-status.md, .ai-bridge/current-plan.md, .ai-bridge/decisions.md, .ai-bridge/execution-log.jsonl, .ai-bridge/implementation-diff.patch, .ai-bridge/open-questions.md, .ai-bridge/session-log.jsonl, .ai-bridge/wow-video-extraction/, lkwj/\345\233\276\351\211\264\350\257\276\351\242\230\350\277\233\345\272\246\350\241\250\357\274\210\345\217\246\345\255\230\346\210\226\345\255\230\344\270\272\345\211\257\346\234\254\344\275\277\347\224\250\357\274\211.xlsx, order-review/docs/CURRENT.md, order-review/docs/archive/2026-07-29-mixed-split-v1/, order-review/docs/archive/2026-07-30-memory-and-composition/, order-review/docs/archive/2026-07-30-mixed-split-and-audit/, order-review/docs/archive/2026-08-03-save-plan-and-case-correction/, order-review/docs/archive/2026-08-05-split-scroll-and-direct-review/, order-review/docs/archive/2026-08-06-split-result-stability/, order-review/src/order_review/memory_diagnostics.py, order-review/src/order_review/split_dry_run.py, order-review/src/order_review/split_probe.py, order-review/src/order_review/split_result.py, order-review/src/order_review/split_runner.py, order-review/tests/test_memory_diagnostics.py, order-review/tests/test_split_dry_run.py, order-review/tests/test_split_probe.py, order-review/tests/test_split_result.py, order-review/tests/test_split_runner.py, product-ad-studio/docs/archive/2026-07-31-image-generation-authorization.md, product-ad-studio/jobs/, reviews/monthly/2026-07.md, tasks/, wow-quest-route/data/observations/task-efficiency-corrections.json, wow-quest-route/data/route-specs/35-55-speedrun-constraints.json, wow-quest-route/data/routes/horde/blood-elf/35-55-candidates.csv, wow-quest-route/data/routes/horde/blood-elf/35-55-candidates.json, wow-quest-route/data/routes/horde/blood-elf/35-55-cost-model.json, wow-quest-route/data/routes/horde/blood-elf/35-55-optimizer-input.json, wow-quest-route/data/routes/horde/blood-elf/35-55-overlap-blocks.json, wow-quest-route/data/routes/horde/blood-elf/35-55-overlap-graph.json, wow-quest-route/data/routes/horde/blood-elf/35-55-priority-task-audit.json, wow-quest-route/data/routes/horde/blood-elf/35-55-route-solutions.json, wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation-enriched.json, wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation.csv, wow-quest-route/data/routes/horde/blood-elf/35-55-task-foundation.json, wow-quest-route/data/routes/horde/blood-elf/35-55-transport-edges.json, wow-quest-route/data/routes/horde/blood-elf/35-current-available-tasks.csv, wow-quest-route/data/routes/horde/blood-elf/39-55-a-route-task-details.json, wow-quest-route/data/routes/horde/blood-elf/39-55-eastern-kingdoms-candidate.json, wow-quest-route/data/routes/horde/blood-elf/39-55-evidence-budget-draft.json, wow-quest-route/data/routes/horde/blood-elf/39-55-zero-purchase-budget.json, wow-quest-route/data/routes/horde/blood-elf/39-55-zero-purchase-zone-pool.json, wow-quest-route/data/routes/horde/blood-elf/current-route-task-evidence.json, wow-quest-route/docs/analysis/2026-08-04-35-55-data-contract-and-requirements.md, wow-quest-route/docs/analysis/2026-08-04-35-55-fastest-route-feasibility-v1.md, wow-quest-route/docs/analysis/2026-08-04-35-55-optimizer-audit.md, wow-quest-route/docs/analysis/2026-08-04-35-55-overlap-block-audit.md, wow-quest-route/docs/analysis/2026-08-04-35-55-priority-task-audit.md, wow-quest-route/docs/analysis/2026-08-04-35-55-task-foundation-review.md, wow-quest-route/docs/analysis/2026-08-05-video-34-37-level-band-and-route-difference.md, wow-quest-route/docs/analysis/2026-08-06-a-route-task-coordinate-summary.md, wow-quest-route/docs/analysis/2026-08-06-current-route-static-evidence-matrix.md, wow-quest-route/docs/analysis/2026-08-06-fivebox-video-independent-zero-purchase-optimization.md, wow-quest-route/docs/analysis/2026-08-06-level39-55-task-by-task-web-audit-v1.md, wow-quest-route/docs/analysis/2026-08-08-northrend-daily-quests-unverified-source.md, wow-quest-route/docs/proposed-routes/2026-08-04-35-43-dustwallow-desolace-feralas-tanaris-full-route-v1.md, wow-quest-route/docs/proposed-routes/2026-08-05-35.5-37-stv-video-aligned.md, wow-quest-route/docs/task-library/, wow-quest-route/docs/verified-routes/ERROR-BOOK.md, wow-quest-route/docs/verified-routes/ROUTE-DESIGN-PROCESS.md, wow-quest-route/docs/verified-routes/VETERAN-LEVELING-BACKBONE.md, wow-quest-route/docs/video-extraction/, wow-quest-route/scripts/, wow-quest-route/tests/test_35_55_overlap_blocks.py
Auto-include important root files: no
Auto-include changed files: no
Explicit selected paths: wow-quest-route/data/routes/world-candidate/490-un-goro-crater/route.json, wow-quest-route/data/journey/current-paladin.json, wow-quest-route/docs/task-library/46-55-ungoro.md
Extra globs: none
Files included below: wow-quest-route/data/journey/current-paladin.json, wow-quest-route/data/routes/world-candidate/490-un-goro-crater/route.json, wow-quest-route/docs/task-library/46-55-ungoro.md

## File Contents

### wow-quest-route/data/journey/current-paladin.json

Bytes: 29062
SHA-256: 6eb4c6001402d9f856f0464816a7f4cae3df3aa90ae10d4f157d2355b492e769
Lines: 1-1591 of 1591

```json
   1 | {
   2 |   "source_scope": "account-level QuestieConfig.char entry",
   3 |   "source_sha256": "6231caf430a2bba1299660485539ab5cdbdad3188d7219ba70504c5f0c221d0b",
   4 |   "profile": "PALADIN_BLOODELF_CURRENT",
   5 |   "total_events": 211,
   6 |   "quest_events": 197,
   7 |   "level_events": 14,
   8 |   "earliest_timestamp": 1785438261,
   9 |   "latest_timestamp": 1785531969,
  10 |   "min_level": 6,
  11 |   "max_level": 20,
  12 |   "complete_quest_ids": [
  13 |     8325,
  14 |     8326,
  15 |     8327,
  16 |     8330,
  17 |     8334,
  18 |     8335,
  19 |     8336,
  20 |     8338,
  21 |     8345,
  22 |     8346,
  23 |     8347,
  24 |     8350,
  25 |     8463,
  26 |     8468,
  27 |     8473,
  28 |     8474,
  29 |     8475,
  30 |     8476,
  31 |     8477,
  32 |     8479,
  33 |     8482,
  34 |     8483,
  35 |     8487,
  36 |     8488,
  37 |     8490,
  38 |     8888,
  39 |     8889,
  40 |     8890,
  41 |     8891,
  42 |     8892,
  43 |     8894,
  44 |     9035,
  45 |     9062,
  46 |     9064,
  47 |     9066,
  48 |     9130,
  49 |     9133,
  50 |     9138,
  51 |     9139,
  52 |     9144,
  53 |     9145,
  54 |     9152,
  55 |     9155,
  56 |     9158,
  57 |     9159,
  58 |     9160,
  59 |     9161,
  60 |     9162,
  61 |     9163,
  62 |     9166,
  63 |     9167,
  64 |     9169,
  65 |     9172,
  66 |     9173,
  67 |     9175,
  68 |     9176,
  69 |     9192,
  70 |     9193,
  71 |     9212,
  72 |     9215,
  73 |     9220,
  74 |     9252,
  75 |     9254,
  76 |     9255,
  77 |     9256,
  78 |     9258,
  79 |     9274,
  80 |     9275,
  81 |     9276,
  82 |     9277,
  83 |     9281,
  84 |     9282,
  85 |     9315,
  86 |     9327,
  87 |     9328,
  88 |     9329,
  89 |     9352,
  90 |     9358,
  91 |     9359,
  92 |     9360,
  93 |     9363,
  94 |     9394,
  95 |     9395,
  96 |     9676,
  97 |     9677,
  98 |     9704,
  99 |     9705,
 100 |     9758,
 101 |     9877,
 102 |     10068,
 103 |     10069,
 104 |     10070,
 105 |     10071,
 106 |     10072,
 107 |     10073,
 108 |     10166,
 109 |     93950
 110 |   ],
 111 |   "events": [
 112 |     {
 113 |       "index": 1,
 114 |       "event": "Complete",
 115 |       "quest_id": 8334,
 116 |       "level": 6,
 117 |       "timestamp": 1785438261
 118 |     },
 119 |     {
 120 |       "index": 2,
 121 |       "event": "Accept",
 122 |       "quest_id": 8335,
 123 |       "level": 6,
 124 |       "timestamp": 1785438264
 125 |     },
 126 |     {
 127 |       "index": 3,
 128 |       "event": "Complete",
 129 |       "quest_id": 8335,
 130 |       "level": 6,
 131 |       "timestamp": 1785438663
 132 |     },
 133 |     {
 134 |       "index": 4,
 135 |       "event": "Accept",
 136 |       "quest_id": 8347,
 137 |       "level": 6,
 138 |       "timestamp": 1785438666
 139 |     },
 140 |     {
 141 |       "index": 5,
 142 |       "event": "Complete",
 143 |       "quest_id": 8347,
 144 |       "level": 6,
 145 |       "timestamp": 1785438858
 146 |     },
 147 |     {
 148 |       "index": 6,
 149 |       "event": "Accept",
 150 |       "quest_id": 9704,
 151 |       "level": 6,
 152 |       "timestamp": 1785438858
 153 |     },
 154 |     {
 155 |       "index": 7,
 156 |       "event": "Complete",
 157 |       "quest_id": 9704,
 158 |       "level": 6,
 159 |       "timestamp": 1785438889
 160 |     },
 161 |     {
 162 |       "index": 8,
 163 |       "event": "Accept",
 164 |       "quest_id": 9705,
 165 |       "level": 6,
 166 |       "timestamp": 1785438889
 167 |     },
 168 |     {
 169 |       "index": 9,
 170 |       "event": "Complete",
 171 |       "quest_id": 9705,
 172 |       "level": 6,
 173 |       "timestamp": 1785438931
 174 |     },
 175 |     {
 176 |       "index": 10,
 177 |       "event": "LevelUp",
 178 |       "quest_id": null,
 179 |       "level": 7,
 180 |       "timestamp": 1785438931
 181 |     },
 182 |     {
 183 |       "index": 11,
 184 |       "event": "Accept",
 185 |       "quest_id": 8350,
 186 |       "level": 7,
 187 |       "timestamp": 1785438931
 188 |     },
 189 |     {
 190 |       "index": 12,
 191 |       "event": "Accept",
 192 |       "quest_id": 8472,
 193 |       "level": 7,
 194 |       "timestamp": 1785439040
 195 |     },
 196 |     {
 197 |       "index": 13,
 198 |       "event": "Accept",
 199 |       "quest_id": 8463,
 200 |       "level": 7,
 201 |       "timestamp": 1785439061
 202 |     },
 203 |     {
 204 |       "index": 14,
 205 |       "event": "Accept",
 206 |       "quest_id": 8468,
 207 |       "level": 7,
 208 |       "timestamp": 1785439082
 209 |     },
 210 |     {
 211 |       "index": 15,
 212 |       "event": "Complete",
 213 |       "quest_id": 8350,
 214 |       "level": 7,
 215 |       "timestamp": 1785439120
 216 |     },
 217 |     {
 218 |       "index": 16,
 219 |       "event": "Accept",
 220 |       "quest_id": 8475,
 221 |       "level": 7,
 222 |       "timestamp": 1785439242
 223 |     },
 224 |     {
 225 |       "index": 17,
 226 |       "event": "Accept",
 227 |       "quest_id": 9035,
 228 |       "level": 7,
 229 |       "timestamp": 1785439324
 230 |     },
 231 |     {
 232 |       "index": 18,
 233 |       "event": "Complete",
 234 |       "quest_id": 9035,
 235 |       "level": 7,
 236 |       "timestamp": 1785439382
 237 |     },
 238 |     {
 239 |       "index": 19,
 240 |       "event": "Accept",
 241 |       "quest_id": 9062,
 242 |       "level": 7,
 243 |       "timestamp": 1785439383
 244 |     },
 245 |     {
 246 |       "index": 20,
 247 |       "event": "Complete",
 248 |       "quest_id": 9062,
 249 |       "level": 7,
 250 |       "timestamp": 1785439499
 251 |     },
 252 |     {
 253 |       "index": 21,
 254 |       "event": "Accept",
 255 |       "quest_id": 9064,
 256 |       "level": 7,
 257 |       "timestamp": 1785439499
 258 |     },
 259 |     {
 260 |       "index": 22,
 261 |       "event": "Accept",
 262 |       "quest_id": 8482,
 263 |       "level": 7,
 264 |       "timestamp": 1785439717
 265 |     },
 266 |     {
 267 |       "index": 23,
 268 |       "event": "Accept",
 269 |       "quest_id": 8884,
 270 |       "level": 7,
 271 |       "timestamp": 1785439799
 272 |     },
 273 |     {
 274 |       "index": 24,
 275 |       "event": "Complete",
 276 |       "quest_id": 8468,
 277 |       "level": 7,
 278 |       "timestamp": 1785441271
 279 |     },
 280 |     {
 281 |       "index": 25,
 282 |       "event": "Complete",
 283 |       "quest_id": 8463,
 284 |       "level": 7,
 285 |       "timestamp": 1785441294
 286 |     },
 287 |     {
 288 |       "index": 26,
 289 |       "event": "Accept",
 290 |       "quest_id": 9352,
 291 |       "level": 7,
 292 |       "timestamp": 1785441294
 293 |     },
 294 |     {
 295 |       "index": 27,
 296 |       "event": "Complete",
 297 |       "quest_id": 8482,
 298 |       "level": 7,
 299 |       "timestamp": 1785441295
 300 |     },
 301 |     {
 302 |       "index": 28,
 303 |       "event": "LevelUp",
 304 |       "quest_id": null,
 305 |       "level": 8,
 306 |       "timestamp": 1785441295
 307 |     },
 308 |     {
 309 |       "index": 29,
 310 |       "event": "Accept",
 311 |       "quest_id": 8483,
 312 |       "level": 8,
 313 |       "timestamp": 1785441295
 314 |     },
 315 |     {
 316 |       "index": 30,
 317 |       "event": "Abandon",
 318 |       "quest_id": 8472,
 319 |       "level": 8,
 320 |       "timestamp": 1785441445
 321 |     },
 322 |     {
 323 |       "index": 31,
 324 |       "event": "Complete",
 325 |       "quest_id": 8475,
 326 |       "level": 8,
 327 |       "timestamp": 1785441813
 328 |     },
 329 |     {
 330 |       "index": 32,
 331 |       "event": "Abandon",
 332 |       "quest_id": 8884,
 333 |       "level": 8,
 334 |       "timestamp": 1785441820
 335 |     },
 336 |     {
 337 |       "index": 33,
 338 |       "event": "Complete",
 339 |       "quest_id": 9064,
 340 |       "level": 8,
 341 |       "timestamp": 1785441925
 342 |     },
 343 |     {
 344 |       "index": 34,
 345 |       "event": "Accept",
 346 |       "quest_id": 9066,
 347 |       "level": 8,
 348 |       "timestamp": 1785441926
 349 |     },
 350 |     {
 351 |       "index": 35,
 352 |       "event": "Complete",
 353 |       "quest_id": 9352,
 354 |       "level": 8,
 355 |       "timestamp": 1785442618
 356 |     },
 357 |     {
 358 |       "index": 36,
 359 |       "event": "Complete",
 360 |       "quest_id": 9066,
 361 |       "level": 8,
 362 |       "timestamp": 1785442772
 363 |     },
 364 |     {
 365 |       "index": 37,
 366 |       "event": "Complete",
 367 |       "quest_id": 8483,
 368 |       "level": 8,
 369 |       "timestamp": 1785443182
 370 |     },
 371 |     {
 372 |       "index": 38,
 373 |       "event": "LevelUp",
 374 |       "quest_id": null,
 375 |       "level": 9,
 376 |       "timestamp": 1785443182
 377 |     },
 378 |     {
 379 |       "index": 39,
 380 |       "event": "Accept",
 381 |       "quest_id": 9256,
 382 |       "level": 9,
 383 |       "timestamp": 1785443182
 384 |     },
 385 |     {
 386 |       "index": 40,
 387 |       "event": "Accept",
 388 |       "quest_id": 9395,
 389 |       "level": 9,
 390 |       "timestamp": 1785470098
 391 |     },
 392 |     {
 393 |       "index": 41,
 394 |       "event": "Accept",
 395 |       "quest_id": 9254,
 396 |       "level": 9,
 397 |       "timestamp": 1785470098
 398 |     },
 399 |     {
 400 |       "index": 42,
 401 |       "event": "Accept",
 402 |       "quest_id": 9258,
 403 |       "level": 9,
 404 |       "timestamp": 1785470133
 405 |     },
 406 |     {
 407 |       "index": 43,
 408 |       "event": "Accept",
 409 |       "quest_id": 9358,
 410 |       "level": 9,
 411 |       "timestamp": 1785470144
 412 |     },
 413 |     {
 414 |       "index": 44,
 415 |       "event": "Complete",
 416 |       "quest_id": 9256,
 417 |       "level": 9,
 418 |       "timestamp": 1785470240
 419 |     },
 420 |     {
 421 |       "index": 45,
 422 |       "event": "Accept",
 423 |       "quest_id": 8892,
 424 |       "level": 9,
 425 |       "timestamp": 1785470240
 426 |     },
 427 |     {
 428 |       "index": 46,
 429 |       "event": "Complete",
 430 |       "quest_id": 9395,
 431 |       "level": 9,
 432 |       "timestamp": 1785470339
 433 |     },
 434 |     {
 435 |       "index": 47,
 436 |       "event": "Accept",
 437 |       "quest_id": 9067,
 438 |       "level": 9,
 439 |       "timestamp": 1785470340
 440 |     },
 441 |     {
 442 |       "index": 48,
 443 |       "event": "Complete",
 444 |       "quest_id": 9258,
 445 |       "level": 9,
 446 |       "timestamp": 1785470776
 447 |     },
 448 |     {
 449 |       "index": 49,
 450 |       "event": "Accept",
 451 |       "quest_id": 8473,
 452 |       "level": 9,
 453 |       "timestamp": 1785470776
 454 |     },
 455 |     {
 456 |       "index": 50,
 457 |       "event": "Accept",
 458 |       "quest_id": 8474,
 459 |       "level": 9,
 460 |       "timestamp": 1785471145
 461 |     },
 462 |     {
 463 |       "index": 51,
 464 |       "event": "Complete",
 465 |       "quest_id": 8474,
 466 |       "level": 9,
 467 |       "timestamp": 1785471365
 468 |     },
 469 |     {
 470 |       "index": 52,
 471 |       "event": "Accept",
 472 |       "quest_id": 10166,
 473 |       "level": 9,
 474 |       "timestamp": 1785471366
 475 |     },
 476 |     {
 477 |       "index": 53,
 478 |       "event": "Complete",
 479 |       "quest_id": 10166,
 480 |       "level": 9,
 481 |       "timestamp": 1785471818
 482 |     },
 483 |     {
 484 |       "index": 54,
 485 |       "event": "LevelUp",
 486 |       "quest_id": null,
 487 |       "level": 10,
 488 |       "timestamp": 1785471818
 489 |     },
 490 |     {
 491 |       "index": 55,
 492 |       "event": "Complete",
 493 |       "quest_id": 8473,
 494 |       "level": 10,
 495 |       "timestamp": 1785471905
 496 |     },
 497 |     {
 498 |       "index": 56,
 499 |       "event": "Accept",
 500 |       "quest_id": 9144,
 501 |       "level": 10,
 502 |       "timestamp": 1785472074
 503 |     },
 504 |     {
 505 |       "index": 57,
 506 |       "event": "Complete",
 507 |       "quest_id": 8892,
 508 |       "level": 10,
 509 |       "timestamp": 1785472095
 510 |     },
 511 |     {
 512 |       "index": 58,
 513 |       "event": "Accept",
 514 |       "quest_id": 9359,
 515 |       "level": 10,
 516 |       "timestamp": 1785472095
 517 |     },
 518 |     {
 519 |       "index": 59,
 520 |       "event": "Complete",
 521 |       "quest_id": 9358,
 522 |       "level": 10,
 523 |       "timestamp": 1785472301
 524 |     },
 525 |     {
 526 |       "index": 60,
 527 |       "event": "Accept",
 528 |       "quest_id": 9252,
 529 |       "level": 10,
 530 |       "timestamp": 1785472321
 531 |     },
 532 |     {
 533 |       "index": 61,
 534 |       "event": "Accept",
 535 |       "quest_id": 8490,
 536 |       "level": 10,
 537 |       "timestamp": 1785472830
 538 |     },
 539 |     {
 540 |       "index": 62,
 541 |       "event": "Complete",
 542 |       "quest_id": 9144,
 543 |       "level": 10,
 544 |       "timestamp": 1785472964
 545 |     },
 546 |     {
 547 |       "index": 63,
 548 |       "event": "Accept",
 549 |       "quest_id": 9147,
 550 |       "level": 10,
 551 |       "timestamp": 1785472967
 552 |     },
 553 |     {
 554 |       "index": 64,
 555 |       "event": "Abandon",
 556 |       "quest_id": 9147,
 557 |       "level": 10,
 558 |       "timestamp": 1785473059
 559 |     },
 560 |     {
 561 |       "index": 65,
 562 |       "event": "Complete",
 563 |       "quest_id": 8490,
 564 |       "level": 10,
 565 |       "timestamp": 1785473403
 566 |     },
 567 |     {
 568 |       "index": 66,
 569 |       "event": "LevelUp",
 570 |       "quest_id": null,
 571 |       "level": 11,
 572 |       "timestamp": 1785473758
 573 |     },
 574 |     {
 575 |       "index": 67,
 576 |       "event": "Complete",
 577 |       "quest_id": 9252,
 578 |       "level": 11,
 579 |       "timestamp": 1785473758
 580 |     },
 581 |     {
 582 |       "index": 68,
 583 |       "event": "Complete",
 584 |       "quest_id": 9254,
 585 |       "level": 11,
 586 |       "timestamp": 1785473879
 587 |     },
 588 |     {
 589 |       "index": 69,
 590 |       "event": "Accept",
 591 |       "quest_id": 8487,
 592 |       "level": 11,
 593 |       "timestamp": 1785473880
 594 |     },
 595 |     {
 596 |       "index": 70,
 597 |       "event": "Complete",
 598 |       "quest_id": 8487,
 599 |       "level": 11,
 600 |       "timestamp": 1785475013
 601 |     },
 602 |     {
 603 |       "index": 71,
 604 |       "event": "Accept",
 605 |       "quest_id": 8488,
 606 |       "level": 11,
 607 |       "timestamp": 1785475062
 608 |     },
 609 |     {
 610 |       "index": 72,
 611 |       "event": "Abandon",
 612 |       "quest_id": 8488,
 613 |       "level": 11,
 614 |       "timestamp": 1785475157
 615 |     },
 616 |     {
 617 |       "index": 73,
 618 |       "event": "Accept",
 619 |       "quest_id": 8488,
 620 |       "level": 11,
 621 |       "timestamp": 1785475297
 622 |     },
 623 |     {
 624 |       "index": 74,
 625 |       "event": "Complete",
 626 |       "quest_id": 8488,
 627 |       "level": 11,
 628 |       "timestamp": 1785475355
 629 |     },
 630 |     {
 631 |       "index": 75,
 632 |       "event": "Accept",
 633 |       "quest_id": 9255,
 634 |       "level": 11,
 635 |       "timestamp": 1785475356
 636 |     },
 637 |     {
 638 |       "index": 76,
 639 |       "event": "Complete",
 640 |       "quest_id": 9359,
 641 |       "level": 11,
 642 |       "timestamp": 1785475491
 643 |     },
 644 |     {
 645 |       "index": 77,
 646 |       "event": "Accept",
 647 |       "quest_id": 8476,
 648 |       "level": 11,
 649 |       "timestamp": 1785475491
 650 |     },
 651 |     {
 652 |       "index": 78,
 653 |       "event": "Accept",
 654 |       "quest_id": 8477,
 655 |       "level": 11,
 656 |       "timestamp": 1785475557
 657 |     },
 658 |     {
 659 |       "index": 79,
 660 |       "event": "Accept",
 661 |       "quest_id": 8888,
 662 |       "level": 11,
 663 |       "timestamp": 1785475584
 664 |     },
 665 |     {
 666 |       "index": 80,
 667 |       "event": "Complete",
 668 |       "quest_id": 8888,
 669 |       "level": 11,
 670 |       "timestamp": 1785476896
 671 |     },
 672 |     {
 673 |       "index": 81,
 674 |       "event": "Accept",
 675 |       "quest_id": 8889,
 676 |       "level": 11,
 677 |       "timestamp": 1785476897
 678 |     },
 679 |     {
 680 |       "index": 82,
 681 |       "event": "Accept",
 682 |       "quest_id": 9394,
 683 |       "level": 11,
 684 |       "timestamp": 1785476897
 685 |     },
 686 |     {
 687 |       "index": 83,
 688 |       "event": "Complete",
 689 |       "quest_id": 8889,
 690 |       "level": 11,
 691 |       "timestamp": 1785477654
 692 |     },
 693 |     {
 694 |       "index": 84,
 695 |       "event": "Accept",
 696 |       "quest_id": 8890,
 697 |       "level": 11,
 698 |       "timestamp": 1785477654
 699 |     },
 700 |     {
 701 |       "index": 85,
 702 |       "event": "Complete",
 703 |       "quest_id": 9394,
 704 |       "level": 11,
 705 |       "timestamp": 1785478476
 706 |     },
 707 |     {
 708 |       "index": 86,
 709 |       "event": "Accept",
 710 |       "quest_id": 8894,
 711 |       "level": 11,
 712 |       "timestamp": 1785478476
 713 |     },
 714 |     {
 715 |       "index": 87,
 716 |       "event": "Accept",
 717 |       "quest_id": 8891,
 718 |       "level": 11,
 719 |       "timestamp": 1785479661
 720 |     },
 721 |     {
 722 |       "index": 88,
 723 |       "event": "Complete",
 724 |       "quest_id": 8894,
 725 |       "level": 11,
 726 |       "timestamp": 1785479818
 727 |     },
 728 |     {
 729 |       "index": 89,
 730 |       "event": "LevelUp",
 731 |       "quest_id": null,
 732 |       "level": 12,
 733 |       "timestamp": 1785479818
 734 |     },
 735 |     {
 736 |       "index": 90,
 737 |       "event": "Complete",
 738 |       "quest_id": 8890,
 739 |       "level": 12,
 740 |       "timestamp": 1785480035
 741 |     },
 742 |     {
 743 |       "index": 91,
 744 |       "event": "Complete",
 745 |       "quest_id": 8891,
 746 |       "level": 12,
 747 |       "timestamp": 1785480036
 748 |     },
 749 |     {
 750 |       "index": 92,
 751 |       "event": "Accept",
 752 |       "quest_id": 8479,
 753 |       "level": 12,
 754 |       "timestamp": 1785480726
 755 |     },
 756 |     {
 757 |       "index": 93,
 758 |       "event": "Accept",
 759 |       "quest_id": 9360,
 760 |       "level": 12,
 761 |       "timestamp": 1785481139
 762 |     },
 763 |     {
 764 |       "index": 94,
 765 |       "event": "Complete",
 766 |       "quest_id": 8479,
 767 |       "level": 12,
 768 |       "timestamp": 1785481389
 769 |     },
 770 |     {
 771 |       "index": 95,
 772 |       "event": "Complete",
 773 |       "quest_id": 8476,
 774 |       "level": 12,
 775 |       "timestamp": 1785481529
 776 |     },
 777 |     {
 778 |       "index": 96,
 779 |       "event": "LevelUp",
 780 |       "quest_id": null,
 781 |       "level": 13,
 782 |       "timestamp": 1785481530
 783 |     },
 784 |     {
 785 |       "index": 97,
 786 |       "event": "Complete",
 787 |       "quest_id": 9360,
 788 |       "level": 13,
 789 |       "timestamp": 1785481530
 790 |     },
 791 |     {
 792 |       "index": 98,
 793 |       "event": "Accept",
 794 |       "quest_id": 9363,
 795 |       "level": 13,
 796 |       "timestamp": 1785481530
 797 |     },
 798 |     {
 799 |       "index": 99,
 800 |       "event": "Complete",
 801 |       "quest_id": 8477,
 802 |       "level": 13,
 803 |       "timestamp": 1785481565
 804 |     },
 805 |     {
 806 |       "index": 100,
 807 |       "event": "Complete",
 808 |       "quest_id": 9255,
 809 |       "level": 13,
 810 |       "timestamp": 1785481770
 811 |     },
 812 |     {
 813 |       "index": 101,
 814 |       "event": "Complete",
 815 |       "quest_id": 9363,
 816 |       "level": 13,
 817 |       "timestamp": 1785481798
 818 |     },
 819 |     {
 820 |       "index": 102,
 821 |       "event": "Accept",
 822 |       "quest_id": 9327,
 823 |       "level": 13,
 824 |       "timestamp": 1785482541
 825 |     },
 826 |     {
 827 |       "index": 103,
 828 |       "event": "Complete",
 829 |       "quest_id": 9327,
 830 |       "level": 13,
 831 |       "timestamp": 1785482615
 832 |     },
 833 |     {
 834 |       "index": 104,
 835 |       "event": "Accept",
 836 |       "quest_id": 9758,
 837 |       "level": 13,
 838 |       "timestamp": 1785482616
 839 |     },
 840 |     {
 841 |       "index": 105,
 842 |       "event": "Accept",
 843 |       "quest_id": 9130,
 844 |       "level": 13,
 845 |       "timestamp": 1785484762
 846 |     },
 847 |     {
 848 |       "index": 106,
 849 |       "event": "Accept",
 850 |       "quest_id": 9152,
 851 |       "level": 13,
 852 |       "timestamp": 1785484834
 853 |     },
 854 |     {
 855 |       "index": 107,
 856 |       "event": "Complete",
 857 |       "quest_id": 9758,
 858 |       "level": 13,
 859 |       "timestamp": 1785485141
 860 |     },
 861 |     {
 862 |       "index": 108,
 863 |       "event": "Accept",
 864 |       "quest_id": 9138,
 865 |       "level": 13,
 866 |       "timestamp": 1785485141
 867 |     },
 868 |     {
 869 |       "index": 109,
 870 |       "event": "Complete",
 871 |       "quest_id": 9130,
 872 |       "level": 13,
 873 |       "timestamp": 1785485231
 874 |     },
 875 |     {
 876 |       "index": 110,
 877 |       "event": "Accept",
 878 |       "quest_id": 9133,
 879 |       "level": 13,
 880 |       "timestamp": 1785485232
 881 |     },
 882 |     {
 883 |       "index": 111,
 884 |       "event": "Accept",
 885 |       "quest_id": 9677,
 886 |       "level": 13,
 887 |       "timestamp": 1785485860
 888 |     },
 889 |     {
 890 |       "index": 112,
 891 |       "event": "Accept",
 892 |       "quest_id": 9156,
 893 |       "level": 13,
 894 |       "timestamp": 1785486194
 895 |     },
 896 |     {
 897 |       "index": 113,
 898 |       "event": "Accept",
 899 |       "quest_id": 9315,
 900 |       "level": 13,
 901 |       "timestamp": 1785486390
 902 |     },
 903 |     {
 904 |       "index": 114,
 905 |       "event": "Complete",
 906 |       "quest_id": 9138,
 907 |       "level": 13,
 908 |       "timestamp": 1785487125
 909 |     },
 910 |     {
 911 |       "index": 115,
 912 |       "event": "Accept",
 913 |       "quest_id": 9139,
 914 |       "level": 13,
 915 |       "timestamp": 1785487126
 916 |     },
 917 |     {
 918 |       "index": 116,
 919 |       "event": "Complete",
 920 |       "quest_id": 9315,
 921 |       "level": 13,
 922 |       "timestamp": 1785487145
 923 |     },
 924 |     {
 925 |       "index": 117,
 926 |       "event": "Accept",
 927 |       "quest_id": 9171,
 928 |       "level": 13,
 929 |       "timestamp": 1785487286
 930 |     },
 931 |     {
 932 |       "index": 118,
 933 |       "event": "Abandon",
 934 |       "quest_id": 9171,
 935 |       "level": 13,
 936 |       "timestamp": 1785487300
 937 |     },
 938 |     {
 939 |       "index": 119,
 940 |       "event": "Accept",
 941 |       "quest_id": 9155,
 942 |       "level": 13,
 943 |       "timestamp": 1785487354
 944 |     },
 945 |     {
 946 |       "index": 120,
 947 |       "event": "Accept",
 948 |       "quest_id": 9150,
 949 |       "level": 13,
 950 |       "timestamp": 1785487370
 951 |     },
 952 |     {
 953 |       "index": 121,
 954 |       "event": "Abandon",
 955 |       "quest_id": 9150,
 956 |       "level": 13,
 957 |       "timestamp": 1785487382
 958 |     },
 959 |     {
 960 |       "index": 122,
 961 |       "event": "Accept",
 962 |       "quest_id": 9145,
 963 |       "level": 13,
 964 |       "timestamp": 1785487394
 965 |     },
 966 |     {
 967 |       "index": 123,
 968 |       "event": "Accept",
 969 |       "quest_id": 9160,
 970 |       "level": 13,
 971 |       "timestamp": 1785487418
 972 |     },
 973 |     {
 974 |       "index": 124,
 975 |       "event": "Accept",
 976 |       "quest_id": 9192,
 977 |       "level": 13,
 978 |       "timestamp": 1785487428
 979 |     },
 980 |     {
 981 |       "index": 125,
 982 |       "event": "LevelUp",
 983 |       "quest_id": null,
 984 |       "level": 14,
 985 |       "timestamp": 1785489852
 986 |     },
 987 |     {
 988 |       "index": 126,
 989 |       "event": "Complete",
 990 |       "quest_id": 9155,
 991 |       "level": 14,
 992 |       "timestamp": 1785505022
 993 |     },
 994 |     {
 995 |       "index": 127,
 996 |       "event": "Complete",
 997 |       "quest_id": 9192,
 998 |       "level": 14,
 999 |       "timestamp": 1785505057
1000 |     },
1001 |     {
1002 |       "index": 128,
1003 |       "event": "Accept",
1004 |       "quest_id": 9199,
1005 |       "level": 14,
1006 |       "timestamp": 1785505059
1007 |     },
1008 |     {
1009 |       "index": 129,
1010 |       "event": "Abandon",
1011 |       "quest_id": 9199,
1012 |       "level": 14,
1013 |       "timestamp": 1785505075
1014 |     },
1015 |     {
1016 |       "index": 130,
1017 |       "event": "Accept",
1018 |       "quest_id": 9193,
1019 |       "level": 14,
1020 |       "timestamp": 1785505078
1021 |     },
1022 |     {
1023 |       "index": 131,
1024 |       "event": "Complete",
1025 |       "quest_id": 9152,
1026 |       "level": 14,
1027 |       "timestamp": 1785505202
1028 |     },
1029 |     {
1030 |       "index": 132,
1031 |       "event": "Abandon",
1032 |       "quest_id": 9156,
1033 |       "level": 14,
1034 |       "timestamp": 1785506310
1035 |     },
1036 |     {
1037 |       "index": 133,
1038 |       "event": "Complete",
1039 |       "quest_id": 9139,
1040 |       "level": 14,
1041 |       "timestamp": 1785506529
1042 |     },
1043 |     {
1044 |       "index": 134,
1045 |       "event": "Accept",
1046 |       "quest_id": 9140,
1047 |       "level": 14,
1048 |       "timestamp": 1785506530
1049 |     },
1050 |     {
1051 |       "index": 135,
1052 |       "event": "Abandon",
1053 |       "quest_id": 9140,
1054 |       "level": 14,
1055 |       "timestamp": 1785506562
1056 |     },
1057 |     {
1058 |       "index": 136,
1059 |       "event": "LevelUp",
1060 |       "quest_id": null,
1061 |       "level": 15,
1062 |       "timestamp": 1785506570
1063 |     },
1064 |     {
1065 |       "index": 137,
1066 |       "event": "Complete",
1067 |       "quest_id": 9160,
1068 |       "level": 15,
1069 |       "timestamp": 1785506570
1070 |     },
1071 |     {
1072 |       "index": 138,
1073 |       "event": "Accept",
1074 |       "quest_id": 9163,
1075 |       "level": 15,
1076 |       "timestamp": 1785506571
1077 |     },
1078 |     {
1079 |       "index": 139,
1080 |       "event": "Accept",
1081 |       "quest_id": 9173,
1082 |       "level": 15,
1083 |       "timestamp": 1785506610
1084 |     },
1085 |     {
1086 |       "index": 140,
1087 |       "event": "Complete",
1088 |       "quest_id": 9145,
1089 |       "level": 15,
1090 |       "timestamp": 1785506829
1091 |     },
1092 |     {
1093 |       "index": 141,
1094 |       "event": "Accept",
1095 |       "quest_id": 9143,
1096 |       "level": 15,
1097 |       "timestamp": 1785506830
1098 |     },
1099 |     {
1100 |       "index": 142,
1101 |       "event": "Abandon",
1102 |       "quest_id": 9143,
1103 |       "level": 15,
1104 |       "timestamp": 1785506840
1105 |     },
1106 |     {
1107 |       "index": 143,
1108 |       "event": "Accept",
1109 |       "quest_id": 9158,
1110 |       "level": 15,
1111 |       "timestamp": 1785507010
1112 |     },
1113 |     {
1114 |       "index": 144,
1115 |       "event": "Accept",
1116 |       "quest_id": 9276,
1117 |       "level": 15,
1118 |       "timestamp": 1785507048
1119 |     },
1120 |     {
1121 |       "index": 145,
1122 |       "event": "Accept",
1123 |       "quest_id": 9274,
1124 |       "level": 15,
1125 |       "timestamp": 1785507061
1126 |     },
1127 |     {
1128 |       "index": 146,
1129 |       "event": "Accept",
1130 |       "quest_id": 9214,
1131 |       "level": 15,
1132 |       "timestamp": 1785507069
1133 |     },
1134 |     {
1135 |       "index": 147,
1136 |       "event": "Abandon",
1137 |       "quest_id": 9214,
1138 |       "level": 15,
1139 |       "timestamp": 1785507073
1140 |     },
1141 |     {
1142 |       "index": 148,
1143 |       "event": "Complete",
1144 |       "quest_id": 9158,
1145 |       "level": 15,
1146 |       "timestamp": 1785508907
1147 |     },
1148 |     {
1149 |       "index": 149,
1150 |       "event": "Accept",
1151 |       "quest_id": 9159,
1152 |       "level": 15,
1153 |       "timestamp": 1785508908
1154 |     },
1155 |     {
1156 |       "index": 150,
1157 |       "event": "Complete",
1158 |       "quest_id": 9276,
1159 |       "level": 15,
1160 |       "timestamp": 1785508928
1161 |     },
1162 |     {
1163 |       "index": 151,
1164 |       "event": "Accept",
1165 |       "quest_id": 9277,
1166 |       "level": 15,
1167 |       "timestamp": 1785508928
1168 |     },
1169 |     {
1170 |       "index": 152,
1171 |       "event": "Complete",
1172 |       "quest_id": 9274,
1173 |       "level": 15,
1174 |       "timestamp": 1785508949
1175 |     },
1176 |     {
1177 |       "index": 153,
1178 |       "event": "LevelUp",
1179 |       "quest_id": null,
1180 |       "level": 16,
1181 |       "timestamp": 1785512311
1182 |     },
1183 |     {
1184 |       "index": 154,
1185 |       "event": "Complete",
1186 |       "quest_id": 9277,
1187 |       "level": 16,
1188 |       "timestamp": 1785512733
1189 |     },
1190 |     {
1191 |       "index": 155,
1192 |       "event": "Accept",
1193 |       "quest_id": 9212,
1194 |       "level": 16,
1195 |       "timestamp": 1785514203
1196 |     },
1197 |     {
1198 |       "index": 156,
1199 |       "event": "Accept",
1200 |       "quest_id": 9212,
1201 |       "level": 16,
1202 |       "timestamp": 1785514725
1203 |     },
1204 |     {
1205 |       "index": 157,
1206 |       "event": "Accept",
1207 |       "quest_id": 9212,
1208 |       "level": 16,
1209 |       "timestamp": 1785515433
1210 |     },
1211 |     {
1212 |       "index": 158,
1213 |       "event": "Complete",
1214 |       "quest_id": 9212,
1215 |       "level": 16,
1216 |       "timestamp": 1785515839
1217 |     },
1218 |     {
1219 |       "index": 159,
1220 |       "event": "Accept",
1221 |       "quest_id": 9214,
1222 |       "level": 16,
1223 |       "timestamp": 1785515840
1224 |     },
1225 |     {
1226 |       "index": 160,
1227 |       "event": "Abandon",
1228 |       "quest_id": 9214,
1229 |       "level": 16,
1230 |       "timestamp": 1785515870
1231 |     },
1232 |     {
1233 |       "index": 161,
1234 |       "event": "Complete",
1235 |       "quest_id": 9193,
1236 |       "level": 16,
1237 |       "timestamp": 1785516109
1238 |     },
1239 |     {
1240 |       "index": 162,
1241 |       "event": "Accept",
1242 |       "quest_id": 9175,
1243 |       "level": 16,
1244 |       "timestamp": 1785518440
1245 |     },
1246 |     {
1247 |       "index": 163,
1248 |       "event": "LevelUp",
1249 |       "quest_id": null,
1250 |       "level": 17,
1251 |       "timestamp": 1785519334
1252 |     },
1253 |     {
1254 |       "index": 164,
1255 |       "event": "Complete",
1256 |       "quest_id": 9173,
1257 |       "level": 17,
1258 |       "timestamp": 1785520640
1259 |     },
1260 |     {
1261 |       "index": 165,
1262 |       "event": "Complete",
1263 |       "quest_id": 9175,
1264 |       "level": 17,
1265 |       "timestamp": 1785520641
1266 |     },
1267 |     {
1268 |       "index": 166,
1269 |       "event": "Accept",
1270 |       "quest_id": 9180,
1271 |       "level": 17,
1272 |       "timestamp": 1785520641
1273 |     },
1274 |     {
1275 |       "index": 167,
1276 |       "event": "Complete",
1277 |       "quest_id": 9163,
1278 |       "level": 17,
1279 |       "timestamp": 1785520643
1280 |     },
1281 |     {
1282 |       "index": 168,
1283 |       "event": "Accept",
1284 |       "quest_id": 9166,
1285 |       "level": 17,
1286 |       "timestamp": 1785520644
1287 |     },
1288 |     {
1289 |       "index": 169,
1290 |       "event": "Accept",
1291 |       "quest_id": 9281,
1292 |       "level": 17,
1293 |       "timestamp": 1785520795
1294 |     },
1295 |     {
1296 |       "index": 170,
1297 |       "event": "Accept",
1298 |       "quest_id": 9282,
1299 |       "level": 17,
1300 |       "timestamp": 1785521230
1301 |     },
1302 |     {
1303 |       "index": 171,
1304 |       "event": "Accept",
1305 |       "quest_id": 9220,
1306 |       "level": 17,
1307 |       "timestamp": 1785521249
1308 |     },
1309 |     {
1310 |       "index": 172,
1311 |       "event": "Complete",
1312 |       "quest_id": 9166,
1313 |       "level": 17,
1314 |       "timestamp": 1785521434
1315 |     },
1316 |     {
1317 |       "index": 173,
1318 |       "event": "Accept",
1319 |       "quest_id": 9169,
1320 |       "level": 17,
1321 |       "timestamp": 1785521434
1322 |     },
1323 |     {
1324 |       "index": 174,
1325 |       "event": "Complete",
1326 |       "quest_id": 9159,
1327 |       "level": 17,
1328 |       "timestamp": 1785521630
1329 |     },
1330 |     {
1331 |       "index": 175,
1332 |       "event": "Complete",
1333 |       "quest_id": 9282,
1334 |       "level": 17,
1335 |       "timestamp": 1785521789
1336 |     },
1337 |     {
1338 |       "index": 176,
1339 |       "event": "Accept",
1340 |       "quest_id": 9161,
1341 |       "level": 17,
1342 |       "timestamp": 1785521790
1343 |     },
1344 |     {
1345 |       "index": 177,
1346 |       "event": "Accept",
1347 |       "quest_id": 9275,
1348 |       "level": 17,
1349 |       "timestamp": 1785521822
1350 |     },
1351 |     {
1352 |       "index": 178,
1353 |       "event": "Complete",
1354 |       "quest_id": 9161,
1355 |       "level": 17,
1356 |       "timestamp": 1785522172
1357 |     },
1358 |     {
1359 |       "index": 179,
1360 |       "event": "Accept",
1361 |       "quest_id": 9162,
1362 |       "level": 17,
1363 |       "timestamp": 1785522173
1364 |     },
1365 |     {
1366 |       "index": 180,
1367 |       "event": "LevelUp",
1368 |       "quest_id": null,
1369 |       "level": 18,
1370 |       "timestamp": 1785522284
1371 |     },
1372 |     {
1373 |       "index": 181,
1374 |       "event": "Complete",
1375 |       "quest_id": 9162,
1376 |       "level": 18,
1377 |       "timestamp": 1785522284
1378 |     },
1379 |     {
1380 |       "index": 182,
1381 |       "event": "Accept",
1382 |       "quest_id": 9172,
1383 |       "level": 18,
1384 |       "timestamp": 1785522285
1385 |     },
1386 |     {
1387 |       "index": 183,
1388 |       "event": "Complete",
1389 |       "quest_id": 9172,
1390 |       "level": 18,
1391 |       "timestamp": 1785523718
1392 |     },
1393 |     {
1394 |       "index": 184,
1395 |       "event": "Accept",
1396 |       "quest_id": 9176,
1397 |       "level": 18,
1398 |       "timestamp": 1785523719
1399 |     },
1400 |     {
1401 |       "index": 185,
1402 |       "event": "Complete",
1403 |       "quest_id": 9281,
1404 |       "level": 18,
1405 |       "timestamp": 1785523869
1406 |     },
1407 |     {
1408 |       "index": 186,
1409 |       "event": "Complete",
1410 |       "quest_id": 9176,
1411 |       "level": 18,
1412 |       "timestamp": 1785524781
1413 |     },
1414 |     {
1415 |       "index": 187,
1416 |       "event": "Accept",
1417 |       "quest_id": 9167,
1418 |       "level": 18,
1419 |       "timestamp": 1785524782
1420 |     },
1421 |     {
1422 |       "index": 188,
1423 |       "event": "Complete",
1424 |       "quest_id": 9169,
1425 |       "level": 18,
1426 |       "timestamp": 1785524997
1427 |     },
1428 |     {
1429 |       "index": 189,
1430 |       "event": "Accept",
1431 |       "quest_id": 9215,
1432 |       "level": 18,
1433 |       "timestamp": 1785525171
1434 |     },
1435 |     {
1436 |       "index": 190,
1437 |       "event": "LevelUp",
1438 |       "quest_id": null,
1439 |       "level": 19,
1440 |       "timestamp": 1785525238
1441 |     },
1442 |     {
1443 |       "index": 191,
1444 |       "event": "Complete",
1445 |       "quest_id": 9275,
1446 |       "level": 19,
1447 |       "timestamp": 1785525238
1448 |     },
1449 |     {
1450 |       "index": 192,
1451 |       "event": "Complete",
1452 |       "quest_id": 9215,
1453 |       "level": 19,
1454 |       "timestamp": 1785526308
1455 |     },
1456 |     {
1457 |       "index": 193,
1458 |       "event": "Accept",
1459 |       "quest_id": 9214,
1460 |       "level": 19,
1461 |       "timestamp": 1785526309
1462 |     },
1463 |     {
1464 |       "index": 194,
1465 |       "event": "Abandon",
1466 |       "quest_id": 9214,
1467 |       "level": 19,
1468 |       "timestamp": 1785526338
1469 |     },
1470 |     {
1471 |       "index": 195,
1472 |       "event": "Complete",
1473 |       "quest_id": 9167,
1474 |       "level": 19,
1475 |       "timestamp": 1785529540
1476 |     },
1477 |     {
1478 |       "index": 196,
1479 |       "event": "Accept",
1480 |       "quest_id": 9328,
1481 |       "level": 19,
1482 |       "timestamp": 1785529541
1483 |     },
1484 |     {
1485 |       "index": 197,
1486 |       "event": "LevelUp",
1487 |       "quest_id": null,
1488 |       "level": 20,
1489 |       "timestamp": 1785529565
1490 |     },
1491 |     {
1492 |       "index": 198,
1493 |       "event": "Complete",
1494 |       "quest_id": 9220,
1495 |       "level": 20,
1496 |       "timestamp": 1785529565
1497 |     },
1498 |     {
1499 |       "index": 199,
1500 |       "event": "Accept",
1501 |       "quest_id": 9170,
1502 |       "level": 20,
1503 |       "timestamp": 1785529565
1504 |     },
1505 |     {
1506 |       "index": 200,
1507 |       "event": "Accept",
1508 |       "quest_id": 9877,
1509 |       "level": 20,
1510 |       "timestamp": 1785529594
1511 |     },
1512 |     {
1513 |       "index": 201,
1514 |       "event": "Accept",
1515 |       "quest_id": 9214,
1516 |       "level": 20,
1517 |       "timestamp": 1785529771
1518 |     },
1519 |     {
1520 |       "index": 202,
1521 |       "event": "Abandon",
1522 |       "quest_id": 9214,
1523 |       "level": 20,
1524 |       "timestamp": 1785529780
1525 |     },
1526 |     {
1527 |       "index": 203,
1528 |       "event": "Complete",
1529 |       "quest_id": 9877,
1530 |       "level": 20,
1531 |       "timestamp": 1785530086
1532 |     },
1533 |     {
1534 |       "index": 204,
1535 |       "event": "Accept",
1536 |       "quest_id": 9164,
1537 |       "level": 20,
1538 |       "timestamp": 1785530087
1539 |     },
1540 |     {
1541 |       "index": 205,
1542 |       "event": "Complete",
1543 |       "quest_id": 9133,
1544 |       "level": 20,
1545 |       "timestamp": 1785531570
1546 |     },
1547 |     {
1548 |       "index": 206,
1549 |       "event": "Accept",
1550 |       "quest_id": 9134,
1551 |       "level": 20,
1552 |       "timestamp": 1785531573
1553 |     },
1554 |     {
1555 |       "index": 207,
1556 |       "event": "Complete",
1557 |       "quest_id": 9677,
1558 |       "level": 20,
1559 |       "timestamp": 1785531875
1560 |     },
1561 |     {
1562 |       "index": 208,
1563 |       "event": "Accept",
1564 |       "quest_id": 9678,
1565 |       "level": 20,
1566 |       "timestamp": 1785531875
1567 |     },
1568 |     {
1569 |       "index": 209,
1570 |       "event": "Accept",
1571 |       "quest_id": 9690,
1572 |       "level": 20,
1573 |       "timestamp": 1785531876
1574 |     },
1575 |     {
1576 |       "index": 210,
1577 |       "event": "Complete",
1578 |       "quest_id": 9328,
1579 |       "level": 20,
1580 |       "timestamp": 1785531968
1581 |     },
1582 |     {
1583 |       "index": 211,
1584 |       "event": "Accept",
1585 |       "quest_id": 9621,
1586 |       "level": 20,
1587 |       "timestamp": 1785531969
1588 |     }
1589 |   ]
1590 | }
1591 | 
```

### wow-quest-route/docs/task-library/46-55-ungoro.md

Bytes: 5762
SHA-256: f58f5d663e793cbe65601b8a3882aea0cf2ceb63833a0ac872316c03461662d3
Lines: 1-57 of 57

```markdown
 1 | # 46—55级人工任务卡：安戈洛环形山
 2 | 
 3 | 适用条件：五个约52—53级圣骑士，从灼热峡谷结束后回到加基森，经南口进入安戈洛；最终要去幽暗城。核验日期：2026-08-08。当前服实测优先于本页。
 4 | 
 5 | ## 入口和托尔瓦任务
 6 | 
 7 | | 任务 | 等级、目标和机制 | 实际路线判断 |
 8 | | --- | --- | --- |
 9 | | 3844→3845《无人知晓的秘密》 | 最低47、任务52；入口附近湖边固定物和短跑腿，五号逐个点击 | 必做；去马绍尔营地前完成，3908冬泉谷后续不接 |
10 | | 4290《拉克维的食物》 | 最低48、任务53；固定蛇颈龙尸体取1块肉，五号逐个点 | 必做；从南口进入后先做，回托尔瓦交并接4291 |
11 | | 4291《拉克维的气味》 | 2只拉克维的配偶，任务腺体100%参考掉落 | 必做；东南侧同一小区完成，回托尔瓦接4292 |
12 | | 4292《拉克维的诱饵》 | 最低48、任务56；东部水晶塔后小径79,49，先把肉放平石，再把信息素用于肉，56级非精英拉克维从来路出现 | 必做；五圣骑士53级无战斗难度。把召唤留到本区最后，杀后回南口托尔瓦交并直接出图 |
13 | | 4289《安戈洛的猩猩》 | 最低47、任务55；每号三类毛皮各2，每类参考100%。普通FFA任务物一尸只由一个缺对应毛皮的角色拾取；不能把100%理解成一尸五份 | 必做；与A-Me同洞，最后和4292一起在南口交 |
14 | | 4301《强大的尤尔查》 | 4289交付后才可接，目标尤尔查却在东北猩猩洞最深处 | 跳过。当前环线先经过东北洞、最后在南口交4289；为4301再穿整图进洞并返回南口是一次完整折返，16,300经验抵不过交通 |
15 | 
16 | ## 马绍尔营地和两段护送
17 | 
18 | | 任务 | 核验事实 | 结论和新手说明 |
19 | | --- | --- | --- |
20 | | 4492→4491《走丢了！》/《朋友的帮助》 | 林格在火羽山洞内；4491没有脚本伏击，林格跟随速度快且可以骑马。会多次晕倒，必须用任务给的水壶唤醒；有25分钟计时 | 必做。把水壶拖动作条，始终选中林格；走到营地NPC附近后继续靠近洞口方向，直到完成提示，不要只站NPC旁等 |
21 | | 974《究根问底》 | 最低47、任务52；火羽山固定点使用测温器 | 必做；与找林格同一次进火山完成，交后不接跨区后续980 |
22 | | 4243→4244→4245《找回A-Me 01》 | A-Me在东北洞内沿右墙深处约69,18；4244每号需要1个秘银外壳。4245无脚本伏击，但猩猩会呼救、刷新快，A-Me走太远会直接失败 | 条件必做：进图前五号各有1个秘银外壳才推进4244/4245；否则只做4243。启动前清洞口和外侧猩猩，五号都与A-Me完成外壳步骤，再由主控启动共享护送；不要采矿或离开A-Me视野 |
23 | 
24 | ## 一圈固定任务
25 | 
26 | | 任务 | 数量、点位和五开机制 | 结论 |
27 | | --- | --- | --- |
28 | | 4145《拉瑞安和穆尔金》 | 四类血瓣花各5只，共20次共享击杀；不是4141的低掉率幼苗收集 | 必做；全图环线自然完成，交后4147会把路线带去棘齿城，不接 |
29 | | 3881《抢救物资》 | 食物箱和研究设备各1处固定物，五号逐个点击 | 必做；按地图标记在环线经过时拿，不为刷新原地等，先检查是否有人刚点过 |
30 | | 3883《异型的生态》 | 南部虫巢入口约50,77；进洞第一个岔口向左，到48,85圆形房中央使用背包里的刮取器，不是寻找可点击样本 | 必做。虫怪约50—54级、巡逻和刷新较快，五号到齐后清房再逐个使用 |
31 | | 4501《当心翼手龙》 | 10只狂怒翼手龙，共享击杀，任务55 | 必做；沿西南/南部环线完成 |
32 | | 3884《威利德的日记》 | 被撕破的日记是自然掉落触发 | 自然掉到的角色做，不为凑齐五号刷 |
33 | | 4244秘银外壳、4449丝绸类备料 | 都是“已有材料则把任务变短”的条件，不是到现场临时收材料 | 进入区域前只检查一次；没有就按无材料路线走 |
34 | 
35 | ## 推荐环线依据
36 | 
37 | 1. 南口先完成4290→4291的两次短往返，4292只接不召唤。
38 | 2. 去马绍尔营地接齐任务；先进入火羽山同时做974、找到林格并护送回营地。
39 | 3. 去东北猩猩洞，一次完成4289、4243和有备料时的4244→4245；护送结束回到营地。
40 | 4. 从营地开始外圈，完成4145、3881、4501和南部3883。
41 | 5. 东行到79,49召唤拉克维，杀完向南回托尔瓦；交4292和4289后直接走南口回加基森。不要再回马绍尔营地，也不要为4301第二次横穿地图。
42 | 
43 | 这样安排解决旧正文的两个折返：旧路线先在南口接4301又回东北杀尤尔查，再从南口折回马绍尔飞走；新路线不接4301，并从南口直接离图。
44 | 
45 | ## 来源
46 | 
47 | - [A-Me护送](https://www.wowhead.com/wotlk/quest=4245/chasing-a-me-01)：洞口清怪、呼救、跟丢失败和每人秘银外壳。
48 | - [林格护送](https://www.wowhead.com/wotlk/quest=4491/a-little-help-from-my-friends)：无伏击、可骑马、水壶和终点触发。
49 | - [异型的生态](https://www.wowhead.com/wotlk/quest=3883/alien-ecology)：洞口、左转和房间中央使用任务物。
50 | - [拉克维的诱饵](https://www.wowhead.com/wotlk/quest=4292/the-bait-for-larkorwi)：79,49平石、放肉后抹信息素、56级非精英。
51 | 
52 | ## 尚需实服回填
53 | 
54 | - 《安戈洛的猩猩》（4289）先按普通FFA“一尸一号”轮换拾取；首次现场只检查它是否存在任务特有的多人可取例外，不能因参考100%就推定每怪全队都涨。
55 | - 4245共享护送弹窗在五号完成4244后是否一次启动全队接受；用户已有普通护送共享经验，但该任务仍以首次现场为准。
56 | - 3881固定箱在当前服是一物多人连续点击还是点击后短暂消失。
57 | 
```

## Skipped Files

- wow-quest-route/data/routes/world-candidate/490-un-goro-crater/route.json [File is too large (258341 bytes). Limit: 180000 bytes.]
