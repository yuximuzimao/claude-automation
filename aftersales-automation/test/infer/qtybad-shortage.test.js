'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');

const { inferDecision } = require('../../lib/infer');

function loadFixture(name) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, '../fixtures', name), 'utf8'));
}

function makeSim(fixture) {
  return {
    id: 'sim-test-002',
    queueItemId: fixture.queueItem.id,
    workOrderNum: fixture.queueItem.workOrderNum,
    mode: 'live',
    collectedData: fixture.collectedData,
  };
}

describe('P0-2: qtyBad + 缺件统一输出', () => {
  it('仅次品无缺件 → reason 含次品', () => {
    const fixture = loadFixture('fb-1777914640798.json');
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'escalate');
    assert.ok(result.reason.includes('次品'), `reason 应含"次品"，实际: ${result.reason}`);
  });

  it('含次品+缺件(档案有但入库无) → reason 同时包含次品和不足', () => {
    const fixture = loadFixture('fb-1777914640798.json');
    // 档案加一项入库里没有的 → 匹配时会标记 missing
    fixture.collectedData.productArchives[0].subItems.push({
      name: '赠品小样', specCode: 'SPEC002', qty: 1,
    });
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'escalate');
    assert.ok(result.reason.includes('次品'), `reason 应含"次品"，实际: ${result.reason}`);
    assert.ok(result.reason.includes('不足') || result.reason.includes('没有'),
      `reason 应含缺件信息，实际: ${result.reason}`);
  });
});
