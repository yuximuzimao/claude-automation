'use strict';
/**
 * WHAT: 自动执行置信度系统 — 基于"沉默=正确"模型，按场景指纹累积信用
 * WHERE: routes.js POST /api/feedback 调用 record*(); pipeline.js shouldAutoExecute() 查询
 * WHY: 只有人工反馈才能证明推理正确，系统不能自己给自己累积信用
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const { MERCHANT_FAULT_REASONS, RETURN_KEYWORDS, SIGNED_KEYWORDS } = require('../constants');

const DATA_DIR = path.join(__dirname, '../../data');
const CONFIDENCE_PATH = path.join(DATA_DIR, 'auto-exec-confidence.json');

const AUTO_THRESHOLD_EXECUTIONS = 10;
const AUTO_THRESHOLD_DAYS = 15;

// ── 原子读写 ────────────────────────────────────────────────────────

function readConfidence() {
  try {
    const raw = fs.readFileSync(CONFIDENCE_PATH, 'utf8');
    return JSON.parse(raw);
  } catch {
    return { scenes: {} };
  }
}

function writeConfidence(data) {
  const tmp = CONFIDENCE_PATH + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, CONFIDENCE_PATH);
}

// ── 物流状态提取 ─────────────────────────────────────────────────────

function extractLogisticsState(logistics) {
  if (!logistics) return null;
  const packages = logistics.packages || [];
  if (!packages.length) return null;

  const allText = packages.map(p => p.text || '').join(' ');

  if (RETURN_KEYWORDS.some(kw => allText.includes(kw))) return '已退回';
  if (SIGNED_KEYWORDS.some(kw => allText.includes(kw))) return '已签收';
  if (allText.includes('暂无信息')) return '无物流';
  if (/在途|运输中|转运中/.test(allText)) return '在途';
  if (/驿站|菜鸟|快递柜|自提柜/.test(allText)) return '驿站';
  if (/已发货|发货时间/.test(allText) && !/已签收|签收/.test(allText)) return '已发货';
  return '其他';
}

// ── ERP 货物状态标准化 ──────────────────────────────────────────────

function extractGoodsStatus(erpAftersale) {
  if (!erpAftersale) return null;
  const rows = erpAftersale.rows || [];
  if (!rows.length) return null;
  const status = rows[0].goodsStatus || '';
  if (!status) return null;
  if (status.includes('已收到')) return '已收到';
  if (status.includes('在途')) return '在途';
  if (status.includes('待拆包') || status.includes('待入库')) return '待入库';
  return status;
}

// ── 规则类型推导 ─────────────────────────────────────────────────────

function deriveRuleType(orderType, isMerchantFault, logisticsState) {
  if (isMerchantFault) return 'merchant-fault';
  if (orderType === '换货') return 'exchange';
  if (orderType === '退货退款') return 'refund-return';
  if (orderType === '仅退款') {
    if (logisticsState === '已发货' || logisticsState === '在途') return 'refund-only-shipped';
    return 'refund-only-unshipped';
  }
  return 'other';
}

// ── 场景指纹 ────────────────────────────────────────────────────────

/**
 * 从采集数据和决策中提取场景维度。
 * 关键字段缺失 → 返回 null（不参与置信度学习）
 */
function buildDimensions(collectedData, decision, orderType) {
  if (!collectedData || !decision || !orderType) return null;

  const ticket = collectedData.ticket || {};
  const logistics = collectedData.logistics;
  const erpAftersale = collectedData.erpAftersale;

  const afterSaleReason = ticket.afterSaleReason || null;
  if (!afterSaleReason) return null;

  const logisticsState = extractLogisticsState(logistics);
  const goodsStatus = extractGoodsStatus(erpAftersale);

  // 关键字段缺失 → 不参与
  if (!logisticsState && !goodsStatus) return null;

  const hasReturnTracking = !!ticket.returnTracking;
  const isMerchantFault = MERCHANT_FAULT_REASONS.some(kw => afterSaleReason.includes(kw));
  const ruleType = deriveRuleType(orderType, isMerchantFault, logisticsState);

  return {
    afterSaleReason,
    orderType,
    logisticsState: logisticsState || '未知',
    hasReturnTracking,
    goodsStatus: goodsStatus || '未知',
    isMerchantFault,
    ruleType,
  };
}

function buildSceneKey(dimensions) {
  const stable = JSON.stringify(dimensions, Object.keys(dimensions).sort());
  return crypto.createHash('md5').update(stable).digest('hex').slice(0, 12);
}

function buildSceneLabel(dimensions) {
  const parts = [dimensions.afterSaleReason, dimensions.orderType];
  if (dimensions.logisticsState !== '未知') parts.push(dimensions.logisticsState);
  if (dimensions.hasReturnTracking) parts.push('有退货单号');
  return parts.join(' / ');
}

// ── 置信度记录 ───────────────────────────────────────────────────────

function ensureScene(data, sceneKey, dimensions) {
  if (!data.scenes[sceneKey]) {
    data.scenes[sceneKey] = {
      sceneKey,
      sceneLabel: buildSceneLabel(dimensions),
      dimensions,
      totalExecutions: 0,
      negativeCount: 0,
      lastNegativeAt: null,
      status: 'manual',
      autoEnabledAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }
  return data.scenes[sceneKey];
}

function checkAutoEligible(scene) {
  if (scene.status !== 'auto') return false;
  if (scene.totalExecutions < AUTO_THRESHOLD_EXECUTIONS) return false;
  if (scene.lastNegativeAt) {
    const daysSinceNegative = (Date.now() - new Date(scene.lastNegativeAt).getTime()) / 86400000;
    if (daysSinceNegative <= AUTO_THRESHOLD_DAYS) return false;
  }
  return true;
}

function recordExecution(sceneKey) {
  const data = readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return; // buildDimensions 返回 null 时不创建

  scene.totalExecutions += 1;
  scene.updatedAt = new Date().toISOString();

  // 检查是否该升级为 auto
  if (scene.status === 'manual' && scene.totalExecutions >= AUTO_THRESHOLD_EXECUTIONS) {
    if (!scene.lastNegativeAt ||
        (Date.now() - new Date(scene.lastNegativeAt).getTime()) / 86400000 > AUTO_THRESHOLD_DAYS) {
      scene.status = 'auto';
      scene.autoEnabledAt = new Date().toISOString();
    }
  }

  writeConfidence(data);
}

function recordNegative(sceneKey) {
  const data = readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return;

  scene.negativeCount += 1;
  scene.lastNegativeAt = new Date().toISOString();
  scene.status = 'manual';
  scene.autoEnabledAt = null;
  scene.updatedAt = new Date().toISOString();

  writeConfidence(data);
}

function isSceneAutoEligible(sceneKey) {
  const data = readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return false;
  return checkAutoEligible(scene);
}

function getAllScenes() {
  return readConfidence().scenes;
}

// ── 从 feedback 更新置信度 ──────────────────────────────────────────

/**
 * 在 POST /api/feedback 后调用。
 * simulation 已清理或维度缺失 → 静默跳过。
 */
function onFeedback(simulation, verdict) {
  if (!simulation) return;
  const cd = simulation.collectedData;
  const decision = simulation.decision;
  if (!cd || !decision) return;

  // 仅跟踪 approve 决策（只有同意退款才可能自动执行）
  if (decision.action !== 'approve') return;

  // orderType 从 collectedData 推导（queueItem.type 在 simulation 中没有直接存储）
  // ticket 里可能有类型信息，或从 simulation 关联的 queue item 获取
  // 这里通过 simulation 的 queueItemId 查找
  const db = require('./data');
  const queue = db.readQueue();
  const qi = queue.items.find(i => i.id === simulation.queueItemId);
  const orderType = qi ? qi.type : null;

  const dimensions = buildDimensions(cd, decision, orderType);
  if (!dimensions) return;

  const sceneKey = buildSceneKey(dimensions);

  // 确保 scene 存在
  const data = readConfidence();
  ensureScene(data, sceneKey, dimensions);
  writeConfidence(data);

  if (verdict === 'negative') {
    recordNegative(sceneKey);
  } else {
    recordExecution(sceneKey);
  }
}

// ── 全量重建（手动修复工具）─────────────────────────────────────────

function recalculate() {
  const db = require('./data');
  const simulations = db.readSimulations();
  const feedbacks = db.readFeedback();

  // fbMap: simulationId → verdict
  const fbMap = {};
  for (const fb of feedbacks) {
    if (!fbMap[fb.simulationId]) {
      fbMap[fb.simulationId] = fb.verdict;
    }
  }

  const data = { scenes: {} };

  // 按时间顺序处理（旧→新），模拟历史演进
  const ordered = [...simulations].sort((a, b) =>
    (a.createdAt || '').localeCompare(b.createdAt || '')
  );

  for (const sim of ordered) {
    const verdict = fbMap[sim.id];
    if (!verdict) continue;
    if (!sim.decision || sim.decision.action !== 'approve') continue;

    const queue = db.readQueue();
    const qi = queue.items.find(i => i.id === sim.queueItemId);
    const orderType = qi ? qi.type : null;

    const dimensions = buildDimensions(sim.collectedData, sim.decision, orderType);
    if (!dimensions) continue;

    const sceneKey = buildSceneKey(dimensions);
    ensureScene(data, sceneKey, dimensions);

    const scene = data.scenes[sceneKey];
    if (verdict === 'negative') {
      scene.negativeCount += 1;
      scene.lastNegativeAt = fb.createdAt || sim.createdAt;
      scene.status = 'manual';
      scene.autoEnabledAt = null;
    } else {
      scene.totalExecutions += 1;
      // 检查升级
      if (scene.status === 'manual' && scene.totalExecutions >= AUTO_THRESHOLD_EXECUTIONS) {
        if (!scene.lastNegativeAt ||
            (Date.now() - new Date(scene.lastNegativeAt).getTime()) / 86400000 > AUTO_THRESHOLD_DAYS) {
          scene.status = 'auto';
          scene.autoEnabledAt = new Date().toISOString();
        }
      }
    }
    scene.updatedAt = new Date().toISOString();
  }

  writeConfidence(data);
  return data;
}

module.exports = {
  buildDimensions,
  buildSceneKey,
  buildSceneLabel,
  readConfidence,
  writeConfidence,
  recordExecution,
  recordNegative,
  isSceneAutoEligible,
  getAllScenes,
  onFeedback,
  recalculate,
  AUTO_THRESHOLD_EXECUTIONS,
  AUTO_THRESHOLD_DAYS,
};
