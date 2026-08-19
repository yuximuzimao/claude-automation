from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
WORKBENCH_HTML = ROOT / "data/routes/route-atlas-workbench.html"


def load_source_routes() -> dict:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    required_groups = {"集结红龙 → 触动陷阱 → 考达拉户外收尾", "琥珀崖直飞牦牛村 → 横贯冰原转场"}
    current_titles = {group.get("title") for group in routes["borean"].get("stepGroups", [])}
    if required_groups <= current_titles:
        return routes

    # Recovery path for a stale-index rewrite: the published HTML is generated only after release
    # gates pass, so until the next successful build it remains the last known-good embedded route.
    html = WORKBENCH_HTML.read_text(encoding="utf-8")
    marker = "const ROUTES=/* ROUTE_DATA_START */"
    start = html.index(marker) + len(marker)
    embedded, _ = json.JSONDecoder().raw_decode(html[start:])
    embedded_titles = {group.get("title") for group in embedded["borean"].get("stepGroups", [])}
    if not required_groups <= embedded_titles:
        raise RuntimeError("Neither current route nor published workbench contains the stable Borean anchors")
    routes["borean"] = embedded["borean"]
    return routes


def p(x, y, title, action, kind="quest", note="", transport="ride", flag=False):
    return [x, y, title, action, kind, note, transport, flag]


def main() -> None:
    routes = load_source_routes()
    route = routes["borean"]
    points = route["points"]
    groups = route["stepGroups"]

    # Use semantic group anchors, never naked point/group indexes: later insertions change indexes.
    coldarra_close_index = next(i for i, group in enumerate(groups) if group.get("title") == "集结红龙 → 触动陷阱 → 考达拉户外收尾")
    transfer_group = next(group for group in groups if group.get("title") == "琥珀崖直飞牦牛村 → 横贯冰原转场")
    prefix_groups = groups[: coldarra_close_index + 1]
    prefix_end = prefix_groups[-1]["end"] + 1
    prefix_points = points[:prefix_end]
    transfer_points = points[transfer_group["start"] : transfer_group["end"] + 1]

    suffix = []
    new_groups = []

    def add_group(title: str, summary: str, rows: list[list], fivebox_check: str = "") -> None:
        start = len(prefix_points) + len(suffix)
        suffix.extend(rows)
        end = len(prefix_points) + len(suffix) - 1
        group = {"start": start, "end": end, "title": title, "summary": summary}
        if fivebox_check:
            group["fivebox_check"] = fivebox_check
        new_groups.append(group)

    add_group(
        "永生之盾收尾 → 系统鸟回琥珀崖",
        "考达拉户外任务结束后从永生之盾乘系统鸟回琥珀崖，落地后沿道路北上；钢腭车队就在去博古洛克的必经方向。",
        [
            p(33.31, 34.54, "考达拉·户外任务结束", "《触动陷阱》交付后直接返回永生之盾飞行点，不进入魔枢", "transition"),
            p(33.20, 34.45, "永生之盾·准备转北部", "到飞行管理员处，乘系统鸟返回琥珀崖", "transition"),
            p(45.20, 33.35, "系统鸟：考达拉 → 琥珀崖", "抵达琥珀崖后沿道路骑马北上，先经过钢腭车队战场", "transition", "", "taxi"),
        ],
    )

    add_group(
        "钢腭战场顺路清 → 博古洛克开场",
        "沿琥珀崖到博古洛克的必经路线直接完成《攻击！》《亡者的尊严》《让他们安息》，随后继续北上开博古洛克飞行点并完成第一轮交接。",
        [
            p(48.45, 19.74, "钢腭车队", "接《攻击！》；接《亡者的尊严》；接《让他们安息》"),
            p(49.40, 23.50, "钢腭车队战场", "做《亡者的尊严》：主控对地上的车队卫兵/工人尸体使用任务火把累计10具；同时做《让他们安息》；做《攻击！》", note="《亡者的尊严》烧尸体进度五号共享，主控完成10具即可。"),
            p(48.45, 19.74, "钢腭车队", "交《亡者的尊严》；交《让他们安息》"),
            p(50.28, 9.72, "博古洛克前哨站", "开启博古洛克飞行点；交《攻击！》；交《立即前往博古洛克前哨站！》→接《睿智的气元素》；接《国王姆嘎姆嘎》", "hub"),
        ],
    )

    add_group(
        "沸点途中做学习沟通 → 先推进冬鳞Hub链",
        "交《睿智的气元素》接《沸点》；做两个元素后进入冬鳞区，先完成《学习沟通》并接《冬鳞鱼人的贸易》。裂谷监测暂不下洞，留到最终一次洞穴通行与钥匙、护送、《决不投降！》合并。",
        [
            p(46.57, 9.35, "因波莉安", "交《睿智的气元素》→接《沸点》", "hub"),
            p(50.20, 15.10, "火元素西米尔", "做《沸点》：把西米尔打到认输/提交状态"),
            p(45.60, 13.60, "水元素卓恩", "做《沸点》：把卓恩打到认输/提交状态；随后继续往冬鳞避难所"),
            p(43.50, 13.97, "冬鳞避难所·国王姆嘎姆嘎", "交《国王姆嘎姆嘎》→接《学习沟通》", "hub"),
            p(42.00, 17.00, "斯卡德尔尸体", "做《学习沟通》：击杀一次斯卡德尔后，五个角色依次选中同一具尸体并各自使用《空贝壳》一次", note="进度不共享，但同一具尸体可以连续供五号使用，不需要击杀五次。"),
            p(43.50, 13.97, "冬鳞避难所·国王姆嘎姆嘎", "交《学习沟通》→接《冬鳞鱼人的贸易》", "hub"),
        ],
    )

    add_group(
        "冬鳞外圈连续推进 → 接决不投降",
        "先在外圈完成《冬鳞鱼人的贸易》，再连续推进《救救蝌蚪！》《就是他们！》《我被敲竹杠了！》《咕噜咕噜呜啦哇啦！》《备用的鱼人服》，直到从国王处接到《决不投降！》。这一轮不提前进洞。",
        [
            p(40.00, 19.00, "冬鳞鱼人外圈", "做《冬鳞鱼人的贸易》：优先拾取地面的冬鳞蚌壳；地面不够时再杀冬鳞巡滩者/智者/战士补缺", note="蚌壳既可地面拾取也可打怪获得；首组实跑确认直接拾取更快。"),
            p(43.50, 13.97, "冬鳞避难所", "交《冬鳞鱼人的贸易》→接《救救蝌蚪！》；接《就是他们！》", "hub"),
            p(39.50, 20.00, "冬鳞鱼人第二轮", "做《救救蝌蚪！》；做《就是他们！》", note="《救救蝌蚪！》20只蝌蚪进度五号共享，主控完成即可。"),
            p(43.30, 13.80, "冬鳞避难所", "交《救救蝌蚪！》→接《我被敲竹杠了！》；交《就是他们！》", "hub"),
            p(42.00, 12.77, "姆姆咕咕 / 屠夫布咕布噜", "交《我被敲竹杠了！》→接《咕噜咕噜呜啦哇啦！》；接《美味炖鲸肉》", "hub"),
            p(39.80, 9.50, "幽光海湾", "做《咕噜咕噜呜啦哇啦！》：击杀咕拉咕拉并取得任务物；同时做《美味炖鲸肉》逆戟鲸脂肪"),
            p(42.00, 12.90, "冬鳞Hub", "交《咕噜咕噜呜啦哇啦！》→接《备用的鱼人服》；交《美味炖鲸肉》", "hub"),
            p(43.50, 13.97, "国王姆嘎姆嘎", "交《备用的鱼人服》→接《决不投降！》", "hub"),
        ],
        fivebox_check="《冬鳞鱼人的贸易》的地面蚌壳拾取是否五号共享尚未实测；本轮请只观察同一地面蚌壳被一个角色拾取后其它角色的任务计数是否同步。",
    )

    add_group(
        "冬鳞洞穴一次通行：裂谷 + 钥匙 + 护送 + 决不投降",
        "接到《决不投降！》后只进一次冬鳞洞穴：沿路先做裂谷监测，再接并完成钥匙任务；交钥匙后接护送，并在同一洞穴通行中完成《决不投降！》，最后随护送路线出洞回避难所集中交付。",
        [
            p(40.10, 19.90, "冬鳞洞穴裂谷异常", "做《监视裂谷：冬鳞洞穴》：在异常点附近主动使用《奥术测量器》取得读数", note="不会自动完成，必须主动使用测量器。"),
            p(37.80, 23.10, "冬鳞洞穴NPC", "接《钥匙管理者呜啦咕噜》"),
            p(39.17, 22.61, "钥匙管理者呜啦咕噜", "做《钥匙管理者呜啦咕噜》：击杀钥匙管理者并取得钥匙"),
            p(37.84, 23.23, "咕啦咕啦", "交《钥匙管理者呜啦咕噜》→接《逃离冬鳞洞穴》"),
            p(37.54, 27.53, "克拉西姆斯", "接到护送后沿护送路线继续深入/前进，在同一洞穴通行中完成《决不投降！》，然后继续护送克拉西姆斯出洞，完成《逃离冬鳞洞穴》"),
            p(43.50, 13.97, "冬鳞避难所·国王姆嘎姆嘎", "交《决不投降！》；交《逃离冬鳞洞穴》；冬鳞主线闭环", "hub"),
        ],
    )

    add_group(
        "沸点交付 → 风暴微粒 → 空气的幻象",
        "回因波莉安交《沸点》接《风暴微粒》，完成后回博古洛克做《空气的幻象》仪式并接犸格莫斯两条任务。",
        [
            p(46.57, 9.35, "因波莉安", "交《沸点》→接《风暴微粒》", "hub"),
            p(43.95, 9.22, "狂怒的雷暴", "做《风暴微粒》"),
            p(46.57, 9.35, "因波莉安", "交《风暴微粒》→接《返回灵语者身边》", "hub"),
            p(50.28, 9.72, "斯纳尔芬 / 图腾仪式", "交《返回灵语者身边》→接《空气的幻象》；对斯纳尔芬旁的图腾使用《因波莉安的原始精华》完成仪式；交《空气的幻象》→接《先知格雷姆沃克之魂》；接《向犸格莫斯复仇》", "hub", "《空气的幻象》就在斯纳尔芬旁的图腾原地完成，不需要去野外找幻象目标。"),
        ],
    )

    add_group(
        "犸格莫斯洞穴闭环",
        "完成《卡加尼舒》和《向犸格莫斯复仇》，拾取先知遗骸后回博古洛克一次性交付。",
        [
            p(56.17, 9.11, "犸格莫斯·先知灵魂", "交《先知格雷姆沃克之魂》→接《卡加尼舒》"),
            p(56.00, 12.00, "犸格莫斯洞穴", "做《卡加尼舒》：击杀卡加尼舒取得神像，再对先知格雷姆沃克的残骸使用神像；同时做《向犸格莫斯复仇》", note="拿到神像后还必须对洞内先知残骸使用，不能只杀命名怪。"),
            p(56.17, 9.11, "先知格雷姆沃克灵魂脚下 / 遗骸", "交《卡加尼舒》→接《落叶归根》；立即拾取先知格雷姆沃克灵魂脚下的《先知格雷姆沃克的遗骸》"),
            p(50.00, 9.90, "博古洛克", "交《落叶归根》；交《向犸格莫斯复仇》", "hub"),
        ],
    )

    add_group(
        "博古洛克飞琥珀崖 → 裂谷监测交付",
        "北部任务结束后从博古洛克乘系统鸟到琥珀崖，交《监视裂谷：冬鳞洞穴》。",
        [
            p(50.28, 9.72, "博古洛克飞行点", "乘系统鸟前往琥珀崖", "transition"),
            p(44.98, 33.38, "琥珀崖·盖伦", "交《监视裂谷：冬鳞洞穴》；裂谷监测链闭环", "hub", "", "taxi"),
        ],
    )

    # Preserve the already-audited Amber Ledge -> Taunka'le -> Dragonblight transfer block by semantic anchor.
    add_group(
        "琥珀崖直飞牦牛村 → 横贯冰原转场",
        "琥珀崖收尾后直接乘系统鸟飞牦牛村；接《横贯冰原》并护送撤离者进入龙骨荒野。《前往莫亚基港口》继续携带。",
        transfer_points,
    )

    route["points"] = prefix_points + suffix
    route["stepGroups"] = prefix_groups + new_groups
    ROUTES.write_text(json.dumps(routes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "prefix_points": len(prefix_points),
        "suffix_points": len(suffix),
        "total_points": len(route["points"]),
        "step_groups": len(route["stepGroups"]),
        "removed_quest": 11591,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
