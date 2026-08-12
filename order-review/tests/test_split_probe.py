from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    Package,
    PackageItem,
    PackagePlan,
    SourceSnapshot,
)
from order_review.split_probe import (
    SPLIT_RESULT_SETTLE_SECONDS,
    build_split_result_selection_probe_js,
    read_split_result_observation,
)
from order_review.split_result import validate_split_result


def _selection_payload(*, selected_sequences=(1, 2, 3)):
    return {
        "ok": True,
        "loadingCount": 0,
        "visibleDialogCount": 0,
        "rows": [
            {
                "sequence": sequence,
                "systemOrderId": f"SYSTEM-{sequence}",
                "checkboxCount": 1,
                "checkboxCheckedCount": (
                    1 if sequence in selected_sequences else 0
                ),
                "rowSelectedClass": sequence in selected_sequences,
                "expanded": True,
                "platformOrderNumbers": [f"T{sequence}"],
            }
            for sequence in range(1, 5)
        ],
    }


def _order_payload(sequence: int, *, expanded: bool = True):
    payload = {
        "ok": True,
        "isExpanded": expanded,
        "rowAttributes": {
            "uniqueid": f"SYSTEM-{sequence}",
            "sid": f"SYSTEM-{sequence}",
        },
        "visibleSystemOrderId": f"SYSTEM-{sequence}",
        "orderNumbers": [f"T{sequence}"],
        "products": [
            {
                "platformOrderNumber": f"T{sequence}",
                "dataset": {"tid": f"T{sequence}", "numiid": f"SPU-{sequence}"},
                "lines": [
                    f"商品{sequence}（简称{sequence}）",
                    f"平台ID（skuId）： SPU-{sequence} （SKU-{sequence}）",
                    f"主商家编码： CODE-{sequence}",
                    f"商家编码：CODE-{sequence}",
                    "1/1",
                ],
            }
        ],
    }
    if not expanded:
        payload["products"] = []
    return payload


def test_selection_probe_reads_only_live_rows_and_actual_checkbox_state():
    js = build_split_result_selection_probe_js()

    assert "rect.width > 0 && rect.height > 0" in js
    assert "input.checked" in js
    assert "module-trade-list-item-selected" in js
    assert "loadingCount" in js
    assert "visibleDialogCount" in js
    assert ".click(" not in js


def test_reader_expands_and_reads_exactly_the_selected_first_n_rows():
    calls = []
    expanded_sequences = {1}
    clicked_sequences = []
    mounted_sequences = {1, 2}
    wheels = []
    events = []

    def evaluator(_target_id, js):
        calls.append(js)
        if "checkboxCheckedCount" in js and "mountedSequences" not in js:
            return _selection_payload()
        for sequence in (1, 2, 3):
            if f"seq(row)==='{sequence}'" in js:
                if "mountedSequences" in js:
                    if sequence not in mounted_sequences:
                        return {
                            "ok": True,
                            "found": False,
                            "mountedSequences": sorted(mounted_sequences),
                            "wheelX": 500,
                            "wheelY": 400,
                        }
                    return {
                        "ok": True,
                        "found": True,
                        "inViewport": True,
                        "systemOrderId": f"SYSTEM-{sequence}",
                        "checkboxCount": 1,
                        "checkboxCheckedCount": 1,
                        "mountedSequences": sorted(mounted_sequences),
                        "wheelX": 500,
                        "wheelY": 400,
                    }
                if "trigger.click()" in js:
                    clicked_sequences.append(sequence)
                    expanded_sequences.add(sequence)
                    return {"ok": True, "expanded": True, "clicked": True}
                return _order_payload(
                    sequence,
                    expanded=sequence in expanded_sequences,
                )
        raise AssertionError("出现未预期的页面脚本")

    def wheel_dispatcher(*args):
        wheels.append(args)
        events.append(("wheel", args[-1]))
        if args[-1] > 0:
            mounted_sequences.clear()
            mounted_sequences.update({2, 3})
        else:
            mounted_sequences.clear()
            mounted_sequences.update({1, 2})

    def sleeper(seconds):
        events.append(("sleep", seconds))

    observation = read_split_result_observation(
        3,
        "target-1",
        evaluator=evaluator,
        wheel_dispatcher=wheel_dispatcher,
        sleeper=sleeper,
    )

    selected = [row for row in observation.rows if row.selected]
    assert [row.sequence for row in selected] == [1, 2, 3]
    assert [row.source.system_order_id for row in selected] == [
        "SYSTEM-1",
        "SYSTEM-2",
        "SYSTEM-3",
    ]
    assert all(row.source.products for row in selected)
    assert clicked_sequences == [2, 3]
    assert wheels == [
        ("target-1", 500.0, 400.0, 520.0),
        ("target-1", 500.0, 400.0, -520.0),
    ]
    assert mounted_sequences == {1, 2}
    assert events == [
        ("wheel", 520.0),
        ("sleep", 0.18),
        ("wheel", -520.0),
        ("sleep", 0.18),
        ("sleep", SPLIT_RESULT_SETTLE_SECONDS),
    ]
    assert sum(
        "checkboxCheckedCount" in js and "mountedSequences" not in js
        for js in calls
    ) == 2
    assert not any(
        "trigger.click()" in js and "seq(row)==='1'" in js
        for js in calls
    )


def test_reader_retains_verified_rows_unmounted_after_scrolling():
    selection_reads = 0

    def evaluator(_target_id, js):
        nonlocal selection_reads
        if "checkboxCheckedCount" in js and "mountedSequences" not in js:
            selection_reads += 1
            if selection_reads == 1:
                return _selection_payload()
            payload = _selection_payload(selected_sequences=(3,))
            payload["rows"] = payload["rows"][2:]
            return payload
        for sequence in (1, 2, 3):
            if f"seq(row)==='{sequence}'" not in js:
                continue
            if "mountedSequences" in js:
                return {
                    "ok": True,
                    "found": True,
                    "inViewport": True,
                    "systemOrderId": f"SYSTEM-{sequence}",
                    "checkboxCount": 1,
                    "checkboxCheckedCount": 1,
                    "mountedSequences": [sequence],
                    "wheelX": 500,
                    "wheelY": 400,
                }
            return _order_payload(sequence, expanded=True)
        raise AssertionError("出现未预期的页面脚本")

    observation = read_split_result_observation(
        3,
        "target-1",
        evaluator=evaluator,
        wheel_dispatcher=lambda *_args: None,
        sleeper=lambda _seconds: None,
    )

    selected = [row.sequence for row in observation.rows if row.selected]
    assert selected == [1, 2, 3]
    assert all(row.source is not None for row in observation.rows[:3])


def test_reader_discovers_selected_target_row_unmounted_in_initial_probe():
    mounted_sequences = {1, 2}
    wheels = []

    def selection_payload():
        payload = _selection_payload()
        payload["rows"] = [
            row
            for row in payload["rows"]
            if row["sequence"] in mounted_sequences
        ]
        return payload

    def evaluator(_target_id, js):
        if "checkboxCheckedCount" in js and "mountedSequences" not in js:
            return selection_payload()
        for sequence in (1, 2, 3):
            if f"seq(row)==='{sequence}'" not in js:
                continue
            if "mountedSequences" in js:
                if sequence not in mounted_sequences:
                    return {
                        "ok": True,
                        "found": False,
                        "mountedSequences": sorted(mounted_sequences),
                        "wheelX": 500,
                        "wheelY": 400,
                    }
                return {
                    "ok": True,
                    "found": True,
                    "inViewport": True,
                    "systemOrderId": f"SYSTEM-{sequence}",
                    "checkboxCount": 1,
                    "checkboxCheckedCount": 1,
                    "mountedSequences": sorted(mounted_sequences),
                    "wheelX": 500,
                    "wheelY": 400,
                }
            return _order_payload(sequence, expanded=True)
        raise AssertionError("出现未预期的页面脚本")

    def wheel_dispatcher(*args):
        wheels.append(args)
        if args[-1] > 0:
            mounted_sequences.clear()
            mounted_sequences.update({2, 3})
        else:
            mounted_sequences.clear()
            mounted_sequences.update({1, 2})

    observation = read_split_result_observation(
        3,
        "target-1",
        evaluator=evaluator,
        wheel_dispatcher=wheel_dispatcher,
        sleeper=lambda _seconds: None,
    )

    selected = [row for row in observation.rows if row.selected]
    assert [row.sequence for row in selected] == [1, 2, 3]
    assert all(row.source is not None for row in selected)
    assert [args[-1] for args in wheels] == [520.0, -520.0, 520.0, -520.0]


def test_reader_stops_when_discovered_target_row_is_not_selected():
    mounted_sequences = {1, 2}
    wheels = []
    detail_reads = []

    def selection_payload():
        payload = _selection_payload(selected_sequences=(1, 2))
        payload["rows"] = [
            row
            for row in payload["rows"]
            if row["sequence"] in mounted_sequences
        ]
        return payload

    def evaluator(_target_id, js):
        if "checkboxCheckedCount" in js and "mountedSequences" not in js:
            return selection_payload()
        for sequence in (1, 2, 3):
            if f"seq(row)==='{sequence}'" not in js:
                continue
            if "mountedSequences" in js:
                if sequence not in mounted_sequences:
                    return {
                        "ok": True,
                        "found": False,
                        "mountedSequences": sorted(mounted_sequences),
                        "wheelX": 500,
                        "wheelY": 400,
                    }
                return {
                    "ok": True,
                    "found": True,
                    "inViewport": True,
                    "systemOrderId": f"SYSTEM-{sequence}",
                    "checkboxCount": 1,
                    "checkboxCheckedCount": 0 if sequence == 3 else 1,
                    "mountedSequences": sorted(mounted_sequences),
                    "wheelX": 500,
                    "wheelY": 400,
                }
            detail_reads.append(sequence)
            return _order_payload(sequence, expanded=True)
        raise AssertionError("出现未预期的页面脚本")

    def wheel_dispatcher(*args):
        wheels.append(args)
        if args[-1] > 0:
            mounted_sequences.clear()
            mounted_sequences.update({2, 3})
        else:
            mounted_sequences.clear()
            mounted_sequences.update({1, 2})

    observation = read_split_result_observation(
        3,
        "target-1",
        evaluator=evaluator,
        wheel_dispatcher=wheel_dispatcher,
        sleeper=lambda _seconds: None,
    )

    assert [row.sequence for row in observation.rows if row.selected] == [1, 2]
    assert detail_reads == []
    assert [args[-1] for args in wheels] == [520.0, -520.0]


def test_reader_output_can_be_validated_without_product_type_mismatch():
    def evaluator(_target_id, js):
        if "checkboxCheckedCount" in js and "mountedSequences" not in js:
            return _selection_payload(selected_sequences=(1, 2))
        for sequence in (1, 2):
            if f"seq(row)==='{sequence}'" not in js:
                continue
            if "mountedSequences" in js:
                return {
                    "ok": True,
                    "found": True,
                    "inViewport": True,
                    "systemOrderId": f"SYSTEM-{sequence}",
                    "checkboxCount": 1,
                    "checkboxCheckedCount": 1,
                    "mountedSequences": [1, 2],
                    "wheelX": 500,
                    "wheelY": 400,
                }
            return _order_payload(sequence, expanded=True)
        raise AssertionError("出现未预期的页面脚本")

    observation = read_split_result_observation(
        2,
        "target-1",
        evaluator=evaluator,
        wheel_dispatcher=lambda *_args: None,
        sleeper=lambda _seconds: None,
    )
    products = [
        Product(
            title=f"商品{sequence}（简称{sequence}）",
            standard_name=f"商品{sequence}",
            short_name=f"简称{sequence}",
            quantity=1,
            merchant_code=f"CODE-{sequence}",
            spu_id=f"SPU-{sequence}",
            sku_id=f"SKU-{sequence}",
            platform_order_number=f"T{sequence}",
        )
        for sequence in (1, 2)
    ]
    expected_source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id="SYSTEM-ORIGINAL",
            products=products,
            order_numbers=("T1", "T2"),
        )
    )
    plan = PackagePlan(
        packages=tuple(
            Package(
                package_id=f"package-{index}",
                items=(
                    PackageItem(
                        source_product_id=product.source_product_id,
                        product_name=product.display_name,
                        quantity=product.quantity,
                    ),
                ),
            )
            for index, product in enumerate(expected_source.products, start=1)
        )
    )

    assert all(
        row.source is None or isinstance(row.source, SourceSnapshot)
        for row in observation.rows
    )
    assert validate_split_result(expected_source, plan, observation).verified


def test_reader_does_not_expand_when_selected_rows_are_not_first_n():
    calls = []

    def evaluator(_target_id, js):
        calls.append(js)
        if "checkboxCheckedCount" in js:
            return _selection_payload(selected_sequences=(2, 3, 4))
        raise AssertionError("不应读取错误位置的订单明细")

    observation = read_split_result_observation(
        3,
        "target-1",
        evaluator=evaluator,
    )

    selected = [row for row in observation.rows if row.selected]
    assert [row.sequence for row in selected] == [2, 3, 4]
    assert all(row.source is None for row in selected)
    assert len(calls) == 2
