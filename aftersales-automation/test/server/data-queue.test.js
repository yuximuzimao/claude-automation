'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { buildQueueItem } = require('../../lib/server/data');

test('生产 queue 白名单保留平台阶段和确认无需处理记录', () => {
  const platformStage = {
    raw: '商家-待商家二次发货',
    observedAt: '2026-08-10T03:00:00.000Z',
    source: 'after-sale-list',
    readState: 'read',
  };
  const confirmedNoAction = {
    caseId: 'exchange_waiting_merchant_reship',
    stage: '商家-待商家二次发货',
    confirmedAt: '2026-08-10T04:00:00.000Z',
  };
  const item = buildQueueItem({
    workOrderNum: '100001785233662360131',
    accountNum: '3',
    type: '换货',
    platformStage,
    confirmedNoAction,
  }, 'q-test', '2026-08-10T02:00:00.000Z');

  assert.equal(item.id, 'q-test');
  assert.equal(item.status, 'pending');
  assert.deepEqual(item.platformStage, platformStage);
  assert.deepEqual(item.confirmedNoAction, confirmedNoAction);
});
