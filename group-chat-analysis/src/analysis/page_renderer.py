from __future__ import annotations

import json


def _json_payload(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def dossier_evidence_index(dossier: dict) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for section in dossier.get("sections", []):
        for signal in section.get("signals", []):
            for card_id in signal.get("evidence_ids", []):
                if not card_id:
                    continue
                index.setdefault(card_id, []).append({
                    "section_key": section.get("key", ""),
                    "section_title": section.get("title", ""),
                    "field": signal.get("field", ""),
                })
    return index


def build_page_v3(cards: list[dict], blackwords: list[dict], dossier: dict, knowledge_units: list[dict]) -> str:
    component_ids = {
        ref.get("card_id")
        for unit in knowledge_units
        for ref in unit.get("evidence_refs", [])
        if ref.get("card_id") and ref.get("coverage", "full") == "full"
    }
    component_ids.update(dossier_evidence_index(dossier))
    queue_count = sum(bool(card.get("v3_queue")) and card.get("card_id") not in component_ids for card in cards) + sum(unit.get("initial_state") == "queue" for unit in knowledge_units)
    knowledge_count = sum(bool(card.get("v3_knowledge")) and card.get("card_id") not in component_ids for card in cards) + sum(unit.get("initial_state") == "knowledge" for unit in knowledge_units)
    payload = _json_payload(cards)
    blackword_payload = _json_payload(blackwords)
    dossier_payload = _json_payload(dossier)
    knowledge_payload = _json_payload(knowledge_units)

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>群聊情报</title>
<style>
:root{{--bg:#f4f6f8;--panel:#fff;--line:#dfe5eb;--ink:#172033;--muted:#6b7586;--soft:#f8fafc;--accent:#243a73;--accent-soft:#edf2ff;--warn:#8a5b13;--warn-soft:#fff8e7;--good:#235f46}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}
button,input{{font:inherit}}
.shell{{max-width:1120px;margin:auto;padding:22px 24px 64px}}
.header{{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:14px}}
h1{{font-size:21px;margin:0}}
.sub{{font-size:12px;color:var(--muted);margin-top:3px}}
.header-count{{font-size:12px;color:var(--muted);white-space:nowrap}}
.nav{{position:sticky;top:0;z-index:20;display:flex;gap:2px;background:rgba(244,246,248,.96);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);margin:0 -24px 20px;padding:0 24px;overflow:auto}}
.nav button{{border:0;background:none;color:var(--muted);font-weight:650;padding:12px 13px 10px;white-space:nowrap;border-bottom:2px solid transparent;cursor:pointer}}
.nav button.active{{color:var(--ink);border-color:var(--accent)}}
.view{{display:none}}
.view.active{{display:block}}
.intro{{margin-bottom:13px}}
.intro h2{{font-size:24px;margin:0 0 4px}}
.intro p{{margin:0;color:var(--muted);max-width:850px}}
.search{{width:100%;border:1px solid var(--line);background:#fff;border-radius:9px;padding:9px 11px;color:var(--ink);outline:none}}
.search:focus{{border-color:#a7b5cf;box-shadow:0 0 0 3px #dfe7f522}}
.topicbar{{display:flex;gap:6px;overflow:auto;padding:10px 0 12px;scrollbar-width:thin}}
.topicbar button{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 10px;color:#566277;font-size:12px;white-space:nowrap;cursor:pointer}}
.topicbar button.active{{background:var(--ink);border-color:var(--ink);color:#fff}}
.topicbar span{{margin-left:4px;opacity:.6;font-size:10px}}
.subtopicbar{{padding-top:0;margin-top:-4px}}
.subtopicbar:empty{{display:none}}
.result{{font-size:12px;color:var(--muted);margin:0 0 10px}}
.group{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:0 16px;margin:10px 0 16px}}
.group-head{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #d8dee6;padding:11px 0 8px}}
.group-head b{{font-size:14px}}
.group-head span{{font-size:11px;color:#8792a3}}
.card{{background:transparent;border:0;border-top:1px solid #edf0f4;border-radius:0;padding:12px 0;margin:0}}
.card:first-of-type{{border-top:0}}
.card-eyebrow{{font-size:12px;color:#52617a;font-weight:650;margin-bottom:4px}}
.card h3{{font-size:17px;line-height:1.5;margin:0 0 7px}}
.fact{{font-size:15px;color:#364257}}
.unit{{background:#fff;border:1px solid #cfd8e5;border-radius:12px;padding:15px 17px;margin:10px 0 16px;box-shadow:0 1px 2px #17203308}}
.unit .question{{font-size:12px;color:#66758c;margin-bottom:3px}}
.unit h3{{font-size:18px;margin:0 0 8px}}
.unit-facts{{margin:8px 0 10px;padding-left:20px;color:#374459}}
.unit-facts li{{margin:4px 0}}
.struct-table{{width:100%;border-collapse:collapse;margin:9px 0;font-size:13px}}
.struct-table th,.struct-table td{{border-top:1px solid #e7ebf0;padding:7px 8px;text-align:left;vertical-align:top}}
.struct-table th{{color:#657186;font-weight:650;background:#fafbfc}}
.struct-table td:first-child{{white-space:nowrap;color:#516078;font-weight:650}}
.unit-note{{font-size:12px;color:#778397;margin-top:7px}}
.context{{margin:9px 0;background:var(--soft);border-left:3px solid #cbd5e1;border-radius:7px;padding:8px 10px;color:#566277;font-size:13px}}
.context b{{color:#3f4a5c}}
.meta{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;color:#8a95a5;font-size:11px;margin-bottom:5px}}
.badge{{display:inline-block;background:var(--warn-soft);color:var(--warn);border:1px solid #ead6a9;border-radius:999px;padding:2px 7px;font-size:10px}}
.actions{{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:10px}}
.actions button{{border:1px solid var(--line);background:#fff;border-radius:7px;padding:5px 9px;color:#566277;cursor:pointer;font-size:12px}}
.actions button.keep{{border-color:#bdcadf;color:#2d4b80;background:#f7f9ff}}
.source{{border:0!important;background:none!important;padding:5px 2px!important;color:#3159d6!important}}
.empty{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:24px;color:var(--muted)}}
.pager{{display:flex;justify-content:center;align-items:center;gap:8px;margin-top:14px;color:#6f7b8e;font-size:12px}}
.pager button{{border:1px solid var(--line);background:#fff;border-radius:7px;padding:6px 10px;cursor:pointer;color:#526078}}
.pager button:disabled{{opacity:.35;cursor:default}}
.kb-tip{{font-size:12px;color:var(--muted);margin:7px 0 3px}}
.dossier-head{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 17px;margin-bottom:11px}}
.dossier-stage{{font-size:12px;color:#52617a;font-weight:700;margin-bottom:4px}}
.dossier-head p{{margin:0;color:#5a6678}}
.dossier-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.dossier-card{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:14px 16px}}
.dossier-card h3{{font-size:17px;margin:0 0 6px}}
.dossier-card p{{margin:0;color:#3f4b5e}}
.dossier-card details{{margin-top:10px;border-top:1px solid #edf0f4;padding-top:8px}}
.dossier-card summary{{cursor:pointer;font-size:12px;color:#52617a;font-weight:650}}
.dossier-card ul{{padding-left:20px;margin:7px 0 0;color:#5d6879}}
.dossier-card li{{margin:4px 0}}
.evidence-list{{font-size:12px;color:#697587}}
.slang-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:10px}}
.slang-card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 15px}}
.slang-card h3{{font-size:17px;margin:0 0 4px}}
.slang-card p{{margin:0;color:#465267}}
.slang-card small{{display:block;color:#8993a3;margin-top:6px}}
.drawer-backdrop{{position:fixed;inset:0;background:#1520382b;opacity:0;pointer-events:none;transition:.15s;z-index:40}}
.drawer{{position:fixed;right:0;top:0;width:min(600px,52vw);height:100vh;background:#fff;border-left:1px solid var(--line);transform:translateX(100%);transition:.18s;z-index:41;display:flex;flex-direction:column}}
.drawer.open{{transform:translateX(0)}}
.drawer-backdrop.open{{opacity:1;pointer-events:auto}}
.drawer-head{{height:50px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 17px;border-bottom:1px solid var(--line)}}
.drawer-head button{{border:1px solid var(--line);background:#fff;border-radius:7px;width:30px;height:30px;cursor:pointer}}
.drawer iframe{{border:0;width:100%;height:100%}}
@media(max-width:760px){{.dossier-grid,.slang-grid{{grid-template-columns:1fr}}.drawer{{width:88vw}}}}
@media(max-width:560px){{.shell{{padding:16px 13px 48px}}.nav{{margin:0 -13px 17px;padding:0 13px}}.header{{display:block}}.header-count{{margin-top:6px}}.drawer{{width:100vw}}}}
</style>
</head>
<body>
<div class="shell">
<header class="header"><div><h1>群聊情报</h1><div class="sub">看一遍新信息；有用的留下，没用的不再重复。</div></div><div class="header-count">历史候选 {len(cards):,} · 初始待看 {queue_count:,} · 已确认知识 {knowledge_count:,}</div></header>
<nav class="nav">
  <button class="active" data-view="new">新信息</button>
  <button data-view="knowledge">资料库</button>
  <button data-view="infinite">无限服</button>
  <button data-view="slang">黑话</button>
</nav>
<section id="new" class="view active">
  <div class="intro"><h2>新信息</h2><p>只看第一次值得你扫一眼的内容。旧结论重复出现、单纯可信度升级不会重新占这里。</p></div>
  <input id="newSearch" class="search" placeholder="搜索标题、事实、任务、副本、职业……">
  <div id="newTopics" class="topicbar"></div>
  <div id="newSubtopics" class="topicbar subtopicbar"></div>
  <div id="newResult" class="result"></div>
  <div id="newCards"></div>
  <div class="pager"><button id="newPrev">上一批</button><span id="newPage"></span><button id="newNext">下一批</button></div>
</section>
<section id="knowledge" class="view">
  <div class="intro"><h2>资料库</h2><p>主要用于以后只记得几个关键词时找回来，不要求平时浏览。</p></div>
  <input id="kbSearch" class="search" placeholder="搜任务名、Boss、职业、装备、插件、关键词……">
  <div class="kb-tip">一级专题保持稳定；职业和副本进入后再按职业或具体副本细分，其他专题暂不增加下一级。</div>
  <div id="kbTopics" class="topicbar"></div>
  <div id="kbSubtopics" class="topicbar subtopicbar"></div>
  <div id="kbResult" class="result"></div>
  <div id="kbCards"></div>
</section>
<section id="infinite" class="view">
  <div class="intro"><h2>无限服</h2><p>把封测阶段的零散观察逐渐拼成对玩家发展、经济和打金机会的完整认知。</p></div>
  <div id="dossier"></div>
</section>
<section id="slang" class="view">
  <div class="intro"><h2>黑话</h2><p>只解决群聊语境里的词义和多义，不做普通游戏百科。</p></div>
  <input id="slangSearch" class="search" placeholder="搜索黑话、含义或语境">
  <div id="slangResult" class="result"></div>
  <div id="slangCards" class="slang-grid"></div>
</section>
</div>
<div id="drawerBackdrop" class="drawer-backdrop" onclick="closeSource()"></div>
<aside id="sourceDrawer" class="drawer"><div class="drawer-head"><b>群聊原文</b><button onclick="closeSource()">×</button></div><iframe id="sourceFrame"></iframe></aside>
<script id="cardData" type="application/json">{payload}</script>
<script id="blackwordData" type="application/json">{blackword_payload}</script>
<script id="dossierData" type="application/json">{dossier_payload}</script>
<script id="knowledgeData" type="application/json">{knowledge_payload}</script>
<script>
const ALL=JSON.parse(document.getElementById('cardData').textContent);
const BLACKWORDS=JSON.parse(document.getElementById('blackwordData').textContent);
const DOSSIER=JSON.parse(document.getElementById('dossierData').textContent||'{{}}');
const UNITS=JSON.parse(document.getElementById('knowledgeData').textContent||'[]');
const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]));
const byId=Object.fromEntries(ALL.map(c=>[c.card_id,c]));
const DOSSIER_COMPONENT_IDS=(DOSSIER.sections||[]).flatMap(s=>(s.signals||[]).flatMap(x=>x.evidence_ids||[])).filter(Boolean);
const COMPONENT_IDS=new Set([...UNITS.flatMap(u=>(u.evidence_refs||[]).filter(x=>x.coverage!=='partial').map(x=>x.card_id).filter(Boolean)),...DOSSIER_COMPONENT_IDS]);
let newTopic='', newSubtopic='', kbTopic='', kbSubtopic='', newPage=1; const NEW_PER=40;

function oldFeedback(id){{return localStorage.getItem('gca-feedback:'+id)||''}}
function localDecision(id){{
  const current=localStorage.getItem('gca-v3:'+id);
  if(current)return current;
  const old=oldFeedback(id);
  if(old==='没用')return 'discard';
  if(old==='有用'||old==='重要')return 'knowledge';
  if(old==='一般')return 'seen';
  return ''
}}
function setDecision(id,value){{localStorage.setItem('gca-v3:'+id,value);renderNew();renderKnowledge()}}
const unitById=Object.fromEntries(UNITS.map(u=>[u.knowledge_id,u]));
function unitDecision(id){{
  const u=unitById[id]||{{}};
  const fp=u.semantic_fingerprint||'';
  if(fp){{
    const semantic=localStorage.getItem('gca-semantic:'+fp);
    if(semantic)return semantic;
  }}
  return localStorage.getItem('gca-unit:'+id)||''
}}
async function persistUnitDecision(id,value){{
  const api=window.GCA_REVIEW_API;
  if(!api||!api.csrf)return;
  try{{
    const response=await fetch('/api/review-decision',{{
      method:'POST',
      credentials:'same-origin',
      headers:{{'Content-Type':'application/json','X-GCA-CSRF':api.csrf}},
      body:JSON.stringify({{knowledge_id:id,decision:value}})
    }});
    if(!response.ok){{
      let detail='HTTP '+response.status;
      try{{const body=await response.json();detail=body.message||body.error||detail}}catch(_e){{}}
      throw new Error(detail)
    }}
  }}catch(error){{
    console.error('review decision persistence failed',error);
    alert('正式保存失败，本次选择目前只保存在此浏览器。请保持页面不关闭并检查本地服务。')
  }}
}}
function setUnitDecision(id,value){{
  const u=unitById[id]||{{}};
  const fp=u.semantic_fingerprint||'';
  if(fp)localStorage.setItem('gca-semantic:'+fp,value);
  localStorage.setItem('gca-unit:'+id,value);
  renderNew();renderKnowledge();
  void persistUnitDecision(id,value)
}}
async function syncFormalUnitDecisions(){{
  const api=window.GCA_REVIEW_API;
  if(!api||!api.csrf)return;
  try{{
    const response=await fetch('/api/review-state',{{credentials:'same-origin',cache:'no-store'}});
    if(!response.ok)throw new Error('HTTP '+response.status);
    const payload=await response.json();
    for(const item of payload.items||[]){{
      const u=unitById[item.knowledge_id];
      if(!u)continue;
      localStorage.setItem('gca-unit:'+item.knowledge_id,item.decision);
      const fp=u.semantic_fingerprint||item.semantic_fingerprint||'';
      if(fp)localStorage.setItem('gca-semantic:'+fp,item.decision)
    }}
    renderNew();renderKnowledge()
  }}catch(error){{
    console.error('formal review state sync failed',error)
  }}
}}
function isQueue(c){{return c.v3_first_read_queue&&!localDecision(c.card_id)}}
function isKnowledge(c){{return !COMPONENT_IDS.has(c.card_id)&&(c.v3_knowledge||localDecision(c.card_id)==='knowledge')}}
function unitIsQueue(u){{return u.v3_first_read_queue&&!unitDecision(u.knowledge_id)}}
function unitIsKnowledge(u){{return u.initial_state==='knowledge'||u.v3_reviewed_decision==='knowledge'||unitDecision(u.knowledge_id)==='knowledge'}}
function searchText(c){{return [c.card_id,c.title,c.semantic_summary,c.display_eyebrow,c.display_context,c.display_new_fact,...(c.tags||[]),...(c.collection_candidates||[]),...(c.v3_topics||[]).map(x=>x.label)].join(' ').toLowerCase()}}
function unitSearchText(u){{return [u.knowledge_id,u.subject,u.question,...(u.canonical_facts||[]),...(u.search_terms||[]),...(u.topics||[])].join(' ').toLowerCase()}}
const PRIMARY_TOPIC_ORDER=['职业','副本攻略','任务与练级','装备机制','专业技能','经济 / 打金','插件 / 故障排查','防诈骗经验','PVP / 野外生态','其他'];
function itemTopics(x){{return x.display_topics||['其他']}}
function itemSubtopics(x,key){{return ((x.display_subtopics||{{}})[key]||[])}}
function topicMatch(x,key,subkey=''){{
  if(key&&!itemTopics(x).includes(key))return false;
  return !subkey||itemSubtopics(x,key).includes(subkey)
}}
function displayTopicText(x){{
  const primary=itemTopics(x);
  const sub=x.display_subtopics||{{}};
  return primary.map(label=>{{const children=sub[label]||[];return children.length?`${{label}}：${{children.join(' / ')}}`:label}}).join(' · ')
}}

function buildTopicBar(el,itemsSource,active,onClick){{
  const counts={{}};
  itemsSource.forEach(x=>itemTopics(x).forEach(label=>{{counts[label]=(counts[label]||0)+1}}));
  const items=Object.entries(counts).filter(([,n])=>n>0).sort((a,b)=>{{
    const ai=PRIMARY_TOPIC_ORDER.indexOf(a[0]),bi=PRIMARY_TOPIC_ORDER.indexOf(b[0]);
    if(ai!==-1||bi!==-1)return (ai===-1?999:ai)-(bi===-1?999:bi);
    return a[0].localeCompare(b[0],'zh-CN')
  }});
  el.innerHTML=`<button class="${{active===''?'active':''}}" data-key="">全部<span>${{itemsSource.length}}</span></button>`+items.map(([label,n])=>`<button class="${{active===label?'active':''}}" data-key="${{esc(label)}}">${{esc(label)}}<span>${{n}}</span></button>`).join('');
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>onClick(b.dataset.key||''));
}}
function buildSubtopicBar(el,itemsSource,topic,active,onClick){{
  if(!['职业','副本攻略'].includes(topic)){{el.innerHTML='';return}}
  const counts={{}};
  itemsSource.filter(x=>itemTopics(x).includes(topic)).forEach(x=>itemSubtopics(x,topic).forEach(label=>{{counts[label]=(counts[label]||0)+1}}));
  const items=Object.entries(counts).filter(([,n])=>n>0).sort((a,b)=>a[0].localeCompare(b[0],'zh-CN'));
  if(!items.length){{el.innerHTML='';return}}
  const allCount=itemsSource.filter(x=>itemTopics(x).includes(topic)).length;
  const allLabel=topic==='职业'?'全部职业':'全部副本';
  el.innerHTML=`<button class="${{active===''?'active':''}}" data-key="">${{allLabel}}<span>${{allCount}}</span></button>`+items.map(([label,n])=>`<button class="${{active===label?'active':''}}" data-key="${{esc(label)}}">${{esc(label)}}<span>${{n}}</span></button>`).join('');
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>onClick(b.dataset.key||''));
}}

function sourceButton(c){{
  const link=c.source_link||{{}};
  if(link.confidence==='high'&&link.detail_href)return `<button class="source" onclick="openSource('${{esc(link.detail_href)}}')">查看原文 →</button>`;
  return ''
}}
function cardHtml(c,mode){{
  const eyebrow=c.display_eyebrow||'';
  const context=c.display_context||'';
  const fact=c.display_new_fact||c.semantic_summary||'';
  const topics=displayTopicText(c);
  const actions=mode==='new'?`<div class="actions"><button onclick="setDecision('${{esc(c.card_id)}}','discard')">没用</button><button class="keep" onclick="setDecision('${{esc(c.card_id)}}','knowledge')">存资料库</button>${{sourceButton(c)}}</div>`:`<div class="actions">${{sourceButton(c)}}</div>`;
  return `<article class="card">
    <div class="meta"><span>${{esc(c.card_id||'')}}</span>${{topics?`<span>${{esc(topics)}}</span>`:''}}${{c.v3_completable?'<span class="badge">可补全</span>':''}}</div>
    ${{eyebrow?`<div class="card-eyebrow">${{esc(eyebrow)}}</div>`:''}}
    <h3>${{esc(c.title)}}</h3>
    ${{context?`<div class="context"><b>这个对象：</b>${{esc(context)}}</div>`:''}}
    <div class="fact">${{esc(fact)}}</div>
    ${{actions}}
  </article>`
}}
function structuredHtml(u){{
  const s=u.structured||{{}};
  if(u.kind==='ordered_route'){{
    const rows=(s.stages||[]).map(x=>`<tr><td>${{esc(x.condition||'')}}</td><td>${{esc(x.action||'')}}</td><td>${{esc(x.target_or_gain||'')}}</td><td>${{esc(x.purpose||'')}}</td><td>${{esc(x.notes||'')}}</td></tr>`).join('');
    const extras=(s.supporting_rules||[]).length?`<div class="context"><b>补充规则：</b>${{s.supporting_rules.map(esc).join('；')}}</div>`:'';
    return `<table class="struct-table"><thead><tr><th>条件</th><th>做什么</th><th>获得 / 练什么</th><th>用途</th><th>备注</th></tr></thead><tbody>${{rows}}</tbody></table>${{extras}}`
  }}
  if(u.kind==='comparison'){{
    const rows=(s.variants||[]).map(x=>`<tr><td>${{esc(x.scope||'')}}</td><td>${{esc(x.behavior||'')}}</td><td>${{esc(x.consequence||'')}}</td></tr>`).join('');
    const context=s.object_context?`<div class="context"><b>对象：</b>${{esc(s.object_context)}}</div>`:'';
    const use=(s.use_when||[]).length?`<div class="unit-note">有用场景：${{s.use_when.map(esc).join(' · ')}}</div>`:'';
    return `${{context}}<table class="struct-table"><thead><tr><th>范围</th><th>实际差异</th><th>影响</th></tr></thead><tbody>${{rows}}</tbody></table>${{use}}`
  }}
  if(u.kind==='mechanism'){{
    let rows='';
    if((s.conditions||[]).length)rows+=`<tr><td>适用条件</td><td>${{esc(s.conditions.join('；'))}}</td></tr>`;
    if(s.mechanism)rows+=`<tr><td>机制</td><td>${{esc(s.mechanism)}}</td></tr>`;
    if(s.action)rows+=`<tr><td>怎么用</td><td>${{esc(s.action)}}</td></tr>`;
    if(s.outcome)rows+=`<tr><td>结果</td><td>${{esc(s.outcome)}}</td></tr>`;
    const samples=(s.concrete_samples||[]).map(x=>`<tr><td>实例证据</td><td>${{esc(`${{x.class_spec||''}}：${{x.before_item_level??'?'}} → ${{x.after_item_level??'?'}}装等 / ${{x.runs||1}}车`)}}</td></tr>`).join('');
    return `<table class="struct-table"><tbody>${{rows}}${{samples}}</tbody></table>`
  }}
  return ''
}}
function unitHtml(u,mode){{
  const topics=displayTopicText(u);
  const lead=(u.canonical_facts||[])[0]||'';
  const evidence=(u.evidence_refs||[]).map(x=>x.card_id||x.external).filter(Boolean);
  const evidenceHtml=evidence.map(id=>{{
    const c=byId[id];
    const link=c&&c.source_link||{{}};
    if(link.confidence==='high'&&link.detail_href)return `<button class="source" onclick="openSource('${{esc(link.detail_href)}}')">${{esc(id)}} · 查看原文 →</button>`;
    return esc(id)
  }}).join('<br>');
  const actions=mode==='new'?`<div class="actions"><button onclick="setUnitDecision('${{esc(u.knowledge_id)}}','discard')">没用</button><button class="keep" onclick="setUnitDecision('${{esc(u.knowledge_id)}}','knowledge')">存资料库</button></div>`:'';
  const number=u.display_number?`#${{String(u.display_number).padStart(3,'0')}}`:'';
  return `<article class="unit"><div class="meta">${{number?`<span><b>${{esc(number)}}</b></span>`:''}}<span>已标准化</span><span>${{esc(u.kind||'')}}</span>${{topics?`<span>${{esc(topics)}}</span>`:''}}</div><div class="question">${{esc(u.question||'')}}</div><h3>${{esc(u.subject||'')}}</h3>${{lead?`<div class="fact">${{esc(lead)}}</div>`:''}}${{structuredHtml(u)}}<details><summary>证据来源 · ${{evidence.length}} 条</summary><div class="unit-note">${{evidenceHtml}}</div></details>${{actions}}</article>`
}}
function renderGrouped(cards,el,mode){{
  if(!cards.length){{el.innerHTML='<div class="empty">没有符合当前条件的信息。</div>';return}}
  const groups=new Map();
  cards.forEach(c=>{{
    const name=c.related_topic||c.topic_group_label||'其他';
    const key=`${{c.date||''}}\u0001${{name}}`;
    if(!groups.has(key))groups.set(key,{{name,date:c.date||'',items:[]}});
    groups.get(key).items.push(c)
  }});
  el.innerHTML=[...groups.values()].map(g=>`<section class="group"><div class="group-head"><b>${{esc(g.name)}}</b><span>${{esc(g.date)}} · ${{g.items.length}} 条新增信息</span></div>${{g.items.map(c=>cardHtml(c,mode)).join('')}}</section>`).join('')
}}
function renderNew(){{
  const q=document.getElementById('newSearch').value.trim().toLowerCase();
  const rawBase=ALL.filter(isQueue).filter(c=>!q||searchText(c).includes(q));
  const unitBase=UNITS.filter(unitIsQueue).filter(u=>!q||unitSearchText(u).includes(q));
  const allBase=[...unitBase,...rawBase];
  buildTopicBar(document.getElementById('newTopics'),allBase,newTopic,key=>{{newTopic=key;newSubtopic='';newPage=1;renderNew()}});
  buildSubtopicBar(document.getElementById('newSubtopics'),allBase,newTopic,newSubtopic,key=>{{newSubtopic=key;newPage=1;renderNew()}});
  const units=unitBase.filter(u=>topicMatch(u,newTopic,newSubtopic));
  const cards=rawBase.filter(c=>topicMatch(c,newTopic,newSubtopic)).sort((a,b)=>String(a.date).localeCompare(String(b.date))||String(a.card_id).localeCompare(String(b.card_id)));
  const items=[...units.map(u=>({{type:'unit',value:u}})),...cards.map(c=>({{type:'card',value:c}}))];
  const pages=Math.max(1,Math.ceil(items.length/NEW_PER)); if(newPage>pages)newPage=pages;
  const slice=items.slice((newPage-1)*NEW_PER,newPage*NEW_PER);
  document.getElementById('newResult').textContent=`共 ${{items.length}} 个阅读单元 · ${{units.length}} 个已标准化 · 每批最多 ${{NEW_PER}} 个`;
  document.getElementById('newPage').textContent=`第 ${{newPage}} / ${{pages}} 批`;
  document.getElementById('newPrev').disabled=newPage<=1;document.getElementById('newNext').disabled=newPage>=pages;
  document.getElementById('newCards').innerHTML=slice.map(x=>x.type==='unit'?unitHtml(x.value,'new'):cardHtml(x.value,'new')).join('')||'<div class="empty">没有符合当前条件的信息。</div>'
}}
function renderKnowledge(){{
  const q=document.getElementById('kbSearch').value.trim().toLowerCase();
  const rawBase=ALL.filter(isKnowledge).filter(c=>!q||searchText(c).includes(q));
  const unitBase=UNITS.filter(unitIsKnowledge).filter(u=>!q||unitSearchText(u).includes(q));
  const allBase=[...unitBase,...rawBase];
  buildTopicBar(document.getElementById('kbTopics'),allBase,kbTopic,key=>{{kbTopic=key;kbSubtopic='';renderKnowledge()}});
  buildSubtopicBar(document.getElementById('kbSubtopics'),allBase,kbTopic,kbSubtopic,key=>{{kbSubtopic=key;renderKnowledge()}});
  const units=unitBase.filter(u=>topicMatch(u,kbTopic,kbSubtopic));
  const cards=rawBase.filter(c=>topicMatch(c,kbTopic,kbSubtopic)).sort((a,b)=>String(a.date).localeCompare(String(b.date))||String(a.card_id).localeCompare(String(b.card_id)));
  document.getElementById('kbResult').textContent=`找到 ${{units.length}} 个标准化知识单元 · ${{cards.length}} 条旧格式知识`;
  const unitPart=units.map(u=>unitHtml(u,'knowledge')).join('');
  const temp=document.createElement('div');renderGrouped(cards,temp,'knowledge');
  document.getElementById('kbCards').innerHTML=unitPart+temp.innerHTML
}}
function renderDossier(){{
  const el=document.getElementById('dossier');
  const sections=DOSSIER.sections||[];
  const cards=sections.map(s=>{{
    const signals=s.signals||[];
    const rows=signals.map(sig=>`<tr><td>${{esc(sig.field||'')}}</td><td>${{esc(sig.state||'')}}</td><td>${{esc(sig.scope||'')}}</td><td>${{esc(sig.basis||'')}}</td></tr>`).join('');
    const evidenceIds=[...new Set(signals.flatMap(sig=>sig.evidence_ids||[]))];
    const evidence=evidenceIds.map(id=>byId[id]).filter(Boolean);
    const evidenceHtml=evidence.length?`<div class="evidence-list">${{evidence.map(c=>`${{esc(c.date)}} · ${{esc(c.title)}}`).join('<br>')}}</div>`:'<div class="evidence-list">当前证据索引待补齐</div>';
    const questions=(s.open_questions||[]).length?`<details><summary>待继续积累</summary><ul>${{s.open_questions.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul></details>`:'';
    return `<article class="dossier-card"><h3>${{esc(s.title)}}</h3><table class="struct-table"><thead><tr><th>观察维度</th><th>当前状态</th><th>适用范围</th><th>依据</th></tr></thead><tbody>${{rows}}</tbody></table>${{questions}}<details><summary>查看当前证据 · ${{evidence.length}} 条</summary>${{evidenceHtml}}</details></article>`
  }}).join('');
  el.innerHTML=`<div class="dossier-head"><div class="dossier-stage">${{esc(DOSSIER.stage||'')}}</div><p>${{esc(DOSSIER.scope_note||'')}}</p></div><div class="dossier-grid">${{cards}}</div>`
}}
function renderSlang(){{
  const q=document.getElementById('slangSearch').value.trim().toLowerCase();
  const rows=BLACKWORDS.filter(x=>!q||JSON.stringify(x).toLowerCase().includes(q));
  document.getElementById('slangResult').textContent=`显示 ${{rows.length}} / ${{BLACKWORDS.length}}`;
  document.getElementById('slangCards').innerHTML=rows.map(x=>`<article class="slang-card"><h3>${{esc(x.term||'')}}</h3><p>${{esc(x.canonical_meaning||'暂未形成稳定释义')}}</p>${{x.context?`<small>${{esc(x.context)}}</small>`:''}}</article>`).join('')
}}
function openSource(href){{document.getElementById('sourceFrame').src=href;document.getElementById('sourceDrawer').classList.add('open');document.getElementById('drawerBackdrop').classList.add('open')}}
function closeSource(){{document.getElementById('sourceDrawer').classList.remove('open');document.getElementById('drawerBackdrop').classList.remove('open');setTimeout(()=>document.getElementById('sourceFrame').src='about:blank',160)}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeSource()}});
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.nav button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===b.dataset.view));window.scrollTo({{top:0,behavior:'smooth'}})}});
document.getElementById('newSearch').addEventListener('input',()=>{{newPage=1;renderNew()}});
document.getElementById('newPrev').onclick=()=>{{newPage--;renderNew();window.scrollTo({{top:150,behavior:'smooth'}})}};
document.getElementById('newNext').onclick=()=>{{newPage++;renderNew();window.scrollTo({{top:150,behavior:'smooth'}})}};
document.getElementById('kbSearch').addEventListener('input',renderKnowledge);
document.getElementById('slangSearch').addEventListener('input',renderSlang);
renderNew();renderKnowledge();renderDossier();renderSlang();void syncFormalUnitDecisions();
</script>
</body>
</html>'''
