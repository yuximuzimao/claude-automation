from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from . import cdp
from .case_repository import default_case_path
from .erp_reader import (
    build_read_sequence_one_js,
    find_erp_toaudit_target,
    snapshot_from_payload,
)
from .file_lock import exclusive_file_lock
from .order_identity import same_order_signature_key
from .package_plan import SourceSnapshot


AUDIT_PROBE_SCHEMA_VERSION = 2


class AuditExecutionState(StrEnum):
    IDLE = "idle"
    PREFLIGHT_CHECKING = "preflight_checking"
    SELECTING_ORDER = "selecting_order"
    SELECTION_VERIFYING = "selection_verifying"
    OPENING_AUDIT_MENU = "opening_audit_menu"
    AUDIT_DIALOG_VERIFYING = "audit_dialog_verifying"
    SUBMITTING = "submitting"
    RESULT_VERIFYING = "result_verifying"
    SUCCESS = "success"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class AuditProbeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProbeCheck:
    code: str
    label: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class AuditPreflightReport:
    execution_id: str
    started_at: str
    observed_at: str
    target_id: str
    target_system_order_id: str
    source_snapshot_id: str
    confirmation_reference_id: str
    target_package_count: int
    state: AuditExecutionState
    preflight_ready: bool
    checks: tuple[ProbeCheck, ...]
    raw_probe: dict[str, Any]

    @property
    def blockers(self) -> tuple[ProbeCheck, ...]:
        return tuple(check for check in self.checks if check.status == "blocked")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": AUDIT_PROBE_SCHEMA_VERSION,
            "executionId": self.execution_id,
            "startedAt": self.started_at,
            "observedAt": self.observed_at,
            "mode": "preflight",
            "targetId": self.target_id,
            "targetSystemOrderId": self.target_system_order_id,
            "sourceSnapshotId": self.source_snapshot_id,
            "confirmationReferenceId": self.confirmation_reference_id,
            "targetPackageCount": self.target_package_count,
            "state": self.state.value,
            "preflightReady": self.preflight_ready,
            "checks": [check.to_dict() for check in self.checks],
            "stateHistory": [
                {
                    "state": AuditExecutionState.PREFLIGHT_CHECKING.value,
                    "startedAt": self.started_at,
                },
                {
                    "state": self.state.value,
                    "startedAt": self.observed_at,
                },
            ],
            "rawProbe": self.raw_probe,
        }

    def to_log_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("rawProbe", None)
        return payload

    def render_text(self) -> str:
        headline = "审核前检查通过" if self.preflight_ready else "审核前检查已停止"
        lines = [
            headline,
            f"目标系统订单号：{self.target_system_order_id or '未识别'}",
        ]
        icons = {
            "pass": "✓",
            "blocked": "✕",
            "not_observed": "○",
            "info": "·",
        }
        lines.extend(
            f"{icons.get(check.status, '·')} {check.label}：{check.detail}"
            for check in self.checks
        )
        lines.append("本次只做审核前检查：未勾选订单、未打开审核菜单、未点击任何 ERP 业务按钮。")
        return "\n".join(lines)


# 兼容旧调用名；用户界面和新代码统一使用“审核前检查”。
AuditDryRunReport = AuditPreflightReport


def default_audit_log_path(case_path: str | Path | None = None) -> Path:
    source = Path(case_path) if case_path is not None else default_case_path()
    return source.with_name("audit-executions.jsonl")


class AuditExecutionLogStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_audit_log_path()
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def append(self, report: AuditPreflightReport) -> None:
        self.append_payload(report.to_log_dict())

    def append_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        with exclusive_file_lock(self.lock_path):
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            try:
                os.write(descriptor, encoded)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


def build_audit_probe_js(target_system_order_id: str = "") -> str:
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
      style.display !== 'none' && style.visibility !== 'hidden' &&
      style.opacity !== '0';
  }}
  function enabled(el){{
    return !el.disabled && el.getAttribute('aria-disabled') !== 'true' &&
      !el.classList.contains('is-disabled') && !el.classList.contains('disabled');
  }}
  function checked(el){{
    var input = el.matches && el.matches('input[type="checkbox"]')
      ? el : el.querySelector && el.querySelector('input[type="checkbox"]');
    return Boolean(
      (input && input.checked) ||
      el.getAttribute('aria-checked') === 'true' ||
      el.classList.contains('is-checked') ||
      (el.parentElement && el.parentElement.classList.contains('is-checked'))
    );
  }}
  function lines(el){{
    return String((el && (el.innerText || el.textContent)) || '')
      .split(/\n+/).map(clean).filter(Boolean);
  }}
  function seq(row){{
    return lines(row).find(function(value){{ return /^\d+$/.test(value); }}) || '';
  }}
  function systemIdentity(row){{
    var uniqueid = clean(row.getAttribute('uniqueid') || row.dataset.uniqueid);
    var sid = clean(row.getAttribute('sid') || row.dataset.sid);
    var visibleId = '';
    lines(row).some(function(value){{
      var match = value.match(/(?:系统订单号|系统单号)[：:\s]*([A-Za-z0-9_-]{{6,}})/);
      if (match) visibleId = match[1];
      return Boolean(match);
    }});
    var attributeValues = Array.from(new Set([uniqueid, sid].filter(Boolean)));
    var resolved = attributeValues.length === 1 ? attributeValues[0] : '';
    var consistent = Boolean(resolved) && (!visibleId || visibleId === resolved);
    return {{
      uniqueid:uniqueid,
      sid:sid,
      visibleSystemOrderId:visibleId,
      resolved:consistent ? resolved : '',
      consistent:consistent
    }};
  }}
  function checkboxFor(row){{
    var inputs = Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"],input[type="checkbox"]'
    ));
    return Array.from(new Set(inputs));
  }}
  function checkboxVisible(input){{
    return visible(input) || visible(
      input.closest('.area-checkbox') ||
      input.parentElement
    );
  }}
  function optionState(dialog, label){{
    var nodes = Array.from(dialog.querySelectorAll('label,[role="radio"],.el-radio,.ivu-radio-wrapper,li,div'))
      .filter(function(el){{ return clean(el.innerText || el.textContent).indexOf(label) >= 0; }});
    nodes.sort(function(a, b){{ return clean(a.innerText).length - clean(b.innerText).length; }});
    var node = nodes[0] || null;
    var input = node && node.querySelector('input[type="radio"],input[type="checkbox"]');
    return {{
      found:Boolean(node),
      selected:Boolean(node && (
        (input && input.checked) ||
        node.getAttribute('aria-checked') === 'true' ||
        node.classList.contains('is-checked') ||
        (node.querySelector('.is-checked,[aria-checked="true"]'))
      )),
      text:node ? clean(node.innerText || node.textContent) : ''
    }};
  }}

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var rowProbes = rows.map(function(row){{
    var identity = systemIdentity(row);
    var boxes = checkboxFor(row);
    var text = clean(row.innerText || row.textContent);
    return {{
      sequence:seq(row),
      identity:identity,
      checkboxCount:boxes.length,
      checkboxVisibleCount:boxes.filter(checkboxVisible).length,
      checkboxEnabledCount:boxes.filter(enabled).length,
      checkboxCheckedCount:boxes.filter(checked).length,
      pendingTextObserved:text.indexOf('待审核') >= 0
    }};
  }});
  if (!targetSystemOrderId) {{
    var first = rowProbes.find(function(row){{ return row.sequence === '1'; }});
    targetSystemOrderId = first ? first.identity.resolved : '';
  }}
  var targetRows = rowProbes.filter(function(row){{
    return row.identity.resolved === targetSystemOrderId;
  }});
  var selectedRows = rowProbes.filter(function(row){{ return row.checkboxCheckedCount > 0; }});

  var footerCounts = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
    var text = clean(el.innerText || el.textContent);
    if (text.length > 80) return;
    var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
    if (match) footerCounts.push(Number(match[1]));
  }});
  footerCounts = Array.from(new Set(footerCounts));

  var menuContainers = Array.from(document.querySelectorAll(
    '.toolbar-sub_list,[role="menu"],.el-dropdown-menu,.ivu-dropdown-menu,' +
    '.ant-dropdown-menu,.dropdown-menu'
  ));
  var visibleMenus = menuContainers.filter(visible);
  var auditMenuContainers = menuContainers.filter(function(container){{
    return container.querySelector('[data-name="batch_audit"]') &&
      container.querySelector('[data-name="batch_force_audit"]');
  }});
  var visibleAuditMenus = auditMenuContainers.filter(visible);
  function menuItems(containers, text){{
    return containers.reduce(function(result, container){{
      var nodes = Array.from(container.querySelectorAll('li,a,button,[role="menuitem"],span'))
        .filter(function(el){{ return clean(el.innerText || el.textContent) === text; }})
        .map(function(el){{ return el.closest('li,a,button,[role="menuitem"]') || el; }});
      return result + new Set(nodes).size;
    }}, 0);
  }}

  var dialogs = Array.from(document.querySelectorAll(
    '[role="dialog"],.el-dialog__wrapper,.ivu-modal-wrap,.ant-modal-wrap'
  )).filter(visible);
  var dialogProbes = dialogs.map(function(dialog){{
    var text = clean(dialog.innerText || dialog.textContent);
    var listOption = optionState(dialog, '处理列表页勾选的订单');
    var queryOption = optionState(dialog, '处理查询结果中的订单');
    var countMatch = listOption.text.match(/已勾选\s*(\d+)\s*条订单/);
    return {{
      title:clean((dialog.querySelector(
        '.el-dialog__title,.ivu-modal-header,.ant-modal-title,[data-title]'
      ) || {{}}).innerText || ''),
      listOption:listOption,
      queryOption:queryOption,
      selectedCount:countMatch ? Number(countMatch[1]) : null,
      confirmCount:Array.from(dialog.querySelectorAll('button,a')).filter(function(el){{
        return visible(el) && clean(el.innerText || el.textContent) === '确定';
      }}).length,
      cancelCount:Array.from(dialog.querySelectorAll('button,a')).filter(function(el){{
        return visible(el) && clean(el.innerText || el.textContent) === '取消';
      }}).length,
      text:text.slice(0, 500)
    }};
  }});

  var messageSelectors = '.el-message,.ivu-message-notice,.ant-message-notice,.toast,.toast-message,[role="status"],[role="alert"]';
  var messages = Array.from(document.querySelectorAll(messageSelectors))
    .filter(visible).map(function(el){{ return clean(el.innerText || el.textContent); }}).filter(Boolean);
  var loadingSelectors = '.el-loading-mask,.ivu-spin-fix,.ant-spin-spinning,.loading-mask,.trade-loading';
  var loadingCount = Array.from(document.querySelectorAll(loadingSelectors)).filter(visible).length;

  return JSON.stringify({{
    ok:true,
    title:document.title,
    url:location.href,
    targetSystemOrderId:targetSystemOrderId,
    rowCount:rowProbes.length,
    targetRows:targetRows,
    selectedRowCount:selectedRows.length,
    selectedSystemOrderIds:selectedRows.map(function(row){{ return row.identity.resolved; }}),
    footerSelectedCounts:footerCounts,
    toolbarAuditVisibleCount:Array.from(document.querySelectorAll('.toolbar-list-item'))
      .filter(visible)
      .filter(function(el){{
        return el.querySelector('[data-name="batch_audit"]') &&
          el.querySelector('[data-name="batch_force_audit"],[data-name*="force"]');
      }}).length,
    menu:{{
      containerCount:menuContainers.length,
      visibleContainerCount:visibleMenus.length,
      auditContainerCount:auditMenuContainers.length,
      visibleAuditContainerCount:visibleAuditMenus.length,
      ordinaryAuditCount:menuItems(auditMenuContainers, '审核'),
      forceAuditCount:menuItems(auditMenuContainers, '强制审核'),
      visibleOrdinaryAuditCount:menuItems(visibleAuditMenus, '审核'),
      visibleForceAuditCount:menuItems(visibleAuditMenus, '强制审核')
    }},
    dialogs:dialogProbes,
    messages:messages,
    loadingCount:loadingCount
  }});
}})()"""


def probe_audit_page(
    target_id: str,
    target_system_order_id: str = "",
    *,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
) -> dict[str, Any]:
    payload = evaluator(target_id, build_audit_probe_js(target_system_order_id))
    if not isinstance(payload, dict):
        raise AuditProbeError("INVALID_PROBE_PAYLOAD", "ERP 页面返回了无法识别的探测结果")
    if not payload.get("ok"):
        raise AuditProbeError(
            str(payload.get("error") or "PROBE_FAILED"),
            "当前页面不满足审核只读探测条件",
        )
    return payload


def run_audit_preflight(
    *,
    target_system_order_id: str,
    expected_source: SourceSnapshot,
    confirmation_reference_id: str = "",
    target_id: str | None = None,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
    log_store: AuditExecutionLogStore | None = None,
) -> AuditPreflightReport:
    execution_id = f"audit-{uuid4()}"
    started_at = _utc_now()
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise AuditProbeError(
            "TOAUDIT_TARGET_NOT_FOUND",
            "请先把 Chrome 当前标签页切换到快麦 ERP「订单处理 → 待审核订单」",
        )
    if not target_system_order_id:
        raise AuditProbeError("SYSTEM_ORDER_ID_MISSING", "当前订单缺少可靠的系统订单号")

    probe = probe_audit_page(
        target_id,
        target_system_order_id,
        evaluator=evaluator,
    )
    checks = _build_probe_checks(
        probe,
        target_id=target_id,
        target_system_order_id=target_system_order_id,
        expected_source=expected_source,
        evaluator=evaluator,
    )
    preflight_ready = not any(check.status == "blocked" for check in checks)
    report = AuditPreflightReport(
        execution_id=execution_id,
        started_at=started_at,
        observed_at=_utc_now(),
        target_id=target_id,
        target_system_order_id=target_system_order_id,
        source_snapshot_id=expected_source.snapshot_id,
        confirmation_reference_id=confirmation_reference_id,
        target_package_count=1,
        state=(
            AuditExecutionState.IDLE
            if preflight_ready
            else AuditExecutionState.STOPPED
        ),
        preflight_ready=preflight_ready,
        checks=checks,
        raw_probe=probe,
    )
    if log_store is not None:
        log_store.append(report)
    return report


# 保留命令行和外部旧调用兼容；语义已经收窄为“审核开始前的只读检查”。
run_audit_dry_run = run_audit_preflight


def _build_probe_checks(
    probe: dict[str, Any],
    *,
    target_id: str,
    target_system_order_id: str,
    expected_source: SourceSnapshot,
    evaluator: Callable[[str, str], Any],
) -> tuple[ProbeCheck, ...]:
    checks: list[ProbeCheck] = []
    target_rows = probe.get("targetRows") if isinstance(probe.get("targetRows"), list) else []
    checks.append(
        _binary_check(
            "TARGET_ROW_UNIQUE",
            "目标订单定位",
            len(target_rows) == 1,
            f"系统订单号 {target_system_order_id} 唯一命中"
            if len(target_rows) == 1
            else f"命中 {len(target_rows)} 行，必须且只能为 1 行",
        )
    )
    target_row = target_rows[0] if len(target_rows) == 1 else {}
    pending_observed = bool(target_row.get("pendingTextObserved"))
    checks.append(
        _binary_check(
            "ORDER_PENDING_STATE",
            "目标订单待审核状态",
            pending_observed,
            (
                "目标行可见文本包含“待审核”"
                if pending_observed
                else "目标行没有可验证的“待审核”状态"
            ),
        )
    )
    checkbox_ok = (
        target_row.get("checkboxCount") == 1
        and target_row.get("checkboxVisibleCount") == 1
        and target_row.get("checkboxEnabledCount") == 1
        and target_row.get("checkboxCheckedCount") == 0
    )
    checks.append(
        _binary_check(
            "TARGET_CHECKBOX_READY",
            "目标复选框",
            checkbox_ok,
            "唯一、可见、可用且未勾选"
            if checkbox_ok
            else (
                f"总数 {target_row.get('checkboxCount', 0)}，"
                f"可见 {target_row.get('checkboxVisibleCount', 0)}，"
                f"可用 {target_row.get('checkboxEnabledCount', 0)}，"
                f"已选 {target_row.get('checkboxCheckedCount', 0)}"
            ),
        )
    )
    selected_count = int(probe.get("selectedRowCount") or 0)
    footer_counts = probe.get("footerSelectedCounts")
    footer_counts = footer_counts if isinstance(footer_counts, list) else []
    checks.append(
        _binary_check(
            "NO_EXISTING_SELECTION",
            "页面真实勾选",
            selected_count == 0,
            f"真实选中行 {selected_count}，审核前必须为 0",
        )
    )
    checks.append(
        ProbeCheck(
            code="FOOTER_SELECTION_HISTORY",
            label="底部勾选数量",
            status="info",
            detail=_preflight_footer_history_detail(footer_counts),
        )
    )
    loading_count = int(probe.get("loadingCount") or 0)
    checks.append(
        _binary_check(
            "PAGE_NOT_LOADING",
            "页面加载状态",
            loading_count == 0,
            "未发现可见加载遮罩"
            if loading_count == 0
            else f"发现 {loading_count} 个可见加载状态",
        )
    )
    dialogs = probe.get("dialogs") if isinstance(probe.get("dialogs"), list) else []
    checks.append(
        _binary_check(
            "NO_EXISTING_DIALOG",
            "页面现有弹窗",
            len(dialogs) == 0,
            "未发现可见弹窗"
            if not dialogs
            else f"发现 {len(dialogs)} 个可见弹窗，审核前检查已停止",
        )
    )

    fresh_payload = evaluator(target_id, build_read_sequence_one_js())
    snapshot_matches = False
    detail = "序号 1 订单无法只读重读"
    if isinstance(fresh_payload, dict) and fresh_payload.get("ok"):
        fresh_snapshot = snapshot_from_payload(fresh_payload)
        fresh_source = SourceSnapshot.from_order_snapshot(fresh_snapshot)
        identity_matches = fresh_snapshot.system_order_id == target_system_order_id
        expected_signature = same_order_signature_key(expected_source)
        signature_matches = bool(
            expected_signature
            and same_order_signature_key(fresh_source) == expected_signature
        )
        snapshot_matches = (
            fresh_snapshot.is_expanded and identity_matches and signature_matches
        )
        detail = (
            "订单身份、商品与数量和本地确认快照一致"
            if snapshot_matches
            else (
                f"已展开={fresh_snapshot.is_expanded}，"
                f"系统订单号一致={identity_matches}，商品数量一致={signature_matches}"
            )
        )
    checks.append(
        _binary_check(
            "SOURCE_SNAPSHOT_MATCH",
            "确认快照复核",
            snapshot_matches,
            detail,
        )
    )

    toolbar_count = int(probe.get("toolbarAuditVisibleCount") or 0)
    checks.append(
        _binary_check(
            "AUDIT_TOOLBAR_UNIQUE",
            "操作栏普通审核入口",
            toolbar_count == 1,
            "可见入口唯一"
            if toolbar_count == 1
            else f"可见普通“审核”入口 {toolbar_count} 个",
        )
    )

    checks.append(
        ProbeCheck(
            code="TOAST_CONTAINER",
            label="临时消息容器",
            status="info",
            detail=(
                f"当前可见消息 {len(probe.get('messages', []))} 条；"
                "已具备只读扫描结构，提交观察器由执行阶段单独安装"
            ),
        )
    )
    return tuple(checks)


def _binary_check(
    code: str,
    label: str,
    passed: bool,
    detail: str,
) -> ProbeCheck:
    return ProbeCheck(
        code=code,
        label=label,
        status="pass" if passed else "blocked",
        detail=detail,
    )


def _preflight_footer_history_detail(values: list[Any] | tuple[Any, ...]) -> str:
    if not values:
        return "勾选前未显示数量；该区域不参与放行判定"
    return (
        f"勾选前显示 {list(values)}；可能是历史值，不参与放行判定。"
        "单包审核只在完成勾选后核验该数量"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
