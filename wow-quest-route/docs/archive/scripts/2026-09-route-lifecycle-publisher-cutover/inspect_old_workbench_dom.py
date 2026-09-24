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
        await page.select_option("#zone","hellfire")
        await page.wait_for_timeout(300)
        out=await page.evaluate("""() => ({
          globals:{
            cur: typeof cur==='undefined'?null:cur,
            G: typeof G==='undefined'?null:(Array.isArray(G)?G.length:typeof G),
            S: typeof S==='undefined'?null:(Array.isArray(S)?S.length:typeof S),
            route: typeof route,
            info: typeof info,
            draw: typeof draw,
            render: typeof render,
            setStep: typeof setStep,
            go: typeof go,
            step: typeof step
          },
          ids:[...document.querySelectorAll('[id]')].map(n=>({id:n.id,tag:n.tagName,cls:String(n.className||''),text:(n.innerText||'').trim().slice(0,120)}))
            .filter(x=>/hud|map|step|route|info|action|note|title|status|zone|svg|canvas|img/i.test(x.id+' '+x.cls)).slice(0,120),
          classes:[...new Set([...document.querySelectorAll('[class]')].flatMap(n=>String(n.className||'').split(/\\s+/)).filter(Boolean))]
            .filter(x=>/hud|map|step|route|action|note|task|label/i.test(x)).slice(0,120),
          stepSample:[...document.querySelectorAll('.stepsCard .step,.step')].slice(0,3).map((n,i)=>({i,cls:n.className,text:(n.innerText||'').trim().slice(0,300)})),
          hudAction:document.querySelector('#hudAction')?.innerText||null,
          hudFivebox:document.querySelector('#hudFivebox')?.innerText||null
        })""")
        print(json.dumps(out,ensure_ascii=False,indent=2))
        await b.close()

asyncio.run(main())
