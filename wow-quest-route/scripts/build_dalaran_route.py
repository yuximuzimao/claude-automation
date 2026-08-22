from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dalaran-task-foundation.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE_OUT = ROOT / "data/route-atlas/dalaran-route-coverage.json"
PLAYER_GROUPS_OUT = ROOT / "data/route-atlas/dalaran-player-step-groups.json"
AUDIT_OUT = ROOT / "docs/analysis/2026-08-22-dalaran-route-audit.md"

FOUNDATION_DATA = json.loads(FOUNDATION.read_text(encoding="utf-8"))
TASKS = {int(t["quest_id"]): t for t in FOUNDATION_DATA["tasks"]}
FORMAL = set(int(qid) for qid in FOUNDATION_DATA["current_formal_task_ids"])
EXPECTED_FORMAL = {12521, 12790, 12791, 12853, 12974}
if FORMAL != EXPECTED_FORMAL:
    raise RuntimeError(f"Dalaran formal pool drifted: {sorted(FORMAL)}")

points: list[list[Any]] = []
covered: set[int] = set()
step_groups: list[dict[str, Any]] = []


def n(qid: int) -> str:
    return f"《{TASKS[qid]['name']}》"


def P(
    x: float,
    y: float,
    title: str,
    action: str,
    phase: str,
    note: str = "",
    movement: str = "ride",
    qids: tuple[int, ...] = (),
    optional: bool = False,
    fivebox_check: str = "",
) -> None:
    points.append([x, y, title, action, phase, note, movement, optional, fivebox_check])
    covered.update(qids)


def G(
    title: str,
    summary: str,
    fn,
    *,
    action_html: str,
    note_html: str = "",
    timing_center: float,
    timing_range: tuple[float, float],
) -> None:
    start = len(points)
    fn()
    end = len(points) - 1
    if end < start:
        raise RuntimeError(f"empty group: {title}")
    step_groups.append({
        "start": start,
        "end": end,
        "title": title,
        "summary": summary,
        "actionHtml": action_html.strip(),
        "noteHtml": note_html.strip(),
        "timing": {
            "centerMinutes": timing_center,
            "rangeMinutes": [timing_range[0], timing_range[1]],
            "includeInTotal": True,
        },
    })


def g1_local_chain() -> None:
    P(
        56.30,
        46.72,
        "紫罗兰之门·大法师塞琳德拉",
        f"交{n(12791)} → 接{n(12790)}",
        "violet",
        "",
        "ride",
        (12791, 12790),
    )
    P(
        55.93,
        46.78,
        "紫罗兰之门·传送水晶",
        f"做{n(12790)}",
        "violet",
        f"{n(12790)}：两个水晶都是个人任务交互；五个角色分别完成下城和回城两次点击。",
        "script",
        (12790,),
    )
    P(
        56.30,
        46.72,
        "紫罗兰之门·大法师塞琳德拉",
        f"交{n(12790)}",
        "violet",
        "",
        "ride",
        (12790,),
    )


def g2_east_breadcrumbs() -> None:
    P(
        68.55,
        42.05,
        "克拉苏斯平台西侧·大法师伯塔鲁斯",
        f"接{n(12521)}；只接任务，不选择前往索拉查盆地的出发对话",
        "east",
        f"{n(12521)}：先携带到后续索拉查阶段；现在不要让大法师把角色送走。",
        "ride",
        (12521,),
    )
    P(
        72.0,
        46.0,
        "克拉苏斯平台·飞行点",
        "开飞行点：达拉然（五号分别）",
        "east",
        "不要在附近学习寒冷天气飞行；当前路线要保留到K3领取免费借用双足飞龙的资格。",
        "ride",
    )


def g3_underbelly() -> None:
    P(
        60.0,
        47.5,
        "克拉苏斯平台入口旁·下水道东入口",
        "从东入口下到达拉然下水道，沿通道向西走",
        "underbelly",
        "",
        "ride",
    )
    P(
        48.18,
        44.71,
        "达拉然下水道·狡猾的维克斯",
        f"接{n(12974)}",
        "underbelly",
        f"{n(12974)}：携带到祖达克痛苦斗兽场；现在只接，不离开达拉然。",
        "ride",
        (12974,),
    )
    P(
        37.68,
        50.17,
        "达拉然下水道·林·多克塔",
        f"接{n(12853)}",
        "underbelly",
        f"{n(12853)}：这是当前下一图风暴峭壁K3的引导任务。",
        "ride",
        (12853,),
    )
    P(
        35.0,
        45.0,
        "下水道西入口 → 紫罗兰之门",
        "从西入口回到地面，向东返回紫罗兰之门",
        "underbelly",
        "",
        "ride",
    )


def g4_to_k3() -> None:
    P(
        55.93,
        46.78,
        "紫罗兰之门 → 紫罗兰哨站 → K3",
        f"五号分别点击下城水晶到紫罗兰哨站；落地后沿晶歌森林北部道路向东北骑入风暴峭壁K3；到K3找基尔·斯巴索克交{n(12853)}",
        "exit",
        f"{n(12853)}：抵达K3后直接交付。下一步进入风暴峭壁路线，先找“诚实的”麦克斯领取借用双足飞龙。",
        "crossmap",
        (12853,),
    )


G(
    "紫罗兰之门：魔法王国达拉然 → 来去如风",
    "交达拉然入城任务，完成上下传送水晶教学并原地交回。",
    g1_local_chain,
    action_html="""
<div class="ra-line"><span class="ra-location">紫罗兰之门</span>·<span class="ra-npc">大法师塞琳德拉</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">魔法王国达拉然</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">来去如风</span></div>
<div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">来去如风</span></div>
<div class="ra-line"><span class="ra-location">紫罗兰之门</span>·<span class="ra-npc">大法师塞琳德拉</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">来去如风</span></div>
""",
    note_html="""
<div class="ra-note-heading">备注</div>
<div class="ra-note-block"><div class="ra-note-task">《来去如风》</div><div class="ra-note-text">两个水晶都是个人任务交互，五个角色分别完成下城和回城两次点击。</div></div>
""",
    timing_center=6.0,
    timing_range=(4.0, 9.0),
)

G(
    "克拉苏斯平台：索拉查引导 + 达拉然飞行点",
    "把后续索拉查引导接走，但不触发离城；同时开启达拉然飞行点。",
    g2_east_breadcrumbs,
    action_html="""
<div class="ra-line"><span class="ra-location">克拉苏斯平台西侧</span>·<span class="ra-npc">大法师伯塔鲁斯</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">赫米特·奈辛瓦里哪去了？</span></div>
<div class="ra-line"><span class="ra-danger">只接任务，不选择前往索拉查盆地的出发对话</span></div>
<div class="ra-line"><span class="ra-system-action ra-flightpoint">开飞行点：达拉然（五号分别）</span></div>
""",
    note_html="""
<div class="ra-note-heading">备注</div>
<div class="ra-note-block"><div class="ra-note-task">《赫米特·奈辛瓦里哪去了？》</div><div class="ra-note-text">先携带到索拉查阶段。</div></div>
<div class="ra-note-block"><div class="ra-note-task">免费飞行坐骑</div><div class="ra-note-text"><span class="ra-danger">不要在这里学习寒冷天气飞行</span>；到K3先领取借用双足飞龙。</div></div>
""",
    timing_center=3.0,
    timing_range=(2.0, 5.0),
)

G(
    "达拉然下水道：祖达克/风暴引导",
    "从东入口进下水道，依次拿祖达克斗兽场引导和当前风暴K3引导，再从西入口返回地面。",
    g3_underbelly,
    action_html="""
<div class="ra-line"><span class="ra-location">克拉苏斯平台入口旁</span>·下水道东入口<span class="ra-arrow">→</span><span class="ra-location">达拉然下水道</span></div>
<div class="ra-line"><span class="ra-npc">狡猾的维克斯</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">勇士的召唤！</span></div>
<div class="ra-line"><span class="ra-npc">林·多克塔</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">豪华的体验！</span></div>
<div class="ra-line"><span class="ra-location">下水道西入口</span><span class="ra-arrow">→</span>回地面<span class="ra-arrow">→</span><span class="ra-location">紫罗兰之门</span></div>
""",
    note_html="""
<div class="ra-note-heading">备注</div>
<div class="ra-note-block"><div class="ra-note-task">《勇士的召唤！》</div><div class="ra-note-text">携带到祖达克痛苦斗兽场。</div></div>
<div class="ra-note-block"><div class="ra-note-task">《豪华的体验！》</div><div class="ra-note-text">当前下一图K3引导，离城后马上交。</div></div>
""",
    timing_center=6.0,
    timing_range=(4.0, 9.0),
)

G(
    "紫罗兰之门 → K3",
    "用已经解锁的下城水晶落到晶歌森林，地面骑到K3并交风暴引导。",
    g4_to_k3,
    action_html="""
<div class="ra-line"><span class="ra-location">紫罗兰之门</span>·下城水晶<span class="ra-arrow">→</span><span class="ra-location">晶歌森林·紫罗兰哨站</span></div>
<div class="ra-line"><span class="ra-location">紫罗兰哨站</span><span class="ra-arrow">→</span><span class="ra-transport">沿北部道路向东北骑行</span><span class="ra-arrow">→</span><span class="ra-location">风暴峭壁·K3</span></div>
<div class="ra-line"><span class="ra-location">K3</span>·<span class="ra-npc">基尔·斯巴索克</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">豪华的体验！</span></div>
<div class="ra-line"><span class="ra-danger">到K3后先找“诚实的”麦克斯领取借用双足飞龙，再开始风暴任务</span></div>
""",
    note_html="""
<div class="ra-note-heading">备注</div>
<div class="ra-note-block"><div class="ra-note-task">《豪华的体验！》</div><div class="ra-note-text">抵达K3后直接交付。</div></div>
""",
    timing_center=8.0,
    timing_range=(5.0, 11.0),
)

missing = sorted(FORMAL - covered)
unexpected = sorted(covered - FORMAL)

route = {
    "order": 5,
    "uiStandard": "semantic-hud-v45",
    "title": "达拉然 · 77级主轴任务清理",
    "sub": "龙骨整图完成后进入达拉然：清完本地入城链，一次接走风暴/索拉查/祖达克三条当前可接主轴引导，然后下城去K3；冰冠《作战准备》在冰冠入口重新检查。",
    "badge": "炉石：阿格玛之锤\n预计总时间：约23分钟（15—34分钟）",
    "image": "maps/4395-dalaran.png",
    "legend": "",
    "footer": "",
    "labels": [
        [56.3, 46.7, "紫罗兰之门"],
        [68.6, 42.1, "伯塔鲁斯"],
        [72.0, 46.0, "飞行管理员"],
        [60.0, 47.5, "下水道东入口"],
        [48.2, 44.7, "狡猾的维克斯"],
        [37.7, 50.2, "林·多克塔"],
        [35.0, 45.0, "下水道西入口"],
    ],
    "points": points,
    "defaultIndex": 0,
    "phaseColors": {
        "violet": "#a78bfa",
        "east": "#60a5fa",
        "underbelly": "#f6c453",
        "exit": "#34d399",
    },
    "displayName": "达拉然",
    "stepGroups": step_groups,
    "defaultGroupIndex": 0,
    "hearthChain": ["阿格玛之锤"],
    "timing": {
        "centerMinutes": 23.0,
        "rangeMinutes": [15.0, 34.0],
        "actualRuns": [],
        "model": "dalaran_manual_component_v1",
    },
}

routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
routes["dalaran"] = route
# Reserve the canonical main-spine order for maps still being built.
if "zuldrak" in routes:
    routes["zuldrak"]["order"] = 9
if "grizzly" in routes:
    routes["grizzly"]["order"] = 10
routes = dict(sorted(routes.items(), key=lambda kv: (int(kv[1].get("order", 999)), kv[0])))
WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

coverage = {
    "status": "formal_dalaran_current_level_route",
    "candidate_knowledge_count": FOUNDATION_DATA["knowledge_task_count"],
    "formal_task_count": len(FORMAL),
    "covered_task_count": len(covered & FORMAL),
    "local_closed_ids": [12791, 12790],
    "carried_out_ids": [12521, 12974],
    "excluded_cold_weather_flying_ids": [13419],
    "storm_breadcrumb_closed_at_k3": 12853,
    "missing": missing,
    "unexpected": unexpected,
    "point_count": len(points),
    "step_group_count": len(step_groups),
    "starting_long_term_log_count": 4,
    "ending_long_term_log_count": 5,
    "log_capacity_status": "safe_below_18_advance_breadcrumb_threshold",
}
COVERAGE_OUT.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PLAYER_GROUPS_OUT.write_text(json.dumps({
    "zone": "达拉然",
    "pointCount": len(points),
    "groupCount": len(step_groups),
    "groups": [{"title": g["title"], "summary": g["summary"], "pointCount": g["end"] - g["start"] + 1, "timing": g["timing"]} for g in step_groups],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

AUDIT_OUT.write_text("\n".join([
    "# 达拉然77级主轴路线审计",
    "",
    "- 从零入口：龙骨荒野整图完成，携带12791《魔法王国达拉然》进入达拉然。当前首组实际绕行不反写从零路线。",
    f"- 基础知识召回{FOUNDATION_DATA['knowledge_task_count']}项；结构/等级/阵营/副本/专业/节日与实服可接状态分类后，当前正式池固定为{sorted(FORMAL)}共5项。",
    "- 本地闭合：12791→12790；离开达拉然后没有遗漏的77级当前可接普通一次性本地任务。",
    "- 当前可接的三条主轴出图任务在本次达拉然停靠接取：12521索拉查、12853风暴、12974祖达克。只立即执行12853，其余两条携带到对应地图。",
    "- 13419《作战准备》requiredLevel=77，但实际还要求角色已学习寒冷天气飞行；当前主轴明确不学习该技能，因此从可执行路线剔除。冰冠改为直接使用K3借用双足飞龙飞上奥格瑞姆之锤，不依赖这条运输任务。", 
    "- 龙骨离图长期任务按4条计；达拉然交掉12791、增加三条当前可接主轴引导并在K3交12853后，长期日志约5条，远低于≤18可提前接未来确定任务阈值。",
    "- 12521有NPC出发脚本；当前只接任务，不触发脚本，避免提前跳索拉查。",
    "- 克拉苏斯平台开达拉然飞行点；当前不学寒冷天气飞行，保留K3借用双足飞龙资格。",
    "- 玩家步骤共4段，中心估时23分钟，合理区间15—34分钟；首次实跑后用clean timing校准。",
    "- 地图离开条件：12853已在K3交付，下一步进入风暴峭壁并先取得借用双足飞龙。",
]) + "\n", encoding="utf-8")

print(json.dumps(coverage, ensure_ascii=False, indent=2))
if missing or unexpected:
    raise SystemExit(2)
