from order_review.models import OrderSnapshot, Product
from order_review.package_plan import Package, PackageItem, PackagePlan, SourceSnapshot
from order_review.split_dry_run import (
    DRY_RUN_BLOCKED,
    LOCAL_INTENT_INSUFFICIENT,
    LOCAL_INTENT_NEEDS_SPLIT,
    build_split_dry_run,
)


def make_source(*, system_order_id: str = "ERP-100") -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id=system_order_id,
            order_numbers=("PLATFORM-1",),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=3,
                    merchant_code="A",
                ),
                Product(
                    title="商品B（简称B）",
                    standard_name="商品B",
                    short_name="简称B",
                    quantity=2,
                    merchant_code="B",
                ),
            ],
        ),
        captured_at="2026-07-29T05:00:00Z",
    )


def make_split_plan(source: SourceSnapshot) -> PackagePlan:
    product_a, product_b = source.products
    return PackagePlan(
        packages=(
            Package(
                "package-1",
                (
                    PackageItem(product_a.source_product_id, "简称A", 2),
                    PackageItem(product_b.source_product_id, "简称B", 1),
                ),
            ),
            Package(
                "package-2",
                (
                    PackageItem(product_a.source_product_id, "简称A", 1),
                    PackageItem(product_b.source_product_id, "简称B", 1),
                ),
            ),
        )
    )


def test_valid_multi_package_plan_produces_blocked_information_dry_run():
    source = make_source()

    report = build_split_dry_run(source, make_split_plan(source))

    assert report.local_intent == LOCAL_INTENT_NEEDS_SPLIT
    assert report.status == DRY_RUN_BLOCKED
    assert report.target_package_count == 2
    assert report.source_total_quantity == report.plan_total_quantity == 5
    assert report.package_lines == (
        "包裹 1：简称A ×2 + 简称B ×1",
        "包裹 2：简称A ×1 + 简称B ×1",
    )
    rendered = report.to_text()
    assert "ERP 执行：由界面的受保护拆分按钮单独触发" in rendered
    assert "首个结果样本已经验证" in rendered
    assert "仍需第二个独立订单真实验收" in rendered
    assert "本报告只验证本地方案，不会自行操作 ERP。" in rendered


def test_missing_system_order_id_keeps_local_intent_insufficient():
    source = make_source(system_order_id="")

    report = build_split_dry_run(source, make_split_plan(source))

    assert report.local_intent == LOCAL_INTENT_INSUFFICIENT
    assert report.package_lines == ()
    assert report.blocked_reasons == ("当前订单缺少可靠的 ERP 系统订单号",)


def test_quantity_mismatch_is_reported_instead_of_generating_plan():
    source = make_source()
    product_a, product_b = source.products
    invalid_plan = PackagePlan(
        packages=(
            Package(
                "package-1",
                (PackageItem(product_a.source_product_id, "简称A", 2),),
            ),
            Package(
                "package-2",
                (PackageItem(product_b.source_product_id, "简称B", 2),),
            ),
        )
    )

    report = build_split_dry_run(source, invalid_plan)

    assert report.local_intent == LOCAL_INTENT_INSUFFICIENT
    assert "本地目标方案与原订单商品数量不守恒" in report.blocked_reasons


def test_single_package_plan_is_not_misrepresented_as_split():
    source = make_source()
    product_a, product_b = source.products
    single_plan = PackagePlan(
        packages=(
            Package(
                "package-1",
                (
                    PackageItem(product_a.source_product_id, "简称A", 3),
                    PackageItem(product_b.source_product_id, "简称B", 2),
                ),
            ),
        )
    )

    report = build_split_dry_run(source, single_plan)

    assert report.local_intent == LOCAL_INTENT_INSUFFICIENT
    assert report.blocked_reasons == ("本地目标方案不是多包方案",)
