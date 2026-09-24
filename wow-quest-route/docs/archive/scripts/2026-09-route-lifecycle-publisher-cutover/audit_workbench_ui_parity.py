from __future__ import annotations
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
ROUTES=ROOT/"data/routes"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
STYLE_KEYS=["fontFamily","fontSize","fontWeight","color","backgroundColor","borderRadius","padding","textShadow","whiteSpace","pointerEvents","position"]

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,headless=True,args=["--allow-file-access-from-files"])
        old=await b.new_page(viewport={"width":1440,"height":1100})
        new=await b.new_page(viewport={"width":1440,"height":1100})
        await old.goto((ROUTES/"route-atlas-workbench.html").as_uri(),wait_until="load")
        await new.goto((ROUTES/"route-atlas-workbench-next.html").as_uri(),wait_until="load")
        await old.select_option("#zone","hellfire")
        await new.select_option("#routeSelect","0")
        await old.wait_for_timeout(80); await new.wait_for_timeout(80)
        old_style=await old.evaluate("""keys=>{const n=[...document.querySelectorAll('.mapLabel')].find(x=>x.textContent.trim()==='黑暗之门');const s=getComputedStyle(n);return Object.fromEntries(keys.map(k=>[k,s[k]]))}""",STYLE_KEYS)
        new_style=await new.evaluate("""keys=>{const n=[...document.querySelectorAll('.mapLabel')].find(x=>x.textContent.trim()==='黑暗之门');const s=getComputedStyle(n);return Object.fromEntries(keys.map(k=>[k,s[k]]))}""",STYLE_KEYS)
        old_fonts=await old.evaluate("""() => ({body:getComputedStyle(document.body).fontSize,hud:getComputedStyle(document.querySelector('#hudAction .ra-line')||document.querySelector('#hudAction')).fontSize,hudTitle:getComputedStyle(document.querySelector('#hudTitle')).fontSize,step:getComputedStyle(document.querySelector('#steps .step')).fontSize,select:getComputedStyle(document.querySelector('#zone')).fontSize})""")
        new_fonts=await new.evaluate("""() => ({body:getComputedStyle(document.body).fontSize,hud:getComputedStyle(document.querySelector('#hudBody .line')||document.querySelector('#hudBody')).fontSize,hudTitle:getComputedStyle(document.querySelector('#hudTitle')).fontSize,step:getComputedStyle(document.querySelector('#steps .step')).fontSize,select:getComputedStyle(document.querySelector('#routeSelect')).fontSize})""")
        shell=await new.evaluate("""() => ({
          collapse_inside_hud:!!document.querySelector('#hud #collapse'),
          collapse_in_top:!!document.querySelector('.top #collapse'),
          collapse_text:document.querySelector('#collapse')?.textContent,
          hud_time:document.querySelector('#hudTime')?.textContent,
          hud_time_nonempty:!!document.querySelector('#hudTime')?.textContent?.trim(),
          pending_count:document.querySelectorAll('.pendingTag').length,
          pending_texts:[...document.querySelectorAll('.pendingTag')].map(n=>n.textContent.trim()),
          pending_style:document.querySelector('.pendingTag')?{
            color:getComputedStyle(document.querySelector('.pendingTag')).color,
            backgroundColor:getComputedStyle(document.querySelector('.pendingTag')).backgroundColor,
            borderColor:getComputedStyle(document.querySelector('.pendingTag')).borderColor
          }:null,
          svg_text_count:document.querySelectorAll('#mapSvg text').length,
          html_label_count:document.querySelectorAll('#mapLabels .mapLabel').length
        })""")
        await old.select_option("#zone","icecrown"); await new.select_option("#routeSelect","7")
        await old.wait_for_timeout(80); await new.wait_for_timeout(80)
        ice=await new.evaluate("""() => ({
          lines:[...document.querySelectorAll('#hudBody > .line')].slice(0,18).map(n=>n.textContent.trim()),
          training:[...document.querySelectorAll('#hudBody .task')].filter(n=>/近战训练|碎盾训练|冲锋训练/.test(n.textContent)).map(n=>({
            task:n.textContent.trim(),
            tag:n.previousElementSibling?.classList.contains('taskTag')?n.previousElementSibling.textContent.trim():''
          }))
        })""")
        diffs={k:[old_style[k],new_style[k]] for k in STYLE_KEYS if old_style[k]!=new_style[k]}
        errors=[]
        if diffs: errors.append({"kind":"map_label_style_mismatch","diffs":diffs})
        if old_fonts != new_fonts:
            errors.append({"kind":"font_size_mismatch","old":old_fonts,"new":new_fonts})
        if not shell["collapse_inside_hud"] or shell["collapse_in_top"]:
            errors.append({"kind":"collapse_button_not_in_hud","shell":shell})
        if not shell["hud_time_nonempty"] or not shell["hud_time"].startswith("本段预计："):
            errors.append({"kind":"step_timing_placeholder_missing","value":shell["hud_time"]})
        if shell["pending_style"] is None or shell["pending_style"]["backgroundColor"]!="rgb(166, 37, 51)":
            errors.append({"kind":"pending_tag_not_red","style":shell["pending_style"]})
        if shell["pending_count"] and any(text != "待实测" for text in shell["pending_texts"]):
            errors.append({"kind":"pending_tag_text_wrong","texts":shell["pending_texts"]})
        if shell["svg_text_count"] != 0 or shell["html_label_count"] <= 0:
            errors.append({"kind":"map_label_render_mode_wrong","shell":shell})
        first_line=ice["lines"][0] if ice["lines"] else ""
        if not first_line.startswith("银色比武场·裁决者玛蕾尔·图哈特 → 接") or first_line.count("裁决者玛蕾尔·图哈特") != 1:
            errors.append({"kind":"location_npc_dedup_failed","line":first_line})
        if any(row["tag"]!="不共享" for row in ice["training"]):
            errors.append({"kind":"training_fivebox_status_wrong","training":ice["training"]})
        if not any(
            line.startswith("加拉希亚·晨光 → 交不共享《碎盾训练》 → 接待实测《学习驾驭》")
            for line in ice["lines"]
        ):
            errors.append({"kind":"same_npc_turnin_accept_not_merged","lines":ice["lines"]})
        report={"map_label_old":old_style,"map_label_new":new_style,"map_label_diffs":diffs,"fonts_old":old_fonts,"fonts_new":new_fonts,"shell":shell,"icecrown":ice,"errors":errors}
        print(json.dumps(report,ensure_ascii=False,indent=2))
        await b.close()
        if errors:
            raise SystemExit(1)

asyncio.run(main())
