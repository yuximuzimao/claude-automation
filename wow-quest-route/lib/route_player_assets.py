from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .route_dependencies import ROOT, canonical_json_hash


WORKBENCH_NAME = "route-atlas-workbench.html"
PLAYER_VIEW_DIRNAME = "player-view"


class PlayerAssetsError(ValueError):
    """Raised when Stage 13 player assets cannot be rendered safely."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(row.get("severity") == "error" for row in issues):
        return "blocked"
    if any(row.get("severity") in {"requirement", "unknown"} for row in issues):
        return "requirements"
    return "pass"


def _validate_payload(payload: dict[str, Any]) -> None:
    if payload.get("kind") != "publisher_payload":
        raise PlayerAssetsError("Stage 13 requires Stage 12 publisher_payload input")
    if payload.get("status") not in {"pass", "requirements", "blocked"}:
        raise PlayerAssetsError(f"unsupported Publisher status: {payload.get('status')!r}")
    if not isinstance(payload.get("profile_id"), str) or not payload["profile_id"]:
        raise PlayerAssetsError("publisher profile_id missing")
    if not isinstance(payload.get("profile_version"), int):
        raise PlayerAssetsError("publisher profile_version missing")
    if not isinstance(payload.get("input_fingerprint"), str) or not payload["input_fingerprint"]:
        raise PlayerAssetsError("publisher input_fingerprint missing")
    display = payload.get("display")
    route_map = payload.get("map")
    if not isinstance(display, dict) or not isinstance(display.get("publish_key"), str) or not display["publish_key"]:
        raise PlayerAssetsError("publisher display.publish_key missing")
    if not isinstance(route_map, dict) or not isinstance(route_map.get("geometry"), dict):
        raise PlayerAssetsError("publisher map.geometry missing")
    geometry = route_map["geometry"]
    if not isinstance(geometry.get("visits"), list) or not isinstance(geometry.get("edges"), list):
        raise PlayerAssetsError("publisher map.geometry visits/edges invalid")
    if not isinstance(payload.get("steps"), list) or not payload["steps"]:
        raise PlayerAssetsError("publisher steps missing")
    if not isinstance(payload.get("hearth_chain"), list):
        raise PlayerAssetsError("publisher hearth_chain missing")


def _format_minutes(value: Any) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    return f"{float(value):g}分钟"


def _presentation_badge(row: dict[str, Any]) -> str:
    badge = row.get("badge")
    if badge == "shared":
        return "共享"
    if badge == "not_shared":
        return "不共享"
    if badge == "sequential_loot":
        return "依次拾取"
    if badge == "special":
        return "特殊"
    if row.get("pending"):
        return "待实测"
    return ""


def _decorate_line_with_badges(
    line: dict[str, Any],
    presentations_by_task: dict[int, dict[str, Any]],
) -> str:
    text = str(line.get("text") or "").strip()
    if not text:
        return ""
    cursor = 0
    for ref in line.get("task_refs") or []:
        task_id = ref.get("task_id")
        name = str(ref.get("name") or "")
        if not isinstance(task_id, int) or not name:
            continue
        needle = f"《{name}》"
        at = text.find(needle, cursor)
        if at < 0:
            continue
        badge = _presentation_badge(presentations_by_task.get(task_id) or {})
        if badge:
            prefix = f"【{badge}】"
            text = text[:at] + prefix + text[at:]
            cursor = at + len(prefix) + len(needle)
        else:
            cursor = at + len(needle)
    return text


def render_player_view(payload: dict[str, Any]) -> str:
    """Render a cold-read player view directly from one Stage 12 payload."""
    _validate_payload(payload)
    display = payload["display"]
    timing = payload.get("route_timing") or {}
    hearth_chain = payload.get("hearth_chain") or []
    lines = [f"# {display.get('title') or display.get('display_name') or payload['profile_id']}"]
    subtitle = str(display.get("subtitle") or "").strip()
    if subtitle:
        lines.extend(["", subtitle])
    status_bits: list[str] = []
    if hearth_chain:
        status_bits.append("炉石：" + " → ".join(str(value) for value in hearth_chain))
    route_minutes = _format_minutes(timing.get("center_minutes"))
    if route_minutes:
        status_bits.append("预计总时间：" + route_minutes)
    route_range = timing.get("range_minutes")
    if isinstance(route_range, list) and len(route_range) == 2 and all(isinstance(value, (int, float)) for value in route_range):
        status_bits.append(f"预计范围：{float(route_range[0]):g}–{float(route_range[1]):g}分钟")
    if status_bits:
        lines.extend(["", "｜".join(status_bits)])

    for index, step in enumerate(payload["steps"], 1):
        lines.extend(["", f"## 步骤 {index}｜{step['title']}"])
        summary = str(step.get("summary") or "").strip()
        if summary:
            lines.append(summary)
        step_minutes = _format_minutes((step.get("timing") or {}).get("center_minutes"))
        if step_minutes:
            lines.append("本段预计：" + step_minutes)
        presentations = step.get("task_presentations") or []
        presentations_by_task = {
            int(row["task_id"]): row
            for row in presentations
            if isinstance(row.get("task_id"), int)
        }
        for line in step.get("lines") or []:
            text = _decorate_line_with_badges(line, presentations_by_task)
            if text:
                lines.append("- " + text)
        visible_notes = [
            row
            for row in presentations
            if row.get("note_visible") is not False and str(row.get("note") or "").strip()
        ]
        if visible_notes:
            lines.append("备注：")
            for row in visible_notes:
                note = str(row.get("note") or "").strip()
                lines.append(f"- 《{row.get('name') or row.get('task_id')}》：" + note)
    footer = str(display.get("footer") or "").strip()
    if footer:
        lines.extend(["", footer])
    return "\n".join(lines).rstrip() + "\n"


def _html_shell(payload_json: str) -> str:
    # The runtime is intentionally dependency-free. All business/display data is embedded from Stage 12.
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>魔兽世界五开打金任务路线</title>
<style>
:root{color-scheme:dark;background:#111;color:#eee;font-family:-apple-system,"system-ui","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
*{box-sizing:border-box}body{margin:0;background:#111;color:#eee}.app{max-width:1600px;margin:0 auto;padding:14px}
.pageTitle{margin:0 0 10px;font-size:22px;line-height:1.25;font-weight:800;color:#f4f6f8}.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.top select,.top button{background:#20242a;color:#eee;border:1px solid #454b54;border-radius:6px;padding:7px 10px}
.status{margin-left:auto;white-space:pre-line;color:#ddd}.mapCard{position:relative;background:#080a0d;border:1px solid #343942;border-radius:10px;overflow:hidden;min-height:420px}
.mapWrap{position:relative;width:100%;aspect-ratio:16/9;overflow:hidden}.mapWrap img{position:absolute;inset:0;width:100%;height:100%;object-fit:fill}.mapWrap svg{position:absolute;inset:0;width:100%;height:100%}.mapLabels{position:absolute;inset:0;pointer-events:none;overflow:hidden}.mapLabel{position:absolute;transform:translate(-50%,-50%);white-space:nowrap;pointer-events:none;font-family:-apple-system,"system-ui","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:11px;font-weight:400;line-height:18px;color:rgb(247,239,216);background:rgba(6,12,18,.62);border-radius:4px;padding:2px 5px;text-shadow:0 1px 2px rgb(0,0,0)}
.edge{stroke:#97a0ad;stroke-width:.35;fill:none;opacity:.72}.edge.current{stroke-width:.9;opacity:1}.visit{fill:#fff;stroke:#111;stroke-width:.25}.visit.current{r:1.1}
.hud{position:absolute;left:12px;top:12px;width:min(590px,calc(100% - 24px));max-height:calc(100% - 24px);background:rgba(10,12,15,.91);border:1px solid rgba(255,255,255,.22);border-radius:9px;overflow:hidden;display:flex;flex-direction:column}.hud.collapsed .hudBody{display:none}.hud.collapsed .hudHead{border-bottom:0}.hudHead{display:flex;align-items:stretch;padding:0;border-bottom:1px solid rgba(255,255,255,.14)}.hudTitleBlock{display:flex;align-items:center;flex-wrap:wrap;flex:1;min-width:0;padding:10px 12px}.hudTitle{font-size:15px;font-weight:800}.hudTime{margin-left:8px;color:rgb(145,164,184);font-size:12px;font-weight:400;white-space:nowrap}.hudToggle{font:12px Arial;color:rgb(145,164,184);background:rgb(23,36,49);border:0;border-left:1px solid rgba(255,255,255,.12);border-radius:0 8px 0 0;padding:3px 7px;min-width:56px;cursor:pointer}.hudToggle:hover{color:#dbe6f1;background:#203246}.hudBody{padding:10px 12px;overflow:auto;font-size:14px}.line{margin:4px 0;line-height:1.55}.location{color:#9fcff5}.task.accept{color:#ffd66b}.task.objective{color:#79baff}.task.turnin{color:#82d59a;text-decoration:underline}.routeAction.open_flight_point{color:#ff9f68}.routeAction.bind_hearth{color:#cf9cff}.notes{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.16)}.notesTitle{margin:0 0 5px;font-weight:800;color:#f0f0f0}.note{margin:5px 0;color:#ddd;white-space:pre-line}.tag{display:inline-block;margin-right:5px;padding:1px 5px;border-radius:4px;background:#333;font-size:.8em;font-weight:700}.sharedTag{background:#0369a1;color:#fff;border:1px solid #38bdf8}.notSharedTag{background:#7c3aed;color:#fff;border:1px solid #c084fc}.pendingTag{background:#a62533;color:#fff;border:1px solid #dc4b5b}
.steps{margin-top:12px;border:1px solid #343942;border-radius:10px;overflow:hidden}.step{padding:10px 12px;border-top:1px solid #2b3037;cursor:pointer}.step:first-child{border-top:0}.step.active{background:#1c222a}.stepTitle{font-weight:800}.stepSummary{color:#aaa;margin-top:3px}.small{color:#aaa;font-size:.9em}
</style>
</head>
<body><div class="app">
<h1 class="pageTitle">魔兽世界五开打金任务路线</h1>
<div class="top"><select id="routeSelect"></select><button id="prev">上一段</button><button id="next">下一段</button><button id="playCurrent">播放当前段</button><button id="playRemaining">播放剩余路线</button><div id="status" class="status"></div></div>
<div class="mapCard"><div id="mapWrap" class="mapWrap"><img id="mapImg" alt="路线地图"><svg id="mapSvg" viewBox="0 0 100 100" preserveAspectRatio="none"></svg><div id="mapLabels" class="mapLabels"></div></div><section id="hud" class="hud"><div class="hudHead"><div class="hudTitleBlock"><span id="hudTitle" class="hudTitle"></span><span id="hudTime" class="hudTime"></span></div><button id="collapse" class="hudToggle">收起 ▲</button></div><div id="hudBody" class="hudBody"></div></section></div>
<div id="steps" class="steps"></div>
</div>
<script>
const ROUTES=__PAYLOAD__;
const LAST_ROUTE_KEY='route-atlas:last-route',STEP_PREFIX='route-atlas:last-step:',PLAY_EDGE_MS=1400,PLAY_JUMP_MS=850,PLAY_RATE=1.8;
let routeIndex=0,stepIndex=0,playMode='',raf=0,playLast=0,playEdgeIndex=0,playProgress=0,playEdges=[];
const $=id=>document.getElementById(id); const route=()=>ROUTES[routeIndex];
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function fmtMin(v){return typeof v==='number'?`${v}分钟`:''}
function fmtStepTiming(t){const c=t?.center_minutes,r=t?.range_minutes;if(typeof c!=='number')return'本段预计：—';if(Array.isArray(r)&&r.length===2&&typeof r[0]==='number'&&typeof r[1]==='number')return`本段预计：约${c}分钟（${r[0]}分钟—${r[1]}分钟）`;return`本段预计：约${c}分钟`}
function badgeText(p){if(p.badge==='shared')return'共享';if(p.badge==='not_shared')return'不共享';if(p.badge==='sequential_loot')return'依次拾取';if(p.badge==='special')return'特殊';if(p.pending)return'待实测';return''}
function visibleTaskKind(segment){const m=String(segment||'').match(/(?:^|→|↳| )(接|做|交) *$/);return m?({接:'accept',做:'objective',交:'turnin'})[m[1]]:''}
function renderLine(parent,line,presentationByTask){const row=el('div','line');let text=String(line.text||'');const refs=[...(line.task_refs||[])];if(line.type==='location'){row.classList.add('location');row.textContent=text;parent.appendChild(row);return}if(line.type==='route_action'&&line.action_kind)row.classList.add('routeAction',String(line.action_kind));
let cursor=0;const tokens=refs.map((r,i)=>({needle:`《${r.name}》`,ref:r,index:i})).filter(x=>x.needle.length>2);const used=new Set();while(cursor<text.length){let at=-1,candidates=[];for(const token of tokens){if(used.has(token.index))continue;const pos=text.indexOf(token.needle,cursor);if(pos<0)continue;if(at<0||pos<at){at=pos;candidates=[token]}else if(pos===at)candidates.push(token)}if(at<0){row.appendChild(document.createTextNode(text.slice(cursor)));break}const before=text.slice(cursor,at);if(before)row.appendChild(document.createTextNode(before));const inferred=visibleTaskKind(before);const best=candidates.find(token=>token.ref.kind===inferred)||candidates[0];const p=presentationByTask.get(String(best.ref.task_id));const tag=badgeText(p||{});if(tag){const tagClass=tag==='待实测'?'tag taskTag pendingTag':tag==='共享'?'tag taskTag sharedTag':tag==='不共享'?'tag taskTag notSharedTag':'tag taskTag';row.appendChild(el('span',tagClass,tag))}row.appendChild(el('span',`task ${best.ref.kind}`,best.needle));used.add(best.index);cursor=at+best.needle.length}parent.appendChild(row)}
function renderHud(){const r=route(),s=r.steps[stepIndex],presentations=s.task_presentations||[],presentationByTask=new Map(presentations.map(p=>[String(p.task_id),p]));$('hudTitle').textContent=`步骤 ${stepIndex+1}/${r.steps.length} · ${s.title}`;$('hudTime').textContent=fmtStepTiming(s.timing||{});const body=$('hudBody');body.innerHTML='';for(const line of s.lines||[])renderLine(body,line,presentationByTask);const notes=presentations.filter(p=>p.note_visible!==false&&String(p.note||'').trim());if(notes.length){const box=el('div','notes');box.appendChild(el('div','notesTitle','备注'));for(const p of notes){const row=el('div','note');row.appendChild(document.createTextNode(`《${p.name||p.task_id}》：${String(p.note||'').trim()}`));box.appendChild(row)}body.appendChild(box)}}
function edgeStep(edge,visits){const to=visits.get(edge.to_visit_id),from=visits.get(edge.from_visit_id);return (to&&to.step_id)||(from&&from.step_id)||''}
function positioned(v){return !!v&&typeof v.x==='number'&&Number.isFinite(v.x)&&typeof v.y==='number'&&Number.isFinite(v.y)}
function renderMap(){const r=route(),g=r.map.geometry,svg=$('mapSvg'),labelBox=$('mapLabels');$('mapImg').src=r.map.image;svg.innerHTML='';labelBox.innerHTML='';const visits=new Map((g.visits||[]).map(v=>[v.visit_id,v]));const active=r.steps[stepIndex].step_id;for(const e of g.edges||[]){const a=visits.get(e.from_visit_id),b=visits.get(e.to_visit_id);if(!positioned(a)||!positioned(b))continue;const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);line.setAttribute('class','edge '+(edgeStep(e,visits)===active?'current':''));svg.appendChild(line)}for(const v of g.visits||[]){if(!positioned(v))continue;const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('cx',v.x);c.setAttribute('cy',v.y);c.setAttribute('r',v.step_id===active?1.1:.65);c.setAttribute('class','visit '+(v.step_id===active?'current':''));svg.appendChild(c)}for(const l of r.map.labels||[]){const t=el('span','mapLabel',l.display_name);t.style.left=`${l.x}%`;t.style.top=`${l.y}%`;labelBox.appendChild(t)}const m=document.createElementNS('http://www.w3.org/2000/svg','circle');m.setAttribute('id','mover');m.setAttribute('r','.85');m.setAttribute('fill','#fff');m.setAttribute('stroke','#111');m.setAttribute('stroke-width','.25');m.style.display='none';svg.appendChild(m)}
function renderSteps(){const r=route(),box=$('steps');box.innerHTML='';r.steps.forEach((s,i)=>{const row=el('div','step'+(i===stepIndex?' active':''));row.onclick=()=>setStep(i);row.appendChild(el('div','stepTitle',`${i+1}. ${s.title}`));if(s.summary)row.appendChild(el('div','stepSummary',s.summary));box.appendChild(row)})}
function renderStatus(){const r=route(),bits=[];if((r.hearth_chain||[]).length)bits.push('炉石：'+r.hearth_chain.join(' → '));const t=r.route_timing||{};if(typeof t.center_minutes==='number')bits.push('预计总时间：'+fmtMin(t.center_minutes));$('status').textContent=bits.join('\\n')}
function routeKey(r=route()){return r?.display?.publish_key||r?.profile_id||String(routeIndex)}
function savedStep(key){try{const v=Number.parseInt(localStorage.getItem(STEP_PREFIX+key)||'',10);return Number.isInteger(v)?v:null}catch(_){return null}}
function savedRouteIndex(){try{const key=localStorage.getItem(LAST_ROUTE_KEY)||'';const i=ROUTES.findIndex(r=>routeKey(r)===key);return i>=0?i:0}catch(_){return 0}}
function saveResume(){try{const key=routeKey();localStorage.setItem(LAST_ROUTE_KEY,key);localStorage.setItem(STEP_PREFIX+key,String(stepIndex))}catch(_){}}
function mover(){return $('mapSvg').querySelector('#mover')}
function positionMover(x,y,visible=true){const m=mover();if(!m)return;m.setAttribute('cx',x);m.setAttribute('cy',y);m.style.display=visible?'':'none'}
function currentStepEdges(){const r=route(),g=r.map.geometry,visits=new Map((g.visits||[]).map(v=>[v.visit_id,v])),sid=r.steps[stepIndex].step_id;return (g.edges||[]).map(edge=>({edge,a:visits.get(edge.from_visit_id),b:visits.get(edge.to_visit_id)})).filter(x=>edgeStep(x.edge,visits)===sid&&positioned(x.a)&&positioned(x.b))}
function stopPlayback(){if(raf)cancelAnimationFrame(raf);raf=0;playMode='';playLast=0;playEdgeIndex=0;playProgress=0;playEdges=[];const m=mover();if(m)m.style.display='none';$('playCurrent').textContent='播放当前段';$('playRemaining').textContent='播放剩余路线'}
function applyStep(i){const n=route().steps.length;stepIndex=Math.max(0,Math.min(n-1,i));renderHud();renderMap();renderSteps();saveResume()}
function setStep(i){stopPlayback();applyStep(i)}
function setRoute(i){stopPlayback();routeIndex=Math.max(0,Math.min(ROUTES.length-1,i));const r=route();$('routeSelect').value=String(routeIndex);$('mapSvg').setAttribute('viewBox','0 0 100 100');renderStatus();const remembered=savedStep(routeKey(r));applyStep(remembered===null?0:remembered)}
function preparePlaybackStep(){playEdges=currentStepEdges();playEdgeIndex=0;playProgress=0;playLast=0;if(!playEdges.length)return false;const first=playEdges[0];positionMover(first.a.x,first.a.y,true);return true}
function advancePlayback(){if(playMode==='current'){stopPlayback();return}if(stepIndex>=route().steps.length-1){stopPlayback();return}applyStep(stepIndex+1);if(!preparePlaybackStep()){advancePlayback();return}raf=requestAnimationFrame(playTick)}
function playTick(t){if(!playMode)return;if(!playLast)playLast=t;const dt=t-playLast;playLast=t;const item=playEdges[playEdgeIndex];if(!item){advancePlayback();return}const jump=['hearth','fixed_transport','quest_transport'].includes(item.edge.operation_kind),dur=jump?PLAY_JUMP_MS:PLAY_EDGE_MS;playProgress=Math.min(1,playProgress+(dt*PLAY_RATE)/dur);const u=jump?(playProgress<.58?0:1):playProgress;positionMover(item.a.x+(item.b.x-item.a.x)*u,item.a.y+(item.b.y-item.a.y)*u,true);if(playProgress>=1){positionMover(item.b.x,item.b.y,true);if(playEdgeIndex<playEdges.length-1){playEdgeIndex++;playProgress=0;playLast=t}else{advancePlayback();return}}raf=requestAnimationFrame(playTick)}
function startPlayback(mode){stopPlayback();playMode=mode;$('playCurrent').textContent=mode==='current'?'暂停当前段':'播放当前段';$('playRemaining').textContent=mode==='remaining'?'暂停剩余路线':'播放剩余路线';if(!preparePlaybackStep()){advancePlayback();return}raf=requestAnimationFrame(playTick)}
function togglePlayback(mode){if(playMode===mode){stopPlayback();return}startPlayback(mode)}
function toggleHud(){const hud=$('hud'),collapsed=hud.classList.toggle('collapsed');$('collapse').textContent=collapsed?'展开 ▼':'收起 ▲'}
function init(){ROUTES.forEach((r,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=r.display.display_name||r.display.title||r.profile_id;$('routeSelect').appendChild(o)});$('routeSelect').onchange=e=>setRoute(Number(e.target.value));$('prev').onclick=()=>setStep(stepIndex-1);$('next').onclick=()=>setStep(stepIndex+1);$('playCurrent').onclick=()=>togglePlayback('current');$('playRemaining').onclick=()=>togglePlayback('remaining');$('collapse').onclick=toggleHud;setRoute(savedRouteIndex())}
init();
</script></body></html>""".replace("__PAYLOAD__", payload_json)


def render_workbench_html(payloads: list[dict[str, Any]]) -> str:
    if not payloads:
        raise PlayerAssetsError("no Publisher payloads supplied")
    seen_publish_keys: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for payload in payloads:
        _validate_payload(payload)
        publish_key = str(payload["display"]["publish_key"])
        if publish_key in seen_publish_keys:
            raise PlayerAssetsError(f"duplicate publish_key: {publish_key}")
        seen_publish_keys.add(publish_key)
        ordered.append(payload)
    ordered.sort(key=lambda row: (int((row.get("display") or {}).get("order") or 0), str(row["display"]["publish_key"])))
    payload_json = json.dumps(ordered, ensure_ascii=False, separators=(",", ":")).replace("</script", "<\\/script")
    html = _html_shell(payload_json)
    lowered = html.lower()
    network_load_tokens = (
        'src="http://', 'src="https://', "src='http://", "src='https://",
        'href="http://', 'href="https://', "href='http://", "href='https://",
        "url(http://", "url(https://", "fetch(\"http://", "fetch(\"https://",
        "fetch('http://", "fetch('https://",
    )
    if any(token in lowered for token in network_load_tokens):
        raise PlayerAssetsError("Stage 13 workbench must be fully offline")
    return html


def evaluate_player_assets(
    payloads: list[dict[str, Any]],
    *,
    routes_root: Path | None = None,
) -> dict[str, Any]:
    if not payloads:
        raise PlayerAssetsError("no Publisher payloads supplied")
    routes_root = routes_root or (ROOT / "data/routes")
    issues: list[dict[str, Any]] = []
    publish_keys: set[str] = set()
    referenced_assets: list[str] = []
    player_views: dict[str, str] = {}
    for payload in payloads:
        _validate_payload(payload)
        publish_key = str(payload["display"]["publish_key"])
        if publish_key in publish_keys:
            issues.append(_issue("error", "player_assets_duplicate_publish_key", publish_key=publish_key))
        publish_keys.add(publish_key)
        if payload["status"] == "blocked" or payload.get("publishable") is False:
            issues.append(_issue("error", "player_assets_publisher_blocked", publish_key=publish_key))
        elif payload["status"] == "requirements":
            issues.append(_issue("requirement", "player_assets_publisher_requirements", publish_key=publish_key))
        image = str((payload.get("map") or {}).get("image") or "")
        if not image.startswith("maps/"):
            issues.append(_issue("error", "player_assets_map_path_invalid", publish_key=publish_key, image=image))
        else:
            referenced_assets.append(image)
            if not (routes_root / image).exists():
                issues.append(_issue("error", "player_assets_map_missing", publish_key=publish_key, image=image))
        player_views[publish_key] = render_player_view(payload)

    html = render_workbench_html(payloads)
    html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
    status = _status(issues)
    input_fingerprint = canonical_json_hash(
        {
            "publisher_fingerprints": [payload["input_fingerprint"] for payload in payloads],
            "referenced_assets": referenced_assets,
        }
    )
    return {
        "kind": "player_assets",
        "status": status,
        "publishable": status == "pass" and all(payload.get("publishable") is True for payload in payloads),
        "input_fingerprint": input_fingerprint,
        "publisher_fingerprints": [payload["input_fingerprint"] for payload in payloads],
        "profile_count": len(payloads),
        "publish_keys": sorted(publish_keys),
        "workbench_name": WORKBENCH_NAME,
        "workbench_bytes": len(html.encode("utf-8")),
        "workbench_sha256": html_sha256,
        "player_views": player_views,
        "referenced_assets": sorted(set(referenced_assets)),
        "issues": issues,
    }


def write_player_assets(
    payloads: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir or (ROOT / "data/routes")
    report = evaluate_player_assets(payloads, routes_root=output_dir)
    if report["publishable"] is not True:
        raise PlayerAssetsError("refusing to write Stage 13 assets from non-publishable Publisher payloads")
    html = render_workbench_html(payloads)
    output_dir.mkdir(parents=True, exist_ok=True)
    workbench = output_dir / WORKBENCH_NAME
    workbench.write_text(html, encoding="utf-8")
    player_dir = output_dir / PLAYER_VIEW_DIRNAME
    player_dir.mkdir(parents=True, exist_ok=True)
    for publish_key, text in report["player_views"].items():
        (player_dir / f"{publish_key}.md").write_text(text, encoding="utf-8")
    return {
        **report,
        "workbench_path": str(workbench),
        "player_view_dir": str(player_dir),
    }
