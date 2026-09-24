from __future__ import annotations
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=(ROOT/"data/routes/route-atlas-workbench-compare.html").as_uri()
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=["--allow-file-access-from-files"])
        page=await b.new_page(viewport={"width":1600,"height":1100})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        await page.goto(URL,wait_until="load")
        await page.wait_for_timeout(800)
        await page.select_option("#route","storm")
        await page.fill("#step","3")
        await page.click("#apply")
        await page.wait_for_timeout(250)
        out=await page.evaluate("""() => ({
          status:document.getElementById('syncStatus')?.textContent,
          oldRoute:document.getElementById('oldFrame')?.contentDocument?.getElementById('zone')?.value,
          newRouteIndex:document.getElementById('newFrame')?.contentDocument?.getElementById('routeSelect')?.value,
          oldHud:document.getElementById('oldFrame')?.contentDocument?.getElementById('hudTitle')?.textContent,
          newHud:document.getElementById('newFrame')?.contentDocument?.getElementById('hudTitle')?.textContent,
          errors: []
        })""")
        out["page_errors"]=errors
        print(json.dumps(out,ensure_ascii=False,indent=2))
        await b.close()
asyncio.run(main())
