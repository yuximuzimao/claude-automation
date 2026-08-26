from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
DEPENDENCY = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
OUT = ROOT / "data/route-atlas/icecrown-route-structured-candidate.json"
COVERAGE = ROOT / "data/route-atlas/icecrown-route-structured-coverage.json"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}

# Stable Icecrown anchors only. Cross-map portions intentionally stay on their Icecrown
# departure/return anchor so the Icecrown map does not draw fake lines to another continent.
ANCHORS: dict[str, tuple[float, float]] = {
    "银色比武场": (69.65, 22.86),
    "银色前线基地": (87.1, 75.8),
    "回音谷": (83.0, 73.0),
    "天灾城": (78.5, 64.5),
    "北伐军之峰": (79.8, 71.8),
    "奥格瑞姆之锤": (64.0, 50.0),  # moving hub: representative map marker only
    "暗影拱顶": (44.1, 24.7),
    "Savage Ledge": (37.0, 23.7),
    "Jotunheim": (28.0, 40.0),
    "约尔达村": (27.0, 39.0),
    "白骨女巫": (32.5, 43.0),
    "地下大厅": (33.1, 37.8),
    "乌弗朗之厅": (40.1, 23.9),
    "巫妖王之眼": (26.2, 62.3),
    "先祖大厅": (28.0, 47.0),
    "战痕尖塔": (28.7, 51.9),
    "巴拉加德堡垒": (18.0, 56.0),
    "瓦哈拉斯西南鱼叉平台": (32.0, 24.0),
    "瓦哈拉斯": (30.7, 29.0),
    "死亡高地": (19.5, 48.1),
    "先锋军港口": (8.0, 43.0),
    "赤色大教堂": (10.0, 46.0),
    "黑色观察站": (35.4, 66.3),
    "缝合场": (34.0, 68.0),
    "复生密室": (34.0, 68.0),
    "伊米海姆": (52.0, 58.0),
    "萨隆邪铁矿洞": (55.0, 59.0),
    "玛雷卡里斯": (58.0, 72.0),
    "破碎前线": (68.0, 68.0),
    "冰冠堡垒": (54.0, 86.0),
    "遗忘深渊": (54.0, 87.0),
    "莫德雷萨": (60.8, 63.4),
    "失落希望之谷": (68.0, 51.8),
    "第一军团": (64.5, 44.0),
    "辛达苟萨之墓": (71.0, 37.0),
    "白骨之庭": (49.2, 73.2),
    "黑暗大教堂": (44.5, 77.6),
    "沉默墓地": (79.8, 30.8),
    "荒凉之门": (50.4, 40.3),
    "奥尔杜萨": (51.0, 33.0),
    "哭泣采掘场": (39.0, 35.0),
    "恐惧之门": (44.0, 62.0),
    "科雷萨": (48.0, 68.5),
    "苦难高地": (53.9, 71.5),
}

# When a step starts with dialogue/transport text that has no coordinate, keep a deterministic
# player-facing map anchor instead of guessing from the previous step.
PRIMARY_STEP_ANCHOR: dict[int, tuple[float, float]] = {
    1: ANCHORS["银色比武场"],
    2: ANCHORS["暗影拱顶"],
    3: ANCHORS["暗影拱顶"],
    4: ANCHORS["Savage Ledge"],
    5: ANCHORS["白骨女巫"],
    6: ANCHORS["Jotunheim"],
    7: ANCHORS["Jotunheim"],
    8: ANCHORS["白骨女巫"],
    9: ANCHORS["瓦哈拉斯"],
    10: ANCHORS["死亡高地"],
    11: ANCHORS["先锋军港口"],
    12: ANCHORS["先锋军港口"],
    13: ANCHORS["黑色观察站"],
    14: ANCHORS["玛雷卡里斯"],
    15: ANCHORS["黑色观察站"],
    16: ANCHORS["奥格瑞姆之锤"],
}

EXPLICIT_COORD = re.compile(r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*[,，]\s*(\d{1,2}(?:\.\d+)?)")
TASK_NAME = re.compile(r"《([^》]+)》")
LOCATION_HINT = re.compile(r"(基地|林地|废墟|墓地|神殿|港口|大教堂|堡垒|营地|村|高地|前线|大厅|矿洞|之峰|之墓|之庭|之门|拱顶|观察站|海姆|雷卡里斯|杜萨|采掘场|约|附近|外围|顶部|底层|上层|下层|水域|城墙)")


def extract_coord(text: str) -> tuple[float, float] | None:
    match = EXPLICIT_COORD.search(text)
    if not match:
        return None
    x, y = float(match.group(1)), float(match.group(2))
    if 0 <= x <= 100 and 0 <= y <= 100:
        return x, y
    return None


def infer_anchor(text: str) -> tuple[float, float] | None:
    # Coordinates are trusted wherever explicitly written. Named locations, however, are only
    # trusted in the action's leading location/NPC segment. Later prose often says things like
    # 'do not return to X yet', which must not move the map point to X.
    explicit = extract_coord(text)
    if explicit:
        return explicit
    prefix = text.split("→", 1)[0].split("↳", 1)[0].strip()
    # System transport names its destination explicitly; anchor the point at that destination.
    if prefix.startswith(("使用炉石：", "炉石绑定：", "开飞行点：")):
        for name in sorted(ANCHORS, key=len, reverse=True):
            if name in prefix:
                return ANCHORS[name]
    # If an action has no explicit location segment and begins as an instruction, place names
    # mentioned later in that prose describe the objective/destination, not the current anchor.
    if "→" not in text and prefix.startswith(("做《", "先做《", "先由", "五号", "每", "使用", "继续", "同一片", "第一", "三项", "两项", "个人")):
        return None
    for name in sorted(ANCHORS, key=len, reverse=True):
        if name in prefix:
            return ANCHORS[name]
    return None


def movement_kind(text: str, step: int) -> str:
    if any(term in text for term in ("传送门", "任务脚本返回", "传送回")):
        return "script"
    if "炉石" in text:
        return "hearth"
    if step in {4, 28, 29, 30} and any(term in text for term in ("晶歌", "月光", "龙眠", "红玉", "沙塔斯", "达拉然")):
        return "crossmap"
    return "fly"


def action_location(text: str) -> str:
    head = text.split("→", 1)[0].strip()
    head = head.split("↳", 1)[0].strip()
    return head[:48] if head else "本段"


def decorate_task_tokens(text: str) -> str:
    safe = html.escape(text)
    safe = re.sub(r"(开飞行点：[^；<]+)", r'<span class="ra-system-action ra-flightpoint">\1</span>', safe)
    safe = re.sub(r"(炉石绑定：[^；<]+)", r'<span class="ra-system-action ra-hearthstone">\1</span>', safe)
    safe = re.sub(r"(使用炉石：[^；<]+)", r'<span class="ra-system-action ra-hearthstone">\1</span>', safe)

    def render_task_group(match: re.Match[str]) -> str:
        verb = match.group(1)
        names = re.findall(r"《([^》]+)》", match.group(2))
        cls = {"接": "ra-accept", "交": "ra-turnin", "做": "ra-do-task"}[verb]
        rendered = "、".join(f'<span class="ra-task {cls}">{name}</span>' for name in names)
        if verb == "做":
            return f'<span class="ra-branch">↳</span> <span class="ra-verb">做</span> {rendered}'
        return f'<span class="ra-verb">{verb}</span> {rendered}'

    # One verb governs the full adjacent task list: 接《A》《B》 / 交《A》、《B》 / 做《A》《B》.
    # Every task inherits the same semantic color and can therefore be audited from the final HUD.
    safe = re.sub(r"(接|交|做)((?:《[^》]+》[、，, ]*)+)", render_task_group, safe)
    # Task names used only as references/explanations still receive generic task styling.
    safe = re.sub(r"《([^》]+)》", r'<span class="ra-task">\1</span>', safe)
    return safe


def semantic_action_html(text: str) -> str:
    if "→" not in text:
        return f'<div class="ra-line">{decorate_task_tokens(text)}</div>'
    prefix, rest = text.split("→", 1)
    prefix = prefix.strip()
    rest = rest.strip()
    if prefix and "《" not in prefix and not prefix.startswith(("做《", "交《", "接《", "五号", "先", "每", "离开条件", "使用", "接受", "单号", "三项", "两项", "连续推进")):
        cls = "ra-location" if LOCATION_HINT.search(prefix) or infer_anchor(prefix) else "ra-npc"
        rendered_prefix = f'<span class="{cls}">{html.escape(prefix)}</span>'
        return f'<div class="ra-line">{rendered_prefix}<span class="ra-arrow">→</span>{decorate_task_tokens(rest)}</div>'
    return f'<div class="ra-line">{decorate_task_tokens(text)}</div>'


def note_html(step: dict) -> str:
    blocks: list[str] = []
    for card in (step.get("task_cards") or {}).values():
        name = str(card.get("name") or "任务")
        note = str(card.get("route_note") or "").strip()
        fivebox = str(card.get("fivebox") or "").strip()
        if not note and not fivebox:
            continue

        body = ""
        confirmed_prefix = ""
        confirmed_class = ""
        confirmed_detail = ""
        pending_detail = ""
        if fivebox.startswith("共享："):
            confirmed_prefix = "共享："
            confirmed_class = "ra-shared"
            confirmed_detail = fivebox[len("共享："):].strip()
        elif fivebox.startswith("不共享："):
            confirmed_prefix = "不共享："
            confirmed_class = "ra-not-shared"
            confirmed_detail = fivebox[len("不共享："):].strip()
        elif fivebox:
            pending_detail = re.sub(r"^(?:重点)?待实测[：:]\s*", "", fivebox).strip() or fivebox

        if confirmed_prefix:
            text = f'<span class="{confirmed_class}">{confirmed_prefix}</span>'
            if confirmed_detail:
                text += html.escape(confirmed_detail)
            if note:
                text += (" " if confirmed_detail else "") + html.escape(note)
            body += f'<div class="ra-note-text">{text}</div>'
        elif note:
            body += f'<div class="ra-note-text">{html.escape(note)}</div>'

        if pending_detail:
            body += (
                '<div class="ra-fivebox-line">'
                '<span class="ra-pending">五开待实测：</span>'
                f'{html.escape(pending_detail)}</div>'
            )
        blocks.append(f'<div class="ra-note-block"><div class="ra-note-task">《{html.escape(name)}》</div>{body}</div>')
    return ('<div class="ra-note-heading">备注</div>' + ''.join(blocks)) if blocks else ""


def main() -> None:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    dependency = json.loads(DEPENDENCY.read_text(encoding="utf-8"))
    first_step = {int(qid): int(step) for qid, step in (dependency.get("first_step_by_quest_id") or {}).items()}
    formal = {
        int(task["quest_id"])
        for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    }

    points: list[list] = []
    groups: list[dict] = []
    geometry_fallbacks: list[dict] = []
    previous = PRIMARY_STEP_ANCHOR[1]

    for step in draft.get("steps", []):
        step_no = int(step["step"])
        start = len(points)
        current = PRIMARY_STEP_ANCHOR.get(step_no, previous)
        step_actions = step.get("actions") or []
        outside_icecrown_map = False
        for action_idx, action in enumerate(step_actions, start=1):
            coord = infer_anchor(str(action))
            if coord is None:
                coord = current
                geometry_fallbacks.append({
                    "step": step_no,
                    "action": action_idx,
                    "text": str(action),
                    "fallback": [round(coord[0], 2), round(coord[1], 2)],
                })
            else:
                current = coord
            move = movement_kind(str(action), step_no)
            prefix = str(action).split("→", 1)[0].strip()
            if move == "crossmap":
                outside_icecrown_map = True
            elif outside_icecrown_map and any(name in prefix for name in ANCHORS):
                move = "crossmap"
                outside_icecrown_map = False
            if "返程传送门返回冰冠冰川" in str(action):
                coord = ANCHORS["银色前线基地"]
                current = coord
                move = "script"
                outside_icecrown_map = False
            title = action_location(str(action))
            points.append([
                round(coord[0], 2), round(coord[1], 2), title, str(action), f"ice{step_no:02d}", "", move, False, ""
            ])
        previous = current
        end = len(points) - 1
        if end < start:
            raise RuntimeError(f"Icecrown step {step_no} has no actions")
        timing = step.get("timing") or {}
        groups.append({
            "start": start,
            "end": end,
            "title": str(step["title"]),
            "summary": "",
            "actionHtml": "\n".join(semantic_action_html(str(action)) for action in step_actions),
            "noteHtml": note_html(step),
            "timing": {
                "centerMinutes": float(timing["centerMinutes"]),
                "rangeMinutes": [float(x) for x in timing["rangeMinutes"]],
                "includeInTotal": True,
                "status": str(timing.get("status") or "pre_live_marginal_budget"),
            },
            "questIds": sorted(qid for qid, first in first_step.items() if first == step_no and qid in formal),
        })

    covered = {qid for group in groups for qid in group["questIds"]}
    missing = sorted(formal - covered)
    unexpected = sorted(covered - formal)
    policy = draft.get("timing_policy") or {}
    route = {
        "order": 7,
        "uiStandard": "semantic-hud-v45",
        "status": "live_entry_confirmed_current_group_at_12897",
        "title": "冰冠冰川 · 80级五开可达路线",
        "sub": "银色比武场入图；主任务可达链已由《乐趣十足》实服确认。",
        "badge": (
            f"炉石：格罗玛什坠毁点 → 暗影拱顶\\n"
            f"预计总时间：{policy.get('route_total_center_minutes', 0)/60:.1f}小时"
            f"（{policy.get('route_total_pre_live_band_minutes', [0, 0])[0]/60:.1f}–"
            f"{policy.get('route_total_pre_live_band_minutes', [0, 0])[1]/60:.1f}小时）"
        ),
        "image": "maps/210-icecrown-hd.jpg",
        "legend": "",
        "footer": "",
        "labels": [[x, y, name] for name, (x, y) in ANCHORS.items() if name not in {"奥格瑞姆之锤"}],
        "points": points,
        "defaultIndex": groups[1]["start"] if len(groups) > 1 else 0,
        "phaseColors": {f"ice{i:02d}": "#94a3b8" for i in range(1, len(groups) + 1)},
        "displayName": "冰冠冰川",
        "stepGroups": groups,
        "defaultGroupIndex": 1 if len(groups) > 1 else 0,
        "hearthChain": ["格罗玛什坠毁点", "暗影拱顶"],
        "timing": {
            "centerMinutes": float(policy.get("route_total_center_minutes") or 0),
            "rangeMinutes": [float(x) for x in (policy.get("route_total_pre_live_band_minutes") or [])],
            "actualRuns": [],
            "model": "icecrown_16_step_reachable_live_entry_v3",
        },
        "geometryAudit": {
            "fallbackActionCount": len(geometry_fallbacks),
            "fallbackActions": geometry_fallbacks,
            "movingHubRepresentative": {"name": "奥格瑞姆之锤", "point": list(ANCHORS["奥格瑞姆之锤"])},
        },
    }
    OUT.write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COVERAGE.write_text(json.dumps({
        "status": "icecrown_structured_candidate_coverage",
        "formalTaskCount": len(formal),
        "coveredTaskCount": len(covered & formal),
        "missing": missing,
        "unexpected": unexpected,
        "pointCount": len(points),
        "stepGroupCount": len(groups),
        "geometryFallbackActionCount": len(geometry_fallbacks),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "formal": len(formal), "covered": len(covered & formal), "missing": len(missing),
        "points": len(points), "groups": len(groups), "geometry_fallbacks": len(geometry_fallbacks),
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    if missing or unexpected:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
