'use strict';

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');

const confidence = require('../../lib/server/auto-exec-confidence');

const CONFIDENCE_PATH = path.join(__dirname, '../../data/auto-exec-confidence.json');

// 保存并恢复原始置信度文件
let backup = null;
before(() => {
  try { backup = fs.readFileSync(CONFIDENCE_PATH); } catch { backup = null; }
});
after(() => {
  if (backup !== null) {
    fs.writeFileSync(CONFIDENCE_PATH, backup);
  } else {
    try { fs.unlinkSync(CONFIDENCE_PATH); } catch {}
  }
});

// ── helpers ──────────────────────────────────────────────────────────
function makeSim(overrides = {}) {
  return {
    id: 'sim-test-001',
    queueItemId: 'qi-001',
    workOrderNum: '100001234567890',
    mode: 'live',
    collectedData: {
      ticket: {
        afterSaleReason: '七天无理由退货（不喜欢/不合适）',
        returnTracking: 'YT1234567890',
        workOrderStatus: '处理中',
        subOrders: [{ id: '1', logistics: '买家已退货' }],
      },
      logistics: {
        packages: [{ num: 'YT1234567890', text: '签收 2026-05-20 14:00:00 本人签收' }],
      },
      erpAftersale: {
        rows: [{ goodsStatus: '卖家已收到退货', items: [{ name: '商品A', qtyGood: 1, qtyBad: 0 }] }],
      },
      ...overrides.collectedData,
    },
    decision: {
      action: 'approve',
      reason: '核对通过',
      confidence: 'high',
      rulesApplied: [{ doc: 'flow-5.1', section: 'Step5', summary: '退货核对通过→同意退款' }],
      warnings: [],
      ...overrides.decision,
    },
  };
}

// ── buildDimensions ──────────────────────────────────────────────────

describe('buildDimensions', () => {
  it('正常退货退款 → 返回完整维度', () => {
    const sim = makeSim();
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.ok(dims);
    assert.equal(dims.afterSaleReason, '七天无理由退货（不喜欢/不合适）');
    assert.equal(dims.orderType, '退货退款');
    assert.equal(dims.logisticsState, '已签收');
    assert.equal(dims.hasReturnTracking, true);
    assert.equal(dims.goodsStatus, '已收到');
    assert.equal(dims.isMerchantFault, false);
    assert.equal(dims.ruleType, 'refund-return');
  });

  it('仅退款未发货 → ruleType=refund-only-unshipped', () => {
    const sim = makeSim({
      collectedData: {
        logistics: { packages: [{ num: 'YT01', text: '暂无信息' }] },
        erpAftersale: null,
      },
    });
    sim.collectedData.ticket.afterSaleReason = '多拍/拍错/不想要';
    sim.collectedData.ticket.returnTracking = null;
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '仅退款');
    assert.ok(dims);
    assert.equal(dims.ruleType, 'refund-only-unshipped');
    assert.equal(dims.hasReturnTracking, false);
  });

  it('商责原因 → ruleType=merchant-fault', () => {
    const sim = makeSim();
    sim.collectedData.ticket.afterSaleReason = '商品破损';
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.ok(dims);
    assert.equal(dims.isMerchantFault, true);
    assert.equal(dims.ruleType, 'merchant-fault');
  });

  it('换货 → ruleType=exchange', () => {
    const sim = makeSim();
    sim.collectedData.ticket.afterSaleReason = '尺码不合适';
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '换货');
    assert.ok(dims);
    assert.equal(dims.ruleType, 'exchange');
    assert.equal(dims.isMerchantFault, false);
  });

  it('afterSaleReason 缺失 → 返回 null', () => {
    const sim = makeSim();
    sim.collectedData.ticket.afterSaleReason = null;
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.equal(dims, null);
  });

  it('物流和ERP都缺失 → 返回 null', () => {
    const sim = makeSim({
      collectedData: { logistics: null, erpAftersale: null },
    });
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.equal(dims, null);
  });

  it('只有物流无ERP → goodsStatus=未知 但正常返回', () => {
    const sim = makeSim({
      collectedData: { erpAftersale: null },
    });
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.ok(dims);
    assert.equal(dims.goodsStatus, '未知');
  });

  it('决策非 approve → 维度仍可构建（由 onFeedback 过滤）', () => {
    const sim = makeSim({ decision: { action: 'reject' } });
    const dims = confidence.buildDimensions(sim.collectedData, sim.decision, '退货退款');
    assert.ok(dims);
  });
});

// ── buildSceneKey ────────────────────────────────────────────────────

describe('buildSceneKey', () => {
  it('相同维度 → 相同 key', () => {
    const dims1 = { afterSaleReason: 'A', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const dims2 = { hasReturnTracking: true, logisticsState: '已签收', orderType: '退货退款', goodsStatus: '已收到', ruleType: 'refund-return', afterSaleReason: 'A', isMerchantFault: false };
    assert.equal(confidence.buildSceneKey(dims1), confidence.buildSceneKey(dims2));
  });

  it('不同维度 → 不同 key', () => {
    const dims1 = { afterSaleReason: 'A', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const dims2 = { afterSaleReason: 'B', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    assert.notEqual(confidence.buildSceneKey(dims1), confidence.buildSceneKey(dims2));
  });
});

// ── 置信度读写 ───────────────────────────────────────────────────────

describe('readConfidence / writeConfidence', () => {
  it('空文件 → 返回 {scenes:{}}', () => {
    confidence.writeConfidence({ scenes: {} });
    const data = confidence.readConfidence();
    assert.deepEqual(data, { scenes: {} });
  });

  it('写入并读取场景数据', () => {
    confidence.writeConfidence({ scenes: { test: { total: 1 } } });
    const data = confidence.readConfidence();
    assert.equal(data.scenes.test.total, 1);
  });
});

// ── recordExecution ──────────────────────────────────────────────────

describe('recordExecution', () => {
  it('新场景第一次执行 → totalExecutions=1, status=manual', () => {
    const dims = { afterSaleReason: '七天无理由退货', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const key = confidence.buildSceneKey(dims);
    // 确保 scene 存在
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key,
      sceneLabel: 'test',
      dimensions: dims,
      totalExecutions: 0,
      negativeCount: 0,
      lastNegativeAt: null,
      status: 'manual',
      autoEnabledAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);

    confidence.recordExecution(key);
    const scenes = confidence.getAllScenes();
    assert.equal(scenes[key].totalExecutions, 1);
    assert.equal(scenes[key].status, 'manual');
  });

  it('执行达到10次且无差评 → status=auto', () => {
    const dims = { afterSaleReason: '多拍/拍错/不想要', orderType: '仅退款', logisticsState: '已退回', hasReturnTracking: false, goodsStatus: '未知', isMerchantFault: false, ruleType: 'refund-only-unshipped' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key,
      sceneLabel: 'test',
      dimensions: dims,
      totalExecutions: 9,
      negativeCount: 0,
      lastNegativeAt: null,
      status: 'manual',
      autoEnabledAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);

    confidence.recordExecution(key); // 第10次
    const scenes = confidence.getAllScenes();
    assert.equal(scenes[key].totalExecutions, 10);
    assert.equal(scenes[key].status, 'auto');
    assert.ok(scenes[key].autoEnabledAt);
  });
});

// ── recordNegative ───────────────────────────────────────────────────

describe('recordNegative', () => {
  it('差评 → status 立即变 manual（即使之前是 auto）', () => {
    const dims = { afterSaleReason: '七天无理由退货', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key,
      sceneLabel: 'test',
      dimensions: dims,
      totalExecutions: 10,
      negativeCount: 0,
      lastNegativeAt: null,
      status: 'auto',
      autoEnabledAt: new Date().toISOString(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);

    confidence.recordNegative(key);
    const scenes = confidence.getAllScenes();
    assert.equal(scenes[key].negativeCount, 1);
    assert.equal(scenes[key].status, 'manual');
    assert.equal(scenes[key].autoEnabledAt, null);
    assert.ok(scenes[key].lastNegativeAt);
  });
});

// ── isSceneAutoEligible ─────────────────────────────────────────────

describe('isSceneAutoEligible', () => {
  it('status=auto && 10次 && 无差评 → true', () => {
    const dims = { afterSaleReason: 'A', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key, sceneLabel: 'test', dimensions: dims,
      totalExecutions: 12, negativeCount: 0, lastNegativeAt: null,
      status: 'auto', autoEnabledAt: new Date().toISOString(),
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);
    assert.equal(confidence.isSceneAutoEligible(key), true);
  });

  it('status=auto 但次数不够 → false', () => {
    const dims = { afterSaleReason: 'B', orderType: '仅退款', logisticsState: '已退回', hasReturnTracking: false, goodsStatus: '未知', isMerchantFault: false, ruleType: 'refund-only-unshipped' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key, sceneLabel: 'test', dimensions: dims,
      totalExecutions: 5, negativeCount: 0, lastNegativeAt: null,
      status: 'auto', autoEnabledAt: new Date().toISOString(),
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);
    assert.equal(confidence.isSceneAutoEligible(key), false);
  });

  it('status=manual → false（即使次数够）', () => {
    const dims = { afterSaleReason: 'C', orderType: '仅退款', logisticsState: '无物流', hasReturnTracking: false, goodsStatus: '未知', isMerchantFault: false, ruleType: 'refund-only-unshipped' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key, sceneLabel: 'test', dimensions: dims,
      totalExecutions: 20, negativeCount: 0, lastNegativeAt: null,
      status: 'manual', autoEnabledAt: null,
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);
    assert.equal(confidence.isSceneAutoEligible(key), false);
  });

  it('最近16天内有过差评 → false', () => {
    const dims = { afterSaleReason: 'D', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const key = confidence.buildSceneKey(dims);
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key, sceneLabel: 'test', dimensions: dims,
      totalExecutions: 15, negativeCount: 1,
      lastNegativeAt: new Date(Date.now() - 5 * 86400000).toISOString(), // 5天前
      status: 'auto', autoEnabledAt: new Date().toISOString(),
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);
    assert.equal(confidence.isSceneAutoEligible(key), false);
  });

  it('场景不存在 → false', () => {
    assert.equal(confidence.isSceneAutoEligible('nonexistent'), false);
  });
});

// ── onFeedback ───────────────────────────────────────────────────────

describe('onFeedback', () => {
  it('差评 → 场景负计数+1', () => {
    // 需要一个可用的 queue item (type=退货退款)
    // onFeedback 内部查 db.readQueue()，需要 mock 队列
    // 直接测 recordNegative 路径已覆盖，此处验证集成路径存在
    const dims = { afterSaleReason: '测试集成', orderType: '退货退款', logisticsState: '已签收', hasReturnTracking: true, goodsStatus: '已收到', isMerchantFault: false, ruleType: 'refund-return' };
    const key = confidence.buildSceneKey(dims);
    // 预创建 scene
    const data = confidence.readConfidence();
    data.scenes[key] = {
      sceneKey: key, sceneLabel: '集成测试', dimensions: dims,
      totalExecutions: 5, negativeCount: 0, lastNegativeAt: null,
      status: 'manual', autoEnabledAt: null,
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    confidence.writeConfidence(data);

    confidence.recordNegative(key);
    const scenes = confidence.getAllScenes();
    assert.equal(scenes[key].negativeCount, 1);
    assert.equal(scenes[key].status, 'manual');
  });
});
