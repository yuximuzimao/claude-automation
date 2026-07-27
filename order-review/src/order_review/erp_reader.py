from __future__ import annotations

from typing import Any

from . import cdp
from .models import OrderDetailGroup, OrderSnapshot
from .parser import parse_order_product
from .window_position import ChromeActiveTab, get_chrome_active_tab


TOAUDIT_ROUTE = "#/trade/toaudit/"
TOAUDIT_TITLE = "快麦ERP--待审核订单"


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
    for target in targets:
        if target.get("url", "") == active_tab.url:
            return target.get("targetId") or target.get("id") or ""
    return ""


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


def read_sequence_one_order(target_id: str | None = None) -> OrderSnapshot:
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
    if not payload.get("isExpanded"):
        expanded = cdp.eval_js(target_id, build_expand_sequence_one_js())
        if isinstance(expanded, dict) and expanded.get("expanded"):
            payload = cdp.eval_js(target_id, build_read_sequence_one_js())
            if not isinstance(payload, dict) or not payload.get("ok"):
                raise RuntimeError("展开订单后读取 ERP 订单失败")
    return snapshot_from_payload(payload)


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
