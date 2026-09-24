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
        await page.evaluate("localStorage.clear()")
        await page.reload(wait_until="load")
        storm_index=await page.evaluate("""() => {
          const i=ROUTES.findIndex(r=>r?.display?.publish_key==='storm');
          if(i<0) throw new Error('storm route not found');
          return i;
        }""")
        await page.select_option("#routeSelect",str(storm_index))
        await page.locator("#steps .step").nth(2).click()
        saved=await page.evaluate("""() => ({
          route:localStorage.getItem('route-atlas:last-route'),
          step:localStorage.getItem('route-atlas:last-step:storm')
        })""")
        before_view=await page.locator("#mapSvg").get_attribute("viewBox")
        await page.click("#playCurrent")
        await page.wait_for_timeout(320)
        mover=await page.evaluate("""() => {
          const m=document.querySelector('#mover');
          return {display:m?.style.display,cx:m?.getAttribute('cx'),cy:m?.getAttribute('cy'),
                  button:document.querySelector('#playCurrent')?.textContent}
        }""")
        during_view=await page.locator("#mapSvg").get_attribute("viewBox")
        await page.click("#playCurrent")
        await page.reload(wait_until="load")
        restored={
            "route_index": await page.input_value("#routeSelect"),
            "hud_title": await page.text_content("#hudTitle"),
            "active_step_text": await page.locator("#steps .step.active .stepTitle").text_content(),
            "view_box": await page.locator("#mapSvg").get_attribute("viewBox"),
            "follow_exists": await page.locator("#follow").count(),
        }
        print(json.dumps({"saved":saved,"mover":mover,"before_view":before_view,"during_view":during_view,"restored":restored,"errors":errors},ensure_ascii=False,indent=2))
        await b.close()

asyncio.run(main())
