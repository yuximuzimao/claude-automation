from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Page

ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = ROOT / "data/routes"
OUT_DIR = ROUTES_DIR / "workbench-compare"
OLD_URL = (ROUTES_DIR / "route-atlas-workbench.html").as_uri()
NEW_URL = (ROUTES_DIR / "route-atlas-workbench-next.html").as_uri()
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ROUTE_KEYS = [
    "hellfire", "zang", "nagrand", "borean", "dragonblight", "dalaran",
    "storm", "icecrown", "sholazar", "zuldrak", "grizzly", "howling",
    "hellfire_dk", "zang_dk",
]

PUBLISH_TO_PROFILE = {
    "hellfire": "hellfire-fivebox",
    "zang": "zangarmarsh-fivebox",
    "nagrand": "nagrand-fivebox-67-68",
    "borean": "borean-fivebox",
    "dragonblight": "dragonblight-fivebox",
    "dalaran": "dalaran-mainline-77",
    "storm": "storm-peaks-fivebox",
    "icecrown": "icecrown-fivebox",
    "sholazar": "sholazar-fivebox",
    "zuldrak": "zuldrak-fivebox",
    "grizzly": "grizzly-fivebox",
    "howling": "howling-fivebox",
    "hellfire_dk": "hellfire-dk-speed",
    "zang_dk": "zangarmarsh-dk-speed",
}

ROLE_CLASS_OLD = {
    "ra-accept": "accept",
    "ra-do-task": "objective",
    "ra-turnin": "turnin",
}
ROLE_CLASS_NEW = {
    "accept": "accept",
    "objective": "objective",
    "turnin": "turnin",
}


def compact(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def line_normalize(text: str | None) -> list[str]:
    rows = []
    for raw in str(text or "").splitlines():
        row = compact(raw)
        if row:
            rows.append(row)
    return rows


def task_names_from_text(text: str) -> list[str]:
    return [compact(v) for v in re.findall(r"《([^》]+)》", text or "") if compact(v)]


async def route_index_new(page: Page, key: str) -> int:
    return int(await page.evaluate(
        """key => ROUTES.findIndex(r => r.display && r.display.publish_key === key)""",
        key,
    ))


async def switch_old(page: Page, key: str) -> None:
    await page.select_option("#zone", key)
    await page.wait_for_timeout(80)


async def switch_new(page: Page, key: str) -> None:
    idx = await route_index_new(page, key)
    if idx < 0:
        raise RuntimeError(f"new route missing: {key}")
    await page.evaluate("idx => setRoute(idx)", idx)
    await page.wait_for_timeout(80)


async def capture_old_step(page: Page, index: int) -> dict[str, Any]:
    steps = page.locator("#steps .step")
    count = await steps.count()
    if index >= count:
        raise IndexError(index)
    await steps.nth(index).click(force=True)
    await page.wait_for_timeout(15)
    return await page.evaluate("""() => {
      const action=document.querySelector('#hudAction');
      const hud=document.querySelector('#hud');
      const tasks=[...(action?.querySelectorAll('.ra-task')||[])].map(n=>({
        text:(n.textContent||'').trim(), cls:[...n.classList]
      }));
      const notes=[...(hud?.querySelectorAll('.ra-note-block')||[])].map(n=>({
        task:(n.querySelector('.ra-note-task')?.textContent||'').trim(),
        text:(n.querySelector('.ra-note-text')?.textContent||'').trim(),
        cls:[...n.classList]
      }));
      return {
        title:(document.querySelector('#hudTitle')?.textContent||'').trim(),
        time:(document.querySelector('#hudCoord')?.textContent||'').trim(),
        actionText:(action?.innerText||'').trim(),
        nextText:(document.querySelector('#hudNext')?.innerText||'').trim(),
        noteText:(document.querySelector('#hudNote')?.innerText||'').trim(),
        fiveboxText:(document.querySelector('#hudFivebox')?.innerText||'').trim(),
        tasks, notes,
        routeTitle:(document.querySelector('#pageTitle')?.textContent||'').trim(),
        routeSubtitle:(document.querySelector('#pageSubtitle')?.textContent||'').trim(),
        routeMeta:(document.querySelector('#meta')?.innerText||'').trim(),
        mapLines:document.querySelectorAll('#lines line,#lines path,#lines polyline').length,
        mapLabels:document.querySelectorAll('#mapLabels .mapLabel').length,
        mapImageHref:document.querySelector('#mapImage')?.getAttribute('href')||document.querySelector('#mapImage')?.getAttribute('xlink:href')||'',
        svgWidth:document.querySelector('#svg')?.getBoundingClientRect().width||0,
        svgHeight:document.querySelector('#svg')?.getBoundingClientRect().height||0,
        bodyScrollHeight:document.documentElement.scrollHeight,
        bodyScrollWidth:document.documentElement.scrollWidth,
      };
    }""")


async def capture_new_step(page: Page, index: int) -> dict[str, Any]:
    steps = page.locator("#steps .step")
    count = await steps.count()
    if index >= count:
        raise IndexError(index)
    await steps.nth(index).click(force=True)
    await page.wait_for_timeout(15)
    return await page.evaluate("""() => {
      const body=document.querySelector('#hudBody');
      const r=route(),s=r.steps[stepIndex];
      const tasks=[...(body?.querySelectorAll('.task')||[])].map(n=>({
        text:(n.textContent||'').trim(), cls:[...n.classList]
      }));
      const notes=[...(body?.querySelectorAll('.notes .note')||[])].map(n=>({
        task:(n.textContent||'').trim(),
        text:(n.textContent||'').trim(),
        cls:[...n.classList]
      }));
      return {
        title:(document.querySelector('#hudTitle')?.textContent||'').trim(),
        time:(document.querySelector('#hudTime')?.textContent||'').trim(),
        actionText:(body?.innerText||'').trim(),
        nextText:'',
        noteText:(body?.querySelector('.notes')?.innerText||'').trim(),
        fiveboxText:'',
        tasks, notes,
        routeTitle:String(r.display?.title||'').trim(),
        routeSubtitle:String(r.display?.subtitle||'').trim(),
        routeMeta:(document.querySelector('#status')?.innerText||'').trim(),
        mapLines:document.querySelectorAll('#mapSvg .edge').length,
        mapVisits:document.querySelectorAll('#mapSvg .visit').length,
        mapLabels:document.querySelectorAll('#mapSvg .label').length,
        mapImageHref:document.querySelector('#mapImg')?.getAttribute('src')||'',
        mapNaturalWidth:document.querySelector('#mapImg')?.naturalWidth||0,
        mapNaturalHeight:document.querySelector('#mapImg')?.naturalHeight||0,
        svgWidth:document.querySelector('#mapSvg')?.getBoundingClientRect().width||0,
        svgHeight:document.querySelector('#mapSvg')?.getBoundingClientRect().height||0,
        bodyScrollHeight:document.documentElement.scrollHeight,
        bodyScrollWidth:document.documentElement.scrollWidth,
        summary:String(s.summary||'').trim(),
        presentations:(s.task_presentations||[]).map(p=>({
          task_id:p.task_id,name:p.name,badge:p.badge,pending:!!p.pending,note:String(p.note||'').trim()
        })),
      };
    }""")


def role_sequence(tasks: list[dict[str, Any]], class_map: dict[str, str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for task in tasks:
        role = ""
        classes = set(task.get("cls") or [])
        for cls, value in class_map.items():
            if cls in classes:
                role = value
                break
        name = compact(task.get("text"))
        if name:
            result.append((role, name.strip("《》")))
    return result


def step_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_roles = role_sequence(old.get("tasks") or [], ROLE_CLASS_OLD)
    new_roles = role_sequence(new.get("tasks") or [], ROLE_CLASS_NEW)
    old_lines = line_normalize(old.get("actionText"))
    new_lines = line_normalize(new.get("actionText"))
    old_task_names = [name for _, name in old_roles]
    new_task_names = [name for _, name in new_roles]
    return {
        "title_old": compact(old.get("title")),
        "title_new": compact(new.get("title")),
        "title_same": compact(old.get("title")).replace("步骤 ", "").split(" · ",1)[-1] == compact(new.get("title")),
        "time_old": compact(old.get("time")),
        "time_new": compact(new.get("time")),
        "task_role_sequence_same": old_roles == new_roles,
        "old_task_role_sequence": old_roles,
        "new_task_role_sequence": new_roles,
        "old_task_only": list((Counter(old_task_names) - Counter(new_task_names)).elements()),
        "new_task_only": list((Counter(new_task_names) - Counter(old_task_names)).elements()),
        "action_lines_same": old_lines == new_lines,
        "old_line_count": len(old_lines),
        "new_line_count": len(new_lines),
        "old_action_lines": old_lines,
        "new_action_lines": new_lines,
        "old_next": compact(old.get("nextText")),
        "new_summary": compact(new.get("summary")),
        "old_notes": old.get("notes") or [],
        "new_presentations": new.get("presentations") or [],
    }


def route_summary_diff(old_meta: dict[str, Any], new_meta: dict[str, Any], step_diffs: list[dict[str, Any]]) -> dict[str, Any]:
    old_titles = [compact(v) for v in old_meta["step_titles"]]
    new_titles = [compact(v) for v in new_meta["step_titles"]]
    sm = SequenceMatcher(a=old_titles, b=new_titles, autojunk=False)
    ops = [
        {"tag": tag, "old": [i1, i2], "new": [j1, j2],
         "old_titles": old_titles[i1:i2], "new_titles": new_titles[j1:j2]}
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != "equal"
    ]
    return {
        "display_name_old": old_meta["display_name"],
        "display_name_new": new_meta["display_name"],
        "route_title_old": old_meta["route_title"],
        "route_title_new": new_meta["route_title"],
        "subtitle_old": old_meta["subtitle"],
        "subtitle_new": new_meta["subtitle"],
        "route_status_old": old_meta["route_status"],
        "route_status_new": new_meta["route_status"],
        "step_count_old": len(old_titles),
        "step_count_new": len(new_titles),
        "step_title_sequence_same": old_titles == new_titles,
        "step_title_ops": ops,
        "steps_task_sequence_changed": sum(not x["task_role_sequence_same"] for x in step_diffs),
        "steps_action_text_changed": sum(not x["action_lines_same"] for x in step_diffs),
        "steps_old_task_only_total": sum(len(x["old_task_only"]) for x in step_diffs),
        "steps_new_task_only_total": sum(len(x["new_task_only"]) for x in step_diffs),
        "map_old": old_meta["map"],
        "map_new": new_meta["map"],
    }


async def route_meta_old(page: Page, key: str) -> dict[str, Any]:
    return await page.evaluate("""key => {
      const r=ROUTES[key], groups=r.stepGroups||[];
      return {
        display_name:r.displayName||r.title||key,
        route_title:(document.querySelector('#pageTitle')?.textContent||r.title||'').trim(),
        subtitle:(document.querySelector('#pageSubtitle')?.textContent||'').trim(),
        route_status:(document.querySelector('#meta')?.innerText||'').trim(),
        step_titles:groups.map(g=>String(g.title||'').trim()),
        map:{
          source:r.mapImage||r.map||'',
          rendered_lines:document.querySelectorAll('#lines line,#lines path,#lines polyline').length,
          rendered_labels:document.querySelectorAll('#mapLabels .mapLabel').length,
          svg_width:document.querySelector('#svg')?.getBoundingClientRect().width||0,
          svg_height:document.querySelector('#svg')?.getBoundingClientRect().height||0,
        }
      }
    }""", key)


async def route_meta_new(page: Page) -> dict[str, Any]:
    return await page.evaluate("""() => {
      const r=route();
      return {
        display_name:r.display?.display_name||r.display?.title||r.profile_id,
        route_title:String(r.display?.title||'').trim(),
        subtitle:String(r.display?.subtitle||'').trim(),
        route_status:(document.querySelector('#status')?.innerText||'').trim(),
        step_titles:(r.steps||[]).map(g=>String(g.title||'').trim()),
        map:{
          source:r.map?.image||'',
          rendered_lines:document.querySelectorAll('#mapSvg .edge').length,
          rendered_visits:document.querySelectorAll('#mapSvg .visit').length,
          rendered_labels:document.querySelectorAll('#mapSvg .label').length,
          natural_width:document.querySelector('#mapImg')?.naturalWidth||0,
          natural_height:document.querySelector('#mapImg')?.naturalHeight||0,
          svg_width:document.querySelector('#mapSvg')?.getBoundingClientRect().width||0,
          svg_height:document.querySelector('#mapSvg')?.getBoundingClientRect().height||0,
        }
      }
    }""")


async def page_controls(page: Page, kind: str) -> dict[str, Any]:
    return await page.evaluate("""kind => ({
      title:document.title,
      buttons:[...document.querySelectorAll('button')].map(n=>(n.textContent||'').trim()),
      selects:[...document.querySelectorAll('select')].map(n=>({id:n.id,text:(n.textContent||'').trim(),value:n.value})),
      checkboxes:[...document.querySelectorAll('input[type=checkbox]')].map(n=>({id:n.id,checked:n.checked,label:n.parentElement?.innerText?.trim()||''})),
      hasLocalStorageResume: kind==='old'
        ? !![...document.scripts].some(s=>(s.textContent||'').includes('route-atlas:last-route'))
        : !![...document.scripts].some(s=>(s.textContent||'').includes('route-atlas:last-route')),
      bodyScrollWidth:document.documentElement.scrollWidth,
      viewportWidth:innerWidth,
    })""", kind)


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for side in ["old", "new"]:
        (OUT_DIR / side).mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--allow-file-access-from-files"],
        )
        old = await browser.new_page(viewport={"width": 1440, "height": 1100})
        new = await browser.new_page(viewport={"width": 1440, "height": 1100})
        old_errors: list[str] = []
        new_errors: list[str] = []
        old.on("pageerror", lambda e: old_errors.append(str(e)))
        new.on("pageerror", lambda e: new_errors.append(str(e)))
        await old.goto(OLD_URL, wait_until="load")
        await new.goto(NEW_URL, wait_until="load")
        await old.wait_for_timeout(250)
        await new.wait_for_timeout(250)

        report: dict[str, Any] = {
            "controls": {
                "old": await page_controls(old, "old"),
                "new": await page_controls(new, "new"),
            },
            "routes": {},
        }

        for key in ROUTE_KEYS:
            await switch_old(old, key)
            await switch_new(new, key)
            old_meta = await route_meta_old(old, key)
            new_meta = await route_meta_new(new)

            await old.screenshot(path=str(OUT_DIR / "old" / f"{key}.png"), full_page=False)
            await new.screenshot(path=str(OUT_DIR / "new" / f"{key}.png"), full_page=False)

            old_count = await old.locator("#steps .step").count()
            new_count = await new.locator("#steps .step").count()
            compare_count = min(old_count, new_count)
            step_diffs: list[dict[str, Any]] = []
            for idx in range(compare_count):
                o = await capture_old_step(old, idx)
                n = await capture_new_step(new, idx)
                step_diffs.append(step_diff(o, n))

            summary = route_summary_diff(old_meta, new_meta, step_diffs)
            report["routes"][key] = {
                "profile_id": PUBLISH_TO_PROFILE[key],
                "summary": summary,
                "steps": step_diffs,
            }

        report["browser_errors"] = {"old": old_errors, "new": new_errors}
        await browser.close()

    json_path = OUT_DIR / "workbench-diff.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Route Atlas 旧版 / 新版浏览器级差异报告",
        "",
        "本报告来自真实 Chrome + Playwright 渲染。它只描述差异，不替用户做最终好坏裁决。",
        "",
        "## 全局控件",
        "",
        f"- 旧按钮：{' / '.join(report['controls']['old']['buttons'])}",
        f"- 新按钮：{' / '.join(report['controls']['new']['buttons'])}",
        f"- 旧状态恢复：{report['controls']['old']['hasLocalStorageResume']}",
        f"- 新状态恢复：{report['controls']['new']['hasLocalStorageResume']}",
        "",
        "## 逐路线",
        "",
    ]
    for key in ROUTE_KEYS:
        row = report["routes"][key]
        s = row["summary"]
        lines += [
            f"### {key}｜{s['display_name_old']} → {s['display_name_new']}",
            "",
            f"- 步骤：{s['step_count_old']} → {s['step_count_new']}；标题序列相同：{s['step_title_sequence_same']}",
            f"- 同索引步骤中，任务接/做/交序列变化：{s['steps_task_sequence_changed']} 段；动作正文变化：{s['steps_action_text_changed']} 段",
            f"- 旧版独有任务引用总数：{s['steps_old_task_only_total']}；新版独有任务引用总数：{s['steps_new_task_only_total']}",
            f"- 旧标题：{s['route_title_old']}",
            f"- 新标题：{s['route_title_new']}",
            f"- 旧副标题：{s['subtitle_old'] or '（空）'}",
            f"- 新副标题：{s['subtitle_new'] or '（空）'}",
        ]
        if s["step_title_ops"]:
            lines.append("- 步骤标题结构差异：")
            for op in s["step_title_ops"]:
                lines.append(
                    f"  - {op['tag']} old{op['old']}={op['old_titles']} → new{op['new']}={op['new_titles']}"
                )
        changed = [
            (i + 1, d) for i, d in enumerate(row["steps"])
            if (not d["task_role_sequence_same"]) or (not d["action_lines_same"])
        ]
        if changed:
            lines.append("- 有正文/任务差异的同索引步骤：")
            for idx, d in changed:
                lines.append(
                    f"  - Step {idx}: 《{d['title_old']}》 → 《{d['title_new']}》；"
                    f"旧独有任务={d['old_task_only'] or []}；新独有任务={d['new_task_only'] or []}"
                )
        lines.append("")

    (OUT_DIR / "workbench-diff.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "json": str(json_path),
        "markdown": str(OUT_DIR / "workbench-diff.md"),
        "old_screenshots": str(OUT_DIR / "old"),
        "new_screenshots": str(OUT_DIR / "new"),
        "browser_errors": report["browser_errors"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
