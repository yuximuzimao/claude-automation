from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE_OUT = ROOT / "data/route-atlas/sholazar-route-coverage.json"
PLAYER_GROUPS_OUT = ROOT / "data/route-atlas/sholazar-player-step-groups.json"
TRANSITION_AUDIT = ROOT / "data/route-atlas/sholazar-zuldrak-transition-audit.json"
MERGE_AUDIT = ROOT / "data/route-atlas/sholazar-whole-map-merge-audit.json"

DATA = json.loads(FOUNDATION.read_text(encoding="utf-8"))
TASKS = {int(t["quest_id"]): t for t in DATA["tasks"]}
FORMAL = {int(qid) for qid in DATA["formal_task_ids"]}
points: list[list[Any]] = []
covered: set[int] = set()
step_groups: list[dict[str, Any]] = []
_current_html: list[str] = []
_current_note_blocks: list[tuple[int | None, str, str]] = []
opened_flight_points = {"银色比武场", "达拉然", "龙眠神殿"}
flight_path_audit: list[dict[str, str]] = []


def name(qid: int) -> str: return str(TASKS[qid]["name"])
def n(qid: int) -> str: return f"《{name(qid)}》"
def S(kind: str, value: Any = None, *qids: int): return kind, value, tuple(qids)
def NPC(text: str): return S("npc", text)
def TXT(text: str): return S("txt", text)
def AR(): return S("arrow")
def BR(): return S("branch")
def FP(text: str): return S("flightpoint", text)
def TAXI(a: str, b: str): return S("taxi", (a, b))
def HB(text: str): return S("hearthbind", text)
def HR(text: str): return S("hearthreturn", text)
def TG(action: str, *qids: int): return S("taskgroup", action, *qids)
def DO(*qids: int): return [BR(), TG("do", *qids)]


def render_plain(line):
    out=[]
    for kind,value,qids in line:
        if kind in {"npc","txt"}: out.append(str(value))
        elif kind=="arrow": out.append(" → ")
        elif kind=="branch": out.append("↳ ")
        elif kind=="flightpoint": out.append(f"开飞行点：{value}")
        elif kind=="taxi": out.append(f"系统飞行：{value[0]} → {value[1]}")
        elif kind=="hearthbind": out.append(f"炉石绑定：{value}")
        elif kind=="hearthreturn": out.append(f"使用炉石：{value}")
        elif kind=="taskgroup":
            verb={"accept":"接","turn":"交","do":"做"}[str(value)]
            out.append("；".join(f"{verb}{n(q)}" for q in qids))
    return "".join(out)


def render_html(line, inline_location: str | None = None):
    parts=[]; branch=False
    if inline_location:
        parts += [f'<span class="ra-location">{html.escape(inline_location)}</span>', '<span class="ra-inline-sep"> </span>']
    for kind,value,qids in line:
        if kind=="npc": parts.append(f'<span class="ra-npc">{html.escape(str(value))}</span>')
        elif kind=="txt": parts.append(html.escape(str(value)))
        elif kind=="arrow": parts.append('<span class="ra-arrow">→</span>')
        elif kind=="branch": branch=True; parts.append('<span class="ra-branch">↳</span>')
        elif kind=="flightpoint": parts.append(f'<span class="ra-system-action ra-flightpoint">开飞行点：{html.escape(str(value))}</span>')
        elif kind=="taxi": parts.append(f'<span class="ra-system-action ra-flightpath">系统飞行：{html.escape(str(value[0]))} → {html.escape(str(value[1]))}</span>')
        elif kind=="hearthbind": parts.append(f'<span class="ra-system-action ra-hearthstone">炉石绑定：{html.escape(str(value))}</span>')
        elif kind=="hearthreturn": parts.append(f'<span class="ra-system-action ra-hearthstone">使用炉石：{html.escape(str(value))}</span>')
        elif kind=="taskgroup":
            verb={"accept":"接","turn":"交","do":"做"}[str(value)]
            cls={"accept":"ra-accept","turn":"ra-turnin","do":"ra-do-task"}[str(value)]
            parts.append(f'<span class="ra-verb">{verb}</span> ')
            parts.append("、".join(f'<span class="ra-task {cls}">{html.escape(name(q))}</span>' for q in qids))
    cls="ra-line ra-do-inline" if branch and inline_location else ("ra-line ra-do" if branch else "ra-line")
    return f'<div class="{cls}">'+"".join(parts)+"</div>"


def qids_in(lines, action: str | None = None):
    result=[]
    for line in lines:
        for kind,value,qids in line:
            if kind!="taskgroup" or (action is not None and value!=action): continue
            for q in qids:
                if q not in result: result.append(q)
    return result


def note_text(qid: int) -> str: return str(TASKS[qid].get("route_mechanism_note") or "").strip()
def fivebox_text(qid: int) -> str: return str(TASKS[qid].get("fivebox_check") or "").strip()


def render_note_text(text: str) -> str:
    safe = html.escape(text)
    for prefix, cls in (("共享：", "ra-shared"), ("不共享：", "ra-not-shared")):
        if safe.startswith(prefix):
            safe = f'<span class="{cls}">{prefix}</span>' + safe[len(prefix):]
            break
    for term in ("顶层", "一层", "地下", "不要提前离开", "不要攻击", "不要过快击杀"):
        safe = safe.replace(term, f'<span class="ra-danger">{term}</span>')
    return safe


def note_html():
    order=[]; grouped={}
    for qid,kind,text in _current_note_blocks:
        key=(qid,)
        if key not in grouped:
            grouped[key]={"note":[],"fivebox":[]}; order.append(key)
        if text not in grouped[key][kind]: grouped[key][kind].append(text)
    blocks=[]
    for (qid,) in order:
        title=n(qid) if qid else "本段"; payload=grouped[(qid,)]
        body="".join(f'<div class="ra-note-text">{render_note_text(t)}</div>' for t in payload["note"])
        fb="".join('<div class="ra-fivebox-line"><span class="ra-pending">五开待实测：</span>'+html.escape(t)+'</div>' for t in payload["fivebox"])
        blocks.append(f'<div class="ra-note-block"><div class="ra-note-task">{html.escape(title)}</div>{body}{fb}</div>')
    return ('<div class="ra-note-heading">备注</div>'+"".join(blocks)) if blocks else ""


def P(x: float, y: float, title: str, phase: str, lines, *, movement="fly", notes=None, cover=(), show_anchor=True):
    global _current_html, _current_note_blocks
    for line in lines:
        for kind,value,_ in line:
            if kind=="flightpoint": opened_flight_points.add(str(value))
            elif kind=="taxi":
                a,b=map(str,value); missing=[p for p in (a,b) if p not in opened_flight_points]
                if missing: raise RuntimeError(f"unopened flight point at {title}: {a}->{b}; missing={missing}")
                flight_path_audit.append({"from":a,"to":b,"status":"both_opened"})
    covered.update(qids_in(lines)); covered.update(cover)
    action="\n".join(render_plain(l) for l in lines)
    first_do=bool(lines and lines[0] and lines[0][0][0]=="branch")
    if show_anchor:
        if first_do:
            _current_html.append(render_html(lines[0], title)); _current_html.extend(render_html(l) for l in lines[1:])
        else:
            _current_html.append(f'<div class="ra-line ra-point-anchor"><span class="ra-location">{html.escape(title)}</span></div>')
            _current_html.extend(render_html(l) for l in lines)
    else: _current_html.extend(render_html(l) for l in lines)
    regular=[]; fb=[]
    for q in qids_in(lines,"do"):
        t=note_text(q)
        if t: regular.append(f"{n(q)}：{t}"); _current_note_blocks.append((q,"note",t))
        f=fivebox_text(q)
        if f: fb.append(f"五开待实测·{n(q)}：{f}"); _current_note_blocks.append((q,"fivebox",f))
    for q,text in notes or []:
        regular.append(f"{n(q) if q else '本段'}：{text}"); _current_note_blocks.append((q,"note",text))
    points.append([x,y,title,action,phase,"\n".join(regular),movement,False,"\n".join(fb)])


def G(title: str, summary: str, fn, center: float, lo: float, hi: float):
    global _current_html,_current_note_blocks
    start=len(points); _current_html=[]; _current_note_blocks=[]; fn(); end=len(points)-1
    step_groups.append({"start":start,"end":end,"title":title,"summary":summary,"actionHtml":"\n".join(_current_html),"noteHtml":note_html(),"timing":{"centerMinutes":center,"rangeMinutes":[lo,hi],"includeInTotal":True}})

# GROUP_DEFINITIONS

def g1_entry_engineering() -> None:
    P(39.7,58.7,"达拉然 → 蛮藤谷","entry",[
        [TAXI("银色比武场","达拉然")],
        [NPC("大法师伯塔鲁斯"),BR(),TG("do",12521)],
        [NPC("蒙特"),AR(),TG("turn",12521),AR(),TG("accept",12489)],
    ],movement="crossmap",notes=[(None,"从奥格瑞姆之锤先到已开的银色比武场，系统飞达拉然后找大法师伯塔鲁斯触发脚本运输。")])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [NPC("赫米特·奈辛瓦里"),AR(),TG("turn",12489)],
        [HB("奈辛瓦里营地")],
        [NPC("维斯雷·扭钳"),AR(),TG("accept",12522)],
        [NPC("蒂巴尔"),AR(),TG("accept",12524)],
        [NPC("查德"),AR(),TG("accept",12624)],
    ])
    P(38.7,56.7,"蛮藤谷·飞行器引擎","engineering",[DO(12522)])
    P(25.4,58.5,"奈辛瓦里营地","camp",[
        [NPC("维斯雷·扭钳"),AR(),TG("turn",12522),AR(),TG("accept",12523)],
    ])
    P(35.5,47.4,"斯温迪格林挖掘场","dig",[
        DO(12523,12524,12624),
        [NPC("工程师赫莉丝"),AR(),TG("accept",12688)],
        DO(12688),
    ],notes=[(12624,"15只风险投资公司目标完成后戒指仍没齐，就继续刷挖掘者/恶棍；五号都1/1才离开。")])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [NPC("赫米特·奈辛瓦里"),AR(),TG("turn",12688)],
        [NPC("维斯雷·扭钳"),AR(),TG("turn",12523)],
        [NPC("蒂巴尔"),AR(),TG("turn",12524),AR(),TG("accept",12525)],
        [NPC("查德"),AR(),TG("turn",12624)],
        [FP("奈辛瓦里营地")],
        [NPC("卡尔维特教授"),AR(),TG("accept",12696)],
    ])
    P(35.8,50.4,"斯温迪格林挖掘场·北侧高台","dig",[DO(12525)])
    P(27.1,59.9,"奈辛瓦里营地","camp",[
        [NPC("蒂巴尔"),AR(),TG("turn",12525)],
        [NPC("赫米特·奈辛瓦里"),AR(),TG("accept",12520)],
        [NPC("巴克·坎维尔"),AR(),TG("accept",12549)],
        [NPC("德洛斯坦"),AR(),TG("accept",12589)],
    ])
    P(27.0,60.3,"奈辛瓦里营地·幸运的威尔海姆","camp",[DO(12589)])
    P(27.1,59.9,"奈辛瓦里营地","camp",[
        [NPC("德洛斯坦"),AR(),TG("turn",12589),AR(),TG("accept",12592)],
    ],show_anchor=False)


def g2_hunts_nozzlerust() -> None:
    P(28.0,56.9,"奈辛瓦里营地东侧","hunt",[DO(12549)])
    P(29.4,50.4,"碎角犀牛区","hunt",[DO(12520)])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [NPC("赫米特·奈辛瓦里"),AR(),TG("turn",12520),AR(),TG("accept",12526)],
        [NPC("巴克·坎维尔"),AR(),TG("turn",12549),AR(),TG("accept",12550)],
        [NPC("蒂巴尔"),AR(),TG("accept",12551)],
        [NPC("葛瑞姆·雷酒"),AR(),TG("accept",12634)],
        [NPC("菜刀库尔格"),AR(),TG("accept",12804)],
    ])
    P(25.6,66.5,"诺兹隆之骨·神谕者索乌拉姆","nozzlerust",[
        [NPC("神谕者索乌拉姆"),AR(),TG("turn",12526),AR(),TG("accept",12543)],
    ])
    P(28.4,71.3,"诺兹隆之骨南侧","nozzlerust",[DO(12804)])
    P(47.0,61.0,"蛮藤谷中部","central",[DO(12543,12551,12634)])
    P(25.6,66.5,"诺兹隆之骨","nozzlerust",[
        [NPC("神谕者索乌拉姆"),AR(),TG("turn",12543),AR(),TG("accept",12544)],
        DO(12544),
    ])
    P(32.6,38.5,"苦潮湖西北·杉苟足迹","tracks",[DO(12550)])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [NPC("赫米特·奈辛瓦里"),AR(),TG("turn",12544),AR(),TG("accept",12556)],
        [NPC("巴克·坎维尔"),AR(),TG("turn",12550),AR(),TG("accept",12558)],
        [NPC("蒂巴尔"),AR(),TG("turn",12551),AR(),TG("accept",12560)],
        [NPC("菜刀库尔格"),AR(),TG("turn",12804)],
        [NPC("葛瑞姆·雷酒"),AR(),TG("turn",12634),AR(),TG("accept",12644)],
        DO(12644),
        [NPC("葛瑞姆·雷酒"),AR(),TG("turn",12644),AR(),TG("accept",12645)],
        [NPC("赫米特·奈辛瓦里"),BR(),TG("do",12645)],
        [NPC("哈迪乌斯·哈洛维"),BR(),TG("do",12645)],
    ],notes=[(12645,"这里只完成赫米特和哈迪乌斯两个品酒目标；塔玛拉留到河流之心自然经过。")])


def g3_final_hunts_river() -> None:
    P(43.9,63.3,"蛮藤谷河岸·沙蕨","final_hunt",[DO(12560)])
    P(46.7,42.8,"法鲁恩","final_hunt",[DO(12556)])
    P(33.8,33.7,"杉苟","final_hunt",[DO(12558,12592)],notes=[(12592,"若还没60/60，返程沿路补足猎物；《湖边着陆场》要求这项已完成。")])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [HR("奈辛瓦里营地")],
        [NPC("赫米特·奈辛瓦里"),AR(),TG("turn",12556)],
        [NPC("巴克·坎维尔"),AR(),TG("turn",12558)],
        [NPC("蒂巴尔"),AR(),TG("turn",12560),AR(),TG("accept",12569)],
        [NPC("德洛斯坦"),AR(),TG("turn",12592)],
        [NPC("赫米特·奈辛瓦里"),AR(),TG("accept",12651)],
    ],movement="hearth")
    P(46.3,63.4,"蛮藤谷河岸·倒下的原木","river",[DO(12569)])
    P(50.5,62.1,"河流之心","rivers_heart",[
        [FP("河流之心")],
        [NPC("塔玛拉·摇链"),AR(),TG("turn",12651)],
        [NPC("飞行员维克"),AR(),TG("turn",12696),AR(),TG("accept",12699)],
        [NPC("塔玛拉·摇链"),BR(),TG("do",12645)],
        [NPC("塔玛拉·摇链"),AR(),TG("accept",12654)],
    ])
    P(48.2,63.3,"河流之心·湖内","rivers_heart",[DO(12699)])
    P(50.0,61.5,"河流之心·飞行员维克","rivers_heart",[
        [NPC("飞行员维克"),AR(),TG("turn",12699),AR(),TG("accept",12671)],
        DO(12671),
        [NPC("飞行员维克"),AR(),TG("turn",12671)],
    ])
    P(50.5,77.2,"匹奇","pitch",[
        DO(12654),
        [NPC("猎手基克吉克"),AR(),TG("accept",12528)],
    ])
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("turn",12528)],
    ])


def g4_frenzyheart() -> None:
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("accept",12529)],
        [NPC("猩猩猎手格利基克"),AR(),TG("accept",12530)],
    ])
    P(64.0,72.5,"硬皮猩猩区","hardknuckle",[DO(12529,12530)])
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("turn",12529,12530),AR(),TG("accept",12533)],
        [NPC("长者哈尔卡克"),AR(),TG("accept",12534)],
    ])
    P(58.5,81.0,"蓝玉虫巢","sapphire",[DO(12533,12534)])
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("turn",12533,12534)],
        [NPC("长者哈尔卡克"),AR(),TG("accept",12532)],
        DO(12532),
        [NPC("长者哈尔卡克"),AR(),TG("turn",12532),AR(),TG("accept",12531)],
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("accept",12535)],
    ])
    P(57.0,85.7,"狂心岭南部","frenzyheart_south",[DO(12531,12535)])
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("turn",12531,12535),AR(),TG("accept",12536)],
    ])


def g5_mistwhisper_hearth() -> None:
    P(57.3,68.4,"狂心岭·被俘虏的鳄鱼","transport",[DO(12536)])
    P(42.1,38.6,"雾语村·瑟匹克","mistwhisper",[
        [NPC("鳄鱼人猎手瑟匹克"),AR(),TG("turn",12536),AR(),TG("accept",12537,12538)],
    ])
    P(44.5,37.0,"雾语天气祭坛","mistwhisper",[DO(12537,12538)])
    P(42.1,38.6,"雾语村·瑟匹克","mistwhisper",[
        [NPC("鳄鱼人猎手瑟匹克"),AR(),TG("turn",12537,12538),AR(),TG("accept",12539)],
    ])
    P(27.1,58.6,"奈辛瓦里营地","camp",[
        [HR("奈辛瓦里营地")],
        [NPC("蒂巴尔"),AR(),TG("turn",12569)],
        [NPC("葛瑞姆·雷酒"),AR(),TG("turn",12645)],
        [NPC("赫米特·奈辛瓦里"),AR(),TG("accept",12595)],
    ],movement="hearth")
    P(55.0,69.1,"狂心岭","frenzyheart",[
        [NPC("高阶萨满祭司拉克亚克"),AR(),TG("turn",12539),AR(),TG("accept",12540)],
    ])


def g6_oracle() -> None:
    P(56.6,64.5,"受伤的雨声神谕者","oracle",[
        [NPC("受伤的雨声神谕者"),AR(),TG("turn",12540),AR(),TG("accept",12570)],
        DO(12570),
    ])
    P(54.6,56.4,"雨声树屋","rainspeaker",[
        [NPC("高阶神谕者索乌塞"),AR(),TG("turn",12570),AR(),TG("accept",12571)],
        [NPC("拉弗乌"),AR(),TG("accept",12572)],
    ])
    P(52.0,56.0,"雨声树屋外圈","rainspeaker",[DO(12571,12572)])
    P(54.6,56.4,"雨声树屋","rainspeaker",[
        [NPC("高阶神谕者索乌塞"),AR(),TG("turn",12571,12572),AR(),TG("accept",12573)],
    ])
    P(51.3,64.6,"萨满祭司维克伊克","peace",[DO(12573)])
    P(50.5,62.1,"河流之心","rivers_heart",[
        [NPC("塔玛拉·摇链"),AR(),TG("turn",12654)],
    ])
    P(54.6,56.4,"雨声树屋","rainspeaker",[
        [NPC("高阶神谕者索乌塞"),AR(),TG("turn",12573),AR(),TG("accept",12574)],
    ])
    P(42.1,38.6,"雾语村","mistwhisper",[
        [NPC("唤雾者索乌甘"),AR(),TG("turn",12574),AR(),TG("accept",12575,12576)],
    ])


def g7_dorian_north() -> None:
    P(42.3,28.7,"多里安营地","dorian",[
        [NPC("多里安·达克斯托克"),AR(),TG("turn",12595),AR(),TG("accept",12603,12605)],
        [NPC("考尔文·诺灵顿"),AR(),TG("accept",12683)],
    ])
    P(48.0,27.5,"燃烧林地","burning_nest",[DO(12603,12605)])
    P(41.3,41.7,"苦潮湖·多头蛇","bittertide",[DO(12683)])
    P(42.3,28.7,"多里安营地","dorian",[
        [NPC("多里安·达克斯托克"),AR(),TG("turn",12603,12605)],
        [NPC("考尔文·诺灵顿"),AR(),TG("turn",12683)],
        [NPC("苏特菲兹"),AR(),TG("accept",12607,12658)],
        [NPC("考尔文·诺灵顿"),AR(),TG("accept",12681)],
    ])
    P(51.7,33.1,"裂牙猛犸区","mammoth",[DO(12607)])
    P(42.3,28.7,"多里安营地","dorian",[
        [NPC("苏特菲兹"),AR(),TG("turn",12607)],
        [NPC("多里安·达克斯托克"),AR(),TG("accept",12614)],
    ],notes=[(12607,"驯服最近的中立猛犸后直接送回营地并用载具技能交付；不要带着慢速猛犸绕路。")])
    P(41.5,21.5,"矛生营地","spearborn",[DO(12575,12576)])
    P(47.1,21.3,"母龙斯利维娜","north_hunt",[DO(12614)])
    P(56.8,26.5,"大鹏区","north_hunt",[DO(12658,12681)])
    P(42.3,28.7,"多里安营地","dorian",[
        [NPC("多里安·达克斯托克"),AR(),TG("turn",12614)],
        [NPC("苏特菲兹"),AR(),TG("turn",12658)],
        [NPC("考尔文·诺灵顿"),AR(),TG("turn",12681)],
    ])
    P(42.1,38.6,"雾语村","mistwhisper",[
        [NPC("唤雾者索乌甘"),AR(),TG("turn",12575,12576),AR(),TG("accept",12577)],
    ])
    P(54.6,56.4,"雨声树屋","rainspeaker",[
        [NPC("高阶神谕者索乌塞"),AR(),TG("turn",12577),AR(),TG("accept",12578)],
    ])


def g8_east_exit() -> None:
    P(75.5,52.5,"苔行村·莫乌德","mosswalker",[
        [NPC("莫乌德"),AR(),TG("turn",12578),AR(),TG("accept",12579,12580)],
    ])
    P(71.1,58.0,"苔行祭坛东侧","mosswalker",[DO(12579)])
    P(75.7,51.5,"苔行村东侧","mosswalker",[DO(12580)])
    P(80.4,55.8,"造物者悬台·古旧石箱","makers",[
        [NPC("古旧石箱"),AR(),TG("accept",12691)],
    ])
    P(81.3,54.0,"造物者悬台·索拉查卫士","makers",[DO(12691)])
    P(80.4,55.8,"造物者悬台·古旧石箱","makers",[
        [NPC("古旧石箱"),AR(),TG("turn",12691)],
    ])
    P(75.5,52.5,"苔行村·莫乌德","mosswalker",[
        [NPC("莫乌德"),AR(),TG("turn",12579,12580),AR(),TG("accept",12581)],
    ])
    P(72.1,57.6,"残忍的阿图里斯","artruis",[
        DO(12581),
        [NPC("阿图里斯的护命匣"),AR(),TG("turn",12581)],
        [NPC("亚鲁乌特"),AR(),TG("accept",12689),AR(),TG("turn",12689),AR(),TG("accept",12695)],
    ])
    P(54.6,56.4,"雨声树屋","rainspeaker",[
        [NPC("高阶神谕者索乌塞"),AR(),TG("turn",12695)],
    ])
    P(50.5,62.1,"河流之心 → 祖达克","exit",[
        [TAXI("河流之心","达拉然")],
        [TAXI("达拉然","龙眠神殿")],
    ],movement="taxi",notes=[(None,"龙眠神殿落地后沿龙骨东北道路到此前接《前往圣光据点！》的北伐军战士瓦鲁斯处，继续沿道路进入祖达克；到圣光据点找莉安娜中士交任务。")])

GROUPS = [
    ("入图 → 奈辛瓦里 → 挖掘场", "从达拉然脚本进入索拉查，绑定奈辛瓦里炉石；完成飞行器、挖掘场零件/击杀/戒指/护送，开营地飞行点后再回挖掘场杀工头。", g1_entry_engineering, 24, 16, 38),
    ("初阶狩猎 → 诺兹隆之骨", "完成犀牛和恶刃豹初阶狩猎；继续做诺兹隆、鳄鱼、酿酒材料和猎豹足迹，回奈辛瓦里交接。", g2_hunts_nozzlerust, 24, 17, 34),
    ("终极狩猎 → 河流之心 → 匹奇", "依次完成沙蕨、法鲁恩和杉苟后炉石回营；随后做鳄鱼伏击，开河流之心飞行点，完成维克任务并杀匹奇进入狂心岭。", g3_final_hunts_river, 21, 14, 31),
    ("狂心岭 → 硬皮猩猩 → 蓝玉虫巢", "从狂心岭连续推进硬皮猩猩、蓝玉虫巢、抓鸡和南部任务，最后乘被俘鳄鱼进入雾语村。", g4_frenzyheart, 24, 16, 36),
    ("雾语村 → 炉石奈辛瓦里 → 狂心岭", "完成第一轮雾语村任务后炉石回营集中交鳄鱼与品酒，接《更大的猎物》，再回狂心岭切入神谕者线。", g5_mistwhisper_hearth, 14, 9, 21),
    ("雨声树屋 → 河流之心 → 雾语村", "护送受伤神谕者，完成坏蛇、亮闪闪宝物和议和；经过河流之心顺交塔玛拉任务，再回雾语村接北部任务。", g6_oracle, 19, 13, 29),
    ("多里安营地 → 苦潮湖 → 北部猎场", "先完成始祖龙/幼崽和苦潮多头蛇；回多里安后就近送回猛犸，再去矛生营地、母龙和大鹏区域，最后回雨声树屋。", g7_dorian_north, 27, 18, 42),
    ("苔行村 → 造物者悬台 → 阿图里斯", "完成苔行村东部任务和造物者悬台；回莫乌德接《英雄的负担》后立即去阿图里斯，选择神谕者并回雨声树屋，最后从河流之心转场祖达克。", g8_east_exit, 22, 14, 34),
]

for title, summary, fn, center, lo, hi in GROUPS:
    G(title, summary, fn, center, lo, hi)

missing = sorted(FORMAL - covered)
unexpected = sorted(covered - FORMAL)

route = {
    "order": 8,
    "uiStandard": "semantic-hud-v45",
    "title": "索拉查盆地 · 80级五开整图路线",
    "sub": "达拉然脚本入图后，以奈辛瓦里营地为前半段炉石Hub，依次完成狩猎、狂心/神谕者转换、多里安北部与阿图里斯线；最终固定选择神谕者，并从河流之心转场祖达克。",
    "badge": "炉石：奈辛瓦里营地\n最终阵营：神谕者\n预计总时间：首轮约2小时55分",
    "image": "maps/3711-sholazar-basin-hd.jpg",
    "legend": "",
    "footer": "",
    "labels": [
        [27.1,58.6,"奈辛瓦里营地"], [35.5,47.4,"斯温迪格林挖掘场"], [25.6,66.5,"诺兹隆之骨"],
        [50.5,62.1,"河流之心"], [55.0,69.1,"狂心岭"], [42.1,38.6,"雾语村"],
        [54.6,56.4,"雨声树屋"], [42.3,28.7,"多里安营地"], [75.5,52.5,"苔行村"], [72.1,57.6,"残忍的阿图里斯"],
    ],
    "points": points,
    "defaultIndex": 0,
    "phaseColors": {
        "entry":"#93c5fd", "camp":"#fde68a", "engineering":"#fdba74", "dig":"#fdba74",
        "hunt":"#86efac", "nozzlerust":"#86efac", "central":"#86efac", "tracks":"#86efac", "final_hunt":"#a7f3d0",
        "river":"#67e8f9", "rivers_heart":"#67e8f9", "pitch":"#fca5a5", "frenzyheart":"#fca5a5", "hardknuckle":"#fca5a5",
        "sapphire":"#fca5a5", "frenzyheart_south":"#fca5a5", "transport":"#c4b5fd", "mistwhisper":"#c4b5fd",
        "oracle":"#a7f3d0", "rainspeaker":"#a7f3d0", "peace":"#a7f3d0", "dorian":"#fdba74", "burning_nest":"#fdba74",
        "bittertide":"#fdba74", "mammoth":"#fdba74", "spearborn":"#fdba74", "north_hunt":"#fdba74", "mosswalker":"#86efac",
        "makers":"#d1d5db", "artruis":"#fca5a5", "exit":"#93c5fd",
    },
    "displayName": "索拉查盆地",
    "stepGroups": step_groups,
    "defaultGroupIndex": 0,
    "hearthChain": ["奈辛瓦里营地"],
    "timing": {
        "centerMinutes": sum(float(g["timing"]["centerMinutes"]) for g in step_groups),
        "rangeMinutes": [
            sum(float(g["timing"]["rangeMinutes"][0]) for g in step_groups),
            sum(float(g["timing"]["rangeMinutes"][1]) for g in step_groups),
        ],
        "actualRuns": [],
        "model": "sholazar_initial_clean_baseline_pre_live_calibration",
    },
}

routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
routes["sholazar"] = route
if "zuldrak" in routes:
    routes["zuldrak"]["order"] = 9
if "grizzly" in routes:
    routes["grizzly"]["order"] = 10
routes = dict(sorted(routes.items(), key=lambda kv: (int(kv[1].get("order", 999)), kv[0])))
WORKBENCH.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

transition = json.loads(TRANSITION_AUDIT.read_text(encoding="utf-8"))
merge = json.loads(MERGE_AUDIT.read_text(encoding="utf-8"))
coverage = {
    "status": "formal_sholazar_full_clear_initial_route_pre_live_fivebox_calibration",
    "formal_task_count": len(FORMAL),
    "covered_task_count": len(covered & FORMAL),
    "missing": missing,
    "unexpected": unexpected,
    "point_count": len(points),
    "step_group_count": len(step_groups),
    "opened_flight_points_final": sorted(opened_flight_points),
    "system_flight_audit": flight_path_audit,
    "transition_status": transition.get("status"),
    "merge_status": merge.get("status"),
    "harmful_split_count": merge.get("harmful_split_count"),
    "fivebox_policy": "未知五开机制保留待实测标记，不阻塞当前路线；首跑反馈只打开对应任务簇窗口。",
}
COVERAGE_OUT.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PLAYER_GROUPS_OUT.write_text(json.dumps({
    "zone": "索拉查盆地",
    "pointCount": len(points),
    "groupCount": len(step_groups),
    "groups": [
        {"title": g["title"], "summary": g["summary"], "pointCount": g["end"] - g["start"] + 1, "timing": g["timing"]}
        for g in step_groups
    ],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps(coverage, ensure_ascii=False, indent=2))
if missing or unexpected:
    raise SystemExit(2)
