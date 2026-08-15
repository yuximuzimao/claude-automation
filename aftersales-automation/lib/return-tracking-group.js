'use strict';

function idOf(value) {
  return value == null ? '' : String(value).trim();
}

function subOrderIds(collectedData) {
  const ticket = collectedData && collectedData.ticket;
  if (!ticket) return [];
  return [...(ticket.subOrders || []), ...(ticket.gifts || [])]
    .map(order => idOf(order && order.id))
    .filter(Boolean);
}

function archiveItems(archive) {
  if (!archive) return null;
  if (Array.isArray(archive.subItems) && archive.subItems.length) return archive.subItems;
  if (archive.title && archive.outerId) {
    return [{
      name: String(archive.title).split(';')[0].split('-')[0].trim(),
      specCode: archive.outerId,
      qty: 1,
    }];
  }
  return null;
}

function expectedItemsOf(collectedData, workOrderNum) {
  const ticket = collectedData && collectedData.ticket;
  if (!ticket) return { error: `关联工单 ${workOrderNum} 缺少工单详情` };

  const result = [];
  const mainOrders = ticket.subOrders || [];
  const archives = collectedData.productArchives || [];
  const mainOrderIds = mainOrders.map(order => idOf(order && order.id));
  if (mainOrderIds.some(orderId => !orderId) || new Set(mainOrderIds).size !== mainOrderIds.length) {
    return { error: `关联工单 ${workOrderNum} 的主品子订单号缺失或重复` };
  }
  for (const order of mainOrders) {
    const orderId = idOf(order && order.id);
    const multiplier = Number(order && order.afterSaleNum);
    if (!Number.isFinite(multiplier) || multiplier <= 0) {
      return { error: `关联工单 ${workOrderNum} 的子订单 ${orderId || '未知'} 缺少有效退货数量` };
    }
    let archive = archives.find(item => idOf(item && item.subOrderId) === orderId);
    if (!archive && mainOrders.length === 1) archive = collectedData.productArchive;
    const items = archiveItems(archive);
    if (!items) return { error: `关联工单 ${workOrderNum} 的子订单 ${orderId || '未知'} 缺少商品档案` };
    for (const item of items) {
      const specCode = idOf(item && item.specCode);
      const qty = Number(item && item.qty) * multiplier;
      if (!specCode || !Number.isFinite(qty) || qty <= 0) {
        return { error: `关联工单 ${workOrderNum} 的子订单 ${orderId || '未知'} 商品档案不完整` };
      }
      result.push({ specCode, name: item.name || specCode, qty });
    }
  }

  const gifts = ticket.gifts || [];
  if (gifts.length > 1) {
    return { error: `关联工单 ${workOrderNum} 有多个赠品子订单，现有记录不足以逐个核对` };
  }
  if (gifts.length === 1) {
    const items = archiveItems(collectedData.giftProductArchive);
    if (!items) return { error: `关联工单 ${workOrderNum} 的赠品子订单 ${idOf(gifts[0].id) || '未知'} 缺少商品档案` };
    for (const item of items) {
      const specCode = idOf(item && item.specCode);
      const qty = Number(item && item.qty);
      if (!specCode || !Number.isFinite(qty) || qty <= 0) {
        return { error: `关联工单 ${workOrderNum} 的赠品商品档案不完整` };
      }
      result.push({ specCode, name: item.name || specCode, qty });
    }
  }

  if (!result.length) return { error: `关联工单 ${workOrderNum} 没有可核对的商品明细` };
  return { items: result };
}

function resolveSharedReturnGroup(currentCollectedData, simulations, currentWorkOrderNum) {
  const ticket = currentCollectedData && currentCollectedData.ticket;
  if (!ticket || !ticket.returnTrackingMultiUse) return null;

  const currentNum = idOf(currentWorkOrderNum || ticket.workOrderNum);
  const usedBy = [...new Set((ticket.returnTrackingUsedBy || []).map(idOf).filter(Boolean))]
    .filter(workOrderNum => workOrderNum !== currentNum);
  if (!usedBy.length) {
    return { mode: 'incomplete', reason: '平台提示退货单号重复使用，但没有提供关联工单号' };
  }

  const records = [];
  const missingWorkOrderNums = [];
  const pendingWorkOrderNums = [...usedBy];
  const discoveredWorkOrderNums = new Set(usedBy);
  while (pendingWorkOrderNums.length) {
    const workOrderNum = pendingWorkOrderNums.shift();
    const simulation = [...(simulations || [])].reverse().find(item =>
      idOf(item && item.workOrderNum) === workOrderNum && item.collectedData && item.collectedData.ticket
    );
    if (!simulation) {
      missingWorkOrderNums.push(workOrderNum);
      continue;
    }
    const record = { workOrderNum, collectedData: simulation.collectedData };
    records.push(record);

    const relatedTicket = record.collectedData.ticket;
    const relatedLinks = [...new Set((relatedTicket.returnTrackingUsedBy || []).map(idOf).filter(Boolean))]
      .filter(num => num !== currentNum && !discoveredWorkOrderNums.has(num));
    if (relatedLinks.length > 0) {
      const relatedTracking = idOf(relatedTicket.returnTracking);
      if (!relatedTracking || relatedTracking !== idOf(ticket.returnTracking)) {
        return {
          mode: 'incomplete',
          reason: `关联工单 ${workOrderNum} 还指向其他工单，但其退货单号记录不一致，无法继续汇总关联组`,
        };
      }
      for (const linkedWorkOrderNum of relatedLinks) {
        discoveredWorkOrderNums.add(linkedWorkOrderNum);
        pendingWorkOrderNums.push(linkedWorkOrderNum);
      }
    }
  }
  if (missingWorkOrderNums.length) {
    return {
      mode: 'incomplete',
      reason: `平台提示关联工单 ${missingWorkOrderNums.join('、')}，但系统没有该工单的完整采集记录`,
      missingWorkOrderNums,
    };
  }

  const currentIds = new Set(subOrderIds(currentCollectedData));
  if (!currentIds.size) return { mode: 'incomplete', reason: '当前工单缺少子订单号，无法核对重复退货单' };

  const includedIds = new Set(currentIds);
  const ignoredWorkOrderNums = [];
  const distinctRecords = [];
  for (const record of records) {
    const ids = subOrderIds(record.collectedData);
    if (!ids.length) return { mode: 'incomplete', reason: `关联工单 ${record.workOrderNum} 缺少子订单号` };
    const overlappingIds = ids.filter(id => includedIds.has(id));
    if (overlappingIds.length === ids.length) {
      ignoredWorkOrderNums.push(record.workOrderNum);
      continue;
    }
    if (overlappingIds.length > 0) {
      return {
        mode: 'incomplete',
        reason: `关联工单 ${record.workOrderNum} 同时包含已计入和未计入的子订单，无法安全拆分应退数量`,
      };
    }
    const relatedTracking = idOf(record.collectedData.ticket.returnTracking);
    if (!relatedTracking || relatedTracking !== idOf(ticket.returnTracking)) {
      return { mode: 'incomplete', reason: `平台关联工单 ${record.workOrderNum} 的退货单号记录不一致` };
    }
    ids.forEach(id => includedIds.add(id));
    distinctRecords.push(record);
  }

  if (!distinctRecords.length) return { mode: 'same_suborders_only', ignoredWorkOrderNums };

  const workOrderNums = [currentNum, ...distinctRecords.map(record => record.workOrderNum)].filter(Boolean);
  const grouped = new Map();
  for (const record of [{ workOrderNum: currentNum || '当前工单', collectedData: currentCollectedData }, ...distinctRecords]) {
    const expected = expectedItemsOf(record.collectedData, record.workOrderNum);
    if (expected.error) return { mode: 'incomplete', reason: expected.error };
    for (const item of expected.items) {
      const existing = grouped.get(item.specCode);
      if (existing) existing.qty += item.qty;
      else grouped.set(item.specCode, { ...item });
    }
  }

  const result = {
    mode: 'distinct_suborders',
    workOrderNums,
    expectedItems: [...grouped.values()],
  };
  if (ignoredWorkOrderNums.length) result.ignoredWorkOrderNums = ignoredWorkOrderNums;
  return result;
}

module.exports = { resolveSharedReturnGroup };
