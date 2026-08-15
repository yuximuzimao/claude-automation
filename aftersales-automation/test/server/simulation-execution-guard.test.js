'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  latestSimulationForQueue,
  assertLatestSimulationForExecution,
} = require('../../lib/server/simulation-execution-guard');

function simulation(id, action) {
  return { id, queueItemId: 'queue-B', decision: { action } };
}

test('关联组占位写入后，旧页面持有的历史 approve simulation 不可执行', () => {
  const oldApprove = simulation('sim-old-approve', 'approve');
  const safetyPlaceholder = simulation('sim-shared-placeholder', 'escalate');
  const simulations = [oldApprove, safetyPlaceholder];

  assert.equal(latestSimulationForQueue(simulations, 'queue-B'), safetyPlaceholder);
  assert.throws(
    () => assertLatestSimulationForExecution(oldApprove, simulations),
    /历史结论不可执行/
  );
  assert.equal(assertLatestSimulationForExecution(safetyPlaceholder, simulations), safetyPlaceholder);
});

test('旧 approve 先入队、占位后写入时，实际执行前的二次校验仍会拒绝旧结论', () => {
  const queuedSimulation = simulation('sim-queued-old-approve', 'approve');
  const simulationsAtEnqueue = [queuedSimulation];
  assert.equal(assertLatestSimulationForExecution(queuedSimulation, simulationsAtEnqueue), queuedSimulation);

  const simulationsAtExecution = [
    ...simulationsAtEnqueue,
    simulation('sim-placeholder-written-during-wait', 'escalate'),
  ];
  assert.throws(
    () => assertLatestSimulationForExecution(queuedSimulation, simulationsAtExecution),
    /历史结论不可执行/
  );
});

test('HTTP 入队前与操作队列真正执行前都装配最新 simulation 门禁', () => {
  const routesSource = fs.readFileSync(path.join(__dirname, '../../lib/server/routes.js'), 'utf8');
  const queueSource = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');

  assert.match(routesSource, /assertLatestSimulationForExecution\(sim, db\.readSimulations\(\)\)/);
  assert.match(queueSource, /assertLatestSimulationForExecution\(sim, db\.readSimulations\(\)\)/);
});
