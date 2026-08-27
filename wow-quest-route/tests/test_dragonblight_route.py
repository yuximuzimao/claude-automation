import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
COVERAGE = ROOT / "data/route-atlas/dragonblight-route-coverage.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def load_routes():
    return json.loads(ROUTES.read_text(encoding="utf-8"))


def route_text(route):
    values = []
    for point in route["points"]:
        values.extend(str(value) for value in point[2:6])
        if len(point) > 8 and point[8]:
            values.append(str(point[8]))
    return "\n".join(values)


def player_visible_text(route):
    values = [str(route.get(key, "")) for key in ("title", "sub", "badgeTitle", "badge", "legend", "footer")]
    for group in route["stepGroups"]:
        values.extend((str(group.get("title", "")), str(group.get("summary", ""))))
    values.append(route_text(route))
    return "\n".join(values)


def test_dragonblight_route_is_in_single_workbench_with_map_asset():
    routes = load_routes()
    assert "dragonblight" in routes
    route = routes["dragonblight"]
    assert route["image"] == "maps/65-dragonblight-hd.jpg"
    assert (ROOT / "data/routes" / route["image"]).exists()
    assert len(route["points"]) == 194
    assert len(route["stepGroups"]) == 51
    assert "龙骨荒野" in HTML.read_text(encoding="utf-8")


def test_dragonblight_step_groups_cover_every_geometry_point_once():
    route = load_routes()["dragonblight"]
    covered = [i for group in route["stepGroups"] for i in range(group["start"], group["end"] + 1)]
    assert covered == list(range(len(route["points"])))


def test_dragonblight_foundation_coverage_has_no_accidental_missing_tasks():
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    assert coverage["missing"] == []
    assert coverage["unexpected"] == []
    assert coverage["expected_world_task_count"] == coverage["covered_task_count"] + len(coverage["intentional_skip"])
    assert set(coverage["intentional_skip"]) == {"11979", "11996"}


def test_dragonblight_route_keeps_core_special_mechanics_visible():
    text = route_text(load_routes()["dragonblight"])
    required = (
        "《血之魔典》此时还不能刷；必须先回阿格玛向高尔特上尉交《死亡名单：高阶教徒扎古斯》",
        "五号各自插1面旗",
        "等张嘴时扔炸药",
        "五号分别召伐木机",
        "腐蚀性唾液",
        "五号分别点击深海珍珠",
        "珍珠约1分40秒刷新",
        "用图尔凯的呼吸气囊下潜",
        "吉加托尔精英支线留80后",
        "龙眠为多层结构",
        "只由主控放1个毁灭结界",
        "沙漏",
        "上顶层敲钟",
        "主控召红龙",
        "等安提沃克出现后必须下龙，用角色本体击杀",
    )
    for value in required:
        assert value in text


def test_dragonblight_route_uses_transport_and_player_facing_narf_fix():
    route = load_routes()["dragonblight"]
    text = route_text(route)
    assert "纳尔弗约(54.5,23.6)，在哨站西侧。" in text
    assert "Questie" not in player_visible_text(route)
    assert "人工锚点" not in player_visible_text(route)
    assert "使用炉石：阿格玛之锤" in text
    assert "乘系统鸟：库卡隆先锋营地 → 龙眠神殿" in text
    assert "乘系统鸟：龙眠神殿 → 库卡隆先锋营地" in text
    assert sum(1 for point in route["points"] if point[6] == "hearth") == 5
    assert sum(1 for point in route["points"] if point[6] == "taxi") >= 2


def test_dragonblight_route_hides_internal_route_design_copy():
    route = load_routes()["dragonblight"]
    text = player_visible_text(route)
    forbidden = (
        "反向面包屑",
        "目标簇",
        "前置逐轮",
        "候选覆盖",
        "人工锚点",
        "不强塞",
        "严格链",
    )
    for value in forbidden:
        assert value not in text
    assert "《魔法王国达拉然》" in text
    assert "交《阻碍协议》《奇怪的设备》 → 接《投影和计划》" in text
    assert "奥拉斯塔萨 → 交《强大的猛犸人》 → 接《隐居的铭语师》" in text
    assert not re.search(r"·第[一二三四五六七八九十]+轮", text)
    assert not re.search(r"(?<![\d.])\b(?:1[12]\d{3}|13\d{3})\b(?![\d.])", text)


def test_dragonblight_fivebox_checks_are_separate_and_actionable():
    route = load_routes()["dragonblight"]
    checks = [point[8] for point in route["points"] if len(point) > 8 and point[8]]
    assert checks
    assert all("请确认" in check for check in checks)
    assert all("共享未知" not in check and "待实测" not in check for check in checks)
    assert any("同一具" in check or "同一尸体" in check for check in checks)
    assert any("其他四" in check for check in checks)
    assert any("载具" in check for check in checks)
    for point in route["points"]:
        if len(point) > 8 and point[8]:
            assert "请确认" not in str(point[5])


def test_dragonblight_html_renders_fivebox_checks_as_independent_ui():
    html = HTML.read_text(encoding="utf-8")
    assert "fiveboxTag" in html
    assert "hudFivebox" in html
    assert "groupFivebox" in html
    assert "fivebox:p[8]||''" in html
    assert "五开待实测" in html


def test_dragonblight_corrected_objective_locations_are_preserved():
    route = load_routes()["dragonblight"]
    by_title: dict[str, list] = {}
    for point in route["points"]:
        by_title.setdefault(point[2], []).append(point[:2])
    expected = {
        "深海珍珠": [[34.0, 83.46]],
        "翡翠圣地东南端": [[65.0, 78.0]],
        "火炬之环": [[57.0, 76.0]],
        "冰心洞穴": [[55.3, 11.0]],
        "钻雪虫·拉特尔博尔": [[50.67, 17.8]],
        "红玉圣地·巨树下洞穴": [[48.0, 50.0]],
        "奈萨里奥之喉·洞穴深处": [[31.75, 30.46], [31.93, 28.17]],
                "奈萨里奥之喉·腐烂者洛森": [[31.44, 30.95]],
        "新壁炉谷·兵营": [[69.7, 71.9]],
        "新壁炉谷·修道院一楼图书馆": [[73.4, 72.6]],
        "新壁炉谷·海滩营地": [[71.6, 80.4]],
    }
    for title, coords in expected.items():
        assert by_title.get(title) == coords


def test_dragonblight_route_stays_reusable_not_live_progress_crop():
    route = load_routes()["dragonblight"]
    first = route["points"][0]
    assert "交《横贯冰原》" in first[3]
    assert "接《牦牛人中的牛头人》" in first[3]
    dumped = json.dumps(route, ensure_ascii=False)
    assert "1093065" not in dumped
    assert "首组当前状态" not in player_visible_text(route)
