import json
import re
from pathlib import Path

from scripts.audit_route_atlas_player_text import main as audit_player_text

# Mixed suite by design: cross-map UI invariants and route-shape snapshots coexist here.
# Exact step/point counts, fixed indices, titles and exact player copy are snapshot references,
# not universal release gates. Select only tests that protect the current authorized change.
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def test_workbench_contains_all_current_route_maps_and_assets():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    assert set(routes) >= {"zang", "nagrand", "borean"}
    assert len(routes["borean"]["points"]) >= 224
    borean = routes["borean"]
    borean_text = json.dumps(borean, ensure_ascii=False)
    assert borean["uiStandard"] == "semantic-hud-v45"
    assert "莱洛拉斯" in borean["stepGroups"][56]["actionHtml"]
    assert "集结红龙" in borean["stepGroups"][56]["actionHtml"]
    assert "触动陷阱" in borean["stepGroups"][56]["actionHtml"]
    assert "冬鳞洞穴：裂谷 → 钥匙 → 护送" in borean_text
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


def test_dragonblight_is_fully_promoted_to_semantic_hud():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    dragon = routes["dragonblight"]
    assert dragon["uiStandard"] == "semantic-hud-v45"
    assert len(dragon["stepGroups"]) == 51
    step45 = dragon["stepGroups"][44]
    assert step45["title"] == "怨毒镇 → 斯古莉 → 祈祷之书 → 完美伪装 → 狼狈不堪"
    for text in ("高级执行官乌洛斯", "斯古莉探员", "祈祷之书", "完美的伪装", "狼狈不堪"):
        assert text in step45["actionHtml"]
    html = HTML.read_text(encoding="utf-8")
    assert "raSemanticPrototypeStyle" in html
    assert "↳</span><span class=\"ra-verb\">做" in html
    assert "ra-task ra-turnin" in html
    assert "ra-task ra-accept" in html
    assert "ra-task ra-do-task" in html
    assert "ra-map-pulse" not in html
    assert "raFlashMapPoint" not in html


def test_grizzly_is_fully_promoted_to_semantic_hud_and_handoffs_are_locked():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    grizzly = routes["grizzly"]
    assert grizzly["uiStandard"] == "semantic-hud-v45"
    assert len(grizzly["stepGroups"]) == 11
    assert len(grizzly["points"]) == 79
    assert all(group.get("actionHtml") for group in grizzly["stepGroups"])

    step2 = grizzly["stepGroups"][1]["actionHtml"]
    assert "征服者克雷娜" in step2 and "米克哈尔的日记" in step2 and "高戈娜" in step2
    step7 = grizzly["stepGroups"][6]["actionHtml"]
    assert "斥候沃塔肯" in step7 and "符文中的预言" in step7 and "先知帕鲁纳" in step7
    step9 = grizzly["stepGroups"][8]["actionHtml"]
    assert "哈里森·琼斯" in step9 and "克拉斯" in step9 and "萨莎" in step9
    step10 = grizzly["stepGroups"][9]["actionHtml"]
    for text in ("斥候沃塔肯", "勘探员罗卡尔", "托尔玛克", "洛肯的命令"):
        assert text in step10

    html = HTML.read_text(encoding="utf-8")
    assert '<span class="ra-task ra-turnin">前往征服堡，自求多福吧！</span>' in html
    assert '<span class="ra-task ra-accept">征服者的指派</span>' in html
    assert '<span class="ra-task ra-do-task">沃德伦的领主</span>' in html


def test_zuldrak_is_fully_promoted_to_semantic_hud_and_handoffs_are_locked():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    zuldrak = routes["zuldrak"]
    assert zuldrak["uiStandard"] == "semantic-hud-v45"
    assert len(zuldrak["stepGroups"]) == 12
    assert len(zuldrak["points"]) == 107
    assert all(group.get("actionHtml") for group in zuldrak["stepGroups"])

    coverage = json.loads((ROOT / "data/route-atlas/zuldrak-route-coverage.json").read_text(encoding="utf-8"))
    assert coverage["formal_task_count"] == 105
    assert coverage["covered_task_count"] == 105
    assert coverage["missing"] == []
    assert coverage["unexpected"] == []

    step1 = zuldrak["stepGroups"][0]["actionHtml"]
    for text in ("莉安娜中士", "萨满长者莫奇", "怒爪酋长", "北伐军领主兰迪加", "悬浮的达库鲁命令卷轴"):
        assert text in step1
    step5 = zuldrak["stepGroups"][4]["actionHtml"]
    for text in ("斯塔哈默中士", "玛加下士", "奇怪的魔精"):
        assert text in step5
    step6 = zuldrak["stepGroups"][5]["actionHtml"]
    for text in ("穆尔沙·月影中士", "专家考格维尔", "狡猾的维克斯", "勇士的召唤！"):
        assert text in step6
    step7 = zuldrak["stepGroups"][6]["actionHtml"]
    assert "古尔戈索克" in step7 and "巨魔仆从伍迪" in step7
    later_text = "\n".join(group["actionHtml"] for group in zuldrak["stepGroups"][6:])
    for text in ("巫医库弗", "剥皮师埃霍奈", "记载者图基尼", "元素驯服者德苟达"):
        assert text in later_text

    zuldrak_text = json.dumps(zuldrak, ensure_ascii=False)
    for text in ("干瘪巨魔", "尸灵项圈", "某种邀请……", "西莱图斯祭坛", "奇怪的魔精"):
        assert text in zuldrak_text
    assert "返回已开启的古达克飞行点" not in zuldrak_text


def test_route_level_inert_legends_are_not_embedded_in_player_html():
    html = HTML.read_text(encoding="utf-8")
    for stale in ("<b>北风：</b>", "<b>灰熊：</b>", "<b>祖达克：</b>"):
        assert stale not in html


def test_borean_player_steps_group_geometry_without_losing_points():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean = routes["borean"]
    groups = borean["stepGroups"]
    assert len(groups) >= 66
    covered = [i for group in groups for i in range(group["start"], group["end"] + 1)]
    assert covered == list(range(len(borean["points"])))
    assert all(group.get("title") for group in groups)
    assert all(group.get("actionHtml") for group in groups)


def test_borean_flight_point_is_deferred_to_magic_carpet_handoff():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean = routes["borean"]
    points = borean["points"]
    flight_actions = [(p[2], p[3]) for p in points if "开飞行点：战歌要塞" in p[3]]
    assert flight_actions == [("战歌要塞飞行点", flight_actions[0][1])]
    assert "驭风大师图波尔" in borean["stepGroups"][6]["actionHtml"]
    assert "魔法飞毯" in borean["stepGroups"][6]["actionHtml"]


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
    assert groups[48]["title"] == "调查 / 峭壁断层 → 琥珀崖"
    assert "图书管理员多纳森" in groups[48]["actionHtml"]
    assert "苔原上的审讯" in groups[48]["actionHtml"]
    assert "监视裂谷：冬鳞洞穴" in groups[48]["actionHtml"]
    assert groups[49]["title"] == "法师塔二楼 → 与时间赛跑 → 苏雷斯塔兹"
    assert "图书管理员诺曼提斯" in groups[49]["actionHtml"]
    assert "图书管理员多纳森" in groups[49]["actionHtml"]
    assert "苏雷斯塔兹" in groups[49]["actionHtml"]
    assert groups[50]["title"] == "营救艾瓦诺尔 → 苏雷斯塔兹 → 考达拉"
    assert "战斗法师安斯姆" in groups[50]["actionHtml"]
    assert "启动任务飞行：考达拉" in groups[50]["actionHtml"]


def test_borean_monster_drop_quest_starters_document_sources_and_conditions():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    required = (
        "收割者伊斯里克斯",
        "伊斯里克斯的甲壳",
        "战歌要塞南门",
        "达斯·血痕",
        "鲜血瓶",
        "完成《乔装潜入》后",
        "考达拉缚法者",
        "闪光碎片",
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
        "巨大的发光蛾卵",
        "目标在巨蛋旁边非常集中",
        "不要把蛋拖到迦莫斯洞穴之后再单独爬山",
    ):
        assert text in borean_text
    assert "49.6,66.1" not in borean_text


def test_borean_mercy_kill_prisoner_release_is_fivebox_shared():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    borean_text = json.dumps(routes["borean"], ensure_ascii=False)
    for text in (
        "《慈悲为怀》",
        "共享：",
        "5把天灾牢笼钥匙",
        "开5个囚笼",
        "同步全队",
    ):
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
        "任务仪式物品",
        "载具栏",
        "外部传送器",
        "内部传送器",
        "风魂图腾",
        "祖母的捕魂器",
        "奥术测量器",
        "先知格雷姆沃克灵魂脚下",
        "启动任务飞行：考达拉",
    )
    for text in required:
        assert text in borean_text


def test_outland_monster_drop_quest_starters_document_sources_and_conditions():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    zang_text = json.dumps(routes["zang"], ensure_ascii=False)
    nagrand_text = json.dumps(routes["nagrand"], ensure_ascii=False)
    for text in ("蒸汽泵监工", "血鳞监工", "血鳞唤潮者", "《抽水泵结构图》", "《恢复平衡》", "铁藤种子"):
        assert text in zang_text
    for text in ("“伯爵”昂古拉", "昂古拉的下颚", "《沼泽中的伯爵》", "必掉"):
        assert text in zang_text
    for text in ("枯萎的巨人", "枯萎的孢芽", "《枯萎的孢芽》", "不为它额外补刷"):
        assert text in zang_text
    for text in ("三人组暗血入侵者", "暗血入侵计划", "《暗血入侵者》", "不按固定点等待"):
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


def test_storm_v45_full_step_cards_and_transport_state_are_locked():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    storm = routes["storm"]
    assert storm["uiStandard"] == "semantic-hud-v45"
    assert len(storm["stepGroups"]) == 20
    assert all(group.get("actionHtml") for group in storm["stepGroups"])

    action_html = "\n".join(group["actionHtml"] for group in storm["stepGroups"])
    assert '<div class="ra-line ra-do-inline"><span class="ra-location">K3西侧</span>' in storm["stepGroups"][1]["actionHtml"]
    assert storm["stepGroups"][0].get("noteHtml", "") == ""
    assert "《清理残骸》" not in storm["stepGroups"][1].get("noteHtml", "")
    assert "按地面安全路线进入雷区；工具可连续拾取，一次通过即可。" in storm["stepGroups"][1].get("noteHtml", "")
    assert "西侧野蛮岭营地优先开粮食箱，每箱约2—4份。" in storm["stepGroups"][1].get("noteHtml", "")
    assert "一个号开始护送即可，结束后五号同步完成。" in storm["stepGroups"][2].get("noteHtml", "")
    assert "准备5把寒铁钥匙，依次开启5个牢笼。" in storm["stepGroups"][2].get("noteHtml", "")
    assert "最南建筑" in storm["stepGroups"][2].get("noteHtml", "")
    assert "两点来回拾取。" in storm["stepGroups"][2].get("noteHtml", "")
    assert "系统飞行：奥杜尔 → 丹尼芬雷" in action_html
    assert "开飞行点：丹尼芬雷" in action_html
    assert "开飞行点：奥杜尔" in action_html
    assert "炉石绑定：格罗玛什坠毁点" in action_html
    assert action_html.count("使用炉石：格罗玛什坠毁点") >= 3
    assert storm["hearthChain"] == ["阿格玛之锤", "格罗玛什坠毁点", "布德克拉格庇护所"]
    assert storm["stepGroups"][4]["title"].startswith("荒弃矿洞")
    assert storm["stepGroups"][8]["title"].endswith("格罗玛什")
    assert storm["stepGroups"][10]["title"].startswith("丹尼芬雷：元素之战")
    assert storm["stepGroups"][13]["title"].startswith("炉石格罗玛什")

    step11_action = storm["stepGroups"][10]["actionHtml"]
    step11_notes = storm["stepGroups"][10].get("noteHtml", "")
    for task_name in ("热与冷", "猎杀间谍", "粘滞清洁", "喂饱安格里姆"):
        assert task_name in step11_action
    for expected_note in (
        "五号分别骑亚米尔德旁的斯诺里",
        "同一具死亡铁巨人只能挖一次",
        "每号先杀怪取得6份任务道具",
        "对座狼尸体使用灵体座狼之牙",
        "五号分别完成《粘滞清洁》",
        "对游荡的冰虫使用安格里姆之牙",
        "雷暴台地的号角碎片五号分别拾取",
    ):
        assert expected_note in step11_notes

    step12_action = storm["stepGroups"][11]["actionHtml"]
    step12_notes = storm["stepGroups"][11].get("noteHtml", "")
    assert "失踪的布莱恩·铜须" in step12_action
    assert 'ra-turnin">失踪的布莱恩·铜须' not in step12_action
    assert "风暴神殿东南" in step12_notes
    assert "唐卡洛开点" in storm["stepGroups"][11]["title"]
    assert "做《见证者与英雄》并接《雷蹄的记忆》" in storm["stepGroups"][11]["summary"]

    assert "从这里进入洞穴" in action_html
    for special_detail in ("右键触发", "载具技能", "海德尼尔鱼叉"):
        assert special_detail not in action_html

    for group in storm["stepGroups"]:
        note_titles = re.findall(r'class="ra-note-task">([^<]+)</div>', group.get("noteHtml", ""))
        assert len(note_titles) == len(set(note_titles))

    coverage = json.loads((ROOT / "data/route-atlas/storm-peaks-route-coverage.json").read_text(encoding="utf-8"))
    assert coverage["formal_task_count"] == 108
    assert coverage["covered_task_count"] == 108
    assert coverage["missing"] == []
    assert coverage["unexpected"] == []
    assert coverage["system_flight_audit"] == [
        {"from": "奥杜尔", "to": "丹尼芬雷", "status": "both_opened_before_departure"},
        {"from": "布德克拉格庇护所", "to": "唐卡洛营地", "status": "both_opened_before_departure"},
    ]
    assert {"K3", "丹尼芬雷", "奥杜尔", "布德克拉格庇护所", "唐卡洛营地"} <= set(coverage["opened_flight_points_final"])

    foundation = json.loads((ROOT / "data/route-atlas/storm-peaks-task-foundation.json").read_text(encoding="utf-8"))
    assert foundation["formal_task_count"] == 108
    assert not any(task.get("fivebox_check") for task in foundation["tasks"])
    for qid in (12981, 12994, 13006, 13046):
        task = next(task for task in foundation["tasks"] if task["quest_id"] == qid)
        assert task["scope_status"].startswith("include_verified_calendar_first_run")
    earthen_oath = next(task for task in foundation["tasks"] if task["quest_id"] == 13005)
    assert [(objective["required_count"], objective["sources"][0]["name"]) for objective in earthen_oath["objectives"]] == [
        (7, "铁哨兵"),
        (20, "铁矮人攻击者"),
    ]

    objective_audit = json.loads((ROOT / "data/route-atlas/objective-anchor-audit.json").read_text(encoding="utf-8"))["routes"]["storm"]
    assert objective_audit["failure_count"] == 0
    assert objective_audit["review_count"] == 0
    assert objective_audit["reviews"] == []

    flight_audit = json.loads((ROOT / "data/route-atlas/flight-state-audit.json").read_text(encoding="utf-8"))["routes"]["storm"]
    assert flight_audit["violation_count"] == 0
    assert flight_audit["unknown_destination_count"] == 0

    html = HTML.read_text(encoding="utf-8")
    assert "raApplySemanticStepCards" in html
    assert "semanticGr=route()?.stepGroups?.[cur]" in html
    assert ".stepsCard .step .sm{display:none!important}" in html
    assert ".stepsCard .ra-step-semantic{display:none!important}" in html
    assert ".hud.ra-semantic-panel" in html
    assert "overflow-y:auto!important" in html
    assert ".ra-flightpoint,.ra-flightpath" in html
    assert "ra-point-anchor" in html


def test_no_cold_weather_flying_route_excludes_skill_gates():
    universe = json.loads((ROOT / "data/route-atlas/northrend-task-universe.json").read_text(encoding="utf-8"))
    by_id = {int(task["quest_id"]): task for task in universe["tasks"]}
    for qid in (12561, 12803, 13060, 13419):
        assert by_id[qid]["cold_weather_flying_gate"] is True
    assert by_id[12561]["required_spell"] == 54197
    assert by_id[12803]["required_spell"] == 54197
    assert by_id[13060]["required_level"] == 77 and by_id[13060]["quest_level"] == 78
    assert by_id[13419]["required_level"] == 77 and by_id[13419]["quest_level"] == 80
    assert by_id[12925]["required_level"] == 77 and by_id[12925]["quest_level"] == 80
    assert by_id[12925]["cold_weather_flying_gate"] is False

    gate_audit = json.loads((ROOT / "data/route-atlas/cold-weather-flying-gate-audit.json").read_text(encoding="utf-8"))
    assert gate_audit["horde_paladin_direct_gate_ids"] == [12561, 12803, 13060, 13419]
    sholazar_blocked = {
        row["quest_id"] for row in [*gate_audit["direct_gates"], *gate_audit["dependency_blocked"]]
        if row["zone_id"] == 3711
    }
    assert len(sholazar_blocked) == 15

    routes = json.loads(DATA.read_text(encoding="utf-8"))
    storm_text = "\n".join(group["actionHtml"] for group in routes["storm"]["stepGroups"])
    assert "终极运输方案" not in storm_text
    assert "借用双足飞龙直接飞往格罗玛什坠毁点" not in storm_text
    assert "借用双足飞龙返回" not in storm_text
