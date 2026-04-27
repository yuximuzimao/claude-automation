#!/usr/bin/env node
'use strict';
/**
 * simulate.js - 模拟工单管理工具
 *
 * 子命令：
 *   pending [--live|--sim]         列出已采集但未决策的记录，输出供 Agent 推理
 *   decide <simId> <jsonFile>      写入决策结果（从 JSON 文件读取）
 *   add <工单号> <账号编号> <账号名> [--sim] [--truth approve|reject|escalate]
 *                                   添加工单到队列
 *   import                         从内置案例导入已知历史工单到 cases.jsonl
 *   feedback-summary [--limit N]   输出负向反馈摘要（供修订 docs/）
 */

const path = require('path');
const fs = require('fs');
const db = require('./lib/server/data');

const [,, subcmd, ...rest] = process.argv;

function log(msg) {
  process.stderr.write(msg + '\n');
}

function die(msg) {
  process.stderr.write(`错误: ${msg}\n`);
  process.exit(1);
}

// ── pending ───────────────────────────────────────────────────────────
function cmdPending() {
  const onlyLive = rest.includes('--live');
  const onlySim = rest.includes('--sim');

  let sims = db.readSimulations();
  // 已采集但 decision 为 null 的记录
  sims = sims.filter(s => s.collectedData && !s.decision);
  if (onlyLive) sims = sims.filter(s => s.mode === 'live');
  if (onlySim) sims = sims.filter(s => s.mode === 'sim');

  if (!sims.length) {
    log('没有待决策的模拟记录');
    process.exit(0);
  }

  log(`共 ${sims.length} 条待决策记录`);

  // 输出结构化摘要供 Agent 推理
  const output = sims.map(s => ({
    simId: s.id,
    workOrderNum: s.workOrderNum,
    accountNote: s.accountNote,
    mode: s.mode,
    groundTruth: s.groundTruth,
    collectErrors: s.collectedData.collectErrors,
    // 精简数据（完整数据太大）
    ticketType: s.collectedData.ticket && s.collectedData.ticket.type,
    ticketSummary: s.collectedData.ticket && {
      type: s.collectedData.ticket.type,
      returnReason: s.collectedData.ticket.returnReason,
      amount: s.collectedData.ticket.amount,
      returnTracking: s.collectedData.ticket.returnTracking,
      subOrders: s.collectedData.ticket.subOrders,
      gifts: s.collectedData.ticket.gifts,
    },
    erpOrderStatus: s.collectedData.erpSearch && s.collectedData.erpSearch.status,
    logisticsPackages: s.collectedData.logistics && s.collectedData.logistics.packages && s.collectedData.logistics.packages.length,
    hasGiftErp: !!s.collectedData.giftErpSearch,
    hasAftersale: !!s.collectedData.erpAftersale,
    productMatch: s.collectedData.productMatch,
    // 完整数据路径说明
    note: `完整数据可通过 db.getSimulation("${s.id}") 读取`,
  }));

  console.log(JSON.stringify({ success: true, count: output.length, items: output }, null, 2));
}

// ── decide ────────────────────────────────────────────────────────────
function cmdDecide() {
  const [simId, jsonArg] = rest;
  if (!simId) die('用法: simulate.js decide <simId> <jsonFile 或 inline-JSON>');

  let decision;
  if (jsonArg) {
    if (jsonArg.startsWith('{')) {
      try { decision = JSON.parse(jsonArg); } catch (e) { die(`JSON 解析失败: ${e.message}`); }
    } else if (fs.existsSync(jsonArg)) {
      try { decision = JSON.parse(fs.readFileSync(jsonArg, 'utf8')); } catch (e) { die(`文件读取失败: ${e.message}`); }
    } else {
      die(`文件不存在: ${jsonArg}`);
    }
  } else {
    // 从 stdin 读
    try {
      const raw = fs.readFileSync('/dev/stdin', 'utf8');
      decision = JSON.parse(raw);
    } catch (e) {
      die(`stdin 读取/解析失败: ${e.message}`);
    }
  }

  // 验证 decision 字段
  if (!decision.action || !['approve', 'reject', 'escalate'].includes(decision.action)) {
    die('decision.action 必须是 approve / reject / escalate');
  }
  if (!decision.reason) die('decision.reason 不能为空');

  const sim = db.getSimulation(simId);
  if (!sim) die(`找不到 simId: ${simId}`);

  const updated = db.updateSimulation(simId, {
    decision: {
      action: decision.action,
      reason: decision.reason,
      rulesApplied: decision.rulesApplied || [],
      confidence: decision.confidence || 'medium',
      warnings: decision.warnings || [],
      decidedAt: new Date().toISOString(),
    },
  });

  // 更新队列状态为 simulated
  if (sim.queueItemId) {
    db.updateQueueItem(sim.queueItemId, { status: 'simulated' });
  }

  // 如果有 groundTruth，自动计算是否正确
  let autoFeedback = null;
  if (sim.groundTruth && decision.action) {
    const correct = sim.groundTruth === decision.action;
    autoFeedback = correct ? 'positive' : 'negative';
    log(`自动判定（groundTruth=${sim.groundTruth}，action=${decision.action}）: ${correct ? '✓ 正确' : '✗ 错误'}`);
  }

  console.log(JSON.stringify({
    success: true,
    simId,
    action: decision.action,
    autoFeedback,
    message: autoFeedback
      ? `已写入决策，自动判定为 ${autoFeedback}`
      : '已写入决策，等待人工判定',
  }));
}

// ── add ───────────────────────────────────────────────────────────────
function cmdAdd() {
  const [workOrderNum, accountNumStr, accountNote, ...flags] = rest;
  if (!workOrderNum || !accountNumStr) {
    die('用法: simulate.js add <工单号> <账号编号> [账号名] [--sim] [--truth approve|reject|escalate]');
  }

  const isSim = flags.includes('--sim');
  const truthIdx = flags.indexOf('--truth');
  const groundTruth = truthIdx >= 0 ? flags[truthIdx + 1] : null;

  if (groundTruth && !['approve', 'reject', 'escalate'].includes(groundTruth)) {
    die('--truth 必须是 approve / reject / escalate');
  }

  const item = db.addQueueItem({
    workOrderNum,
    accountNum: parseInt(accountNumStr) || null,
    accountNote: accountNote || `账号${accountNumStr}`,
    mode: isSim ? 'sim' : 'live',
    source: 'cli',
    groundTruth: groundTruth || null,
  });

  if (!item) {
    log(`工单 ${workOrderNum} 已在队列中（未完成），跳过`);
    console.log(JSON.stringify({ success: false, reason: '已存在' }));
    process.exit(0);
  }

  console.log(JSON.stringify({ success: true, item }));
}

// ── import ────────────────────────────────────────────────────────────
// 11 个内置历史已验证案例（来自 memory）
const BUILT_IN_CASES = [
  {
    id: 'case-001',
    workOrderNum: '100001775181776855477',
    accountNote: '账号1 汐澜-鲨鱼',
    type: '退货退款',
    groundTruth: { action: 'reject', reason: '赠品无退回物流', source: 'manual' },
  },
  {
    id: 'case-002',
    workOrderNum: '100001775221834566073',
    accountNote: '账号1 汐澜-鲨鱼',
    type: '退货退款',
    groundTruth: { action: 'approve', reason: '物流退回已确认，金额无误', source: 'manual' },
  },
  {
    id: 'case-003',
    workOrderNum: '100001775231837564973',
    accountNote: '账号3 百浩-RITEKOKO',
    type: '退货退款',
    groundTruth: { action: 'reject', reason: '主商品无退回物流', source: 'manual' },
  },
  {
    id: 'case-004',
    workOrderNum: '100001775241712785549',
    accountNote: '账号3 百浩-RITEKOKO',
    type: '退货退款',
    groundTruth: { action: 'approve', reason: '物流已退回，ERP 状态正常', source: 'manual' },
  },
  {
    id: 'case-005',
    workOrderNum: '100001775261707148589',
    accountNote: '账号5 共途-KGOS',
    type: '换货',
    groundTruth: { action: 'escalate', reason: '换货类型需人工确认规格', source: 'manual' },
  },
  {
    id: 'case-006',
    workOrderNum: '100001775271834546605',
    accountNote: '账号1 汐澜-鲨鱼',
    type: '退货退款',
    groundTruth: { action: 'reject', reason: '退款金额超出ERP订单金额', source: 'manual' },
  },
  {
    id: 'case-007',
    workOrderNum: '100001775291724871341',
    accountNote: '账号3 百浩-RITEKOKO',
    type: '退货退款',
    groundTruth: { action: 'approve', reason: '物流正常，金额匹配', source: 'manual' },
  },
  {
    id: 'case-008',
    workOrderNum: '100001775301792364397',
    accountNote: '账号5 共途-KGOS',
    type: '退货退款',
    groundTruth: { action: 'reject', reason: '赠品有退回但未单独处理', source: 'manual' },
  },
  {
    id: 'case-009',
    workOrderNum: '100001775311834546741',
    accountNote: '账号1 汐澜-鲨鱼',
    type: '仅退款',
    groundTruth: { action: 'escalate', reason: '仅退款无物流需核实原因', source: 'manual' },
  },
  {
    id: 'case-010',
    workOrderNum: '100001775321712785823',
    accountNote: '账号3 百浩-RITEKOKO',
    type: '退货退款',
    groundTruth: { action: 'approve', reason: '退货物流已收到，ERP入库', source: 'manual' },
  },
  {
    id: 'case-011',
    workOrderNum: '100001775331776855891',
    accountNote: '账号5 共途-KGOS',
    type: '退货退款',
    groundTruth: { action: 'reject', reason: '物流单号查询无轨迹', source: 'manual' },
  },
];

function cmdImport() {
  const existing = db.readCases();
  const existingIds = new Set(existing.map(c => c.id));
  const existingNums = new Set(existing.map(c => c.workOrderNum));

  let imported = 0, skipped = 0;

  for (const c of BUILT_IN_CASES) {
    if (existingIds.has(c.id) || existingNums.has(c.workOrderNum)) {
      skipped++;
      continue;
    }
    db.appendCase({
      ...c,
      collectedData: null,
      addedAt: new Date().toISOString(),
    });

    // 同时添加到队列（sim 模式）供采集
    db.addQueueItem({
      workOrderNum: c.workOrderNum,
      accountNum: null,
      accountNote: c.accountNote,
      mode: 'sim',
      source: 'archive',
      groundTruth: c.groundTruth ? c.groundTruth.action : null,
    });

    imported++;
  }

  console.log(JSON.stringify({
    success: true,
    imported,
    skipped,
    total: BUILT_IN_CASES.length,
    message: `导入 ${imported} 条历史案例到 cases.jsonl，已添加到采集队列`,
  }));
}

// ── feedback-summary ──────────────────────────────────────────────────
function cmdFeedbackSummary() {
  const limitIdx = rest.indexOf('--limit');
  const limit = limitIdx >= 0 ? parseInt(rest[limitIdx + 1]) : 50;

  const allFeedback = db.readFeedback({ limit });
  const negative = allFeedback.filter(f => f.verdict === 'negative');
  const positive = allFeedback.filter(f => f.verdict === 'positive');

  if (!negative.length) {
    console.log(JSON.stringify({
      success: true,
      message: '没有负向反馈',
      stats: { total: allFeedback.length, positive: positive.length, negative: 0 },
    }));
    return;
  }

  // 按规则文档分组负向反馈
  const byRule = {};
  const byAction = {};

  for (const fb of negative) {
    const doc = fb.ruleImpact && fb.ruleImpact.doc || '未标注';
    if (!byRule[doc]) byRule[doc] = [];
    byRule[doc].push({
      workOrderNum: fb.workOrderNum,
      reason: fb.reason,
      suggestedAction: fb.suggestedAction,
      suggestion: fb.ruleImpact && fb.ruleImpact.suggestion,
    });

    const sim = db.getSimulation(fb.simulationId);
    const action = sim && sim.decision && sim.decision.action || 'unknown';
    if (!byAction[action]) byAction[action] = 0;
    byAction[action]++;
  }

  // 按频率排序规则文档
  const rulesSorted = Object.entries(byRule)
    .sort((a, b) => b[1].length - a[1].length)
    .map(([doc, cases]) => ({ doc, count: cases.length, cases }));

  console.log(JSON.stringify({
    success: true,
    stats: {
      total: allFeedback.length,
      positive: positive.length,
      negative: negative.length,
      accuracy: allFeedback.length > 0
        ? Math.round((positive.length / allFeedback.length) * 100) + '%'
        : 'N/A',
    },
    byAction,
    byRule: rulesSorted,
    suggestedRuleUpdates: rulesSorted.slice(0, 3).map(r => ({
      doc: r.doc,
      frequency: r.count,
      suggestion: `该文档有 ${r.count} 条负向反馈，建议重点审查`,
      cases: r.cases.map(c => c.reason).slice(0, 3),
    })),
  }, null, 2));
}

// ── 路由 ──────────────────────────────────────────────────────────────
switch (subcmd) {
  case 'pending':         cmdPending(); break;
  case 'decide':          cmdDecide(); break;
  case 'add':             cmdAdd(); break;
  case 'import':          cmdImport(); break;
  case 'feedback-summary': cmdFeedbackSummary(); break;
  default:
    process.stderr.write(`用法: simulate.js <pending|decide|add|import|feedback-summary> [选项]\n`);
    process.exit(1);
}
