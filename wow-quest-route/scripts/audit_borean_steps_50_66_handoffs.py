from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/borean-tundra-task-foundation.json"
OUT = ROOT / "data/route-atlas/borean-steps-50-66-handoff-audit.json"

NAMES = {
    "苔原上的审讯", "说服的艺术", "分享情报", "与时间赛跑", "重铸钥匙", "准备飞翔",
    "营救艾瓦诺尔", "苏雷斯塔兹", "飞越裂谷", "监测数据", "古树的秘密", "冰冷的草莓",
    "基本的训练", "保持隐蔽", "蓝龙的卵", "奇怪……", "猎龙", "牢笼", "破译密码",
    "克莉斯塔萨", "诱饵", "莎拉苟萨的末日", "集结红龙", "触动陷阱", "攻击！",
    "亡者的尊严", "让他们安息", "立即前往博古洛克前哨站！", "睿智的气元素", "国王姆嘎姆嘎",
    "沸点", "学习沟通", "冬鳞鱼人的贸易", "救救蝌蚪！", "就是他们！", "我被敲竹杠了！",
    "咕噜咕噜呜啦哇啦！", "美味炖鲸肉", "备用的鱼人服", "决不投降！", "监视裂谷：冬鳞洞穴",
    "钥匙管理者呜啦咕噜", "逃离冬鳞洞穴", "风暴微粒", "返回灵语者身边", "空气的幻象",
    "先知格雷姆沃克之魂", "向犸格莫斯复仇", "卡加尼舒", "落叶归根", "横贯冰原",
}


def compact_entity(entity: dict) -> dict:
    return {
        "name": entity.get("name"),
        "entity_type": entity.get("entity_type"),
        "entity_id": entity.get("entity_id"),
        "representative_by_zone": entity.get("representative_by_zone"),
    }


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in payload.get("tasks", []):
        if task.get("name") not in NAMES:
            continue
        rows.append({
            "quest_id": task.get("quest_id"),
            "name": task.get("name"),
            "start_entities": [compact_entity(x) for x in task.get("start_entities", [])],
            "finish_entities": [compact_entity(x) for x in task.get("finish_entities", [])],
            "pre_any": task.get("pre_any", []),
            "pre_all": task.get("pre_all", []),
            "parent_active": task.get("parent_active", []),
        })
    rows.sort(key=lambda x: int(x["quest_id"]))
    missing = sorted(NAMES - {str(row["name"]) for row in rows})
    result = {"row_count": len(rows), "missing_names": missing, "tasks": rows}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "missing": missing, "output": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
