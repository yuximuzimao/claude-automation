from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = ROOT / "data/routes"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def inspect(path: Path) -> dict:
    messages: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--allow-file-access-from-files"],
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("console", lambda msg: messages.append({"kind": "console", "type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: messages.append({"kind": "pageerror", "text": str(exc)}))
        await page.goto(path.as_uri(), wait_until="load")
        await page.wait_for_timeout(800)
        result = await page.evaluate(
            """() => ({
                title: document.title,
                readyState: document.readyState,
                routeCount: typeof ROUTES !== 'undefined' ? (Array.isArray(ROUTES) ? ROUTES.length : Object.keys(ROUTES).length) : null,
                selectOptions: document.querySelectorAll('select option').length,
                buttons: [...document.querySelectorAll('button')].map(x => (x.textContent || '').trim()),
                stepsChildren: document.getElementById('steps')?.children.length ?? null,
                mapSrc: document.getElementById('mapImg')?.getAttribute('src') ?? null,
                mapNaturalWidth: document.getElementById('mapImg')?.naturalWidth ?? null,
                mapNaturalHeight: document.getElementById('mapImg')?.naturalHeight ?? null,
                hudTitle: document.getElementById('hudTitle')?.textContent ?? null,
                hudText: document.getElementById('hudBody')?.innerText ?? null,
                bodyTextHead: (document.body?.innerText || '').slice(0, 1000),
            })"""
        )
        result["messages"] = messages
        await browser.close()
        return result


async def main() -> None:
    name = "route-atlas-workbench.html"
    out = {name: await inspect(ROUTES_DIR / name)}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
