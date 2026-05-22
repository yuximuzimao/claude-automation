'use strict';
/**
 * 自动执行置信度系统 — 基于"沉默=正确"模型，按场景指纹累积信用。
 * 只有人工反馈才能证明推理正确，系统不能自己给自己累积信用。
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const { MERCHANT_FAULT_REASONS, RETURN_KEYWORDS, SIGNED_KEYWORDS, isMerchantFaultReason } = require('../constants');
const db = require('./data');

const DATA_DIR = path.join(__dirname, '../../data');
const CONFIDENCE_PATH = path.join(DATA_DIR, 'auto-exec-confidence.json');

const AUTO_THRESHOLD_EXECUTIONS = 10;
const AUTO_THRESHOLD_DAYS = 15;

// ── 内存缓存（消除热路径上的同步文件 I/O）─────────────────────────

let _cache = null;

function readConfidence() {
  if (_cache) return _cache;
  try {
    _cache = JSON.parse(fs.readFileSync(CONFIDENCE_PATH, 'utf8'));
    return _cache;
  } catch {
    _cache = { scenes: {} };
    return _cache;
  }
}

function writeConfidence(data) {
  _cache = data;
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
  const isMerchantFault = isMerchantFaultReason(afterSaleReason);
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

// ── 置信度逻辑（共享核心，消除重复）─────────────────────────────────

const STATUS_MANUAL = 'manual';
const STATUS_AUTO = 'auto';

function meetsAutoThreshold(scene) {
  if (scene.totalExecutions < AUTO_THRESHOLD_EXECUTIONS) return false;
  if (!scene.lastNegativeAt) return true;
  return (Date.now() - new Date(scene.lastNegativeAt).getTime()) / 86400000 > AUTO_THRESHOLD_DAYS;
}

function ensureScene(data, sceneKey, dimensions) {
  if (!data.scenes[sceneKey]) {
    data.scenes[sceneKey] = {
      sceneKey,
      sceneLabel: buildSceneLabel(dimensions),
      dimensions,
      totalExecutions: 0,
      negativeCount: 0,
      lastNegativeAt: null,
      status: STATUS_MANUAL,
      autoEnabledAt: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }
  return data.scenes[sceneKey];
}

/**
 * 记录一次好评（人工确认推理正确）。
 * data 参数可选——调用方持有时传入以避免重复读盘。
 */
function recordExecution(sceneKey, _data) {
  const data = _data || readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return;

  scene.totalExecutions += 1;
  scene.updatedAt = new Date().toISOString();

  if (scene.status === STATUS_MANUAL && meetsAutoThreshold(scene)) {
    scene.status = STATUS_AUTO;
    scene.autoEnabledAt = new Date().toISOString();
  }

  if (!_data) writeConfidence(data);
}

/**
 * 记录一次差评（推理错误），立即退出自动执行。
 * data 参数可选——调用方持有时传入以避免重复读盘。
 */
function recordNegative(sceneKey, _data) {
  const data = _data || readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return;

  scene.negativeCount += 1;
  scene.lastNegativeAt = new Date().toISOString();
  scene.status = STATUS_MANUAL;
  scene.autoEnabledAt = null;
  scene.updatedAt = new Date().toISOString();

  if (!_data) writeConfidence(data);
}

function isSceneAutoEligible(sceneKey) {
  const data = readConfidence();
  const scene = data.scenes[sceneKey];
  if (!scene) return false;
  return scene.status === STATUS_AUTO && meetsAutoThreshold(scene);
}

function getAllScenes() {
  return readConfidence().scenes;
}

// ── pipeline 集成 ──────────────────────────────────────────────────

/**
 * pipeline.js 调用：当前工单是否满足自动执行条件？
 * 封装了构建维度→生成场景 key→查询置信度的完整调用链。
 */
function shouldAutoExecute(decision, collectedData, queueItem) {
  if (!decision || decision.action !== 'approve') return false;
  if (!queueItem || !queueItem.type) return false;

  const dimensions = buildDimensions(collectedData, decision, queueItem.type);
  if (!dimensions) return false;

  const sceneKey = buildSceneKey(dimensions);
  return isSceneAutoEligible(sceneKey);
}

// ── 从 feedback 更新置信度 ──────────────────────────────────────────

/**
 * 在 POST /api/feedback 后调用。仅跟踪 approve 决策。
 * simulation 已清理或维度缺失 → 静默跳过。
 * orderType 可选——传入时跳过 queue.json 读取。
 */
function onFeedback(simulation, verdict, orderType) {
  if (!simulation) return;
  const cd = simulation.collectedData;
  const decision = simulation.decision;
  if (!cd || !decision || decision.action !== 'approve') return;

  // orderType：优先用传入值，否则从 queue item 查（兼容旧 simulation）
  if (!orderType) {
    const queue = db.readQueue();
    const qi = queue.items.find(i => i.id === simulation.queueItemId);
    orderType = qi ? qi.type : null;
  }

  const dimensions = buildDimensions(cd, decision, orderType);
  if (!dimensions) return;

  const sceneKey = buildSceneKey(dimensions);

  // 单次读 → 修改 → 单次写
  const data = readConfidence();
  ensureScene(data, sceneKey, dimensions);

  if (verdict === 'negative') {
    recordNegative(sceneKey, data);
  } else {
    recordExecution(sceneKey, data);
  }
  writeConfidence(data);
}

// ── 全量重建（手动修复工具）─────────────────────────────────────────

function recalculate() {
  const simulations = db.readSimulations();
  const feedbacks = db.readFeedback();
  const queue = db.readQueue();  // 读一次，不在循环内重复读

  const fbMap = {};
  for (const fb of feedbacks) {
    if (!fbMap[fb.simulationId]) {
      fbMap[fb.simulationId] = fb.verdict;
    }
  }

  const data = { scenes: {} };

  const ordered = [...simulations].sort((a, b) =>
    (a.createdAt || '').localeCompare(b.createdAt || '')
  );

  for (const sim of ordered) {
    const verdict = fbMap[sim.id];
    if (!verdict) continue;
    if (!sim.decision || sim.decision.action !== 'approve') continue;

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
      scene.status = STATUS_MANUAL;
      scene.autoEnabledAt = null;
    } else {
      scene.totalExecutions += 1;
      if (scene.status === STATUS_MANUAL && meetsAutoThreshold(scene)) {
        scene.status = STATUS_AUTO;
        scene.autoEnabledAt = new Date().toISOString();
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
  shouldAutoExecute,
  onFeedback,
  recalculate,
  AUTO_THRESHOLD_EXECUTIONS,
  AUTO_THRESHOLD_DAYS,
};
