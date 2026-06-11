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
    id: 'sim-test-001',
    queueItemId: fixture.queueItem.id,
    workOrderNum: fixture.queueItem.workOrderNum,
    mode: 'live',
    collectedData: fixture.collectedData,
  };
}

describe('P0-1: MERCHANT_FAULT_REASONS 包含"质量问题"', () => {
  it('afterSaleReason="质量问题" → escalate 商责', () => {
    const fixture = loadFixture('fb-1778868858729.json');
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'escalate');
    assert.ok(result.reason.includes('商责'), `reason 应含"商责"，实际: ${result.reason}`);
  });

  it('afterSaleReason="商品破损" → 仍正确拦截（回归）', () => {
    const fixture = loadFixture('fb-1778868858729.json');
    fixture.collectedData.ticket.afterSaleReason = '商品破损';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'escalate');
    assert.ok(result.reason.includes('商责'));
  });

  it('afterSaleReason="卖家发错货" → escalate 商责，禁止自动同意退款', () => {
    const fixture = loadFixture('fb-1778868858729.json');
    fixture.queueItem.type = '退货退款';
    fixture.collectedData.ticket.afterSaleReason = '卖家发错货';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    assert.equal(result.action, 'escalate');
    assert.ok(result.reason.includes('商责'), `reason 应含"商责"，实际: ${result.reason}`);
    assert.ok(result.reason.includes('卖家发错货'), `reason 应含原始售后原因，实际: ${result.reason}`);
  });

  it('afterSaleReason="七天无理由退货" → 不被误判为商责', () => {
    const fixture = loadFixture('fb-1778868858729.json');
    fixture.collectedData.ticket.afterSaleReason = '七天无理由退货';
    const sim = makeSim(fixture);
    const result = inferDecision(sim, fixture.queueItem);

    // 非商责应走正常仅退款流程（approve/escalate/reject 都行，但不应该是商责 escalate）
    const rulesApplied = (result.rulesApplied || []).map(r => r.section);
    assert.ok(!rulesApplied.includes('商责拦截'), `不应触发商责拦截，实际 rulesApplied: ${JSON.stringify(rulesApplied)}`);
  });
});
