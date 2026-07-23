#!/usr/bin/env node
'use strict';
/**
 * 鲸灵 A1 — 原子步骤 10：读取 48 小时内售后工单列表。
 *
 * 前置假设：
 *   - 已通过步骤 08 点击进入「售后工单」列表。
 *   - 已通过步骤 09 选择「按逾期时间最近排序」。
 *
 * 本步只读列表，可点击分页「下一页」继续读取；不刷新、不导航、不处理工单。
 * 因列表已按逾期时间升序排列，读取到第一条 totalHours > thresholdHours 后立即停止，
 * 后续卡片和后续页面都不再读取。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { sleep, waitFor } = require(path.join(__dirname, '../../lib/wait'));

const JL_DOMAIN = 'scrm.jlsupp.com';
const DEFAULT_THRESHOLD_HOURS = 48;
const MAX_PAGES = 20;
const MOVE_DELAY_MS = 150;
const PRESS_DELAY_MS = 130;
const SCROLL_TO_BOTTOM_DELTA_PX = 5000;

function parseRemainingHours(text) {
  if (!text) return null;
  let m = String(text).match(/(\d+)\s*天\s*(\d+)\s*小时\s*(\d+)\s*分/);
  if (m) return parseInt(m[1], 10) * 24 + parseInt(m[2], 10) + parseInt(m[3], 10) / 60;

  m = String(text).match(/(\d+)\s*天\s*(\d+)\s*小时/);
  if (m) return parseInt(m[1], 10) * 24 + parseInt(m[2], 10);

  m = String(text).match(/(\d+)\s*小时\s*(\d+)\s*分/);
  if (m) return parseInt(m[1], 10) + parseInt(m[2], 10) / 60;

  m = String(text).match(/(\d+)\s*小时/);
  if (m) return parseInt(m[1], 10);

  return null;
}

function extractRemainingTimerText(card, isVisible = () => true) {
  if (!card || typeof card.querySelectorAll !== 'function') return null;
  const timer = Array.from(card.querySelectorAll('.el-timer')).find(isVisible);
  if (!timer) return null;
  const text = timer.innerText || timer.textContent || '';
  return String(text).replace(/\s+/g, ' ').trim() || null;
}

function parseTotalCount(text) {
  if (!text) return null;
  const match = String(text).match(/共\s*(\d+)\s*条/);
  if (!match) return null;
  const totalCount = Number(match[1]);
  return Number.isSafeInteger(totalCount) && totalCount >= 0 ? totalCount : null;
}

function collectUrgentTicketsFromPages(pages, thresholdHours = DEFAULT_THRESHOLD_HOURS) {
  const seen = new Set();
  const urgent = [];
  let pagesRead = 0;
  let stoppedEarly = false;
  let stopTicket = null;

  for (const page of pages) {
    pagesRead += 1;
    for (const ticket of page || []) {
      if (!ticket || !ticket.workOrderNum) continue;
      if (seen.has(ticket.workOrderNum)) continue;
      seen.add(ticket.workOrderNum);

      if (ticket.totalHours != null && ticket.totalHours > thresholdHours) {
        stoppedEarly = true;
        stopTicket = ticket;
        return { urgent, pagesRead, stoppedEarly, stopTicket };
      }

      if (ticket.totalHours != null && ticket.totalHours <= thresholdHours) {
        urgent.push(ticket);
      }
    }
  }

  return { urgent, pagesRead, stoppedEarly, stopTicket };
}

function isAscendingByTotalHours(tickets) {
  let prev = null;
  for (const ticket of tickets || []) {
    if (!ticket || ticket.totalHours == null) continue;
    if (prev != null && ticket.totalHours < prev) return false;
    prev = ticket.totalHours;
  }
  return true;
}

function ticketFingerprint(tickets) {
  return (tickets || []).map(ticket => ticket && ticket.workOrderNum).join('|');
}

function makeStablePagePredicate(targetId, expectedPage, beforeTickets) {
  const beforeFingerprint = ticketFingerprint(beforeTickets);
  let previousFingerprint = null;
  let stableReads = 0;
  return async () => {
    const pageData = await cdp.eval(targetId, READ_CURRENT_PAGE_TICKETS_JS);
    if (!pageData || pageData.loading === true) return null;
    const pagination = normalizePaginationState(pageData.pagination || null);
    if (!pagination || pagination.currentPage !== expectedPage) return null;
    if (!Number.isSafeInteger(pagination.totalCount) || pagination.totalCount < 0) return null;
    const tickets = pageData.tickets || [];
    const fingerprint = ticketFingerprint(tickets);
    if (beforeFingerprint && fingerprint === beforeFingerprint) {
      stableReads = 0;
      previousFingerprint = fingerprint;
      return null;
    }
    stableReads = fingerprint === previousFingerprint ? stableReads + 1 : 1;
    previousFingerprint = fingerprint;
    return stableReads >= 2 ? pageData : null;
  };
}

function normalizePaginationState(raw) {
  const nextButton = raw && raw.nextButton ? raw.nextButton : null;
  const nextButtonFound = nextButton ? nextButton.found !== false : false;
  const pages = ((raw && raw.pages) || [])
    .filter(page => page && page.text != null)
    .map(page => ({
      text: String(page.text).trim(),
      active: Boolean(page.active),
      rect: page.rect || null,
    }));
  const activePage = pages.find(page => page.active);
  const currentPage = activePage
    ? parseInt(activePage.text, 10)
    : (raw && raw.currentPage != null ? parseInt(raw.currentPage, 10) : null);

  let reason = null;
  if (!nextButtonFound) {
    reason = '未找到下一页按钮';
  } else if (!nextButton.visible) {
    reason = '下一页按钮不可见';
  } else if (nextButton.disabled) {
    reason = '下一页按钮已禁用';
  }

  return {
    hasNext: Boolean(nextButtonFound && nextButton.visible && !nextButton.disabled),
    reason,
    totalCount: parseTotalCount(raw && raw.totalText),
    currentPage: Number.isFinite(currentPage) ? currentPage : null,
    pages,
    nextButton: nextButton ? {
      visible: Boolean(nextButton.visible),
      disabled: Boolean(nextButton.disabled),
      rect: nextButton.rect || null,
    } : null,
  };
}

function isTrustedThresholdStop(pageData, pagination, totalCount) {
  return pageData && pageData.loading !== true && Number.isSafeInteger(totalCount) && totalCount >= 0 &&
    pagination && Number.isSafeInteger(pagination.currentPage) && pagination.currentPage >= 1;
}

function isTrustedListEnd(pageData, pagination, totalCount) {
  if (!isTrustedThresholdStop(pageData, pagination, totalCount)) return false;
  return pagination.currentPage === Math.max(1, Math.ceil(totalCount / 10)) &&
    pagination.nextButton && pagination.nextButton.disabled === true;
}

async function findJlPageTarget() {
  const targets = await cdp.getTargets();
  const page = (targets || []).find(t =>
    t &&
    t.type === 'page' &&
    t.url &&
    t.url.includes(JL_DOMAIN)
  );
  if (!page) throw new Error('未找到鲸灵后台页面');
  return page;
}

const READ_CURRENT_PAGE_TICKETS_JS = `
(() => {
  function visible(el) {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rect.width > 0 &&
      rect.height > 0;
  }
  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return {
      left: r.left,
      top: r.top,
      width: r.width,
      height: r.height,
      centerX: r.left + r.width / 2,
      centerY: r.top + r.height / 2
    };
  }
  ${extractRemainingTimerText.toString()}
  function parseRemainingHours(text) {
    if (!text) return null;
    let m = String(text).match(/(\\d+)\\s*天\\s*(\\d+)\\s*小时\\s*(\\d+)\\s*分/);
    if (m) return parseInt(m[1], 10) * 24 + parseInt(m[2], 10) + parseInt(m[3], 10) / 60;
    m = String(text).match(/(\\d+)\\s*天\\s*(\\d+)\\s*小时/);
    if (m) return parseInt(m[1], 10) * 24 + parseInt(m[2], 10);
    m = String(text).match(/(\\d+)\\s*小时\\s*(\\d+)\\s*分/);
    if (m) return parseInt(m[1], 10) + parseInt(m[2], 10) / 60;
    m = String(text).match(/(\\d+)\\s*小时/);
    if (m) return parseInt(m[1], 10);
    return null;
  }
  function normalizeType(value) {
    if (value == null) return null;
    const text = String(value).trim();
    if (!text) return null;
    if (text === '323') return '仅退款';
    if (text.includes('仅退款')) return '仅退款';
    if (text.includes('退货退款')) return '退货退款';
    if (text.includes('换货')) return '换货';
    if (text.includes('补寄')) return '补寄';
    return null;
  }

  const cards = Array.from(document.querySelectorAll('#AfterSaleList .table_main')).filter(visible);
  const tickets = cards.map((card, index) => {
    const text = card.innerText || card.textContent || '';
    const lines = text.split(/\\n/).map(s => s.trim()).filter(Boolean);
    const workOrderNum = (text.match(/售后工单号[:：]\\s*(100001\\d{12,})/) || text.match(/100001\\d{12,}/) || [])[1] ||
      (text.match(/100001\\d{12,}/) || [])[0] || null;
    const orderNo = (text.match(/订单号[:：]\\s*([A-Za-z0-9]+)/) || [])[1] || null;
    const applyTime = (text.match(/申请时间[:：]\\s*(\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2})/) || [])[1] || null;
    const remaining = extractRemainingTimerText(card, visible);
    const totalHours = parseRemainingHours(remaining);
      const type = lines.map(normalizeType).find(Boolean) || null;
    const status = lines.find(l => /^商家-/.test(l)) || null;
    const tracking = lines.find(l => /^[A-Z]{1,4}\\d{8,}$/.test(l) || /^\\d{10,}$/.test(l)) || null;
    const typeIndex = type ? lines.indexOf(type) : -1;
    const reason = typeIndex >= 0 && lines[typeIndex + 1] && !/^[A-Z]{1,4}\\d{8,}$/.test(lines[typeIndex + 1])
      ? lines[typeIndex + 1]
      : null;
    const actionBtn = Array.from(card.querySelectorAll('button,[role=button],a'))
      .filter(visible)
      .find(btn => /^(处理|查看|售后处理)$/.test((btn.innerText || btn.textContent || '').trim()));

    return {
      index: index + 1,
      workOrderNum,
      remaining,
      totalHours,
      orderNo,
      applyTime,
      status,
      type,
      reason,
      returnTracking: tracking,
      actionButton: actionBtn ? {
        text: (actionBtn.innerText || actionBtn.textContent || '').trim(),
        rect: rectOf(actionBtn)
      } : null
    };
  });

  const pag = document.querySelector('.el-pagination');
  const totalEl = pag
    ? Array.from(pag.querySelectorAll('.el-pagination__total')).find(visible)
    : null;
  const totalText = totalEl
    ? (totalEl.innerText || totalEl.textContent || '').trim()
    : (pag && visible(pag) ? (pag.innerText || pag.textContent || '').trim() : null);
  const nextBtn = pag ? pag.querySelector('.btn-next') : null;
  const pageItems = pag
    ? Array.from(pag.querySelectorAll('.el-pager li')).filter(visible).map(item => ({
      text: (item.innerText || item.textContent || '').trim(),
      active: item.classList.contains('active'),
      rect: rectOf(item)
    }))
    : [];
  const sortInput = document.querySelector('input[placeholder="排序规则"]');
  const loading = Array.from(document.querySelectorAll('.el-loading-mask')).some(visible);
  // 读"待商家处理"后面的数字。如果是 0，说明此店铺没有待处理工单，
  // 调用方应跳过后续翻页/加载检测逻辑，避免误报"仍在加载/读取不完整"。
  var bodyText = document.body.innerText || '';
  var pendingMatch = bodyText.match(/待商家处理[^\\d]*(\\d+)/);
  var pendingCount = pendingMatch ? parseInt(pendingMatch[1], 10) : null;
  return JSON.stringify({
    tickets,
    loading,
    pendingCount,
    pagination: {
      totalText,
      nextButton: nextBtn ? {
        found: true,
        visible: visible(nextBtn),
        disabled: Boolean(nextBtn.disabled || nextBtn.classList.contains('disabled') || nextBtn.getAttribute('aria-disabled') === 'true'),
        rect: visible(nextBtn) ? rectOf(nextBtn) : null
      } : {
        found: false,
        visible: false,
        disabled: true,
        rect: null
      },
      pages: pageItems
    },
    sortValue: sortInput ? sortInput.value : null
  });
})()
`;

async function clickNextPage(targetId) {
  const raw = await cdp.eval(targetId, READ_CURRENT_PAGE_TICKETS_JS);
  const state = normalizePaginationState(raw && raw.pagination);

  if (!state.hasNext) {
    return { clicked: false, reason: state.reason || '下一页按钮不可点击', pagination: state };
  }

  // 分页条在页面底部（top ≈ 2400px），CDP 物理点击只接受 viewport 坐标。
  // 先向下大幅滚动使分页条进入 viewport，重读坐标，再物理点击——与 step 12 同原则。
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mouseWheel',
    x: 640,
    y: 400,
    deltaX: 0,
    deltaY: SCROLL_TO_BOTTOM_DELTA_PX,
    button: 'none',
  });
  await sleep(400);

  const raw2 = await cdp.eval(targetId, READ_CURRENT_PAGE_TICKETS_JS);
  const state2 = normalizePaginationState(raw2 && raw2.pagination);
  const nextRect = state2 && state2.nextButton && state2.nextButton.rect;

  if (!nextRect || !Number.isFinite(nextRect.centerX) || !Number.isFinite(nextRect.centerY)) {
    return { clicked: false, reason: '滚动后未能获取下一页按钮坐标', pagination: state2 || state };
  }

  await cdp.dispatchMouseEvent(targetId, {
    type: 'mouseMoved', x: nextRect.centerX, y: nextRect.centerY, button: 'none',
  });
  await sleep(MOVE_DELAY_MS);
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mousePressed', x: nextRect.centerX, y: nextRect.centerY, button: 'left', clickCount: 1,
  });
  await sleep(PRESS_DELAY_MS);
  await cdp.dispatchMouseEvent(targetId, {
    type: 'mouseReleased', x: nextRect.centerX, y: nextRect.centerY, button: 'left', clickCount: 1,
  });

  return { clicked: true, reason: null, pagination: state };
}

async function readUrgentAfterSaleList(options = {}) {
  const thresholdHours = options.thresholdHours == null
    ? DEFAULT_THRESHOLD_HOURS
    : Number(options.thresholdHours);
  const maxPages = options.maxPages || MAX_PAGES;
  const target = options.targetId
    ? { id: options.targetId }
    : await findJlPageTarget();

  const pages = [];
  let stopReason = null;
  let lastPagination = null;
  let totalCount = null;
  let sortValue = null;
  let prefetchedPageData = null;

  for (let pageIndex = 1; pageIndex <= maxPages; pageIndex++) {
    const pageData = prefetchedPageData || await cdp.eval(target.id, READ_CURRENT_PAGE_TICKETS_JS);
    prefetchedPageData = null;
    // 第一页"待商家处理"数为 0 → 此店铺没有待处理工单，直接返回空列表
    if (pageIndex === 1 && pageData && pageData.pendingCount === 0) {
      return {
        success: true,
        complete: true,
        targetId: target.id,
        thresholdHours,
        sortValue: pageData.sortValue || null,
        urgent: [],
        totalCollected: 0,
        totalCount: 0,
        pagesRead: 1,
        stoppedEarly: false,
        stopReason: '待商家处理数为 0，无需读取',
        stopTicket: null,
        pagination: normalizePaginationState(pageData.pagination || null),
      };
    }
    if (pageData && pageData.loading === true) {
      throw new Error(`售后工单列表第${pageIndex}页仍在加载，停止读取`);
    }
    const tickets = pageData.tickets || [];
    const invalidTimer = tickets.find(ticket => ticket && ticket.workOrderNum && ticket.totalHours == null);
    if (invalidTimer) {
      throw new Error(`售后工单 ${invalidTimer.workOrderNum} 倒计时解析失败，停止冻结48小时清单`);
    }
    pages.push(tickets);
    lastPagination = normalizePaginationState(pageData.pagination || null);
    if (lastPagination.totalCount != null) totalCount = lastPagination.totalCount;
    sortValue = pageData.sortValue || sortValue;

    const collected = collectUrgentTicketsFromPages(pages, thresholdHours);
    if (collected.stoppedEarly) {
      stopReason = `遇到超过 ${thresholdHours} 小时工单，停止读取`;
      return {
        success: true,
        complete: isTrustedThresholdStop(pageData, lastPagination, totalCount),
        targetId: target.id,
        thresholdHours,
        sortValue,
        urgent: collected.urgent,
        totalCollected: collected.urgent.length,
        totalCount,
        pagesRead: collected.pagesRead,
        stoppedEarly: true,
        stopReason,
        stopTicket: collected.stopTicket,
        pagination: lastPagination,
      };
    }

    if (!lastPagination || !lastPagination.hasNext) {
      return {
        success: true,
        complete: isTrustedListEnd(pageData, lastPagination, totalCount),
        targetId: target.id,
        thresholdHours,
        sortValue,
        urgent: collected.urgent,
        totalCollected: collected.urgent.length,
        totalCount,
        pagesRead: collected.pagesRead,
        stoppedEarly: false,
        stopReason: lastPagination && lastPagination.reason ? lastPagination.reason : '没有下一页',
        stopTicket: null,
        pagination: lastPagination,
      };
    }

    const nextPage = (lastPagination.currentPage || pageIndex) + 1;
    const clickResult = await clickNextPage(target.id);
    if (!clickResult.clicked) {
      return {
        success: true,
        complete: false,
        targetId: target.id,
        thresholdHours,
        sortValue,
        urgent: collected.urgent,
        totalCollected: collected.urgent.length,
        totalCount,
        pagesRead: collected.pagesRead,
        stoppedEarly: false,
        stopReason: clickResult.reason || '下一页按钮不可点击',
        stopTicket: null,
        pagination: clickResult.pagination || lastPagination,
      };
    }

    await sleep(1500);
    prefetchedPageData = await waitFor(
      makeStablePagePredicate(target.id, nextPage, tickets),
      { timeoutMs: 8000, intervalMs: 500, label: `翻页到第${nextPage}页并等待列表刷新稳定` }
    );
  }

  const collected = collectUrgentTicketsFromPages(pages, thresholdHours);
  return {
    success: true,
    complete: false,
    targetId: target.id,
    thresholdHours,
    sortValue,
    urgent: collected.urgent,
    totalCollected: collected.urgent.length,
    totalCount,
    pagesRead: collected.pagesRead,
    stoppedEarly: collected.stoppedEarly,
    stopReason: '达到最大页数',
    stopTicket: collected.stopTicket,
    pagination: lastPagination,
  };
}

if (require.main === module) {
  const thresholdHours = process.argv[2] ? Number(process.argv[2]) : DEFAULT_THRESHOLD_HOURS;
  readUrgentAfterSaleList({ thresholdHours })
    .then(result => {
      console.log(JSON.stringify(result));
      process.exit(0);
    })
    .catch(error => {
      console.log(JSON.stringify({ success: false, error: error.message }));
      process.exit(1);
    });
}

module.exports = {
  readUrgentAfterSaleList,
  clickNextPage,
  READ_CURRENT_PAGE_TICKETS_JS,
  parseRemainingHours,
  extractRemainingTimerText,
  parseTotalCount,
  collectUrgentTicketsFromPages,
  isAscendingByTotalHours,
  normalizePaginationState,
  isTrustedThresholdStop,
  isTrustedListEnd,
  DEFAULT_THRESHOLD_HOURS,
};
