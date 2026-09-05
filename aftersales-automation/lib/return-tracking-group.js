'use strict';

function idOf(value) {
  return value == null ? '' : String(value).trim();
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

function expectedItemsOf(collectedData, workOrderNum, countedGiftIds) {
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
    const giftOrderId = idOf(gifts[0] && gifts[0].id);
    if (!giftOrderId) return { error: `关联工单 ${workOrderNum} 的赠品子订单号缺失` };
    if (!countedGiftIds || !countedGiftIds.has(giftOrderId)) {
      const items = archiveItems(collectedData.giftProductArchive);
      if (!items) return { error: `关联工单 ${workOrderNum} 的赠品子订单 ${giftOrderId} 缺少商品档案` };
      for (const item of items) {
        const specCode = idOf(item && item.specCode);
        const qty = Number(item && item.qty);
        if (!specCode || !Number.isFinite(qty) || qty <= 0) {
          return { error: `关联工单 ${workOrderNum} 的赠品商品档案不完整` };
        }
        result.push({ specCode, name: item.name || specCode, qty });
      }
      if (countedGiftIds) countedGiftIds.add(giftOrderId);
    }
  }

  if (!result.length) return { error: `关联工单 ${workOrderNum} 没有可核对的商品明细` };
  return { items: result };
}

function resolveSharedReturnGroup(currentCollectedData, simulations, currentWorkOrderNum, options = {}) {
  const ticket = currentCollectedData && currentCollectedData.ticket;
  if (!ticket || !ticket.returnTrackingMultiUse) return null;

  const currentNum = idOf(currentWorkOrderNum || ticket.workOrderNum);
  const tracking = idOf(ticket.returnTracking);
  const activeWorkOrderNums = options.activeWorkOrderNums instanceof Set
    ? new Set([...options.activeWorkOrderNums].map(idOf).filter(Boolean))
    : null;
  const freshWorkOrderNums = options.freshWorkOrderNums instanceof Set
    ? new Set([...options.freshWorkOrderNums].map(idOf).filter(Boolean))
    : null;
  const linkedWorkOrderNums = [...new Set((ticket.returnTrackingUsedBy || []).map(idOf).filter(Boolean))]
    .filter(workOrderNum => workOrderNum !== currentNum);
  if (!linkedWorkOrderNums.length) {
    return { mode: 'incomplete', reason: '平台提示退货单号重复使用，但没有提供关联工单号' };
  }

  const currentRecords = [];
  const historicalRecords = [];
  const missingCurrentWorkOrderNums = [];
  const missingHistoricalWorkOrderNums = [];
  const pendingWorkOrderNums = [...linkedWorkOrderNums];
  const discoveredWorkOrderNums = new Set(linkedWorkOrderNums);

  while (pendingWorkOrderNums.length) {
    const workOrderNum = pendingWorkOrderNums.shift();
    const isCurrentApplication = !activeWorkOrderNums || activeWorkOrderNums.has(workOrderNum);
    if (isCurrentApplication && freshWorkOrderNums && !freshWorkOrderNums.has(workOrderNum)) {
      missingCurrentWorkOrderNums.push(workOrderNum);
      continue;
    }

    const matchingSimulations = (simulations || []).filter(item =>
      idOf(item && item.workOrderNum) === workOrderNum && item.collectedData && item.collectedData.ticket
    );
    const newestFirst = [...matchingSimulations].reverse();
    const simulation = isCurrentApplication
      ? newestFirst[0]
      : newestFirst.find(item => item.decision && item.decision.action === 'approve' && item.executedAt) || newestFirst[0];
    if (!simulation) {
      (isCurrentApplication ? missingCurrentWorkOrderNums : missingHistoricalWorkOrderNums).push(workOrderNum);
      continue;
    }

    const relatedTicket = simulation.collectedData.ticket;
    const relatedTracking = idOf(relatedTicket.returnTracking);
    if (isCurrentApplication) {
      if (!relatedTracking || relatedTracking !== tracking) {
        return { mode: 'incomplete', reason: `当前关联工单 ${workOrderNum} 的退货单号记录不一致` };
      }
      currentRecords.push({ workOrderNum, simulation, collectedData: simulation.collectedData });

      const relatedLinks = [...new Set((relatedTicket.returnTrackingUsedBy || []).map(idOf).filter(Boolean))]
        .filter(num => num !== currentNum && !discoveredWorkOrderNums.has(num));
      for (const linkedWorkOrderNum of relatedLinks) {
        discoveredWorkOrderNums.add(linkedWorkOrderNum);
        pendingWorkOrderNums.push(linkedWorkOrderNum);
      }
    } else {
      if (relatedTracking && relatedTracking !== tracking) {
        return { mode: 'incomplete', reason: `历史关联工单 ${workOrderNum} 的退货单号记录与平台当前提示不一致` };
      }
      historicalRecords.push({ workOrderNum, simulation, collectedData: simulation.collectedData });
    }
  }

  if (missingCurrentWorkOrderNums.length) {
    return {
      mode: 'incomplete',
      reason: `平台提示关联工单 ${missingCurrentWorkOrderNums.join('、')} 仍在当前48小时批次，但本轮尚未采集完整`,
      missingWorkOrderNums: missingCurrentWorkOrderNums,
    };
  }
  if (missingHistoricalWorkOrderNums.length) {
    return {
      mode: 'incomplete',
      reason: `平台提示关联工单 ${missingHistoricalWorkOrderNums.join('、')}，但本轮48小时采集与历史记录均未找到；可能为历史记录缺失或特殊重复申请，需人工判断`,
      missingWorkOrderNums: missingHistoricalWorkOrderNums,
      missingHistoricalWorkOrderNums,
    };
  }

  const countedGiftIds = new Set();
  const historicalConsumedBySpec = new Map();
  const historicalWorkOrders = [];
  for (const record of historicalRecords) {
    const action = record.simulation && record.simulation.decision && record.simulation.decision.action;
    const executedAt = record.simulation && record.simulation.executedAt;
    if (executedAt && !action) {
      return {
        mode: 'incomplete',
        reason: `历史关联工单 ${record.workOrderNum} 有执行记录但缺少决策动作，无法确认是否已占用退货数量`,
      };
    }
    const consumesReturnQty = action === 'approve' && Boolean(executedAt);
    historicalWorkOrders.push({
      workOrderNum: record.workOrderNum,
      action: action || null,
      executedAt: executedAt || null,
      consumesReturnQty,
    });
    if (!consumesReturnQty) continue;

    const consumed = expectedItemsOf(record.collectedData, record.workOrderNum, countedGiftIds);
    if (consumed.error) {
      return {
        mode: 'incomplete',
        reason: `历史关联工单 ${record.workOrderNum} 已执行同意退款，但无法还原其占用数量：${consumed.error}`,
      };
    }
    for (const item of consumed.items) {
      const existing = historicalConsumedBySpec.get(item.specCode);
      if (existing) existing.qty += item.qty;
      else historicalConsumedBySpec.set(item.specCode, { ...item });
    }
  }

  const currentExpectedBySpec = new Map();
  const currentGroup = [
    { workOrderNum: currentNum || '当前工单', collectedData: currentCollectedData },
    ...currentRecords,
  ];
  for (const record of currentGroup) {
    const expected = expectedItemsOf(record.collectedData, record.workOrderNum, countedGiftIds);
    if (expected.error) return { mode: 'incomplete', reason: expected.error };
    for (const item of expected.items) {
      const existing = currentExpectedBySpec.get(item.specCode);
      if (existing) existing.qty += item.qty;
      else currentExpectedBySpec.set(item.specCode, { ...item });
    }
  }

  const result = {
    mode: 'combined_applications',
    workOrderNums: currentGroup.map(record => record.workOrderNum).filter(Boolean),
    expectedItems: [...currentExpectedBySpec.values()],
  };
  if (historicalWorkOrders.length) {
    result.historicalConsumedItems = [...historicalConsumedBySpec.values()];
    result.historicalWorkOrders = historicalWorkOrders;
  }
  return result;
}

module.exports = { resolveSharedReturnGroup };
