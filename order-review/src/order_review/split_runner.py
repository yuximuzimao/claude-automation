from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable
from uuid import uuid4

from . import cdp
from .audit_dialog import (
    AuditDialogValidation,
    probe_and_validate_audit_dialog,
)
from .audit_execution import (
    AuditResultValidation,
    probe_and_validate_audit_result,
)
from .audit_probe import (
    AuditExecutionLogStore,
    AuditExecutionState,
    AuditProbeError,
    run_audit_preflight,
)
from .audit_runner import AuditStep, build_select_target_order_js, click_mouse_at
from .erp_reader import find_erp_toaudit_target
from .file_lock import FileLock
from .package_plan import PackagePlan, SourceSnapshot
from .split_dry_run import build_split_dry_run
from .split_probe import read_split_result_observation
from .split_result import (
    SplitResultObservation,
    SplitResultValidationReport,
    validate_split_result,
)


SPLIT_DIALOG_WAIT_SECONDS = 5.0
SPLIT_RESULT_WAIT_SECONDS = 15.0
SPLIT_POLL_INTERVAL_SECONDS = 0.1
SPLIT_ACTION_PAUSE_SECONDS = 0.3


@dataclass(frozen=True)
class SplitOrderReport:
    execution_id: str
    started_at: str
    finished_at: str
    target_system_order_id: str
    source_snapshot_id: str
    confirmation_reference_id: str
    state: AuditExecutionState
    steps: tuple[AuditStep, ...]
    split_completed: bool = False

    @property
    def successful(self) -> bool:
        return self.state == AuditExecutionState.SUCCESS

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "mode": "mixed_split_order",
            "executionId": self.execution_id,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "targetSystemOrderId": self.target_system_order_id,
            "sourceSnapshotId": self.source_snapshot_id,
            "confirmationReferenceId": self.confirmation_reference_id,
            "splitCompleted": self.split_completed,
            "state": self.state.value,
            "steps": [step.to_dict() for step in self.steps],
        }

    def render_text(self) -> str:
        if self.successful:
            return (
                f"拆分并审核成功：订单 {self.target_system_order_id} 已按当前方案"
                "拆成目标包裹，逐包明细、审核弹窗数量和审核结果均已核对通过。"
            )
        detail = self.steps[-1].detail if self.steps else "没有可用执行结果"
        if self.split_completed:
            if self.state == AuditExecutionState.UNKNOWN:
                return (
                    f"拆分已成功，但审核结果不确定：{detail}。"
                    "没有重试审核，请人工核对 ERP。"
                )
            return (
                f"拆分已成功，但审核已停止：{detail}。"
                "没有重试审核。"
            )
        if self.state == AuditExecutionState.UNKNOWN:
            return (
                f"拆分结果不确定：{detail}。没有重试提交，"
                "请人工核对 ERP。"
            )
        return f"拆分已停止：{detail}。没有重试提交。"


class _SplitStopped(RuntimeError):
    pass


class _SplitSubmittedUncertain(RuntimeError):
    pass


def run_mixed_order_split(
    *,
    target_system_order_id: str,
    expected_source: SourceSnapshot,
    plan: PackagePlan,
    confirmation_reference_id: str = "",
    target_id: str | None = None,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
    mouse_clicker: Callable[[str, float, float], None] = click_mouse_at,
    mouse_mover: Callable[[str, float, float], None] | None = None,
    target_finder: Callable[[], str | None] = find_erp_toaudit_target,
    preflight_runner: Callable[..., Any] = run_audit_preflight,
    audit_dialog_reader: Callable[..., AuditDialogValidation] = (
        probe_and_validate_audit_dialog
    ),
    audit_result_reader: Callable[..., AuditResultValidation] = (
        probe_and_validate_audit_result
    ),
    split_result_reader: Callable[..., SplitResultObservation] = (
        read_split_result_observation
    ),
    split_result_validator: Callable[
        [SourceSnapshot, PackagePlan, SplitResultObservation],
        SplitResultValidationReport,
    ] = validate_split_result,
    progress_callback: Callable[[AuditExecutionState, str], None] | None = None,
    log_store: AuditExecutionLogStore | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    dialog_wait_seconds: float = SPLIT_DIALOG_WAIT_SECONDS,
    result_wait_seconds: float = SPLIT_RESULT_WAIT_SECONDS,
    action_pause_seconds: float = SPLIT_ACTION_PAUSE_SECONDS,
) -> SplitOrderReport:
    execution_id = f"split-{uuid4()}"
    started_at = _utc_now()
    steps: list[AuditStep] = []
    final_state = AuditExecutionState.STOPPED
    split_submitted = False
    split_completed = False
    audit_submitted = False
    mouse_mover = mouse_mover or move_mouse_at

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
        raise _SplitStopped(detail)

    local = build_split_dry_run(expected_source, plan)
    if not local.local_plan_valid:
        record(
            AuditExecutionState.STOPPED,
            "；".join(local.blocked_reasons),
            status="blocked",
        )
        return _finish_report(
            execution_id,
            started_at,
            target_system_order_id,
            expected_source,
            confirmation_reference_id,
            AuditExecutionState.STOPPED,
            steps,
            log_store,
        )

    expected_rows = _expected_dialog_rows(expected_source)
    package_quantities = _package_quantities(expected_source, plan)
    operation_lock = _operation_lock_path(log_store)

    try:
        with FileLock(operation_lock, timeout=0.0):
            target_id = target_id or target_finder()
            if not target_id:
                stop(
                    AuditExecutionState.PREFLIGHT_CHECKING,
                    "没有找到当前前台的 ERP 待审核标签页",
                )

            record(
                AuditExecutionState.PREFLIGHT_CHECKING,
                "正在核对当前订单、已保存方案和页面状态",
            )
            preflight = preflight_runner(
                target_system_order_id=target_system_order_id,
                expected_source=expected_source,
                confirmation_reference_id=confirmation_reference_id,
                target_id=target_id,
                evaluator=evaluator,
                log_store=None,
            )
            if not preflight.preflight_ready:
                stop(
                    AuditExecutionState.PREFLIGHT_CHECKING,
                    "；".join(check.detail for check in preflight.blockers),
                )

            _require_payload(
                evaluator(target_id, build_install_network_observer_js(execution_id)),
                "NETWORK_OBSERVER_FAILED",
                "无法安装拆分结果观测器",
            )
            record(
                AuditExecutionState.SELECTING_ORDER,
                "检查通过，正在勾选当前订单",
            )
            selected = _require_payload(
                evaluator(
                    target_id,
                    build_select_target_order_js(
                        target_system_order_id,
                        guard_footer_multiple=False,
                    ),
                ),
                "SELECT_TARGET_FAILED",
                "未能安全勾选当前订单",
            )
            if (
                int(selected.get("selectedRowCount") or 0) != 1
                or selected.get("selectedSystemOrderIds")
                != [target_system_order_id]
            ):
                stop(
                    AuditExecutionState.SELECTION_VERIFYING,
                    "勾选后并非只选中当前目标订单",
                )
            sleeper(action_pause_seconds)

            trigger = _require_payload(
                evaluator(
                    target_id,
                    build_prepare_split_menu_trigger_js(target_system_order_id),
                ),
                "SPLIT_MENU_TRIGGER_NOT_READY",
                "订单拆分菜单入口无法唯一定位",
            )
            record(
                AuditExecutionState.OPENING_AUDIT_MENU,
                "正在悬浮打开订单拆分菜单",
            )
            mouse_mover(target_id, float(trigger["x"]), float(trigger["y"]))
            mixed_item = _poll_payload(
                target_id,
                evaluator,
                lambda: build_prepare_mixed_split_item_js(target_system_order_id),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if mixed_item is None:
                stop(
                    AuditExecutionState.OPENING_AUDIT_MENU,
                    "混合拆分菜单没有在限定时间内出现",
                )
            sleeper(action_pause_seconds)
            mouse_clicker(
                target_id,
                float(mixed_item["x"]),
                float(mixed_item["y"]),
            )

            record(
                AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                "已打开混合拆分，正在核对商品行顺序和可拆数量",
            )
            dialog = _poll_payload(
                target_id,
                evaluator,
                lambda: build_probe_split_dialog_js(
                    target_system_order_id,
                    expected_rows,
                ),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if dialog is None:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    "混合拆分弹窗未出现，或商品明细与原订单不一致",
                )
            component_uid = int(dialog["componentUid"])
            sleeper(action_pause_seconds)

            remaining = [row["quantity"] for row in expected_rows]
            added_packages: list[list[int]] = []
            packages_to_fill = package_quantities[:-1]
            final_package = package_quantities[-1]
            for index, quantities in enumerate(packages_to_fill, start=1):
                _require_payload(
                    evaluator(
                        target_id,
                        build_fill_split_package_js(
                            target_system_order_id,
                            component_uid,
                            expected_rows,
                            quantities,
                            remaining,
                            added_packages,
                        ),
                    ),
                    "SPLIT_PACKAGE_FILL_FAILED",
                    f"包裹 {index} 数量填写失败",
                )
                record(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    f"包裹 {index}/{len(package_quantities)} 数量已填写，正在等待页面稳定",
                )
                sleeper(action_pause_seconds)
                if index == len(packages_to_fill):
                    record(
                        AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                        (
                            f"包裹 {index}/{len(package_quantities)} 数量已填写；"
                            "将直接确认，最后一包由 ERP 按剩余量生成"
                        ),
                    )
                    break

                add_button = _poll_payload(
                    target_id,
                    evaluator,
                    lambda: build_prepare_add_split_package_js(
                        target_system_order_id,
                        component_uid,
                        expected_rows,
                        quantities,
                        remaining,
                        added_packages,
                    ),
                    dialog_wait_seconds,
                    sleeper,
                    monotonic,
                )
                if add_button is None:
                    stop(
                        AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                        f"包裹 {index} 填写后页面或添加按钮未稳定",
                    )
                record(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    f"包裹 {index}/{len(package_quantities)} 数量已核对，正在点击添加待拆分",
                )
                mouse_clicker(
                    target_id,
                    float(add_button["x"]),
                    float(add_button["y"]),
                )
                remaining = [
                    current - quantity
                    for current, quantity in zip(remaining, quantities)
                ]
                added_packages.insert(0, list(quantities))
                sleeper(action_pause_seconds)
                added = _poll_payload(
                    target_id,
                    evaluator,
                    lambda: build_verify_added_package_js(
                        target_system_order_id,
                        component_uid,
                        expected_rows,
                        remaining,
                        added_packages,
                    ),
                    dialog_wait_seconds,
                    sleeper,
                    monotonic,
                )
                if added is None:
                    stop(
                        AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                        f"包裹 {index} 添加后的剩余量或包裹卡片不一致",
                    )

            confirm = _poll_payload(
                target_id,
                evaluator,
                lambda: build_prepare_split_confirm_js(
                    target_system_order_id,
                    component_uid,
                    expected_rows,
                    packages_to_fill[-1],
                    final_package,
                    remaining,
                    added_packages,
                ),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if confirm is None:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    "倒数第二包填写后，确认按钮或最后剩余包裹未稳定",
                )
            record(
                AuditExecutionState.SUBMITTING,
                "已核对待拆包裹、倒数第二包和最后剩余包裹，正在点击确定",
            )
            sleeper(action_pause_seconds)
            mouse_clicker(target_id, float(confirm["x"]), float(confirm["y"]))

            secondary = _poll_payload(
                target_id,
                evaluator,
                lambda: build_prepare_secondary_confirm_js(
                    target_system_order_id
                ),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if secondary is None:
                stop(
                    AuditExecutionState.SUBMITTING,
                    "没有出现唯一的订单拆分二次确认",
                )
            record(
                AuditExecutionState.SUBMITTING,
                "二次确认内容正确，正在点击一次确定",
            )
            sleeper(action_pause_seconds)
            split_submitted = True
            try:
                mouse_clicker(
                    target_id,
                    float(secondary["x"]),
                    float(secondary["y"]),
                )
            except Exception as exc:
                raise _SplitSubmittedUncertain(
                    f"二次确认点击过程返回异常：{exc}"
                ) from exc

            network = _poll_payload(
                target_id,
                evaluator,
                lambda: build_read_split_network_result_js(execution_id),
                result_wait_seconds,
                sleeper,
                monotonic,
            )
            if network is None:
                raise _SplitSubmittedUncertain("没有读取到混合拆分接口响应")
            expected_increase = len(plan.packages) - 1
            if not _network_confirms_split(network, expected_increase):
                stop(
                    AuditExecutionState.RESULT_VERIFYING,
                    (
                        "ERP 接口结果不满足拆分成功条件："
                        f"status={network.get('status', 0)}，"
                        f"result={network.get('result')}，"
                        "splitResult.success(仅记录，不参与判定)="
                        f"{network.get('splitSuccess')}，"
                        f"increaseSplitCount="
                        f"{network.get('increaseSplitCount', 0)}/"
                        f"{expected_increase}"
                    ),
                )

            split_completed = True
            record(
                AuditExecutionState.RESULT_VERIFYING,
                (
                    "ERP 已返回拆分成功；正在核对前 "
                    f"{len(plan.packages)} 条已勾选结果的逐包商品明细"
                ),
            )

            try:
                split_validation = _poll_split_result_validation(
                    target_id,
                    expected_source,
                    plan,
                    split_result_reader,
                    split_result_validator,
                    evaluator,
                    result_wait_seconds,
                    sleeper,
                    monotonic,
                )
            except Exception as exc:
                stop(
                    AuditExecutionState.RESULT_VERIFYING,
                    f"拆分成功，但读取已勾选结果明细失败：{exc}",
                )
            if not split_validation.verified:
                stop(
                    AuditExecutionState.RESULT_VERIFYING,
                    split_validation.to_text(),
                )
            record(
                AuditExecutionState.RESULT_VERIFYING,
                (
                    f"前 {len(plan.packages)} 条已勾选结果均已读取；"
                    "逐包明细、平台子订单和商品总量与本地方案一致"
                ),
            )

            audit_trigger = _poll_payload(
                target_id,
                evaluator,
                lambda: build_prepare_split_audit_menu_trigger_js(
                    len(plan.packages)
                ),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if audit_trigger is None:
                stop(
                    AuditExecutionState.OPENING_AUDIT_MENU,
                    "拆分成功，但普通审核菜单入口没有稳定出现",
                )
            record(
                AuditExecutionState.OPENING_AUDIT_MENU,
                "拆分成功，正在打开已勾选结果的普通审核菜单",
            )
            mouse_clicker(
                target_id,
                float(audit_trigger["x"]),
                float(audit_trigger["y"]),
            )
            sleeper(action_pause_seconds)

            ordinary_item = _poll_payload(
                target_id,
                evaluator,
                lambda: build_prepare_split_ordinary_audit_item_js(
                    len(plan.packages)
                ),
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if ordinary_item is None:
                stop(
                    AuditExecutionState.OPENING_AUDIT_MENU,
                    "拆分成功，但普通审核子菜单没有稳定出现",
                )
            mouse_clicker(
                target_id,
                float(ordinary_item["x"]),
                float(ordinary_item["y"]),
            )
            sleeper(action_pause_seconds)

            record(
                AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                (
                    "已点击普通审核，正在核对弹窗是否显示已勾选 "
                    f"{len(plan.packages)} 条订单"
                ),
            )
            audit_dialog = _poll_audit_dialog(
                target_id,
                target_system_order_id,
                len(plan.packages),
                audit_dialog_reader,
                evaluator,
                dialog_wait_seconds,
                sleeper,
                monotonic,
            )
            if audit_dialog is None:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    "拆分成功，但审核弹窗没有在限定时间内出现",
                )
            if not audit_dialog.ready_to_submit:
                stop(
                    AuditExecutionState.AUDIT_DIALOG_VERIFYING,
                    audit_dialog.render_text(),
                )

            audit_confirm = _require_payload(
                evaluator(
                    target_id,
                    build_prepare_split_audit_confirm_js(
                        target_system_order_id,
                        len(plan.packages),
                    ),
                ),
                "SPLIT_AUDIT_CONFIRM_NOT_READY",
                "拆分后审核提交前，弹窗勾选数量或处理范围发生变化",
            )
            record(
                AuditExecutionState.SUBMITTING,
                (
                    f"审核弹窗确认已勾选 {len(plan.packages)} 条订单，"
                    "正在点击一次确定"
                ),
            )
            sleeper(action_pause_seconds)
            audit_submitted = True
            try:
                mouse_clicker(
                    target_id,
                    float(audit_confirm["x"]),
                    float(audit_confirm["y"]),
                )
            except Exception as exc:
                raise _SplitSubmittedUncertain(
                    f"拆分后审核确定按钮点击过程返回异常：{exc}"
                ) from exc

            record(
                AuditExecutionState.RESULT_VERIFYING,
                "已经点击一次审核确定，正在确认拆分结果离开待审核列表",
            )
            audit_result = _poll_audit_result(
                target_id,
                target_system_order_id,
                len(plan.packages),
                audit_result_reader,
                evaluator,
                result_wait_seconds,
                sleeper,
                monotonic,
            )
            if audit_result is None:
                raise _SplitSubmittedUncertain(
                    "限定时间内没有获得完整的拆分后审核结果"
                )
            if audit_result.state == AuditExecutionState.SUCCESS:
                final_state = AuditExecutionState.SUCCESS
                record(AuditExecutionState.SUCCESS, audit_result.render_text())
            elif audit_result.state == AuditExecutionState.STOPPED:
                final_state = AuditExecutionState.STOPPED
                record(
                    AuditExecutionState.STOPPED,
                    audit_result.render_text(),
                    status="blocked",
                )
            else:
                raise _SplitSubmittedUncertain(audit_result.render_text())
    except _SplitStopped:
        final_state = AuditExecutionState.STOPPED
    except _SplitSubmittedUncertain as exc:
        final_state = AuditExecutionState.UNKNOWN
        record(AuditExecutionState.UNKNOWN, str(exc), status="blocked")
    except Exception as exc:
        final_state = (
            AuditExecutionState.UNKNOWN
            if audit_submitted or (split_submitted and not split_completed)
            else AuditExecutionState.STOPPED
        )
        record(final_state, f"执行异常：{exc}", status="blocked")

    return _finish_report(
        execution_id,
        started_at,
        target_system_order_id,
        expected_source,
        confirmation_reference_id,
        final_state,
        steps,
        log_store,
        split_completed,
    )


def move_mouse_at(target_id: str, x: float, y: float) -> None:
    cdp.cdp_call(
        target_id,
        "Input.dispatchMouseEvent",
        {"type": "mouseMoved", "x": x, "y": y},
    )


def build_install_network_observer_js(execution_id: str) -> str:
    run_json = json.dumps(execution_id, ensure_ascii=False)
    return rf"""(function(){{
  var runId = {run_json};
  window.__orderReviewSplitNetwork = {{runId:runId, result:null}};
  if (!window.__orderReviewSplitXhrPatched) {{
    window.__orderReviewSplitXhrPatched = true;
    var originalOpen = XMLHttpRequest.prototype.open;
    var originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {{
      this.__orderReviewRequest = {{method:String(method || ''),url:String(url || '')}};
      return originalOpen.apply(this, arguments);
    }};
    XMLHttpRequest.prototype.send = function(body) {{
      var request = this.__orderReviewRequest;
      if (request && request.url.indexOf('/trade/split/mix') >= 0) {{
        request.body = typeof body === 'string' ? body : '';
        this.addEventListener('loadend', function(){{
          var response = {{}};
          try {{ response = JSON.parse(this.responseText || '{{}}'); }} catch (_error) {{}}
          var split = response && response.data && response.data.splitResult || {{}};
          if (window.__orderReviewSplitNetwork) {{
            window.__orderReviewSplitNetwork.result = {{
              url:request.url,
              status:Number(this.status || 0),
              body:request.body,
              result:response.result,
              splitSuccess:typeof split.success === 'boolean' ? split.success : null,
              increaseSplitCount:Number(split.increaseSplitCount || 0),
              insertSids:Array.isArray(split.insertSids) ? split.insertSids : []
            }};
          }}
        }});
      }}
      return originalSend.apply(this, arguments);
    }};
  }}
  return JSON.stringify({{ok:true,runId:runId}});
}})()"""


def build_prepare_split_menu_trigger_js(target_system_order_id: str) -> str:
    return _selected_order_guard_js(
        target_system_order_id,
        r"""
  var taskbars = Array.from(document.querySelectorAll(
    '.module-trade-taskbar-inner.J_Taskbar'
  )).filter(visible);
  if (taskbars.length !== 1) return JSON.stringify({ok:false,error:'TASKBAR_NOT_UNIQUE'});
  var triggers = Array.from(taskbars[0].querySelectorAll('a.toolbar-menu_item'))
    .filter(function(el){
      return visible(el) && clean(el.innerText || el.textContent).indexOf('订单拆分') >= 0 &&
        el.parentElement && el.parentElement.querySelector(
          '.toolbar-sub_list [data-name="trade_split_by_mixed"]'
        );
    });
  if (triggers.length !== 1) return JSON.stringify({ok:false,error:'TRIGGER_NOT_UNIQUE'});
  return center(triggers[0]);
""",
    )


def build_prepare_mixed_split_item_js(target_system_order_id: str) -> str:
    return _selected_order_guard_js(
        target_system_order_id,
        r"""
  var items = Array.from(document.querySelectorAll(
    '.module-trade-taskbar-inner.J_Taskbar ' +
    '.toolbar-sub_list [data-name="trade_split_by_mixed"]'
  )).filter(function(el){
    return visible(el) && clean(el.innerText || el.textContent) === '混合拆分';
  });
  if (items.length !== 1) return JSON.stringify({ok:false,error:'MIXED_ITEM_NOT_UNIQUE'});
  return center(items[0]);
""",
    )


def build_probe_split_dialog_js(
    target_system_order_id: str,
    expected_rows: list[dict[str, Any]],
) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    rows_json = json.dumps(expected_rows, ensure_ascii=False)
    return rf"""(function(){{
  var target = {target_json};
  var expected = {rows_json};
  { _dialog_helpers_js() }
  var found = currentDialog(target);
  if (!found) return JSON.stringify({{ok:false,error:'DIALOG_NOT_READY'}});
  var state = validateRows(found.biz, expected);
  var inputs = Array.from(found.dialog.querySelectorAll(
    '.el-table__body input.el-input__inner'
  ));
  var ready = state.ok && found.biz.pendingSplitList.length === 0 &&
    inputs.length === expected.length &&
    inputs.every(function(input){{ return String(input.value) === '0' && !input.disabled; }});
  if (!ready) return JSON.stringify({{ok:false,error:'DIALOG_DATA_MISMATCH'}});
  return JSON.stringify({{
    ok:true,
    componentUid:found.biz._uid,
    rows:state.rows
  }});
}})()"""


def build_fill_split_package_js(
    target_system_order_id: str,
    component_uid: int,
    expected_rows: list[dict[str, Any]],
    quantities: list[int],
    remaining: list[int],
    added_packages: list[list[int]],
) -> str:
    return _split_component_action_js(
        target_system_order_id,
        component_uid,
        expected_rows,
        remaining,
        added_packages,
        rf"""
  var quantities = {json.dumps(quantities)};
  if (quantities.length !== expected.length || quantities.every(function(x){{ return x === 0; }}))
    return JSON.stringify({{ok:false,error:'EMPTY_PACKAGE'}});
  for (var i = 0; i < quantities.length; i += 1) {{
    if (quantities[i] < 0 || quantities[i] > remaining[i])
      return JSON.stringify({{ok:false,error:'PACKAGE_QUANTITY_INVALID'}});
  }}
  var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  quantities.forEach(function(quantity, index){{
    if (quantity <= 0) return;
    setter.call(inputs[index], String(quantity));
    inputs[index].dispatchEvent(new Event('input', {{bubbles:true}}));
    inputs[index].dispatchEvent(new Event('change', {{bubbles:true}}));
    inputs[index].blur();
  }});
  var actual = found.biz.tableData.map(function(row){{ return Number(row.rcSplitNum || 0); }});
  if (!actual.every(function(value, index){{
    return remaining[index] === 0 ?
      quantities[index] === 0 : value === quantities[index];
  }}))
    return JSON.stringify({{ok:false,error:'INPUT_COMPONENT_MISMATCH'}});
  return JSON.stringify({{ok:true,filled:true}});
""",
    )


def build_prepare_add_split_package_js(
    target_system_order_id: str,
    component_uid: int,
    expected_rows: list[dict[str, Any]],
    quantities: list[int],
    remaining: list[int],
    added_packages: list[list[int]],
) -> str:
    return _split_component_action_js(
        target_system_order_id,
        component_uid,
        expected_rows,
        remaining,
        added_packages,
        rf"""
  var quantities = {json.dumps(quantities)};
  var actual = found.biz.tableData.map(function(row){{ return Number(row.rcSplitNum || 0); }});
  if (!actual.every(function(value, index){{
    return remaining[index] === 0 ?
      quantities[index] === 0 : value === quantities[index];
  }}))
    return JSON.stringify({{ok:false,error:'INPUT_COMPONENT_MISMATCH'}});
  if (!inputs.every(function(input, index){{
    return remaining[index] === 0 ?
      quantities[index] === 0 && input.disabled :
      String(input.value) === String(quantities[index]) && !input.disabled;
  }}))
    return JSON.stringify({{ok:false,error:'INPUT_DOM_MISMATCH'}});
  var buttons = Array.from(found.dialog.querySelectorAll('button')).filter(function(button){{
    return visible(button) && clean(button.innerText || button.textContent) === '添加待拆分';
  }});
  if (buttons.length !== 1 || buttons[0].disabled)
    return JSON.stringify({{ok:false,error:'ADD_BUTTON_NOT_READY'}});
  return center(buttons[0]);
""",
        input_quantities=quantities,
    )


def build_verify_added_package_js(
    target_system_order_id: str,
    component_uid: int,
    expected_rows: list[dict[str, Any]],
    remaining: list[int],
    added_packages: list[list[int]],
) -> str:
    return _split_component_action_js(
        target_system_order_id,
        component_uid,
        expected_rows,
        remaining,
        added_packages,
        r"""
  var cards = Array.from(found.dialog.querySelectorAll('.split-item-wrapper')).filter(visible);
  if (cards.length !== pendingExpected.length)
    return JSON.stringify({ok:false,error:'PACKAGE_CARD_COUNT_CHANGED'});
  return JSON.stringify({ok:true,pendingCount:found.biz.pendingSplitList.length});
""",
    )


def build_prepare_split_confirm_js(
    target_system_order_id: str,
    component_uid: int,
    expected_rows: list[dict[str, Any]],
    current_quantities: list[int],
    final_quantities: list[int],
    remaining: list[int],
    added_packages: list[list[int]],
) -> str:
    return _split_component_action_js(
        target_system_order_id,
        component_uid,
        expected_rows,
        remaining,
        added_packages,
        rf"""
  var current = {json.dumps(current_quantities)};
  var finalPackage = {json.dumps(final_quantities)};
  var actual = found.biz.tableData.map(function(row){{ return Number(row.rcSplitNum || 0); }});
  if (!actual.every(function(value, index){{
    return remaining[index] === 0 ?
      current[index] === 0 : value === current[index];
  }}))
    return JSON.stringify({{ok:false,error:'CONFIRM_INPUT_COMPONENT_MISMATCH'}});
  var finalRemaining = remaining.map(function(value, index){{
    return value - current[index];
  }});
  if (finalRemaining.some(function(value){{ return value < 0; }}) ||
      JSON.stringify(finalRemaining) !== JSON.stringify(finalPackage))
    return JSON.stringify({{ok:false,error:'FINAL_PACKAGE_MISMATCH'}});
  var cards = Array.from(found.dialog.querySelectorAll('.split-item-wrapper')).filter(visible);
  if (cards.length !== pendingExpected.length)
    return JSON.stringify({{ok:false,error:'PACKAGE_CARD_COUNT_CHANGED'}});
  var buttons = Array.from(found.dialog.querySelectorAll('button')).filter(function(button){{
    return visible(button) && clean(button.innerText || button.textContent) === '确定';
  }});
  if (buttons.length !== 1 || buttons[0].disabled)
    return JSON.stringify({{ok:false,error:'MAIN_CONFIRM_NOT_READY'}});
  return center(buttons[0]);
""",
        input_quantities=current_quantities,
    )


def build_prepare_secondary_confirm_js(target_system_order_id: str) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    return rf"""(function(){{
  var expected = {target_json};
  { _common_page_helpers_js() }
  if (document.visibilityState !== 'visible')
    return JSON.stringify({{ok:false,error:'PAGE_NOT_VISIBLE'}});
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var selected = rows.filter(checked);
  if (selected.length !== 1 || systemOrderId(selected[0]) !== expected)
    return JSON.stringify({{ok:false,error:'TARGET_SELECTION_CHANGED'}});
  var boxes = Array.from(document.querySelectorAll('.el-message-box__wrapper'))
    .filter(function(el){{
      return visible(el) && !el.classList.contains('msgbox-fade-leave') &&
        !el.classList.contains('msgbox-fade-leave-active');
    }});
  if (boxes.length !== 1) return JSON.stringify({{ok:false,error:'CONFIRM_NOT_UNIQUE'}});
  var text = clean(boxes[0].innerText || boxes[0].textContent);
  if (text !== '提示 您是否确定进行订单拆分？ 取消确定')
    return JSON.stringify({{ok:false,error:'CONFIRM_TEXT_CHANGED'}});
  var buttons = Array.from(boxes[0].querySelectorAll('button')).filter(function(button){{
    return visible(button) && clean(button.innerText || button.textContent) === '确定';
  }});
  if (buttons.length !== 1 || buttons[0].disabled)
    return JSON.stringify({{ok:false,error:'SECONDARY_CONFIRM_NOT_READY'}});
  return center(buttons[0]);
}})()"""


def build_read_split_network_result_js(execution_id: str) -> str:
    run_json = json.dumps(execution_id, ensure_ascii=False)
    return rf"""(function(){{
  var monitor = window.__orderReviewSplitNetwork;
  if (!monitor || monitor.runId !== {run_json} || !monitor.result)
    return JSON.stringify({{ok:false,error:'RESULT_NOT_READY'}});
  return JSON.stringify(Object.assign({{ok:true}}, monitor.result));
}})()"""


def build_prepare_split_audit_menu_trigger_js(
    target_package_count: int,
) -> str:
    count_json = json.dumps(target_package_count)
    return rf"""/* ORDER_REVIEW_ACTION:PREPARE_SPLIT_AUDIT_MENU */
(function(){{
  var expectedCount = {count_json};
  { _common_page_helpers_js() }
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0)
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE'}});
  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"],.el-message-box__wrapper'
  )))).filter(visible);
  if (dialogs.length !== 0)
    return JSON.stringify({{ok:false,error:'EXISTING_DIALOG'}});
  var loading = Array.from(document.querySelectorAll(
    '.el-loading-mask,.ivu-spin-fix,.ant-spin-spinning,[aria-busy="true"]'
  )).filter(visible);
  if (loading.length !== 0)
    return JSON.stringify({{ok:false,error:'PAGE_LOADING'}});
  var selected = Array.from(document.querySelectorAll(
    '.module-trade-list-item'
  )).filter(visible).filter(checked);
  var selectedSequences = selected.map(sequence).sort(function(a,b){{ return a-b; }});
  var expectedSequences = Array.from(
    {{length:expectedCount}}, function(_value,index){{ return index + 1; }}
  );
  if (selected.length !== expectedCount ||
      JSON.stringify(selectedSequences) !== JSON.stringify(expectedSequences))
    return JSON.stringify({{ok:false,error:'SPLIT_SELECTION_CHANGED'}});
  var toolbars = Array.from(document.querySelectorAll('.toolbar-list-item'))
    .filter(function(el){{
      return visible(el) &&
        el.querySelector('.toolbar-sub_list [data-name="batch_audit"]') &&
        el.querySelector('.toolbar-sub_list [data-name="batch_force_audit"]');
    }});
  if (toolbars.length !== 1)
    return JSON.stringify({{ok:false,error:'TOOLBAR_NOT_UNIQUE'}});
  var triggers = Array.from(toolbars[0].children).filter(function(el){{
    return el.matches('a.toolbar-menu_item') && visible(el) &&
      !el.getAttribute('data-name');
  }});
  if (triggers.length !== 1)
    return JSON.stringify({{ok:false,error:'TRIGGER_NOT_UNIQUE'}});
  return center(triggers[0]);
}})()"""


def build_prepare_split_ordinary_audit_item_js(
    target_package_count: int,
) -> str:
    count_json = json.dumps(target_package_count)
    return rf"""/* ORDER_REVIEW_ACTION:PREPARE_SPLIT_ORDINARY_AUDIT */
(function(){{
  var expectedCount = {count_json};
  { _common_page_helpers_js() }
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0)
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE'}});
  var selected = Array.from(document.querySelectorAll(
    '.module-trade-list-item'
  )).filter(visible).filter(checked);
  var selectedSequences = selected.map(sequence).sort(function(a,b){{ return a-b; }});
  var expectedSequences = Array.from(
    {{length:expectedCount}}, function(_value,index){{ return index + 1; }}
  );
  if (selected.length !== expectedCount ||
      JSON.stringify(selectedSequences) !== JSON.stringify(expectedSequences))
    return JSON.stringify({{ok:false,error:'SPLIT_SELECTION_CHANGED'}});
  var menus = Array.from(document.querySelectorAll(
    '.toolbar-sub_list'
  )).filter(visible);
  if (menus.length !== 1)
    return JSON.stringify({{ok:false,error:'MENU_NOT_VISIBLE'}});
  var ordinary = Array.from(menus[0].querySelectorAll(
    '[data-name="batch_audit"]'
  )).filter(function(el){{
    return visible(el) && clean(el.innerText || el.textContent) === '审核';
  }});
  var force = Array.from(menus[0].querySelectorAll(
    '[data-name="batch_force_audit"]'
  )).filter(function(el){{
    return visible(el) && clean(el.innerText || el.textContent) === '强制审核';
  }});
  if (ordinary.length !== 1 || force.length !== 1)
    return JSON.stringify({{ok:false,error:'AUDIT_ITEMS_NOT_UNIQUE'}});
  return center(ordinary[0]);
}})()"""


def build_prepare_split_audit_confirm_js(
    target_system_order_id: str,
    target_package_count: int,
) -> str:
    target_json = json.dumps(target_system_order_id, ensure_ascii=False)
    count_json = json.dumps(target_package_count)
    return rf"""/* ORDER_REVIEW_ACTION:PREPARE_SPLIT_AUDIT_CONFIRM */
(function(){{
  var target = {target_json};
  var expectedCount = {count_json};
  { _common_page_helpers_js() }
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0)
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE'}});
  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"].el-message-box__wrapper,.el-message-box__wrapper[role="dialog"],' +
    '[role="dialog"]'
  )))).filter(visible);
  if (dialogs.length !== 1)
    return JSON.stringify({{ok:false,error:'DIALOG_NOT_UNIQUE'}});
  var dialog = dialogs[0];
  var title = clean((dialog.querySelector(
    '.el-message-box__title'
  ) || {{}}).innerText || '');
  var radios = Array.from(dialog.querySelectorAll('input[type="radio"]'));
  var list = radios.find(function(input){{ return input.value === '1'; }}) || null;
  var query = radios.find(function(input){{ return input.value === '2'; }}) || null;
  var listNode = list && list.closest('label.el-radio,[role="radio"],label');
  var listText = clean(
    (listNode && (listNode.innerText || listNode.textContent)) || ''
  );
  var count = listText.match(/已勾选\s*(\d+)\s*条订单/);
  if (title !== '提示' || !list || !list.checked || !query || query.checked ||
      !count || Number(count[1]) !== expectedCount)
    return JSON.stringify({{ok:false,error:'DIALOG_SCOPE_CHANGED'}});
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
      confirm[0].getAttribute('aria-disabled') === 'true')
    return JSON.stringify({{ok:false,error:'DIALOG_BUTTONS_NOT_READY'}});

  if (window.__orderReviewAuditObserver)
    window.__orderReviewAuditObserver.disconnect();
  var observation = {{targetDisappearedAt:'',dialogClosedAt:'',messages:[]}};
  var messageSelector = '.el-message,.ivu-message-notice,.ant-message-notice,' +
    '.toast,.toast-message,[role="status"],[role="alert"]';
  function observe(){{
    var currentRows = Array.from(document.querySelectorAll(
      '.module-trade-list-item'
    ));
    if (!currentRows.some(function(row){{
      return systemOrderId(row) === target;
    }}) && !observation.targetDisappearedAt)
      observation.targetDisappearedAt = new Date().toISOString();
    var dialogOpen = Array.from(document.querySelectorAll(
      '[role="dialog"],.el-message-box__wrapper'
    )).some(visible);
    if (!dialogOpen && !observation.dialogClosedAt)
      observation.dialogClosedAt = new Date().toISOString();
    Array.from(document.querySelectorAll(messageSelector)).filter(visible)
      .forEach(function(el){{
        var text = clean(el.innerText || el.textContent).slice(0, 300);
        if (text && observation.messages.indexOf(text) < 0)
          observation.messages.push(text);
      }});
  }}
  var observer = new MutationObserver(observe);
  observer.observe(document.body, {{childList:true,subtree:true}});
  window.__orderReviewAuditObservation = observation;
  window.__orderReviewAuditObserver = observer;
  return center(confirm[0]);
}})()"""


def _network_confirms_split(
    network: dict[str, Any],
    expected_increase: int,
) -> bool:
    result = network.get("result")
    return (
        200 <= int(network.get("status") or 0) < 300
        and (result is True or result == 1)
        and int(network.get("increaseSplitCount") or 0) == expected_increase
    )


def _split_component_action_js(
    target_system_order_id: str,
    component_uid: int,
    expected_rows: list[dict[str, Any]],
    remaining: list[int],
    added_packages: list[list[int]],
    body: str,
    *,
    input_quantities: list[int] | None = None,
) -> str:
    return rf"""(function(){{
  var target = {json.dumps(target_system_order_id, ensure_ascii=False)};
  var expected = {json.dumps(expected_rows, ensure_ascii=False)};
  var remaining = {json.dumps(remaining)};
  var pendingExpected = {json.dumps(added_packages)};
  var inputExpected = {json.dumps(input_quantities)};
  var componentUid = {component_uid};
  { _dialog_helpers_js() }
  var found = currentDialog(target);
  if (!found || found.biz._uid !== componentUid)
    return JSON.stringify({{ok:false,error:'DIALOG_COMPONENT_CHANGED'}});
  var state = validateRows(found.biz, expected);
  if (!state.ok) return JSON.stringify({{ok:false,error:'DIALOG_DATA_MISMATCH'}});
  var actualRemaining = found.biz.tableData.map(function(row){{
    return Number(row.rcCanSplitNum || 0);
  }});
  if (JSON.stringify(actualRemaining) !== JSON.stringify(remaining))
    return JSON.stringify({{ok:false,error:'REMAINING_QUANTITY_CHANGED'}});
  var pending = found.biz.pendingSplitList.map(function(packageRows){{
    var result = Array(expected.length).fill(0);
    packageRows.forEach(function(row){{
      var index = expected.findIndex(function(item, rowIndex){{
        return rowIndex < expected.length &&
          String(row.id || '') === String(item.id || '') &&
          String(row.tid || '') === String(item.tid || '');
      }});
      if (index >= 0) result[index] = Number(row.rcSplitNum || 0);
    }});
    return result;
  }});
  if (JSON.stringify(pending) !== JSON.stringify(pendingExpected))
    return JSON.stringify({{ok:false,error:'PENDING_PACKAGES_CHANGED'}});
  var inputs = Array.from(found.dialog.querySelectorAll(
    '.el-table__body input.el-input__inner'
  ));
  if (inputs.length !== expected.length ||
      !inputs.every(function(input, index){{
        if (inputExpected !== null)
          return remaining[index] === 0 ?
            Number(inputExpected[index] || 0) === 0 && input.disabled :
            String(input.value) === String(inputExpected[index]) && !input.disabled;
        return remaining[index] === 0 ? input.disabled :
          String(input.value) === '0' && !input.disabled;
      }}))
    return JSON.stringify({{ok:false,error:'INPUT_STATE_CHANGED'}});
{body}
}})()"""


def _selected_order_guard_js(target_system_order_id: str, body: str) -> str:
    return rf"""(function(){{
  var expected = {json.dumps(target_system_order_id, ensure_ascii=False)};
  { _common_page_helpers_js() }
  if (document.visibilityState !== 'visible')
    return JSON.stringify({{ok:false,error:'PAGE_NOT_VISIBLE'}});
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var selected = rows.filter(checked);
  if (selected.length !== 1 || systemOrderId(selected[0]) !== expected)
    return JSON.stringify({{ok:false,error:'TARGET_SELECTION_CHANGED'}});
{body}
}})()"""


def _common_page_helpers_js() -> str:
    return r"""
  function clean(value){ return String(value || '').replace(/\s+/g, ' ').trim(); }
  function visible(el){
    if (!el || !el.getBoundingClientRect) return false;
    var rect = el.getBoundingClientRect();
    var style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }
  function systemOrderId(row){
    var values = Array.from(new Set([
      clean(row.getAttribute('uniqueid') || row.dataset.uniqueid),
      clean(row.getAttribute('sid') || row.dataset.sid)
    ].filter(Boolean)));
    return values.length === 1 ? values[0] : '';
  }
  function checked(row){
    return Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"]'
    )).some(function(input){ return input.checked; });
  }
  function sequence(row){
    var values = String(row.innerText || row.textContent || '')
      .split(/\n+/).map(clean).filter(Boolean);
    var value = values.find(function(item){ return /^\d+$/.test(item); }) || '';
    return Number(value || 0);
  }
  function center(el){
    var rect = el.getBoundingClientRect();
    return JSON.stringify({
      ok:true,
      x:rect.left + rect.width / 2,
      y:rect.top + rect.height / 2
    });
  }
"""


def _dialog_helpers_js() -> str:
    return _common_page_helpers_js() + r"""
  function currentDialog(target){
    var dialogs = Array.from(document.querySelectorAll(
      '[role="dialog"].el-dialog[aria-label="混合拆分"]'
    ));
    var matches = dialogs.map(function(dialog){
      var transition = dialog.parentElement && dialog.parentElement.__vue__;
      var elementDialog = transition && transition.$parent;
      var biz = elementDialog && elementDialog.$parent;
      var host = biz && biz.$parent;
      return {dialog:dialog,biz:biz,host:host};
    }).filter(function(item){
      return item.biz && item.host &&
        String(item.host.sid || '') === String(target) &&
        item.biz.visible === true && visible(item.dialog);
    });
    return matches.length === 1 ? matches[0] : null;
  }
  function validateRows(biz, expected){
    var rows = biz && Array.isArray(biz.tableData) ? biz.tableData : [];
    if (rows.length !== expected.length) return {ok:false,rows:[]};
    var result = rows.map(function(row, index){
      var item = expected[index];
      var ids = [row.outerId,row.sysOuterId,row.mainOuterId].map(String);
      var idMatches = !item.id || String(row.id || '') === String(item.id);
      return {
        ok:ids.indexOf(String(item.outerId || '')) >= 0 &&
          String(row.tid || '') === String(item.tid || '') &&
          Number(row.rcNum || row.num || 0) === Number(item.quantity || 0) &&
          idMatches,
        outerId:String(row.outerId || ''),
        tid:String(row.tid || ''),
        id:String(row.id || ''),
        quantity:Number(row.rcNum || row.num || 0)
      };
    });
    return {ok:result.every(function(row){ return row.ok; }),rows:result};
  }
"""


def _expected_dialog_rows(source: SourceSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in source.products:
        details = product.details
        attributes = details.get("rawAttributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        rows.append(
            {
                "outerId": product.merchant_code
                or product.main_merchant_code
                or "",
                "tid": product.platform_order_number,
                "id": str(
                    attributes.get("data-orderid")
                    or attributes.get("data-id")
                    or ""
                ),
                "quantity": product.quantity,
            }
        )
    return rows


def _package_quantities(
    source: SourceSnapshot,
    plan: PackagePlan,
) -> list[list[int]]:
    indexes = {
        product.source_product_id: index
        for index, product in enumerate(source.products)
    }
    result: list[list[int]] = []
    for package in plan.packages:
        quantities = [0] * len(source.products)
        for item in package.items:
            quantities[indexes[item.source_product_id]] = item.quantity
        result.append(quantities)
    return result


def _poll_payload(
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
        sleeper(SPLIT_POLL_INTERVAL_SECONDS)


def _poll_split_result_validation(
    target_id: str,
    source: SourceSnapshot,
    plan: PackagePlan,
    reader: Callable[..., SplitResultObservation],
    validator: Callable[
        [SourceSnapshot, PackagePlan, SplitResultObservation],
        SplitResultValidationReport,
    ],
    evaluator: Callable[[str, str], Any],
    timeout_seconds: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
) -> SplitResultValidationReport:
    """等待前 N 条勾选结果稳定；一旦明细齐全就立即给出最终对账结论。"""
    deadline = monotonic() + timeout_seconds
    while True:
        observation = reader(
            len(plan.packages),
            target_id,
            evaluator=evaluator,
        )
        validation = validator(source, plan, observation)
        if validation.verified or _split_result_validation_is_definitive(validation):
            return validation
        if monotonic() >= deadline:
            return validation
        sleeper(SPLIT_POLL_INTERVAL_SECONDS)


def _split_result_validation_is_definitive(
    validation: SplitResultValidationReport,
) -> bool:
    checks = {check.code: check.passed for check in validation.checks}
    # 前 N 行已经稳定勾选时，reader 已完成本轮真实滚动与逐行读取。
    # 身份或明细仍不完整属于本次核验的安全阻断，不再靠重复整轮滚动等待；
    # 只有加载、行数或位置尚未稳定时才允许继续只读轮询。
    return all(
        checks.get(code, False)
        for code in (
            "CONFIRMATION_UI_CLOSED",
            "SELECTED_RESULT_ROW_COUNT",
            "SELECTED_ROWS_ARE_FIRST_N",
        )
    )


def _poll_audit_dialog(
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
        sleeper(SPLIT_POLL_INTERVAL_SECONDS)


def _poll_audit_result(
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
        sleeper(SPLIT_POLL_INTERVAL_SECONDS)


def _require_payload(payload: Any, code: str, message: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("ok"):
        detail = payload.get("error") if isinstance(payload, dict) else ""
        raise AuditProbeError(code, f"{message}{f'：{detail}' if detail else ''}")
    return payload


def _finish_report(
    execution_id: str,
    started_at: str,
    target_system_order_id: str,
    source: SourceSnapshot,
    confirmation_reference_id: str,
    state: AuditExecutionState,
    steps: list[AuditStep],
    log_store: AuditExecutionLogStore | None,
    split_completed: bool = False,
) -> SplitOrderReport:
    report = SplitOrderReport(
        execution_id=execution_id,
        started_at=started_at,
        finished_at=_utc_now(),
        target_system_order_id=target_system_order_id,
        source_snapshot_id=source.snapshot_id,
        confirmation_reference_id=confirmation_reference_id,
        state=state,
        steps=tuple(steps),
        split_completed=split_completed,
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
