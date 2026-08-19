from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
OUT = ROOT / "data/route-atlas/grizzly-hills-route-skeleton.json"
REPORT = ROOT / "docs/analysis/2026-08-18-grizzly-hills-route-skeleton.md"

PHASES = [
    {
        "id": "G1",
        "title": "龙骨接入 → 征服堡首圈 → 沃德伦",
        "quest_ids": [12487, 12468, 12257, 12256, 12175, 12436, 12176, 12259, 12433],
        "intent": "交跨图引导、绑征服堡炉石；清南侧野兽和沃德伦链，并把一次性《寻找溶解剂》在西南角同圈完成。",
        "transport": ["进入征服堡后自然开启/确认本地飞行点", "炉石绑定征服堡"],
    },
    {
        "id": "G2",
        "title": "银溪镇 → 征服堡链条展开",
        "quest_ids": [12451, 12412, 12423, 12424, 12422, 12177, 12178, 12453, 12208],
        "intent": "做银溪镇击杀并拾取米克哈尔日记；回征服堡一次性推进高戈娜、休尼克购买链、巨魔引导，并携带《前往欧尼瓦营地》。",
        "transport": ["仍以征服堡为回收Hub"],
    },
    {
        "id": "G3",
        "title": "西线Drakuru → 古树之心 → 银溪北缘",
        "quest_ids": [11984, 11989, 11990, 11991, 12484, 12029, 12483, 12007, 12042, 12802, 12413],
        "intent": "连续推进Drakuru链；把普雷蒙/马克支线与同片巨魔素材并做；经古树之心继续到Drak'atal，再从北侧完成《攻击银溪镇》。",
        "transport": ["完成长西线后炉石回征服堡"],
    },
    {
        "id": "G4",
        "title": "征服堡斗兽场 → 沃达希尔第一层 → 卢娜",
        "quest_ids": [12425, 12427, 12428, 12429, 12430, 12431, 12207, 12213, 12328, 12327, 12329],
        "intent": "交银溪链后原地连做征服斗兽场五连；开启沃达希尔第一层并在中部顺带推进卢娜完整中间链。",
        "transport": ["征服堡继续作为西侧Hub"],
    },
    {
        "id": "G5",
        "title": "欧尼瓦开点 → 本地首圈 → 破损日记",
        "quest_ids": [12074, 12415, 12195, 12279, 12026],
        "intent": "交《前往欧尼瓦营地》，五号开启飞行点；接库伦引导、野马/鹿/鱼等本地任务，并在北上路上取得破损日记。",
        "transport": ["首次开启欧尼瓦营地飞行点", "此后征服堡↔欧尼瓦优先系统飞行，不再整图骑回"],
    },
    {
        "id": "G6",
        "title": "沃达希尔第二层 → 两Hub飞行回收",
        "quest_ids": [12229, 12231, 12241, 12242, 12236],
        "intent": "利用已开的两端飞行点推进沃达希尔的血液/熊神子嗣→树苗/种子→乌索克三层链；只为链解锁做必要Hub回收。",
        "transport": ["征服堡↔欧尼瓦系统飞行", "避免骑马跨整张图回交"],
    },
    {
        "id": "G7",
        "title": "欧尼瓦 → 索尔莫丹/库伦 → 铁矮人并圈",
        "quest_ids": [12054, 12058, 12073, 11982, 12070, 11985, 12081],
        "intent": "交破损日记后带《符文中的预言》《钢铁之子》北上；与库伦三连在索尔莫丹同圈完成，最后拿《加弗洛克》向东。",
        "transport": ["欧尼瓦作为东侧回收Hub"],
    },
    {
        "id": "G8",
        "title": "哈考尔/克拉斯 → 加弗洛克 → 萨莎/灰喉堡",
        "quest_ids": [12190, 12113, 12114, 12116, 12093, 12204, 12134, 12330, 12411],
        "intent": "在东北任务中心接肉/治疗/罐子；去加弗洛克开符文链；回中部交卢娜后续，连续完成萨莎狩猎与阿纳托雷并取得《姐姐的誓言》。",
        "transport": ["按目标区串联，不为单任务回Hub"],
    },
    {
        "id": "G9",
        "title": "Drakil'jin合并圈 → Bloodmoon → 加弗洛克第二层",
        "quest_ids": [12068, 12082, 12120, 12121, 12137, 12152, 12164, 12094],
        "intent": "把Drakuru石板、哈里森护送、克拉斯整条死亡/复活链集中在Drakil'jin一次处理；之后完成Bloodmoon狼人链，再推进加弗洛克潜能石。",
        "transport": ["Drakil'jin只做一套连续地形流程，减少反复进墓穴"],
    },
    {
        "id": "G10",
        "title": "Dun Argol：两条铁矮人链交织推进",
        "quest_ids": [12165, 12196, 12197, 12198, 12199, 12201, 12202, 12203],
        "intent": "把托尔玛克/罗卡尔的魔像链与沃塔肯的监工/影像/洛肯链交织在Dun Argol完成；保留伪装直到铁领主需要它的步骤结束。",
        "transport": ["欧尼瓦↔Dun Argol短往返", "同一趟尽量并做共享目标"],
    },
    {
        "id": "G11",
        "title": "加弗洛克收尾 → 东北任务回收 → 离图",
        "quest_ids": [12099],
        "intent": "完成《终获解救》，同时回收沿途尚未交付的东北任务；确认83项正式任务全部闭合后再进入祖达克轴。",
        "transport": ["不额外回征服堡，除非仍有沃达希尔/斗兽场未交付项"],
    },
]


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    formal_ids = {int(qid) for qid in foundation.get("formal_task_ids", [])}
    tasks = {int(task["quest_id"]): task for task in foundation.get("tasks", [])}

    used: list[int] = []
    duplicate_ids: list[int] = []
    phase_payload = []
    seen: set[int] = set()
    for phase in PHASES:
        qids = [int(qid) for qid in phase["quest_ids"]]
        for qid in qids:
            if qid in seen:
                duplicate_ids.append(qid)
            seen.add(qid)
            used.append(qid)
        phase_payload.append({
            **phase,
            "quests": [{"quest_id": qid, "name": tasks.get(qid, {}).get("name")} for qid in qids],
        })

    used_ids = set(used)
    missing = sorted(formal_ids - used_ids)
    unexpected = sorted(used_ids - formal_ids)
    payload = {
        "status": "route_skeleton_not_player_release",
        "zone": {"id": 394, "name": "灰熊丘陵"},
        "strategy": "continuous outdoor full-clear first-run baseline",
        "formal_task_count": len(formal_ids),
        "phase_count": len(PHASES),
        "coverage": {
            "used_unique": len(used_ids),
            "missing": missing,
            "unexpected": unexpected,
            "duplicates": sorted(set(duplicate_ids)),
            "pass": not missing and not unexpected and not duplicate_ids,
        },
        "hearth_chain": ["征服堡"],
        "flight_state_plan": {
            "entry": "龙骨→征服堡交通方式仍需按龙骨离图时实际已开网络锁定",
            "open_naturally": ["征服堡", "欧尼瓦营地"],
            "rule": "欧尼瓦开点后所有跨西东Hub步骤重新检查系统飞行，不沿用旧骑马线",
        },
        "phases": phase_payload,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 灰熊丘陵路线骨架（未发布玩家HTML）",
        "",
        "- 目标：83项一次性户外候选全清；不做首跑前经济删留。",
        f"- 骨架：{len(PHASES)}个自然任务块；覆盖{len(used_ids)}/{len(formal_ids)}；missing={missing}；unexpected={unexpected}；duplicates={sorted(set(duplicate_ids))}。",
        "- 这版只固定任务中心和大循环，尚未完成逐任务特殊机制/五开标记、精确点位、动态飞行状态和冷启动玩家复审，因此还不能称为实跑入口。",
        "",
    ]
    for phase in phase_payload:
        names = "、".join(f"《{row['name']}》" for row in phase["quests"])
        lines.extend([
            f"## {phase['id']} {phase['title']}",
            "",
            phase["intent"],
            "",
            f"任务归属：{names}",
            "",
            "交通：" + "；".join(phase["transport"]),
            "",
        ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "phases": len(PHASES),
        "formal": len(formal_ids),
        "covered": len(used_ids),
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": sorted(set(duplicate_ids)),
        "pass": payload["coverage"]["pass"],
        "out": str(OUT.relative_to(ROOT)),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
