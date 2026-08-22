from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VIDEO_ROOT = ROOT.parent / ".ai-bridge" / "wow-video-extraction"
OUT_DIR = ROOT / "data" / "video-route"
ARCHIVE_DIR = ROOT / "docs" / "archive" / "analysis"
QUESTIE_ZIP = ROOT / "_sandbox" / "sources" / "Questie-v11.32.3.zip"

MASTER_OUT = OUT_DIR / "master-events.json"
BOUNDARY_OUT = OUT_DIR / "episode-boundaries.json"
GAPS_OUT = OUT_DIR / "cross-episode-gaps.json"
MASTER_REPORT = ARCHIVE_DIR / "video-route-master-audit.md"
GAPS_REPORT = ARCHIVE_DIR / "video-route-cross-episode-audit.md"

END_STATE_KEYS = (
    "unclosed_or_uncertain_quests",
    "accepted_or_active_unclosed",
    "ending_active_or_unclosed_quests",
    "explicitly_incomplete_at_episode_end",
    "carried_uncertainties_no_new_direct_evidence",
)

TIME_RE = re.compile(r"(?<!\d)(?:(\d+):)?(\d{1,2}):(\d{2})(?!\d)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_seconds(data: dict[str, Any]) -> int:
    for key in ("duration_seconds", "duration_seconds_stable", "playlist_duration_seconds"):
        value = data.get(key)
        if isinstance(value, (int, float)):
            return int(round(float(value)))
    raise ValueError(f"episode {data.get('episode')} has no numeric duration")


def parse_time_seconds(value: Any, duration: int | None = None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    if text in {"episode_end", "end", "episode end"} and duration is not None:
        return float(duration)
    match = TIME_RE.search(text)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    return float(hours * 3600 + minutes * 60 + seconds)


def event_time(event: dict[str, Any], duration: int) -> float | None:
    for key in (
        "time_seconds",
        "time_seconds_approx",
        "time",
        "time_range",
    ):
        if key in event:
            parsed = parse_time_seconds(event.get(key), duration)
            if parsed is not None:
                return parsed
    return None


def normalized_experience(event: dict[str, Any]) -> tuple[int | float | None, str | None]:
    preferred = (
        "experience",
        "experience_shown",
        "experience_observed",
        "experience_observed_value",
        "experience_observed_or_calibrated",
        "experience_calibrated",
        "quest_experience",
        "xp",
    )
    for key in preferred:
        value = event.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value, key
    return None, None


def action_class(action: str) -> str:
    a = action.lower().strip()
    if "objective_complete_not_turnin" in a:
        return "objective"
    if "reward_window" in a and ("not" in a or "unproven" in a or "proven" in a):
        return "uncertain"
    if "abandon" in a:
        return "abandon"
    if "level" in a:
        return "level"
    if "discover" in a or "exploration" in a:
        return "discover"
    if "objective" in a or "progress" in a:
        return "objective"
    if "complete" in a:
        return "complete"
    if "accept" in a:
        return "accept"
    if "active" in a or "unclosed" in a or "held" in a:
        return "state"
    return "other"


def quest_key(quest_id: Any, quest_name: Any) -> str | None:
    if isinstance(quest_id, int):
        return f"id:{quest_id}"
    if isinstance(quest_id, str) and quest_id.isdigit():
        return f"id:{int(quest_id)}"
    if isinstance(quest_name, str) and quest_name.strip():
        return f"name:{quest_name.strip()}"
    return None


def end_states(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any, str]] = set()
    for section in END_STATE_KEYS:
        value = data.get(section)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            qid = item.get("quest_id")
            name = item.get("quest_name") or item.get("name")
            state = item.get("state") or "listed_unclosed"
            key = (qid, name, state, section)
            if key in seen:
                continue
            seen.add(key)
            row = dict(item)
            row["quest_name"] = name
            row["state"] = state
            row["source_section"] = section
            rows.append(row)
    return rows


def normalize_event(
    episode: int,
    title: str,
    bvid: str | None,
    duration: int,
    cumulative_start: int,
    source_path: Path,
    source_kind: str,
    index: int,
    raw: dict[str, Any],
    forced_action: str | None = None,
) -> dict[str, Any]:
    action = forced_action or str(raw.get("action") or "unknown")
    seconds = event_time(raw, duration)
    xp, xp_field = normalized_experience(raw)
    qid = raw.get("quest_id")
    if isinstance(qid, str) and qid.isdigit():
        qid = int(qid)
    name = raw.get("quest_name") or raw.get("name")
    canonical = {
        "event_id": f"ep{episode}:{source_kind}:{index}",
        "episode": episode,
        "episode_title": title,
        "bvid": bvid,
        "source_kind": source_kind,
        "source_event_index": index,
        "source_json": str(source_path),
        "original_action": action,
        "action_class": action_class(action),
        "quest_id": qid,
        "quest_name": name,
        "quest_key": quest_key(qid, name),
        "time_range": raw.get("time_range"),
        "episode_seconds_start": seconds,
        "series_seconds_start": (cumulative_start + seconds) if seconds is not None else None,
        "confidence": raw.get("confidence"),
        "experience": xp,
        "experience_source_field": xp_field,
        "next_quest_id": raw.get("next_quest_id") or raw.get("followup_accepted_quest_id"),
        "next_quest_name": raw.get("next_quest_name"),
        "objective": raw.get("objective"),
        "basis": raw.get("basis") or raw.get("evidence") or raw.get("note"),
        "synthetic_normalized": source_kind not in {"events", "level_evidence"},
        "raw": raw,
    }
    return canonical


def build() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    all_events: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    cumulative = 0
    source_hashes: dict[str, str] = {}

    for episode in range(1, 54):
        path = VIDEO_ROOT / f"episode-{episode}-events.json"
        if not path.exists():
            raise FileNotFoundError(path)
        data = load_json(path)
        if int(data.get("episode", -1)) != episode:
            raise ValueError(f"episode mismatch in {path}")
        duration = duration_seconds(data)
        title = str(data.get("title") or f"episode {episode}")
        bvid = data.get("bvid")
        digest = sha256(path)
        source_hashes[str(path)] = digest

        episode_events: list[dict[str, Any]] = []
        raw_events = data.get("events")
        if isinstance(raw_events, list):
            for i, raw in enumerate(raw_events):
                if isinstance(raw, dict):
                    episode_events.append(
                        normalize_event(episode, title, bvid, duration, cumulative, path, "events", i, raw)
                    )
        else:
            # Early backfill schemas (episodes 1-3) stored completion/accept facts in separate arrays.
            completed = data.get("completed_quest_details") or []
            for i, raw in enumerate(completed):
                if isinstance(raw, dict):
                    episode_events.append(
                        normalize_event(
                            episode, title, bvid, duration, cumulative, path,
                            "completed_quest_details", i, raw, forced_action="complete"
                        )
                    )
            accepted = data.get("acceptance_events") or []
            for i, raw in enumerate(accepted):
                if isinstance(raw, dict):
                    episode_events.append(
                        normalize_event(
                            episode, title, bvid, duration, cumulative, path,
                            "acceptance_events", i, raw, forced_action="accept"
                        )
                    )

        # Add direct/inferred level evidence as a separate query layer unless already represented.
        level_rows = data.get("level_evidence") or []
        existing_levels = {
            (e.get("raw", {}).get("level"), e.get("episode_seconds_start"))
            for e in episode_events
            if e.get("action_class") == "level"
        }
        for i, raw in enumerate(level_rows):
            if not isinstance(raw, dict):
                continue
            seconds = event_time(raw, duration)
            marker = (raw.get("level"), seconds)
            if marker in existing_levels:
                continue
            level_action = "level_up_direct" if raw.get("direct") is True or "direct" in str(raw.get("type", "")) else "level_evidence"
            episode_events.append(
                normalize_event(
                    episode, title, bvid, duration, cumulative, path,
                    "level_evidence", i, {**raw, "action": level_action}
                )
            )

        episode_events.sort(
            key=lambda e: (
                e["episode_seconds_start"] is None,
                e["episode_seconds_start"] if e["episode_seconds_start"] is not None else 10**12,
                e["source_kind"],
                e["source_event_index"],
            )
        )
        for seq, event in enumerate(episode_events):
            event["sequence_in_episode"] = seq
            event["series_sequence"] = len(all_events)
            all_events.append(event)

        states = end_states(data)
        boundaries.append(
            {
                "episode": episode,
                "title": title,
                "bvid": bvid,
                "duration_seconds": duration,
                "series_seconds_start": cumulative,
                "series_seconds_end": cumulative + duration,
                "source_json": str(path),
                "source_sha256": digest,
                "normalized_event_count": len(episode_events),
                "raw_events_present": isinstance(raw_events, list),
                "synthetic_early_schema": not isinstance(raw_events, list),
                "ending_states": states,
                "level_evidence": data.get("level_evidence") or [],
                "evidence_cautions": data.get("evidence_cautions") or [],
            }
        )
        cumulative += duration

    # Build quest-centric lookup without collapsing same-name different IDs.
    by_quest: dict[str, dict[str, Any]] = {}
    for event in all_events:
        key = event.get("quest_key")
        if not key:
            continue
        row = by_quest.setdefault(
            key,
            {
                "quest_id": event.get("quest_id"),
                "quest_name": event.get("quest_name"),
                "episodes": [],
                "event_ids": [],
                "action_classes": [],
            },
        )
        if event["episode"] not in row["episodes"]:
            row["episodes"].append(event["episode"])
        row["event_ids"].append(event["event_id"])
        row["action_classes"].append(event["action_class"])

    # Questie name calibration diagnostics. This is audit-only; it never rewrites the video event.
    questie_name_mismatches: list[dict[str, Any]] = []
    questie_loaded = False
    if QUESTIE_ZIP.exists():
        try:
            from lib.questie_source import load_questie

            questie = load_questie(QUESTIE_ZIP)
            questie_loaded = True
            for key, row in by_quest.items():
                qid = row.get("quest_id")
                name = row.get("quest_name")
                if not isinstance(qid, int) or not isinstance(name, str):
                    continue
                qn = questie.quest_names.get(qid)
                canonical_name = qn.get(1) if isinstance(qn, dict) else qn
                if canonical_name and str(canonical_name) != name:
                    questie_name_mismatches.append(
                        {
                            "quest_id": qid,
                            "video_name": name,
                            "questie_name": canonical_name,
                            "episodes": row["episodes"],
                        }
                    )
        except Exception as exc:  # keep index build usable even if Questie loader changes
            questie_name_mismatches.append({"loader_error": repr(exc)})

    master = {
        "schema": "video-route-master-events-v1",
        "purpose": "route_reference_and_correction_only",
        "source_episode_range": [1, 53],
        "episode_count": len(boundaries),
        "event_count": len(all_events),
        "series_video_seconds": cumulative,
        "action_class_counts": dict(Counter(e["action_class"] for e in all_events)),
        "source_kind_counts": dict(Counter(e["source_kind"] for e in all_events)),
        "quest_index_count": len(by_quest),
        "questie_calibration_loaded": questie_loaded,
        "questie_name_mismatch_count": len(questie_name_mismatches),
        "questie_name_mismatches": questie_name_mismatches,
        "source_hashes": source_hashes,
        "quest_index": by_quest,
        "events": all_events,
    }
    MASTER_OUT.write_text(json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    BOUNDARY_OUT.write_text(
        json.dumps(
            {
                "schema": "video-route-episode-boundaries-v1",
                "episode_count": len(boundaries),
                "series_video_seconds": cumulative,
                "episodes": boundaries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    gaps = build_gap_audit(all_events, boundaries, by_quest)
    GAPS_OUT.write_text(json.dumps(gaps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_master_report(master, boundaries)
    write_gap_report(gaps)
    return {"master": master, "boundaries": boundaries, "gaps": gaps}


def build_gap_audit(
    events: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    by_quest: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quest_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("quest_key"):
            quest_events[event["quest_key"]].append(event)

    boundary_states: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for boundary in boundaries:
        for state in boundary.get("ending_states", []):
            key = quest_key(state.get("quest_id"), state.get("quest_name"))
            if not key:
                continue
            boundary_states[key].append(
                {
                    "episode": boundary["episode"],
                    "quest_id": state.get("quest_id"),
                    "quest_name": state.get("quest_name"),
                    "state": state.get("state"),
                    "source_section": state.get("source_section"),
                    "raw": state,
                }
            )

    carryover_resolutions: list[dict[str, Any]] = []
    unresolved_series_end: list[dict[str, Any]] = []
    completion_without_prior_accept_or_active: list[dict[str, Any]] = []
    duplicate_completion_candidates: list[dict[str, Any]] = []
    duplicate_accept_candidates: list[dict[str, Any]] = []

    for key in sorted(set(quest_events) | set(boundary_states)):
        evs = sorted(quest_events.get(key, []), key=lambda e: e["series_sequence"])
        states = sorted(boundary_states.get(key, []), key=lambda s: s["episode"])
        completes = [e for e in evs if e["action_class"] == "complete"]
        accepts = [e for e in evs if e["action_class"] == "accept"]

        # End-state -> later completion continuity.
        for state in states:
            later = [e for e in completes if e["episode"] > state["episode"]]
            if later:
                first = later[0]
                carryover_resolutions.append(
                    {
                        "quest_key": key,
                        "quest_id": state.get("quest_id"),
                        "quest_name": state.get("quest_name"),
                        "from_episode": state["episode"],
                        "to_episode": first["episode"],
                        "from_state": state["state"],
                        "resolution_event_id": first["event_id"],
                        "resolution_action": first["original_action"],
                        "classification": "resolved_unique_transition",
                        "resolution_basis": "later same-quest completion/chain-completion event exists",
                    }
                )
            elif state["episode"] == 53:
                unresolved_series_end.append(
                    {
                        "quest_key": key,
                        "quest_id": state.get("quest_id"),
                        "quest_name": state.get("quest_name"),
                        "episode": 53,
                        "state": state["state"],
                        "classification": "unresolved",
                        "reason": "active/unclosed at end of final episode",
                    }
                )

        # Completion that has no prior accept/state evidence in the extracted series.
        for complete in completes:
            prior_accept = any(a["series_sequence"] < complete["series_sequence"] for a in accepts)
            prior_state = any(s["episode"] < complete["episode"] for s in states)
            if not prior_accept and not prior_state:
                completion_without_prior_accept_or_active.append(
                    {
                        "quest_key": key,
                        "quest_id": complete.get("quest_id"),
                        "quest_name": complete.get("quest_name"),
                        "completion_event_id": complete["event_id"],
                        "episode": complete["episode"],
                        "classification": "action_exists_order_unknown",
                        "reason": "completion exists but no earlier accept/active evidence in normalized index",
                    }
                )

        if len(completes) > 1:
            duplicate_completion_candidates.append(
                {
                    "quest_key": key,
                    "quest_id": by_quest.get(key, {}).get("quest_id"),
                    "quest_name": by_quest.get(key, {}).get("quest_name"),
                    "event_ids": [e["event_id"] for e in completes],
                    "episodes": [e["episode"] for e in completes],
                    "classification": "action_exists_order_unknown",
                    "reason": "multiple completion-class events for same quest key; may be duplicate evidence, repeatable content, or distinct semantics requiring review",
                }
            )

        if len(accepts) > 1:
            duplicate_accept_candidates.append(
                {
                    "quest_key": key,
                    "quest_id": by_quest.get(key, {}).get("quest_id"),
                    "quest_name": by_quest.get(key, {}).get("quest_name"),
                    "event_ids": [e["event_id"] for e in accepts],
                    "episodes": [e["episode"] for e in accepts],
                    "classification": "action_exists_order_unknown",
                    "reason": "multiple accept-class events for same quest key; requires review before treating as duplicate",
                }
            )

    id_to_names: dict[int, set[str]] = defaultdict(set)
    name_to_ids: dict[str, set[int]] = defaultdict(set)
    for event in events:
        qid = event.get("quest_id")
        name = event.get("quest_name")
        if isinstance(qid, int) and isinstance(name, str) and name:
            id_to_names[qid].add(name)
            name_to_ids[name].add(qid)

    quest_id_name_conflicts = [
        {"quest_id": qid, "names": sorted(names), "classification": "action_exists_order_unknown"}
        for qid, names in sorted(id_to_names.items())
        if len(names) > 1
    ]
    same_name_multi_id = [
        {"quest_name": name, "quest_ids": sorted(ids)}
        for name, ids in sorted(name_to_ids.items())
        if len(ids) > 1
    ]

    return {
        "schema": "video-route-cross-episode-gaps-v1",
        "purpose": "support_route_order_and_omission_audit_not_complete_video_reconstruction",
        "counts": {
            "carryover_resolutions": len(carryover_resolutions),
            "unresolved_series_end": len(unresolved_series_end),
            "completion_without_prior_accept_or_active": len(completion_without_prior_accept_or_active),
            "duplicate_completion_candidates": len(duplicate_completion_candidates),
            "duplicate_accept_candidates": len(duplicate_accept_candidates),
            "quest_id_name_conflicts": len(quest_id_name_conflicts),
            "same_name_multi_id": len(same_name_multi_id),
        },
        "carryover_resolutions": carryover_resolutions,
        "unresolved_series_end": unresolved_series_end,
        "completion_without_prior_accept_or_active": completion_without_prior_accept_or_active,
        "duplicate_completion_candidates": duplicate_completion_candidates,
        "duplicate_accept_candidates": duplicate_accept_candidates,
        "quest_id_name_conflicts": quest_id_name_conflicts,
        "same_name_multi_id": same_name_multi_id,
        "manual_followup": [
            "Questie predecessor/successor validation is required before promoting any action_exists_order_unknown candidate to a resolved gap.",
            "Duplicate candidates are diagnostics only; repeatable quests, same-title multi-stage chains, and multiple evidence rows must not be auto-collapsed.",
            "Title-level comparisons are intentionally not auto-resolved because episode titles are metadata and may describe a range reached during the episode rather than the opening level.",
        ],
    }


def write_master_report(master: dict[str, Any], boundaries: list[dict[str, Any]]) -> None:
    synthetic = [b for b in boundaries if b["synthetic_early_schema"]]
    lines = [
        "# 视频路线参考索引 P1 审计",
        "",
        "用途：只为本项目自己的路线顺序/邻接对照和遗漏审计提供可查询输入；不是联盟最终路线，也不是五开时间模型。",
        "",
        "## 构建结果",
        "",
        f"- 单集输入：{master['episode_count']}/53。",
        f"- 标准化事件：{master['event_count']}。",
        f"- 不同任务键：{master['quest_index_count']}。",
        f"- 全系列视频画面时长：{master['series_video_seconds']}秒；只作累计定位，不当真实墙钟。",
        f"- 早期异构JSON兼容：{len(synthetic)}集（第1—3集采用synthetic-normalized查询层，不改原检查点）。",
        f"- Questie名称校准已加载：{master['questie_calibration_loaded']}；名称不一致候选：{master['questie_name_mismatch_count']}。",
        "",
        "## action类别",
        "",
    ]
    for key, value in sorted(master["action_class_counts"].items()):
        lines.append(f"- `{key}`：{value}")
    lines += [
        "",
        "## 证据边界",
        "",
        "- 原始`original_action`、raw事件和单集JSON路径全部保留，标准化只增加查询字段。",
        "- `objective_complete_not_turnin`与奖励窗口未证明状态不会进入complete类别。",
        "- 同名不同Quest ID以ID分开索引，不按中文名合并任务阶段。",
        "- 视频累计秒数不能替代真实玩家墙钟，也不能进入五开估时。",
        "",
        "输入哈希已保存在`data/video-route/master-events.json`，后续可复算。",
    ]
    MASTER_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_gap_report(gaps: dict[str, Any]) -> None:
    c = gaps["counts"]
    lines = [
        "# 视频跨集连续性 P2 初始审计",
        "",
        "用途：只暴露后续路线反审需要知道的证据缺口；不追求把视频补成无缝时间线。",
        "",
        "## 机械检查结果",
        "",
        f"- 集末活动状态在后续出现同任务完成：{c['carryover_resolutions']}条。",
        f"- 第53集结束仍未闭环：{c['unresolved_series_end']}条。",
        f"- 有完成但标准化索引中无更早接取/活动证据：{c['completion_without_prior_accept_or_active']}条。",
        f"- 同Quest键多次complete候选：{c['duplicate_completion_candidates']}条。",
        f"- 同Quest键多次accept候选：{c['duplicate_accept_candidates']}条。",
        f"- 同Quest ID出现多个中文名候选：{c['quest_id_name_conflicts']}条。",
        f"- 同中文名对应多个Quest ID：{c['same_name_multi_id']}组；这是正常多阶段链的重要提醒，不视为错误。",
        "",
        "## 当前解释边界",
        "",
        "- `carryover_resolutions`只说明后续存在同任务completion/chain-completion证据；具体缺失动作顺序仍以单集检查点为准。",
        "- `completion_without_prior_accept_or_active`不是路线错误，常见原因是视频剪辑、前一集未捕获接取或早期JSON只记录完成；后续需Questie/单集证据人工判定。",
        "- duplicate候选不自动合并：重复任务、同任务多条证据和action语义差异都可能造成多行。",
        "- 视频标题等级不参与自动补链。",
        "",
        "下一步：用P1索引按地图生成参考序列，然后只对本项目已有路线做“共同任务顺序/邻接 + 视频独有任务遗漏分类”反向审查。",
    ]
    GAPS_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = build()
    print(
        json.dumps(
            {
                "episode_count": result["master"]["episode_count"],
                "event_count": result["master"]["event_count"],
                "quest_index_count": result["master"]["quest_index_count"],
                "action_class_counts": result["master"]["action_class_counts"],
                "gap_counts": result["gaps"]["counts"],
                "outputs": [
                    str(MASTER_OUT.relative_to(ROOT)),
                    str(BOUNDARY_OUT.relative_to(ROOT)),
                    str(GAPS_OUT.relative_to(ROOT)),
                    str(MASTER_REPORT.relative_to(ROOT)),
                    str(GAPS_REPORT.relative_to(ROOT)),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
