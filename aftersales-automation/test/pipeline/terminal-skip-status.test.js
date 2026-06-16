'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { getSkipCompletionStatus } = require('../../lib/server/pipeline-status');

describe('pipeline terminal skip visibility', () => {
  it('扫描来源的终态 skip 进入已自动执行列表', () => {
    const status = getSkipCompletionStatus({
      source: 'scan',
      mode: 'live',
      workOrderNum: '100001781000000000001',
    });

    assert.equal(status, 'auto_executed');
  });

  it('非扫描来源的终态 skip 仍直接完成', () => {
    const status = getSkipCompletionStatus({
      source: 'web',
      mode: 'live',
      workOrderNum: '100001781000000000002',
    });

    assert.equal(status, 'done');
  });
});
