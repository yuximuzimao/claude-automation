from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data" / "route-atlas" / "workbench-routes.json"


def main() -> None:
    data = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = data["zang"]
    points = route["points"]

    expected_titles = ["塞纳里奥开场", "沼泽鼠首次", "暗泽湖 / 第一泵"]
    actual_titles = [str(points[i][2]) for i in range(3)]
    if actual_titles != expected_titles:
        raise SystemExit(f"unexpected Zang opening: {actual_titles!r}")
    if any("逃离暗泽村" in str(p[3]) for p in points):
        raise SystemExit("9752 already exists in workbench route; refusing duplicate patch")

    opening = list(points[0])
    opening[3] = (
        "若从地狱火携带《塞纳里奥远征队》，先交《塞纳里奥远征队》；"
        "接《赞加沼泽的植物》；"
        "接《暗泽湖的异常》；接《失踪的先遣队》；接《观察者莉萨奥》；"
        "接《崩溃的平衡》；接《暗潮纳迦的首领》；接《血鳞纳迦的领袖》；"
        "接《古树的祝福》；接《暗泽部族》；接《监护者哈穆特》；"
        "在营地内交《监护者哈穆特》接《热情的欢迎》"
    )

    dark_lake = [
        70.75,
        80.15,
        "暗泽湖",
        "完成《暗泽湖的异常》；随后继续向东南进入暗泽村",
        "east",
        "",
    ]
    kayra = [
        83.38,
        85.54,
        "暗泽村·凯拉",
        "在暗泽村完成《暗泽部族》；找到凯拉·长鬃，五号都接好《逃离暗泽村》后一起护送她返回塞纳里奥庇护所",
        "east",
        "护送一次即可让五个已接任务的角色一起完成；保持队伍跟随凯拉，不需要逐号重复护送。",
    ]
    cenarion_return = [
        78.40,
        62.02,
        "护送回塞纳里奥",
        "交《逃离暗泽村》；交《暗泽湖的异常》接《乌鸦的飞翔》；完成《乌鸦的飞翔》后交《乌鸦的飞翔》接《恢复平衡》；交《暗泽部族》接《阴冷之地》；接《拯救孢子人》；接《保护观察者》",
        "east",
        "",
    ]

    old_first_pump = list(points[2])
    old_first_pump[3] = (
        "从沼泽鼠岗哨继续东部大环，同时推进《古树的祝福》《沼牙的威胁》《崩溃的平衡》"
        "《别再提蘑菇了！》《时尚无罪》《厚重多头蛇鳞片》《热情的欢迎》《阴冷之地》"
        "《拯救孢子人》《保护观察者》《暗潮纳迦的首领》；"
        "《热情的欢迎》只随路累计纳迦爪子，留到第二/第三泵重叠区补齐。"
        "完成《沼牙的威胁》后回沼泽鼠交《沼牙的威胁》接《对方的尊重》；"
        "随后到暗泽湖完成《恢复平衡》第一处抽水泵"
    )

    # Insert three explicit opening stops. Original point 1+ therefore shifts by +3.
    route["points"] = [opening, dark_lake, kayra, cenarion_return, list(points[1]), old_first_pump] + [list(p) for p in points[3:]]

    groups = route["stepGroups"]
    if groups[0]["start"] != 0 or groups[0]["end"] != 2:
        raise SystemExit("unexpected Zang first stepGroup bounds")
    groups[0]["end"] = 5
    groups[0]["title"] = "塞纳里奥开场 → 暗泽村护送 → 沼泽鼠 → 第一泵"
    groups[0]["summary"] = (
        "塞纳里奥接齐开场任务后先做暗泽湖和暗泽村；从凯拉处五号一起完成《逃离暗泽村》护送并回到塞纳里奥，"
        "同次交付解锁南部后续和《恢复平衡》，再到沼泽鼠接东部任务并完成第一处抽水泵。"
    )
    groups[0]["timing"] = {
        "centerMinutes": 15.0,
        "rangeMinutes": [12.3, 17.7],
        "includeInTotal": True,
    }
    for group in groups[1:]:
        group["start"] += 3
        group["end"] += 3

    # Restore the old reusable-route rule for q9802: carry it as background inventory;
    # never create a dedicated farm. Give it a natural mid-map and final turn-in check.
    touched_mid = False
    touched_final = False
    for point in route["points"]:
        title = str(point[2])
        if "塞纳里奥集中交付" in title and "赞加沼泽的植物" not in str(point[3]):
            point[3] = str(point[3]) + "；若五个角色都已有10株未鉴定过的植物，交《赞加沼泽的植物》；不足就继续保留，不专门补刷"
            touched_mid = True
        if "最终塞纳里奥" in title and "赞加沼泽的植物" not in str(point[3]):
            point[3] = str(point[3]) + "；若《赞加沼泽的植物》仍在日志且五个角色都已满10株，交《赞加沼泽的植物》；不足就不专门补刷"
            touched_final = True
    if not touched_mid:
        raise SystemExit("could not locate Zang mid Cenarion turn-in point for q9802")
    # Some current workbench versions end elsewhere and have no final Cenarion stop; mid check is sufficient.

    ROUTES.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "points_before": len(points),
        "points_after": len(route["points"]),
        "q9752_present": any("逃离暗泽村" in str(p[3]) for p in route["points"]),
        "q9802_present": any("赞加沼泽的植物" in str(p[3]) for p in route["points"]),
        "q9912_present": any("塞纳里奥远征队" in str(p[3]) for p in route["points"]),
        "mid_9802_check": touched_mid,
        "final_9802_check": touched_final,
        "first_group": route["stepGroups"][0],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
