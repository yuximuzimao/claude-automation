from __future__ import annotations

import html
import re
from typing import Any

from dragonblight_semantic_steps import loc, note_block, notes_html, status_span, task

TASK_RE = re.compile(r"《([^》]+)》")
EXPLICIT_NOTE_RE = re.compile(r"^《([^》]+)》\s*[：:]\s*(.*)$", re.S)
CONFIRMED_STATUS_BY_TASK = {
    "绿色的龙卵和龙崽": "不共享",
    "龙的胃病": "共享",
    "亡者复生！": "不共享",
    "盾牌岭": "不共享",
    "难民的食物": "不共享",
    "卡玛古的武装": "不共享",
    "赌债": "不共享",
    "斯库德": "不共享",
    "被遗忘的宝藏": "不共享",
}
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
    if len(names) == 1:
        return names[0]
    return str(point[2] if len(point) > 2 else "路线提醒")


def _note_entries(text: str) -> list[str]:
    value = text.strip()
    if not value:
        return []
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) > 1 and all(EXPLICIT_NOTE_RE.match(line) for line in lines):
        return lines
    return [value]


DISPLAY_SPLITS: dict[int, list[tuple[int, str]]] = {
    1: [(8, "征服堡 → 冷原海岸 / 腐鳃 / 护盾"), (7, "钢铁之门前哨 → 古器 / 囚犯 → 酒桶")],
    2: [(4, "灰烬龙巢 → 新阿加曼德开场"), (5, "龙卵 / 龙胃 → 盾牌岭 → 奥弗斯"), (6, "卡玛古 → 长矛岛 → 伊斯卡尔"), (3, "卡玛古 → 格雷兹克斯 → 银月哈瑞")],
    3: [(4, "斯库德 / 被遗忘的宝藏 → 赌债 / 嗜酒的杰克"), (7, "无赖港西侧 → 权力链 → 洞穴双任务"), (3, "死人的债务 / 风暴愤怒法杖 → 无赖港"), (3, "慈悲修女号")],
    5: [(4, "新阿加曼德 → 复仇港开场"), (4, "复仇港前线 → 北岸 → 回港")],
    7: [(4, "戈斯中士 → 拜尔海姆"), (4, "林德尔 → 尼弗莱瓦")],
    8: [(5, "新阿加曼德：量身订制 → 药剂喷雾"), (4, "重要零件 → 集中处理")],
    9: [(2, "冬蹄营地 → 东北自然区"), (3, "冬蹄交接 → 冰瀑")],
    10: [(4, "鲁莉尔蕾 → 裂木 / 凋零林地"), (3, "鲁莉尔蕾 → 凋零之叶")],
    11: [(6, "巨人平原：符文 / 巨人前两段"), (5, "巨人平原：命令符文 / 麦加利斯")],
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


def apply_howling_semantic_hud(
    points: list[list[Any]],
    groups: list[dict[str, Any]],
    *,
    apply_howling_display_splits: bool = False,
    confirmed_status_by_task: dict[str, str] | None = None,
) -> None:
    statuses = CONFIRMED_STATUS_BY_TASK if confirmed_status_by_task is None else confirmed_status_by_task
    if apply_howling_display_splits:
        _rebuild_display_groups(groups)
    for group in groups:
        start = int(group["start"])
        end = int(group["end"])
        action_rows: list[str] = []
        note_rows: list[str] = []
        status_seen_order: list[str] = []
        status_rendered: set[str] = set()
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

            task_names = _task_names(action)
            mapped_tasks = [name for name in task_names if name in statuses]
            for task_name in mapped_tasks:
                if task_name not in status_seen_order:
                    status_seen_order.append(task_name)

            for pending_entry in _note_entries(fivebox):
                pending_explicit = EXPLICIT_NOTE_RE.match(pending_entry)
                pending_title = pending_explicit.group(1).strip() if pending_explicit else _note_title(point)
                pending_body = pending_explicit.group(2).strip() if pending_explicit else pending_entry
                note_rows.append(note_block(pending_title, status_span("五开待实测") + html.escape(pending_body)))

            for note_entry in _note_entries(note):
                explicit = EXPLICIT_NOTE_RE.match(note_entry)
                note_title = explicit.group(1).strip() if explicit else _note_title(point)
                note_body = explicit.group(2).strip() if explicit else note_entry
                if note_title in statuses:
                    note_rows.append(
                        note_block(
                            note_title,
                            status_span(statuses[note_title]) + html.escape(note_body),
                        )
                    )
                    status_rendered.add(note_title)
                elif len(task_names) == 1 and task_names[0] in statuses:
                    task_name = task_names[0]
                    note_rows.append(
                        note_block(
                            task_name,
                            status_span(statuses[task_name]) + html.escape(note_body),
                        )
                    )
                    status_rendered.add(task_name)
                else:
                    note_rows.append(note_block(note_title, html.escape(note_body)))

        for task_name in status_seen_order:
            if task_name not in status_rendered:
                note_rows.append(note_block(task_name, status_span(statuses[task_name])))

        group["actionHtml"] = "\n".join(action_rows)
        group["noteHtml"] = notes_html(*note_rows)
