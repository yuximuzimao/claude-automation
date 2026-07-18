'use strict';

const { EXEMPT_ACCESSORY_KEYWORDS } = require('./constants');

function text(value) {
  return value == null ? '' : String(value).trim();
}

function archiveItems(archive) {
  if (!archive) return null;
  if (Array.isArray(archive.subItems) && archive.subItems.length > 0) return archive.subItems;
  if (archive.title && archive.outerId) {
    return [{
      name: String(archive.title).split(';')[0].split('-')[0].trim(),
      specCode: archive.outerId,
      qty: 1,
    }];
  }
  return null;
}

function addExpected(target, items, multiplier, source, missingFacts) {
  for (const item of items || []) {
    if (EXEMPT_ACCESSORY_KEYWORDS.some(keyword => text(item && item.name).includes(keyword))) continue;
    const specCode = text(item && item.specCode);
    const itemQty = Number(item && item.qty);
    const quantity = itemQty * multiplier;
    if (!specCode || !Number.isFinite(quantity) || quantity <= 0) {
      missingFacts.push(`${source}商品档案缺少规格编码或有效数量`);
      continue;
    }
    target.set(specCode, (target.get(specCode) || 0) + quantity);
  }
}

function mapToObject(map) {
  return Object.fromEntries([...map.entries()].sort((a, b) => a[0].localeCompare(b[0])));
}

function proveReturnItems(collectedData) {
  const cd = collectedData || {};
  const ticket = cd.ticket || {};
  const mainOrders = ticket.subOrders || [];
  const gifts = ticket.gifts || [];
  const missingFacts = [];
  const mainExpected = new Map();
  const giftExpected = new Map();
  const archives = cd.productArchives || [];

  if ((cd.collectErrors || []).length > 0) missingFacts.push('存在采集错误，不能证明数据完整');
  if (!text(ticket.returnTracking)) missingFacts.push('缺少退货单号');
  if (!mainOrders.length) missingFacts.push('缺少主品子订单');
  for (const order of mainOrders) {
    const orderId = text(order && order.id);
    const multiplier = Number(order && order.afterSaleNum);
    let archive = archives.find(item => text(item && item.subOrderId) === orderId);
    if (!archive && mainOrders.length === 1) archive = cd.productArchive;
    const items = archiveItems(archive);
    if (!items) {
      missingFacts.push(`主品子订单${orderId || '未知'}缺少商品档案`);
      continue;
    }
    if (!Number.isFinite(multiplier) || multiplier <= 0) {
      missingFacts.push(`主品子订单${orderId || '未知'}缺少有效退货数量`);
      continue;
    }
    addExpected(mainExpected, items, multiplier, '主品', missingFacts);
  }

  if (gifts.length > 1) {
    missingFacts.push('多个赠品子订单只有单个赠品档案，无法逐个核对');
  } else if (gifts.length === 1) {
    const items = archiveItems(cd.giftProductArchive);
    const rawMultiplier = gifts[0] && gifts[0].afterSaleNum;
    const multiplier = rawMultiplier == null || rawMultiplier === '' ? 1 : Number(rawMultiplier);
    if (!items) missingFacts.push(`赠品子订单${text(gifts[0].id) || '未知'}缺少商品档案`);
    else if (!Number.isFinite(multiplier) || multiplier <= 0) missingFacts.push(`赠品子订单${text(gifts[0].id) || '未知'}缺少有效退货数量`);
    else addExpected(giftExpected, items, multiplier, '赠品', missingFacts);
  }

  const receivedRows = (cd.erpAftersale?.rows || []).filter(row =>
    text(row && row.goodsStatus).includes('卖家已收到退货')
  );
  if (!receivedRows.length) missingFacts.push('没有卖家已收到退货的 ERP 记录');

  const receivedGood = new Map();
  const receivedBad = new Map();
  const seenErpOrderIds = new Set();
  for (const row of receivedRows) {
    const erpOrderId = text(row && row.erpOrderId);
    if (!erpOrderId) missingFacts.push('ERP 已收货行缺少售后单号');
    else if (seenErpOrderIds.has(erpOrderId)) missingFacts.push(`ERP 售后单号${erpOrderId}重复`);
    else seenErpOrderIds.add(erpOrderId);

    if (text(row && row.tracking) !== text(ticket.returnTracking)) {
      missingFacts.push(`ERP 已收货行退货单号与工单不一致`);
    }
    if (!Array.isArray(row.items) || row.items.length === 0) {
      missingFacts.push(`ERP 已收货行${erpOrderId || '未知'}缺少商品明细`);
      continue;
    }

    let detailQuantity = 0;
    for (const item of row.items) {
      const qtyGood = Number(item && item.qtyGood);
      const qtyBad = Number(item && item.qtyBad);
      if (!Number.isFinite(qtyGood) || qtyGood < 0 || !Number.isFinite(qtyBad) || qtyBad < 0) {
        missingFacts.push(`ERP 已收货商品数量无效`);
        continue;
      }
      detailQuantity += qtyGood + qtyBad;
      if (qtyGood <= 0 && qtyBad <= 0) continue;
      const specCode = text(item && item.specCode);
      if (!specCode) {
        missingFacts.push('ERP 已收货商品缺少规格编码');
        continue;
      }
      receivedGood.set(specCode, (receivedGood.get(specCode) || 0) + qtyGood);
      receivedBad.set(specCode, (receivedBad.get(specCode) || 0) + qtyBad);
    }
    const returnQty = Number(row.returnQty);
    if (!Number.isFinite(returnQty) || returnQty < 0 || returnQty !== detailQuantity) {
      missingFacts.push(`ERP 已收货行${erpOrderId || '未知'}退回总数与良品次品合计不一致`);
    }
  }

  const expected = new Map(mainExpected);
  for (const [specCode, quantity] of giftExpected) {
    expected.set(specCode, (expected.get(specCode) || 0) + quantity);
  }
  if (!expected.size) missingFacts.push('没有可核对的应退规格');

  if (missingFacts.length > 0) {
    return {
      outcome: 'incomplete',
      mainOutcome: mainExpected.size ? 'incomplete' : 'missing',
      giftOutcome: gifts.length ? 'incomplete' : 'none',
      missingFacts: [...new Set(missingFacts)],
      expectedBySpec: mapToObject(expected),
      receivedGoodBySpec: mapToObject(receivedGood),
      receivedBadBySpec: mapToObject(receivedBad),
    };
  }

  const damagedSpecs = [...receivedBad].filter(([, quantity]) => quantity > 0).map(([specCode]) => specCode);
  const unmatchedSpecs = [...new Set([...receivedGood.keys(), ...receivedBad.keys()])]
    .filter(specCode => !expected.has(specCode));
  const shortSpecs = [...expected].filter(([specCode, quantity]) => (receivedGood.get(specCode) || 0) < quantity).map(([specCode]) => specCode);
  const excessSpecs = [...receivedGood].filter(([specCode, quantity]) => quantity > (expected.get(specCode) || 0)).map(([specCode]) => specCode);

  let outcome = 'exact';
  if (damagedSpecs.length) outcome = 'damaged';
  else if (unmatchedSpecs.length) outcome = 'unmatched';
  else if (shortSpecs.length) outcome = 'short';
  else if (excessSpecs.length) outcome = 'excess';

  return {
    outcome,
    mainOutcome: outcome,
    giftOutcome: gifts.length ? outcome : 'none',
    missingFacts: [],
    expectedBySpec: mapToObject(expected),
    receivedGoodBySpec: mapToObject(receivedGood),
    receivedBadBySpec: mapToObject(receivedBad),
    damagedSpecs,
    unmatchedSpecs,
    shortSpecs,
    excessSpecs,
  };
}

module.exports = { proveReturnItems };
