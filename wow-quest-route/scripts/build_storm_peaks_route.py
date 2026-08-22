from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/storm-peaks-task-foundation.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE_OUT = ROOT / "data/route-atlas/storm-peaks-route-coverage.json"
PLAYER_GROUPS_OUT = ROOT / "data/route-atlas/storm-peaks-player-step-groups.json"
AUDIT_OUT = ROOT / "docs/analysis/2026-08-22-storm-peaks-route-insertion-audit.md"

DATA = json.loads(FOUNDATION.read_text(encoding="utf-8"))
TASKS = {int(t["quest_id"]): t for t in DATA["tasks"]}
FORMAL = {int(qid) for qid in DATA["formal_task_ids"]}

points: list[list[Any]] = []
covered: set[int] = set()
step_groups: list[dict[str, Any]] = []
_current_html: list[str] = []
_current_note_blocks: list[tuple[int | None, str, str]] = []
opened_flight_points: set[str] = set()
flight_path_audit: list[dict[str, str]] = []


def name(qid: int) -> str:
    return str(TASKS[qid]["name"])


def n(qid: int) -> str:
    return f"《{name(qid)}》"


def seg(kind: str, value: Any = None, *qids: int) -> tuple[str, Any, tuple[int, ...]]:
    return kind, value, tuple(qids)


def LOC(text: str): return seg("loc", text)
def NPC(text: str): return seg("npc", text)
def TXT(text: str): return seg("txt", text)
def AR(): return seg("arrow")
def BR(): return seg("branch")
def TR(text: str): return seg("transport", text)
def FP(text: str): return seg("flightpoint", text)
def TAXI(origin: str, destination: str): return seg("taxi", (origin, destination))
def HB(text: str): return seg("hearthbind", text)
def HR(text: str): return seg("hearthreturn", text)
def KEY(text: str): return seg("key", text)
def DANGER(text: str): return seg("danger", text)
def TG(action: str, *qids: int): return seg("taskgroup", action, *qids)


def DO(*qids: int, tail: str = "") -> list[tuple[str, Any, tuple[int, ...]]]:
    row = [BR(), TG("do", *qids)]
    if tail:
        row.append(TXT(tail))
    return row


def render_plain(line: list[tuple[str, Any, tuple[int, ...]]]) -> str:
    out: list[str] = []
    for kind, value, qids in line:
        if kind in {"loc", "npc", "txt", "transport", "key", "danger"}:
            out.append(str(value))
        elif kind == "flightpoint":
            out.append(f"开飞行点：{value}（五号分别）")
        elif kind == "taxi":
            origin, destination = value
            out.append(f"系统飞行：{origin} → {destination}")
        elif kind == "hearthbind":
            out.append(f"炉石绑定：{value}")
        elif kind == "hearthreturn":
            out.append(f"使用炉石：{value}")
        elif kind == "arrow":
            out.append(" → ")
        elif kind == "branch":
            out.append("↳ ")
        elif kind == "taskgroup":
            verb = {"turn": "交", "accept": "接", "do": "做"}[str(value)]
            out.append("；".join(f"{verb}{n(qid)}" for qid in qids))
    return "".join(out)


def render_html(
    line: list[tuple[str, Any, tuple[int, ...]]],
    *,
    inline_location: str | None = None,
) -> str:
    parts: list[str] = []
    has_branch = False
    if inline_location:
        parts.append(f'<span class="ra-location">{html.escape(inline_location)}</span>')
        parts.append('<span class="ra-inline-sep"> </span>')
    for kind, value, qids in line:
        if kind == "loc":
            parts.append(f'<span class="ra-location">{html.escape(str(value))}</span>')
        elif kind == "npc":
            parts.append(f'<span class="ra-npc">{html.escape(str(value))}</span>')
        elif kind == "txt":
            parts.append(html.escape(str(value)))
        elif kind == "transport":
            parts.append(f'<span class="ra-transport">{html.escape(str(value))}</span>')
        elif kind == "flightpoint":
            parts.append(f'<span class="ra-system-action ra-flightpoint">开飞行点：{html.escape(str(value))}（五号分别）</span>')
        elif kind == "taxi":
            origin, destination = value
            parts.append(f'<span class="ra-system-action ra-flightpath">系统飞行：{html.escape(str(origin))} → {html.escape(str(destination))}</span>')
        elif kind == "hearthbind":
            parts.append(f'<span class="ra-system-action ra-hearthstone">炉石绑定：{html.escape(str(value))}</span>')
        elif kind == "hearthreturn":
            parts.append(f'<span class="ra-system-action ra-hearthstone">使用炉石：{html.escape(str(value))}</span>')
        elif kind == "key":
            parts.append(f'<span class="ra-key">{html.escape(str(value))}</span>')
        elif kind == "danger":
            parts.append(f'<span class="ra-danger">{html.escape(str(value))}</span>')
        elif kind == "arrow":
            parts.append('<span class="ra-arrow">→</span>')
        elif kind == "branch":
            has_branch = True
            parts.append('<span class="ra-branch">↳</span>')
        elif kind == "taskgroup":
            action = str(value)
            verb = {"turn": "交", "accept": "接", "do": "做"}[action]
            cls = {"turn": "ra-turnin", "accept": "ra-accept", "do": "ra-do-task"}[action]
            parts.append(f'<span class="ra-verb">{verb}</span> ')
            parts.append("、".join(
                f'<span class="ra-task {cls}">{html.escape(name(qid))}</span>' for qid in qids
            ))
    if has_branch and inline_location:
        line_cls = "ra-line ra-do-inline"
    elif has_branch:
        line_cls = "ra-line ra-do"
    else:
        line_cls = "ra-line"
    return f'<div class="{line_cls}">' + "".join(parts) + "</div>"


def task_qids(lines: list[list[tuple[str, Any, tuple[int, ...]]]]) -> list[int]:
    result: list[int] = []
    for line in lines:
        for kind, value, qids in line:
            if kind != "taskgroup":
                continue
            for qid in qids:
                if qid not in result:
                    result.append(qid)
    return result


def executed_qids(lines: list[list[tuple[str, Any, tuple[int, ...]]]]) -> list[int]:
    result: list[int] = []
    for line in lines:
        for kind, value, qids in line:
            if kind != "taskgroup" or value != "do":
                continue
            for qid in qids:
                if qid not in result:
                    result.append(qid)
    return result


def note_text(qid: int) -> str:
    return str(TASKS[qid].get("route_mechanism_note") or "").strip()


def fivebox_text(qid: int) -> str:
    return str(TASKS[qid].get("fivebox_check") or "").strip()


def render_note_text(text: str) -> str:
    safe = html.escape(text)
    for prefix, cls in (("共享：", "ra-shared"), ("不共享：", "ra-not-shared")):
        if safe.startswith(prefix):
            safe = f'<span class="{cls}">{prefix}</span>' + safe[len(prefix):]
            break
    for term in (
        "最上层", "顶层", "一层", "地下", "不要使用加速技能", "不要提前离开",
        "不要下坐骑直接硬打", "不要只在洞里普通刷怪", "不要离开对话/事件范围",
    ):
        safe = safe.replace(term, f'<span class="ra-danger">{term}</span>')
    return safe


def P(
    x: float,
    y: float,
    title: str,
    phase: str,
    lines: list[list[tuple[str, Any, tuple[int, ...]]]],
    *,
    movement: str = "fly",
    optional: bool = False,
    extra_notes: list[tuple[int | None, str]] | None = None,
    cover: tuple[int, ...] = (),
    show_anchor: bool = True,
) -> None:
    global _current_html, _current_note_blocks
    for line in lines:
        for kind, value, _ in line:
            if kind == "flightpoint":
                opened_flight_points.add(str(value))
            elif kind == "taxi":
                origin, destination = value
                missing = [p for p in (str(origin), str(destination)) if p not in opened_flight_points]
                if missing:
                    raise RuntimeError(
                        f"system flight uses unopened flight point(s) at {title}: "
                        f"{origin} -> {destination}; unopened={missing}; opened={sorted(opened_flight_points)}"
                    )
                flight_path_audit.append({"from": str(origin), "to": str(destination), "status": "both_opened_before_departure"})
    qids = task_qids(lines)
    covered.update(qids)
    covered.update(cover)
    action = "\n".join(render_plain(line) for line in lines)
    first_is_do = bool(lines and lines[0] and lines[0][0][0] == "branch")
    if not show_anchor:
        _current_html.extend(render_html(line) for line in lines)
    elif first_is_do:
        _current_html.append(render_html(lines[0], inline_location=title))
        _current_html.extend(render_html(line) for line in lines[1:])
    else:
        _current_html.append(
            f'<div class="ra-line ra-point-anchor"><span class="ra-location">{html.escape(title)}</span></div>'
        )
        _current_html.extend(render_html(line) for line in lines)

    point_notes: list[str] = []
    seen_note_qids: set[int] = set()
    for qid in executed_qids(lines):
        note = note_text(qid)
        if note and qid not in seen_note_qids:
            seen_note_qids.add(qid)
            point_notes.append(f"{n(qid)}：{note}")
            _current_note_blocks.append((qid, "note", note))
        fb = fivebox_text(qid)
        if fb:
            point_notes.append(f"五开待实测·{n(qid)}：{fb}")
            _current_note_blocks.append((qid, "fivebox", fb))
    for qid, text in extra_notes or []:
        label = n(qid) if qid is not None else "本段"
        point_notes.append(f"{label}：{text}")
        _current_note_blocks.append((qid, "note", text))

    fivebox_only = "\n".join(x for x in point_notes if x.startswith("五开待实测"))
    regular_notes = "\n".join(x for x in point_notes if not x.startswith("五开待实测"))
    points.append([x, y, title, action, phase, regular_notes, movement, optional, fivebox_only])


def render_group_notes() -> str:
    order: list[tuple[str, int | None]] = []
    grouped: dict[tuple[str, int | None], dict[str, list[str]]] = {}
    for qid, kind, text in _current_note_blocks:
        key = ("task", qid) if qid is not None else ("segment", None)
        if key not in grouped:
            grouped[key] = {"note": [], "fivebox": []}
            order.append(key)
        bucket = grouped[key][kind]
        if text not in bucket:
            bucket.append(text)

    blocks: list[str] = []
    for _, qid in order:
        key = ("task", qid) if qid is not None else ("segment", None)
        payload = grouped[key]
        title = n(qid) if qid is not None else "本段"
        body = "".join(
            f'<div class="ra-note-text">{render_note_text(text)}</div>'
            for text in payload["note"]
        )
        fivebox = "".join(
            '<div class="ra-fivebox-line">'
            '<span class="ra-pending">五开待实测：</span>'
            f'{html.escape(text)}'
            '</div>'
            for text in payload["fivebox"]
        )
        blocks.append(
            '<div class="ra-note-block">'
            f'<div class="ra-note-task">{html.escape(title)}</div>'
            f'{body}{fivebox}'
            '</div>'
        )
    if not blocks:
        return ""
    return '<div class="ra-note-heading">备注</div>' + "".join(blocks)


def G(title: str, summary: str, fn, *, timing_center: float = 10.0, timing_range=(6.0, 16.0)) -> None:
    global _current_html, _current_note_blocks
    start = len(points)
    _current_html = []
    _current_note_blocks = []
    fn()
    end = len(points) - 1
    if end < start:
        raise RuntimeError(f"empty group: {title}")
    step_groups.append({
        "start": start,
        "end": end,
        "title": title,
        "summary": summary,
        "actionHtml": "\n".join(_current_html),
        "noteHtml": render_group_notes(),
        "timing": {
            "centerMinutes": float(timing_center),
            "rangeMinutes": [float(timing_range[0]), float(timing_range[1])],
            "includeInTotal": True,
        },
    })


# 1. K3 arrival: transport capability first, then first-arrival NPC scan.
def g1_k3_entry() -> None:
    P(41.0, 86.4, "K3", "k3", [
        [NPC("基尔·斯巴索克"), AR(), TG("turn", 12853)],
        [NPC("“诚实的”麦克斯"), AR(), TXT("五号分别领取借用双足飞龙")],
        [FP("K3")],
    ], movement="crossmap")
    P(41.0, 85.6, "K3", "k3", [
        [NPC("基尔·斯巴索克"), AR(), TG("accept", 12818)],
        [NPC("莉吉特"), AR(), TG("accept", 12827, 12836)],
        [NPC("格莱奇·菲兹巴克"), AR(), TG("accept", 12843, 12844)],
    ], movement="ride", show_anchor=False)


# 2. Compact K3 west loop and first return.
def g2_k3_west() -> None:
    P(39.0, 86.7, "K3西侧", "k3_west", [DO(12818)])
    P(41.0, 86.4, "K3", "k3", [
        [NPC("基尔·斯巴索克"), AR(), TG("turn", 12818), AR(), TG("accept", 12819)],
    ], movement="fly")
    P(35.1, 87.8, "K3西侧雷区", "k3_west", [DO(12819)])
    P(30.3, 85.7, "野蛮岭", "k3_west", [DO(12836, 12827)])
    P(41.0, 85.7, "K3", "k3", [
        [NPC("基尔·斯巴索克"), AR(), TG("turn", 12819), AR(), TG("accept", 12826)],
        [NPC("莉吉特"), AR(), TG("turn", 12826), AR(), TG("accept", 12820)],
        [NPC("莉吉特"), AR(), TG("turn", 12827, 12836), AR(), TG("accept", 12828)],
    ], movement="fly")


# 3. Garm, UDED, Crystalweb Cave and Sifreldar on one northbound pass.
def g3_garm_cave_sifreldar() -> None:
    P(44.9, 81.3, "加姆雷区", "garm", [DO(12820)])
    P(41.7, 80.0, "水晶蛛网洞穴外", "crystalweb", [
        [NPC("托莉·兰波维奇"), AR(), TG("accept", 12829, 12830)],
    ], movement="fly")
    P(39.6, 81.9, "K3北侧", "garm", [DO(12828)])
    P(43.0, 74.8, "水晶蛛网洞穴内", "crystalweb", [
        DO(12829, 12830),
        [NPC("受伤的地精矿工"), AR(), TG("accept", 12831)],
    ], movement="fly")
    P(47.1, 71.2, "水晶蛛网洞穴深处", "crystalweb", [DO(12831)], movement="ride")
    P(43.5, 75.2, "水晶蛛网洞穴内", "crystalweb", [
        [NPC("受伤的地精矿工"), AR(), TG("turn", 12831), AR(), TG("accept", 12832)],
        DO(12832),
    ], movement="ride")
    P(41.7, 80.0, "水晶蛛网洞穴外", "crystalweb", [
        [NPC("托莉·兰波维奇"), AR(), TG("turn", 12829, 12830)],
    ], movement="fly")
    P(41.2, 72.2, "希弗列尔达村", "sifreldar", [DO(12843, 12844)], movement="fly")
    P(41.0, 85.7, "K3", "k3", [
        [NPC("莉吉特"), AR(), TG("turn", 12820, 12828, 12832), AR(), TG("accept", 12821)],
        [NPC("格莱奇·菲兹巴克"), AR(), TG("turn", 12843, 12844), AR(), TG("accept", 12846)],
    ], movement="fly")


# 4. Garm backdoor chain, then unlock the one-way deep transport.
def g4_garm_backdoor() -> None:
    P(48.2, 82.1, "加姆高地", "garm", [DO(12821)], movement="fly")
    P(40.9, 85.3, "K3", "k3", [
        [NPC("莉吉特"), AR(), TG("turn", 12821), AR(), TG("accept", 12822)],
        [TXT("使用莉吉特旁的传送台回到"), LOC("加姆高地")],
    ], movement="script")
    P(50.3, 81.8, "加姆高地", "garm", [
        [NPC("吉诺"), AR(), TG("accept", 12823)],
        DO(12822, 12823),
        [NPC("吉诺"), AR(), TG("turn", 12823), AR(), TG("accept", 12824)],
        [TXT("使用加姆传送器返回"), LOC("K3")],
    ], movement="script")
    P(40.9, 85.3, "K3", "k3", [
        [NPC("莉吉特"), AR(), TG("turn", 12822, 12824)],
    ], movement="script")


# 6. Forlorn Mine disguise chain.
def g6_forlorn_mine() -> None:
    P(42.8, 68.9, "荒弃矿洞", "forlorn", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12846), AR(), TG("accept", 12841)],
    ], movement="fly")
    P(45.2, 71.0, "荒弃矿洞内", "forlorn", [
        [NPC("监督者希尔拉"), BR(), TG("do", 12841)],
    ], movement="ride", show_anchor=False)
    P(42.8, 68.9, "荒弃矿洞内", "forlorn", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12841), AR(), TG("accept", 12905)],
    ], movement="ride", show_anchor=False)
    P(44.4, 68.9, "荒弃矿洞内", "forlorn", [
        [NPC("残酷的米尔德蕾"), AR(), TG("turn", 12905), AR(), TG("accept", 12906)],
    ], movement="ride", show_anchor=False)
    P(44.3, 68.2, "荒弃矿洞内", "forlorn", [
        [NPC("筋疲力尽的维库人"), BR(), TG("do", 12906)],
    ], movement="ride", show_anchor=False)
    P(44.4, 68.9, "荒弃矿洞内", "forlorn", [
        [NPC("残酷的米尔德蕾"), AR(), TG("turn", 12906), AR(), TG("accept", 12907)],
    ], movement="ride", show_anchor=False)
    P(45.4, 69.1, "荒弃矿洞内", "forlorn", [
        [NPC("加哈尔"), BR(), TG("do", 12907)],
    ], movement="ride", show_anchor=False)
    P(44.4, 68.9, "荒弃矿洞内", "forlorn", [
        [NPC("残酷的米尔德蕾"), AR(), TG("turn", 12907), AR(), TG("accept", 12908)],
    ], movement="ride", show_anchor=False)
    P(42.8, 68.9, "荒弃矿洞内", "forlorn", [
        [NPC("特殊囚犯"), BR(), TG("do", 12908)],
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12908), AR(), TG("accept", 12921)],
    ], movement="ride", show_anchor=False)


# 7. Brunnhildar village and Valkyrion in one side loop.
def g7_brunnhildar_valkyrion() -> None:
    P(47.5, 69.1, "布伦希尔达村", "brunnhildar", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12921), AR(), TG("accept", 12969)],
    ], movement="fly")
    P(48.3, 69.8, "布伦希尔达村", "brunnhildar", [
        [NPC("安格妮塔"), BR(), TG("do", 12969)],
    ], movement="ride", show_anchor=False)
    P(47.5, 69.1, "布伦希尔达村", "brunnhildar", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12969), AR(), TG("accept", 12970)],
        DO(12970),
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12970), AR(), TG("accept", 12971)],
    ], movement="ride", show_anchor=False)
    P(50.5, 66.9, "布伦希尔达村南侧", "brunnhildar", [
        [NPC("获胜的挑战者"), BR(), TG("do", 12971)],
    ], movement="ride")
    P(47.5, 69.1, "布伦希尔达村", "brunnhildar", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 12971), AR(), TG("accept", 12972)],
    ], movement="ride")
    P(48.4, 72.1, "布伦希尔达村", "brunnhildar", [
        [NPC("塞拉·克文沙尔"), AR(), TG("accept", 12925)],
        [NPC("复仇者伊芬"), AR(), TG("accept", 12942, 12968)],
    ], movement="ride", show_anchor=False)
    P(24.0, 61.9, "瓦基里安最大建筑室内", "valkyrion", [
        [NPC("伊尔达"), BR(), TG("do", 12968)],
        [LOC("伊尔达旁大箱子"), AR(), TG("accept", 12953)],
    ], movement="fly")
    P(24.8, 61.2, "瓦基里安室外", "valkyrion", [DO(12925, 12942)], movement="ride")
    P(26.6, 59.9, "瓦基里安室外", "valkyrion", [
        [LOC("东侧鱼叉炮"), BR(), TG("do", 12953)],
    ], movement="ride", show_anchor=False)
    P(48.4, 72.1, "布伦希尔达村", "brunnhildar", [
        [NPC("塞拉·克文沙尔"), AR(), TG("turn", 12925)],
        [NPC("复仇者伊芬"), AR(), TG("turn", 12942, 12953, 12968)],
    ], movement="fly")


# 8. Brianna bear combat and Cold Hearted.
def g8_brianna() -> None:
    P(53.1, 65.7, "布伦希尔达东侧", "brunnhildar", [
        [NPC("布莉亚娜"), AR(), TG("turn", 12972), AR(), TG("accept", 12851)],
    ], movement="fly")
    P(60.0, 61.2, "上古寒冬山谷", "brunnhildar", [DO(12851)], movement="ride")
    P(53.1, 65.7, "布伦希尔达东侧", "brunnhildar", [
        [NPC("布莉亚娜"), AR(), TG("turn", 12851), AR(), TG("accept", 12856)],
    ], movement="ride")
    P(64.6, 60.5, "丹尼芬雷上空", "dun_niffelem", [DO(12856)], movement="fly")
    P(53.1, 65.7, "布伦希尔达东侧", "brunnhildar", [
        [NPC("布莉亚娜"), AR(), TG("turn", 12856), AR(), TG("accept", 13063)],
    ], movement="fly")


# 9. Astrid, Hibernal Cavern and the bear pit.
def g9_astrid_pit() -> None:
    P(49.8, 71.8, "布伦希尔达村", "brunnhildar", [
        [NPC("艾丝崔·约利塔尔"), AR(), TG("turn", 13063), AR(), TG("accept", 12900)],
    ], movement="fly")
    P(45.8, 74.2, "布伦希尔达西侧", "brunnhildar", [DO(12900)], movement="ride")
    P(49.8, 71.8, "布伦希尔达村", "brunnhildar", [
        [NPC("艾丝崔·约利塔尔"), AR(), TG("turn", 12900), AR(), TG("accept", 12983, 12989)],
    ], movement="ride")
    P(55.9, 63.9, "冬眠洞穴入口", "hibernal", [], movement="fly")
    P(55.2, 61.9, "冬眠洞穴内", "hibernal", [DO(12983, 12989)], movement="ride")
    P(49.8, 71.8, "布伦希尔达村", "brunnhildar", [
        [NPC("艾丝崔·约利塔尔"), AR(), TG("turn", 12983, 12989), AR(), TG("accept", 12996)],
    ], movement="fly")
    P(50.7, 67.3, "布伦希尔达南侧", "brunnhildar", [
        [NPC("基加拉格"), BR(), TG("do", 12996)],
    ], movement="ride")
    P(49.8, 71.8, "布伦希尔达村", "brunnhildar", [
        [NPC("艾丝崔·约利塔尔"), AR(), TG("turn", 12996), AR(), TG("accept", 12997)],
    ], movement="ride")
    P(49.2, 68.6, "利齿之坑", "brunnhildar", [DO(12997)], movement="ride")
    P(49.8, 71.8, "布伦希尔达村", "brunnhildar", [
        [NPC("艾丝崔·约利塔尔"), AR(), TG("turn", 12997), AR(), TG("accept", 13061)],
    ], movement="ride")
    P(47.5, 69.1, "布伦希尔达村", "brunnhildar", [
        [NPC("女巫洛莉拉"), AR(), TG("turn", 13061), AR(), TG("accept", 13062)],
        [NPC("仲裁者格蕾塔"), AR(), TG("turn", 13062), AR(), TG("accept", 12886)],
    ], movement="ride", show_anchor=False)


# 10. Drakkensryd into Thorim, then use the first natural near-pass to seed Grom'arsh.
def g10_drakkensryd_thorim() -> None:
    P(33.4, 57.9, "驭龙赛 → 风暴神殿", "thorim", [
        DO(12886),
        [NPC("托里姆"), AR(), TG("turn", 12886), AR(), TG("accept", 13064)],
        DO(13064),
        [NPC("托里姆"), AR(), TG("turn", 13064), AR(), TG("accept", 12915)],
    ], movement="script")
    P(37.3, 49.6, "格罗玛什坠毁点", "gromarsh", [
        [NPC("奥鲁特·埃雷古"), AR(), TG("accept", 12882)],
        [NPC("伯克塔·血怒"), AR(), TG("accept", 12895)],
        [NPC("血卫士洛尔加"), AR(), TG("accept", 13000, 13054)],
        [FP("格罗玛什坠毁点")],
        [HB("格罗玛什坠毁点")],
    ], movement="fly", extra_notes=[(12882, "雷铸敌人沿后续路线自然累计；发明家图书馆补齐10件。")])
    P(46.7, 55.2, "基莫拉克之巢入口", "brann", [], movement="fly")
    P(48.5, 54.3, "基莫拉克之巢内", "brann", [
        DO(13000),
        [NPC("猎户瓦尔兹"), BR(), TG("do", 13054)],
        [NPC("猎户瓦尔兹"), AR(), TG("turn", 13054), AR(), TG("accept", 13055)],
    ], movement="ride")
    P(48.6, 50.0, "基莫拉克之巢深处", "brann", [DO(13055)], movement="ride")
    P(48.5, 54.3, "基莫拉克之巢内", "brann", [
        [NPC("猎户瓦尔兹"), AR(), TG("turn", 13055), AR(), TG("accept", 13056)],
    ], movement="ride", show_anchor=False)
    P(49.0, 46.6, "基莫拉克之巢更深处", "brann", [DO(13056)], movement="ride")
    P(48.5, 54.3, "基莫拉克之巢内", "brann", [
        [NPC("猎户瓦尔兹"), AR(), TG("turn", 13056)],
    ], movement="ride", show_anchor=False)


# 11. Mending Fences + item-triggered Refiner's Fire.
def g11_mending_fences() -> None:
    P(73.0, 62.8, "弗约恩之砧", "hodir", [
        DO(12915),
        [TXT("拾取熔渣覆盖的金属"), AR(), TG("accept", 12922)],
        DO(12922),
        [LOC("弗约恩之砧铁砧"), AR(), TG("turn", 12922), AR(), TG("accept", 12956)],
    ], movement="fly")
    P(33.4, 57.9, "风暴神殿", "thorim", [
        [NPC("托里姆"), AR(), TG("turn", 12915, 12956), AR(), TG("accept", 12924)],
    ], movement="fly")


REPUTATION_ASSUMED_AVAILABLE = [12985, 13001, 13011, 13420]


# 12. Dun Niffelem: first close Reforging an Alliance, then lock the local one-time tasks into one fixed loop.
def g12_dun_first() -> None:
    P(63.2, 63.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("亚米尔德"), AR(), TG("turn", 12924), AR(), TG("accept", 13009, 12985)],
    ], movement="fly")
    P(65.4, 60.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("约库姆国王"), AR(), TG("accept", 12966, 12975, 13011)],
        [NPC("博学者兰德维尔"), AR(), TG("accept", 13001)],
        [FP("丹尼芬雷")],
    ], movement="ride", show_anchor=False)
    P(69.4, 59.6, "霜原湖", "dun_niffelem", [DO(12985)], movement="fly")
    P(63.2, 63.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("亚米尔德"), AR(), TG("turn", 12985), AR(), TG("accept", 12987)],
    ], movement="fly")
    P(64.2, 59.2, "丹尼芬雷北侧冰柱", "dun_niffelem", [DO(12987)], movement="fly")
    P(63.2, 63.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("亚米尔德"), AR(), TG("turn", 12987)],
    ], movement="fly")
    P(54.9, 61.0, "冬眠洞穴 / 上古寒冬山谷", "dun_niffelem", [DO(13001, 13011)], movement="fly")
    P(65.0, 59.1, "丹尼芬雷", "dun_niffelem", [
        [NPC("博学者兰德维尔"), AR(), TG("turn", 13001)],
        [NPC("约库姆国王"), AR(), TG("turn", 13011)],
    ], movement="fly")
    P(75.4, 63.6, "弗约恩之砧", "hodir", [
        [NPC("亚米尔德"), AR(), TG("turn", 12966), AR(), TG("accept", 12967)],
        DO(12967),
        [NPC("亚米尔德"), AR(), TG("turn", 12967)],
    ], movement="fly")
    P(72.0, 49.5, "雷暴台地", "dun_niffelem", [DO(12975)], movement="fly")
    P(65.4, 60.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("约库姆国王"), AR(), TG("turn", 12975), AR(), TG("accept", 12976)],
        [NPC("亚米尔德"), AR(), TG("turn", 12976)],
        [LOC("丹尼芬雷外围永冻碎片"), AR(), TG("accept", 13420)],
        [NPC("卡尔德"), AR(), TG("turn", 13420)],
    ], movement="fly")


# 13. Veranus chain.
def g13_veranus() -> None:
    P(33.4, 57.9, "风暴神殿", "thorim", [
        [NPC("托里姆"), AR(), TG("turn", 13009), AR(), TG("accept", 13050)],
    ], movement="fly")
    P(45.2, 67.2, "布伦希尔达附近峭壁龙巢", "thorim", [DO(13050)], movement="fly")
    P(33.4, 57.9, "风暴神殿", "thorim", [
        [NPC("托里姆"), AR(), TG("turn", 13050), AR(), TG("accept", 13051)],
    ], movement="fly")
    P(36.1, 64.1, "风暴神殿南侧", "brann", [DO(12895)], movement="fly")
    P(38.8, 65.5, "风暴神殿东南", "thorim", [DO(13051)], movement="fly")
    P(33.4, 57.9, "风暴神殿", "thorim", [
        [NPC("托里姆"), AR(), TG("turn", 13051), AR(), TG("accept", 13010)],
    ], movement="fly")
    P(65.4, 60.2, "丹尼芬雷", "dun_niffelem", [DO(13010)], movement="fly", extra_notes=[(13010, "按约库姆对话/脚本完成科洛米尔事件。")])
    P(71.0, 49.0, "雷暴台地", "thorim", [
        [NPC("托里姆"), AR(), TG("turn", 13010), AR(), TG("accept", 13057)],
    ], movement="script")


# 14. Terrace of the Makers finale, Ulduar flight point, then hearth to the seeded western hub.
def g15_thorim_finale() -> None:
    P(56.0, 43.5, "造物者圣台", "terrace", [
        [NPC("托里姆"), AR(), TG("turn", 13057), AR(), TG("accept", 13005, 13035)],
    ], movement="fly")
    P(55.3, 43.3, "塑造者之厅", "terrace", [
        [NPC("伊森法斯"), BR(), TG("do", 13035)],
    ], movement="ride")
    P(51.5, 44.7, "造物者圣台", "terrace", [DO(13005)], movement="ride")
    P(48.7, 45.7, "造物者圣台", "terrace", [
        [NPC("风之哈勒弗尼尔"), BR(), TG("do", 13035)],
    ], movement="ride", show_anchor=False)
    P(44.9, 38.0, "造物者圣台北侧", "terrace", [
        [NPC("符文巨人杜洛恩"), BR(), TG("do", 13035)],
    ], movement="ride")
    P(56.0, 43.5, "造物者圣台", "terrace", [
        [NPC("托里姆"), AR(), TG("turn", 13005, 13035), AR(), TG("accept", 13047)],
    ], movement="fly")
    P(35.9, 31.6, "智慧神殿附近桥上", "thorim", [DO(13047)], movement="fly")
    P(45.0, 28.0, "奥杜尔", "ulduar", [
        [FP("奥杜尔")],
        [TAXI("奥杜尔", "丹尼芬雷")],
    ], movement="fly")
    P(65.4, 60.2, "丹尼芬雷", "dun_niffelem", [
        [NPC("约库姆国王"), AR(), TG("turn", 13047)],
    ], movement="taxi")


# After the Thorim/Ulduar main chain, hearth back to the Grom'arsh point seeded on the first Thorim pass.
def g16_gromarsh_brann_start() -> None:
    P(37.3, 49.6, "格罗玛什坠毁点", "gromarsh", [
        [HR("格罗玛什坠毁点")],
        [NPC("伯克塔·血怒"), AR(), TG("turn", 12895), AR(), TG("accept", 12909)],
        [NPC("血卫士洛尔加"), AR(), TG("turn", 13000)],
    ], movement="hearth")
    P(40.8, 51.2, "格罗玛什东侧", "brann", [
        [NPC("凯尔莉丝"), AR(), TG("turn", 12909), AR(), TG("accept", 12910)],
    ], movement="ride")
    P(48.6, 60.8, "追踪终点", "brann", [
        [NPC("追踪者图林"), BR(), TG("do", 12910)],
        [LOC("布莱恩通讯器"), AR(), TG("turn", 12910), AR(), TG("accept", 12913)],
    ], movement="ride")
    P(37.3, 49.7, "格罗玛什坠毁点", "gromarsh", [
        [NPC("莫塔哈·风魂"), AR(), TG("turn", 12913), AR(), TG("accept", 12917)],
    ], movement="fly")


# 17. Brann library chain.
def g17_brann_library() -> None:
    P(27.9, 43.6, "西部峡谷", "brann", [DO(12917)], movement="fly")
    P(37.3, 49.7, "格罗玛什坠毁点", "gromarsh", [
        [NPC("莫塔哈·风魂"), AR(), TG("turn", 12917)],
        [NPC("伯克塔·血怒"), AR(), TG("accept", 12920)],
        DO(12920),
        [NPC("伯克塔·血怒"), AR(), TG("turn", 12920), AR(), TG("accept", 12926)],
    ], movement="fly")
    P(39.5, 41.2, "发明家图书馆", "library", [
        DO(12926, 12882),
        [LOC("布莱恩通讯器"), AR(), TG("turn", 12926), AR(), TG("accept", 12927)],
        DO(12927),
        [LOC("布莱恩通讯器"), AR(), TG("turn", 12927), AR(), TG("accept", 13416)],
    ], movement="fly")
    P(37.5, 46.8, "发明家图书馆内层", "library", [
        [LOC("控制台"), AR(), TG("turn", 13416), AR(), TG("accept", 12928)],
        DO(12928),
        [LOC("布莱恩通讯器"), AR(), TG("turn", 12928), AR(), TG("accept", 12929, 13273)],
    ], movement="ride")


# 18. Norgannon Core side chain, return to Grom'arsh and close Ancient Relics.
def g18_brann_core_gromarsh() -> None:
    P(59.5, 52.1, "布莱恩营地上层", "brann", [
        DO(13273),
        [LOC("布莱恩通讯器"), AR(), TG("turn", 13273), AR(), TG("accept", 13274)],
    ], movement="fly")
    P(56.4, 52.1, "洛肯的宝库", "brann", [
        DO(13274),
        [LOC("布莱恩通讯器"), AR(), TG("turn", 13274), AR(), TG("accept", 13285)],
    ], movement="fly")
    P(45.5, 49.0, "创世神殿顶部", "brann", [
        [NPC("布莱恩"), BR(), TG("do", 13285)],
    ], movement="fly")
    P(37.3, 49.7, "格罗玛什坠毁点", "gromarsh", [
        [NPC("伯克塔·血怒"), AR(), TG("turn", 13285), AR(), TG("accept", 13426)],
        [NPC("奥鲁特·埃雷古"), AR(), TG("turn", 12882)],
    ], movement="fly")


# 19. Bouldercrag first wave.
def g19_bouldercrag_first() -> None:
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12929), AR(), TG("accept", 12930)],
        [FP("布德克拉格庇护所")],
    ], movement="fly")
    P(25.1, 34.1, "庇护所西北", "bouldercrag", [DO(12930)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12930), AR(), TG("accept", 12931, 12937)],
    ], movement="fly")
    P(27.5, 37.3, "雪流平原", "bouldercrag", [DO(12931, 12937)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12931, 12937), AR(), TG("accept", 12957, 12964)],
    ], movement="fly")
    P(26.5, 50.9, "尼达维里尔", "nidavelir", [DO(12957, 12964)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12957, 12964), AR(), TG("accept", 12965)],
        [NPC("布鲁沃·斩铁"), AR(), TG("accept", 12978)],
    ], movement="fly")


# 20. Loken objects, Dark Armor trigger, Varduran.
def g20_bouldercrag_second() -> None:
    P(24.0, 42.6, "尼达维里尔", "nidavelir", [[LOC("洛肯之怒"), BR(), TG("do", 12965)]], movement="fly")
    P(26.2, 47.7, "尼达维里尔", "nidavelir", [[LOC("洛肯之力"), BR(), TG("do", 12965)]], movement="ride", show_anchor=False)
    P(24.6, 48.4, "尼达维里尔", "nidavelir", [[LOC("洛肯之赐"), BR(), TG("do", 12965)]], movement="ride", show_anchor=False)
    P(29.1, 45.1, "尼达维里尔", "nidavelir", [
        DO(12978),
        [TXT("拾取黑暗护甲板"), AR(), TG("accept", 12979)],
        DO(12979),
    ], movement="ride", show_anchor=False)
    P(31.3, 38.2, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12965)],
        [NPC("布鲁沃·斩铁"), AR(), TG("turn", 12978, 12979), AR(), TG("accept", 12980)],
    ], movement="fly")
    P(32.0, 40.7, "米米尔车间", "bouldercrag", [
        [NPC("随从托克"), BR(), TG("do", 12980)],
    ], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("布鲁沃·斩铁"), AR(), TG("turn", 12980)],
        [NPC("塑石者布德克拉格"), AR(), TG("accept", 12984)],
    ], movement="fly")
    P(24.3, 52.2, "尼达维里尔北侧", "nidavelir", [
        [NPC("风暴之子瓦杜兰"), BR(), TG("do", 12984)],
    ], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12984), AR(), TG("accept", 12988)],
        [NPC("布鲁沃·斩铁"), AR(), TG("accept", 12991)],
    ], movement="fly")


# 21. Bouldercrag forge/finale chain.
def g21_bouldercrag_finale() -> None:
    P(29.7, 45.8, "尼达维里尔", "nidavelir", [DO(12988, 12991)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12988), AR(), TG("accept", 12993)],
        [NPC("布鲁沃·斩铁"), AR(), TG("turn", 12991)],
    ], movement="fly")
    P(29.4, 44.9, "尼达维里尔下层", "nidavelir", [DO(12993)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12993), AR(), TG("accept", 12998)],
    ], movement="fly")
    P(36.1, 60.9, "奥迪斯", "bouldercrag", [[LOC("风暴之心"), BR(), TG("do", 12998)]], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 12998), AR(), TG("accept", 13007)],
    ], movement="fly")
    P(27.5, 45.3, "尼达维里尔", "nidavelir", [DO(13007)], movement="fly")
    P(31.4, 38.1, "布德克拉格庇护所", "bouldercrag", [
        [NPC("塑石者布德克拉格"), AR(), TG("turn", 13007)],
    ], movement="fly")


# 22. Camp Tunka'lo final one-time chain.
def g22_tunkalo() -> None:
    P(65.7, 51.4, "唐卡洛营地", "tunkalo", [
        [FP("唐卡洛营地")],
        [NPC("夏拉托尔"), AR(), TG("turn", 13426), AR(), TG("accept", 13034)],
        DO(13034),
        [NPC("夏拉托尔"), AR(), TG("turn", 13034), AR(), TG("accept", 13037)],
    ], movement="fly")
    P(61.2, 39.0, "唐卡洛北侧", "tunkalo", [
        [NPC("迅矛酋长"), BR(), TG("do", 13037)],
        [NPC("迅矛酋长"), AR(), TG("accept", 13038)],
    ], movement="fly")
    P(64.6, 45.0, "浮冰深渊南侧", "tunkalo", [DO(13038)], movement="fly")
    P(65.7, 51.4, "唐卡洛营地", "tunkalo", [
        [NPC("夏拉托尔"), AR(), TG("turn", 13037, 13038), AR(), TG("accept", 13048, 13049)],
    ], movement="fly")
    P(65.2, 42.6, "嚎风洞穴", "howling_hollow", [DO(13048, 13049)], movement="fly")
    P(65.7, 51.4, "唐卡洛营地", "tunkalo", [
        [NPC("夏拉托尔"), AR(), TG("turn", 13048, 13049), AR(), TG("accept", 13058)],
    ], movement="fly")
    P(64.4, 46.7, "唐卡洛南侧", "tunkalo", [DO(13058)], movement="fly")
    P(65.7, 51.4, "唐卡洛营地", "tunkalo", [
        [NPC("夏拉托尔"), AR(), TG("turn", 13058)],
    ], movement="fly")


GROUPS = [
    ("K3：入图、借用飞龙、接任务", "交《豪华的体验！》，五号分别领取借用双足飞龙并开K3飞行点，再接基尔、莉吉特和格莱奇当前任务。", g1_k3_entry),
    ("K3西侧：清理残骸 → 雷区 → 野蛮岭", "先取烧焦零件，回K3接《雷区里的工具》；再进雷区取工具，去野蛮岭做瘤皮和粮食，最后回K3交接。", g2_k3_west),
    ("加姆 → 水晶蛛网洞穴 → 希弗列尔达", "先做加姆雷区地雷，再接洞穴任务；K3北侧做U.D.E.D.，进洞完成蜘蛛、矿石、毒囊和护送，再去希弗列尔达做囚犯与设备后回K3。", g3_garm_cave_sifreldar),
    ("加姆高地：牢门探戈 → 完美计划", "在加姆高地取电池并激活传送器回K3；交接后用莉吉特旁传送台返回加姆，沿路杀怪到最上层祭坛爆破，再传回K3交任务。", g4_garm_backdoor),
    ("荒弃矿洞：洛莉拉 → 米尔德蕾", "沿矿洞内NPC顺序推进，做到《特殊的囚犯》并回洛莉拉。", g6_forlorn_mine),
    ("布伦希尔达 → 瓦基里安", "完成村内比武链；到瓦基里安先杀伊尔达并从旁边大箱子接《燃烧吧，瓦基里安》，再做室外任务。", g7_brunnhildar_valkyrion),
    ("布莉亚娜：熊熊大作战 → 冰冷的心", "完成冰牙载具战和丹尼芬雷营救，再回布莉亚娜。", g8_brianna),
    ("艾丝崔 → 冬眠洞穴 → 利齿之坑", "从冬眠洞穴入口进洞完成母熊/冰虫，再做基加拉格和利齿之坑。", g9_astrid_pit),
    ("驭龙赛 → 托里姆 → 格罗玛什", "完成驭龙赛和托里姆对话；到格罗玛什接任务、开飞行点、绑炉石，再进基莫拉克之巢完成猎人链和《紧急措施》。", g10_drakkensryd_thorim),
    ("弗约恩之砧：弥补关系 + 精炼之火", "完成《弥补关系》，拾取熔渣覆盖的金属接《精炼之火》，同地完成后回托里姆。", g11_mending_fences),
    ("丹尼芬雷：重铸盟约 → 霍迪尔任务 → 回首往事", "依次处理丹尼芬雷、霜原湖、冬眠洞穴/上古寒冬山谷和雷暴台地任务。", g12_dun_first),
    ("托里姆：维拉努斯 → 科洛米尔", "取5枚小型始祖龙卵；回托里姆后顺路拿布莱恩便笺，再引出维拉努斯并推进科洛米尔。", g13_veranus),
    ("造物者圣台 → 奥杜尔 → 丹尼芬雷", "完成造物者圣台任务和《清算之战》，开奥杜尔飞行点后系统飞行到丹尼芬雷。", g15_thorim_finale),
    ("炉石格罗玛什 → 兽人语 → 寒风", "炉石回格罗玛什交布莱恩便笺和《紧急措施》，继续霜齿追踪与兽人语任务。", g16_gromarsh_brann_start),
    ("寒风峡谷 → 发明家图书馆", "完成寒风后进入发明家图书馆，连续推进磁盘、数据库和档案员麦卡顿。", g17_brann_library),
    ("布莱恩营地 → 诺甘农之核 → 格罗玛什", "取两份文件，进入洛肯的宝库取得诺甘农之核，再到创世神殿顶部完成钥石事件。", g18_brann_core_gromarsh),
    ("布德克拉格：土壤 → 雪流平原 → 尼达维里尔", "开布德克拉格飞行点，完成魔化土壤、雪流平原和尼达维里尔第一组任务。", g19_bouldercrag_first),
    ("布德克拉格：洛肯物件 → 黑暗护甲 → 瓦杜兰", "依次处理三件洛肯固定物、黑暗护甲板链和风暴之子瓦杜兰。", g20_bouldercrag_second),
    ("尼达维里尔熔炉 → 风暴之心 → 钢铁巨像", "完成三个闪电熔炉、两份规格说明书、风暴之心和钢铁巨像。", g21_bouldercrag_finale),
    ("唐卡洛营地 → 嚎风洞穴 → 北风", "开唐卡洛飞行点，完成雷蹄记忆、4道裂隙、嚎风洞穴和北风事件。", g22_tunkalo),
]

for title, summary, fn in GROUPS:
    G(title, summary, fn)

missing = sorted(FORMAL - covered)
unexpected = sorted(covered - FORMAL)

route = {
    "order": 6,
    "uiStandard": "semantic-hud-v45",
    "title": "风暴峭壁 · 77+ 五开整图路线",
    "sub": "K3取得借用双足飞龙后，按K3→希弗列尔达/布伦希尔达→霍迪尔/托里姆→格罗玛什/布莱恩→布德克拉格→唐卡洛固定顺序清一次性户外任务。",
    "badge": "炉石：阿格玛之锤-格罗玛什坠毁点\n预计总时间：待组件模型重算",
    "image": "maps/67-the-storm-peaks-hd.jpg",
    "legend": "",
    "footer": "",
    "labels": [
        [41.0, 86.0, "K3"], [50.3, 81.8, "加姆高地"], [42.5, 74.8, "水晶蛛网洞穴"],
        [42.0, 69.0, "荒弃矿洞"], [48.0, 70.0, "布伦希尔达村"], [25.0, 61.0, "瓦基里安"],
        [65.4, 60.2, "丹尼芬雷"], [33.4, 57.9, "风暴神殿"], [56.0, 43.5, "造物者圣台"],
        [45.0, 28.0, "奥杜尔"], [37.3, 49.6, "格罗玛什坠毁点"], [39.5, 41.2, "发明家图书馆"],
        [31.4, 38.1, "布德克拉格庇护所"], [27.0, 47.0, "尼达维里尔"], [65.7, 51.4, "唐卡洛营地"],
    ],
    "points": points,
    "defaultIndex": 0,
    "phaseColors": {
        "k3": "#60a5fa", "k3_west": "#60a5fa", "garm": "#7dd3fc", "crystalweb": "#7dd3fc",
        "sifreldar": "#c4b5fd", "gromarsh": "#f6c453", "forlorn": "#c4b5fd", "brunnhildar": "#c4b5fd",
        "valkyrion": "#f9a8d4", "hibernal": "#bae6fd", "thorim": "#fde68a", "hodir": "#a7f3d0",
        "dun_niffelem": "#a7f3d0", "terrace": "#fde68a", "ulduar": "#d1d5db", "brann": "#fdba74",
        "library": "#fdba74", "bouldercrag": "#fca5a5", "nidavelir": "#fca5a5", "tunkalo": "#86efac",
        "howling_hollow": "#86efac",
    },
    "displayName": "风暴峭壁",
    "stepGroups": step_groups,
    "defaultGroupIndex": 0,
    "hearthChain": ["阿格玛之锤", "格罗玛什坠毁点"],
    "timing": {
        "centerMinutes": sum(float(g["timing"]["centerMinutes"]) for g in step_groups),
        "rangeMinutes": [
            sum(float(g["timing"]["rangeMinutes"][0]) for g in step_groups),
            sum(float(g["timing"]["rangeMinutes"][1]) for g in step_groups),
        ],
        "actualRuns": [],
        "model": "storm_peaks_pre_component_placeholder",
    },
}

routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
routes["storm"] = route
# Preserve main-spine reserved slots while later maps are still being built.
if "zuldrak" in routes:
    routes["zuldrak"]["order"] = 9
if "grizzly" in routes:
    routes["grizzly"]["order"] = 10
routes = dict(sorted(routes.items(), key=lambda kv: (int(kv[1].get("order", 999)), kv[0])))
WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

coverage = {
    "status": "formal_storm_peaks_full_clear_fixed_route_pre_live_reputation_calibration",
    "formal_task_count": len(FORMAL),
    "covered_task_count": len(covered & FORMAL),
    "missing": missing,
    "unexpected": unexpected,
    "point_count": len(points),
    "step_group_count": len(step_groups),
    "reputation_assumed_available_ids": REPUTATION_ASSUMED_AVAILABLE,
    "reputation_policy": "route is deterministic: assume these quests are available at their geographic insertion points; live run only calibrates the real unlock point if the assumption fails",
    "hearth_chain": route["hearthChain"],
    "opened_flight_points_final": sorted(opened_flight_points),
    "system_flight_audit": flight_path_audit,
}
COVERAGE_OUT.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PLAYER_GROUPS_OUT.write_text(json.dumps({
    "zone": "风暴峭壁",
    "pointCount": len(points),
    "groupCount": len(step_groups),
    "groups": [
        {"title": g["title"], "summary": g["summary"], "pointCount": g["end"] - g["start"] + 1, "timing": g["timing"]}
        for g in step_groups
    ],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

AUDIT_OUT.write_text("\n".join([
    "# 风暴峭壁整图路线插入审计",
    "",
    "- 从零入口：达拉然当前77级路线完成后，12853《豪华的体验！》在K3交付；五号先拿借用双足飞龙并开K3飞行点。",
    f"- foundation正式池：{len(FORMAL)}项；路线覆盖：{len(covered & FORMAL)}；missing={missing}；unexpected={unexpected}。",
    "- 声望策略按用户当前要求：路线内部不保留条件分支；12985/13001/13011/13420按排定位置无条件接做交。若首跑发现真实声望门槛卡住，再只校正其固定解锁位置。",
    "- 12930《稀有的土壤》不安排霜纹布获取；五号使用用户现有库存，只计算7块魔化土壤的现场动作。",
    "- 当前路线不学习寒冷天气飞行，因此排除13060《终极运输方案》；失去免费任务运输后，不再从K3提前绕行格罗玛什。",
    "- 格罗玛什改为第一次到风暴神殿后顺路插入：接齐西侧任务、开飞行点并绑定炉石，同一趟完成基莫拉克之巢猎人链与《紧急措施》；布莱恩便笺后移到维拉努斯诱引点前顺路取得。托里姆/奥杜尔完成后从丹尼芬雷炉石回格罗玛什继续布莱恩线。普通自主飞行只由地图路线表达，不进入玩家动作文字。",
    "- 新路线从第一版即声明semantic-hud-v45；所有stepGroup均由结构化动作段直接生成actionHtml，不经过广义字符串替换器。",
]) + "\n", encoding="utf-8")

print(json.dumps(coverage, ensure_ascii=False, indent=2))
if missing or unexpected:
    raise SystemExit(2)
