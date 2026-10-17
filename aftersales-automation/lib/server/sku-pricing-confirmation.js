'use strict';

const db = require('./data');
const { inferDecision } = require('../infer');
const { validateConfirmedPricing, saveConfirmedSkuPricing } = require('../sku-pricing');

function latestLiveSimulations(simulations) {
  const latest = new Map();
  for (const sim of simulations || []) {
    if (!sim || sim.mode !== 'live' || !sim.queueItemId) continue;
    const prev = latest.get(sim.queueItemId);
    const simTime = Date.parse(sim.createdAt || '') || 0;
    const prevTime = prev ? (Date.parse(prev.createdAt || '') || 0) : -1;
    if (!prev || simTime >= prevTime) latest.set(sim.queueItemId, sim);
  }
  return [...latest.values()];
}

function buildPendingIndex(simulations) {
  const bySpecCode = new Map();
  for (const sim of latestLiveSimulations(simulations)) {
    const pending = sim.decision && sim.decision.skuPricingPending;
    if (!pending || !pending.specCode) continue;
    const code = String(pending.specCode);
    if (!bySpecCode.has(code)) bySpecCode.set(code, []);
    bySpecCode.get(code).push({ sim, pending });
  }
  return bySpecCode;
}

function confirmSkuPricingAndReinfer(entries, dependencies = {}) {
  const data = dependencies.db || db;
  const infer = dependencies.inferDecision || inferDecision;
  const save = dependencies.saveConfirmedSkuPricing || saveConfirmedSkuPricing;
  const now = dependencies.now || (() => new Date().toISOString());

  if (!Array.isArray(entries) || entries.length === 0) {
    throw new Error('请至少勾选一个SKU计价关系');
  }

  const simulations = data.readSimulations({ mode: 'live' });
  const queue = data.readQueue();
  const queueById = new Map((queue.items || []).map(item => [item.id, item]));
  const pendingBySpec = buildPendingIndex(simulations);
  const validated = [];

  for (const raw of entries) {
    const requested = validateConfirmedPricing(raw);
    const linked = pendingBySpec.get(requested.specCode) || [];
    if (linked.length === 0) {
      throw new Error(`${requested.specCode} 当前没有等待确认的工单，未保存`);
    }

    const physicalQtys = [...new Set(linked.map(({ pending }) => Number(pending.physicalQty)))];
    if (physicalQtys.length !== 1 || physicalQtys[0] !== requested.physicalQty) {
      throw new Error(`${requested.specCode} 当前工单的ERP实际组成与提交值不一致，请刷新页面后重新确认`);
    }
    validated.push(requested);
  }

  const saved = save(validated, now);
  const selectedCodes = new Set(saved.map(item => item.specCode));
  const reinferred = [];

  for (const sim of latestLiveSimulations(simulations)) {
    const pending = sim.decision && sim.decision.skuPricingPending;
    if (!pending || !selectedCodes.has(String(pending.specCode))) continue;
    const queueItem = queueById.get(sim.queueItemId);
    if (!queueItem || queueItem.status === 'done') continue;

    const decision = infer(sim, queueItem);
    data.updateSimulation(sim.id, {
      decision,
      skuPricingReinferredAt: now(),
    });
    reinferred.push({
      simulationId: sim.id,
      workOrderNum: sim.workOrderNum,
      specCode: String(pending.specCode),
    });
  }

  return { saved, reinferred };
}

module.exports = {
  latestLiveSimulations,
  buildPendingIndex,
  confirmSkuPricingAndReinfer,
};
