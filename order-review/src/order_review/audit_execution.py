from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable

from . import cdp
from .audit_probe import AuditExecutionState, AuditProbeError, ProbeCheck


@dataclass(frozen=True)
class SingleOrderSelectionProbe:
    selected_row_count: int
    selected_system_order_ids: tuple[str, ...]
    footer_selected_counts: tuple[int, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SingleOrderSelectionProbe:
        return cls(
            selected_row_count=_int_or_zero(payload.get("selectedRowCount")),
            selected_system_order_ids=tuple(
                str(value)
                for value in _list_or_empty(payload.get("selectedSystemOrderIds"))
                if value
            ),
            footer_selected_counts=tuple(
                _int_or_zero(value)
                for value in _list_or_empty(payload.get("footerSelectedCounts"))
            ),
        )


@dataclass(frozen=True)
class SingleOrderSelectionValidation:
    target_system_order_id: str
    target_package_count: int
    probe: SingleOrderSelectionProbe
    checks: tuple[ProbeCheck, ...]

    @property
    def ready_to_open_audit_menu(self) -> bool:
        return not any(check.status == "blocked" for check in self.checks)

    @property
    def blockers(self) -> tuple[ProbeCheck, ...]:
        return tuple(check for check in self.checks if check.status == "blocked")

    def render_text(self) -> str:
        if self.ready_to_open_audit_menu:
            return (
                "勾选核对通过：页面真实复选框只选中了当前目标订单。"
                "底部数量仅用于发现 2 条或更多的危险状态。"
            )
        details = "；".join(check.detail for check in self.blockers)
        return f"已停止：勾选状态不安全。{details}。未打开审核菜单。"


def validate_single_order_selection(
    probe: SingleOrderSelectionProbe,
    *,
    target_system_order_id: str,
    target_package_count: int = 1,
) -> SingleOrderSelectionValidation:
    target_selected = (
        probe.selected_row_count == 1
        and probe.selected_system_order_ids == (target_system_order_id,)
    )
    checks = (
        _check(
            "SINGLE_PACKAGE_ORDER_SCOPE",
            "适用范围",
            target_package_count == 1,
            (
                "当前是单包单订单审核"
                if target_package_count == 1
                else f"当前方案有 {target_package_count} 个包裹，不能套用单订单审核规则"
            ),
        ),
        _check(
            "TARGET_SELECTION",
            "页面真实勾选",
            target_selected,
            (
                f"仅选中目标订单 {target_system_order_id}"
                if target_selected
                else (
                    f"真实选中行 {probe.selected_row_count}，"
                    f"系统订单号 {list(probe.selected_system_order_ids)}"
                )
            ),
        ),
        _check(
            "FOOTER_MULTIPLE_ORDER_GUARD",
            "底部多选反向保护",
            _single_order_footer_safe(probe.footer_selected_counts),
            _footer_guard_detail(probe.footer_selected_counts),
        ),
    )
    return SingleOrderSelectionValidation(
        target_system_order_id=target_system_order_id,
        target_package_count=target_package_count,
        probe=probe,
        checks=checks,
    )


@dataclass(frozen=True)
class AuditResultProbe:
    required_fields_present: bool
    target_present_in_dom: bool
    target_visible_count: int
    visible_dialog_count: int
    selected_row_count: int
    selected_system_order_ids: tuple[str, ...]
    footer_selected_counts: tuple[int, ...]
    loading_count: int
    current_sequence_one_system_order_id: str
    messages: tuple[str, ...]
    target_disappeared_at: str
    dialog_closed_at: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AuditResultProbe:
        observation = (
            payload.get("observation")
            if isinstance(payload.get("observation"), dict)
            else {}
        )
        messages = _list_or_empty(payload.get("messages"))
        if not messages:
            messages = _list_or_empty(payload.get("visibleMessages"))
        required_fields = {
            "targetPresentInDom",
            "targetVisibleCount",
            "visibleDialogCount",
            "selectedRowCount",
            "selectedSystemOrderIds",
            "footerSelectedCounts",
            "loadingCount",
            "currentSequenceOneSystemOrderId",
        }
        return cls(
            required_fields_present=required_fields.issubset(payload),
            target_present_in_dom=bool(payload.get("targetPresentInDom")),
            target_visible_count=_int_or_zero(payload.get("targetVisibleCount")),
            visible_dialog_count=_int_or_zero(payload.get("visibleDialogCount")),
            selected_row_count=_int_or_zero(payload.get("selectedRowCount")),
            selected_system_order_ids=tuple(
                str(value)
                for value in _list_or_empty(payload.get("selectedSystemOrderIds"))
                if value
            ),
            footer_selected_counts=tuple(
                _int_or_zero(value)
                for value in _list_or_empty(payload.get("footerSelectedCounts"))
            ),
            loading_count=_int_or_zero(payload.get("loadingCount")),
            current_sequence_one_system_order_id=str(
                payload.get("currentSequenceOneSystemOrderId") or ""
            ),
            messages=tuple(_message_text(value) for value in messages if value),
            target_disappeared_at=str(
                payload.get("targetDisappearedAt")
                or observation.get("targetDisappearedAt")
                or ""
            ),
            dialog_closed_at=str(
                payload.get("dialogClosedAt")
                or observation.get("dialogClosedAt")
                or ""
            ),
        )


@dataclass(frozen=True)
class AuditResultValidation:
    target_system_order_id: str
    target_package_count: int
    probe: AuditResultProbe
    state: AuditExecutionState
    checks: tuple[ProbeCheck, ...]

    @property
    def successful(self) -> bool:
        return self.state == AuditExecutionState.SUCCESS

    @property
    def blockers(self) -> tuple[ProbeCheck, ...]:
        return tuple(check for check in self.checks if check.status == "blocked")

    def render_text(self) -> str:
        if self.successful:
            next_order = (
                f"下一条序号 1 订单为 {self.probe.current_sequence_one_system_order_id}，"
                if self.probe.current_sequence_one_system_order_id
                else "当前列表没有新的序号 1 订单，"
            )
            return (
                f"审核成功：目标订单 {self.target_system_order_id} 已从待审核列表消失，"
                f"{next_order}且没有订单被继续勾选。"
                "底部汇总可能残留上一单数据，不参与成功判定。"
            )
        if self.state == AuditExecutionState.STOPPED:
            details = "；".join(check.detail for check in self.blockers)
            return (
                f"审核已停止：{details or '页面出现明确失败信息'}。"
                "不会重试，也不会处理下一单。"
            )
        details = "；".join(check.detail for check in self.blockers)
        return (
            f"审核结果不确定：{details or '页面没有给出足够证据'}。"
            "不会重试，也不会处理下一单。"
        )


def validate_audit_result(
    probe: AuditResultProbe,
    *,
    target_system_order_id: str,
    target_package_count: int = 1,
) -> AuditResultValidation:
    failure_message = next(
        (
            message
            for message in probe.messages
            if any(word in message for word in ("失败", "错误", "异常", "未成功"))
        ),
        "",
    )
    target_removed = (
        probe.required_fields_present
        and not probe.target_present_in_dom
        and probe.target_visible_count == 0
    )
    checks = (
        _check(
            "RESULT_PROBE_COMPLETE",
            "结果读取完整性",
            probe.required_fields_present,
            (
                "结果判定所需字段完整"
                if probe.required_fields_present
                else "结果字段不完整，不能推断审核成功"
            ),
        ),
        _check(
            "SINGLE_PACKAGE_ORDER_SCOPE",
            "适用范围",
            target_package_count == 1,
            (
                "当前是单包单订单审核"
                if target_package_count == 1
                else f"当前方案有 {target_package_count} 个包裹，不能套用单订单审核结果"
            ),
        ),
        _check(
            "TARGET_REMOVED_FROM_TOAUDIT",
            "目标订单离开待审核列表",
            target_removed,
            (
                "原系统订单号已从页面 DOM 消失"
                if target_removed
                else "原系统订单号仍在待审核页面中"
            ),
        ),
        _check(
            "DIALOG_CLOSED",
            "审核弹窗",
            probe.visible_dialog_count == 0,
            (
                "弹窗已关闭"
                if probe.visible_dialog_count == 0
                else f"仍有 {probe.visible_dialog_count} 个可见弹窗"
            ),
        ),
        _check(
            "SELECTION_CLEARED",
            "页面真实勾选",
            probe.selected_row_count == 0 and not probe.selected_system_order_ids,
            (
                "当前没有任何订单被勾选"
                if probe.selected_row_count == 0 and not probe.selected_system_order_ids
                else (
                    f"仍选中 {probe.selected_row_count} 行，"
                    f"系统订单号 {list(probe.selected_system_order_ids)}"
                )
            ),
        ),
        _check(
            "PAGE_NOT_LOADING",
            "页面加载状态",
            probe.loading_count == 0,
            (
                "页面加载完成"
                if probe.loading_count == 0
                else f"仍有 {probe.loading_count} 个加载状态"
            ),
        ),
        ProbeCheck(
            code="FOOTER_POST_SUBMIT_INFORMATION",
            label="底部汇总",
            status="info",
            detail=(
                f"底部计数 {list(probe.footer_selected_counts)}；"
                "审核后可能残留，不能用于成功或失败判定"
            ),
        ),
    )
    main_checks_pass = all(
        check.status != "blocked"
        for check in checks
        if check.code != "FOOTER_POST_SUBMIT_INFORMATION"
    )
    if failure_message:
        state = AuditExecutionState.STOPPED
        checks = checks + (
            ProbeCheck(
                code="FAILURE_MESSAGE",
                label="页面失败提示",
                status="blocked",
                detail=failure_message,
            ),
        )
    elif main_checks_pass:
        state = AuditExecutionState.SUCCESS
    else:
        state = AuditExecutionState.UNKNOWN
    return AuditResultValidation(
        target_system_order_id=target_system_order_id,
        target_package_count=target_package_count,
        probe=probe,
        state=state,
        checks=checks,
    )


def build_audit_result_probe_js(target_system_order_id: str) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    return rf"""(function(){{
  var targetSystemOrderId = {target_json};
  if (location.hash.indexOf('#/trade/toaudit/') !== 0) {{
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE',url:location.href}});
  }}
  if (document.title.indexOf('快麦ERP--待审核订单') < 0) {{
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_TITLE',title:document.title}});
  }}
  function clean(value){{ return String(value || '').replace(/\s+/g, ' ').trim(); }}
  function visible(el){{
    if (!el || !el.getBoundingClientRect) return false;
    var rect = el.getBoundingClientRect();
    var style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }}
  function systemOrderId(row){{
    var values = Array.from(new Set([
      clean(row.getAttribute('uniqueid') || row.dataset.uniqueid),
      clean(row.getAttribute('sid') || row.dataset.sid)
    ].filter(Boolean)));
    return values.length === 1 ? values[0] : '';
  }}
  function checked(row){{
    return Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"],input[type="checkbox"]'
    )).some(function(input){{ return input.checked; }});
  }}
  function sequence(row){{
    return String(row.innerText || row.textContent || '').split(/\n+/)
      .map(clean).find(function(value){{ return /^\d+$/.test(value); }}) || '';
  }}

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'));
  var visibleRows = rows.filter(visible);
  var targetRows = rows.filter(function(row){{
    return systemOrderId(row) === targetSystemOrderId;
  }});
  var selectedRows = visibleRows.filter(checked);
  var footerCounts = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
    var text = clean(el.innerText || el.textContent);
    if (text.length > 120) return;
    var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
    if (match) footerCounts.push(Number(match[1]));
  }});
  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"],.el-message-box__wrapper'
  )))).filter(visible);
  var messageSelectors = '.el-message,.ivu-message-notice,.ant-message-notice,' +
    '.toast,.toast-message,[role="status"],[role="alert"]';
  var messages = Array.from(document.querySelectorAll(messageSelectors))
    .filter(visible).map(function(el){{ return clean(el.innerText || el.textContent); }})
    .filter(Boolean);
  var loadingSelectors = '.el-loading-mask,.ivu-spin-fix,.ant-spin-spinning,' +
    '.loading-mask,.trade-loading';
  var first = visibleRows.find(function(row){{ return sequence(row) === '1'; }});
  var observation = window.__orderReviewAuditObservation || {{}};

  return JSON.stringify({{
    ok:true,
    targetPresentInDom:targetRows.length > 0,
    targetVisibleCount:targetRows.filter(visible).length,
    visibleDialogCount:dialogs.length,
    selectedRowCount:selectedRows.length,
    selectedSystemOrderIds:selectedRows.map(systemOrderId),
    footerSelectedCounts:Array.from(new Set(footerCounts)),
    loadingCount:Array.from(document.querySelectorAll(loadingSelectors)).filter(visible).length,
    currentSequenceOneSystemOrderId:first ? systemOrderId(first) : '',
    messages:messages,
    observation:{{
      targetDisappearedAt:clean(observation.targetDisappearedAt),
      dialogClosedAt:clean(observation.dialogClosedAt)
    }}
  }});
}})()"""


def probe_and_validate_audit_result(
    target_id: str,
    *,
    target_system_order_id: str,
    target_package_count: int = 1,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
) -> AuditResultValidation:
    payload = evaluator(
        target_id,
        build_audit_result_probe_js(target_system_order_id),
    )
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise AuditProbeError(
            "INVALID_AUDIT_RESULT_PAYLOAD",
            "审核后的页面返回了无法识别的只读核对结果",
        )
    return validate_audit_result(
        AuditResultProbe.from_payload(payload),
        target_system_order_id=target_system_order_id,
        target_package_count=target_package_count,
    )


def _check(code: str, label: str, passed: bool, detail: str) -> ProbeCheck:
    return ProbeCheck(
        code=code,
        label=label,
        status="pass" if passed else "blocked",
        detail=detail,
    )


def _single_order_footer_safe(values: tuple[int, ...]) -> bool:
    return all(0 <= value <= 1 for value in values)


def _footer_guard_detail(values: tuple[int, ...]) -> str:
    if not values:
        return "底部未显示数量；不作为正向证明"
    if _single_order_footer_safe(values):
        return f"底部计数 {list(values)}；只用于发现 2 或更大的危险值"
    return f"底部计数 {list(values)}；单包单订单出现 2 或更大时必须停止"


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _message_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "")
    return str(value)
