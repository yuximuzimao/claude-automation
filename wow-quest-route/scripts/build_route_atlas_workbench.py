from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/routes/route-atlas-workbench.html"
START = "/* ROUTE_DATA_START */"
END = "/* ROUTE_DATA_END */"
HUD_ACTIONS_START = "/* HUD_GROUP_ACTIONS_START */"
HUD_ACTIONS_END = "/* HUD_GROUP_ACTIONS_END */"
RESUME_START = "/* ROUTE_RESUME_START */"
RESUME_END = "/* ROUTE_RESUME_END */"
SEMANTIC_HUD_STANDARD = "semantic-hud-v45"
# These routes predate the v45 HUD publication contract and are being migrated separately.
# Any newly introduced route key must opt into the v45 contract instead of silently falling back
# to the legacy plaintext HUD.
LEGACY_PLAINTEXT_ROUTE_KEYS: set[str] = set()
TASK_NAME_RE = re.compile(r"《([^》]+)》")
HUD_ACTIONS_PATCH = "\n" + HUD_ACTIONS_START + r"""
const routeAtlasInfoWithFullActions=info;

(function installRouteAtlasSemanticPrototype(){
  if(!document.getElementById('raSemanticPrototypeStyle')){
    const style=document.createElement('style');
    style.id='raSemanticPrototypeStyle';
    style.textContent=`
      .hud.ra-semantic-panel{max-height:calc(100% - 24px);overflow:hidden!important;display:flex;flex-direction:column;box-sizing:border-box}
      .hud.ra-semantic-panel .hudbody{min-height:0;overflow-y:auto!important;overscroll-behavior:contain;scrollbar-gutter:stable;scrollbar-width:thin}
      #hudAction.ra-semantic-hud{white-space:normal!important;line-height:1.68;margin-top:4px}
      #hudAction .ra-line,.stepsCard .ra-step-semantic .ra-line{display:block;margin:2px 0;color:#f2f2f2}
      #hudAction .ra-line.ra-do,.stepsCard .ra-step-semantic .ra-line.ra-do{padding-left:14px;margin-top:0;margin-bottom:6px}
      #hudAction .ra-line.ra-do-inline{padding-left:0;margin-top:6px;margin-bottom:5px}
      #hudAction .ra-inline-sep{color:#b9bec5}
      #hudAction .ra-point-anchor,.stepsCard .ra-step-semantic .ra-point-anchor{margin-top:8px;margin-bottom:1px}
      #hudAction .ra-point-anchor:first-child,.stepsCard .ra-step-semantic .ra-point-anchor:first-child{margin-top:0}
      .ra-location{font-weight:400!important;color:#9fcff5!important}
      .ra-npc{font-weight:700!important;color:#f2f2f2!important}
      .ra-task{font-weight:600!important;text-decoration:underline!important;text-decoration-thickness:1px!important;text-underline-offset:2px!important}
      .ra-task.ra-turnin{color:#82d59a!important}
      .ra-task.ra-accept{color:#ffd66b!important}
      .ra-task.ra-do-task{color:#79baff!important}
      .ra-verb{font:inherit;font-weight:400;color:inherit;padding:0;border:0;background:none}
      .ra-arrow{display:inline-block;margin:0 4px;color:#b9bec5!important}
      .ra-branch{display:inline-block;width:18px;font-size:1.08em;font-weight:800;color:#b9bec5!important}
      .ra-transport{font-weight:750;color:#c9d6e3!important}
      .ra-system-action{display:inline-block;font-weight:700}
      .ra-flightpoint,.ra-flightpath{color:#7dd3fc!important}
      .ra-hearthstone{color:#fdba74!important}
      .stepsCard .step .sm{display:none!important}
      .stepsCard .ra-step-semantic{display:none!important}
      .stepsCard .ra-step-note{display:none!important}
      .ra-semantic-notes{display:block!important;margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.18);white-space:normal!important}
      .ra-note-heading{display:block!important;font-weight:850;color:#fff;margin-bottom:3px}
      .ra-note-block{display:block!important;width:100%;padding:7px 0 8px;margin:0;clear:both}
      .ra-note-block+.ra-note-block{border-top:1px dashed rgba(255,255,255,.16);margin-top:2px}
      .ra-note-task{display:block!important;font-weight:800;color:#f0e4bd;margin:0 0 2px}
      .ra-note-text{display:block!important;line-height:1.62;color:#eee}
      .ra-fivebox-line{display:block!important;margin-top:5px;padding-top:5px;border-top:1px solid rgba(255,214,107,.22);line-height:1.55;color:#eee}
      .ra-key{font-weight:400;color:#ff8f8f}
      .ra-shared{font-weight:700;color:#9fd8c5}
      .ra-not-shared{font-weight:700;color:#f0b66e}
      .ra-danger{font-weight:400;color:#ff8f8f}
      .ra-pending{font-weight:850;color:#ffd66b}
      .ra-note-meta{margin-top:2px;font-size:.93em;color:#ddd}
    `;
    document.head.appendChild(style);
  }
})();
function raFindNoteBox(actionEl,create){
  const fallback=document.querySelector('[data-ra-semantic-fallback="1"]');
  if(fallback)return fallback;
  let root=actionEl.parentElement;
  for(let depth=0;root&&depth<4;depth++,root=root.parentElement){
    const nodes=[...root.querySelectorAll('div,p,section')];
    const hit=nodes.find(node=>{
      if(node===actionEl||node.contains(actionEl))return false;
      const text=(node.textContent||'').trim();
      return text.startsWith('备注：')||text.startsWith('备注:');
    });
    if(hit)return hit;
  }
  if(!create)return null;
  const box=document.createElement('div');
  box.dataset.raSemanticFallback='1';
  actionEl.insertAdjacentElement('afterend',box);
  return box;
}
function raPrototypeActionHtml(){
  return `
    <div class="ra-line"><span class="ra-location">怨毒镇</span>·<span class="ra-npc">高级执行官</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">炸毁弩炮</span>、<span class="ra-task ra-turnin">日常计划</span>、<span class="ra-task ra-turnin">解决方案</span>、<span class="ra-task ra-turnin">谴责</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">新壁炉谷的卧底</span>、<span class="ra-task ra-accept">水火之灾</span></div>
    <div class="ra-line"><span class="ra-npc">斯古莉</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">新壁炉谷的卧底</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">祈祷之书</span></div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">祈祷之书</span></div>
    <div class="ra-line"><span class="ra-npc">斯古莉</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">祈祷之书</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">完美的伪装</span></div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">完美的伪装</span></div>
    <div class="ra-line"><span class="ra-npc">斯古莉</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">完美的伪装</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">狼狈不堪</span></div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">狼狈不堪</span></div>`;
}
function raPrototypeNoteHtml(){
  return `
    <div class="ra-note-heading">备注</div>
    <div class="ra-note-block">
      <div class="ra-note-task">《祈祷之书》</div>
      <div class="ra-note-text"><span class="ra-location">小礼拜堂</span> 约 (69,76)；斯崔特主教只杀一次，同一具尸体五号分别拾取祈祷之书。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《完美的伪装》</div>
      <div class="ra-note-text"><span class="ra-shared">共享：</span>主控对 <span class="ra-npc">黑鸦祭司</span> 使用一次女妖魔镜即可五号完成；<span class="ra-danger">不要直接击杀</span>。随后需要祭司伪装时，直接找斯古莉对话变身。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《狼狈不堪》</div>
      <div class="ra-note-text"><span class="ra-danger">先锋军骑士会识破伪装</span>；<span class="ra-shared">共享：</span>主控进入 <span class="ra-location">修道院</span>，沿螺旋楼梯上 <span class="ra-key">顶层</span> 敲钟 → 回 <span class="ra-key">一层</span> 与高阶修士交谈 → 出门跟随，直到事件完成。</div>
    </div>`;
}
function raGrizzlyStep1ActionHtml(){
  return `
    <div class="ra-line"><span class="ra-location">征服堡</span>：从龙骨荒野沿东/东南公路过河进入征服堡</div>
    <div class="ra-line"><span class="ra-npc">征服者克雷娜</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">前往征服堡，自求多福吧！</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">征服者的指派</span></div>
    <div class="ra-line"><span class="ra-npc">纳兹格利姆中士</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">征服者的指派</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">缚焰者的秘密</span>、<span class="ra-task ra-accept">显示力量</span></div>
    <div class="ra-line"><span class="ra-npc">皮货商人休尼克</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">灰狼的毛皮</span></div>
    <div class="ra-line"><span class="ra-npc">粮食商人洛克兰</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">赚外快</span></div>
    <div class="ra-line">五号开启<span class="ra-location">征服堡</span>飞行点；炉石绑定<span class="ra-location">征服堡</span></div>
    <div class="ra-line"><span class="ra-location">征服堡南侧</span><span class="ra-arrow">→</span><span class="ra-location">沃德伦</span>：沿道路推进</div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">赚外快</span>、<span class="ra-task ra-do-task">灰狼的毛皮</span></div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">缚焰者的秘密</span>、<span class="ra-task ra-do-task">显示力量</span></div>
    <div class="ra-line"><span class="ra-npc">粮食商人洛克兰</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">赚外快</span></div>
    <div class="ra-line"><span class="ra-npc">皮货商人休尼克</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">灰狼的毛皮</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">替代品</span></div>
    <div class="ra-line"><span class="ra-npc">纳兹格利姆中士</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">缚焰者的秘密</span>、<span class="ra-task ra-turnin">显示力量</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">沃德伦的领主</span></div>
    <div class="ra-line"><span class="ra-location">风险湾</span>·<span class="ra-npc">古图尔</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">寻找溶解剂</span></div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span>进入仓库拾取 Element 115</div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span>立即原路返回<span class="ra-npc">古图尔</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">寻找溶解剂</span></div>
    <div class="ra-line"><span class="ra-location">沃德伦</span>：骑乘任务龙</div>
    <div class="ra-line ra-do"><span class="ra-branch">↳</span><span class="ra-verb">做</span> <span class="ra-task ra-do-task">沃德伦的领主</span>：击杀沃德伦领主</div>
    <div class="ra-line">完成后直接返回<span class="ra-location">征服堡</span></div>
    <div class="ra-line"><span class="ra-npc">纳兹格利姆中士</span><span class="ra-arrow">→</span><span class="ra-verb">交</span> <span class="ra-task ra-turnin">沃德伦的领主</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">前往欧尼瓦营地</span></div>
    <div class="ra-line"><span class="ra-npc">征服者克雷娜</span><span class="ra-arrow">→</span><span class="ra-verb">接</span> <span class="ra-task ra-accept">我的敌人的朋友</span></div>`;
}
function raGrizzlyStep1NoteHtml(){
  return `
    <div class="ra-note-heading">备注</div>
    <div class="ra-note-block">
      <div class="ra-note-task">《赚外快》《灰狼的毛皮》</div>
      <div class="ra-note-text">鹿和狼分布在征服堡南侧道路两边；任务物为个人掉落，五号分别拾取。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《缚焰者的秘密》</div>
      <div class="ra-note-text">任务物为个人掉落，五号分别拾取。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《显示力量》</div>
      <div class="ra-note-text"><span class="ra-shared">共享：</span>击杀进度五号共享。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《寻找溶解剂》</div>
      <div class="ra-note-text">拾取 Element 115 后开始<span class="ra-key">短时限返程</span>；<span class="ra-danger">立即原路返回</span>，尽量不进战斗，坐骑/移速增益不能代替快速返程。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task ra-pending">五开待实测</div>
      <div class="ra-note-text">Element 115必须逐号拾取的概率很高；首组确认是否能同一刷新点连续五号取、以及返程窗口是否分别计时。</div>
    </div>
    <div class="ra-note-block">
      <div class="ra-note-task">《沃德伦的领主》</div>
      <div class="ra-note-text">载具战贴近目标；技能冷却结束就优先使用高伤技能。</div>
    </div>`;
}
function raApplySemanticStepCards(){
  document.querySelectorAll('.stepsCard [data-ra-step-note="1"],.stepsCard [data-ra-step-semantic="1"]').forEach(node=>node.remove());
}

info=function(){
  routeAtlasInfoWithFullActions();
  raApplySemanticStepCards();
  setTimeout(raApplySemanticStepCards,0);
  const legacyFivebox=document.getElementById('hudFivebox');
  if(legacyFivebox)legacyFivebox.style.display='';
  const runtimeGr=G[cur],semanticGr=route()?.stepGroups?.[cur],el=document.getElementById('hudAction');
  if(!runtimeGr||!el)return;
  const gr=semanticGr||runtimeGr;
  const hudPanel=el.closest('.hud');
  if(hudPanel)hudPanel.classList.remove('ra-semantic-panel');
  document.querySelectorAll('[data-ra-semantic-fallback="1"]').forEach(node=>node.remove());
  el.classList.remove('ra-semantic-hud');
  const lines=S.slice(runtimeGr.start,runtimeGr.end+1).map(point=>`${point.label}：${point.action}`).filter(Boolean);
  if(typeof gr.actionHtml==='string'&&gr.actionHtml.trim()){
    if(legacyFivebox){legacyFivebox.textContent='';legacyFivebox.style.display='none'}
    if(hudPanel)hudPanel.classList.add('ra-semantic-panel');
    el.classList.add('ra-semantic-hud');
    el.innerHTML=gr.actionHtml;
    const note=raFindNoteBox(el,true);
    if(typeof gr.noteHtml==='string'&&gr.noteHtml.trim()){
      note.style.removeProperty('display');
      note.classList.add('ra-semantic-notes');
      note.dataset.raSemantic='1';
      note.innerHTML=gr.noteHtml;
    }else{
      note.innerHTML='';
      note.classList.remove('ra-semantic-notes');
      delete note.dataset.raSemantic;
      if(note.id==='hudNote')note.style.display='none';
      else note.remove();
    }
    return;
  }
  if(gr.title==='新壁炉谷：祈祷之书 → 完美伪装 → 狼狈不堪'){
    if(hudPanel)hudPanel.classList.add('ra-semantic-panel');
    el.classList.add('ra-semantic-hud');
    el.innerHTML=raPrototypeActionHtml();
    const note=raFindNoteBox(el,true);
    note.classList.add('ra-semantic-notes');
    note.dataset.raSemantic='1';
    note.innerHTML=raPrototypeNoteHtml();
    return;
  }
  if(gr.title==='征服堡 → 沃德伦 → 风险湾 → 沃德伦领主'){
    if(hudPanel)hudPanel.classList.add('ra-semantic-panel');
    el.classList.add('ra-semantic-hud');
    el.innerHTML=raGrizzlyStep1ActionHtml();
    const note=raFindNoteBox(el,true);
    note.classList.add('ra-semantic-notes');
    note.dataset.raSemantic='1';
    note.innerHTML=raGrizzlyStep1NoteHtml();
    return;
  }
  const note=raFindNoteBox(el,false);
  if(note&&note.dataset.raSemantic==='1'){
    note.classList.remove('ra-semantic-notes');
    delete note.dataset.raSemantic;
  }
  el.style.whiteSpace='pre-line';
  el.textContent=lines.join('\n');
};
if(Array.isArray(G)&&G.length)info();
""" + HUD_ACTIONS_END + "\n"

RESUME_PATCH = "\n" + RESUME_START + r"""
(function installRouteAtlasResume(){
  const STEP_PREFIX='route-atlas:last-step:';
  const LAST_ROUTE='route-atlas:last-route';
  const originalInfo=info;
  let restoring=true;
  function currentRouteKey(){
    try{
      const current=route();
      const hit=Object.entries(ROUTES).find(([,value])=>value===current);
      if(hit)return hit[0];
      return current?.displayName||current?.title||'default';
    }catch(_){
      return 'default';
    }
  }
  function savedStep(routeKey){
    try{
      const saved=Number.parseInt(localStorage.getItem(STEP_PREFIX+routeKey)||'',10);
      return Number.isInteger(saved)?saved:null;
    }catch(_){
      return null;
    }
  }
  function restoreStep(){
    const saved=savedStep(currentRouteKey());
    if(saved!==null&&Array.isArray(G)&&G.length){
      cur=Math.max(0,Math.min(saved,G.length-1));
    }
  }
  function saveState(){
    try{
      const key=currentRouteKey();
      localStorage.setItem(LAST_ROUTE,key);
      localStorage.setItem(STEP_PREFIX+key,String(cur));
    }catch(_){}
  }
  function activateRoute(routeKey){
    if(!routeKey||!ROUTES[routeKey]||routeKey===currentRouteKey())return;
    const label=ROUTES[routeKey].displayName||ROUTES[routeKey].title||'';
    const nodes=[...document.querySelectorAll('button,[role="tab"],option')];
    const hit=nodes.find(node=>
      node.dataset?.route===routeKey||
      node.dataset?.key===routeKey||
      node.dataset?.routeKey===routeKey||
      node.value===routeKey||
      (label&&(node.textContent||'').trim()===label)
    );
    if(!hit)return;
    if(hit.tagName==='OPTION'&&hit.parentElement){
      hit.parentElement.value=hit.value;
      hit.parentElement.dispatchEvent(new Event('change',{bubbles:true}));
    }else{
      hit.click();
    }
  }
  info=function(){
    originalInfo();
    if(!restoring)saveState();
  };
  function resume(){
    let lastRoute='';
    try{lastRoute=localStorage.getItem(LAST_ROUTE)||'';}catch(_){}
    activateRoute(lastRoute);
    restoreStep();
    originalInfo();
    restoring=false;
    saveState();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>setTimeout(resume,0),{once:true});
  }else{
    setTimeout(resume,0);
  }
})();
""" + RESUME_END + "\n"


def main() -> None:
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    if not routes:
        raise SystemExit("workbench route set is empty")

    # Route-level legend copy has no live-action value. Per-step transport/mechanic
    # instructions belong in the step actions/notes, so keep this HUD slot empty.
    for route in routes.values():
        route["legend"] = ""

    for key, route in routes.items():
        image = ROOT / "data/routes" / route["image"]
        if not image.exists():
            raise SystemExit(f"missing map asset for {key}: {route['image']}")
        if not route.get("points"):
            raise SystemExit(f"route has no points: {key}")
        hearth = route.get("hearthChain")
        if not isinstance(hearth, list) or not hearth or not all(isinstance(value, str) and value for value in hearth):
            raise SystemExit(f"route hearthChain missing/invalid: {key}")
        timing = route.get("timing")
        if not isinstance(timing, dict) or not isinstance(timing.get("centerMinutes"), (int, float)):
            raise SystemExit(f"route timing missing: {key}")
        timing_range = timing.get("rangeMinutes")
        if not isinstance(timing_range, list) or len(timing_range) != 2:
            raise SystemExit(f"route timing range missing: {key}")
        groups = route.get("stepGroups")
        if not isinstance(groups, list) or not groups:
            raise SystemExit(f"route stepGroups missing: {key}")
        requires_semantic_hud = key not in LEGACY_PLAINTEXT_ROUTE_KEYS
        if requires_semantic_hud and route.get("uiStandard") != SEMANTIC_HUD_STANDARD:
            raise SystemExit(
                f"new route must declare uiStandard={SEMANTIC_HUD_STANDARD}: {key}"
            )
        for index, group in enumerate(groups, 1):
            if requires_semantic_hud:
                action_html = group.get("actionHtml")
                if not isinstance(action_html, str) or not action_html.strip():
                    raise SystemExit(f"v45 semantic HUD actionHtml missing: {key} step {index}")
                if "《" in action_html or "》" in action_html:
                    raise SystemExit(f"v45 actionHtml must remove task-name brackets: {key} step {index}")
                start_index = group.get("start")
                end_index = group.get("end")
                if not isinstance(start_index, int) or not isinstance(end_index, int):
                    raise SystemExit(f"v45 step range missing: {key} step {index}")
                plain_tasks = {
                    task_name
                    for point in route["points"][start_index : end_index + 1]
                    for task_name in TASK_NAME_RE.findall(str(point[3]))
                }
                semantic_text = re.sub(r"<[^>]+>", "", action_html)
                missing_semantic_tasks = sorted(task for task in plain_tasks if task not in semantic_text)
                if missing_semantic_tasks:
                    raise SystemExit(
                        f"v45 actionHtml lost player action tasks: {key} step {index}: {missing_semantic_tasks}"
                    )
            step_timing = group.get("timing")
            if not isinstance(step_timing, dict) or not isinstance(step_timing.get("centerMinutes"), (int, float)):
                raise SystemExit(f"step timing missing: {key} step {index}")
            step_range = step_timing.get("rangeMinutes")
            if not isinstance(step_range, list) or len(step_range) != 2:
                raise SystemExit(f"step timing range missing: {key} step {index}")
        if route.get("badgeTitle"):
            raise SystemExit(f"route top-right card must not have a title: {key}")
        if "炉石：" not in str(route.get("badge", "")) or "预计总时间：" not in str(route.get("badge", "")):
            raise SystemExit(f"route top-right hearth/timing card contract broken: {key}")

    html = OUT.read_text(encoding="utf-8")
    payload = json.dumps(routes, ensure_ascii=False, separators=(",", ":"))
    prefix = f"const ROUTES={START}"
    start = html.find(prefix)
    if start < 0:
        raise SystemExit("route data start marker not found")
    data_start = start + len(prefix)
    data_end = html.find(END, data_start)
    if data_end < 0:
        raise SystemExit("route data end marker not found")
    html = html[:data_start] + payload + html[data_end:]

    for patch_start, patch_end, error_text in (
        (HUD_ACTIONS_START, HUD_ACTIONS_END, "HUD group-actions end marker not found"),
        (RESUME_START, RESUME_END, "route-resume end marker not found"),
    ):
        existing_patch_start = html.find(patch_start)
        if existing_patch_start >= 0:
            existing_patch_end = html.find(patch_end, existing_patch_start)
            if existing_patch_end < 0:
                raise SystemExit(error_text)
            existing_patch_end += len(patch_end)
            html = html[:existing_patch_start] + html[existing_patch_end:]
    script_close = html.rfind("</script>")
    if script_close < 0:
        raise SystemExit("workbench closing script tag not found")
    html = html[:script_close] + HUD_ACTIONS_PATCH + RESUME_PATCH + html[script_close:]

    # User-visible route text must not expose internal A/C/T quest-id notation.
    visible = "\n".join(
        str(value)
        for route in routes.values()
        for point in route.get("points", [])
        for value in point[2:6]
    )
    if re.search(r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}", visible):
        raise SystemExit("internal quest action token leaked into workbench text")
    if "function fmtRouteMinutes" not in html or "本段预计：约" not in html:
        raise SystemExit("Route Atlas timing HUD contract missing from HTML")

    OUT.write_text(html, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
