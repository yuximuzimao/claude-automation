#!/usr/bin/env node
'use strict';
/**
 * 鲸灵 A1 — 原子步骤 11：固定导航售后列表并准备 48 小时内工单。
 *
 * 串联流程：
 *   1. 对目标 tab 直接导航固定售后列表 URL。
 *   2. 等 3 秒，检测页面标题「售后工单」和快捷筛选「待商家处理」。
 *   3. 点击排序下拉框，选择「按逾期时间最近排序」。
 *   4. 等 5 秒，检测下拉框值已切换，且当前列表时效从小到大。
 *   5. 读取 48 小时内工单列表；遇到超过 48 小时即停止。
 *
 * 本步不点击任何工单「处理」按钮。
 */

const path = require('path');
const cdp = require(path.join(__dirname, '../../lib/cdp'));
const { selectOverdueSort, TARGET_SORT } = require('./09-select-overdue-sort');
const {
  readUrgentAfterSaleList,
  isAscendingByTotalHours,
} = require('./10-read-urgent-after-sale-list');

const AFTER_NAVIGATION_WAIT_MS = 3000;
const AFTER_SORT_WAIT_MS = 5000;
const AFTER_SALE_LIST_URL = 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function assertAfterSaleListReady(targetId) {
  const status = await cdp.eval(targetId, `
(() => {
  const bodyText = document.body ? document.body.innerText || '' : '';
  const hasTitle = bodyText.includes('售后工单');
  const hasPendingFilter = bodyText.includes('待商家处理');
  return JSON.stringify({
    success: hasTitle && hasPendingFilter,
    title: document.title,
    url: location.href,
    hasTitle,
    hasPendingFilter
  });
})()
`);
  if (!status || !status.success) {
    throw new Error(`未到售后列表页: ${JSON.stringify(status)}`);
  }
  return status;
}

async function readCurrentPageSortCheck(targetId) {
  const data = await cdp.eval(targetId, `
(() => {
  function visible(el) {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rect.width > 0 &&
      rect.height > 0;
  }
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
  const sortInput = document.querySelector('input[placeholder="排序规则"]');
  const tickets = Array.from(document.querySelectorAll('#AfterSaleList .table_main'))
    .filter(visible)
    .map(card => {
      const text = card.innerText || card.textContent || '';
      const workOrderNum = (text.match(/售后工单号[:：]\\s*(100001\\d{12,})/) || text.match(/100001\\d{12,}/) || [])[1] ||
        (text.match(/100001\\d{12,}/) || [])[0] || null;
      const remaining = (text.split(/\\n/).map(s => s.trim()).find(l => /后自动/.test(l))) || null;
      return { workOrderNum, remaining, totalHours: parseRemainingHours(remaining) };
    })
    .filter(t => t.workOrderNum);
  return JSON.stringify({
    sortValue: sortInput ? sortInput.value : null,
    tickets
  });
})()
`);
  const sortOk = data && data.sortValue === TARGET_SORT;
  const ascending = isAscendingByTotalHours(data && data.tickets);
  if (!sortOk || !ascending) {
    throw new Error(`排序校验失败: ${JSON.stringify({ sortValue: data && data.sortValue, sortOk, ascending, tickets: data && data.tickets })}`);
  }
  return { ...data, ascending };
}

async function prepareAfterSaleList(options = {}) {
  const thresholdHours = options.thresholdHours == null ? 48 : Number(options.thresholdHours);
  const targetId = options.targetId;
  if (!targetId) throw new Error('缺少目标鲸灵 targetId');

  await cdp.navigate(targetId, AFTER_SALE_LIST_URL);
  await sleep(AFTER_NAVIGATION_WAIT_MS);

  const listReady = await assertAfterSaleListReady(targetId);
  const sorted = await selectOverdueSort({ targetId });
  await sleep(AFTER_SORT_WAIT_MS);

  const sortCheck = await readCurrentPageSortCheck(targetId);
  const list = await readUrgentAfterSaleList({
    targetId,
    thresholdHours,
  });

  return {
    success: true,
    targetId,
    listReady,
    sorted,
    sortCheck,
    list,
  };
}

if (require.main === module) {
  const targetId = process.argv[2];
  const thresholdHours = process.argv[3] ? Number(process.argv[3]) : 48;
  prepareAfterSaleList({ targetId, thresholdHours })
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
  prepareAfterSaleList,
  assertAfterSaleListReady,
  readCurrentPageSortCheck,
  AFTER_NAVIGATION_WAIT_MS,
  AFTER_SORT_WAIT_MS,
  AFTER_SALE_LIST_URL,
};
