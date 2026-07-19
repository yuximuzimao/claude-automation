from __future__ import annotations

from typing import Any

from . import cdp
from .models import OrderSnapshot
from .parser import parse_order_product


def find_erp_toaudit_target(targets: list[dict[str, Any]] | None = None) -> str:
    targets = targets if targets is not None else cdp.list_targets()
    for target in targets:
        title = target.get("title", "")
        url = target.get("url", "")
        is_order_title = "快麦ERP--待审核订单" in title or "快麦ERP--订单管理" in title
        is_order_route = "#/trade/toaudit/" in url or "#/tradeNew/manage/" in url
        if is_order_title or is_order_route:
            return target.get("targetId") or target.get("id") or ""
    return ""


def build_read_sequence_one_js() -> str:
    return r"""(function(){
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
  if (!row) return JSON.stringify({ok:false,error:'SEQ_ONE_NOT_FOUND',rowCount:rows.length});
  var isExpanded = row.classList.contains('module-trade-list-item-open');
  var hasCanMergeMark = row.querySelectorAll('.trade-icon-canmerged,[data-name="trade-icon-canmerged"]').length > 0;
  if (!isExpanded) {
    return JSON.stringify({ok:true,isExpanded:false,hasCanMergeMark:hasCanMergeMark,hasSuiteAction:false,products:[]});
  }
  var orderRows = Array.from(row.querySelectorAll('tr.order-temp'));
  var products = orderRows.map(function(tr){
    var actionText = Array.from(tr.querySelectorAll('a,button,[data-name]')).map(function(el){ return clean(el.innerText || el.getAttribute('data-title') || ''); }).join('\n');
    return {
      dataset: Object.assign({}, tr.dataset),
      lines: lines(tr.innerText || tr.textContent),
      hasSuiteAction: /套件明细|套件转单品/.test(actionText)
    };
  });
  var hasSuiteAction = products.some(function(product){ return product.hasSuiteAction; });
  return JSON.stringify({ok:true,isExpanded:true,hasCanMergeMark:hasCanMergeMark,hasSuiteAction:hasSuiteAction,products:products});
})()"""


def read_sequence_one_order(target_id: str | None = None) -> OrderSnapshot:
    target_id = target_id or find_erp_toaudit_target()
    if not target_id:
        raise RuntimeError("未找到快麦 ERP 待审核订单标签页")
    payload = cdp.eval_js(target_id, build_read_sequence_one_js())
    if not isinstance(payload, dict):
        raise RuntimeError("ERP 页面返回了无法识别的数据")
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "读取 ERP 订单失败")
    return snapshot_from_payload(payload)


def snapshot_from_payload(payload: dict[str, Any]) -> OrderSnapshot:
    products = [
        parse_order_product(product.get("lines", []), product.get("dataset", {}))
        for product in payload.get("products", [])
    ]
    return OrderSnapshot(
        is_expanded=bool(payload.get("isExpanded")),
        products=products,
        has_can_merge_mark=bool(payload.get("hasCanMergeMark")),
        has_suite_action=bool(payload.get("hasSuiteAction")),
    )
