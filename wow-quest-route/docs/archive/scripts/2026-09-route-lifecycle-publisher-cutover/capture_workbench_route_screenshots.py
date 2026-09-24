from __future__ import annotations
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
ROUTES=ROOT/"data/routes"
OUT=ROUTES/"workbench-compare"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KEYS=["hellfire","zang","nagrand","borean","dragonblight","dalaran","storm","icecrown","sholazar","zuldrak","grizzly","howling","hellfire_dk","zang_dk"]

async def main():
    (OUT/"old").mkdir(parents=True,exist_ok=True)
    (OUT/"new").mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=["--allow-file-access-from-files"])
        old=await b.new_page(viewport={"width":1440,"height":1100})
        new=await b.new_page(viewport={"width":1440,"height":1100})
        await old.goto((ROUTES/"route-atlas-workbench.html").as_uri(),wait_until="load")
        await new.goto((ROUTES/"route-atlas-workbench-next.html").as_uri(),wait_until="load")
        for idx,key in enumerate(KEYS):
            await old.select_option("#zone",key)
            await new.select_option("#routeSelect",str(idx))
            await old.wait_for_timeout(60)
            await new.wait_for_timeout(60)
            await old.screenshot(path=str(OUT/"old"/f"{key}.png"),full_page=False)
            await new.screenshot(path=str(OUT/"new"/f"{key}.png"),full_page=False)
        await b.close()
    print(f"captured {len(KEYS)*2} screenshots")

asyncio.run(main())
