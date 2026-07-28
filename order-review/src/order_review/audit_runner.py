from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable
from uuid import uuid4

from . import cdp
from .audit_dialog import AuditDialogValidation, probe_and_validate_audit_dialog
from .audit_execution import (
    AuditResultValidation,
    SingleOrderSelectionProbe,
    probe_and_validate_audit_result,
    validate_single_order_selection,
)
from .audit_probe import (
    AUDIT_PROBE_SCHEMA_VERSION,
    AuditExecutionLogStore,
    AuditExecutionState,
    AuditPreflightReport,
    AuditProbeError,
    run_audit_preflight,
)
from .erp_reader import find_erp_toaudit_target
from .file_lock import FileLock
from .package_plan import SourceSnapshot


AUDIT_DIALOG_WAIT_SECONDS = 5.0
AUDIT_RESULT_WAIT_SECONDS = 15.0
AUDIT_POLL_INTERVAL_SECONDS = 0.2


@dataclass(frozen=True)
class AuditStep:
    state: AuditExecutionState
    observed_at: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "state": self.state.value,
            "observedAt": self.observed_at,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SingleOrderAuditReport:
    execution_id: str
    started_at: str
    finished_at: str
    target_system_order_id: str
    source_snapshot_id: str
    confirmation_reference_id: str
    state: AuditExecutionState
    steps: tuple[AuditStep, ...]

    @property
    def successful(self) -> bool:
        return self.state == AuditExecutionState.SUCCESS

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": AUDIT_PROBE_SCHEMA_VERSION,
            "mode": "single_order_audit",
            "executionId": self.execution_id,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "targetSystemOrderId": self.target_system_order_id,
            "sourceSnapshotId": self.source_snapshot_id,
            "confirmationReferenceId": self.confirmation_reference_id,
            "targetPackageCount": 1,
            "state": self.state.value,
            "steps": [step.to_dict() for step in self.steps],
        }

    def render_text(self) -> str:
        if self.state == AuditExecutionState.SUCCESS:
            return (
                f"审核成功：订单 {self.target_system_order_id} 已离开待审核列表。"
                "没有继续处理下一单，请点击顶部“刷新”读取新订单。"
            )
        final_detail = self.steps[-1].detail if self.steps else "没有可用执行结果"
        if self.state == AuditExecutionState.UNKNOWN:
            return (
                f"审核结果不确定：{final_detail}。"
                "没有重试，也没有继续处理下一单，请人工核对 ERP。"
            )
        return f"审核已停止：{final_detail}。没有继续执行后续动作。"


class _AuditStopped(RuntimeError):
    pass


class _AuditSubmittedUncertain(RuntimeError):
    pass


def run_single_order_audit(
    *,
    target_system_order_id: str,
    expected_source: SourceSnapshot,
    confirmation_reference_id: str = "",
    target_package_count: int = 1,
    target_id: str | None = None,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
    mouse_clicker: Callable[[str, float, float], None] | None = None,
    target_finder: Callable[[], str | None] = find_erp_toaudit_target,
    preflight_runner: Callable[..., AuditPreflightReport] = run_audit_preflight,
    dialog_reader: Callable[..., AuditDialogValidation] = probe_and_validate_audit_dialog,
    result_reader: Callable[..., AuditResultValidation] = probe_and_validate_audit_result,
    progress_callback: Callable[[AuditExecutionState, str], None] | None = None,
    log_store: AuditExecutionLogStore | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    dialog_wait_seconds: float = AUDIT_DIALOG_WAIT_SECONDS,
    result_wait_seconds: float = AUDIT_RESULT_WAIT_SECONDS,
) -> SingleOrderAuditReport:
    execution_id = f"audit-{uuid4()}"
    started_at = _utc_now()
    steps: list[AuditStep] = []
    final_state = AuditExecutionState.STOPPED
    submitted = False
    mouse_clicker = mouse_clicker or click_mouse_at

    def record(
        state: AuditExecutionState,
        detail: str,
        *,
        status: str = "pass",
    ) -> None:
        steps.append(
            AuditStep(
                state=state,
                observed_at=_utc_now(),
                status=status,
                detail=detail,
            )
        )
        if progress_callback is not None:
            progress_callback(state, detail)

    def stop(state: AuditExecutionState, detail: str) -> None:
        record(state, detail, status="blocked")
        raise _AuditStopped(detail)

    if target_package_count != 1:
        record(
            AuditExecutionState.STOPPED,
            f"当前方案有 {target_package_count} 个包裹，单订单审核只允许 1 个包裹",
            status="blocked",
        )
        return _finish_report(
            execution_id=execution_id,
            started_at=started_at,
            target_system_order_id=target_system_order_id,
            expected_source=expected_source,
            confirmation_reference_id=confirmation_reference_id,
            state=AuditExecutionState.STOPPED,
            steps=steps,
            log_store=log_store,
        )
    if not target_system_order_id:
        record(
            AuditExecutionState.STOPPED,
            "当前订单缺少可靠系统订单号",
            status="blocked",
        )
        return _finish_report(
            execution_id=execution_id,
            started_at=started_at,
            target_system_order_id=target_system_order_id,
            expected_source=expected_source,
            confirmation_reference_id=confirmation_reference_id,
            state=AuditExecutionState.STOPPED,
            steps=steps,
            log_store=log_store,
        )

    operation_lock_path = _operation_lock_path(log_store)
    try:
        with FileLock(operation_lock_path, timeout=0.0):
            target_id = target_id or target_finder()
            if not target_id:
                stop(
                    AuditExecutionState.PREFLIGHT_CHECKING,
                    "没有找到当前前台的 ERP 待审核标签页",
                )

            record(AuditExecutionState.PREFLIGHT_CHECKING, "正在核对当前订单和页面状态")
            preflight = preflight_runner(
                target_system_order_id=target_system_order_id,
                expected_source=expected_source,
                confirmation_reference_id=confirmation_reference_id,
                target_id=target_id,
                evaluator=evaluator,
                log_store=None,
            )
            if not preflight.preflight_ready:
                detail = "；".join(check.detail for check in preflight.blockers)
                stop(AuditExecutionState.PREFLIGHT_CHECKING, detail)

            record(AuditExecutionState.SELECTING_ORDER, "审核前检查通过，正在勾选当前订单")
            selection_payload = _require_payload(
                evaluator(
                    target_id,
                    build_select_target_order_js(target_system_order_id),
                ),
                "SELECT_TARGET_FAILED",
                "未能安全勾选当前订单",
            )
            selection = validate_single_order_selection(
                SingleOrderSelectionProbe.from_payload(selection_payload),
                target_system_order_id=target_system_order_id,
                target_package_count=target_package_count,
            )
            if not selection.ready_to_open_audit_menu:
                stop(
                    AuditExecutionState.SELECTION_VERIFYING,
                    "；".join(check.detail for check in selection.blockers),
                )
            record(
                AuditExecutionState.SELECTION_VERIFYING,
                "只选中了当前目标订单，底部没有出现 2 条或更多",
            )

            trigger = _require_payload(
                evaluator(
                    target_id,
                    build_prepare_audit_menu_trigger_js(target_system_order_id),
                ),
                "AUDIT_MENU_TRIGGER_NOT_READY",
                "普通审核菜单入口无法唯一定位",
            )
            record(AuditExecutionState.OPENING_AUDIT_MENU, "正在打开普通审核菜单")
            mouse_clicker(target_id, float(trigger["x"]), float(trigger["y"]))

            ordinary_item = _poll_payload(
                target_id=target_id,
                evaluator=evaluator,
                js_builder=lambda: build_prepare_ordinary_audit_item_js(
                    target_system_order_id
                ),
                timeout_seconds=dialog_wait_seconds,
                sleeper=sleeper,
                monotonic=monotonic,
            )
            if ordinary_item is None:
                stop(
                    AuditExecutionState.OPENING_AUDIT_MENU,
                    "审核子菜单没有在限定时间内出现",
                )
            mouse_clicker(
                target_id,
                float(ordinary_item["x"]),
                float(ordinary_item["y"]),
            )

            record(
                AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                "已点击普通审核，正在核对弹窗处理范围",
            )
            dialog_validation = _poll_dialog(
                target_id=target_id,
                target_system_order_id=target_system_order_id,
                target_package_count=target_package_count,
                reader=dialog_reader,
                evaluator=evaluator,
                timeout_seconds=dialog_wait_seconds,
                sleeper=sleeper,
                monotonic=monotonic,
            )
            if dialog_validation is None:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    "审核弹窗没有在限定时间内出现",
                )
            if not dialog_validation.ready_to_submit:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    dialog_validation.render_text(),
                )

            confirm = _require_payload(
                evaluator(
                    target_id,
                    build_prepare_confirm_js(target_system_order_id),
                ),
                "AUDIT_CONFIRM_NOT_READY",
                "提交前弹窗状态发生变化",
            )
            record(
                AuditExecutionState.SUBMITTING,
                "弹窗确认只处理当前 1 单，正在点击一次确定",
            )
            # 从这一刻起，即使 CDP 返回异常，也不能再把结果当作“尚未提交”。
            # mousePressed 可能已经被 ERP 接收，任何后续异常都必须进入人工核对，
            # 绝不能重试确定按钮。
            submitted = True
            try:
                mouse_clicker(target_id, float(confirm["x"]), float(confirm["y"]))
            except Exception as exc:
                raise _AuditSubmittedUncertain(
                    f"确定按钮点击过程返回异常：{exc}"
                ) from exc

            record(
                AuditExecutionState.RESULT_VERIFYING,
                "已经点击一次确定，正在确认原订单是否离开待审核列表",
            )
            result = _poll_result(
                target_id=target_id,
                target_system_order_id=target_system_order_id,
                target_package_count=target_package_count,
                reader=result_reader,
                evaluator=evaluator,
                timeout_seconds=result_wait_seconds,
                sleeper=sleeper,
                monotonic=monotonic,
            )
            if result is None:
                raise _AuditSubmittedUncertain("限定时间内没有获得完整审核结果")
            if result.state == AuditExecutionState.SUCCESS:
                final_state = AuditExecutionState.SUCCESS
                record(AuditExecutionState.SUCCESS, result.render_text())
            elif result.state == AuditExecutionState.STOPPED:
                final_state = AuditExecutionState.STOPPED
                record(
                    AuditExecutionState.STOPPED,
                    result.render_text(),
                    status="blocked",
                )
            else:
                raise _AuditSubmittedUncertain(result.render_text())
    except _AuditStopped:
        final_state = AuditExecutionState.STOPPED
    except _AuditSubmittedUncertain as exc:
        final_state = AuditExecutionState.UNKNOWN
        record(AuditExecutionState.UNKNOWN, str(exc), status="blocked")
    except Exception as exc:
        final_state = (
            AuditExecutionState.UNKNOWN
            if submitted
            else AuditExecutionState.STOPPED
        )
        record(
            final_state,
            f"执行异常：{exc}",
            status="blocked",
        )

    return _finish_report(
        execution_id=execution_id,
        started_at=started_at,
        target_system_order_id=target_system_order_id,
        expected_source=expected_source,
        confirmation_reference_id=confirmation_reference_id,
        state=final_state,
        steps=steps,
        log_store=log_store,
    )


def click_mouse_at(target_id: str, x: float, y: float) -> None:
    cdp.cdp_call(
        target_id,
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": x, "y": y},
    )
    cdp.cdp_call(
        target_id,
        "Input.dispatchMouseEvent",
        {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": "left",
            "buttons": 1,
            "clickCount": 1,
        },
    )
    cdp.cdp_call(
        target_id,
        "Input.dispatchMouseEvent",
        {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": "left",
            "buttons": 0,
            "clickCount": 1,
        },
    )


def build_select_target_order_js(target_system_order_id: str) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    return rf"""/* ORDER_REVIEW_ACTION:SELECT_TARGET */
(async function(){{
  var expected = {target_json};
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
  function boxes(row){{
    return Array.from(new Set(Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"]'
    ))));
  }}
  function checked(row){{ return boxes(row).some(function(box){{ return box.checked; }}); }}
  function footerCounts(){{
    var values = [];
    Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
      var text = clean(el.innerText || el.textContent);
      if (text.length > 120) return;
      var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
      if (match) values.push(Number(match[1]));
    }});
    return Array.from(new Set(values));
  }}
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0) {{
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE'}});
  }}
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var targets = rows.filter(function(row){{ return systemOrderId(row) === expected; }});
  var selected = rows.filter(checked);
  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"],.el-message-box__wrapper'
  )))).filter(visible);
  if (targets.length !== 1) return JSON.stringify({{ok:false,error:'TARGET_NOT_UNIQUE'}});
  var targetBoxes = boxes(targets[0]);
  if (targetBoxes.length !== 1 || targetBoxes[0].checked || targetBoxes[0].disabled ||
      targetBoxes[0].getAttribute('aria-disabled') === 'true') {{
    return JSON.stringify({{ok:false,error:'TARGET_CHECKBOX_NOT_READY'}});
  }}
  if (selected.length !== 0) return JSON.stringify({{ok:false,error:'EXISTING_SELECTION'}});
  if (dialogs.length !== 0) return JSON.stringify({{ok:false,error:'EXISTING_DIALOG'}});
  if (footerCounts().some(function(value){{ return value >= 2; }})) {{
    return JSON.stringify({{ok:false,error:'FOOTER_MULTIPLE_ORDERS'}});
  }}
  targetBoxes[0].click();
  await new Promise(function(resolve){{ setTimeout(resolve, 100); }});
  rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  selected = rows.filter(checked);
  return JSON.stringify({{
    ok:true,
    selectedRowCount:selected.length,
    selectedSystemOrderIds:selected.map(systemOrderId),
    footerSelectedCounts:footerCounts()
  }});
}})()"""


def build_prepare_audit_menu_trigger_js(target_system_order_id: str) -> str:
    return _build_prepare_menu_js(
        target_system_order_id,
        marker="PREPARE_MENU_TRIGGER",
        body=r"""
  var toolbars = Array.from(document.querySelectorAll('.toolbar-list-item'))
    .filter(function(el){
      return visible(el) &&
        el.querySelector('.toolbar-sub_list [data-name="batch_audit"]') &&
        el.querySelector('.toolbar-sub_list [data-name="batch_force_audit"]');
    });
  if (toolbars.length !== 1) return JSON.stringify({ok:false,error:'TOOLBAR_NOT_UNIQUE'});
  var triggers = Array.from(toolbars[0].children).filter(function(el){
    return el.matches('a.toolbar-menu_item') && visible(el) && !el.getAttribute('data-name');
  });
  if (triggers.length !== 1) return JSON.stringify({ok:false,error:'TRIGGER_NOT_UNIQUE'});
  return center(triggers[0]);
""",
    )


def build_prepare_ordinary_audit_item_js(target_system_order_id: str) -> str:
    return _build_prepare_menu_js(
        target_system_order_id,
        marker="PREPARE_ORDINARY_AUDIT",
        body=r"""
  var menus = Array.from(document.querySelectorAll('.toolbar-sub_list')).filter(visible);
  if (menus.length !== 1) return JSON.stringify({ok:false,error:'MENU_NOT_VISIBLE'});
  var ordinary = Array.from(menus[0].querySelectorAll('[data-name="batch_audit"]'))
    .filter(function(el){ return visible(el) && clean(el.innerText || el.textContent) === '审核'; });
  var force = Array.from(menus[0].querySelectorAll('[data-name="batch_force_audit"]'))
    .filter(function(el){ return visible(el) && clean(el.innerText || el.textContent) === '强制审核'; });
  if (ordinary.length !== 1 || force.length !== 1) {
    return JSON.stringify({ok:false,error:'AUDIT_ITEMS_NOT_UNIQUE'});
  }
  return center(ordinary[0]);
""",
    )


def _build_prepare_menu_js(
    target_system_order_id: str,
    *,
    marker: str,
    body: str,
) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    return rf"""/* ORDER_REVIEW_ACTION:{marker} */
(function(){{
  var expected = {target_json};
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
      'input.J_Checkbox[data-name="check_select_item"]'
    )).some(function(input){{ return input.checked; }});
  }}
  function center(el){{
    var rect = el.getBoundingClientRect();
    return JSON.stringify({{ok:true,x:rect.left + rect.width / 2,y:rect.top + rect.height / 2}});
  }}
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var selected = rows.filter(checked);
  if (selected.length !== 1 || systemOrderId(selected[0]) !== expected) {{
    return JSON.stringify({{ok:false,error:'TARGET_SELECTION_CHANGED'}});
  }}
  var footerCounts = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
    var text = clean(el.innerText || el.textContent);
    if (text.length > 120) return;
    var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
    if (match) footerCounts.push(Number(match[1]));
  }});
  if (footerCounts.some(function(value){{ return value >= 2; }})) {{
    return JSON.stringify({{ok:false,error:'FOOTER_MULTIPLE_ORDERS'}});
  }}
{body}
}})()"""


def build_prepare_confirm_js(target_system_order_id: str) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    return rf"""/* ORDER_REVIEW_ACTION:PREPARE_CONFIRM */
(function(){{
  var expected = {target_json};
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
      'input.J_Checkbox[data-name="check_select_item"]'
    )).some(function(input){{ return input.checked; }});
  }}
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var selected = rows.filter(checked);
  if (selected.length !== 1 || systemOrderId(selected[0]) !== expected) {{
    return JSON.stringify({{ok:false,error:'TARGET_SELECTION_CHANGED'}});
  }}
  var footerCounts = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
    var text = clean(el.innerText || el.textContent);
    if (text.length > 120) return;
    var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
    if (match) footerCounts.push(Number(match[1]));
  }});
  if (footerCounts.some(function(value){{ return value >= 2; }})) {{
    return JSON.stringify({{ok:false,error:'FOOTER_MULTIPLE_ORDERS'}});
  }}
  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"].el-message-box__wrapper,.el-message-box__wrapper[role="dialog"],' +
    '[role="dialog"]'
  )))).filter(visible);
  if (dialogs.length !== 1) return JSON.stringify({{ok:false,error:'DIALOG_NOT_UNIQUE'}});
  var dialog = dialogs[0];
  var title = clean((dialog.querySelector('.el-message-box__title') || {{}}).innerText || '');
  var radios = Array.from(dialog.querySelectorAll('input[type="radio"]'));
  var list = radios.find(function(input){{ return input.value === '1'; }}) || null;
  var query = radios.find(function(input){{ return input.value === '2'; }}) || null;
  var listNode = list && list.closest('label.el-radio,[role="radio"],label');
  var listText = clean((listNode && (listNode.innerText || listNode.textContent)) || '');
  var count = listText.match(/已勾选\s*(\d+)\s*条订单/);
  if (title !== '提示' || !list || !list.checked || !query || query.checked ||
      !count || Number(count[1]) !== 1) {{
    return JSON.stringify({{ok:false,error:'DIALOG_SCOPE_CHANGED'}});
  }}
  var buttons = Array.from(dialog.querySelectorAll(
    '.el-message-box__btns button,button'
  )).filter(visible);
  var confirm = buttons.filter(function(button){{
    return clean(button.innerText || button.textContent) === '确定';
  }});
  var cancel = buttons.filter(function(button){{
    return clean(button.innerText || button.textContent) === '取消';
  }});
  if (confirm.length !== 1 || cancel.length !== 1 || confirm[0].disabled ||
      confirm[0].getAttribute('aria-disabled') === 'true') {{
    return JSON.stringify({{ok:false,error:'DIALOG_BUTTONS_NOT_READY'}});
  }}

  if (window.__orderReviewAuditObserver) window.__orderReviewAuditObserver.disconnect();
  var observation = {{
    targetDisappearedAt:'',
    dialogClosedAt:'',
    messages:[]
  }};
  var messageSelector = '.el-message,.ivu-message-notice,.ant-message-notice,' +
    '.toast,.toast-message,[role="status"],[role="alert"]';
  function observe(){{
    var currentRows = Array.from(document.querySelectorAll('.module-trade-list-item'));
    if (!currentRows.some(function(row){{ return systemOrderId(row) === expected; }}) &&
        !observation.targetDisappearedAt) {{
      observation.targetDisappearedAt = new Date().toISOString();
    }}
    var dialogOpen = Array.from(document.querySelectorAll(
      '[role="dialog"],.el-message-box__wrapper'
    )).some(visible);
    if (!dialogOpen && !observation.dialogClosedAt) {{
      observation.dialogClosedAt = new Date().toISOString();
    }}
    Array.from(document.querySelectorAll(messageSelector)).filter(visible)
      .forEach(function(el){{
        var text = clean(el.innerText || el.textContent).slice(0, 300);
        if (text && observation.messages.indexOf(text) < 0) observation.messages.push(text);
      }});
  }}
  var observer = new MutationObserver(observe);
  observer.observe(document.body, {{childList:true,subtree:true}});
  window.__orderReviewAuditObservation = observation;
  window.__orderReviewAuditObserver = observer;

  var rect = confirm[0].getBoundingClientRect();
  return JSON.stringify({{
    ok:true,
    x:rect.left + rect.width / 2,
    y:rect.top + rect.height / 2
  }});
}})()"""


def _poll_payload(
    *,
    target_id: str,
    evaluator: Callable[[str, str], Any],
    js_builder: Callable[[], str],
    timeout_seconds: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> dict[str, Any] | None:
    deadline = monotonic() + timeout_seconds
    while True:
        payload = evaluator(target_id, js_builder())
        if isinstance(payload, dict) and payload.get("ok"):
            return payload
        if monotonic() >= deadline:
            return None
        sleeper(AUDIT_POLL_INTERVAL_SECONDS)


def _poll_dialog(
    *,
    target_id: str,
    target_system_order_id: str,
    target_package_count: int,
    reader: Callable[..., AuditDialogValidation],
    evaluator: Callable[[str, str], Any],
    timeout_seconds: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> AuditDialogValidation | None:
    deadline = monotonic() + timeout_seconds
    while True:
        validation = reader(
            target_id,
            target_system_order_id=target_system_order_id,
            target_package_count=target_package_count,
            evaluator=evaluator,
        )
        if validation.probe.visible_dialog_count > 0:
            return validation
        if monotonic() >= deadline:
            return None
        sleeper(AUDIT_POLL_INTERVAL_SECONDS)


def _poll_result(
    *,
    target_id: str,
    target_system_order_id: str,
    target_package_count: int,
    reader: Callable[..., AuditResultValidation],
    evaluator: Callable[[str, str], Any],
    timeout_seconds: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> AuditResultValidation | None:
    deadline = monotonic() + timeout_seconds
    last_result: AuditResultValidation | None = None
    while True:
        last_result = reader(
            target_id,
            target_system_order_id=target_system_order_id,
            target_package_count=target_package_count,
            evaluator=evaluator,
        )
        if last_result.state in {
            AuditExecutionState.SUCCESS,
            AuditExecutionState.STOPPED,
        }:
            return last_result
        if monotonic() >= deadline:
            return last_result
        sleeper(AUDIT_POLL_INTERVAL_SECONDS)


def _require_payload(
    payload: Any,
    code: str,
    message: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("ok"):
        detail = payload.get("error") if isinstance(payload, dict) else ""
        raise AuditProbeError(code, f"{message}{f'：{detail}' if detail else ''}")
    return payload


def _finish_report(
    *,
    execution_id: str,
    started_at: str,
    target_system_order_id: str,
    expected_source: SourceSnapshot,
    confirmation_reference_id: str,
    state: AuditExecutionState,
    steps: list[AuditStep],
    log_store: AuditExecutionLogStore | None,
) -> SingleOrderAuditReport:
    report = SingleOrderAuditReport(
        execution_id=execution_id,
        started_at=started_at,
        finished_at=_utc_now(),
        target_system_order_id=target_system_order_id,
        source_snapshot_id=expected_source.snapshot_id,
        confirmation_reference_id=confirmation_reference_id,
        state=state,
        steps=tuple(steps),
    )
    if log_store is not None:
        try:
            log_store.append_payload(report.to_log_dict())
        except Exception:
            pass
    return report


def _operation_lock_path(log_store: AuditExecutionLogStore | None) -> Path:
    if log_store is not None:
        return log_store.path.with_name("audit-operation.lock")
    return Path("/tmp/order-review-audit-operation.lock")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
