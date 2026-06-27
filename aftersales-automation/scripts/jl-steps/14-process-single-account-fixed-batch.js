#!/usr/bin/env node
'use strict';

const { matchShopName } = require('../../lib/jl/login-state');
const { getSkipCompletionStatus } = require('../../lib/server/pipeline-status');
const { UNFINISHED_INTENT_BLOCK_REASON } = require('../../lib/server/auto-execution-journal');

const MAX_PAGES = 20;
const JL_HOST_SUFFIX = 'jlsupp.com';
const AFTER_SALE_LIST_PATH = '/micro-customer/business/after-sale-list';

function cloneSnapshot(items) {
  return JSON.parse(JSON.stringify(items || []));
}

function assertAccountNum(value) {
  const accountNum = String(value == null ? '' : value).trim();
  if (!/^\d+$/.test(accountNum)) throw new Error('缺少合法 accountNum');
  return accountNum;
}

function assertWorkOrderNum(value) {
  const workOrderNum = String(value == null ? '' : value).trim();
  if (!/^100001\d{12,}$/.test(workOrderNum)) throw new Error(`非法工单号: ${workOrderNum}`);
  return workOrderNum;
}

function targetIdOf(target) {
  return target && (target.id || target.targetId) || null;
}

function parseUrl(value) {
  try { return new URL(String(value || '')); } catch { return null; }
}

function isJlTarget(target) {
  const url = parseUrl(target && target.url);
  return Boolean(url && url.hostname.replace(/^\./, '').endsWith(JL_HOST_SUFFIX));
}

function isAfterSaleListTarget(target) {
  const url = parseUrl(target && target.url);
  return Boolean(url && url.hostname.replace(/^\./, '').endsWith(JL_HOST_SUFFIX) && url.pathname === AFTER_SALE_LIST_PATH);
}

function findTargetById(targets, targetId) {
  return (targets || []).find(target => targetIdOf(target) === targetId) || null;
}

async function assertCurrentAccountShop(targetId, context, dependencies) {
  const accountNote = context && context.account && context.account.matchedNote;
  if (!accountNote) return;
  if (typeof dependencies.readShopName !== 'function') {
    throw new Error('缺少 readShopName 店铺校验依赖，拒绝操作当前账号鲸灵 tab');
  }
  const state = await dependencies.readShopName(targetId, 0);
  if (!state || state.success !== true || state.state !== 'logged-in') {
    throw new Error(`标签页店铺态不可信: ${targetId} ${(state && state.error) || state && state.state || 'unknown'}`);
  }
  if (!matchShopName(state.shopName, accountNote)) {
    throw new Error(`拒绝操作非当前账号鲸灵 tab: 页面店铺="${state.shopName || ''}"，目标店铺="${accountNote}"`);
  }
}

async function assertCurrentAccountListTarget(listTargetId, context, dependencies) {
  if (!listTargetId) throw new Error('缺少售后列表主 tab targetId');
  const targets = await dependencies.getTargets();
  const target = findTargetById(targets, listTargetId);
  if (!target) throw new Error(`售后列表主 tab 不存在: ${listTargetId}`);
  if (!isJlTarget(target)) throw new Error(`售后列表主 tab 不是鲸灵域: ${target.url || listTargetId}`);
  if (!isAfterSaleListTarget(target)) throw new Error(`售后列表主 tab 不在售后列表页: ${target.url || listTargetId}`);
  await assertCurrentAccountShop(listTargetId, context, dependencies);
  return target;
}

async function assertClosableCurrentAccountDetailTarget(detailTargetId, context, dependencies) {
  if (!detailTargetId) throw new Error('缺少待关闭详情 tab targetId');
  if (context && context.listTargetId && detailTargetId === context.listTargetId) {
    throw new Error('拒绝关闭售后列表主 tab');
  }
  const targets = await dependencies.getTargets();
  const target = findTargetById(targets, detailTargetId);
  if (!target) throw new Error(`待关闭详情 tab 不存在: ${detailTargetId}`);
  if (!isJlTarget(target)) throw new Error(`拒绝关闭非鲸灵标签页: ${target.url || detailTargetId}`);
  if (isAfterSaleListTarget(target)) throw new Error(`拒绝关闭售后列表页 tab: ${target.url || detailTargetId}`);
  await assertCurrentAccountShop(detailTargetId, context, dependencies);
  return target;
}

function stepError(stepName, result, fallback = '未知错误') {
  return new Error(`${stepName}: ${(result && result.error) || fallback}`);
}

function activeNumericPages(pagination) {
  return (pagination && Array.isArray(pagination.pages) ? pagination.pages : [])
    .filter(item => item && /^\d+$/.test(String(item.text)))
    .map(item => ({
      ...item,
      number: Number(item.text),
    }));
}

function assertTrustedPagination(pageData) {
  const pagination = pageData && pageData.pagination;
  const pages = activeNumericPages(pagination);
  const active = pages.filter(item => item.active);
  if (pageData && pageData.loading === true) throw new Error('分页状态不可信: 工单列表仍在加载');
  if (!pagination || !Number.isSafeInteger(pagination.totalCount) || pagination.totalCount < 0) {
    throw new Error('分页状态不可信: 缺少有效工单总数');
  }
  if (!Number.isSafeInteger(pagination.currentPage) || pagination.currentPage < 1) {
    throw new Error('分页状态不可信: 缺少当前页码');
  }
  if (active.length !== 1 || active[0].number !== pagination.currentPage) {
    throw new Error('分页状态不可信: 激活页码与当前页不一致');
  }
  const expectedPages = Math.max(1, Math.ceil(pagination.totalCount / 10));
  if (pagination.currentPage > expectedPages) throw new Error('分页状态不可信: 当前页超过总数推导页数');
  return { pagination, pages };
}

function containsWorkOrder(pageData, workOrderNum) {
  return (pageData && Array.isArray(pageData.tickets) ? pageData.tickets : [])
    .some(ticket => ticket && String(ticket.workOrderNum) === workOrderNum);
}

function isConfirmedSinglePage(pagination, pages) {
  return pagination.totalCount <= 10 &&
    pagination.currentPage === 1 &&
    pages.length === 1 &&
    pages[0].number === 1 &&
    pages[0].active &&
    pagination.hasNext === false &&
    pagination.nextButton &&
    pagination.nextButton.disabled === true;
}

function ticketFingerprint(pageData) {
  return (pageData && Array.isArray(pageData.tickets) ? pageData.tickets : [])
    .map(ticket => ticket && ticket.workOrderNum).join('|');
}

function createWaitForPage(waitForFn) {
  return (targetId, expectedPage, readPage, beforeState) => {
    let previousFingerprint = null;
    let stableReads = 0;
    const beforeFingerprint = beforeState ? ticketFingerprint(beforeState) : null;
    return waitForFn(async () => {
      const state = await readPage();
      if (!state || state.loading || !state.pagination || state.pagination.currentPage !== expectedPage) return null;
      if (!Number.isSafeInteger(state.pagination.totalCount) || state.pagination.totalCount < 0) return null;
      const minimumOffset = (expectedPage - 1) * 10;
      if (state.pagination.totalCount > minimumOffset && state.tickets.length === 0) return null;
      const fingerprint = ticketFingerprint(state);
      if (beforeState && beforeState.pagination && beforeState.pagination.currentPage !== expectedPage && fingerprint === beforeFingerprint) {
        stableReads = 0;
        previousFingerprint = fingerprint;
        return null;
      }
      stableReads = fingerprint === previousFingerprint ? stableReads + 1 : 1;
      previousFingerprint = fingerprint;
      return stableReads >= 2 ? state : null;
    }, { timeoutMs: 8000, intervalMs: 500, label: `等待售后列表第${expectedPage}页刷新` });
  };
}

function createCircuitReader(readFile, filePath) {
  return () => {
    try { return JSON.parse(readFile(filePath, 'utf8')); } catch (error) {
      if (error && error.code === 'ENOENT') return null;
      throw error;
    }
  };
}

function createAutoExecutionGate({ readCircuit, executionJournal, readSimulations }) {
  if (typeof readCircuit !== 'function') throw new Error('自动执行安全门缺少 readCircuit');
  if (!executionJournal || typeof executionJournal.getUnfinishedIntent !== 'function') {
    throw new Error('自动执行安全门缺少 executionJournal');
  }
  if (typeof readSimulations !== 'function') throw new Error('自动执行安全门缺少 readSimulations');

  return async ({ ticket }) => {
    const workOrderNum = ticket && ticket.workOrderNum;
    if (!workOrderNum) throw new Error('自动执行安全门缺少工单号');
    const circuit = readCircuit();
    if (circuit && circuit.tripped) return { allowed: false, reason: '风控熔断中' };
    const unfinishedIntent = executionJournal.getUnfinishedIntent(workOrderNum);
    if (unfinishedIntent) return { allowed: false, reason: UNFINISHED_INTENT_BLOCK_REASON };
    const duplicate = readSimulations().some(simulation =>
      simulation.workOrderNum === workOrderNum &&
      simulation.mode === 'live' &&
      simulation.executedAt &&
      simulation.decision &&
      simulation.decision.action !== 'skip'
    );
    return duplicate
      ? { allowed: false, reason: '已有真实执行记录，禁止重复执行' }
      : { allowed: true };
  };
}

async function clickPageOneLikeHuman(targetId, dependencies) {
  const before = await dependencies.readCurrentPage(targetId);
  const { pagination, pages } = assertTrustedPagination(before);
  if (pagination.currentPage === 1) return pagination;

  const firstPage = pages.find(item => item.number === 1);
  if (!firstPage || !firstPage.rect || !Number.isFinite(firstPage.rect.centerX) || !Number.isFinite(firstPage.rect.centerY)) {
    throw new Error('无法切回第一页: 页码1不可见或缺少点击坐标');
  }

  const eventBase = { x: firstPage.rect.centerX, y: firstPage.rect.centerY };
  await dependencies.dispatchMouseEvent({ type: 'mouseMoved', ...eventBase });
  await dependencies.sleep(100);
  await dependencies.dispatchMouseEvent({ type: 'mousePressed', ...eventBase, button: 'left', clickCount: 1 });
  await dependencies.sleep(100);
  await dependencies.dispatchMouseEvent({ type: 'mouseReleased', ...eventBase, button: 'left', clickCount: 1 });
  await dependencies.sleep(1500);

  const after = typeof dependencies.waitForPage === 'function'
    ? await dependencies.waitForPage(targetId, 1, () => dependencies.readCurrentPage(targetId), before)
    : await dependencies.readCurrentPage(targetId);
  const trusted = assertTrustedPagination(after);
  if (trusted.pagination.currentPage !== 1) {
    throw new Error(`切回第一页失败: 当前仍为第${trusted.pagination.currentPage}页`);
  }
  return after;
}

async function locateWorkOrderOnFreshList(targetId, workOrderNum, dependencies, options = {}) {
  const order = assertWorkOrderNum(workOrderNum);
  const maxPages = options.maxPages || MAX_PAGES;
  let current = await dependencies.readCurrentPage(targetId);
  let trusted = assertTrustedPagination(current);

  if (containsWorkOrder(current, order)) {
    return { found: true, workOrderNum: order, page: trusted.pagination.currentPage, pagesChecked: [trusted.pagination.currentPage] };
  }
  if (isConfirmedSinglePage(trusted.pagination, trusted.pages)) {
    return {
      found: false,
      gone: true,
      reason: '单页待处理列表未找到目标工单',
      pagesChecked: [1],
    };
  }

  if (trusted.pagination.currentPage !== 1) {
    const pageOne = await dependencies.clickPageOne(targetId);
    if (pageOne && pageOne.pagination && pageOne.pagination.currentPage === 1 && Array.isArray(pageOne.tickets)) {
      current = pageOne;
    } else {
      current = await dependencies.readCurrentPage(targetId);
    }
    trusted = assertTrustedPagination(current);
    if (trusted.pagination.currentPage !== 1) throw new Error('回到第一页后页码验证失败');
  }

  const pagesChecked = [];
  for (let checked = 0; checked < maxPages; checked++) {
    trusted = assertTrustedPagination(current);
    const pageNumber = trusted.pagination.currentPage;
    if (!pagesChecked.includes(pageNumber)) pagesChecked.push(pageNumber);
    if (containsWorkOrder(current, order)) {
      return { found: true, workOrderNum: order, page: pageNumber, pagesChecked };
    }

    if (!trusted.pagination.hasNext) {
      if (!trusted.pagination.nextButton || trusted.pagination.nextButton.disabled !== true) {
        throw new Error('分页状态不可信: 未确认下一页按钮已禁用');
      }
      const expectedPages = Math.max(1, Math.ceil(trusted.pagination.totalCount / 10));
      if (pageNumber !== expectedPages) {
        throw new Error(`分页状态不可信: 当前第${pageNumber}页，但总数推导末页为第${expectedPages}页`);
      }
      return {
        found: false,
        gone: true,
        reason: '完整遍历待处理列表后未找到目标工单',
        pagesChecked,
      };
    }

    if (checked === maxPages - 1) throw new Error(`达到最大页数 ${maxPages}，不能判定工单消失`);
    const next = await dependencies.clickNextPage(targetId);
    if (!next || next.clicked !== true) {
      throw new Error(`翻页失败: ${(next && next.reason) || '下一页点击未确认'}`);
    }
    const expectedPage = pageNumber + 1;
    current = typeof dependencies.waitForPage === 'function'
      ? await dependencies.waitForPage(targetId, expectedPage, () => dependencies.readCurrentPage(targetId), current)
      : await dependencies.readCurrentPage(targetId);
    const after = assertTrustedPagination(current);
    if (after.pagination.currentPage !== expectedPage) {
      throw new Error(`翻页后页码未变化: 期望${expectedPage}，实际${after.pagination.currentPage}`);
    }
  }

  throw new Error(`达到最大页数 ${maxPages}，不能判定工单消失`);
}

async function closeAndVerifyDetailTarget(detailTargetId, dependencies, context = {}) {
  await assertClosableCurrentAccountDetailTarget(detailTargetId, context, dependencies);
  await dependencies.closeTarget(detailTargetId);
  const targets = await dependencies.getTargets();
  if ((targets || []).some(target => targetIdOf(target) === detailTargetId)) {
    throw new Error(`详情标签页关闭验证失败: ${detailTargetId}`);
  }
}

async function cleanupCurrentAccountJlTargets(context, dependencies) {
  const listTargetId = context && context.listTargetId;
  await assertCurrentAccountListTarget(listTargetId, context, dependencies);

  const before = await dependencies.getTargets();
  const closeIds = [];
  for (const target of before || []) {
    const targetId = targetIdOf(target);
    if (!targetId || targetId === listTargetId || !isJlTarget(target)) continue;
    if (context && context.account && context.account.matchedNote && typeof dependencies.readShopName === 'function') {
      const state = await dependencies.readShopName(targetId, 0);
      if (!state || state.success !== true || state.state !== 'logged-in') {
        throw new Error(`账号收尾清理遇到不可信鲸灵 tab: ${target.url || targetId}`);
      }
      if (!matchShopName(state.shopName, context.account.matchedNote)) continue;
    }
    await assertClosableCurrentAccountDetailTarget(targetId, context, dependencies);
    closeIds.push(targetId);
  }

  for (const targetId of closeIds) {
    await dependencies.closeTarget(targetId);
  }

  await assertCurrentAccountListTarget(listTargetId, context, dependencies);
  const after = await dependencies.getTargets();
  const remainingCurrentAccountJlTargets = [];
  for (const target of after || []) {
    const targetId = targetIdOf(target);
    if (!targetId || targetId === listTargetId || !isJlTarget(target)) continue;
    if (context && context.account && context.account.matchedNote && typeof dependencies.readShopName === 'function') {
      const state = await dependencies.readShopName(targetId, 0);
      if (state && state.success === true && state.state === 'logged-in' && matchShopName(state.shopName, context.account.matchedNote)) {
        remainingCurrentAccountJlTargets.push(targetId);
      }
      continue;
    }
    remainingCurrentAccountJlTargets.push(targetId);
  }
  if (remainingCurrentAccountJlTargets.length) {
    throw new Error(`账号收尾后仍残留当前账号鲸灵 tab: ${remainingCurrentAccountJlTargets.join(', ')}`);
  }
  return { closedTargetIds: closeIds };
}

async function processOpenedDetail(context, dependencies) {
  const collectedData = await dependencies.collectDetail(context);
  const decision = await dependencies.inferDecision(collectedData, context.ticket);
  if (context && context.disableAutoExecute === true) {
    return {
      status: 'simulated',
      collectedData,
      decision,
      autoBlockedReason: 'fixed_batch 已显式关闭自动执行',
    };
  }
  const auto = await dependencies.shouldAutoExecute(decision, collectedData, context.ticket);
  if (!auto) return { status: 'simulated', collectedData, decision };
  if (typeof dependencies.assertAutoExecutionAllowed === 'function') {
    const gate = await dependencies.assertAutoExecutionAllowed({ ...context, collectedData, decision });
    if (!gate || gate.allowed !== true) {
      return {
        status: 'simulated',
        collectedData,
        decision,
        autoBlockedReason: (gate && gate.reason) || '自动执行安全门拒绝',
      };
    }
  }

  if (typeof dependencies.reserveAutoExecution !== 'function' || typeof dependencies.markAutoExecuted !== 'function') {
    throw new Error('自动执行安全配置缺失: execution journal 未装配');
  }
  await dependencies.reserveAutoExecution({ ...context, collectedData, decision });

  const execution = await dependencies.executeDecision({ ...context, collectedData, decision });
  if (!execution || !execution.success) throw stepError('自动执行失败', execution);
  await dependencies.markAutoExecuted({ ...context, collectedData, decision, execution });
  return { status: 'auto_executed', collectedData, decision, execution };
}

async function reportProgress(dependencies, item) {
  if (typeof dependencies.onProgress === 'function') {
    await dependencies.onProgress(cloneSnapshot(item));
  }
}

function buildUrgency(ticket) {
  if (ticket && ticket.remaining) return ticket.remaining;
  if (ticket && ticket.days !== undefined && ticket.hours !== undefined) {
    return ticket.days > 0 ? `${ticket.days}天${ticket.hours}小时` : `${ticket.hours}小时`;
  }
  if (ticket && ticket.totalHours != null) return `${Math.max(0, Math.floor(Number(ticket.totalHours)))}小时`;
  return '时间解析失败';
}

function buildDeadlineAt(ticket) {
  if (!ticket) return null;
  if (ticket.deadlineAt) return ticket.deadlineAt;
  if (ticket.totalHours == null) return null;
  const hours = Number(ticket.totalHours);
  if (!Number.isFinite(hours)) return null;
  return new Date(Date.now() + hours * 3600000).toISOString();
}

function createEnsureQueueItem(db) {
  if (!db || typeof db.readQueue !== 'function' || typeof db.updateQueueItem !== 'function' || typeof db.addQueueItem !== 'function') {
    throw new Error('ensureQueueItem 缺少 queue 数据依赖');
  }
  return async ({ account, ticket }) => {
    const queue = db.readQueue();
    const existing = (queue.items || []).find(item => item.workOrderNum === ticket.workOrderNum && item.status !== 'done');
    const patch = {
      mode: 'live',
      source: 'fixed_batch',
      accountNum: account.accountNum || null,
      accountNote: account.matchedNote || ticket.accountNote || '',
      type: ticket.type || null,
      urgency: buildUrgency(ticket),
      deadlineAt: buildDeadlineAt(ticket),
    };
    if (existing) return db.updateQueueItem(existing.id, patch) || { ...existing, ...patch };
    const added = db.addQueueItem({
      workOrderNum: ticket.workOrderNum,
      ...patch,
    });
    if (added) return added;
    const refreshed = db.readQueue();
    return (refreshed.items || []).find(item => item.workOrderNum === ticket.workOrderNum && item.status !== 'done');
  };
}

function buildGoneDecision(ticket, located) {
  const reason = '该工单已不在待商家处理列表，可能已处理、取消、关闭或状态变化；系统未自动判断终态。';
  return {
    action: 'escalate',
    reason,
    confidence: 'low',
    inferredAt: new Date().toISOString(),
    rulesApplied: [{ doc: 'A1-fixed-batch', section: 'gone_from_pending', summary: '固定清单工单从待商家处理列表消失，保留待确认人工复核' }],
    warnings: [reason, located && located.reason].filter(Boolean),
    context: { workOrderNum: ticket && ticket.workOrderNum, goneFromPending: true },
  };
}

function buildFailureProcessed(ticket, error) {
  const message = (error && error.message) || String(error || '未知错误');
  const reason = `fixed_batch处理失败: ${message}`;
  return {
    status: 'simulated',
    internalStatus: 'fixed_batch_failed',
    collectedData: {
      ticket,
      fixedBatchError: true,
      error: message,
    },
    decision: {
      action: 'escalate',
      reason,
      confidence: 'low',
      inferredAt: new Date().toISOString(),
      rulesApplied: [{ doc: 'A1-fixed-batch', section: 'processing_failed', summary: '固定清单逐单处理失败，写回待确认人工复核' }],
      warnings: [reason],
      context: { workOrderNum: ticket && ticket.workOrderNum, fixedBatchFailed: true },
    },
  };
}

function statusForProcessed(processed, queueItem) {
  const decision = processed && processed.decision;
  if (decision && decision.action === 'skip') return getSkipCompletionStatus(queueItem);
  if (decision && decision.waitingRescan) return 'waiting';
  if (processed && processed.status === 'auto_executed') return 'auto_executed';
  return 'simulated';
}

function buildSimulationPayload({ account, queueItem, ticket, processed, source = 'fixed_batch' }) {
  const now = new Date().toISOString();
  const decision = processed && processed.decision;
  const queueStatus = statusForProcessed(processed, queueItem);
  const sim = {
    id: `${source}-${Date.now()}-${ticket.workOrderNum}`,
    workOrderNum: ticket.workOrderNum,
    queueItemId: queueItem && queueItem.id,
    accountNum: account && account.accountNum,
    accountNote: (account && account.matchedNote) || ticket.accountNote || '',
    mode: 'live',
    source,
    collectedData: processed && processed.collectedData,
    decision,
    createdAt: now,
  };
  if (processed && processed.autoBlockedReason) sim.autoBlockedReason = processed.autoBlockedReason;
  if (processed && processed.execution) sim.execution = processed.execution;
  if (queueStatus === 'auto_executed' || queueStatus === 'done') {
    sim.executedAt = now;
    if (queueStatus === 'auto_executed') sim.autoExecutedAt = now;
  }
  return sim;
}

function loadDefaultDependencies() {
  const cdp = require('../../lib/cdp');
  const { openAccountFlow } = require('../../lib/jl/open-account-flow');
  const { prepareAfterSaleList } = require('./11-prepare-after-sale-list');
  const { clickWorkOrderAction } = require('./12-click-work-order-action');
  const { readShopName } = require('./02-read-shop-name');
  const step10 = require('./10-read-urgent-after-sale-list');
  const { inferDecision } = require('../../lib/infer');
  const { shouldAutoExecute } = require('../../lib/server/auto-exec-confidence');
  const { approveTicket } = require('../../lib/jl/approve');
  const db = require('../../lib/server/data');
  const { createAutoExecutionJournal } = require('../../lib/server/auto-execution-journal');
  const fs = require('node:fs');
  const path = require('node:path');
  const {
    collectTicketTargetAware,
    resolveUniqueErpTargetId,
  } = require('../../lib/jl/target-aware-collector');
  const { sleep, waitFor } = require('../../lib/wait');

  const readCurrentPage = async targetId => {
    const raw = await cdp.eval(targetId, step10.READ_CURRENT_PAGE_TICKETS_JS);
    return {
      tickets: (raw && raw.tickets) || [],
      loading: Boolean(raw && raw.loading),
      pagination: step10.normalizePaginationState(raw && raw.pagination),
    };
  };
  const waitForPage = createWaitForPage(waitFor);
  const circuitFile = path.join(__dirname, '../../data/circuit-breaker.json');
  const executionJournal = createAutoExecutionJournal();
  const readCircuit = createCircuitReader(fs.readFileSync, circuitFile);
  if (typeof globalThis.__tripCircuitBreaker !== 'function') {
    globalThis.__tripCircuitBreaker = (error, label) => {
      const state = {
        tripped: true,
        reason: (error && error.message) || '未知风控错误',
        trippedAt: new Date().toISOString(),
        trippedBy: label || 'fixed_batch',
      };
      fs.writeFileSync(circuitFile, JSON.stringify(state, null, 2));
    };
  }
  return {
    openAccountFlow,
    prepareAfterSaleList,
    clickWorkOrderAction,
    locateWorkOrder: (targetId, workOrderNum) => {
      const pageDependencies = {
        readCurrentPage,
        sleep,
        waitForPage,
        dispatchMouseEvent: event => cdp.cdpCall(targetId, 'Input.dispatchMouseEvent', event),
      };
      return locateWorkOrderOnFreshList(targetId, workOrderNum, {
        readCurrentPage,
        clickPageOne: id => clickPageOneLikeHuman(id, pageDependencies),
        clickNextPage: step10.clickNextPage,
        waitForPage,
      });
    },
    resolveErpTargetId: requestedTargetId => resolveUniqueErpTargetId({ getTargets: cdp.getTargets }, requestedTargetId),
    readShopName: (targetId, waitMs = 0) => readShopName(targetId, waitMs),
    cleanupCurrentAccountJlTargets: context => cleanupCurrentAccountJlTargets(context, {
      getTargets: cdp.getTargets,
      closeTarget: cdp.closeTarget,
      readShopName: (targetId, waitMs = 0) => readShopName(targetId, waitMs),
    }),
    collectDetail: context => collectTicketTargetAware({
      detailTargetId: context.detailTargetId,
      erpTargetId: context.erpTargetId,
      workOrderNum: context.ticket.workOrderNum,
      accountNote: context.account.matchedNote || context.ticket.accountNote || '',
      type: context.ticket.type,
    }),
    inferDecision: (collectedData, ticket) => inferDecision({ collectedData }, ticket),
    shouldAutoExecute,
    assertBatchAllowed: async () => {
      const circuit = readCircuit();
      return circuit && circuit.tripped
        ? { allowed: false, reason: `风控熔断中: ${circuit.reason || '未知原因'}` }
        : { allowed: true };
    },
    assertAutoExecutionAllowed: createAutoExecutionGate({
      readCircuit,
      executionJournal,
      readSimulations: () => db.readSimulations(),
    }),
    executeDecision: async ({ detailTargetId, ticket, decision }) => {
      if (!decision || decision.action !== 'approve') {
        throw new Error(`不支持自动执行动作: ${decision && decision.action}`);
      }
      return approveTicket(detailTargetId, ticket.workOrderNum);
    },
    reserveAutoExecution: async ({ account, ticket, decision }) => executionJournal.reserve(ticket.workOrderNum, {
      accountNote: account.matchedNote || '',
      decisionAction: decision.action,
    }),
    markAutoExecuted: async ({ ticket }) => executionJournal.markExecuted(ticket.workOrderNum),
    ensureQueueItem: createEnsureQueueItem(db),
    persistOutcome: async ({ account, queueItem, ticket, processed }) => {
      if (!queueItem || !queueItem.id) throw new Error(`工单 ${ticket.workOrderNum} 缺少 queue item，拒绝写回结果`);
      const sim = buildSimulationPayload({ account, queueItem, ticket, processed });
      const queueStatus = statusForProcessed(processed, queueItem);
      db.appendSimulation(sim);
      db.updateQueueItem(queueItem.id, { status: queueStatus });
      return { ...sim, queueStatus };
    },
    closeTarget: cdp.closeTarget,
    getTargets: cdp.getTargets,
    onProgress: async () => {},
  };
}

async function processSingleAccountFixedBatch(accountNum, options = {}) {
  const account = assertAccountNum(accountNum);
  if (options.thresholdHours != null && Number(options.thresholdHours) !== 48) {
    throw new Error('生产处理范围固定为48小时，不允许改写 thresholdHours');
  }
  const thresholdHours = 48;
  const dependencies = options.dependencies || loadDefaultDependencies();

  const assertBatchAllowed = async () => {
    if (typeof dependencies.assertBatchAllowed !== 'function') throw new Error('批次熔断安全门未装配');
    const gate = await dependencies.assertBatchAllowed();
    if (!gate || gate.allowed !== true) throw new Error((gate && gate.reason) || '批次安全门拒绝');
  };
  await assertBatchAllowed();

  const accountResult = await dependencies.openAccountFlow(account);
  if (!accountResult || !accountResult.success) throw stepError('打开账号失败', accountResult);
  const prepared = await dependencies.prepareAfterSaleList({
    targetId: accountResult.targetId,
    thresholdHours,
  });
  if (!prepared || !prepared.success) throw stepError('准备售后列表失败', prepared);
  if (!prepared.list || prepared.list.complete !== true) {
    throw new Error(`48小时清单读取不完整: ${(prepared.list && prepared.list.stopReason) || '未确认完整终止条件'}`);
  }
  if (!Number.isSafeInteger(prepared.list.totalCount) || prepared.list.totalCount < 0) {
    throw new Error('48小时清单缺少有效 totalCount，拒绝冻结');
  }

  const urgent = prepared.list && Array.isArray(prepared.list.urgent) ? prepared.list.urgent : [];
  const snapshot = cloneSnapshot(urgent);
  if (typeof dependencies.ensureQueueItem !== 'function' || typeof dependencies.persistOutcome !== 'function') {
    throw new Error('原售后系统数据流写回未装配: ensureQueueItem/persistOutcome 缺失');
  }
  const items = [];
  for (const ticket of snapshot) {
    const workOrderNum = assertWorkOrderNum(ticket.workOrderNum);
    const queueItem = await dependencies.ensureQueueItem({ account: accountResult, ticket: { ...ticket, workOrderNum } });
    if (!queueItem || !queueItem.id) throw new Error(`工单 ${workOrderNum} 缺少原系统 queue item`);
    items.push({
      workOrderNum,
      status: 'pending',
      ticket: { ...ticket, workOrderNum },
      queueItemId: queueItem.id,
      queueItem,
    });
  }
  for (const item of items) await reportProgress(dependencies, item);
  const erpTargetId = snapshot.length && typeof dependencies.resolveErpTargetId === 'function'
    ? await dependencies.resolveErpTargetId(options.erpTargetId)
    : (options.erpTargetId || null);

  for (const item of items) {
    await assertBatchAllowed();
    item.status = 'processing';
    await reportProgress(dependencies, item);
    let detailTargetId = null;
    let processingError = null;

    try {
      const located = await dependencies.locateWorkOrder(prepared.targetId, item.workOrderNum);
      item.location = located;
      if (!located || !located.found) {
        if (!located || !located.gone) throw new Error('工单定位结果不可信');
        const goneProcessed = {
          status: 'simulated',
          internalStatus: 'gone_from_pending',
          collectedData: { ticket: item.ticket, listLocation: located },
          decision: buildGoneDecision(item.ticket, located),
        };
        const persisted = await dependencies.persistOutcome({
          account: accountResult,
          queueItem: item.queueItem,
          ticket: item.ticket,
          processed: goneProcessed,
        });
        Object.assign(item, goneProcessed, {
          status: 'gone_from_pending',
          reason: located.reason,
          persistedSimulationId: persisted && persisted.id,
        });
        await reportProgress(dependencies, item);
        continue;
      }

      const opened = await dependencies.clickWorkOrderAction(item.workOrderNum, { targetId: prepared.targetId });
      if (!opened || !opened.success || !opened.newTargetId) throw stepError('打开目标工单失败', opened);
      detailTargetId = opened.newTargetId;
      item.detailTargetId = detailTargetId;

      const processed = await processOpenedDetail({
        account: accountResult,
        listTargetId: prepared.targetId,
        detailTargetId,
        erpTargetId,
        ticket: item.ticket,
        disableAutoExecute: options.disableAutoExecute === true,
      }, dependencies);
      Object.assign(item, processed);
      const persisted = await dependencies.persistOutcome({
        account: accountResult,
        queueItem: item.queueItem,
        ticket: item.ticket,
        processed,
      });
      if (persisted && persisted.queueStatus) item.status = persisted.queueStatus;
      item.persistedSimulationId = persisted && persisted.id;
    } catch (error) {
      processingError = error;
      if (!detailTargetId && Array.isArray(error.newTargetIds)) {
        for (const unexpectedTargetId of error.newTargetIds) {
          try {
            await closeAndVerifyDetailTarget(unexpectedTargetId, dependencies, {
              account: accountResult,
              listTargetId: prepared.targetId,
            });
          } catch (cleanupError) {
            processingError = cleanupError;
            break;
          }
        }
      }
    } finally {
      if (detailTargetId) {
        try {
          await closeAndVerifyDetailTarget(detailTargetId, dependencies, {
            account: accountResult,
            listTargetId: prepared.targetId,
          });
          item.detailClosed = true;
        } catch (closeError) {
          processingError = closeError;
        }
      }
    }

    if (processingError) {
      const failureProcessed = buildFailureProcessed(item.ticket, processingError);
      try {
        const persisted = await dependencies.persistOutcome({
          account: accountResult,
          queueItem: item.queueItem,
          ticket: item.ticket,
          processed: failureProcessed,
        });
        Object.assign(item, failureProcessed, {
          status: 'simulated',
          error: processingError.message,
          persistedSimulationId: persisted && persisted.id,
        });
      } catch (persistError) {
        item.status = 'failed';
        item.error = `${processingError.message}; 写回失败: ${persistError.message}`;
        processingError.persistError = persistError;
      }
      await reportProgress(dependencies, item);
      processingError.batch = { success: false, account: accountResult, snapshot, items };
      throw processingError;
    }
    await reportProgress(dependencies, item);
  }

  let cleanup = null;
  if (typeof dependencies.cleanupCurrentAccountJlTargets === 'function') {
    cleanup = await dependencies.cleanupCurrentAccountJlTargets({
      account: accountResult,
      listTargetId: prepared.targetId,
    });
  } else if (typeof dependencies.readShopName === 'function') {
    cleanup = await cleanupCurrentAccountJlTargets({
      account: accountResult,
      listTargetId: prepared.targetId,
    }, dependencies);
  }

  return {
    success: true,
    account: accountResult,
    listTargetId: prepared.targetId,
    initialTotalCount: prepared.list && prepared.list.totalCount,
    erpTargetId,
    snapshot,
    items,
    cleanup,
  };
}

async function runCli(argv, options = {}) {
  const writeLine = options.writeLine || console.log;
  const args = Array.isArray(argv) ? argv.slice(2) : [];
  const disableAutoExecute = options.disableAutoExecute === true || args.includes('--disable-auto-execute');
  const accountNum = args.find(arg => arg && !String(arg).startsWith('--'));
  try {
    const result = await processSingleAccountFixedBatch(accountNum, {
      dependencies: options.dependencies,
      disableAutoExecute,
    });
    writeLine(JSON.stringify(result));
    return 0;
  } catch (error) {
    writeLine(JSON.stringify({ success: false, error: error.message, batch: error.batch || null }));
    return 1;
  }
}

if (require.main === module) {
  runCli(process.argv).then(code => process.exit(code));
}

module.exports = {
  clickPageOneLikeHuman,
  createWaitForPage,
  createCircuitReader,
  createAutoExecutionGate,
  locateWorkOrderOnFreshList,
  processOpenedDetail,
  processSingleAccountFixedBatch,
  closeAndVerifyDetailTarget,
  cleanupCurrentAccountJlTargets,
  assertClosableCurrentAccountDetailTarget,
  assertCurrentAccountListTarget,
  statusForProcessed,
  buildSimulationPayload,
  createEnsureQueueItem,
  loadDefaultDependencies,
  runCli,
  MAX_PAGES,
};
