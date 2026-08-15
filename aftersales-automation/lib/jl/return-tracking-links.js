'use strict';

/**
 * 读取平台“退货单号多次使用”的关联工单号。
 *
 * 该函数会被序列化后放进浏览器页面上下文执行，因此必须保持自包含，
 * 不能依赖模块作用域变量或 Node.js API。
 */
function readReturnTrackingLinksFromPage(documentRef, rootVm, returnTracking) {
  var doc = documentRef;
  var tracking = returnTracking == null ? '' : String(returnTracking).trim();
  var usedBy = [];
  var seenNums = {};
  var sawReference = false;

  function safeGet(value, key) {
    try {
      return value == null ? undefined : value[key];
    } catch (_) {
      return undefined;
    }
  }

  function addWorkOrderNums(value) {
    if (value == null) return;
    if (Array.isArray(value)) {
      for (var ai = 0; ai < value.length; ai++) addWorkOrderNums(value[ai]);
      return;
    }
    var matches = String(value).match(/1\d{16,21}/g) || [];
    for (var mi = 0; mi < matches.length; mi++) {
      var num = matches[mi];
      if (seenNums[num]) continue;
      seenNums[num] = true;
      usedBy.push(num);
    }
  }

  function readLogisticsList(list) {
    if (!Array.isArray(list)) return;
    for (var li = 0; li < list.length; li++) {
      var item = list[li];
      if (!item || typeof item !== 'object') continue;
      var rawItemTracking = safeGet(item, 'logisticsNum');
      var itemTracking = rawItemTracking == null ? '' : String(rawItemTracking).trim();
      if (tracking && itemTracking !== tracking) continue;
      var linkedWorkOrders = safeGet(item, 'logisticsUsedWorkOrderNumList');
      if (Array.isArray(linkedWorkOrders) && linkedWorkOrders.length > 0) {
        var previousCount = usedBy.length;
        addWorkOrderNums(linkedWorkOrders);
        if (usedBy.length > previousCount) sawReference = true;
      }
    }
  }

  var pending = rootVm ? [{ vm: rootVm, depth: 0 }] : [];
  var seenVms = [];
  while (pending.length) {
    var entry = pending.shift();
    var vm = entry.vm;
    if (!vm || entry.depth > 12 || seenVms.indexOf(vm) !== -1) continue;
    seenVms.push(vm);

    readLogisticsList(safeGet(vm, 'logisticsInfoList'));
    readLogisticsList(safeGet(vm, 'parcelList'));
    var props = safeGet(vm, '$props');
    if (props) {
      readLogisticsList(safeGet(props, 'logisticsInfoList'));
      readLogisticsList(safeGet(props, 'parcelList'));
    }
    var data = safeGet(vm, '$data');
    if (data) {
      readLogisticsList(safeGet(data, 'logisticsInfoList'));
      readLogisticsList(safeGet(data, 'parcelList'));
    }

    var children = safeGet(vm, '$children') || [];
    for (var ci = 0; ci < children.length; ci++) {
      pending.push({ vm: children[ci], depth: entry.depth + 1 });
    }
  }

  if (doc && typeof doc.querySelectorAll === 'function') {
    var references = doc.querySelectorAll('[aria-describedby], [aria-controls]') || [];
    var tooltipCandidates = [];
    for (var ri = 0; ri < references.length; ri++) {
      var reference = references[ri];
      var referenceText = String(safeGet(reference, 'textContent') || safeGet(reference, 'innerText') || '').trim();
      if (referenceText.indexOf('多次使用') === -1) continue;
      sawReference = true;
      var getAttribute = safeGet(reference, 'getAttribute');
      var tooltipId = '';
      if (typeof getAttribute === 'function') {
        try {
          tooltipId = getAttribute.call(reference, 'aria-describedby') ||
            getAttribute.call(reference, 'aria-controls') || '';
        } catch (_) {
          tooltipId = '';
        }
      }
      if (!tooltipId || typeof doc.getElementById !== 'function') continue;
      var tooltip = doc.getElementById(tooltipId);
      if (!tooltip) continue;
      var tooltipText = String(safeGet(tooltip, 'textContent') || safeGet(tooltip, 'innerText') || '');
      if (tooltipText.indexOf('物流单号已被工单号') === -1) continue;

      var nearTracking = false;
      var ancestor = reference;
      for (var pi = 0; pi < 6 && ancestor; pi++) {
        var ancestorText = String(safeGet(ancestor, 'textContent') || safeGet(ancestor, 'innerText') || '');
        if (tracking && ancestorText.indexOf(tracking) !== -1) {
          nearTracking = true;
          break;
        }
        ancestor = safeGet(ancestor, 'parentElement');
      }
      tooltipCandidates.push({ text: tooltipText, nearTracking: nearTracking });
    }

    var trackingCandidates = tooltipCandidates.filter(function(candidate) { return candidate.nearTracking; });
    var acceptedCandidates = trackingCandidates.length === 1
      ? trackingCandidates
      : (trackingCandidates.length === 0 && tooltipCandidates.length === 1 ? tooltipCandidates : []);
    for (var ti = 0; ti < acceptedCandidates.length; ti++) {
      addWorkOrderNums(acceptedCandidates[ti].text);
    }
  }

  var bodyText = doc && doc.body ? String(doc.body.innerText || '') : '';
  return {
    multiUse: sawReference || bodyText.indexOf('多次使用') !== -1 || usedBy.length > 0,
    usedBy: usedBy,
  };
}

module.exports = { readReturnTrackingLinksFromPage };
