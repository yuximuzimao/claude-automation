#!/usr/bin/env node
'use strict';

const { matchShopName } = require('../../lib/jl/login-state');
const { getSkipCompletionStatus } = require('../../lib/server/pipeline-status');
const { UNFINISHED_INTENT_BLOCK_REASON } = require('../../lib/server/auto-execution-journal');
const { getHoursUntilNextScan } = require('../../lib/constants');
const { resolveSharedReturnGroup } = require('../../lib/return-tracking-group');
const {
  getTicketPlatformStage,
  matchesConfirmedNoAction,
  applyPlatformStageObservation,
} = require('../../lib/after-sales-platform-stage');

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
  return Boolean(findWorkOrderTicket(pageData, workOrderNum));
}

function findWorkOrderTicket(pageData, workOrderNum) {
  return (pageData && Array.isArray(pageData.tickets) ? pageData.tickets : [])
    .find(ticket => ticket && String(ticket.workOrderNum) === workOrderNum) || null;
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
    }, { timeoutMs: 15000, intervalMs: 500, label: `等待售后列表第${expectedPage}页刷新` });
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
    if (typeof executionJournal.getBlockingRecord === 'function') {
      const blocked = executionJournal.getBlockingRecord(workOrderNum);
      if (blocked) return { allowed: false, reason: blocked.blockReason || UNFINISHED_INTENT_BLOCK_REASON };
    } else {
      const unfinishedIntent = executionJournal.getUnfinishedIntent(workOrderNum);
      if (unfinishedIntent) return { allowed: false, reason: UNFINISHED_INTENT_BLOCK_REASON };
    }
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
  const { pagination } = assertTrustedPagination(before);
  if (pagination.currentPage === 1) return pagination;

  // 分页条在页面底部（top ≈ 2400px），CDP 物理点击只接受 viewport 坐标。
  // 先向下大幅滚动使分页条进入 viewport，重读坐标，物理点击——与 step 12 / clickNextPage 同原则。
  await dependencies.dispatchMouseEvent({
    type: 'mouseWheel', x: 640, y: 400, deltaX: 0, deltaY: 5000, button: 'none',
  });
  await dependencies.sleep(400);

  const afterScroll = await dependencies.readCurrentPage(targetId);
  const { pages } = assertTrustedPagination(afterScroll);
  const pageOneLi = pages.find(p => p.number === 1 && !p.active);
  if (!pageOneLi || !pageOneLi.rect || !Number.isFinite(pageOneLi.rect.centerX)) {
    throw new Error('滚动后未找到第 1 页 li 按钮坐标');
  }

  const { centerX: x, centerY: y } = pageOneLi.rect;
  await dependencies.dispatchMouseEvent({ type: 'mouseMoved', x, y, button: 'none' });
  await dependencies.sleep(150);
  await dependencies.dispatchMouseEvent({ type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await dependencies.sleep(130);
  await dependencies.dispatchMouseEvent({ type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });

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
    return {
      found: true,
      workOrderNum: order,
      ticket: findWorkOrderTicket(current, order),
      page: trusted.pagination.currentPage,
      pagesChecked: [trusted.pagination.currentPage],
    };
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
      return {
        found: true,
        workOrderNum: order,
        ticket: findWorkOrderTicket(current, order),
        page: pageNumber,
        pagesChecked,
      };
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
  // Chrome closeTarget HTTP 返回成功后标签页可能尚未从 /json 列表移除，短等待 + 重试一次
  await dependencies.sleep(300);
  let targets = await dependencies.getTargets();
  if ((targets || []).some(target => targetIdOf(target) === detailTargetId)) {
    await dependencies.closeTarget(detailTargetId);
    await dependencies.sleep(500);
    targets = await dependencies.getTargets();
    if ((targets || []).some(target => targetIdOf(target) === detailTargetId)) {
      throw new Error(`详情标签页关闭验证失败: ${detailTargetId}`);
    }
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

function applyInboundSharedReturnLinks(collectedData, currentWorkOrderNum, sharedReturnContext) {
  const ticket = collectedData && collectedData.ticket;
  const records = sharedReturnContext && sharedReturnContext.collectedDataByWorkOrder;
  const currentNum = String(currentWorkOrderNum || ticket && ticket.workOrderNum || '');
  if (!ticket || !currentNum || !(records instanceof Map)) return;

  const inboundWorkOrderNums = [];
  for (const [otherNum, otherCollectedData] of records.entries()) {
    if (String(otherNum) === currentNum) continue;
    const otherTicket = otherCollectedData && otherCollectedData.ticket;
    const linkedNums = Array.isArray(otherTicket && otherTicket.returnTrackingUsedBy)
      ? otherTicket.returnTrackingUsedBy.map(String)
      : [];
    if (linkedNums.includes(currentNum)) inboundWorkOrderNums.push(String(otherNum));
  }
  if (!inboundWorkOrderNums.length) return;

  ticket.returnTrackingMultiUse = true;
  ticket.returnTrackingUsedBy = [...new Set([
    ...(Array.isArray(ticket.returnTrackingUsedBy) ? ticket.returnTrackingUsedBy.map(String) : []),
    ...inboundWorkOrderNums,
  ])];
  ticket.returnTrackingAssociationSources = [...new Set([
    ...(Array.isArray(ticket.returnTrackingAssociationSources)
      ? ticket.returnTrackingAssociationSources.map(String)
      : []),
    ...inboundWorkOrderNums,
  ])];
}

async function processOpenedDetail(context, dependencies) {
  const collectedData = await dependencies.collectDetail(context);
  const sharedReturnContext = context && context.sharedReturnContext;
  const currentWorkOrderNum = context && context.ticket && context.ticket.workOrderNum;
  if (sharedReturnContext && sharedReturnContext.collectedDataByWorkOrder instanceof Map && currentWorkOrderNum) {
    sharedReturnContext.collectedDataByWorkOrder.set(String(currentWorkOrderNum), collectedData);
  }
  applyInboundSharedReturnLinks(collectedData, currentWorkOrderNum, sharedReturnContext);
  const platformStage = getTicketPlatformStage(context && context.ticket);
  collectedData.platformStage = platformStage;
  if (collectedData.ticket && collectedData.ticket.returnTrackingMultiUse &&
      typeof dependencies.resolveSharedReturnGroup === 'function') {
    collectedData.sharedReturnGroup = await dependencies.resolveSharedReturnGroup(
      collectedData,
      currentWorkOrderNum,
      sharedReturnContext
    );
    const batchWorkOrderNums = sharedReturnContext && sharedReturnContext.batchWorkOrderNums;
    if (collectedData.sharedReturnGroup && batchWorkOrderNums instanceof Set &&
        (collectedData.sharedReturnGroup.ignoredWorkOrderNums || []).some(num => batchWorkOrderNums.has(String(num)))) {
      collectedData.sharedReturnGroup = {
        mode: 'incomplete',
        reason: '相同子订单的关联工单同时处于本批次待处理状态，无法按历史重新申请忽略，需人工确认有效工单',
      };
    }
    const missingWorkOrderNums = collectedData.sharedReturnGroup &&
      Array.isArray(collectedData.sharedReturnGroup.missingWorkOrderNums)
      ? collectedData.sharedReturnGroup.missingWorkOrderNums.map(String)
      : [];
    const canDeferForBatch = (!context || context.allowSharedReturnDefer !== false) &&
      missingWorkOrderNums.length > 0 &&
      batchWorkOrderNums instanceof Set &&
      missingWorkOrderNums.every(num => batchWorkOrderNums.has(num));
    if (canDeferForBatch) {
      return {
        status: 'deferred_shared_return',
        collectedData,
        pendingSharedReturnWorkOrderNums: missingWorkOrderNums,
      };
    }
  }
  const queueItem = { ...context.queueItem, hoursUntilNextScan: getHoursUntilNextScan() };
  const baselineDecision = await dependencies.inferDecision(collectedData, queueItem);
  const stageResult = applyPlatformStageObservation({
    type: context && context.ticket && context.ticket.type,
    platformStage,
    baselineDecision,
  });
  const decision = stageResult.decision;
  if (stageResult.assessment) collectedData.platformStageAssessment = stageResult.assessment;
  if (context && context.disableAutoExecute === true) {
    return {
      status: 'simulated',
      collectedData,
      decision,
      autoBlockedReason: context.autoBlockedReason || 'fixed_batch 已显式关闭自动执行',
    };
  }
  const auto = await dependencies.shouldAutoExecute(decision, collectedData, queueItem);
  if (!auto) return { status: 'simulated', collectedData, decision };
  if (context && context.deferRefundReturnAutoUntilBatchComplete === true &&
      context.ticket && context.ticket.type === '退货退款') {
    return {
      status: 'deferred_auto_execution',
      collectedData,
      decision,
      autoBlockedReason: '退货退款自动执行等待当前批次关联关系采集完成',
    };
  }
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

  if (typeof dependencies.markPageActionStarted === 'function') {
    await dependencies.markPageActionStarted({ ...context, collectedData, decision });
  }
  const execution = await dependencies.executeDecision({ ...context, collectedData, decision });
  if (!execution || !execution.success) throw stepError('自动执行失败', execution);
  if (typeof dependencies.markPageActionSucceeded === 'function') {
    await dependencies.markPageActionSucceeded({ ...context, collectedData, decision, execution });
  }
  await dependencies.markAutoExecuted({ ...context, collectedData, decision, execution });
  return { status: 'auto_executed', collectedData, decision, execution };
}

function buildDeferredSafetyPlaceholder(processed) {
  const isSharedReturn = processed && processed.status === 'deferred_shared_return';
  const pendingNums = isSharedReturn
    ? (processed.pendingSharedReturnWorkOrderNums || []).map(String).filter(Boolean)
    : [];
  const reason = isSharedReturn
    ? `共用退货单关联组尚未采齐${pendingNums.length ? `（等待工单：${pendingNums.join('、')}）` : ''}，暂不可执行`
    : '退货退款自动执行正在等待本批次关联关系采集完成，暂不可执行';
  return {
    status: 'simulated',
    collectedData: processed.collectedData,
    decision: {
      action: 'escalate',
      reason,
      confidence: 'low',
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: false,
      warnings: [],
    },
    autoBlockedReason: reason,
  };
}

function buildRelatedSharedReturnPlaceholder(relatedItem, sourceWorkOrderNum) {
  const reason = `同批次工单 ${sourceWorkOrderNum} 已将当前工单列为共用退货单关联成员，关联组核验完成前暂不可执行`;
  return {
    status: 'simulated',
    collectedData: {
      ticket: relatedItem.ticket,
      batchSafetyAssociation: { sourceWorkOrderNum: String(sourceWorkOrderNum) },
    },
    decision: {
      action: 'escalate',
      reason,
      confidence: 'low',
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: false,
      warnings: [],
    },
    autoBlockedReason: reason,
  };
}

async function processOpenedDetailAndPersist(context, dependencies, options = {}) {
  if (!context || !context.queueItem || !context.queueItem.id) {
    throw new Error('详情处理缺少完整 queue item，拒绝进入推理和自动执行');
  }
  if (typeof dependencies.persistOutcome !== 'function') {
    throw new Error('原售后系统数据流写回未装配: persistOutcome 缺失');
  }

  const processed = await processOpenedDetail(context, dependencies);
  if (processed && ['deferred_shared_return', 'deferred_auto_execution'].includes(processed.status)) {
    const persisted = await dependencies.persistOutcome({
      account: context.account,
      queueItem: context.queueItem,
      ticket: context.ticket,
      processed: buildDeferredSafetyPlaceholder(processed),
      source: options.source || 'fixed_batch',
    });
    const relatedSafetyPlaceholders = [];
    if (processed.status === 'deferred_shared_return') {
      const batchItemsByWorkOrder = context.sharedReturnContext &&
        context.sharedReturnContext.batchItemsByWorkOrder;
      if (batchItemsByWorkOrder instanceof Map) {
        for (const pendingNum of processed.pendingSharedReturnWorkOrderNums || []) {
          const relatedItem = batchItemsByWorkOrder.get(String(pendingNum));
          if (!relatedItem || String(pendingNum) === String(context.ticket.workOrderNum)) continue;
          const relatedPersisted = await dependencies.persistOutcome({
            account: context.account,
            queueItem: relatedItem.queueItem,
            ticket: relatedItem.ticket,
            processed: buildRelatedSharedReturnPlaceholder(relatedItem, context.ticket.workOrderNum),
            source: options.source || 'fixed_batch',
          });
          relatedItem.persistedSimulationId = relatedPersisted && relatedPersisted.id;
          relatedSafetyPlaceholders.push({
            workOrderNum: String(pendingNum),
            persisted: relatedPersisted,
          });
        }
      }
    }
    return { processed, persisted, persistedSafetyPlaceholder: true, relatedSafetyPlaceholders };
  }
  const persisted = await dependencies.persistOutcome({
    account: context.account,
    queueItem: context.queueItem,
    ticket: context.ticket,
    processed,
    source: options.source || 'fixed_batch',
  });
  return { processed, persisted };
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
    const platformStage = getTicketPlatformStage(ticket);
    const existing = (queue.items || []).find(item => item.workOrderNum === ticket.workOrderNum && item.status !== 'done');
    const patch = {
      mode: 'live',
      source: 'fixed_batch',
      accountNum: account.accountNum || null,
      accountNote: account.matchedNote || ticket.accountNote || '',
      type: ticket.type || null,
      urgency: buildUrgency(ticket),
      deadlineAt: buildDeadlineAt(ticket),
      platformStage,
    };
    if (existing) return db.updateQueueItem(existing.id, patch) || { ...existing, ...patch };
    const confirmed = [...(queue.items || [])].reverse().find(item =>
      item.workOrderNum === ticket.workOrderNum
      && item.status === 'done'
      && matchesConfirmedNoAction({
        type: ticket.type,
        platformStage,
        confirmedNoAction: item.confirmedNoAction,
      })
    );
    if (confirmed) {
      const updated = db.updateQueueItem(confirmed.id, { platformStage }) || { ...confirmed, platformStage };
      return { ...updated, suppressConfirmedNoAction: true };
    }
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

function buildMissingWaitingRescanProcessed(queueItem, latestSimulation, observedAt = new Date().toISOString()) {
  const reason = '等待重查工单未出现于本次完整48小时清单，无法确认当前平台阶段和剩余时效；请人工打开工单核对。';
  const previousCollectedData = latestSimulation && latestSimulation.collectedData;
  const previousTicket = previousCollectedData && previousCollectedData.ticket;
  return {
    status: 'simulated',
    internalStatus: 'waiting_rescan_missing_from_48h_list',
    collectedData: {
      ...(previousCollectedData || {}),
      ticket: {
        ...(previousTicket || {}),
        workOrderNum: queueItem.workOrderNum,
      },
      waitingRescanAbsence: {
        observedAt,
        source: 'fixed_batch_48h_reconciliation',
        previousSimulationId: latestSimulation && latestSimulation.id || null,
      },
    },
    decision: {
      action: 'escalate',
      reason,
      reasonCode: 'WAITING_RESCAN_MISSING_FROM_48H_LIST',
      confidence: 'low',
      inferredAt: observedAt,
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: false,
      rulesApplied: [{
        doc: 'INDEX',
        section: '3.1',
        summary: '自动等待重查项未出现于本次完整48小时清单→异常转待确认',
      }],
      warnings: ['不能据此推断工单已关闭、已处理或已超时。'],
      context: {
        workOrderNum: queueItem.workOrderNum,
        waitingRescanMissingFrom48hList: true,
      },
    },
  };
}

function createReconcileWaitingRescanAbsences(db) {
  if (!db || typeof db.readQueue !== 'function' || typeof db.readSimulations !== 'function' ||
      typeof db.appendSimulation !== 'function' || typeof db.updateQueueItem !== 'function') {
    throw new Error('reconcileWaitingRescanAbsences 缺少 queue/simulation 数据依赖');
  }
  return async ({ account, snapshot, observedAt = new Date().toISOString() }) => {
    const accountNum = String(account && account.accountNum || '').trim();
    if (!accountNum) throw new Error('等待重查对账缺少 accountNum');
    const currentWorkOrderNums = new Set((snapshot || []).map(ticket => String(ticket && ticket.workOrderNum || '')));
    const candidates = (db.readQueue().items || []).filter(item =>
      item &&
      item.mode === 'live' &&
      item.status === 'waiting' &&
      item.waitingRescan === true &&
      String(item.accountNum || '') === accountNum &&
      !currentWorkOrderNums.has(String(item.workOrderNum || ''))
    );
    if (candidates.length === 0) return [];

    const latestSimulationByQueueItem = new Map();
    for (const simulation of db.readSimulations()) {
      if (simulation && simulation.queueItemId) {
        latestSimulationByQueueItem.set(simulation.queueItemId, simulation);
      }
    }

    const reconciled = [];
    for (const queueItem of candidates) {
      const latestSimulation = latestSimulationByQueueItem.get(queueItem.id) || null;
      const processed = buildMissingWaitingRescanProcessed(queueItem, latestSimulation, observedAt);
      const ticket = processed.collectedData.ticket;
      const simulation = buildSimulationPayload({
        account,
        queueItem,
        ticket,
        processed,
        source: 'waiting_rescan_missing',
      });
      db.appendSimulation(simulation);
      const updated = db.updateQueueItem(queueItem.id, {
        status: 'simulated',
        waitingRescan: false,
        hint: processed.decision.reason,
      });
      if (!updated) throw new Error(`等待重查异常写回失败: ${queueItem.workOrderNum}`);
      reconciled.push({
        workOrderNum: queueItem.workOrderNum,
        queueItemId: queueItem.id,
        status: 'simulated',
        persistedSimulationId: simulation.id,
        decision: processed.decision,
      });
    }
    return reconciled;
  };
}

function statusForProcessed(processed, queueItem) {
  const decision = processed && processed.decision;
  if (decision && decision.action === 'skip' && decision.manualArchiveOnly === true) return 'simulated';
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
  const { shouldAutoExecute } = require('../../lib/server/after-sales-auto-gate');
  const { executeTicketDecision } = require('../../lib/jl/execute-decision');
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
        dispatchMouseEvent: event => cdp.dispatchMouseEvent(targetId, event),
        eval: (id, js) => cdp.eval(id, js),
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
    resolveSharedReturnGroup: (collectedData, workOrderNum, sharedReturnContext) =>
      resolveSharedReturnGroupForBatch(
        collectedData,
        db.readSimulations(),
        workOrderNum,
        sharedReturnContext
      ),
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
      return executeTicketDecision({
        targetId: detailTargetId,
        workOrderNum: ticket.workOrderNum,
        type: ticket.type,
        decision,
      });
    },
    reserveAutoExecution: async ({ account, ticket, decision }) => executionJournal.reserve(ticket.workOrderNum, {
      accountNote: account.matchedNote || '',
      decisionAction: decision.action,
    }),
    markPageActionStarted: async ({ ticket }) => executionJournal.markPageActionStarted(ticket.workOrderNum),
    markPageActionSucceeded: async ({ ticket }) => executionJournal.markPageActionSucceeded(ticket.workOrderNum),
    markAutoExecuted: async ({ ticket }) => executionJournal.markExecuted(ticket.workOrderNum),
    ensureQueueItem: createEnsureQueueItem(db),
    reconcileWaitingRescanAbsences: createReconcileWaitingRescanAbsences(db),
    persistOutcome: async ({ account, queueItem, ticket, processed, source = 'fixed_batch' }) => {
      if (!queueItem || !queueItem.id) throw new Error(`工单 ${ticket.workOrderNum} 缺少 queue item，拒绝写回结果`);
      const sim = buildSimulationPayload({ account, queueItem, ticket, processed, source });
      const queueStatus = statusForProcessed(processed, queueItem);
      db.appendSimulation(sim);
      db.updateQueueItem(queueItem.id, {
        status: queueStatus,
        waitingRescan: !!(processed.decision && processed.decision.waitingRescan),
      });
      return { ...sim, queueStatus };
    },
    closeTarget: cdp.closeTarget,
    getTargets: cdp.getTargets,
    sleep,
    onProgress: async () => {},
  };
}

function resolveSharedReturnGroupForBatch(
  collectedData,
  historicalSimulations,
  workOrderNum,
  sharedReturnContext
) {
  const batchWorkOrderNums = sharedReturnContext && sharedReturnContext.batchWorkOrderNums instanceof Set
    ? sharedReturnContext.batchWorkOrderNums
    : null;
  const collectedDataByWorkOrder = sharedReturnContext &&
    sharedReturnContext.collectedDataByWorkOrder instanceof Map
    ? sharedReturnContext.collectedDataByWorkOrder
    : null;
  const usableHistorical = batchWorkOrderNums
    ? (historicalSimulations || []).filter(record =>
      !batchWorkOrderNums.has(String(record && record.workOrderNum || ''))
    )
    : (historicalSimulations || []);
  const freshBatchRecords = collectedDataByWorkOrder
    ? [...collectedDataByWorkOrder.entries()].map(([num, data]) => ({
      workOrderNum: num,
      collectedData: data,
    }))
    : [];
  return resolveSharedReturnGroup(
    collectedData,
    [...usableHistorical, ...freshBatchRecords],
    workOrderNum
  );
}

async function processSingleAccountFixedBatch(accountNum, options = {}) {
  const account = assertAccountNum(accountNum);
  if (options.thresholdHours != null && Number(options.thresholdHours) !== 48) {
    throw new Error('生产处理范围固定为48小时，不允许改写 thresholdHours');
  }
  const thresholdHours = 48;
  const dependencies = options.dependencies || loadDefaultDependencies();
  if (typeof options.onTicketProgress === 'function') {
    const origOnProgress = dependencies.onProgress;
    dependencies.onProgress = async (item) => {
      options.onTicketProgress(item);
      if (typeof origOnProgress === 'function') await origOnProgress(item);
    };
  }

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
  const waitingRescanAbsences = typeof dependencies.reconcileWaitingRescanAbsences === 'function'
    ? await dependencies.reconcileWaitingRescanAbsences({ account: accountResult, snapshot })
    : [];
  for (const absence of waitingRescanAbsences) await reportProgress(dependencies, absence);
  if (typeof dependencies.ensureQueueItem !== 'function' || typeof dependencies.persistOutcome !== 'function') {
    throw new Error('原售后系统数据流写回未装配: ensureQueueItem/persistOutcome 缺失');
  }
  const items = [];
  for (const ticket of snapshot) {
    const workOrderNum = assertWorkOrderNum(ticket.workOrderNum);
    const queueItem = await dependencies.ensureQueueItem({ account: accountResult, ticket: { ...ticket, workOrderNum } });
    if (!queueItem || !queueItem.id) throw new Error(`工单 ${workOrderNum} 缺少原系统 queue item`);
    const suppressConfirmedNoAction = queueItem.suppressConfirmedNoAction === true;
    items.push({
      workOrderNum,
      status: suppressConfirmedNoAction ? 'done' : 'pending',
      ticket: { ...ticket, workOrderNum },
      queueItemId: queueItem.id,
      queueItem,
      suppressConfirmedNoAction,
    });
  }
  for (const item of items) await reportProgress(dependencies, item);
  const processableItems = items.filter(item => !item.suppressConfirmedNoAction);
  const erpTargetId = processableItems.length && typeof dependencies.resolveErpTargetId === 'function'
    ? await dependencies.resolveErpTargetId(options.erpTargetId)
    : (options.erpTargetId || null);
  const sharedReturnContext = {
    batchWorkOrderNums: new Set(processableItems.map(item => String(item.workOrderNum))),
    collectedDataByWorkOrder: new Map(),
    batchItemsByWorkOrder: new Map(processableItems.map(item => [String(item.workOrderNum), item])),
  };

  for (const item of processableItems) {
    if (options.abortSignal && options.abortSignal.aborted) {
      const err = new Error('操作已被用户停止');
      err.name = 'AbortError';
      throw err;
    }
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

      const outcome = await processOpenedDetailAndPersist({
        account: accountResult,
        listTargetId: prepared.targetId,
        detailTargetId,
        erpTargetId,
        ticket: item.ticket,
        queueItem: item.queueItem,
        disableAutoExecute: options.disableAutoExecute === true,
        sharedReturnContext,
        allowSharedReturnDefer: true,
        deferRefundReturnAutoUntilBatchComplete: true,
      }, dependencies, { source: 'fixed_batch' });
      const { processed, persisted } = outcome;
      Object.assign(item, processed);
      if (persisted && persisted.queueStatus &&
          !['deferred_shared_return', 'deferred_auto_execution'].includes(processed.status)) {
        item.status = persisted.queueStatus;
      }
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

  // 同一固定批次里的共用退货单必须先采集齐关联组，再统一推理。
  // 第二阶段只复用内存中的采集结果，不重新打开工单，也不允许自动执行。
  const deferredSharedReturnItems = processableItems.filter(item => item.status === 'deferred_shared_return');
  for (const item of deferredSharedReturnItems) {
    if (options.abortSignal && options.abortSignal.aborted) {
      const err = new Error('操作已被用户停止');
      err.name = 'AbortError';
      throw err;
    }
    await assertBatchAllowed();
    item.status = 'processing';
    await reportProgress(dependencies, item);

    try {
      const replayDependencies = {
        ...dependencies,
        collectDetail: async () => item.collectedData,
      };
      const outcome = await processOpenedDetailAndPersist({
        account: accountResult,
        listTargetId: prepared.targetId,
        detailTargetId: null,
        erpTargetId,
        ticket: item.ticket,
        queueItem: item.queueItem,
        disableAutoExecute: true,
        autoBlockedReason: '共用退货单关联组回算只生成待人工确认结果',
        sharedReturnContext,
        allowSharedReturnDefer: false,
      }, replayDependencies, { source: 'fixed_batch' });
      const { processed, persisted } = outcome;
      if (processed && processed.status === 'deferred_shared_return') {
        throw new Error(`工单 ${item.workOrderNum} 关联组回算后仍处于等待状态`);
      }
      Object.assign(item, processed);
      if (persisted && persisted.queueStatus) item.status = persisted.queueStatus;
      item.persistedSimulationId = persisted && persisted.id;
    } catch (error) {
      const failureProcessed = buildFailureProcessed(item.ticket, error);
      try {
        const persisted = await dependencies.persistOutcome({
          account: accountResult,
          queueItem: item.queueItem,
          ticket: item.ticket,
          processed: failureProcessed,
        });
        Object.assign(item, failureProcessed, {
          status: 'simulated',
          error: error.message,
          persistedSimulationId: persisted && persisted.id,
        });
      } catch (persistError) {
        item.status = 'failed';
        item.error = `${error.message}; 写回失败: ${persistError.message}`;
        error.persistError = persistError;
      }
      await reportProgress(dependencies, item);
      error.batch = { success: false, account: accountResult, snapshot, items };
      throw error;
    }
    await reportProgress(dependencies, item);
  }

  // 普通退货退款即使命中自动分支，也要等当前批次所有详情采集完再执行。
  // 这样后出现的工单若反向关联到它，能先把它改判为共用退货单人工确认，避免单向提示导致提前退款。
  const deferredAutoExecutionItems = processableItems.filter(item => item.status === 'deferred_auto_execution');
  for (const item of deferredAutoExecutionItems) {
    if (options.abortSignal && options.abortSignal.aborted) {
      const err = new Error('操作已被用户停止');
      err.name = 'AbortError';
      throw err;
    }
    await assertBatchAllowed();
    item.status = 'processing';
    await reportProgress(dependencies, item);
    let detailTargetId = null;
    let processingError = null;

    try {
      let autoEligibleAfterBatch = false;
      const evaluationDependencies = {
        ...dependencies,
        collectDetail: async () => item.collectedData,
        shouldAutoExecute: async (decision, collectedData, queueItem) => {
          autoEligibleAfterBatch = await dependencies.shouldAutoExecute(decision, collectedData, queueItem);
          return false;
        },
      };
      const evaluated = await processOpenedDetail({
        account: accountResult,
        listTargetId: prepared.targetId,
        detailTargetId: null,
        erpTargetId,
        ticket: item.ticket,
        queueItem: item.queueItem,
        sharedReturnContext,
        allowSharedReturnDefer: false,
        deferRefundReturnAutoUntilBatchComplete: false,
      }, evaluationDependencies);
      if (evaluated && ['deferred_shared_return', 'deferred_auto_execution'].includes(evaluated.status)) {
        throw new Error(`工单 ${item.workOrderNum} 批次回算后仍处于等待状态`);
      }

      if (!autoEligibleAfterBatch) {
        const persisted = await dependencies.persistOutcome({
          account: accountResult,
          queueItem: item.queueItem,
          ticket: item.ticket,
          processed: evaluated,
          source: 'fixed_batch',
        });
        Object.assign(item, evaluated);
        if (persisted && persisted.queueStatus) item.status = persisted.queueStatus;
        item.persistedSimulationId = persisted && persisted.id;
      } else {
        const located = await dependencies.locateWorkOrder(prepared.targetId, item.workOrderNum);
        item.location = located;
        if (!located || !located.found) throw new Error('自动执行前无法重新定位工单');
        const opened = await dependencies.clickWorkOrderAction(item.workOrderNum, { targetId: prepared.targetId });
        if (!opened || !opened.success || !opened.newTargetId) throw stepError('自动执行前重新打开目标工单失败', opened);
        detailTargetId = opened.newTargetId;
        item.detailTargetId = detailTargetId;

        const outcome = await processOpenedDetailAndPersist({
          account: accountResult,
          listTargetId: prepared.targetId,
          detailTargetId,
          erpTargetId,
          ticket: item.ticket,
          queueItem: item.queueItem,
          sharedReturnContext,
          allowSharedReturnDefer: false,
          deferRefundReturnAutoUntilBatchComplete: false,
        }, dependencies, { source: 'fixed_batch' });
        const { processed, persisted } = outcome;
        Object.assign(item, processed);
        if (persisted && persisted.queueStatus) item.status = persisted.queueStatus;
        item.persistedSimulationId = persisted && persisted.id;
      }
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

  try {
    const { fetchAndCacheAlerts } = require('../../lib/jl/alerts');
    const accountNote = (accountResult && accountResult.matchedNote) || `账号${accountNum}`;
    await fetchAndCacheAlerts(accountNum, accountNote);
  } catch(e) {
    console.warn('[step14] fetchAndCacheAlerts 非致命错误:', e.message);
  }

  return {
    success: true,
    account: accountResult,
    listTargetId: prepared.targetId,
    initialTotalCount: prepared.list && prepared.list.totalCount,
    erpTargetId,
    snapshot,
    items,
    waitingRescanAbsences,
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
  assertAccountNum,
  clickPageOneLikeHuman,
  createWaitForPage,
  createCircuitReader,
  createAutoExecutionGate,
  buildMissingWaitingRescanProcessed,
  createReconcileWaitingRescanAbsences,
  locateWorkOrderOnFreshList,
  processOpenedDetail,
  processOpenedDetailAndPersist,
  processSingleAccountFixedBatch,
  closeAndVerifyDetailTarget,
  cleanupCurrentAccountJlTargets,
  assertClosableCurrentAccountDetailTarget,
  assertCurrentAccountListTarget,
  statusForProcessed,
  buildSimulationPayload,
  createEnsureQueueItem,
  loadDefaultDependencies,
  resolveSharedReturnGroupForBatch,
  runCli,
  MAX_PAGES,
};
