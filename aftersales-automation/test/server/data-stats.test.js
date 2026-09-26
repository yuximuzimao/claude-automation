'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { computeStatsFromData } = require('../../lib/server/data');

test('累计处理不受 simulation 裁剪影响，并按工单号去重', () => {
  const result = computeStatsFromData({
    simulations: [{
      id: 'sim-current', mode: 'live', workOrderNum: 'WO-2', createdAt: '2026-09-02T00:00:00.000Z',
      decision: { action: 'approve' },
    }],
    queueItems: [
      { id: 'q-1', mode: 'live', workOrderNum: 'WO-1', status: 'done' },
      { id: 'q-2', mode: 'live', workOrderNum: 'WO-2', status: 'auto_executed' },
      { id: 'q-pending', mode: 'live', workOrderNum: 'WO-3', status: 'pending' },
      { id: 'q-training', mode: 'sim', workOrderNum: 'TRAIN-1', status: 'done' },
    ],
    archivedCases: [
      { id: 'case-1', workOrderNum: 'WO-1', addedAt: '2026-09-01T00:00:00.000Z' },
      { id: 'case-1-repeat', workOrderNum: 'WO-1', addedAt: '2026-09-03T00:00:00.000Z' },
    ],
  });

  assert.equal(result.processedTotal, 2);
  assert.equal(result.archivedCount, 2);
  assert.equal(result.activeCount, 2);
});

test('正确率只用每张工单的最新人工评价计算', () => {
  const result = computeStatsFromData({
    queueItems: [
      { id: 'q-1', mode: 'live', workOrderNum: 'WO-1', status: 'done' },
      { id: 'q-2', mode: 'live', workOrderNum: 'WO-2', status: 'done' },
    ],
    archivedCases: [
      { id: 'case-1', workOrderNum: 'WO-1', addedAt: '2026-09-01T00:00:00.000Z', decision: { action: 'approve' } },
      { id: 'case-2', workOrderNum: 'WO-2', addedAt: '2026-09-01T00:00:00.000Z', decision: { action: 'reject' } },
    ],
    feedbacks: [
      { id: 'fb-1-old', workOrderNum: 'WO-1', verdict: 'negative', createdAt: '2026-09-01T00:00:00.000Z' },
      { id: 'fb-1-new', workOrderNum: 'WO-1', verdict: 'positive', createdAt: '2026-09-02T00:00:00.000Z' },
      { id: 'fb-2', workOrderNum: 'WO-2', verdict: 'negative', createdAt: '2026-09-02T00:00:00.000Z' },
    ],
  });

  assert.equal(result.feedbackCount, 2);
  assert.equal(result.positive, 1);
  assert.equal(result.negative, 1);
  assert.equal(result.accuracy, 0.5);
  assert.deepEqual(result.byAction.approve, { total: 1, positive: 1, negative: 0 });
  assert.deepEqual(result.byAction.reject, { total: 1, positive: 0, negative: 1 });
});
