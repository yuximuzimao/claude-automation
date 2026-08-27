from __future__ import annotations

import time
from typing import Any, Callable

from . import cdp
from .erp_reader import (
    OrderSequenceReadError,
    dispatch_mouse_wheel,
    find_erp_toaudit_target,
    read_order_at_sequence,
    scroll_order_sequence_into_view,
)
from .package_plan import SourceSnapshot
from .split_result import SplitResultObservation, SplitResultRow


SPLIT_RESULT_SETTLE_SECONDS = 0.1
SPLIT_RESULT_EXPANDED_SETTLE_SECONDS = 0.6


class SplitResultProbeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_split_result_selection_probe_js() -> str:
    """只读扫描有效顶层订单行及其真实勾选状态。"""
    return r"""(function(){
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0) {
    return JSON.stringify({ok:false,error:'NOT_TOAUDIT_PAGE'});
  }
  function visible(el){
    if (!el || !el.getBoundingClientRect) return false;
    var rect = el.getBoundingClientRect();
    var style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      style.opacity !== '0';
  }
  function clean(value){ return String(value || '').replace(/\s+/g, ' ').trim(); }
  function lines(value){
    return String(value || '').split(/\n+/).map(clean).filter(Boolean);
  }
  function sequence(row){
    return lines(row.innerText || row.textContent)
      .find(function(value){ return /^\d+$/.test(value); }) || '';
  }
  function checkboxState(row){
    var inputs = Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"],input[type="checkbox"]'
    ));
    return {
      count:inputs.length,
      checkedCount:inputs.filter(function(input){ return input.checked; }).length
    };
  }
  function systemIdentity(row){
    var uniqueid = clean(row.getAttribute('uniqueid') || row.dataset.uniqueid);
    var sid = clean(row.getAttribute('sid') || row.dataset.sid);
    var visibleId = '';
    lines(row.innerText || row.textContent).some(function(value){
      var match = value.match(/(?:系统订单号|系统单号)[：:\s]*([A-Za-z0-9_-]{6,})/);
      if (match) visibleId = match[1];
      return Boolean(match);
    });
    var values = Array.from(new Set([uniqueid, sid].filter(Boolean)));
    var resolved = values.length === 1 ? values[0] : '';
    return {
      uniqueid:uniqueid,
      sid:sid,
      visibleSystemOrderId:visibleId,
      resolved:resolved && (!visibleId || visibleId === resolved) ? resolved : ''
    };
  }

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'))
    .filter(visible)
    .map(function(row){
      var boxes = checkboxState(row);
      return {
        sequence:Number(sequence(row) || 0),
        systemOrderId:systemIdentity(row).resolved,
        checkboxCount:boxes.count,
        checkboxCheckedCount:boxes.checkedCount,
        rowSelectedClass:row.classList.contains('module-trade-list-item-selected'),
        expanded:row.classList.contains('module-trade-list-item-open'),
        platformOrderNumbers:clean(row.getAttribute('tids') || '')
          .split(',').map(clean).filter(Boolean)
      };
    })
    .filter(function(row){ return row.sequence > 0; })
    .sort(function(left, right){ return left.sequence - right.sequence; });

  return JSON.stringify({
    ok:true,
    title:document.title,
    url:location.href,
    loadingCount:Array.from(document.querySelectorAll(
      '.el-loading-mask,.ivu-spin-fix,.ant-spin-spinning,[aria-busy="true"]'
    )).filter(visible).length,
    visibleDialogCount:Array.from(new Set(Array.from(document.querySelectorAll(
      '[role="dialog"],.el-dialog__wrapper,.el-message-box__wrapper'
    )))).filter(visible).length,
    rows:rows
  });
})()"""


def probe_split_result_selection(
    target_id: str,
    *,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
) -> dict[str, Any]:
    payload = evaluator(target_id, build_split_result_selection_probe_js())
    if not isinstance(payload, dict):
        raise SplitResultProbeError(
            "INVALID_PROBE_PAYLOAD",
            "ERP 页面返回了无法识别的拆分结果",
        )
    if not payload.get("ok"):
        raise SplitResultProbeError(
            str(payload.get("error") or "PROBE_FAILED"),
            "当前页面不满足拆分结果读取条件",
        )
    return payload


def read_split_result_observation(
    target_package_count: int,
    target_id: str | None = None,
    *,
    evaluator: Callable[[str, str], Any] = cdp.eval_js,
    wheel_dispatcher: Callable[[str, float, float, float], None] = (
        dispatch_mouse_wheel
    ),
    sleeper: Callable[[float], None] = time.sleep,
) -> SplitResultObservation:
    """读取前 N 条勾选结果行，并展开商品明细供纯逻辑验证器比较。"""
    if target_package_count < 2:
        raise ValueError("拆分结果至少需要 2 个目标包裹")
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise SplitResultProbeError(
            "TOAUDIT_TARGET_NOT_FOUND",
            "请先把 Chrome 当前标签页切换到快麦 ERP「订单处理 → 待审核订单」",
        )

    initial = _discover_target_selection_rows(
        target_package_count,
        target_id,
        evaluator=evaluator,
        wheel_dispatcher=wheel_dispatcher,
        sleeper=sleeper,
    )
    initial_rows = _row_payloads(initial)
    selected = tuple(
        row
        for row in initial_rows
        if int(row.get("checkboxCheckedCount") or 0) > 0
    )
    expected_sequences = tuple(range(1, target_package_count + 1))
    selected_sequences = tuple(int(row.get("sequence") or 0) for row in selected)

    sources_by_sequence: dict[int, SourceSnapshot] = {}
    verified_selected_sequences: set[int] = set()
    stable_enough_to_read = (
        int(initial.get("loadingCount") or 0) == 0
        and int(initial.get("visibleDialogCount") or 0) == 0
        and len(selected) == target_package_count
        and selected_sequences == expected_sequences
        and all(str(row.get("systemOrderId") or "") for row in selected)
    )
    if stable_enough_to_read:
        for row in selected:
            sequence = int(row["sequence"])
            source: SourceSnapshot | None = None
            for attempt in range(2):
                try:
                    positioned = scroll_order_sequence_into_view(
                        sequence,
                        target_id,
                        expected_system_order_id=str(row["systemOrderId"]),
                        evaluator=evaluator,
                        wheel_dispatcher=wheel_dispatcher,
                        sleeper=sleeper,
                    )
                    if (
                        int(positioned.get("checkboxCount") or 0) != 1
                        or int(positioned.get("checkboxCheckedCount") or 0) != 1
                    ):
                        raise SplitResultProbeError(
                            "TARGET_SELECTION_CHANGED",
                            f"滚动到第 {sequence} 行后，该结果行已不再保持唯一勾选",
                        )
                    source = SourceSnapshot.from_order_snapshot(
                        read_order_at_sequence(
                            sequence,
                            target_id,
                            expected_system_order_id=str(row["systemOrderId"]),
                            expand_if_needed=True,
                            evaluator=evaluator,
                            post_expand_wait_seconds=(
                                SPLIT_RESULT_EXPANDED_SETTLE_SECONDS
                            ),
                            sleeper=sleeper,
                        )
                    )
                    break
                except OrderSequenceReadError as exc:
                    if exc.code not in {
                        f"SEQ_{sequence}_NOT_FOUND",
                        f"SEQ_{sequence}_NOT_UNIQUE",
                        f"SEQ_{sequence}_NOT_VISIBLE",
                    }:
                        raise
                    if attempt == 0:
                        # 结果行展开会让虚拟列表原地重排；只复核当前行一次，
                        # 不回到上层重新执行整轮上下滚动。
                        sleeper(SPLIT_RESULT_SETTLE_SECONDS)
                        continue
                break
            if source is None:
                break
            verified_selected_sequences.add(sequence)
            sources_by_sequence[sequence] = source

        if verified_selected_sequences:
            first_row = selected[0]
            returned = scroll_order_sequence_into_view(
                1,
                target_id,
                expected_system_order_id=str(first_row["systemOrderId"]),
                evaluator=evaluator,
                wheel_dispatcher=wheel_dispatcher,
                sleeper=sleeper,
            )
            if (
                int(returned.get("checkboxCount") or 0) != 1
                or int(returned.get("checkboxCheckedCount") or 0) != 1
            ):
                raise SplitResultProbeError(
                    "FIRST_RESULT_SELECTION_CHANGED",
                    "滚回第 1 行后，该结果行已不再保持唯一勾选",
                )
            sleeper(SPLIT_RESULT_SETTLE_SECONDS)

    final = probe_split_result_selection(target_id, evaluator=evaluator)
    final_rows = _row_payloads(final)
    if stable_enough_to_read:
        # 真实滚动到后续行后，虚拟列表可能卸载已核对的前序行。
        # 保留逐行滚动时取得的勾选证据，同时把最终可见的新行并入，
        # 以便额外勾选仍能阻断。
        combined = {
            int(row.get("sequence") or 0): row
            for row in initial_rows
            if int(row.get("sequence") or 0) > 0
        }
        combined.update(
            {
                int(row.get("sequence") or 0): row
                for row in final_rows
                if int(row.get("sequence") or 0) > 0
            }
        )
        final_by_sequence = {
            int(row.get("sequence") or 0): row for row in final_rows
        }
        for sequence in verified_selected_sequences:
            if sequence not in final_by_sequence:
                retained = dict(combined[sequence])
                retained["checkboxCheckedCount"] = 1
                combined[sequence] = retained
        final_rows = tuple(combined[key] for key in sorted(combined))
    rows = tuple(
        SplitResultRow(
            sequence=int(row.get("sequence") or 0),
            selected=int(row.get("checkboxCheckedCount") or 0) > 0,
            source=sources_by_sequence.get(int(row.get("sequence") or 0)),
        )
        for row in final_rows
    )
    return SplitResultObservation(
        loading_count=int(final.get("loadingCount") or 0),
        visible_dialog_count=int(final.get("visibleDialogCount") or 0),
        rows=rows,
    )


def _row_payloads(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return ()
    return tuple(row for row in rows if isinstance(row, dict))


def _discover_target_selection_rows(
    target_package_count: int,
    target_id: str,
    *,
    evaluator: Callable[[str, str], Any],
    wheel_dispatcher: Callable[[str, float, float, float], None],
    sleeper: Callable[[float], None],
) -> dict[str, Any]:
    """滚动收集虚拟列表前 N 行的身份和勾选状态，并回到第 1 行。"""
    initial = probe_split_result_selection(target_id, evaluator=evaluator)
    initial_rows = _row_payloads(initial)
    target_rows = tuple(
        row
        for row in initial_rows
        if 1 <= int(row.get("sequence") or 0) <= target_package_count
    )
    mounted_sequences = tuple(
        int(row.get("sequence") or 0) for row in target_rows
    )
    selected_sequences = tuple(
        int(row.get("sequence") or 0)
        for row in target_rows
        if int(row.get("checkboxCheckedCount") or 0) > 0
    )
    first_row = next(
        (
            row
            for row in target_rows
            if int(row.get("sequence") or 0) == 1
        ),
        None,
    )
    first_system_order_id = (
        str(first_row.get("systemOrderId") or "") if first_row else ""
    )

    safe_prefix = (
        int(initial.get("loadingCount") or 0) == 0
        and int(initial.get("visibleDialogCount") or 0) == 0
        and bool(first_system_order_id)
        and mounted_sequences
        == tuple(range(1, len(mounted_sequences) + 1))
        and selected_sequences == mounted_sequences
        and all(
            int(row.get("checkboxCount") or 0) == 1
            and int(row.get("checkboxCheckedCount") or 0) == 1
            and str(row.get("systemOrderId") or "")
            for row in target_rows
        )
    )
    if not safe_prefix or len(mounted_sequences) >= target_package_count:
        return initial

    combined = {
        int(row.get("sequence") or 0): row
        for row in initial_rows
        if int(row.get("sequence") or 0) > 0
    }
    try:
        for sequence in range(len(mounted_sequences) + 1, target_package_count + 1):
            positioned = scroll_order_sequence_into_view(
                sequence,
                target_id,
                expected_system_order_id="",
                evaluator=evaluator,
                wheel_dispatcher=wheel_dispatcher,
                sleeper=sleeper,
            )
            if (
                not str(positioned.get("systemOrderId") or "")
                or int(positioned.get("checkboxCount") or 0) != 1
                or int(positioned.get("checkboxCheckedCount") or 0) != 1
            ):
                break
            observed = probe_split_result_selection(
                target_id,
                evaluator=evaluator,
            )
            combined.update(
                {
                    int(row.get("sequence") or 0): row
                    for row in _row_payloads(observed)
                    if int(row.get("sequence") or 0) > 0
                }
            )
    finally:
        returned = scroll_order_sequence_into_view(
            1,
            target_id,
            expected_system_order_id=first_system_order_id,
            evaluator=evaluator,
            wheel_dispatcher=wheel_dispatcher,
            sleeper=sleeper,
        )
        if (
            int(returned.get("checkboxCount") or 0) != 1
            or int(returned.get("checkboxCheckedCount") or 0) != 1
        ):
            raise SplitResultProbeError(
                "FIRST_RESULT_SELECTION_CHANGED",
                "滚回第 1 行后，该结果行已不再保持唯一勾选",
            )
        sleeper(SPLIT_RESULT_SETTLE_SECONDS)

    final = probe_split_result_selection(target_id, evaluator=evaluator)
    combined.update(
        {
            int(row.get("sequence") or 0): row
            for row in _row_payloads(final)
            if int(row.get("sequence") or 0) > 0
        }
    )
    final["rows"] = [combined[key] for key in sorted(combined)]
    return final
