'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { inferDecision } = require('../../lib/infer');

function makeQueueItem(overrides = {}) {
  return {
    id: 'q-scan-gone-001',
    workOrderNum: '100001781088047516685',
    accountNum: 3,
    accountNote: '百浩-RITEKOKO',
    mode: 'live',
    source: 'scan',
    status: 'processing',
    type: '仅退款',
    urgency: '20小时',
    ...overrides,
  };
}

function makeSim(queueItem, collectedData) {
  return {
    id: 'sim-scan-gone-001',
    queueItemId: queueItem.id,
    workOrderNum: queueItem.workOrderNum,
    mode: 'live',
    collectedData,
  };
}

describe('scan live 工单详情页暂时未确认', () => {
  it('read-ticket 已不在待处理列表时不得 skip 自动归档', () => {
    const queueItem = makeQueueItem();
    const sim = makeSim(queueItem, {
      ticket: null,
      erpSearch: null,
      collectErrors: [
        `read-ticket: 工单 ${queueItem.workOrderNum} 已不在待处理列表（可能已处理或已关闭）`,
        'erp-search: 所有子订单搜索均失败',
      ],
    });

    const result = inferDecision(sim, queueItem);

    assert.notEqual(result.action, 'skip');
    assert.notEqual(result.confidence, 'high');
    assert.ok(result.reason.includes('详情页未确认'), `reason 应提示详情页未确认，实际: ${result.reason}`);
  });

  it('页面明确读到已关闭时仍允许 skip 自动归档', () => {
    const queueItem = makeQueueItem();
    const sim = makeSim(queueItem, {
      ticket: {
        workOrderStatus: '已关闭',
      },
      collectErrors: [],
    });

    const result = inferDecision(sim, queueItem);

    assert.equal(result.action, 'skip');
    assert.equal(result.confidence, 'high');
    assert.ok(result.reason.includes('已关闭'), `reason 应保留终态状态，实际: ${result.reason}`);
  });
});
