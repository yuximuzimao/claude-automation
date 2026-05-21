'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');

const { inferDecision } = require('../../lib/infer');

function makeFixture(overrides = {}) {
  return {
    queueItem: {
      id: 'qi-test-intercept',
      type: '退货退款',
      workOrderNum: '100001779999999999999',
      accountNum: 1,
    },
    collectedData: {
      ticket: {
        workOrderStatus: '待处理',
        afterSaleReason: '七天无理由退货',
        type: '退货退款',
        returnTracking: 'SF9999999999',
        subOrders: [{ id: 'sub-1', attr1: '测试商品', afterSaleNum: 1 }],
      },
      erpSearch: {
        rows: {
          rows: [{
            status: '卖家已收到退货',
            trackings: ['SF9999999999'],
            internalId: 'T001',
            aftersaleRows: [{
              status: '卖家已收到退货',
              receivedItems: [{ name: '测试商品', qtyGood: 1, qtyBad: 0 }],
            }],
          }],
        },
      },
      productArchives: [{
        subOrderId: 'sub-1',
        outerId: 'SPEC001',
        title: '测试商品',
        subItems: [{ name: '测试商品', specCode: 'SPEC001', qty: 1 }],
      }],
      productMatches: [{ subOrderId: 'sub-1', matched: true }],
      intercepted: { tracking: 'SF8888888888', workOrderNum: '100001778888888888888', accountNote: '测试' },
      ...overrides,
    },
  };
}

function makeSim(fixture) {
  return {
    id: 'sim-test-intercept',
    queueItemId: fixture.queueItem.id,
    workOrderNum: fixture.queueItem.workOrderNum,
    mode: 'live',
    collectedData: fixture.collectedData,
  };
}

describe('P1-7: inferRefundReturn 检测已有拦截记录 → warnings', () => {
  it('cd.intercepted 存在时 → warnings 包含拦截提示', () => {
    const fixture = makeFixture();
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.ok(result.warnings.some(w => w.includes('拦截') || w.includes('已有拦截记录')),
      `warnings 应包含拦截提示，实际: ${JSON.stringify(result.warnings)}`);
  });

  it('cd.intercepted 不存在时 → warnings 不含拦截提示', () => {
    const fixture = makeFixture({ intercepted: undefined });
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.ok(!result.warnings.some(w => w.includes('拦截记录')),
      `warnings 不应含拦截提示，实际: ${JSON.stringify(result.warnings)}`);
  });
});
