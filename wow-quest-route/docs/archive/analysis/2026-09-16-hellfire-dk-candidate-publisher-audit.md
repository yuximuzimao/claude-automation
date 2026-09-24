# Hellfire DK Candidate Publisher Semantic Audit — 2026-09-16

Status: **pilot passed with `unclassified=0`; candidate only, no formal cutover**.

Profile: `hellfire-dk-speed`
Publish key: `hellfire_dk`
Candidate JSON: `data/route-atlas/candidates/hellfire_dk.json`
Candidate HTML: `data/routes/route-atlas-workbench-candidate-hellfire_dk.html`
Formal comparison source: current `data/route-atlas/workbench-routes.json#hellfire_dk`

## 1. Exact structural equivalence

The candidate and current formal route are identical on the route-level fields that should survive publication unchanged:

- order/title/displayName/sub/footer/image/hearthChain
- route timing: `330` minutes, range `[243, 436]`
- 63 route points
- every point x/y coordinate, point title, phase and transport value
- 11 map labels, including independent label coordinates
- 11 step groups
- every step title, summary and timing budget

The first Publisher audit exposed that the current page carries 11 curated floating zhCN map labels whose display coordinates can intentionally differ from route-point coordinates. These are UI hints, not route geometry truth. They are therefore preserved losslessly in `data/route-ui/hellfire-dk-speed.json` and consumed by Publisher from the UI layer; they do not enter Route Profile.

## 2. Task/action equivalence

The Route Profile now contains 230 actions. Of these, 153 are task actions (`accept/objective/turnin`). Candidate publication renders all 153 in the same order with the same task IDs.

Actor audit: all published accept/turn-in task occurrences with a structured `npc_name` or `target_name` resolve to the same actor; mismatch count = `0`.

System-action counts preserve the current route:

- open flight point: 3
- bind hearth: 1
- use hearth: 2
- system taxi: 2
- quest transport: 1

In addition, three route atoms were restored from legacy prose because they are real player movement, not presentation text:

1. fixed transport: `奥格瑞玛·精神谷传送门区 → 诅咒之地·黑暗之门前`
2. fixed transport: `诅咒之地·黑暗之门 → 外域·黑暗之门`
3. land move: `塞纳里奥哨站 → 赞加沼泽·塞纳里奥庇护所`

These were previously embedded inside two long legacy action sentences and were dropped by the first Profile migration. Their restoration is classified as **data migration omission fixed**, not an architecture redesign.

The same audit caught and fixed a legacy migration-parser regression where the first route line could incorrectly assign `奥格瑞玛` as the NPC for task 9407/10120. The Profile now locks the audited actors:

- 9407 accept: 督军达图恩
- 9407 turn-in: 沃雷恩中将
- 10120 accept: 沃雷恩中将

## 3. Ordinary note equivalence

Current formal `hellfire_dk` contains 16 non-empty ordinary point notes.

After candidate audit:

- 13/16 are preserved verbatim in projected Presentation.
- the remaining three are semantically represented without duplicating stale route prose:
  - 《肮脏的工作》: Task Card Presentation already contains the same execution mechanic with slightly normalized wording.
  - 《遗失的信件》 at the Great Fissure: replaced by the structured conditional accept `when=has_item(被腐蚀的皮箱)` plus Task Card guide; if the item did not drop, the route simply skips the action.
  - 《遗失的信件》 at Cenarion Post: replaced by the structured conditional turn-in `when=task_active(9373)`; no extra farming/return is introduced.

Four short legacy notes that still had independent player value were found missing from Presentation and restored losslessly with the deferred marker `【需要单独修正优化】`:

- 10369 《阿尔泽斯之死》 — use the elder staff before the kill
- 10286 《埃雷利恩的秘密》 — Alidis patrols the road outside Falcon Watch
- 9472 《埃雷利恩的“恋人”》 — lure Viera away before using the scroll
- 10351 《自然的治愈》 — use the Seed of Revitalization in the earthbinder circle

The deferred marker stays in Task Card storage for the later note-cleanup pass, but `project_task_presentation()` strips the marker from player output.

## 4. Fivebox equivalence and intentional workflow separation

The old Hellfire DK page contains 24 fivebox text blocks:

- 6 are already-tested conclusions.
- 18 are validation prompts/questions.

The six tested conclusions are represented by current Task Card coarse statuses rather than copied prose:

- 10208 《阻断援军》 → `special`
- 10129 《任务：穆尔凯斯和沙德拉兹之门》 → `special`
- 10162 《任务：地狱岩床》 → `shared`
- 10220 《聆听之魂》 → `shared`; 10229 《解读书卷》 retains its own personal-pickup status/facts
- 10809 《通缉：座狼主宰卡鲁什》 → `shared`
- 10792 《燃烧吧，塞斯高！》 → `shared`; 10813 《格里洛克之眼》 remains `pending`

The 18 unresolved questions intentionally do **not** remain task facts. They are preserved in `tasks/task-card-migration/fivebox-validation-todo.json`; corresponding Task Cards remain `pending`. Candidate output shows the pending badge but does not present the question text as if it were a confirmed fact. This is an **expected architecture improvement**, not information loss.

## 5. Candidate/UI contract

The candidate uses the existing Route Atlas UI shell but receives route payload only from:

`Route Profile + Task Card/Task Presentation + Timing Model`.

It does not write `workbench-routes.json` or the formal `route-atlas-workbench.html`.

The old common Builder's closed-action parser is not used as a new-Profile truth validator: `hellfire_dk` is already an explicit legacy exemption, and that parser conflates the first textual token with the structured point title/NPC. New Publisher correctness is instead guarded by Route Profile schema/semantic validation plus Publisher tests that compare the rendered task-action sequence against the Profile action IDs.

## 6. Difference classification

- Expected improvement: fivebox validation questions moved to workflow ledger; deferred marker hidden from player output.
- Data migration omission fixed: independent map-label coordinates; two endpoint movement sentences; first-line task NPC regression; four useful legacy short notes.
- Conversion implementation bug fixed: migration task-name index no longer fails because unrelated maps contain same-name task chains.
- Structure/model gap remaining: **0**.
- Unclassified differences remaining: **0**.

## 7. Gate result

`hellfire-dk-speed` is suitable as the Publisher pilot and can be used as the reference implementation for migrating the remaining Route Profiles.

This audit does **not** authorize formal cutover yet. Formal `hellfire_dk` remains unchanged until the remaining route profiles are migrated and the project-wide candidate replacement gate is satisfied.
