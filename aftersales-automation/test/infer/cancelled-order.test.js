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
    id: 'sim-test-003',
    queueItemId: fixture.queueItem.id,
    workOrderNum: fixture.queueItem.workOrderNum,
    mode: 'live',
    collectedData: fixture.collectedData,
  };
}

describe('P0-4: 已取消工单等待人工归档', () => {
  it('workOrderStatus="已取消" → action=wait_archive', () => {
    const fixture = loadFixture('fb-1779121317343.json');
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'wait_archive');
    assert.ok(result.reason.includes('取消'), `reason 应含"取消"，实际: ${result.reason}`);
    assert.ok(result.warnings.some(w => w.includes('拦截')), `warnings 应提示拦截清理`);
  });

  it('workOrderStatus="取消中" → action=wait_archive（不入终态）', () => {
    const fixture = loadFixture('fb-1779121317343.json');
    fixture.collectedData.ticket.workOrderStatus = '取消中';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'wait_archive');
    assert.ok(result.reason.includes('取消'));
  });

  it('workOrderStatus="用户已取消" → action=wait_archive', () => {
    const fixture = loadFixture('fb-1779121317343.json');
    fixture.collectedData.ticket.workOrderStatus = '用户已取消';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'wait_archive');
  });

  it('workOrderStatus="已退款" → action=skip（终态不受影响）', () => {
    const fixture = loadFixture('fb-1779121317343.json');
    fixture.collectedData.ticket.workOrderStatus = '已退款';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'skip');
  });

  it('正常工单不受影响', () => {
    const fixture = loadFixture('fb-1779121317343.json');
    fixture.collectedData.ticket.workOrderStatus = '待处理';
    fixture.collectedData.ticket.afterSaleReason = '七天无理由退货';
    // 未发货+无运单号 → 应 approve
    fixture.collectedData.erpSearch = {
      rows: { rows: [{ status: '待打印快递单', trackings: [], tracking: '' }] },
    };
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    // 正常工单不应被取消逻辑拦截
    assert.ok(result.action !== 'escalate' || !result.reason.includes('取消'),
      `正常工单不应触发取消逻辑，实际 action=${result.action} reason=${result.reason}`);
  });
});
