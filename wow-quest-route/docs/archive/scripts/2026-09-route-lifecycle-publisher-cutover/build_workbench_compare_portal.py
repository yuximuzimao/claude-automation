from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROUTES=ROOT/"data/routes"
DIFF=json.loads((ROUTES/"workbench-compare/workbench-diff.json").read_text(encoding="utf-8"))
keys=list(DIFF["routes"])
options="\n".join(
    '<option value="'+k+'">'+DIFF["routes"][k]["summary"]["display_name_new"]+'</option>'
    for k in keys
)
summary={
    k:{
        "display":v["summary"]["display_name_new"],
        "old_steps":v["summary"]["step_count_old"],
        "new_steps":v["summary"]["step_count_new"],
        "titles_same":v["summary"]["step_title_sequence_same"],
        "task_changed":v["summary"]["steps_task_sequence_changed"],
        "old_only":v["summary"]["steps_old_task_only_total"],
        "new_only":v["summary"]["steps_new_task_only_total"],
        "old_map":v["summary"]["map_old"],
        "new_map":v["summary"]["map_new"],
    } for k,v in DIFF["routes"].items()
}
template="""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Route Atlas 旧版 / 新版替代验收</title>
<style>
*{box-sizing:border-box}html,body{margin:0;background:#101216;color:#e7e9ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:20;background:#171a20;border-bottom:1px solid #39414e;padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
header strong{margin-right:10px}select,input,button,a.btn{background:#242a33;color:#eee;border:1px solid #4d5969;border-radius:6px;padding:7px 9px;text-decoration:none}
button{cursor:pointer}#syncStatus{color:#aeb8c6;font-size:12px}
.frames{display:grid;grid-template-columns:1fr 1fr;height:67vh;border-bottom:1px solid #3a414c}
.pane{display:flex;flex-direction:column;min-width:0}.pane:first-child{border-right:1px solid #4b5564}
.label{height:31px;display:flex;align-items:center;justify-content:center;background:#1d222a;font-weight:700;font-size:13px}
iframe{border:0;width:100%;flex:1;background:#fff}
.detail{padding:18px;max-width:1800px;margin:auto}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin-bottom:16px}
.card{background:#181c22;border:1px solid #343c48;border-radius:8px;padding:12px}.card b{display:block;margin-bottom:6px}
.shots{display:grid;grid-template-columns:1fr 1fr;gap:12px}.shot{background:#181c22;border:1px solid #343c48;border-radius:8px;padding:8px}.shot img{display:block;width:100%;height:auto;border-radius:4px}
.warn{color:#f0c36a}.ok{color:#87d78a}.muted{color:#9ba6b5;font-size:13px}
@media(max-width:900px){.frames,.shots{grid-template-columns:1fr}.frames{height:auto}iframe{height:70vh}}
</style></head>
<body>
<header>
<strong>Route Atlas 替代验收</strong>
<label>路线 <select id="route">__OPTIONS__</select></label>
<label>步骤 <input id="step" type="number" min="1" value="1" style="width:72px"></label>
<button id="apply">同步旧/新</button><button id="prev">← 同步上一步</button><button id="next">同步下一步 →</button>
<a class="btn" href="route-atlas-workbench.html" target="_blank">单独打开旧版</a>
<a class="btn" href="route-atlas-workbench-next.html" target="_blank">单独打开新版</a>
<span id="syncStatus">等待两个页面加载…</span>
</header>
<div class="frames">
<section class="pane"><div class="label">旧正式版（只读比较）</div><iframe id="oldFrame" src="route-atlas-workbench.html"></iframe></section>
<section class="pane"><div class="label">新 Publisher 候选版（worktree）</div><iframe id="newFrame" src="route-atlas-workbench-next.html"></iframe></section>
</div>
<section class="detail">
<h2 id="detailTitle"></h2>
<p class="muted">上方是真实页面；下方两张图是同一路线 Step 1 的 1440×1100 Chrome 截图，便于整体视觉对照。</p>
<div class="metrics" id="metrics"></div>
<div class="shots"><div class="shot"><b>旧版首屏</b><img id="oldShot"></div><div class="shot"><b>新版首屏</b><img id="newShot"></div></div>
</section>
<script>
const SUMMARY=__SUMMARY__;
const routeEl=document.getElementById('route'),stepEl=document.getElementById('step'),statusEl=document.getElementById('syncStatus');
const oldF=document.getElementById('oldFrame'),newF=document.getElementById('newFrame');
function clampStep(key,n){const s=SUMMARY[key];return Math.max(1,Math.min(Math.min(s.old_steps,s.new_steps),Number(n)||1))}
function updateDetail(){
 const key=routeEl.value,s=SUMMARY[key];
 document.getElementById('detailTitle').textContent=s.display+'｜'+key;
 const cls=s.titles_same?'ok':'warn';
 document.getElementById('metrics').innerHTML=
  '<div class="card"><b>步骤数</b>'+s.old_steps+' → '+s.new_steps+'</div>'+
  '<div class="card"><b>步骤标题序列</b><span class="'+cls+'">'+(s.titles_same?'一致':'存在重排/增删')+'</span></div>'+
  '<div class="card"><b>同索引任务序列变化</b>'+s.task_changed+' 段</div>'+
  '<div class="card"><b>任务引用差异计数</b>旧独有 '+s.old_only+' / 新独有 '+s.new_only+'</div>'+
  '<div class="card"><b>地图线段</b>'+s.old_map.rendered_lines+' → '+s.new_map.rendered_lines+'</div>'+
  '<div class="card"><b>地图标签</b>'+s.old_map.rendered_labels+' → '+s.new_map.rendered_labels+'</div>';
 document.getElementById('oldShot').src='workbench-compare/old/'+key+'.png';
 document.getElementById('newShot').src='workbench-compare/new/'+key+'.png';
}
function sync(){
 const key=routeEl.value,n=clampStep(key,stepEl.value);stepEl.value=n;updateDetail();
 try{
   const od=oldF.contentDocument;
   const zone=od.getElementById('zone');zone.value=key;zone.dispatchEvent(new Event('change',{bubbles:true}));
   const os=od.querySelectorAll('#steps .step');if(os[n-1])os[n-1].click();
   const nd=newF.contentDocument;
   const idx=Object.keys(SUMMARY).indexOf(key),routeSelect=nd.getElementById('routeSelect');
   routeSelect.value=String(idx);routeSelect.dispatchEvent(new Event('change',{bubbles:true}));
   const ns=nd.querySelectorAll('#steps .step');if(ns[n-1])ns[n-1].click();
   statusEl.textContent='已同步：'+SUMMARY[key].display+' · Step '+n;statusEl.className='ok';
 }catch(e){statusEl.textContent='同步失败：'+e;statusEl.className='warn';}
}
document.getElementById('apply').onclick=sync;
document.getElementById('prev').onclick=()=>{stepEl.value=clampStep(routeEl.value,Number(stepEl.value)-1);sync()};
document.getElementById('next').onclick=()=>{stepEl.value=clampStep(routeEl.value,Number(stepEl.value)+1);sync()};
routeEl.onchange=()=>{stepEl.value=1;sync()};
let loaded=0;function ready(){loaded++;if(loaded===2)sync()}oldF.onload=ready;newF.onload=ready;
updateDetail();
</script></body></html>"""
html=template.replace("__OPTIONS__",options).replace("__SUMMARY__",json.dumps(summary,ensure_ascii=False,separators=(",",":")))
path=ROUTES/"route-atlas-workbench-compare.html"
path.write_text(html,encoding="utf-8")
print(path)
