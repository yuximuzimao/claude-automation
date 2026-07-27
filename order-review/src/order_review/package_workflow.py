from __future__ import annotations

import logging
from typing import Callable

from .case_repository import (
    CaseRepositoryError,
    ConfirmedCase,
    Decision,
    DecisionSource,
    JsonCaseRepository,
    ShippingMode,
)
from .models import OrderSnapshot
from .order_identity import same_order_signature_key
from .package_plan import (
    PackageDraft,
    PackagePlan,
    PackagePlanValidationError,
    SourceSnapshot,
)
from .recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    MATCH_SINGLE_PACKAGE_TOTAL,
    FreightReminder,
    RecommendationCandidate,
    RecommendationResult,
    apply_case_plan,
    apply_recommendation,
    find_freight_reminder,
    find_recommendations,
)
from .recommendation_events import RecommendationEventStore


LOGGER = logging.getLogger(__name__)


class PackagePlanWorkflow:
    """管理当前订单、历史方案恢复、规则采用、编辑与确认持久化。"""

    def __init__(
        self,
        repository: JsonCaseRepository | None = None,
        event_store: RecommendationEventStore | None = None,
    ) -> None:
        self.repository = repository or JsonCaseRepository()
        self.event_warning = ""
        if event_store is not None:
            self.event_store: RecommendationEventStore | None = event_store
        else:
            try:
                self.event_store = RecommendationEventStore(
                    case_path=self.repository.path
                )
            except Exception as exc:
                self.event_store = None
                self._record_event_warning("初始化推荐事件", exc)
        self.source_snapshot: SourceSnapshot | None = None
        self.draft: PackageDraft | None = None
        self._initial_draft: PackageDraft | None = None

        self.historical_case: ConfirmedCase | None = None
        self.historical_plan: PackagePlan | None = None
        self.historical_rule_id: str | None = None
        self.editing_historical_case: ConfirmedCase | None = None

        self.confirmed_case: ConfirmedCase | None = None
        self.confirmed_plan: PackagePlan | None = None
        self.confirmation_note = ""
        self.freight_pending = False
        self.freight_reminder: FreightReminder | None = None

        self.recommendations = RecommendationResult(candidates=(), conflict=False)
        self.recommendation_error = ""
        self.selected_recommendation: RecommendationCandidate | None = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.load_notice = ""
        self._pending_recommendations: dict[
            str, tuple[SourceSnapshot, RecommendationCandidate]
        ] = {}

    def load_order(self, order_snapshot: OrderSnapshot) -> None:
        # 每次读取都创建新会话并丢弃未确认草稿；事实层刷新不能静默延续旧编辑状态。
        source_snapshot = SourceSnapshot.from_order_snapshot(order_snapshot)
        if (
            self.source_snapshot is not None
            and self._event_order_key(self.source_snapshot)
            != self._event_order_key(source_snapshot)
        ):
            self._abandon_pending_recommendations()
        self.source_snapshot = source_snapshot
        self._reset_transient_state()
        try:
            history = self.repository.find_same_order(self.source_snapshot)
            if history is not None:
                self.historical_case = history.case
                self.historical_rule_id = history.assignment.rule_id if history.assignment else None
                if history.case.is_freight:
                    self.load_notice = "该订单已经保存为物流发货。"
                    return
                self.historical_plan = apply_case_plan(
                    self.source_snapshot, history.case
                ).confirm(self.source_snapshot)
                self.load_notice = (
                    f"该订单已经保存过包裹方案，当前显示第 {history.case.order_version} 个版本。"
                )
                return

            cases = self.repository.list_cases()
            self.freight_reminder = find_freight_reminder(
                self.source_snapshot, cases
            )
            if source_snapshot.total_quantity == 1 and not order_snapshot.has_suite_action:
                self.start_single_package()
                self.load_notice = "总数量为 1 且非套件，已默认生成单包草稿，请确认。"
                return
            stats = self.repository.get_rule_stats()
            self.recommendations = find_recommendations(
                self.source_snapshot, cases, stats
            )
            for candidate in self.recommendations.candidates:
                event_ok, event_key = self._try_event(
                    "记录推荐展示",
                    lambda candidate=candidate: self.event_store.record_shown(
                        self.source_snapshot,
                        candidate,
                    ),
                )
                if not event_ok or event_key is not None:
                    self._pending_recommendations[candidate.recommendation_id] = (
                        self.source_snapshot,
                        candidate,
                    )
            if len(self.recommendations.candidates) == 1 and not self.recommendations.conflict:
                candidate = self.recommendations.candidates[0]
                if candidate.match_type != MATCH_SINGLE_PACKAGE_CAPACITY:
                    self.adopt_recommendation(candidate.recommendation_id, automatic=True)
                    match_label = (
                        "完全匹配的历史方案"
                        if candidate.match_type == MATCH_EXACT_STRUCTURE
                        else "历史单包方案"
                    )
                    self.load_notice = f"已自动采用{match_label}，可直接确认或继续修改。"
        except CaseRepositoryError as exc:
            self._abandon_pending_recommendations()
            self.recommendations = RecommendationResult(candidates=(), conflict=False)
            self.recommendation_error = str(exc)

    def clear_order(self) -> None:
        self._abandon_pending_recommendations()
        self.source_snapshot = None
        self._reset_transient_state()

    def _reset_transient_state(self) -> None:
        self.draft = None
        self._initial_draft = None
        self.historical_case = None
        self.historical_plan = None
        self.historical_rule_id = None
        self.editing_historical_case = None
        self.confirmed_case = None
        self.confirmed_plan = None
        self.confirmation_note = ""
        self.freight_pending = False
        self.freight_reminder = None
        self.recommendations = RecommendationResult(candidates=(), conflict=False)
        self.recommendation_error = ""
        self.selected_recommendation = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.load_notice = ""

    def start_single_package(self) -> None:
        source = self._require_source()
        self._abandon_pending_recommendations()
        self._clear_recommendation_selection()
        self.freight_pending = False
        self.draft = PackageDraft.single_package(source)
        self._initial_draft = self.draft

    def start_split(self) -> None:
        source = self._require_source()
        self._abandon_pending_recommendations()
        self._clear_recommendation_selection()
        self.freight_pending = False
        self.draft = PackageDraft.split(source, package_count=1)
        self._initial_draft = self.draft

    def start_freight(self) -> None:
        self._require_source()
        self._abandon_pending_recommendations()
        self._clear_recommendation_selection()
        self.draft = None
        self._initial_draft = None
        self.freight_pending = True

    def edit_historical_plan(self) -> None:
        source = self._require_source()
        if self.historical_case is None:
            raise PackagePlanValidationError("当前订单没有可修改的历史方案")
        self.draft = apply_case_plan(source, self.historical_case)
        self._initial_draft = self.draft
        self.editing_historical_case = self.historical_case
        self.selected_recommendation = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.freight_pending = False

    def adopt_recommendation(
        self, recommendation_id: str, *, automatic: bool = False
    ) -> None:
        source = self._require_source()
        candidate = next(
            (
                item
                for item in self.recommendations.candidates
                if item.recommendation_id == recommendation_id
            ),
            None,
        )
        if candidate is None:
            raise PackagePlanValidationError("历史推荐不存在或已经失效")
        self.draft = apply_recommendation(source, candidate)
        self._initial_draft = self.draft
        self.selected_recommendation = candidate
        self.recommendation_modified = False
        self.auto_adopted_recommendation = automatic
        self.editing_historical_case = None
        self.freight_pending = False

    def set_quantity(self, package_id: str, source_product_id: str, quantity: int) -> None:
        source, draft = self._require_draft()
        current_quantity = next(
            (
                item.quantity
                for package in draft.packages
                if package.package_id == package_id
                for item in package.items
                if item.source_product_id == source_product_id
            ),
            0,
        )
        if quantity == current_quantity:
            return
        self.draft = draft.set_quantity(
            package_id, source_product_id, quantity, source=source
        )
        self._mark_modified()

    def add_package(self) -> None:
        _, draft = self._require_draft()
        if self.remaining_quantity <= 0:
            raise PackagePlanValidationError(
                "所有商品已分配；请先从现有包裹退回商品，再新增包裹"
            )
        if any(not package.items for package in draft.packages):
            raise PackagePlanValidationError(
                "请先给当前空包裹分配商品，再新增下一个包裹"
            )
        self.draft = draft.add_package()
        self._mark_modified()

    def remove_package(self, package_id: str) -> None:
        _, draft = self._require_draft()
        self.draft = draft.remove_package(package_id)
        self._mark_modified()

    def reset(self) -> None:
        self._require_draft()
        if self._initial_draft is None:
            raise PackagePlanValidationError("当前方案没有可恢复的初始状态")
        self.draft = self._initial_draft
        self.recommendation_modified = False

    def cancel(self) -> None:
        self._abandon_pending_recommendations()
        self.draft = None
        self._initial_draft = None
        self.editing_historical_case = None
        self.selected_recommendation = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.freight_pending = False

    @property
    def remaining_quantity(self) -> int:
        if self.source_snapshot is None or self.draft is None:
            return 0
        return sum(
            self.draft.remaining_quantity(product)
            for product in self.source_snapshot.products
        )

    @property
    def can_add_package(self) -> bool:
        return self.draft is not None and self.remaining_quantity > 0

    def confirm(self, *, allow_same_snapshot: bool = False) -> ConfirmedCase:
        source, draft = self._require_draft()
        package_plan = draft.confirm(source)

        if self.editing_historical_case is not None:
            previous = self.editing_historical_case
            saved = self.repository.confirm(
                source,
                package_plan,
                Decision(
                    source=DecisionSource.ORDER_VERSION,
                    recommendation_id=self.historical_rule_id,
                    recommendation_modified=True,
                    recommendation_case_ids=(previous.case_id,),
                ),
                previous_case_id=previous.case_id,
                rule_id=self.historical_rule_id,
            )
            self.historical_case = saved
            self.historical_plan = None
            self.load_notice = ""
            self.confirmed_case = saved
            self.confirmed_plan = package_plan
            self.confirmation_note = f"已保存为该订单的第 {saved.order_version} 个方案版本。"
            self._finish_confirmation()
            return saved

        candidate = self.selected_recommendation
        if (
            candidate is not None
            and not self.recommendation_modified
            and candidate.match_type != MATCH_SINGLE_PACKAGE_CAPACITY
        ):
            decision = self._build_decision()
            adopted = self.repository.record_rule_adoption(
                source,
                package_plan,
                decision,
                source_case_id=candidate.source_case_ids[0],
                rule_id=candidate.rule_id,
            )
            self.confirmed_case = adopted.case
            self.confirmed_plan = adopted.package_plan
            self.confirmation_note = "已确认采用历史规则；未重复保存完整案例。"
            self._record_recommendation_confirmation(candidate, modified=False)
            self._finish_confirmation()
            return adopted.case

        decision = self._build_decision()
        saved = self.repository.confirm(
            source,
            package_plan,
            decision,
            allow_same_snapshot=allow_same_snapshot,
            rule_id=candidate.rule_id if candidate is not None else None,
        )
        self.confirmed_case = saved
        self.confirmed_plan = package_plan
        if (
            candidate is not None
            and candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY
            and not self.recommendation_modified
        ):
            self.confirmation_note = "已保存新的单包容量案例，并记录规则采用。"
        elif candidate is not None:
            self.confirmation_note = "已保存修改后的方案分支。"
        else:
            self.confirmation_note = "已保存新的本地案例。"
        if candidate is not None:
            self._record_recommendation_confirmation(
                candidate,
                modified=self.recommendation_modified,
            )
        self._finish_confirmation()
        return saved

    def confirm_freight(
        self,
        *,
        estimated_package_band: str | None = None,
        shipping_reasons: tuple[str, ...] | None = None,
    ) -> ConfirmedCase:
        source = self._require_source()
        if not self.freight_pending:
            raise PackagePlanValidationError("请先选择物流发货")
        plan = PackageDraft.single_package(source).confirm(source)
        reasons = shipping_reasons or self._default_freight_reasons(source)
        saved = self.repository.confirm(
            source,
            plan,
            Decision(
                source=DecisionSource.MANUAL,
                shipping_mode=ShippingMode.FREIGHT,
                estimated_package_band=estimated_package_band,
                shipping_reasons=reasons,
            ),
        )
        self.confirmed_case = saved
        self.confirmed_plan = None
        self.confirmation_note = "已保存为物流发货，不参与普通单包推荐。"
        self._finish_confirmation()
        return saved

    def close(self) -> None:
        self._abandon_pending_recommendations()

    def _finish_confirmation(self) -> None:
        self.draft = None
        self._initial_draft = None
        self.editing_historical_case = None
        self.selected_recommendation = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.freight_pending = False

    def _build_decision(self) -> Decision:
        candidate = self.selected_recommendation
        if candidate is not None:
            source = (
                DecisionSource.RECOMMENDED_MODIFIED
                if self.recommendation_modified
                else DecisionSource.RECOMMENDED_ACCEPTED
            )
            return Decision(
                source=source,
                recommendation_id=candidate.recommendation_id,
                recommendation_modified=self.recommendation_modified,
                recommendation_case_ids=candidate.source_case_ids,
                recommendation_algorithm_version=candidate.algorithm_version,
                recommendation_match_type=candidate.match_type,
            )
        return Decision(source=DecisionSource.MANUAL)

    @staticmethod
    def _default_freight_reasons(source: SourceSnapshot) -> tuple[str, ...]:
        reasons = ["manual_judgment"]
        if source.total_quantity >= 70:
            reasons.append("high_quantity")
        if len({product.match_key for product in source.products}) >= 3:
            reasons.append("complex_mix")
        return tuple(reasons)

    def _clear_recommendation_selection(self) -> None:
        self.selected_recommendation = None
        self.recommendation_modified = False
        self.auto_adopted_recommendation = False
        self.editing_historical_case = None

    def _mark_modified(self) -> None:
        if self.selected_recommendation is not None or self.editing_historical_case is not None:
            self.recommendation_modified = True

    def _record_recommendation_confirmation(
        self,
        candidate: RecommendationCandidate,
        *,
        modified: bool,
    ) -> None:
        source = self._require_source()
        self._try_event(
            "记录推荐确认",
            lambda: self.event_store.record_confirmed(
                source,
                candidate,
                modified=modified,
            ),
        )
        self._pending_recommendations.pop(candidate.recommendation_id, None)
        self._abandon_pending_recommendations()

    def _abandon_pending_recommendations(self) -> None:
        pending = tuple(self._pending_recommendations.values())
        self._pending_recommendations.clear()
        for source, candidate in pending:
            self._try_event(
                "记录推荐未知离开",
                lambda source=source, candidate=candidate: (
                    self.event_store.record_abandoned_unknown(source, candidate)
                ),
            )

    def _try_event(
        self,
        action: str,
        callback: Callable[[], object],
    ) -> tuple[bool, object | None]:
        if self.event_store is None:
            return False, None
        try:
            return True, callback()
        except Exception as exc:
            self._record_event_warning(action, exc)
            return False, None

    def _record_event_warning(self, action: str, exc: Exception) -> None:
        self.event_warning = f"{action}失败：{exc}"
        LOGGER.warning("%s；核心案例流程继续", self.event_warning, exc_info=True)

    @staticmethod
    def _event_order_key(source: SourceSnapshot) -> str:
        return same_order_signature_key(source) or f"snapshot:{source.snapshot_id}"

    def _require_source(self) -> SourceSnapshot:
        if self.source_snapshot is None or not self.source_snapshot.products:
            raise PackagePlanValidationError("当前没有可分配的原订单商品")
        return self.source_snapshot

    def _require_draft(self) -> tuple[SourceSnapshot, PackageDraft]:
        source = self._require_source()
        if self.draft is None:
            raise PackagePlanValidationError("请先选择单包方案或拆分包裹")
        return source, self.draft
