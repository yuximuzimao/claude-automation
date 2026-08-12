from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

from . import cdp
from .models import OrderDetailGroup, OrderSnapshot
from .parser import parse_order_product
from .window_position import (
    ChromeActiveTab,
    get_chrome_active_tab,
    get_chrome_front_window_title,
)


TOAUDIT_ROUTE = "#/trade/toaudit/"
TOAUDIT_TITLE = "快麦ERP--待审核订单"
ORDER_SEQUENCE_WHEEL_STEP_PX = 520
ORDER_SEQUENCE_WHEEL_WAIT_SECONDS = 0.18
ORDER_SEQUENCE_MAX_WHEEL_STEPS = 20


class OrderSequenceReadError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SequenceOneIdentityProbe:
    system_order_id: str
    loading_count: int
    visible_dialog_count: int
    selected_row_count: int

    @property
    def safe_to_auto_refresh(self) -> bool:
        return (
            bool(self.system_order_id)
            and self.loading_count == 0
            and self.visible_dialog_count == 0
            and self.selected_row_count == 0
        )


def is_toaudit_tab(tab: ChromeActiveTab | None) -> bool:
    if tab is None:
        return False
    return TOAUDIT_TITLE in tab.title and TOAUDIT_ROUTE in tab.url


def find_erp_toaudit_target(
    targets: list[dict[str, Any]] | None = None,
    active_tab: ChromeActiveTab | None = None,
) -> str:
    active_tab = active_tab if active_tab is not None else get_chrome_active_tab()
    targets = targets if targets is not None else cdp.list_targets()
    if active_tab is None:
        front_window_title = get_chrome_front_window_title()
        if TOAUDIT_TITLE not in front_window_title:
            return ""
        matching = [
            target.get("targetId") or target.get("id") or ""
            for target in targets
            if TOAUDIT_ROUTE in target.get("url", "")
            and TOAUDIT_TITLE in target.get("title", "")
            and (not target.get("type") or target.get("type") == "page")
        ]
        matching = [target_id for target_id in matching if target_id]
        return matching[0] if len(matching) == 1 else ""
    if not is_toaudit_tab(active_tab):
        return ""
    matching = [
        target.get("targetId") or target.get("id") or ""
        for target in targets
        if target.get("url", "") == active_tab.url
        and (not target.get("type") or target.get("type") == "page")
    ]
    matching = [target_id for target_id in matching if target_id]
    return matching[0] if len(matching) == 1 else ""


def resolve_system_order_id(payload: dict[str, Any]) -> str:
    """只在 uniqueid、sid 与可见系统订单号不冲突时返回稳定身份。"""
    dataset = _string_dict(payload.get("rowDataset"))
    attributes = _string_dict(payload.get("rowAttributes"))
    explicit = str(payload.get("visibleSystemOrderId", "")).strip()
    attribute_candidates = [
        attributes.get("uniqueid", "").strip(),
        attributes.get("sid", "").strip(),
        dataset.get("uniqueid", "").strip(),
        dataset.get("sid", "").strip(),
    ]
    unique = tuple(dict.fromkeys(value for value in attribute_candidates if value))
    if len(unique) != 1:
        return ""
    return unique[0] if not explicit or explicit == unique[0] else ""


def build_read_sequence_one_js() -> str:
    return r"""(function(){
  if (location.hash.indexOf('#/trade/toaudit/') !== 0) {
    return JSON.stringify({ok:false,error:'NOT_TOAUDIT_PAGE',title:document.title,url:location.href});
  }
  function visible(el){
    var r = el.getBoundingClientRect();
    var s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }
  function clean(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function lines(s){ return String(s || '').split(/\n+/).map(clean).filter(Boolean); }
  function seq(row){ return lines(row.innerText).find(function(x){ return /^\d+$/.test(x); }) || ''; }
  function dataset(el){ return el ? Object.assign({}, el.dataset || {}) : {}; }
  function ancestorDataset(el, stop){
    var nodes = [];
    var current = el;
    while (current) {
      nodes.push(current);
      if (current === stop) break;
      current = current.parentElement;
    }
    return nodes.reverse().reduce(function(result, node){
      return Object.assign(result, dataset(node));
    }, {});
  }
  function attributes(el){
    var result = {};
    if (!el || !el.attributes) return result;
    Array.from(el.attributes).forEach(function(attr){ result[attr.name] = attr.value; });
    return result;
  }
  function unique(values){
    return Array.from(new Set(values.map(clean).filter(Boolean)));
  }
  function valueAfterLabel(sourceLines, label){
    for (var i = 0; i < sourceLines.length; i += 1) {
      var line = sourceLines[i];
      if (line === label || line === label + '：' || line === label + ':') {
        return clean(sourceLines[i + 1] || '');
      }
      if (line.indexOf(label + '：') === 0 || line.indexOf(label + ':') === 0) {
        return clean(line.slice(label.length + 1));
      }
    }
    return '';
  }
  function extractOrderNumbers(sourceLines){
    var values = [];
    var re = /(?:平台单号|子订单号|平台订单号|订单编号|订单号|交易号)[：:\s]*([A-Za-z0-9_-]{6,})/g;
    sourceLines.forEach(function(line){
      var match;
      while ((match = re.exec(line)) !== null) values.push(match[1]);
      re.lastIndex = 0;
    });
    var platformOrder = valueAfterLabel(sourceLines, '平台单号');
    if (platformOrder) values.push(platformOrder);
    return unique(values);
  }
  function groupKey(group, index){
    return group.platformOrderNumber || group.orderNumbers[0] || ('group-' + (index + 1));
  }
  function visibleSystemOrderId(sourceLines){
    for (var i = 0; i < sourceLines.length; i += 1) {
      var match = sourceLines[i].match(/(?:系统订单号|系统单号)[：:\s]*([A-Za-z0-9_-]{6,})/);
      if (match) return match[1];
    }
    return '';
  }

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var row = rows.find(function(row){ return seq(row)==='1'; });
  if (!row) return JSON.stringify({ok:false,error:'SEQ_ONE_NOT_FOUND',rowCount:rows.length});

  var rowText = row.innerText || row.textContent || '';
  var rowLines = lines(rowText);
  var base = {
    ok:true,
    title:document.title,
    url:location.href,
    rowText:rowText,
    rowLines:rowLines,
    rowDataset:dataset(row),
    rowAttributes:attributes(row),
    visibleSystemOrderId:visibleSystemOrderId(rowLines),
    orderNumbers:extractOrderNumbers(rowLines),
    hasCanMergeMark:row.querySelectorAll('.trade-icon-canmerged,[data-name="trade-icon-canmerged"]').length > 0
  };

  var isExpanded = row.classList.contains('module-trade-list-item-open');
  if (!isExpanded) {
    return JSON.stringify(Object.assign(base, {
      isExpanded:false,
      hasSuiteAction:false,
      groups:[],
      products:[]
    }));
  }

  var scopeNodes = Array.from(row.querySelectorAll('tr.order-temp')).filter(visible);
  var groups = scopeNodes.map(function(scope, index){
    var rawText = scope.innerText || scope.textContent || '';
    var groupLines = lines(rawText);
    var group = {
      index:index,
      rawText:rawText,
      lines:groupLines,
      dataset:dataset(scope),
      attributes:attributes(scope),
      platformOrderNumber:valueAfterLabel(groupLines, '平台单号') || dataset(scope).tid || '',
      orderNumbers:extractOrderNumbers(groupLines),
      productIndexes:[]
    };
    group.key = groupKey(group, index);
    return group;
  });
  var scopeIndexes = new Map(scopeNodes.map(function(scope, index){ return [scope, index]; }));

  function ensureGroup(scope){
    if (scopeIndexes.has(scope)) return scopeIndexes.get(scope);
    var rawText = scope ? (scope.innerText || scope.textContent || '') : '';
    var groupLines = lines(rawText);
    var group = {
      index:groups.length,
      rawText:rawText,
      lines:groupLines,
      dataset:dataset(scope),
      attributes:attributes(scope),
      platformOrderNumber:valueAfterLabel(groupLines, '平台单号') || dataset(scope).tid || '',
      orderNumbers:extractOrderNumbers(groupLines),
      productIndexes:[]
    };
    group.key = groupKey(group, group.index);
    groups.push(group);
    if (scope) scopeIndexes.set(scope, group.index);
    return group.index;
  }

  var itemNodes = Array.from(row.querySelectorAll('.item-snapshot-itemname')).filter(visible);
  var productScopes = itemNodes.length
    ? itemNodes.map(function(item){ return {item:item, scope:item.closest('tr.order-temp') || item}; })
    : scopeNodes.map(function(scope){ return {item:null, scope:scope}; });

  var products = productScopes.map(function(productScope, productIndex){
    var item = productScope.item;
    var scope = productScope.scope;
    var identityNode = item ? (item.closest('[data-numiid],[data-oid],[data-tid],[data-sid],[data-sku-id],[data-skuid]') || scope) : scope;
    var inheritedDataset = item ? ancestorDataset(item, scope) : dataset(scope);
    var sourceGroupIndex = ensureGroup(scope);
    var sourceGroup = groups[sourceGroupIndex];
    sourceGroup.productIndexes.push(productIndex);
    var actionText = Array.from(scope.querySelectorAll('a,button,[data-name]')).map(function(el){
      return clean(el.innerText || el.getAttribute('data-title') || '');
    }).join('\n');
    var quantityNode = scope.querySelector('.module-trade-list-item-price .list-order-num, .module-trade-list-item-price .needNum');
    var productText = item
      ? [item.innerText || item.textContent, quantityNode ? (quantityNode.innerText || quantityNode.textContent) : ''].join('\n')
      : (scope.innerText || scope.textContent || '');
    return {
      sourceGroupIndex:sourceGroupIndex,
      sourceGroupKey:sourceGroup.key,
      platformOrderNumber:sourceGroup.platformOrderNumber,
      dataset:Object.assign({}, dataset(scope), inheritedDataset, dataset(identityNode), dataset(item)),
      attributes:Object.assign({}, attributes(scope), attributes(identityNode), attributes(item)),
      itemDataset:dataset(item),
      itemAttributes:attributes(item),
      identityDataset:dataset(identityNode),
      identityAttributes:attributes(identityNode),
      scopeDataset:dataset(scope),
      scopeAttributes:attributes(scope),
      lines:lines(productText),
      rawText:productText,
      scopeLines:sourceGroup.lines,
      scopeRawText:sourceGroup.rawText,
      hasSuiteAction:/套件明细|套件转单品/.test(actionText)
    };
  });

  var hasSuiteAction = products.some(function(product){ return product.hasSuiteAction; });
  return JSON.stringify(Object.assign(base, {
    isExpanded:true,
    hasSuiteAction:hasSuiteAction,
    groups:groups,
    products:products
  }));
})()"""


def build_read_order_sequence_js(sequence: int) -> str:
    """生成任意页面序号订单的读取脚本，保留序号 1 的成熟解析逻辑。"""
    if sequence < 1:
        raise ValueError("订单序号必须大于 0")
    marker = "seq(row)==='1'"
    script = build_read_sequence_one_js()
    if script.count(marker) != 1:
        raise RuntimeError("ERP 订单读取脚本的序号定位标记已经变化")
    return script.replace(marker, f"seq(row)==='{sequence}'", 1).replace(
        "SEQ_ONE_NOT_FOUND",
        f"SEQ_{sequence}_NOT_FOUND",
        1,
    )


def build_sequence_one_identity_probe_js() -> str:
    return r"""(function(){
  function visible(el){
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    var s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 &&
      s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  }
  function clean(value){ return String(value || '').replace(/\s+/g, ' ').trim(); }
  function lines(value){
    return String(value || '').split(/\n+/).map(clean).filter(Boolean);
  }
  function seq(row){
    return lines(row.innerText || row.textContent)
      .find(function(value){ return /^\d+$/.test(value); }) || '';
  }
  function checked(row){
    return Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"],input[type="checkbox"]'
    )).some(function(input){ return input.checked; });
  }
  if (location.hash.indexOf('#/trade/toaudit/') !== 0 ||
      document.title.indexOf('快麦ERP--待审核订单') < 0) {
    return JSON.stringify({ok:false,error:'NOT_TOAUDIT_PAGE'});
  }
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'))
    .filter(visible);
  var firstRows = rows.filter(function(row){ return seq(row) === '1'; });
  if (firstRows.length !== 1) {
    return JSON.stringify({ok:false,error:'SEQ_ONE_NOT_UNIQUE'});
  }
  var row = firstRows[0];
  var rowLines = lines(row.innerText || row.textContent);
  var visibleId = '';
  rowLines.some(function(value){
    var match = value.match(/(?:系统订单号|系统单号)[：:\s]*([A-Za-z0-9_-]{6,})/);
    if (match) visibleId = match[1];
    return Boolean(match);
  });
  return JSON.stringify({
    ok:true,
    rowAttributes:{
      uniqueid:clean(row.getAttribute('uniqueid') || row.dataset.uniqueid),
      sid:clean(row.getAttribute('sid') || row.dataset.sid)
    },
    visibleSystemOrderId:visibleId,
    loadingCount:Array.from(document.querySelectorAll(
      '.el-loading-mask,.ivu-spin-fix,.ant-spin-spinning,[aria-busy="true"]'
    )).filter(visible).length,
    visibleDialogCount:Array.from(new Set(Array.from(document.querySelectorAll(
      '[role="dialog"],.el-message-box__wrapper'
    )))).filter(visible).length,
    selectedRowCount:rows.filter(checked).length
  });
})()"""


def build_expand_sequence_one_js() -> str:
    return r"""(function(){
  if (location.hash.indexOf('#/trade/toaudit/') !== 0) {
    return JSON.stringify({ok:false,error:'NOT_TOAUDIT_PAGE'});
  }
  function visible(el){
    var r = el.getBoundingClientRect();
    var s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }
  function clean(s){ return String(s || '').replace(/\s+/g, ' ').trim(); }
  function lines(s){ return String(s || '').split(/\n+/).map(clean).filter(Boolean); }
  function seq(row){ return lines(row.innerText).find(function(x){ return /^\d+$/.test(x); }) || ''; }

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item')).filter(visible);
  var row = rows.find(function(row){ return seq(row)==='1'; });
  if (!row) return JSON.stringify({ok:false,error:'SEQ_ONE_NOT_FOUND'});
  if (row.classList.contains('module-trade-list-item-open')) {
    return JSON.stringify({ok:true,expanded:true,clicked:false});
  }

  var trigger = row.querySelector(
    '.trade-plus .trade-expand [data-name="trigger_show_orders"]'
  );
  if (!trigger || !visible(trigger)) {
    return JSON.stringify({ok:false,error:'EXPAND_CONTROL_NOT_FOUND'});
  }
  trigger.click();

  return new Promise(function(resolve){
    var startedAt = Date.now();
    function checkExpanded(){
      var detailsReady = Array.from(
        row.querySelectorAll('tr.order-temp, .item-snapshot-itemname')
      ).some(visible);
      if (row.classList.contains('module-trade-list-item-open') && detailsReady) {
        resolve(JSON.stringify({ok:true,expanded:true,clicked:true}));
        return;
      }
      if (Date.now() - startedAt >= 2000) {
        resolve(JSON.stringify({ok:false,error:'EXPAND_TIMEOUT'}));
        return;
      }
      setTimeout(checkExpanded, 50);
    }
    checkExpanded();
  });
})()"""


def build_expand_order_sequence_js(sequence: int) -> str:
    """生成任意页面序号订单的展开脚本。"""
    if sequence < 1:
        raise ValueError("订单序号必须大于 0")
    marker = "seq(row)==='1'"
    script = build_expand_sequence_one_js()
    if script.count(marker) != 1:
        raise RuntimeError("ERP 订单展开脚本的序号定位标记已经变化")
    return script.replace(marker, f"seq(row)==='{sequence}'", 1).replace(
        "SEQ_ONE_NOT_FOUND",
        f"SEQ_{sequence}_NOT_FOUND",
        1,
    )


def build_order_sequence_view_probe_js(
    sequence: int,
    expected_system_order_id: str,
) -> str:
    """定位目标结果行及其视口坐标；本脚本只读，不滚动页面。"""
    if sequence < 1:
        raise ValueError("订单序号必须大于 0")
    expected_json = json.dumps(expected_system_order_id, ensure_ascii=False)
    return rf"""(function(){{
  var expectedSystemOrderId = {expected_json};
  if (location.hash.indexOf('#/trade/toaudit/') !== 0) {{
    return JSON.stringify({{ok:false,error:'NOT_TOAUDIT_PAGE'}});
  }}
  function visible(el){{
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    var s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 &&
      s.display !== 'none' && s.visibility !== 'hidden';
  }}
  function clean(value){{ return String(value || '').replace(/\s+/g, ' ').trim(); }}
  function lines(value){{
    return String(value || '').split(/\n+/).map(clean).filter(Boolean);
  }}
  function seq(row){{
    return lines(row.innerText || row.textContent)
      .find(function(value){{ return /^\d+$/.test(value); }}) || '';
  }}
  function identity(row){{
    var uniqueid = clean(row.getAttribute('uniqueid') || row.dataset.uniqueid);
    var sid = clean(row.getAttribute('sid') || row.dataset.sid);
    var visibleId = '';
    lines(row.innerText || row.textContent).some(function(value){{
      var match = value.match(/(?:系统订单号|系统单号)[：:\s]*([A-Za-z0-9_-]{{6,}})/);
      if (match) visibleId = match[1];
      return Boolean(match);
    }});
    var values = Array.from(new Set([uniqueid, sid].filter(Boolean)));
    var resolved = values.length === 1 ? values[0] : '';
    return resolved && (!visibleId || visibleId === resolved) ? resolved : '';
  }}
  function checkboxState(row){{
    var inputs = Array.from(row.querySelectorAll(
      'input.J_Checkbox[data-name="check_select_item"],input[type="checkbox"]'
    ));
    return {{
      count:inputs.length,
      checkedCount:inputs.filter(function(input){{ return input.checked; }}).length
    }};
  }}

  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'))
    .filter(visible);
  var mountedSequences = rows.map(function(row){{ return Number(seq(row) || 0); }})
    .filter(function(value){{ return value > 0; }});
  var matches = rows.filter(function(row){{ return seq(row)==='{sequence}'; }});
  if (matches.length > 1) {{
    return JSON.stringify({{ok:false,error:'SEQ_{sequence}_NOT_UNIQUE'}});
  }}
  var viewport = {{width:window.innerWidth, height:window.innerHeight}};
  var fallback = rows.length ? rows[rows.length - 1].getBoundingClientRect() : null;
  var wheelX = Math.max(20, Math.min(
    viewport.width - 20,
    fallback ? fallback.left + fallback.width / 2 : viewport.width / 2
  ));
  var wheelY = Math.max(20, Math.min(viewport.height - 20, viewport.height / 2));
  if (!matches.length) {{
    return JSON.stringify({{
      ok:true,
      found:false,
      mountedSequences:mountedSequences,
      wheelX:wheelX,
      wheelY:wheelY
    }});
  }}
  var row = matches[0];
  var systemOrderId = identity(row);
  if (!systemOrderId) {{
    return JSON.stringify({{ok:false,error:'ROW_IDENTITY_MISSING'}});
  }}
  if (expectedSystemOrderId && systemOrderId !== expectedSystemOrderId) {{
    return JSON.stringify({{ok:false,error:'ROW_IDENTITY_CHANGED'}});
  }}
  var rect = row.getBoundingClientRect();
  var boxes = checkboxState(row);
  var margin = 40;
  return JSON.stringify({{
    ok:true,
    found:true,
    systemOrderId:systemOrderId,
    checkboxCount:boxes.count,
    checkboxCheckedCount:boxes.checkedCount,
    inViewport:rect.top >= margin && rect.bottom <= viewport.height - margin,
    direction:rect.bottom > viewport.height - margin ? 'down' : 'up',
    rect:{{top:rect.top,bottom:rect.bottom,left:rect.left,right:rect.right}},
    mountedSequences:mountedSequences,
    wheelX:Math.max(20, Math.min(viewport.width - 20, rect.left + rect.width / 2)),
    wheelY:wheelY
  }});
}})()"""


def dispatch_mouse_wheel(
    target_id: str,
    x: float,
    y: float,
    delta_y: float,
) -> None:
    """通过 CDP 发送真实滚轮事件，与人工滚动页面的路径一致。"""
    cdp.cdp_call(
        target_id,
        "Input.dispatchMouseEvent",
        {
            "type": "mouseWheel",
            "x": x,
            "y": y,
            "deltaX": 0,
            "deltaY": delta_y,
            "button": "none",
        },
    )


def scroll_order_sequence_into_view(
    sequence: int,
    target_id: str,
    *,
    expected_system_order_id: str,
    evaluator=cdp.eval_js,
    wheel_dispatcher=dispatch_mouse_wheel,
    sleeper=time.sleep,
    max_wheel_steps: int = ORDER_SEQUENCE_MAX_WHEEL_STEPS,
) -> dict[str, Any]:
    """用真实滚轮把指定序号行滚入视口，并在每步后重新核对身份。"""
    probe_js = build_order_sequence_view_probe_js(
        sequence,
        expected_system_order_id,
    )
    last_probe: dict[str, Any] = {}
    for step in range(max_wheel_steps + 1):
        probe = evaluator(target_id, probe_js)
        if not isinstance(probe, dict) or not probe.get("ok"):
            detail = probe.get("error") if isinstance(probe, dict) else ""
            raise RuntimeError(
                f"定位第 {sequence} 行订单失败"
                f"{f'：{detail}' if detail else ''}"
            )
        last_probe = probe
        if probe.get("found") and probe.get("inViewport"):
            return probe
        if step >= max_wheel_steps:
            break
        direction = str(probe.get("direction") or "")
        if not direction:
            mounted = tuple(
                int(value)
                for value in probe.get("mountedSequences", [])
                if isinstance(value, (int, float))
            )
            direction = "up" if mounted and min(mounted) > sequence else "down"
        delta_y = (
            -ORDER_SEQUENCE_WHEEL_STEP_PX
            if direction == "up"
            else ORDER_SEQUENCE_WHEEL_STEP_PX
        )
        wheel_dispatcher(
            target_id,
            float(probe.get("wheelX") or 20),
            float(probe.get("wheelY") or 20),
            float(delta_y),
        )
        sleeper(ORDER_SEQUENCE_WHEEL_WAIT_SECONDS)
    mounted = last_probe.get("mountedSequences", [])
    raise OrderSequenceReadError(
        f"SEQ_{sequence}_NOT_VISIBLE",
        f"滚动后仍未看到第 {sequence} 行订单；当前挂载序号 {mounted}",
    )


def read_order_at_sequence(
    sequence: int,
    target_id: str | None = None,
    *,
    expected_system_order_id: str = "",
    expand_if_needed: bool = True,
    evaluator=cdp.eval_js,
) -> OrderSnapshot:
    """读取指定序号的有效订单行；仅在需要时展开一次。"""
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise RuntimeError("请先把 Chrome 当前标签页切换到快麦 ERP「订单处理 → 待审核订单」")
    read_js = build_read_order_sequence_js(sequence)
    payload = evaluator(target_id, read_js)
    if not isinstance(payload, dict):
        raise RuntimeError("ERP 页面返回了无法识别的数据")
    if not payload.get("ok"):
        if payload.get("error") == "NOT_TOAUDIT_PAGE":
            raise RuntimeError("当前标签页不是快麦 ERP「订单处理 → 待审核订单」")
        code = str(payload.get("error") or "ORDER_SEQUENCE_READ_FAILED")
        raise OrderSequenceReadError(
            code,
            code if payload.get("error") else f"读取 ERP 第 {sequence} 行订单失败",
        )

    observed_system_order_id = resolve_system_order_id(payload)
    if (
        expected_system_order_id
        and observed_system_order_id != expected_system_order_id
    ):
        raise RuntimeError(f"当前第 {sequence} 行订单在展开前发生变化，已停止读取")
    if not payload.get("isExpanded") and expand_if_needed:
        expanded = evaluator(
            target_id,
            build_expand_order_sequence_js(sequence),
        )
        if not isinstance(expanded, dict) or not expanded.get("expanded"):
            detail = expanded.get("error") if isinstance(expanded, dict) else ""
            raise RuntimeError(
                f"展开第 {sequence} 行订单失败"
                f"{f'：{detail}' if detail else ''}"
            )
        payload = evaluator(target_id, read_js)
        if not isinstance(payload, dict) or not payload.get("ok"):
            code = (
                str(payload.get("error") or "ORDER_SEQUENCE_READ_FAILED")
                if isinstance(payload, dict)
                else "INVALID_PROBE_PAYLOAD"
            )
            raise OrderSequenceReadError(
                code,
                f"展开第 {sequence} 行订单后读取失败：{code}",
            )
        if not payload.get("isExpanded"):
            raise RuntimeError(f"第 {sequence} 行订单展开后没有完整商品明细")
        expanded_system_order_id = resolve_system_order_id(payload)
        if (
            expected_system_order_id
            and expanded_system_order_id != expected_system_order_id
        ):
            raise RuntimeError(
                f"展开第 {sequence} 行订单后目标发生变化，已停止读取"
            )
    return snapshot_from_payload(payload)


def read_sequence_one_order(
    target_id: str | None = None,
    *,
    expected_system_order_id: str = "",
    expand_if_needed: bool = True,
) -> OrderSnapshot:
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise RuntimeError("请先把 Chrome 当前标签页切换到快麦 ERP「订单处理 → 待审核订单」")
    payload = cdp.eval_js(target_id, build_read_sequence_one_js())
    if not isinstance(payload, dict):
        raise RuntimeError("ERP 页面返回了无法识别的数据")
    if not payload.get("ok"):
        if payload.get("error") == "NOT_TOAUDIT_PAGE":
            raise RuntimeError("当前标签页不是快麦 ERP「订单处理 → 待审核订单」")
        raise RuntimeError(payload.get("error") or "读取 ERP 订单失败")
    observed_system_order_id = resolve_system_order_id(payload)
    if (
        expected_system_order_id
        and observed_system_order_id != expected_system_order_id
    ):
        raise RuntimeError("当前第 1 单在展开前再次变化，已停止自动读取")
    if not payload.get("isExpanded") and expand_if_needed:
        expanded = cdp.eval_js(target_id, build_expand_sequence_one_js())
        if isinstance(expanded, dict) and expanded.get("expanded"):
            payload = cdp.eval_js(target_id, build_read_sequence_one_js())
            if not isinstance(payload, dict) or not payload.get("ok"):
                raise RuntimeError("展开订单后读取 ERP 订单失败")
    return snapshot_from_payload(payload)


def read_sequence_one_order_if_matches(
    expected_system_order_id: str,
) -> OrderSnapshot:
    return read_sequence_one_order(
        expected_system_order_id=expected_system_order_id,
        expand_if_needed=True,
    )


def read_sequence_one_order_without_expand() -> OrderSnapshot:
    return read_sequence_one_order(expand_if_needed=False)


def read_sequence_one_identity(
    target_id: str | None = None,
) -> SequenceOneIdentityProbe:
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise RuntimeError("当前前台不是快麦 ERP 待审核页面")
    payload = cdp.eval_js(target_id, build_sequence_one_identity_probe_js())
    if not isinstance(payload, dict) or not payload.get("ok"):
        detail = payload.get("error") if isinstance(payload, dict) else ""
        raise RuntimeError(detail or "读取当前订单身份失败")
    return SequenceOneIdentityProbe(
        system_order_id=resolve_system_order_id(payload),
        loading_count=int(payload.get("loadingCount") or 0),
        visible_dialog_count=int(payload.get("visibleDialogCount") or 0),
        selected_row_count=int(payload.get("selectedRowCount") or 0),
    )


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _int_tuple(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return tuple(result)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def snapshot_from_payload(payload: dict[str, Any]) -> OrderSnapshot:
    product_payloads = payload.get("products", [])
    products = [
        parse_order_product(
            product.get("lines", []),
            product.get("dataset", {}),
            order_lines=product.get("scopeLines", []),
            platform_order_number=str(product.get("platformOrderNumber", "")),
            attributes=product.get("attributes", {}),
            raw_text=str(product.get("scopeRawText") or product.get("rawText", "")),
            source_group_index=_optional_int(product.get("sourceGroupIndex")),
            source_group_key=str(product.get("sourceGroupKey", "")),
        )
        for product in product_payloads
        if isinstance(product, dict)
    ]

    groups = [
        OrderDetailGroup(
            index=int(group.get("index", index)),
            key=str(group.get("key", f"group-{index + 1}")),
            order_numbers=_string_tuple(group.get("orderNumbers")),
            product_indexes=_int_tuple(group.get("productIndexes")),
            dataset=_string_dict(group.get("dataset")),
            attributes=_string_dict(group.get("attributes")),
            raw_lines=_string_tuple(group.get("lines")),
            raw_text=str(group.get("rawText", "")),
        )
        for index, group in enumerate(payload.get("groups", []))
        if isinstance(group, dict)
    ]

    return OrderSnapshot(
        is_expanded=bool(payload.get("isExpanded")),
        system_order_id=resolve_system_order_id(payload),
        products=products,
        groups=groups,
        order_numbers=_string_tuple(payload.get("orderNumbers")),
        has_can_merge_mark=bool(payload.get("hasCanMergeMark")),
        has_suite_action=bool(payload.get("hasSuiteAction")),
        source_title=str(payload.get("title", "")),
        source_url=str(payload.get("url", "")),
        raw_lines=_string_tuple(payload.get("rowLines")),
        raw_dataset=_string_dict(payload.get("rowDataset")),
        raw_attributes=_string_dict(payload.get("rowAttributes")),
        raw_text=str(payload.get("rowText", "")),
        raw_payload=dict(payload),
    )
