import json
import re
from pathlib import Path

from scripts.audit_route_atlas_player_text import main as audit_player_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def test_workbench_contains_all_current_route_maps_and_assets():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    assert set(routes) >= {"zang", "nagrand", "borean"}
    assert len(routes["borean"]["points"]) >= 224
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    assert "交《集结红龙》→接《触动陷阱》" in borean_text
    assert "冬鳞洞穴一次通行：裂谷 + 钥匙 + 护送 + 决不投降" in borean_text
    assert "龙骨荒野边界" in borean_text
    for route in routes.values():
        assert route["points"]
        assert (ROOT / "data/routes" / route["image"]).exists()


def test_route_text_never_leaks_internal_action_tokens():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    visible = "\n".join(
        str(value)
        for route in routes.values()
        for point in route["points"]
        for value in point[2:6]
    )
    assert not re.search(
        r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}", visible
    )


def test_player_visible_handoffs_are_explicit_and_lifecycle_closes():
    audit_player_text()


def test_single_workbench_uses_established_outland_layout_and_manual_follow():
    html = HTML.read_text(encoding="utf-8")
    for required in (
        'class="top"',
        'class="badge"',
        'class="controls"',
        'class="shell"',
        'class="hud"',
        'class="card legend"',
        'class="card stepsCard"',
    ):
        assert required in html
    assert '<input id="follow" type="checkbox"> 跟随当前段' in html
    assert "if(!document.getElementById('follow').checked)return" in html
    assert 'const ROUTES=/* ROUTE_DATA_START */' in html
    assert '/* ROUTE_DATA_END */;' in html



def test_borean_player_steps_group_geometry_without_losing_points():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean = routes["borean"]
    groups = borean["stepGroups"]
    assert len(groups) >= 66
    covered = [i for group in groups for i in range(group["start"], group["end"] + 1)]
    assert covered == list(range(len(borean["points"])))
    titles = [group["title"] for group in groups]
    assert "码头接齐回音海岸任务" in titles
    assert "固定零件 + 克瓦迪尔三任务 + 短护送" in titles
    assert "护送交付并批量换下一轮任务" in titles
    assert "四艘船 + 奥拉布斯一次海岸闭环" in titles


def test_borean_flight_point_is_deferred_to_magic_carpet_handoff():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    points = routes["borean"]["points"]
    flight_actions = [(p[2], p[3]) for p in points if "开启战歌要塞飞行点" in p[3]]
    assert flight_actions == [("驭风大师图波尔", flight_actions[0][1])]
    assert "魔法飞毯" in flight_actions[0][1]


def test_workbench_step_animation_is_group_aware():
    html = HTML.read_text(encoding="utf-8")
    assert "G=buildGroups(r)" in html
    assert "function groupSegRange" in html
    assert "function prepareAnim" in html
    assert "步骤 ${cur+1}/${G.length}" in html


def test_workbench_hud_lists_every_action_in_current_logical_step():
    html = HTML.read_text(encoding="utf-8")
    assert "/* HUD_GROUP_ACTIONS_START */" in html
    assert "S.slice(gr.start,gr.end+1)" in html
    assert "point.label}：${point.action" in html
    assert "el.style.whiteSpace='pre-line'" in html


def test_borean_amber_ledge_chain_is_explicit_in_player_text():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean = routes["borean"]
    groups = borean["stepGroups"]
    assert "交《调查》→接《苔原上的审讯》" in groups[48]["summary"]
    assert "交《监视裂谷：峭壁断层》→接《监视裂谷：冬鳞洞穴》" in groups[48]["summary"]
    assert "上法师塔二楼交《苔原上的审讯》→接《说服的艺术》" in groups[49]["summary"]
    assert "交《准备飞翔》→接《营救艾瓦诺尔》" in groups[50]["summary"]
    borean_text = json.dumps(borean, ensure_ascii=False)
    assert "法师塔二楼·诺曼提斯" in borean_text
    assert "下楼找多纳森交《分享情报》→接《与时间赛跑》" in borean_text


def test_borean_monster_drop_quest_starters_document_sources_and_conditions():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    required = (
        "收割者伊斯里克斯",
        "伊斯里克斯的甲壳",
        "战歌要塞南门",
        "黑暗堕落者达斯·血痕",
        "Vial of Fresh Blood",
        "必须先完成《乔装潜入》",
        "考达拉缚法者",
        "Scintillating Fragment",
        "不要误刷名称相近的考达拉织法者",
    )
    for text in required:
        assert text in borean_text


def test_borean_massive_moth_egg_is_merged_with_pollinated_moth_sweep():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    for text in (
        "《授粉的巨蛾》",
        "《巨大的蛾卵》",
        "48.55,59.04",
        "Massive Glowing Egg",
        "巨蛋旁集中刷完",
        "不再为巨蛋上山",
    ):
        assert text in borean_text
    assert "49.6,66.1" not in borean_text


def test_borean_mercy_kill_prisoner_release_is_fivebox_shared():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    for text in ("《慈悲为怀》", "囚犯数量五号共享", "主控开笼即可同步推进全队"):
        assert text in borean_text


def test_workbench_marks_logical_steps_that_have_execution_notes():
    html = HTML.read_text(encoding="utf-8")
    assert ".noteTag{" in html
    assert '<span class="noteTag">有备注</span>' in html
    assert "notes?`备注：${notes}`:''" in html
    assert "hn.style.display=notes?'block':'none'" in html


def test_borean_hidden_mechanics_audit_keeps_critical_execution_clues():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    required = (
        "55.3,50.8",
        "海象人仪式物品",
        "地精手榴弹",
        "载具技能栏",
        "纳克萨纳尔传送器",
        "风魂图腾",
        "祖母的捕魂器",
        "奥术测量器",
        "先知格雷姆沃克灵魂脚下",
        "任务自带飞行/传送",
    )
    for text in required:
        assert text in borean_text


def test_outland_monster_drop_quest_starters_document_sources_and_conditions():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    zang_text = json.dumps(routes["zang"], ensure_ascii=False)
    nagrand_text = json.dumps(routes["nagrand"], ensure_ascii=False)
    for text in ("蒸汽泵监工", "血鳞监工", "血鳞召潮者", "《抽水泵结构图》", "《恢复平衡》", "铁藤种子"):
        assert text in zang_text
    for text in ("伯爵”昂古拉", "Ungula's Mandible", "《沼泽中的伯爵》", "必掉任务起始物"):
        assert text in zang_text
    for text in ("枯萎的巨人", "Withered Basidium", "《枯萎的孢芽》", "不为它额外补刷"):
        assert text in zang_text
    for text in ("三人一组巡逻的暗血入侵者", "Murkblood Invasion Plans", "《暗血入侵者》", "不按固定点等候"):
        assert text in nagrand_text


def test_deprecated_route_atlas_htmls_are_not_kept_in_routes_directory():
    forbidden = {
        "outland-route-atlas.html",
        "zangarmarsh-authoritative-v2.html",
        "zangarmarsh-current-remaining-route.html",
        "zangarmarsh-final-reusable-route-preview.html",
        "zangarmarsh-r11-route-preview.html",
        "zangarmarsh-route-atlas-prototype.html",
        "borean-tundra-leveling-clear-v1-preview.html",
        "borean-tundra-partial-r6-preview.html",
    }
    existing = {p.name for p in (ROOT / "data/routes").glob("*.html")}
    assert forbidden.isdisjoint(existing)
    assert HTML.name in existing
