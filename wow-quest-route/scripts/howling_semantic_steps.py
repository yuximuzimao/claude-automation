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
    "固定交通：",
    "任务传送：",
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


DISPLAY_SPLITS: dict[int, list[tuple[int, str]]] = {
    1: [(5, "灰熊出口 → 冷原海岸 / 护盾"), (5, "钢铁之门前哨 → 老冰鳞")],
    2: [(4, "灰烬龙巢 → 新阿加曼德开场"), (5, "龙卵 / 龙胃 → 盾牌岭 → 奥弗斯"), (6, "卡玛古 → 长矛岛 → 伊斯卡尔"), (3, "卡玛古 → 格雷兹克斯 → 银月哈瑞")],
    3: [(6, "斯库德 → 无赖港西侧"), (5, "银月哈瑞 → 酒馆 → 长矛岛"), (4, "风暴愤怒法杖 → 无赖港权力链"), (3, "慈悲修女号")],
    5: [(4, "新阿加曼德 → 复仇港开场"), (4, "复仇港前线 → 北岸 → 回港")],
    7: [(4, "戈斯中士 → 拜尔海姆"), (4, "林德尔 → 尼弗莱瓦")],
    8: [(5, "新阿加曼德：量身订制 → 药剂喷雾"), (4, "重要零件 → 集中处理")],
    9: [(2, "冬蹄营地 → 东北自然区"), (3, "冬蹄交接 → 冰瀑")],
    10: [(4, "鲁莉尔蕾 → 裂木 / 凋零林地"), (3, "鲁莉尔蕾 → 凋零之叶")],
    11: [(6, "巨人平原：符文 / 巨人前两段"), (5, "巨人平原：命令符文 / 麦加利斯")],
    15: [(6, "药剂师营地 → 拉瑞恩 / 钢铁之门"), (6, "净化 → 药剂师营地 → 拉瑞恩")],
    16: [(5, "乌尔芬 → 兄弟 → 巨鹰"), (3, "乌尔芬 → 头狼 → 拉瑞恩")],
}


def _rebuild_display_groups(groups: list[dict[str, Any]]) -> None:
    coarse = [dict(group) for group in groups]
    rebuilt: list[dict[str, Any]] = []
    for step_number, parent in enumerate(coarse, 1):
        splits = DISPLAY_SPLITS.get(step_number)
        if not splits:
            rebuilt.append(parent)
            continue
        expected_points = int(parent["end"]) - int(parent["start"]) + 1
        if sum(item[0] for item in splits) != expected_points:
            raise RuntimeError(f"Howling display split {step_number} point drift")
        point_cursor = int(parent["start"])
        for split_index, (point_count, title) in enumerate(splits):
            start = point_cursor
            end = point_cursor + point_count - 1
            rebuilt.append({
                "start": start,
                "end": end,
                "title": title,
                "summary": "",
                "timingLogicalOverheadMinutes": 0.5 if split_index == 0 else 0.0,
            })
            point_cursor = end + 1
    groups[:] = rebuilt


def apply_howling_semantic_hud(points: list[list[Any]], groups: list[dict[str, Any]]) -> None:
    _rebuild_display_groups(groups)
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
