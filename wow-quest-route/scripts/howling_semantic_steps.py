from __future__ import annotations

import html
import re
from typing import Any

from dragonblight_semantic_steps import loc, note_block, notes_html, status_span, task

TASK_RE = re.compile(r"《([^》]+)》")
SYSTEM_PREFIXES = (
    "开飞行点：",
    "绑定炉石：",
    "使用炉石：",
    "系统飞行：",
)


def _kind_for_task(line: str, task_start: int) -> str:
    prefix = line[:task_start]
    candidates = [(prefix.rfind("交"), "turn"), (prefix.rfind("接"), "accept"), (prefix.rfind("做"), "do")]
    position, kind = max(candidates, key=lambda item: item[0])
    return kind if position >= 0 else "do"


def _escape_text(text: str) -> str:
    escaped = html.escape(text)
    escaped = escaped.replace("→", '<span class="ra-arrow">→</span>')
    escaped = escaped.replace("↳", '<span class="ra-branch">↳</span>')
    return escaped


def render_action_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    for prefix in SYSTEM_PREFIXES:
        if stripped.startswith(prefix):
            cls = "ra-flightpoint" if prefix == "开飞行点：" else "ra-hearthstone" if prefix in {"绑定炉石：", "使用炉石："} else "ra-flightpath"
            return f'<div class="ra-line"><span class="ra-system-action {cls}">{html.escape(stripped)}</span></div>'

    chunks: list[str] = []
    cursor = 0
    for match in TASK_RE.finditer(stripped):
        chunks.append(_escape_text(stripped[cursor:match.start()]))
        chunks.append(task(match.group(1), _kind_for_task(stripped, match.start())))
        cursor = match.end()
    chunks.append(_escape_text(stripped[cursor:]))
    cls = "ra-line ra-do" if stripped.startswith("↳") else "ra-line"
    return f'<div class="{cls}">' + "".join(chunks) + "</div>"


def _task_names(action: str) -> list[str]:
    result: list[str] = []
    for name in TASK_RE.findall(action):
        if name not in result:
            result.append(name)
    return result


def _note_title(point: list[Any]) -> str:
    action = str(point[3] if len(point) > 3 else "")
    names = _task_names(action)
    if names:
        return " / ".join(names[:4])
    return str(point[2] if len(point) > 2 else "路线提醒")


def apply_howling_semantic_hud(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    for group in groups:
        start = int(group["start"])
        end = int(group["end"])
        action_rows: list[str] = []
        note_rows: list[str] = []
        for point in points[start : end + 1]:
            title = str(point[2] if len(point) > 2 else "").strip()
            action = str(point[3] if len(point) > 3 else "")
            note = str(point[5] if len(point) > 5 else "").strip()
            fivebox = str(point[8] if len(point) > 8 else "").strip()

            if title:
                action_rows.append(f'<div class="ra-line ra-point-anchor">{loc(title)}</div>')
            for line in action.splitlines():
                rendered = render_action_line(line)
                if rendered:
                    action_rows.append(rendered)

            body_parts: list[str] = []
            if fivebox:
                body_parts.append(status_span("五开待实测") + html.escape(fivebox))
            if note:
                body_parts.append(html.escape(note))
            if body_parts:
                note_rows.append(note_block(_note_title(point), "".join(body_parts)))

        group["actionHtml"] = "\n".join(action_rows)
        group["noteHtml"] = notes_html(*note_rows)
