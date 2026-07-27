'use strict';

const cdp = require('../cdp');
const { readTicket } = require('./read-ticket');

const ERP_URL = 'https://viperp.superboss.cc';
const ERP_DOMAIN = 'superboss.cc';
const { getLogistics } = require('./logistics');
const { erpSearch } = require('../erp/search');
const { readAllErpLogistics } = require('../erp/read-logistics');
const { erpAftersale } = require('../erp/aftersale');
const { productMatch } = require('../product/match');
const { productArchive } = require('../product/archive');
const { getErpShop } = require('../erp/shop-map');
const { normalizeAfterSaleType } = require('./after-sale-type');

function loadDefaultDependencies() {
  return {
    readTicket,
    getLogistics,
    erpSearch,
    readAllErpLogistics,
    erpAftersale,
    productMatch,
    productArchive,
    getErpShop,
  };
}

function emptyCollectedData() {
  return {
    ticket: null,
    erpSearch: null,
    erpSearches: [],
    erpLogistics: null,
    logistics: null,
    erpAftersale: null,
    productMatch: null,
    productArchive: null,
    productMatches: [],
    productArchives: [],
    giftErpSearch: null,
    giftErpSearches: [],
    giftProductMatch: null,
    giftProductArchive: null,
    collectErrors: [],
  };
}

function resultData(result, errorPrefix, collected) {
  if (!result || !result.success) {
    collected.collectErrors.push(`${errorPrefix}: ${(result && result.error) || '未知错误'}`);
    return null;
  }
  return result.data;
}

function targetIdOf(target) {
  return target && (target.id || target.targetId || null);
}

function isErpTarget(target) {
  return Boolean(target && target.type === 'page' && target.url && target.url.includes(ERP_DOMAIN));
}

async function resolveUniqueErpTargetId(dependencies = { getTargets: cdp.getTargets, createTarget: cdp.createTarget, activateTarget: cdp.activateTarget }, requestedTargetId) {
  const targets = await dependencies.getTargets();
  const erpTargets = (targets || []).filter(isErpTarget);
  if (requestedTargetId) {
    const requested = erpTargets.find(target => targetIdOf(target) === requestedTargetId);
    if (!requested) throw new Error(`指定ERP标签页不存在: ${requestedTargetId}`);
    return targetIdOf(requested);
  }
  if (erpTargets.length > 0) return targetIdOf(erpTargets[0]);

  const createTarget = typeof dependencies.createTarget === 'function' ? dependencies.createTarget : cdp.createTarget;
  const activateTarget = typeof dependencies.activateTarget === 'function' ? dependencies.activateTarget : cdp.activateTarget;
  if (typeof createTarget !== 'function') throw new Error('未找到ERP标签页，且无法创建ERP标签页');
  const created = await createTarget(ERP_URL);
  const createdTargetId = targetIdOf(created);
  if (!createdTargetId) throw new Error('ERP标签页已创建但缺少 targetId');
  if (typeof activateTarget === 'function') await activateTarget(createdTargetId);
  return createdTargetId;
}

async function collectProductDetails(context, ticket, collected, dependencies) {
  const shopName = dependencies.getErpShop(context.accountNote || '');
  for (const subOrder of ticket.subOrders || []) {
    if (!subOrder.id || !subOrder.sku) {
      collected.collectErrors.push(`product-match(${subOrder.id || 'unknown'}): 无货号，跳过`);
      continue;
    }
    const matchResult = await dependencies.productMatch(
      context.erpTargetId,
      subOrder.sku,
      subOrder.attr1 || '',
      shopName
    );
    const match = resultData(matchResult, `product-match(${subOrder.id})`, collected);
    if (!match) continue;
    const matchEntry = { subOrderId: subOrder.id, ...match };
    collected.productMatches.push(matchEntry);
    if (match.matched === false || !match.specCode) {
      collected.collectErrors.push(`product-archive(${subOrder.id}): 商品规格未精确匹配，跳过`);
      continue;
    }
    const archiveResult = await dependencies.productArchive(context.erpTargetId, match.specCode);
    const archive = resultData(archiveResult, `product-archive(${subOrder.id})`, collected);
    if (archive) collected.productArchives.push({ subOrderId: subOrder.id, ...archive });
  }
  collected.productMatch = collected.productMatches[0] || null;
  collected.productArchive = collected.productArchives[0] || null;

  const gift = (ticket.gifts || [])[0];
  if (!gift || !gift.sku) return;
  const giftMatchResult = await dependencies.productMatch(
    context.erpTargetId,
    gift.sku,
    gift.attr1 || '',
    shopName
  );
  const giftMatch = resultData(giftMatchResult, 'product-match(gift)', collected);
  if (!giftMatch) return;
  collected.giftProductMatch = giftMatch;
  if (giftMatch.matched === false || !giftMatch.specCode) {
    collected.collectErrors.push('product-archive(gift): 商品规格未精确匹配，跳过');
    return;
  }
  const giftArchiveResult = await dependencies.productArchive(context.erpTargetId, giftMatch.specCode);
  collected.giftProductArchive = resultData(giftArchiveResult, 'product-archive(gift)', collected);
}

async function collectErpOrder(context, subOrderId, errorLabel, collected, dependencies, logisticsResults) {
  const searchResult = await dependencies.erpSearch(context.erpTargetId, subOrderId);
  const search = resultData(searchResult, errorLabel, collected);
  if (!search) return null;

  const logisticsResult = await dependencies.readAllErpLogistics(context.erpTargetId);
  const logistics = resultData(logisticsResult, `erp-logistics(${subOrderId})`, collected);
  if (logistics && Array.isArray(logistics.results)) logisticsResults.push(...logistics.results);
  return search;
}

async function collectTicketTargetAware(context, customDependencies) {
  if (!context || !context.detailTargetId) throw new Error('target-aware 采集缺少 detailTargetId');
  if (!context.erpTargetId) throw new Error('target-aware 采集缺少 erpTargetId');
  if (!context.workOrderNum) throw new Error('target-aware 采集缺少 workOrderNum');

  const dependencies = customDependencies || loadDefaultDependencies();
  const collected = emptyCollectedData();
  const ticketResult = await dependencies.readTicket(context.detailTargetId, context.workOrderNum);
  if (!ticketResult || !ticketResult.success) {
    throw new Error(`read-ticket: ${(ticketResult && ticketResult.error) || '未知错误'}`);
  }
  const ticket = resultData(ticketResult, 'read-ticket', collected);
  if (!ticket) return collected;
  collected.ticket = ticket;

  const logisticsResults = [];
  for (const subOrder of ticket.subOrders || []) {
    if (!subOrder.id) continue;
    const search = await collectErpOrder(
      context,
      subOrder.id,
      `erp-search: 子订单 ${subOrder.id}`,
      collected,
      dependencies,
      logisticsResults
    );
    if (search) collected.erpSearches.push({ subOrderId: subOrder.id, ...search });
  }
  collected.erpSearch = collected.erpSearches[0] || null;

  const logisticsResult = await dependencies.getLogistics(context.detailTargetId, context.workOrderNum);
  if (!logisticsResult || !logisticsResult.success) {
    throw new Error(`logistics: ${(logisticsResult && logisticsResult.error) || '未知错误'}`);
  }
  collected.logistics = resultData(logisticsResult, 'logistics', collected);

  const type = normalizeAfterSaleType(context.type) || normalizeAfterSaleType(ticket.subBizType) || '';
  // 换货有退货单号时同样需要证明客户实际退回了什么商品。
  // 是否换货/商责只限制最终执行，不应阻断商品事实采集。
  const skipProductDetail = type === '仅退款';
  if (skipProductDetail) {
    collected.collectErrors.push(`product-detail: 跳过（工单类型=${type}，无需核对商品明细）`);
  } else {
    try {
      await collectProductDetails(context, ticket, collected, dependencies);
    } catch (error) {
      collected.collectErrors.push(`product-match: ${error.message}`);
    }
  }

  if (ticket.returnTracking) {
    const aftersaleResult = await dependencies.erpAftersale(context.erpTargetId, ticket.returnTracking);
    collected.erpAftersale = resultData(aftersaleResult, 'erp-aftersale', collected);
  } else {
    collected.collectErrors.push('erp-aftersale: 无退货快递单号，跳过');
  }

  const giftsToCollect = type === '仅退款' ? (ticket.gifts || []) : (ticket.gifts || []).slice(0, 1);
  for (const gift of giftsToCollect) {
    if (!gift.id) continue;
    const search = await collectErpOrder(
      context,
      gift.id,
      `erp-search: 赠品 ${gift.id}`,
      collected,
      dependencies,
      logisticsResults
    );
    if (search) collected.giftErpSearches.push({ subOrderId: gift.id, ...search });
  }
  collected.giftErpSearch = collected.giftErpSearches[0] || null;

  if (logisticsResults.length) collected.erpLogistics = { results: logisticsResults };
  return collected;
}

module.exports = {
  collectTicketTargetAware,
  resolveUniqueErpTargetId,
  emptyCollectedData,
  loadDefaultDependencies,
};
