'use strict';

function latestSimulationForQueue(simulations, queueItemId) {
  const targetQueueId = queueItemId == null ? '' : String(queueItemId);
  if (!targetQueueId) return null;
  return [...(simulations || [])].reverse().find(simulation =>
    simulation && String(simulation.queueItemId || '') === targetQueueId
  ) || null;
}

function assertLatestSimulationForExecution(simulation, simulations) {
  const latest = latestSimulationForQueue(simulations, simulation && simulation.queueItemId);
  if (!simulation || !latest || String(latest.id || '') !== String(simulation.id || '')) {
    throw new Error('该工单已有更新的核验结果，历史结论不可执行，请刷新后使用最新结果');
  }
  return simulation;
}

module.exports = { latestSimulationForQueue, assertLatestSimulationForExecution };
