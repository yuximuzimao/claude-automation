from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import cdp
from .models import OrderDetailGroup, OrderSnapshot
from .parser import parse_order_product
from .window_position import ChromeActiveTab, get_chrome_active_tab


TOAUDIT_ROUTE = "#/trade/toaudit/"
TOAUDIT_TITLE = "快麦ERP--待审核订单"


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
    if not is_toaudit_tab(active_tab):
        return ""
    targets = targets if targets is not None else cdp.list_targets()
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
