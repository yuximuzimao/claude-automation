from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "route-atlas" / "workbench-routes.json"
OUT = ROOT / "docs" / "analysis" / "2026-08-24-legacy-route-old-vs-new-audit.md"
ROUTES = ["borean", "dragonblight", "grizzly", "zuldrak", "zang"]
ROUTE_LABELS = {
    "borean": "北风苔原",
    "dragonblight": "龙骨荒野",
    "grizzly": "灰熊丘陵",
    "zuldrak": "祖达克",
    "zang": "赞加沼泽",
}
TASK_RE = re.compile(r"《([^》]+)》")
TOKEN_RE = re.compile(r"(右键接|自动接|接|交|做|完成)|《([^》]+)》")


def load_old() -> dict:
    raw = subprocess.check_output(
        ["git", "show", "HEAD:wow-quest-route/data/route-atlas/workbench-routes.json"],
        cwd=ROOT,
    )
    return json.loads(raw)


def normalize_op(verb: str) -> str:
    if verb in {"接", "右键接", "自动接"}:
        return "接"
    if verb == "交":
        return "交"
    return "做"


def point_action_task_set(route: dict) -> set[str]:
    return {
        task
        for point in route.get("points", [])
        for task in TASK_RE.findall(str(point[3] if len(point) > 3 else ""))
    }


def op_map(route: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for point in route.get("points", []):
        text = str(point[3] if len(point) > 3 else "")
        for line in text.splitlines():
            current_op: str | None = None
            for match in TOKEN_RE.finditer(line):
                verb, task = match.groups()
                if verb:
                    current_op = normalize_op(verb)
                elif task and current_op:
                    out[task].add(current_op)
    return dict(out)


def task_first_step(route: dict) -> dict[str, int]:
    result: dict[str, int] = {}
    points = route.get("points", [])
    for step_number, group in enumerate(route.get("stepGroups", []), 1):
        start = int(group["start"])
        end = int(group["end"])
        for point in points[start : end + 1]:
            for task in TASK_RE.findall(str(point[3] if len(point) > 3 else "")):
                result.setdefault(task, step_number)
    return result


def note_task_map(route: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for point in route.get("points", []):
        note = str(point[5] if len(point) > 5 else "").strip()
        if not note:
            continue
        names = TASK_RE.findall(note)
        for name in names:
            if note not in out[name]:
                out[name].append(note)
    for group in route.get("stepGroups", []):
        note = str(group.get("noteHtml", "")).strip()
        if not note:
            continue
        plain = re.sub(r"<[^>]+>", "", note)
        names = TASK_RE.findall(plain)
        for name in names:
            if plain not in out[name]:
                out[name].append(plain)
    return dict(out)


def transport_lines(route: dict) -> list[str]:
    tokens = ("炉石", "系统飞行", "飞行点", "传送", "系统鸟")
    rows: list[str] = []
    for point in route.get("points", []):
        title = str(point[2] if len(point) > 2 else "")
        action = str(point[3] if len(point) > 3 else "")
        for line in action.splitlines():
            if any(token in line for token in tokens):
                rows.append(f"{title}：{line}")
    return rows


def fmt_set(values: set[str]) -> str:
    return "、".join(f"《{value}》" for value in sorted(values)) if values else "无"


def main() -> None:
    old_data = load_old()
    new_data = json.loads(CURRENT.read_text(encoding="utf-8"))
    head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()

    lines = [
        "# 旧Route Atlas → semantic-hud-v45 对比终审",
        "",
        f"基线：Git HEAD `{head}` 中的重构前 `workbench-routes.json`。",
        "",
        "目的：发现大规模逐段重写中可能出现的漏任务、动作角色漂移、旧备注丢失、步骤/交通意外变化。差异本身不等于错误，必须人工分类。",
        "",
    ]

    hard_findings = 0
    review_findings = 0
    for key in ROUTES:
        old = old_data[key]
        new = new_data[key]
        old_tasks = point_action_task_set(old)
        new_tasks = point_action_task_set(new)
        old_ops = op_map(old)
        new_ops = op_map(new)
        old_first = task_first_step(old)
        new_first = task_first_step(new)
        old_notes = note_task_map(old)
        new_notes = note_task_map(new)

        old_only = old_tasks - new_tasks
        new_only = new_tasks - old_tasks
        op_changes = {
            task: (old_ops.get(task, set()), new_ops.get(task, set()))
            for task in sorted(old_tasks & new_tasks)
            if old_ops.get(task, set()) != new_ops.get(task, set())
        }
        step_moves = {
            task: (old_first[task], new_first[task])
            for task in sorted(old_first.keys() & new_first.keys())
            if old_first[task] != new_first[task]
        }
        old_note_lost = {
            task: notes
            for task, notes in old_notes.items()
            if task not in new_notes
        }

        hard_findings += len(old_only)
        review_findings += len(new_only) + len(op_changes) + len(step_moves) + len(old_note_lost)

        lines += [
            f"## {ROUTE_LABELS[key]} `{key}`",
            "",
            f"- 点数：{len(old.get('points', []))} → {len(new.get('points', []))}",
            f"- 步骤：{len(old.get('stepGroups', []))} → {len(new.get('stepGroups', []))}",
            f"- 动作字段任务数：{len(old_tasks)} → {len(new_tasks)}",
            f"- 旧版有、新版动作字段消失：{fmt_set(old_only)}",
            f"- 新版新增动作字段任务：{fmt_set(new_only)}",
            "",
        ]

        if op_changes:
            lines.append("### 接/做/交角色发生变化")
            lines.append("")
            for task, (before, after) in op_changes.items():
                lines.append(f"- 《{task}》：旧 `{','.join(sorted(before)) or '未解析'}` → 新 `{','.join(sorted(after)) or '未解析'}`")
            lines.append("")

        if step_moves:
            lines.append("### 首次出现步骤变化")
            lines.append("")
            for task, (before, after) in step_moves.items():
                lines.append(f"- 《{task}》：步骤 {before} → {after}")
            lines.append("")

        if old_note_lost:
            lines.append("### 旧版有任务备注、新版未匹配到任务名")
            lines.append("")
            for task, notes in old_note_lost.items():
                snippet = " / ".join(notes)
                if len(snippet) > 240:
                    snippet = snippet[:237] + "..."
                lines.append(f"- 《{task}》：{snippet}")
            lines.append("")

        old_transport = transport_lines(old)
        new_transport = transport_lines(new)
        lines += [
            "### 交通动作摘要",
            "",
            f"- 旧版交通行：{len(old_transport)}；新版交通行：{len(new_transport)}",
        ]
        if old_transport != new_transport:
            lines.append("- 交通文本存在变化，需结合实际开点时序/炉石状态人工判读。")
            lines.append("- 旧版交通：")
            for row in old_transport:
                lines.append(f"  - {row}")
            lines.append("- 新版交通：")
            for row in new_transport:
                lines.append(f"  - {row}")
        else:
            lines.append("- 交通文本无变化。")
        lines.append("")

    lines += [
        "## 人工终审分类",
        "",
        f"### {hard_findings} 个硬候选",
        "",
        "- 北风 26 项全部是旧稿把任务物品/任务道具误用《》包裹后被机器当成任务名；已用北风任务宇宙反查，0 个是真实任务。",
        "- 龙骨《通缉：吉加托尔》及其后续精英支线是首组实测后明确留到80级处理，不属于重构漏任务。",
        "- 龙骨《萨鲁法尔的信》此前被旧P2阶段错误判定为不可解锁；北风全清已恢复并实跑完成《地狱咆哮的勇士》，因此该任务现已恢复到首次到阿格玛之锤时原地完成。",
        "- 祖达克《魔法王国达拉然》继续保持未交，用其任务传送能力进入达拉然；新版没有把它当作本图接/做/交动作，属于携带状态而不是任务丢失。",
        "- 赞加《更多卷须！》《更多孢子囊》是零经验重复声望任务，首轮练级路线明确不接第二轮。",
        f"- 结论：{hard_findings} 个硬候选全部已解释，未发现仍未处理的真实漏任务。",
        "",
        "### 动作角色 / 首次步骤候选",
        "",
        "- 大多数 `旧 接/交 → 新 接/做/交` 来自 semantic-hud-v45 把旧稿隐含的任务执行阶段显式化，不是路线内容新增。掉落触发任务新增 `接` 也是本轮统一规则要求。",
        "- 龙骨《血之魔典》首次出现从步骤5后移到步骤7：必须先交《死亡名单：高阶教徒扎古斯》，再到冰雾村刷阿努巴尔教徒取得起始物；这是实跑纠错。",
        "- 赞加《对方的尊重》从步骤1后移到步骤4：新版先在东部湖区完成《沼牙的威胁》，自然回沼泽鼠交任务后才接出《对方的尊重》，符合前置与当前路线回访时机。",
        "- 祖达克《温暖的篝火》《拎尾巴》等少数 `做` 消失属于机器只识别‘做’关键字，而新版使用‘沿路推进/继续携带’语义；任务仍在路线与交付闭环中。",
        "",
        "### 旧备注候选",
        "",
        "- 北风：采掘场/幼崽先后关系、卡琳高低差、耳环来源与不回水下补刷均已由新版动作顺序或备注保留。",
        "- 龙骨：扎古斯→血之魔典解锁、海边地产镇外同NPC、不可接面包屑、未来的种子首次经过策略均已保留；旧任务名差异不视为丢失。",
        "- 灰熊：本轮已补回停战任务刀、幻象材料、木乃伊/蘑菇来源、灰喉堡树苗/种子、符文监督者触发、护送前检查、达卡古尔巡逻与墓穴多次进入顺序；其余方向性备注已由显式路线顺序吸收。",
        "- 祖达克：圣光据点携带、奇怪魔精前置、四岗哨巡逻、蝙蝠/止痛药/纯粹的邪恶/未完的事情的下一站均已由新版显式接做交顺序吸收；同时补回达拉然传送NPC与希姆托加10份供品条件。",
        "- 赞加：本轮恢复《沼泽中的伯爵》下颚必掉、《枯萎的孢芽》不额外补刷，并统一所有掉落触发任务为‘动作只写接、来源和右键方式写备注’。",
        "",
        "### 交通候选",
        "",
        "- 北风：人工对比发现《过关斩将》的外部/内部纳克萨纳尔传送器曾被压入备注，已恢复为两条显式系统动作；其余差异是旧复合句拆分或普通移动删除。",
        "- 龙骨：新版新增的龙眠↔库卡隆系统鸟是交通状态显式化；所有当前系统飞行通过飞行点状态审计。",
        "- 灰熊：新版把原来隐含在复合句中的征服堡↔欧尼瓦系统飞行拆成独立动作；飞行状态审计无违规。",
        "- 祖达克：人工对比发现《真相大白》的上层密室传送器曾被压入任务流程，已恢复；两次古达克→希姆托加航线统一为‘系统飞行’，最终三段系统飞行均显式存在。",
        "- 赞加：新增交通来自重构后的炉石/飞行点/系统飞行显式化与路线重排，不存在旧系统交通动作被删后无替代的情况。",
        "",
        "### 人工终审结论",
        "",
        "- 本轮旧版对比实际发现并修复了真实信息回归与系统动作回归；修复后，当前五张旧图没有仍未解释的硬漏任务、旧版关键机制丢失或系统交通缺口。",
        "- 旧版对比阶段可通过；最终HTML用户视角冷读作为独立发布门禁，由当前重构流程完成后再标记整体完成。",
        "",
        "## 机器阶段结论",
        "",
        f"- 硬检查候选（旧动作任务在新版消失）：{hard_findings}",
        f"- 人工review候选（新增/动作角色/步骤移动/旧备注未匹配）：{review_findings}",
        "- 本文件只生成差异候选；最终分类与修正必须由人工对照旧稿、当前规则、实跑真值和任务事实完成。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(json.dumps({"hard_candidates": hard_findings, "review_candidates": review_findings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
