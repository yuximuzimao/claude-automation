from order_review.packing_simulator_service import PackingSimulatorService


COFFEE_CODE = "6977987940138"
COFFEE_7_AMERICAN_CODE = "6980319670023"
COFFEE_7_COCONUT_CODE = "6980319670030"
CANDY_2_CODE = "6976299500108"
ENZYME_TRIAL_CODE = "6979499760037"
YUEXI_SUNSCREEN = "6950328271429"
YUEXI_REPAIR_GIFT_BOX = "6950328273508"


def _service(tmp_path):
    return PackingSimulatorService(case_path=tmp_path / "cases.json")


def test_catalog_view_keeps_full_brand_skeleton_and_pending_records(tmp_path):
    view = _service(tmp_path).catalog_view()

    brands = {item["brandId"]: item for item in view["brands"]}
    assert brands["kgos"]["packingStatus"] == "enabled_single_carton"
    assert brands["yuexi"]["packingStatus"] == "catalog_only"

    active_cartons = {item["cartonId"] for item in view["sections"]["cartons"]}
    pending_cartons = {
        item.get("cartonId") for item in view["sections"]["pendingCartons"]
    }
    assert "carton-16" in active_cartons
    assert "carton-17" in pending_cartons
    assert "carton-18" in pending_cartons
    assert "pending-original-yuexi-cleanser" in pending_cartons
    assert "pending-original-black-tea-new-measurement" not in pending_cartons
    assert "pending-original-kgos-candy-2" not in pending_cartons
    assert "pending-original-enzyme-4-trial" not in pending_cartons
    assert "pending-original-yuexi-sunscreen" not in pending_cartons
    assert "pending-original-yuexi-repair-gift-box" not in pending_cartons
    assert "pending-original-yuexi-rejuvenating-cream-3" not in pending_cartons
    rejected_black_tea = next(
        item
        for item in view["sections"]["pending"]
        if item.get("cartonId") == "pending-original-black-tea-new-measurement"
    )
    assert rejected_black_tea["status"] == "rejected_by_user_keep_existing_carton"
    original_ids = {
        item["cartonId"] for item in view["sections"]["originalCartons"]
    }
    assert {
        "original-candy-2-100",
        "original-enzyme-4-trial-72",
        "original-yuexi-sunscreen-60",
        "original-yuexi-repair-gift-box-20",
    } <= original_ids
    assert view["sections"]["packingUnits"]
    assert view["sections"]["fitChecks"]

    directory = {item["shortName"]: item for item in view["sections"]["productDirectory"]}
    assert "糖果" not in directory
    assert directory["KGO糖果2.0"]["fullName"] == "KGO复合多种压片糖果2.0"
    assert directory["KGO糖果2.0"]["mainMerchantCode"] == "6976299500108"
    assert directory["KGO糖果2.0"]["productKey"] == "kgos::KGO复合多种压片糖果2.0"
    assert directory["KGO糖果2.0"]["aliases"] == []
    assert "visualLabel" not in directory["KGO糖果2.0"]
    assert directory["KGOS三围尺"]["dimensionsMm"] == [90, 63, 23]
    assert directory["焕颜乳2.0"]["mainMerchantCode"] == "6940079096228-1"
    assert directory["KGOS玉米片-香菜牛肉味"]["missingDimensions"] is True
    assert directory["KGOS玉米片-玉米浓汤味"]["missingDimensions"] is True
    assert directory["KGOS黑茶 茉莉味 体验装"]["simulationCode"] == "6979499760099"
    assert directory["KGOS黑茶 普洱味 体验装"]["simulationCode"] == "6979265440019"
    assert directory["保湿喷雾2.0"]["mainMerchantCode"] == "6950328273270"
    assert directory["焕颜水"]["mainMerchantCode"] == "yx004"
    assert directory["焕颜水"]["specMerchantCodes"] == ["6940079096211"]
    assert directory["美式咖啡七条装"]["dimensionsMm"] == [90, 37, 154]
    assert directory["生椰拿铁咖啡七条装"]["dimensionsMm"] == [90, 37, 154]
    assert directory["美式咖啡七条装"]["missingDimensions"] is False
    assert directory["生椰拿铁咖啡七条装"]["missingDimensions"] is False
    assert directory["悦希修颜礼盒"]["dimensionsMm"] == [190, 228, 55]
    assert directory["悦希修颜礼盒"]["missingDimensions"] is False
    assert directory["黑茶茉莉花茶味卡片"]["packingBehavior"] == "ignored_zero_space"
    assert directory["黑茶茉莉花茶味卡片"]["missingDimensions"] is False
    assert not any(item["brandId"] == "ritekoko" for item in directory.values())
    assert not any(
        keyword in f"{item['shortName']} {item['fullName']}".upper()
        for item in directory.values()
        for keyword in ("RITEKOKO", "KOKO", "希凝", "钥黑")
    )
    assert not any(item["missingCode"] for item in directory.values())
    assert not any("印花礼盒一盒装" in item["shortName"] for item in directory.values())


def test_kgos_single_carton_returns_coordinates_and_separate_evidence(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="kgos",
        carton_id="carton-08",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 3}],
    )

    assert result["business"]["status"] == "experiment_allowed"
    assert result["geometry"]["status"] == "fits_inner_geometry"
    assert result["geometry"]["completenessVerified"] is True
    assert len(result["geometry"]["placements"]) == 3
    assert result["geometry"]["fullySupported"] is True
    assert result["geometry"]["minimumSupportCoverageRatio"] == 1.0
    assert all(
        item["supportCoverageRatio"] == 1.0
        for item in result["geometry"]["placements"]
    )
    assert result["evidence"]["level"] == "confirmed_capacity"
    assert "supportModelWarning" in result["geometry"]


def test_zero_space_accessory_does_not_add_geometry_units(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="kgos",
        carton_id="carton-08",
        lines=[
            {"merchantCode": COFFEE_CODE, "quantity": 3},
            {"merchantCode": "hcmlhckp", "quantity": 1},
        ],
        use_confirmed_rules=False,
    )

    assert result["business"]["status"] == "experiment_allowed"
    assert result["geometry"]["status"] == "fits_inner_geometry"
    assert len(result["geometry"]["placements"]) == 3
    assert result["request"]["ignoredZeroSpaceLines"] == [
        {
            "merchantCode": "hcmlhckp",
            "quantity": 1,
            "sourceProductId": "",
            "productName": "",
            "platformOrderNumber": "",
        }
    ]


def test_auto_carton_selection_prefers_confirmed_matching_carton(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id=None,
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 3}],
    )

    assert result["selection"]["mode"] == "auto"
    assert result["selection"]["selectedCartonId"] == "carton-08"
    assert result["selection"]["selectedCartonName"] == "咖啡三盒装"
    assert result["geometry"]["status"] == "fits_inner_geometry"


def test_manual_carton_selection_keeps_user_choice(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id="carton-04",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 3}],
    )

    assert result["selection"]["mode"] == "manual"
    assert result["selection"]["selectedCartonId"] == "carton-04"
    assert result["selection"]["selectedCartonName"] == "咖啡七盒装"


def test_auto_selection_uses_applicable_original_carton_when_regular_cartons_fail(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id=None,
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 54}],
    )

    assert result["selection"]["selectedCartonId"] == "original-coffee-60"
    assert result["selection"]["selectedCartonName"] == "咖啡原箱60盒"
    assert result["geometry"]["status"] == "fits_inner_geometry"


def test_auto_selection_uses_newly_measured_enzyme_original_carton(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id=None,
        lines=[{"merchantCode": "6979151090007", "quantity": 18}],
    )

    assert result["selection"]["selectedCartonId"] == "original-enzyme-4-20"
    assert result["selection"]["selectedCartonName"] == "酵素4.0原箱20盒"
    assert result["geometry"]["status"] == "fits_inner_geometry"
    assert result["geometry"]["completenessVerified"] is True
    assert len(result["geometry"]["placements"]) == 18


def test_manual_original_carton_is_available_for_single_matching_product_in_range(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id="original-coffee-60",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 54}],
    )

    assert result["selection"]["mode"] == "manual"
    assert result["selection"]["selectedCartonId"] == "original-coffee-60"
    assert result["selection"]["selectedCartonName"] == "咖啡原箱60盒"
    assert result["business"]["status"] == "experiment_allowed"
    assert result["geometry"]["status"] == "fits_inner_geometry"
    assert len(result["geometry"]["placements"]) == 54


def test_manual_original_carton_rejects_quantity_outside_confirmed_range(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id="original-coffee-60",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 3}],
    )

    assert result["business"]["status"] == "original_carton_not_applicable"
    assert result["geometry"]["status"] == "not_run"


def test_confirmed_single_package_exclusion_blocks_business_but_keeps_geometry_separate(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="kgos",
        carton_id="carton-12",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 36}],
    )

    assert result["business"]["status"] == "blocked_by_confirmed_rule"
    assert result["geometry"]["status"] != "not_run"
    assert result["evidence"]["level"] == "confirmed_rule"
    assert "不能覆盖该规则" in result["evidence"]["summary"]


def test_simulator_request_does_not_leak_confirmed_rule_answers(tmp_path):
    result = _service(tmp_path).assess_request(
        brand_id="kgos",
        carton_id="carton-12",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 36}],
    )

    assert result["business"]["status"] == "experiment_allowed"
    assert result["evidence"]["level"] != "confirmed_rule"
    assert "不读取固定箱量或历史包装答案" in result["business"]["reasons"][0]


def test_cross_brand_carton_is_rejected_before_geometry(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="kgos",
        carton_id="carton-13",
        lines=[{"merchantCode": COFFEE_CODE, "quantity": 1}],
    )

    assert result["business"]["status"] == "brand_mismatch"
    assert result["geometry"]["status"] == "not_run"


def test_yuexi_catalog_exists_but_packing_is_not_enabled(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="yuexi",
        carton_id="carton-13",
        lines=[{"merchantCode": YUEXI_SUNSCREEN, "quantity": 1}],
    )

    assert result["business"]["status"] == "capability_not_enabled"
    assert result["geometry"]["status"] == "not_run"
    assert result["evidence"]["level"] == "catalog_only"


def test_confirmed_coffee_seven_bag_dimensions_enter_active_geometry(tmp_path):
    result = _service(tmp_path).assess_single_carton(
        brand_id="kgos",
        carton_id="carton-08",
        lines=[{"merchantCode": COFFEE_7_AMERICAN_CODE, "quantity": 1}],
    )

    assert result["business"]["status"] == "experiment_allowed"
    assert result["geometry"]["status"] == "fits_inner_geometry"
    assert result["geometry"]["completenessVerified"] is True
    assert result["geometry"]["placements"][0]["dimensionsMm"] in (
        [90, 37, 154],
        [37, 90, 154],
    )


def test_coffee_seven_bag_full_original_carton_is_available_for_both_flavors(tmp_path):
    service = _service(tmp_path)

    for merchant_code in (COFFEE_7_AMERICAN_CODE, COFFEE_7_COCONUT_CODE):
        result = service.assess_request(
            brand_id="kgos",
            carton_id="original-coffee-7-80",
            lines=[{"merchantCode": merchant_code, "quantity": 80}],
        )

        assert result["business"]["status"] == "experiment_allowed"
        assert result["geometry"]["status"] == "fits_inner_geometry"
        assert result["geometry"]["completenessVerified"] is True
        assert len(result["geometry"]["placements"]) == 80


def test_newly_confirmed_kgos_original_cartons_are_usable(tmp_path):
    service = _service(tmp_path)
    cases = (
        ("original-candy-2-100", CANDY_2_CODE, 100),
        ("original-enzyme-4-trial-72", ENZYME_TRIAL_CODE, 72),
    )

    for carton_id, merchant_code, quantity in cases:
        result = service.assess_request(
            brand_id="kgos",
            carton_id=carton_id,
            lines=[{"merchantCode": merchant_code, "quantity": quantity}],
        )

        assert result["business"]["status"] == "experiment_allowed"
        assert result["geometry"]["status"] == "fits_inner_geometry"
        assert result["geometry"]["completenessVerified"] is True
        assert len(result["geometry"]["placements"]) == quantity


def test_historical_case_list_is_read_only_and_empty_when_store_missing(tmp_path):
    result = _service(tmp_path).list_historical_cases()

    assert result["readOnly"] is True
    assert result["cases"] == []
