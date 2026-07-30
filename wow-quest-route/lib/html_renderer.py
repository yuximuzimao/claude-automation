from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_html(route: dict[str, Any], journey: dict[str, Any] | None = None) -> str:
    route_json = _json_for_script(route)
    journey_json = _json_for_script(journey or {})
    title = html.escape(route["title"])
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#0d1117;--panel:#151b23;--panel2:#1b2430;--line:#334155;--text:#e6edf3;--muted:#94a3b8;--accent:#f59e0b;--cyan:#22d3ee;--green:#34d399;--red:#fb7185;--violet:#a78bfa}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;overflow:hidden}}
header{{height:64px;display:flex;align-items:center;gap:18px;padding:10px 18px;border-bottom:1px solid #253142;background:#10161e}}
header h1{{font-size:18px;margin:0;white-space:nowrap}} .subtitle{{color:var(--muted);font-size:12px}}
.controls{{margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap}} button,.file-label{{border:1px solid #3a4758;background:#1b2531;color:var(--text);border-radius:8px;padding:7px 10px;cursor:pointer}} button:hover,.file-label:hover{{border-color:var(--cyan)}} input[type=file]{{display:none}} input[type=range]{{width:90px}}
.layout{{height:calc(100vh - 64px);display:grid;grid-template-columns:290px minmax(480px,1fr) 340px;gap:1px;background:#253142}}
.panel{{background:var(--panel);min-height:0;overflow:auto}} .panel-title{{position:sticky;top:0;z-index:5;background:#151b23ee;backdrop-filter:blur(8px);padding:12px 14px;border-bottom:1px solid #253142;font-weight:700}}
#segments{{padding:10px 10px 2px;display:flex;flex-direction:column;gap:6px}} .segment-btn{{text-align:left;padding:9px;border-radius:9px;background:#101820}} .segment-btn.active{{border-color:var(--cyan);background:#10242b}} .segment-btn strong{{display:block}} .segment-btn small{{display:block;color:var(--muted);margin-top:2px}} #steps{{padding:8px 10px 10px}} .step-card{{border:1px solid #2c3949;background:#121922;border-radius:10px;padding:10px;margin-bottom:8px;cursor:pointer;transition:.15s}} .step-card:hover{{border-color:#52657a}} .step-card.active{{border-color:var(--accent);box-shadow:0 0 0 1px #f59e0b44;background:#211b12}} .step-head{{display:flex;gap:8px;align-items:center}} .step-num{{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:#334155;font-weight:800;font-size:12px}} .step-card.active .step-num{{background:var(--accent);color:#111827}} .step-action{{font-weight:700}} .step-quests{{color:var(--muted);font-size:12px;margin-top:5px}}
.center{{display:grid;grid-template-rows:minmax(430px,62%) minmax(220px,38%);min-height:0;background:#0b1017}} .map-wrap{{position:relative;min-height:0;overflow:hidden}} #map{{width:100%;height:100%;display:block;background:radial-gradient(circle at 55% 30%,#17303a 0,#111923 45%,#0b1017 100%)}} .map-help{{position:absolute;left:12px;bottom:10px;background:#071018dd;border:1px solid #334155;border-radius:8px;padding:7px 9px;color:var(--muted);font-size:12px;pointer-events:none}} .legend{{position:absolute;right:12px;top:10px;background:#071018dd;border:1px solid #334155;border-radius:8px;padding:8px;font-size:12px}} .legend span{{display:block;margin:3px 0}} .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}}
.tabs{{display:grid;grid-template-rows:42px 1fr;min-height:0;border-top:1px solid #253142;background:#10161e}} .tabbar{{display:flex;border-bottom:1px solid #253142}} .tabbar button{{border:0;border-radius:0;background:transparent;color:var(--muted);padding:10px 16px}} .tabbar button.active{{color:var(--text);border-bottom:2px solid var(--accent)}} .tab-content{{min-height:0;overflow:auto;padding:12px}} #chainSvg{{width:100%;min-width:760px;height:100%;min-height:190px;background:#0d141d;border-radius:8px}}
.detail{{padding:14px}} .badge{{display:inline-block;border:1px solid #405066;border-radius:99px;padding:3px 8px;margin:0 5px 5px 0;color:#cbd5e1;font-size:12px}} .badge.confirmed{{border-color:#237c61;color:#6ee7b7}} .badge.partial{{border-color:#986b20;color:#fbbf24}} .badge.pending{{border-color:#7c3f55;color:#fda4af}} .detail h2{{font-size:18px;margin:5px 0 10px}} .detail h3{{font-size:14px;color:#cbd5e1;margin:18px 0 7px}} .instruction{{background:#101820;border-left:3px solid var(--accent);padding:10px;border-radius:4px}} .entity{{border-top:1px solid #283647;padding:9px 0}} .entity small{{color:var(--muted)}} .quest{{padding:8px;border:1px solid #2d3a49;border-radius:8px;margin:6px 0}} .quest-id{{color:var(--cyan);font-family:ui-monospace,monospace}}
.summary-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}} .summary{{background:#101820;border:1px solid #2c3949;border-radius:8px;padding:9px}} .summary strong{{font-size:18px;display:block}} .timeline{{display:flex;flex-direction:column;gap:6px}} .event{{display:grid;grid-template-columns:66px 72px 1fr 48px;gap:8px;align-items:center;padding:7px 8px;border:1px solid #293646;border-radius:7px;background:#111923}} .event.system{{opacity:.55}} .event .time{{color:var(--muted);font-family:ui-monospace,monospace}} .event .type{{font-weight:700}} .event .level{{color:#fbbf24}} .note{{color:var(--muted);font-size:12px}} .empty{{color:var(--muted);padding:20px}}
@media(max-width:1100px){{body{{overflow:auto}} .layout{{height:auto;grid-template-columns:260px minmax(600px,1fr)}} .panel.right{{grid-column:1/-1;max-height:none}} .center{{height:850px}}}}
</style>
</head>
<body>
<header>
<div><h1>{title}</h1><div class="subtitle">Questie坐标复刻 · 任务链 · 实际人物历程</div></div>
<div class="controls">
<label class="file-label">选择游戏地图截图<input id="mapFile" type="file" accept="image/*"></label>
<label>底图 <input id="opacity" type="range" min="0" max="100" value="58"></label>
<button id="focusBtn">显示全图</button>
<button id="spawnBtn">显示当前步骤刷新点</button>
</div>
</header>
<div class="layout">
<section class="panel"><div class="panel-title">小区域与步骤</div><div id="segments"></div><div id="steps"></div></section>
<section class="center">
<div class="map-wrap">
<svg id="map" viewBox="24 13 32 40" preserveAspectRatio="xMidYMid meet">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b"/></marker></defs>
<image id="mapImage" x="0" y="0" width="100" height="100" opacity=".58" preserveAspectRatio="none"/>
<g id="grid"></g><g id="routeLayer"></g><g id="spawnLayer"></g><g id="markerLayer"></g>
</svg>
<div class="legend"><span><i class="dot" style="background:#f59e0b"></i>当前步骤</span><span><i class="dot" style="background:#22d3ee"></i>候选路线</span><span><i class="dot" style="background:#34d399"></i>已实测确认</span></div>
<div class="map-help">坐标按Questie的0–100区域坐标绘制。底图应使用完整大地图截图；点击编号查看步骤。</div>
</div>
<div class="tabs"><div class="tabbar"><button data-tab="chain" class="active">任务链</button><button data-tab="journey">实际历程</button><button data-tab="compare">路线对比</button></div><div id="tabContent" class="tab-content"></div></div>
</section>
<section class="panel right"><div class="panel-title">步骤详情</div><div id="detail" class="detail"></div></section>
</div>
<script id="route-data" type="application/json">{route_json}</script>
<script id="journey-data" type="application/json">{journey_json}</script>
<script>
const route=JSON.parse(document.getElementById('route-data').textContent); const journey=JSON.parse(document.getElementById('journey-data').textContent||'{{}}');
const ns='http://www.w3.org/2000/svg'; const segments=(route.segments&&route.segments.length)?route.segments:[{{id:'ALL',title:'全部步骤',steps:route.steps.map(s=>s.step),goal:'完整候选路线'}}]; let activeSegment=segments[0].id, selected=segments[0].steps[0], showSpawns=false, focused=true, currentTab='chain';
const byQuest=new Map(route.quest_catalog.map(q=>[q.quest_id,q])); const completeSet=new Set(journey.complete_quest_ids||[]); const eventQuestSet=new Set((journey.events||[]).map(e=>e.quest_id).filter(Boolean));
function el(tag,attrs={{}},text=''){{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;return n}}
function rep(step){{return step.anchor_details.representative}}
function currentSegment(){{return segments.find(s=>s.id===activeSegment)||segments[0]}}
function visibleSteps(){{const allowed=new Set(currentSegment().steps);return route.steps.filter(s=>allowed.has(s.step))}}
function routeBounds(steps=visibleSteps()){{const ps=steps.map(rep).filter(Boolean);if(!ps.length)return[0,0,100,100];let minX=Math.min(...ps.map(p=>p.x))-3,maxX=Math.max(...ps.map(p=>p.x))+3,minY=Math.min(...ps.map(p=>p.y))-3,maxY=Math.max(...ps.map(p=>p.y))+3;const x=Math.max(0,minX),y=Math.max(0,minY);return [x,y,Math.max(8,Math.min(100,maxX)-x),Math.max(8,Math.min(100,maxY)-y)]}}
function setView(){{document.getElementById('map').setAttribute('viewBox',focused?routeBounds().join(' '):'0 0 100 100');document.getElementById('focusBtn').textContent=focused?'显示全图':'聚焦小区域'}}
function renderGrid(){{const g=document.getElementById('grid');g.innerHTML='';for(let i=0;i<=100;i+=10){{g.append(el('line',{{x1:i,y1:0,x2:i,y2:100,stroke:'#64748b','stroke-opacity':'.15','stroke-width':'.16','vector-effect':'non-scaling-stroke'}}));g.append(el('line',{{x1:0,y1:i,x2:100,y2:i,stroke:'#64748b','stroke-opacity':'.15','stroke-width':'.16','vector-effect':'non-scaling-stroke'}}));g.append(el('text',{{x:i+.4,y:1.7,fill:'#94a3b8','font-size':'1.05'}},String(i)));g.append(el('text',{{x:.4,y:i+1.3,fill:'#94a3b8','font-size':'1.05'}},String(i)))}}}}
function collisionPoints(steps){{const seen=new Map();return steps.map(s=>{{const p=rep(s);if(!p)return null;const key=p.x.toFixed(1)+','+p.y.toFixed(1);const n=seen.get(key)||0;seen.set(key,n+1);const angle=n*2.2;const radius=n?0.7+Math.floor(n/4)*.4:0;return {{x:p.x+Math.cos(angle)*radius,y:p.y+Math.sin(angle)*radius}}}})}}
function observationStatus(step){{const obs=step.quests.map(q=>route.fivebox_observations[String(q.quest_id)]).filter(Boolean);if(obs.some(o=>o.status==='user_confirmed'))return'confirmed';if(obs.some(o=>o.status==='partially_confirmed'))return'partial';return'pending'}}
function renderSegments(){{const root=document.getElementById('segments');root.innerHTML='';for(const segment of segments){{const b=document.createElement('button');b.className='segment-btn'+(segment.id===activeSegment?' active':'');b.innerHTML=`<strong>${{segment.id}} · ${{segment.title}}</strong><small>${{segment.goal}}</small>`;b.onclick=()=>selectSegment(segment.id);root.append(b)}}}}
function renderMap(){{setView();const routeG=document.getElementById('routeLayer'),markG=document.getElementById('markerLayer'),spawnG=document.getElementById('spawnLayer');routeG.innerHTML=markG.innerHTML=spawnG.innerHTML='';const steps=visibleSteps(),pts=collisionPoints(steps);const path=pts.filter(Boolean).map((p,i)=>(i?'L':'M')+p.x+' '+p.y).join(' ');if(path)routeG.append(el('path',{{d:path,fill:'none',stroke:'#22d3ee','stroke-width':'.5','stroke-opacity':'.75','stroke-dasharray':'1.3 .65','marker-end':'url(#arrow)','vector-effect':'non-scaling-stroke'}}));
steps.forEach((s,i)=>{{const p=pts[i];if(!p)return;const active=s.step===selected,status=observationStatus(s);const color=active?'#f59e0b':status==='confirmed'?'#34d399':status==='partial'?'#fbbf24':'#64748b';const group=el('g',{{class:'marker','data-step':s.step,style:'cursor:pointer'}});group.append(el('circle',{{cx:p.x,cy:p.y,r:active?1.05:.82,fill:color,stroke:'#081018','stroke-width':'.3','vector-effect':'non-scaling-stroke'}}));group.append(el('text',{{x:p.x,y:p.y+.35,'text-anchor':'middle',fill:'#081018','font-size':active?'1.05':'.86','font-weight':'800'}},String(s.step)));group.addEventListener('click',()=>selectStep(s.step));markG.append(group)}});
if(showSpawns){{const s=route.steps.find(x=>x.step===selected);for(const e of s.anchor_details.entities)for(const p of e.coordinates)spawnG.append(el('circle',{{cx:p.x,cy:p.y,r:'.22',fill:'#fb7185','fill-opacity':'.78',stroke:'#fff','stroke-width':'.06'}}))}}
}}
function selectSegment(id){{activeSegment=id;const segment=currentSegment();if(!segment.steps.includes(selected))selected=segment.steps[0];focused=true;renderSegments();renderSteps();renderMap();renderDetail()}}
function selectStep(n){{const segment=segments.find(s=>s.steps.includes(n));if(segment)activeSegment=segment.id;selected=n;renderSegments();renderSteps();renderMap();renderDetail()}}
function renderSteps(){{const root=document.getElementById('steps');root.innerHTML='';for(const s of visibleSteps()){{const q=s.quests.map(x=>x.quest_id+' '+x.name).join('、');const c=document.createElement('div');c.className='step-card'+(s.step===selected?' active':'');c.innerHTML=`<div class="step-head"><span class="step-num">${{s.step}}</span><span class="step-action">${{s.action}}</span></div><div class="step-quests">${{q}}</div>`;c.onclick=()=>selectStep(s.step);root.append(c)}}}}
function statusBadge(o){{if(!o)return'';const cls=o.status==='user_confirmed'?'confirmed':o.status==='partially_confirmed'?'partial':'pending';const label=o.status==='user_confirmed'?'实测确认':o.status==='partially_confirmed'?'部分确认':o.status==='database_confirmed'?'数据库确认':'待验证';return `<span class="badge ${{cls}}">${{label}}</span>`}}
function renderDetail(){{const s=route.steps.find(x=>x.step===selected),r=rep(s),root=document.getElementById('detail');const qs=s.quests.map(q=>{{const o=route.fivebox_observations[String(q.quest_id)];return `<div class="quest">${{statusBadge(o)}}<span class="quest-id">${{q.quest_id}}</span> <strong>${{q.name}}</strong><div class="note">前置：${{[...q.pre_single,...q.pre_group].join('、')||'无'}} · 等级${{q.required_level}}</div>${{o?`<div>${{o.note||''}}</div>`:''}}</div>`}}).join('');const ents=s.anchor_details.entities.map(e=>{{const c=e.coordinate_summary?.representative;return `<div class="entity"><strong>${{e.name}}</strong> <span class="quest-id">${{e.id}}</span><br><small>${{c?`坐标 ${{c.x}}, ${{c.y}} · ${{e.coordinate_summary.spawn_count}}个数据库点`:'无坐标'}}</small></div>`}}).join('');root.innerHTML=`<span class="badge">步骤 ${{s.step}}</span><span class="badge">${{s.action}}</span><span class="badge">置信度 ${{s.confidence}}</span><h2>${{s.quests.map(q=>q.name).join(' / ')}}</h2><div class="instruction">${{s.instruction}}</div><h3>任务与五开规则</h3>${{qs}}<h3>地图锚点</h3>${{ents}}<div class="note">代表坐标：${{r?`${{r.x}}, ${{r.y}}`:'无'}}。代表点用于步骤连线；点击“显示刷新点”可查看本步骤全部Questie坐标。</div>`}}
function questStatus(id){{return completeSet.has(id)?'completed':eventQuestSet.has(id)?'seen':'planned'}}
function renderChain(){{const nodes=route.quest_catalog,ids=new Set(nodes.map(n=>n.quest_id)),parents=new Map();for(const n of nodes)parents.set(n.quest_id,[...n.pre_single,...n.pre_group].filter(x=>ids.has(x)));const memo=new Map();function depth(id,stack=new Set()){{if(memo.has(id))return memo.get(id);if(stack.has(id))return 0;stack.add(id);const ps=parents.get(id)||[];const d=ps.length?Math.max(...ps.map(p=>depth(p,stack)+1)):0;memo.set(id,d);return d}}const cols=new Map();for(const n of nodes){{const d=depth(n.quest_id);if(!cols.has(d))cols.set(d,[]);cols.get(d).push(n)}}const maxD=Math.max(...cols.keys()),w=Math.max(900,(maxD+1)*165),h=Math.max(210,Math.max(...[...cols.values()].map(x=>x.length))*62+40);const svg=el('svg',{{id:'chainSvg',viewBox:`0 0 ${{w}} ${{h}}`}});const defs=el('defs');const marker=el('marker',{{id:'chainArrow',viewBox:'0 0 10 10',refX:'8',refY:'5',markerWidth:'5',markerHeight:'5',orient:'auto'}});marker.append(el('path',{{d:'M0 0 L10 5 L0 10z',fill:'#64748b'}}));defs.append(marker);svg.append(defs);const pos=new Map();for(const [d,list] of cols)list.forEach((n,i)=>pos.set(n.quest_id,{{x:25+d*165,y:25+i*62}}));for(const n of nodes)for(const p of parents.get(n.quest_id)||[]){{const a=pos.get(p),b=pos.get(n.quest_id);svg.append(el('path',{{d:`M ${{a.x+120}} ${{a.y+19}} C ${{a.x+143}} ${{a.y+19}}, ${{b.x-23}} ${{b.y+19}}, ${{b.x}} ${{b.y+19}}`,fill:'none',stroke:'#64748b','stroke-width':'1.5','marker-end':'url(#chainArrow)'}}))}}for(const n of nodes){{const p=pos.get(n.quest_id),st=questStatus(n.quest_id),g=el('g',{{style:'cursor:pointer'}}),fill=st==='completed'?'#123d32':st==='seen'?'#3a2e12':'#182231',stroke=st==='completed'?'#34d399':st==='seen'?'#fbbf24':'#475569';g.append(el('rect',{{x:p.x,y:p.y,width:120,height:38,rx:7,fill,stroke,'stroke-width':'1.2'}}));g.append(el('text',{{x:p.x+7,y:p.y+14,fill:'#67e8f9','font-size':'9','font-family':'monospace'}},String(n.quest_id)));g.append(el('text',{{x:p.x+7,y:p.y+29,fill:'#e5e7eb','font-size':'9.5'}},n.name.length>10?n.name.slice(0,10)+'…':n.name));g.onclick=()=>{{const s=route.steps.find(s=>s.quest_ids.includes(n.quest_id));if(s)selectStep(s.step)}};svg.append(g)}}const root=document.createElement('div');root.innerHTML='<div class="note">绿色＝历程已完成，黄色＝历程出现但未完成，灰色＝后续候选。箭头来自Questie前置关系。</div>';root.append(svg);return root}}
function renderJourney(){{const root=document.createElement('div');if(!journey.events?.length){{root.className='empty';root.textContent='尚未导入人物历程';return root}}const duration=Math.round((journey.latest_timestamp-journey.earliest_timestamp)/60);root.innerHTML=`<div class="summary-grid"><div class="summary"><strong>${{journey.min_level}}→${{journey.max_level}}</strong>等级范围</div><div class="summary"><strong>${{duration}} 分钟</strong>记录跨度</div><div class="summary"><strong>${{journey.quest_events}}</strong>任务事件</div><div class="summary"><strong>${{journey.level_events}}</strong>升级事件</div></div>`;const line=document.createElement('div');line.className='timeline';for(const e of journey.events){{const mins=Math.round((e.timestamp-journey.earliest_timestamp)/60),main=e.quest_id&&byQuest.has(e.quest_id),q=e.quest_id?(byQuest.get(e.quest_id)?.name||`任务 ${{e.quest_id}}`):`升到 ${{e.level}} 级`;const item=document.createElement('div');item.className='event'+(main||e.event==='LevelUp'?'':' system');const labels={{Accept:'接取',Complete:'完成',Abandon:'放弃',LevelUp:'升级'}};item.innerHTML=`<span class="time">+${{mins}}m</span><span class="type">${{labels[e.event]||e.event}}</span><span>${{e.quest_id?`<span class="quest-id">${{e.quest_id}}</span> `:''}}${{q}}</span><span class="level">Lv.${{e.level}}</span>`;line.append(item)}}root.append(line);return root}}
function renderCompare(){{const root=document.createElement('div');const q8325=(journey.events||[]).find(e=>e.event==='Complete'&&e.quest_id===8325);const last=[...(journey.events||[])].reverse().find(e=>e.quest_id);root.innerHTML=`<div class="summary-grid"><div class="summary"><strong>${{q8325?'Lv.'+q8325.level:'未知'}}</strong>完成8325时等级</div><div class="summary"><strong>${{last?last.quest_id:'无'}}</strong>历程最后任务</div></div><h3>已确认</h3><ul><li>打怪任务五号同步增加。</li><li>山猫项圈与奥术薄片需要逐号拾取。</li><li>索兰尼亚三个物品需要逐号点击。</li><li>达斯雷玛神殿只需一次交互。</li><li>被污染的奥术薄片五号均成功触发。</li></ul><h3>历程与候选路线差异</h3><ul><li>P01在开始后较晚才接取8330和8345；V2将它们提前到太阳之塔集中接取。</li><li>人物历程在接取8334后结束，后续步骤仍是Questie静态候选。</li><li>五个账号的账号级SavedVariables基本相同，因此当前历程只代表P01 profile，不能逐号比较。</li></ul><h3>仍需验证</h3><ul>${{route.verification_required.map(x=>`<li>${{x}}</li>`).join('')}}</ul>`;return root}}
function renderTab(){{const root=document.getElementById('tabContent');root.innerHTML='';root.append(currentTab==='chain'?renderChain():currentTab==='journey'?renderJourney():renderCompare())}}
document.querySelectorAll('.tabbar button').forEach(b=>b.onclick=()=>{{currentTab=b.dataset.tab;document.querySelectorAll('.tabbar button').forEach(x=>x.classList.toggle('active',x===b));renderTab()}});
document.getElementById('focusBtn').onclick=()=>{{focused=!focused;renderMap()}};document.getElementById('spawnBtn').onclick=()=>{{showSpawns=!showSpawns;document.getElementById('spawnBtn').textContent=showSpawns?'隐藏当前步骤刷新点':'显示当前步骤刷新点';renderMap()}};
document.getElementById('opacity').oninput=e=>document.getElementById('mapImage').setAttribute('opacity',Number(e.target.value)/100);
document.getElementById('mapFile').onchange=e=>{{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>document.getElementById('mapImage').setAttribute('href',r.result);r.readAsDataURL(f)}};
renderGrid();renderSegments();renderSteps();renderMap();renderDetail();renderTab();
</script>
</body></html>'''


def write_html(route: dict[str, Any], output_dir: Path, journey_path: Path | None = None) -> Path:
    journey = None
    if journey_path and journey_path.exists():
        journey = json.loads(journey_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{route.get('output_basename', 'sunstrider-isle')}.html"
    path.write_text(render_html(route, journey), encoding="utf-8")
    return path
