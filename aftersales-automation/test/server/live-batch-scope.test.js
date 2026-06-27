'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  parseBatchExecuteRequest,
  parseBatchReprocessRequest,
  selectExecutableSimulations,
  selectReprocessQueueItems,
} = require('../../lib/server/live-batch-scope');

const queueItems = [
  { id: 'q-14-late', workOrderNum: '1004', accountNum: 14, accountNote: '茗瑞-KGOS', mode: 'live', status: 'simulated', deadlineAt: '2026-06-27T12:00:00.000Z' },
  { id: 'q-15', workOrderNum: '1002', accountNum: 15, accountNote: '其他店铺', mode: 'live', status: 'simulated', deadlineAt: '2026-06-27T08:00:00.000Z' },
  { id: 'q-14-waiting', workOrderNum: '1003', accountNum: 14, accountNote: '茗瑞-KGOS', mode: 'live', status: 'waiting', deadlineAt: '2026-06-27T07:00:00.000Z' },
  { id: 'q-14-early', workOrderNum: '1001', accountNum: 14, accountNote: '茗瑞-KGOS', mode: 'live', status: 'simulated', deadlineAt: '2026-06-27T06:00:00.000Z' },
  { id: 'q-14-pending', workOrderNum: '1005', accountNum: 14, accountNote: '茗瑞-KGOS', mode: 'live', status: 'pending', deadlineAt: '2026-06-27T05:00:00.000Z' },
  { id: 'q-14-auto', workOrderNum: '1006', accountNum: 14, accountNote: '茗瑞-KGOS', mode: 'live', status: 'auto_executed', deadlineAt: '2026-06-27T04:00:00.000Z' },
  { id: 'q-missing-account', workOrderNum: '1007', accountNum: null, accountNote: '', mode: 'live', status: 'simulated', deadlineAt: '2026-06-27T03:00:00.000Z' },
];

const simulations = [
  { id: 's-14-late', queueItemId: 'q-14-late', workOrderNum: '1004', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
  { id: 's-15', queueItemId: 'q-15', workOrderNum: '1002', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
  { id: 's-14-waiting', queueItemId: 'q-14-waiting', workOrderNum: '1003', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
  { id: 's-14-early-old', queueItemId: 'q-14-early', workOrderNum: '1001', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
  { id: 's-14-early-current', queueItemId: 'q-14-early', workOrderNum: '1001', mode: 'live', createdAt: '2026-06-27T02:00:00.000Z', decision: { action: 'reject', reasonCode: 'SIGNED_NO_INTERCEPT' } },
  { id: 's-14-pending', queueItemId: 'q-14-pending', workOrderNum: '1005', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
  { id: 's-missing-account', queueItemId: 'q-missing-account', workOrderNum: '1007', mode: 'live', createdAt: '2026-06-27T01:00:00.000Z', decision: { action: 'approve' } },
];

test('batch execute explicit pending scope filters by accountNum and preserves deadline order', () => {
  const scope = parseBatchExecuteRequest({ statusScope: 'pending', accountNum: 14 });
  const selected = selectExecutableSimulations({ simulations, queueItems, scope });

  assert.deepEqual(selected.map(s => s.id), ['s-14-early-current', 's-14-late']);
});

test('batch execute excludes waiting, pending-not-simulated, hidden stores, and missing account under single-store scope', () => {
  const scope = parseBatchExecuteRequest({ statusScope: 'pending', accountNum: '14' });
  const selected = selectExecutableSimulations({ simulations, queueItems, scope });

  assert.equal(selected.some(s => s.queueItemId === 'q-14-waiting'), false);
  assert.equal(selected.some(s => s.queueItemId === 'q-14-pending'), false);
  assert.equal(selected.some(s => s.queueItemId === 'q-15'), false);
  assert.equal(selected.some(s => s.queueItemId === 'q-missing-account'), false);
});

test('batch reprocess waiting scope selects only waiting items for the requested account', () => {
  const scope = parseBatchReprocessRequest({ statusScope: 'waiting', accountNum: 14 });
  const selected = selectReprocessQueueItems(queueItems, scope);

  assert.deepEqual(selected.map(i => i.id), ['q-14-waiting']);
});

test('batch reprocess pending scope keeps pending-tab semantics and deadline order', () => {
  const scope = parseBatchReprocessRequest({ statusScope: 'pending', accountNum: 14 });
  const selected = selectReprocessQueueItems(queueItems, scope);

  assert.deepEqual(selected.map(i => i.id), ['q-14-pending', 'q-14-early', 'q-14-late']);
});

test('invalid scoped requests fail closed', () => {
  assert.throws(() => parseBatchExecuteRequest({ statusScope: 'waiting' }), /invalid statusScope/);
  assert.throws(() => parseBatchExecuteRequest({ accountNum: 14 }), /statusScope required/);
  assert.throws(() => parseBatchExecuteRequest({ statusScope: 'pending', accountNum: 0 }), /invalid accountNum/);
  assert.throws(() => parseBatchReprocessRequest({ statusScope: 'later' }), /invalid statusScope/);
});

test('empty legacy requests remain broad for backward compatibility', () => {
  assert.deepEqual(parseBatchExecuteRequest({}), { statusScope: 'all', accountNum: null, explicitScope: false });
  assert.deepEqual(parseBatchReprocessRequest({}), { statusScope: 'all', accountNum: null, explicitScope: false });
});
