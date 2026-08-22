from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
OUT = ROOT / "data/route-atlas/grizzly-hills-special-mechanism-audit.json"
REPORT = ROOT / "docs/analysis/2026-08-18-grizzly-hills-special-mechanism-audit.md"

# Player-facing facts. Keep five-box uncertainty separate from known single-character mechanics.
MANUAL = {
    11984: {
        "facts": ["先与Budd对话取得控制/技能，再对单独巨魔使用指定能力完成抓捕。"],
        "fivebox_check": "确认一名角色成功抓捕是否共享任务进度；若不共享则五号依次执行。",
    },
    11990: {
        "facts": ["先购买水晶瓶；沿湖区收集水草叶并取得3片朦胧叶，再回达库鲁。"],
    },
    12007: {
        "facts": ["先取得任务所需的祭品/魔精，再到雕像处完成先知之眼步骤，最后在火盆旁使用达库鲁药剂交接。"],
    },
    12026: {
        "facts": ["地面拾取破损日记后，在索尔莫丹周围收集8张缺失书页并合成日记。"],
        "fivebox_check": "8张书页属于逐号收集还是可共享/同点多号拾取，首组实测。",
    },
    12058: {
        "facts": ["索尔莫丹内依次检查3块符文板；三处都在库伦链同一目标区。"],
        "fivebox_check": "符文板互动进度是否共享，首组实测。",
    },
    12082: {
        "facts": [
            "在Drakil'jin遗迹内与哈里森·琼斯开启护送；与12068和克拉斯链合并在同一次墓穴流程。",
            "五号接好任务后一起跑一次护送即可完成，不需要逐号重复。",
        ],
    },
    12099: {
        "facts": ["对符文巨人使用加弗洛克的符文破坏者；成功会释放目标，失败会削弱目标，可冷却后再次使用。"],
        "fivebox_check": "一次释放是否共享进度；若道具必须逐号使用则记录真实切号成本。",
    },
    12121: {
        "facts": ["在Drakil'jin遗迹敲锣使用充能战锤，角色会进入死亡/灵魂流程，并向地下的甘休交接。"],
        "fivebox_check": "灵魂/死亡阶段是否必须五号分别触发；这是首组重点黄色机制。",
    },
    12137: {
        "facts": ["从甘休箱子取得永恒沉睡之雪，恢复活人状态后对指定达卡莱目标使用并拾取灵魂微粒，再回克拉斯。"],
        "fivebox_check": "任务道具使用与微粒拾取是否逐号完成。",
    },
    12152: {
        "facts": ["再次进入墓穴取得神圣达卡莱供品，合成灌注供品后回锣处使用，完成金亚拉克收尾。"],
        "fivebox_check": "供品拾取/最终锣互动是否逐号完成。",
    },
    12164: {
        "facts": ["前往血月岛依次处理三个命名狼人和阿鲁高之影；萨莎会参与最终阶段。"],
        "fivebox_check": "精英链按普通小队共享击杀预期执行，首组确认最终脚本阶段五号均完成。",
    },
    12165: {
        "facts": ["在Dun Argol击杀铁符文铸造师，收集蓝图第1/2/3部分后合成完整蓝图。"],
        "fivebox_check": "三张蓝图是否个人掉落；若是，按五号最慢角色记录真实墙钟。",
    },
    12197: {
        "facts": ["在Dun Argol分别取得杜拉尔与卡索恩两颗能量核心；与伪装链同区域完成。"],
        "fivebox_check": "两颗核心是否个人掉落/同尸多号可拾取。",
    },
    12199: {
        "facts": ["保留Dun Argol伪装进入上层建筑，经电梯下去后使用魔像控制器击败铁领主。"],
        "fivebox_check": "载具/控制器击杀进度是否共享；若必须逐号控制则记录。",
    },
    12203: {
        "facts": ["在Dun Argol伪装状态下读取洛肯基座；为后续铁领主流程保留伪装，先不要急着结束会失去伪装的状态。"],
    },
    12236: {
        "facts": ["击败乌索克后对尸体使用净化后的沃达希尔灰烬；NPC助手可承担坦克/输出/治疗职责。"],
        "fivebox_check": "击杀预计共享，但尸体用灰烬是否每号都要操作需首组确认。",
    },
    12241: {
        "facts": ["进入灰喉堡底层，对沃达希尔树苗使用任务火炬完成摧毁。"],
        "fivebox_check": "火炬互动是否共享。",
    },
    12279: {
        "facts": ["在湖中鱼群使用渔网取得北地鲑鱼；不要把它当普通钓鱼专业任务。"],
        "fivebox_check": "鲑鱼任务物为个人获取还是共享，首组实测。",
    },
    12427: {
        "facts": ["征服斗兽场五连第一场；整条12427→12431在征服堡原地连续完成。"],
        "fivebox_check": "五号同时在任务状态下是否一次战斗全部记进度。",
    },
    12428: {"facts": ["征服斗兽场第二场，紧接12427，不离开Hub。"]},
    12429: {"facts": ["征服斗兽场第三场，紧接12428。"]},
    12430: {"facts": ["征服斗兽场第四场，紧接12429。"]},
    12431: {"facts": ["征服斗兽场最终场，完成后向高戈娜收尾。"]},
    12433: {
        "facts": ["取得Element 115后会进入短时返程窗口；移动速度增益/坐骑无法正常抵消该状态，直接沿原路快速回交，避免战斗。"],
        "fivebox_check": "Element 115必须逐号拾取的概率很高；首组确认是否能同一刷新点连续五号取、以及返程窗口是否分别计时。",
    },
}


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = {int(task["quest_id"]): task for task in foundation.get("tasks", [])}
    formal_ids = set(tasks)
    rows = []
    unexpected = []
    for qid, note in sorted(MANUAL.items()):
        if qid not in formal_ids:
            unexpected.append(qid)
            continue
        rows.append({
            "quest_id": qid,
            "name": tasks[qid].get("name"),
            "facts": note.get("facts", []),
            "fivebox_check": note.get("fivebox_check"),
            "player_note_required": True,
            "evidence": ["Questie/current task card", "historical Horde route/mechanic reference"],
        })

    fivebox = [row for row in rows if row.get("fivebox_check")]
    payload = {
        "status": "route_insertion_mechanism_screen",
        "zone": {"id": 394, "name": "灰熊丘陵"},
        "formal_task_count": len(formal_ids),
        "special_note_count": len(rows),
        "fivebox_check_count": len(fivebox),
        "unexpected_manual_qids": unexpected,
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 灰熊丘陵特殊机制与五开核验",
        "",
        f"- 正式全清池：{len(formal_ids)}；需要玩家攻略备注的特殊项：{len(rows)}；其中黄色fivebox_check：{len(fivebox)}。",
        "- 黄色项不阻塞首组路线发布：页面明确提示用户实测，共享/个人结论回报后再锁定。",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['quest_id']}《{row['name']}》")
        lines.append("")
        for fact in row["facts"]:
            lines.append(f"- {fact}")
        if row.get("fivebox_check"):
            lines.append(f"- **fivebox_check：{row['fivebox_check']}**")
        lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "special_notes": len(rows),
        "fivebox_checks": len(fivebox),
        "unexpected": unexpected,
        "out": str(OUT.relative_to(ROOT)),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
