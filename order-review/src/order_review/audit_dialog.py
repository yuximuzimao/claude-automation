from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable

from . import cdp
from .audit_probe import AuditProbeError, ProbeCheck


@dataclass(frozen=True)
class AuditDialogProbe:
    visible_dialog_count: int
    title: str
    list_option_found: bool
    list_option_selected: bool
    list_option_text: str
    list_option_value: str
    query_option_found: bool
    query_option_selected: bool
    query_option_text: str
    query_option_value: str
    list_selected_count: int | None
    query_result_count: int | None
    selected_row_count: int
    selected_system_order_ids: tuple[str, ...]
    footer_selected_counts: tuple[int, ...]
    confirm_button_count: int
    cancel_button_count: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AuditDialogProbe:
        dialogs = payload.get("dialogs")
        dialogs = dialogs if isinstance(dialogs, list) else []
        dialog = dialogs[0] if len(dialogs) == 1 and isinstance(dialogs[0], dict) else {}
        list_option = (
            dialog.get("listOption")
            if isinstance(dialog.get("listOption"), dict)
            else {}
        )
        query_option = (
            dialog.get("queryOption")
            if isinstance(dialog.get("queryOption"), dict)
            else {}
        )
        return cls(
            visible_dialog_count=len(dialogs),
            title=str(dialog.get("title") or ""),
            list_option_found=bool(list_option.get("found")),
            list_option_selected=bool(list_option.get("selected")),
            list_option_text=str(list_option.get("text") or ""),
            list_option_value=str(list_option.get("value") or ""),
            query_option_found=bool(query_option.get("found")),
            query_option_selected=bool(query_option.get("selected")),
            query_option_text=str(query_option.get("text") or ""),
            query_option_value=str(query_option.get("value") or ""),
            list_selected_count=_optional_int(dialog.get("listSelectedCount")),
            query_result_count=_optional_int(dialog.get("queryResultCount")),
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
            confirm_button_count=_int_or_zero(dialog.get("confirmButtonCount")),
            cancel_button_count=_int_or_zero(dialog.get("cancelButtonCount")),
        )


@dataclass(frozen=True)
class AuditDialogValidation:
    target_system_order_id: str
    target_package_count: int
    probe: AuditDialogProbe
    checks: tuple[ProbeCheck, ...]

    @property
    def ready_to_submit(self) -> bool:
        return not any(check.status == "blocked" for check in self.checks)

    @property
    def blockers(self) -> tuple[ProbeCheck, ...]:
        return tuple(check for check in self.checks if check.status == "blocked")

    def render_text(self) -> str:
        if self.probe.query_option_selected:
            affected = (
                f"当前查询到的 {self.probe.query_result_count} 条订单"
                if self.probe.query_result_count is not None
                else "当前查询结果中的全部订单"
            )
            return (
                "已停止：弹窗当前选择“处理查询结果中的订单”，"
                f"可能影响{affected}。未点击确定。"
            )
        if self.ready_to_submit:
            return (
                "弹窗安全核对通过：范围仅限列表页勾选的 1 条目标订单。"
                "这只是允许进入下一道确认关卡，本次没有点击确定。"
            )
        details = "；".join(check.detail for check in self.blockers)
        return f"已停止：弹窗状态不能证明只会处理当前 1 条目标订单。{details}。未点击确定。"


def validate_audit_dialog(
    probe: AuditDialogProbe,
    *,
    target_system_order_id: str,
    target_package_count: int = 1,
) -> AuditDialogValidation:
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
            "DIALOG_UNIQUE",
            "审核弹窗",
            probe.visible_dialog_count == 1,
            "唯一可见弹窗"
            if probe.visible_dialog_count == 1
            else f"可见弹窗 {probe.visible_dialog_count} 个，必须且只能为 1 个",
        ),
        _check(
            "DIALOG_TITLE",
            "弹窗标题",
            probe.title == "提示",
            "标题为“提示”" if probe.title == "提示" else f"标题为“{probe.title or '空'}”",
        ),
        _check(
            "LIST_SCOPE_SELECTED",
            "列表页勾选范围",
            (
                probe.list_option_found
                and probe.list_option_selected
                and probe.list_option_value == "1"
            ),
            "已选择“处理列表页勾选的订单”"
            if probe.list_option_selected
            else "未选择“处理列表页勾选的订单”",
        ),
        _check(
            "QUERY_SCOPE_NOT_SELECTED",
            "查询结果范围",
            (
                probe.query_option_found
                and not probe.query_option_selected
                and probe.query_option_value == "2"
            ),
            "未选择“处理查询结果中的订单”"
            if not probe.query_option_selected
            else "危险：已选择“处理查询结果中的订单”",
        ),
        _check(
            "LIST_SELECTED_COUNT",
            "弹窗勾选数量",
            probe.list_selected_count == 1,
            f"弹窗显示已勾选 {probe.list_selected_count} 条订单"
            if probe.list_selected_count is not None
            else "弹窗没有显示已勾选数量",
        ),
        _check(
            "TARGET_SELECTION",
            "页面目标订单",
            (
                probe.selected_row_count == 1
                and probe.selected_system_order_ids == (target_system_order_id,)
            ),
            (
                f"页面仅选中目标订单 {target_system_order_id}"
                if (
                    probe.selected_row_count == 1
                    and probe.selected_system_order_ids == (target_system_order_id,)
                )
                else (
                    f"选中行 {probe.selected_row_count}，"
                    f"系统订单号 {list(probe.selected_system_order_ids)}"
                )
            ),
        ),
        _check(
            "FOOTER_MULTIPLE_ORDER_GUARD",
            "底部多选反向保护",
            _single_order_footer_safe(probe.footer_selected_counts),
            (
                f"底部计数 {list(probe.footer_selected_counts)}；"
                "只用于发现 2 或更大的危险值，不作为正向证明"
            ),
        ),
        _check(
            "CONFIRM_BUTTON_UNIQUE",
            "确定按钮",
            probe.confirm_button_count == 1,
            f"可见确定按钮 {probe.confirm_button_count} 个",
        ),
        _check(
            "CANCEL_BUTTON_UNIQUE",
            "取消按钮",
            probe.cancel_button_count == 1,
            f"可见取消按钮 {probe.cancel_button_count} 个",
        ),
    )
    return AuditDialogValidation(
        target_system_order_id=target_system_order_id,
        target_package_count=target_package_count,
        probe=probe,
        checks=checks,
    )


def build_audit_dialog_probe_js(target_system_order_id: str) -> str:
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
  function option(dialog, value, label){{
    var inputs = Array.from(dialog.querySelectorAll(
      'input.el-radio__original[type="radio"],input[type="radio"]'
    ));
    var input = inputs.find(function(item){{ return item.value === value; }}) || null;
    var node = input && input.closest('label.el-radio,[role="radio"],label');
    if (!node) {{
      node = Array.from(dialog.querySelectorAll('label.el-radio,[role="radio"],label'))
        .find(function(item){{ return clean(item.innerText).indexOf(label) >= 0; }}) || null;
      input = node && node.querySelector('input[type="radio"]');
    }}
    return {{
      found:Boolean(node && input),
      selected:Boolean(input && input.checked),
      value:input ? clean(input.value) : '',
      text:node ? clean(node.innerText || node.textContent) : ''
    }};
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

  var dialogs = Array.from(new Set(Array.from(document.querySelectorAll(
    '[role="dialog"].el-message-box__wrapper,.el-message-box__wrapper[role="dialog"],' +
    '[role="dialog"]'
  )))).filter(visible);
  var dialogProbes = dialogs.map(function(dialog){{
    var listOption = option(dialog, '1', '处理列表页勾选的订单');
    var queryOption = option(dialog, '2', '处理查询结果中的订单');
    var listMatch = listOption.text.match(/已勾选\s*(\d+)\s*条订单/);
    var queryMatch = queryOption.text.match(/共查询\s*(\d+)\s*条订单/);
    var buttons = Array.from(dialog.querySelectorAll(
      '.el-message-box__btns button,button'
    )).filter(visible);
    return {{
      title:clean((dialog.querySelector('.el-message-box__title') || {{}}).innerText || ''),
      listOption:listOption,
      queryOption:queryOption,
      listSelectedCount:listMatch ? Number(listMatch[1]) : null,
      queryResultCount:queryMatch ? Number(queryMatch[1]) : null,
      confirmButtonCount:buttons.filter(function(button){{
        return clean(button.innerText || button.textContent) === '确定';
      }}).length,
      cancelButtonCount:buttons.filter(function(button){{
        return clean(button.innerText || button.textContent) === '取消';
      }}).length
    }};
  }});

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var selectedRows = rows.filter(checked);
  var footerCounts = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach(function(el){{
    var text = clean(el.innerText || el.textContent);
    if (text.length > 80) return;
    var match = text.match(/已勾选[：:\s\S]*?订单数[：:\s]*(\d+)/);
    if (match) footerCounts.push(Number(match[1]));
  }});
  return JSON.stringify({{
    ok:true,
    targetSystemOrderId:targetSystemOrderId,
    dialogs:dialogProbes,
    selectedRowCount:selectedRows.length,
    selectedSystemOrderIds:selectedRows.map(systemOrderId),
    footerSelectedCounts:Array.from(new Set(footerCounts))
  }});
}})()"""


def probe_and_validate_audit_dialog(
    target_id: str,
    *,
    target_system_order_id: str,
    target_package_count: int = 1,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
) -> AuditDialogValidation:
    payload = evaluator(
        target_id,
        build_audit_dialog_probe_js(target_system_order_id),
    )
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise AuditProbeError(
            "INVALID_AUDIT_DIALOG_PAYLOAD",
            "当前审核弹窗返回了无法识别的只读核对结果",
        )
    return validate_audit_dialog(
        AuditDialogProbe.from_payload(payload),
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


def _single_order_footer_safe(values: tuple[int, ...]) -> bool:
    return all(0 <= value <= 1 for value in values)
