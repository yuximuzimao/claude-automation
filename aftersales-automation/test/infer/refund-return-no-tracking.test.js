'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { inferDecision } = require('../../lib/infer');

function inferNoTracking(afterSaleReason) {
  return inferDecision({
    id: 'sim-no-return-tracking',
    workOrderNum: 'test-no-return-tracking',
    collectedData: {
      ticket: {
        afterSaleReason,
        buyerRemark: '无',
        returnTracking: '',
      },
      collectErrors: [],
    },
  }, {
    type: '退货退款',
    workOrderNum: 'test-no-return-tracking',
    hint: null,
  });
}

describe('七天无理由退货退款无退货单号', () => {
  for (const reason of ['七天无理由退货', '七天无理由退货（不喜欢/不合适）']) {
    it(`${reason} → 转人工并提醒查询特殊退货`, () => {
      const decision = inferNoTracking(reason);

      assert.equal(decision.action, 'escalate');
      assert.equal(
        decision.reason,
        '无退货快递单号，可能为超期特殊退货或次品特殊处理，请人工查询并判断是否可以同意提前无理由退货'
      );
      assert.equal(decision.reasonCode, undefined);
    });
  }
});
