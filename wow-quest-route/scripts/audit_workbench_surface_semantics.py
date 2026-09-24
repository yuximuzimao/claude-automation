from __future__ import annotations
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=(ROOT/"data/routes/route-atlas-workbench.html").as_uri()
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=["--allow-file-access-from-files"])
        page=await b.new_page(viewport={"width":1440,"height":1100})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        await page.goto(URL,wait_until="load")
        report=await page.evaluate("""() => {
          const issues=[];
          const counts={routes:ROUTES.length,steps:0,lines:0,task_refs:0,notes:0,kinds:{},tags:{}};
          const routeActionColors={};
          const expectedRouteActionColors={open_flight_point:'rgb(255, 159, 104)',bind_hearth:'rgb(207, 156, 255)'};
          const expectedTag=p=>p.badge==='shared'?'共享':p.badge==='not_shared'?'不共享':p.badge==='sequential_loot'?'依次拾取':p.badge==='special'?'特殊':p.pending?'待实测':'';
          for(let ri=0;ri<ROUTES.length;ri++){
            setRoute(ri);
            const r=ROUTES[ri];
            for(let si=0;si<r.steps.length;si++){
              setStep(si); counts.steps++;
              const s=r.steps[si];
              const domLines=[...document.querySelectorAll('#hudBody > .line')];
              if(domLines.length!==(s.lines||[]).length){
                issues.push({type:'line_count',route:r.display.publish_key,step:si+1,expected:(s.lines||[]).length,actual:domLines.length});
                continue;
              }
              const presentationByTask=new Map((s.task_presentations||[]).map(p=>[String(p.task_id),p]));
              (s.lines||[]).forEach((line,li)=>{
                counts.lines++;
                const exp=(line.task_refs||[]).map(x=>({text:'《'+x.name+'》',kind:x.kind,task_id:String(x.task_id)}));
                const taskNodes=[...domLines[li].querySelectorAll('.task')];
                const got=taskNodes.map(x=>({text:x.textContent,kind:[...x.classList].find(c=>c!=='task')||''}));
                counts.task_refs+=exp.length;
                exp.forEach(x=>counts.kinds[x.kind]=(counts.kinds[x.kind]||0)+1);
                if(JSON.stringify(exp.map(({text,kind})=>({text,kind})))!==JSON.stringify(got)){
                  issues.push({type:'task_ref_dom',route:r.display.publish_key,step:si+1,line:li+1,text:line.text,expected:exp,actual:got});
                }
                if(line.type==='route_action'&&expectedRouteActionColors[line.action_kind]&&!routeActionColors[line.action_kind]){
                  routeActionColors[line.action_kind]=getComputedStyle(domLines[li]).color;
                }
                exp.forEach((x,ti)=>{
                  const tag=expectedTag(presentationByTask.get(x.task_id)||{});
                  if(tag)counts.tags[tag]=(counts.tags[tag]||0)+1;
                  const node=taskNodes[ti];
                  const prev=node?.previousElementSibling;
                  const gotTag=prev?.classList?.contains('taskTag')?(prev.textContent||'').trim():'';
                  if(tag!==gotTag){
                    issues.push({type:'inline_tag_text',route:r.display.publish_key,step:si+1,line:li+1,task:x.text,expected:tag,actual:gotTag});
                  }
                });
              });
              const expNotes=(s.task_presentations||[]).filter(p=>p.note_visible!==false&&String(p.note||'').trim());
              const gotNotes=[...document.querySelectorAll('#hudBody .notes .note')];
              const noteTitle=document.querySelector('#hudBody .notes .notesTitle');
              counts.notes+=expNotes.length;
              if(expNotes.length!==gotNotes.length){
                issues.push({type:'note_count',route:r.display.publish_key,step:si+1,expected:expNotes.length,actual:gotNotes.length});
              }
              if(expNotes.length&&noteTitle?.textContent?.trim()!=='备注'){
                issues.push({type:'note_title_missing',route:r.display.publish_key,step:si+1,actual:noteTitle?.textContent||''});
              }
              if(!expNotes.length&&noteTitle){
                issues.push({type:'note_title_without_notes',route:r.display.publish_key,step:si+1});
              }
              expNotes.forEach((p,ni)=>{
                const node=gotNotes[ni];
                if(!node)return;
                if(node.querySelector('.tag')){
                  issues.push({type:'tag_leaked_into_note',route:r.display.publish_key,step:si+1,task:p.name||p.task_id});
                }
                const name=String(p.name||p.task_id);
                const full=(node.textContent||'').trim();
                const prefix='《'+name+'》：';
                if(!full.startsWith(prefix)){
                  issues.push({type:'note_task_name',route:r.display.publish_key,step:si+1,task:name,actual:full});
                }
                const body=full.slice(prefix.length);
                if(body.includes('《'+name+'》')){
                  issues.push({type:'note_repeats_own_task_name',route:r.display.publish_key,step:si+1,task:name,actual:full});
                }
                if(/已实测|已验证|经审计|实跑确认|首组实跑|第二组实跑/.test(body)){
                  issues.push({type:'note_process_language',route:r.display.publish_key,step:si+1,task:name,actual:full});
                }
              });
            }
          }
          setRoute(0);
          const colorSamples={};
          for(const kind of ['accept','objective','turnin']){
            const n=document.querySelector('.task.'+kind);
            if(n){const s=getComputedStyle(n);colorSamples[kind]={color:s.color,textDecoration:s.textDecorationLine}}
          }
          if(new Set(Object.values(colorSamples).map(x=>x.color)).size!==Object.keys(colorSamples).length){
            issues.push({type:'task_colors_not_distinct',samples:colorSamples});
          }
          for(const [kind,expected] of Object.entries(expectedRouteActionColors)){
            if(routeActionColors[kind]!==expected){
              issues.push({type:'route_action_color_wrong',kind,expected,actual:routeActionColors[kind]||null});
            }
          }
          return {counts,colorSamples,routeActionColors,issues};
        }""")
        report["page_errors"]=errors
        print(json.dumps(report,ensure_ascii=False,indent=2))
        await b.close()

asyncio.run(main())
