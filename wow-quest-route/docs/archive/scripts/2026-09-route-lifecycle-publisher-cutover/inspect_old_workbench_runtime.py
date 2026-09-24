from __future__ import annotations
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=(ROOT/"data/routes/route-atlas-workbench.html").as_uri()
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=["--allow-file-access-from-files"])
        page=await b.new_page(viewport={"width":1440,"height":1100})
        await page.goto(URL,wait_until="load")
        await page.wait_for_timeout(500)
        out=await page.evaluate("""() => {
          const names=Object.getOwnPropertyNames(window).filter(n=>/^(cur|G|S|route|info|next|prev|set|draw|render|go|switch|show|select|load)/i.test(n));
          const vals={};
          for(const n of names.slice(0,200)){
            try{
              const v=window[n];
              vals[n]=typeof v==='function'?'function':Array.isArray(v)?('array:'+v.length):typeof v==='object'?(v===null?'null':'object'):String(v).slice(0,120);
            }catch(e){vals[n]='ERR'}
          }
          const controls=[...document.querySelectorAll('button,[role="tab"],select,option,input')].map((n,i)=>({
            i,tag:n.tagName,id:n.id||'',cls:n.className||'',text:(n.textContent||'').trim().slice(0,100),
            value:n.value??'',type:n.type??'',checked:n.checked??null,
            dataset:{...n.dataset}
          }));
          const routeEntries=typeof ROUTES!=='undefined'?Object.entries(ROUTES).map(([k,v])=>({key:k,displayName:v.displayName,title:v.title,steps:(v.stepGroups||[]).length,points:(v.points||[]).length})):null;
          return {names:vals,controls,routeEntries,cur:typeof cur!=='undefined'?cur:null,gLen:typeof G!=='undefined'&&Array.isArray(G)?G.length:null,sLen:typeof S!=='undefined'&&Array.isArray(S)?S.length:null};
        }""")
        print(json.dumps(out,ensure_ascii=False,indent=2))
        await b.close()
asyncio.run(main())
