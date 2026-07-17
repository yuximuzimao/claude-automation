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
  for (const order of mainOrders) {
    const orderId = idOf(order && order.id);
    let archive = archives.find(item => idOf(item && item.subOrderId) === orderId);
    if (!archive && mainOrders.length === 1) archive = collectedData.productArchive;
    const items = archiveItems(archive);
    if (!items) return { error: `关联工单 ${workOrderNum} 的子订单 ${orderId || '未知'} 缺少商品档案` };
    for (const item of items) {
      const specCode = idOf(item && item.specCode);
      const qty = Number(item && item.qty) * (Number(order.afterSaleNum) || 1);
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
      const qty = Number(item && item.qty) * (Number(gifts[0].afterSaleNum) || 1);
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
  for (const workOrderNum of usedBy) {
    const simulation = [...(simulations || [])].reverse().find(item =>
      idOf(item && item.workOrderNum) === workOrderNum && item.collectedData && item.collectedData.ticket
    );
    if (!simulation) {
      return { mode: 'incomplete', reason: `平台提示关联工单 ${workOrderNum}，但系统没有该工单的完整采集记录` };
    }
    records.push({ workOrderNum, collectedData: simulation.collectedData });
  }

  const currentIds = new Set(subOrderIds(currentCollectedData));
  if (!currentIds.size) return { mode: 'incomplete', reason: '当前工单缺少子订单号，无法核对重复退货单' };

  const includedIds = new Set(currentIds);
  const ignoredWorkOrderNums = [];
  const distinctRecords = [];
  for (const record of records) {
    const ids = subOrderIds(record.collectedData);
    if (!ids.length) return { mode: 'incomplete', reason: `关联工单 ${record.workOrderNum} 缺少子订单号` };
    if (ids.some(id => includedIds.has(id))) {
      ignoredWorkOrderNums.push(record.workOrderNum);
      continue;
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

  return {
    mode: 'distinct_suborders',
    workOrderNums,
    expectedItems: [...grouped.values()],
  };
}

module.exports = { resolveSharedReturnGroup };
