'use strict';

const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');

const {
  readUrgentAfterSaleList,
  READ_CURRENT_PAGE_TICKETS_JS,
  parseRemainingHours,
  extractRemainingTimerText,
  parseTotalCount,
  attachPlatformStageObservations,
  collectUrgentTicketsFromPages,
  isAscendingByTotalHours,
  normalizePaginationState,
} = require('../../scripts/jl-steps/10-read-urgent-after-sale-list');

const SOURCE_PATH = path.join(__dirname, '../../scripts/jl-steps/10-read-urgent-after-sale-list.js');

test('parseRemainingHours parses days hours and minutes', () => {
  assert.equal(parseRemainingHours('1 天 5 小时 51 分 后自动退货退款'), 29 + 51 / 60);
  assert.equal(parseRemainingHours('47 小时 30 分 后自动退货退款'), 47.5);
  assert.equal(parseRemainingHours('2 天 0 小时 1 分 后自动退货退款'), 48 + 1 / 60);
});

test('列表从倒计时组件读取文本，不依赖平台后缀白名单', () => {
  const hiddenTimer = { innerText: '0 天 1 小时 0 分 后自动退款', visible: false };
  const visibleTimer = { innerText: '1 天 14 小时 45 分 后流转至客服', visible: true };
  const card = {
    querySelectorAll(selector) {
      assert.equal(selector, '.el-timer');
      return [hiddenTimer, visibleTimer];
    },
  };

  const remaining = extractRemainingTimerText(card, timer => timer.visible);
  assert.equal(remaining, '1 天 14 小时 45 分 后流转至客服');
  assert.equal(parseRemainingHours(remaining), 38.75);
  assert.equal(parseRemainingHours('0 天 15 小时 24 分 后供应商处理超时'), 15.4);
  assert.match(READ_CURRENT_PAGE_TICKETS_JS, /querySelectorAll\(['"]\.el-timer['"]\)/);
  assert.doesNotMatch(READ_CURRENT_PAGE_TICKETS_JS, /后自动|供应商处理超时|流转至客服/);
});

test('parseTotalCount parses pagination totals with or without spaces', () => {
  assert.equal(parseTotalCount('共5条'), 5);
  assert.equal(parseTotalCount('共 21 条'), 21);
  assert.equal(parseTotalCount('共0条'), 0);
});

test('parseTotalCount returns null for missing or malformed pagination text', () => {
  assert.equal(parseTotalCount(null), null);
  assert.equal(parseTotalCount(''), null);
  assert.equal(parseTotalCount('第 1 页'), null);
  assert.equal(parseTotalCount('共五条'), null);
  assert.equal(parseTotalCount('共 -1 条'), null);
});

test('列表扫描为所有工单保存平台阶段，缺失时也显式标记', () => {
  const tickets = attachPlatformStageObservations([
    { workOrderNum: '100001700000000000001', status: '商家-待商家二次发货' },
    { workOrderNum: '100001700000000000002', status: null },
  ], '2026-08-10T00:00:00.000Z');

  assert.deepEqual(tickets.map(ticket => ticket.platformStage), [
    {
      raw: '商家-待商家二次发货',
      observedAt: '2026-08-10T00:00:00.000Z',
      source: 'after-sale-list',
      readState: 'read',
    },
    {
      raw: null,
      observedAt: '2026-08-10T00:00:00.000Z',
      source: 'after-sale-list',
      readState: 'missing',
    },
  ]);
});

test('collectUrgentTicketsFromPages stops at first ticket over 48 hours and skips later pages', () => {
  const pages = [
    [
      { workOrderNum: '100001700000000000001', totalHours: 1 },
      { workOrderNum: '100001700000000000002', totalHours: 47.99 },
      { workOrderNum: '100001700000000000003', totalHours: 48.01 },
      { workOrderNum: '100001700000000000004', totalHours: 10 },
    ],
    [
      { workOrderNum: '100001700000000000005', totalHours: 2 },
    ],
  ];

  const result = collectUrgentTicketsFromPages(pages, 48);

  assert.deepEqual(result.urgent.map(t => t.workOrderNum), [
    '100001700000000000001',
    '100001700000000000002',
  ]);
  assert.equal(result.pagesRead, 1);
  assert.equal(result.stoppedEarly, true);
  assert.equal(result.stopTicket.workOrderNum, '100001700000000000003');
});

test('collectUrgentTicketsFromPages dedupes before returning urgent tickets', () => {
  const pages = [
    [
      { workOrderNum: '100001700000000000001', totalHours: 1 },
      { workOrderNum: '100001700000000000001', totalHours: 1 },
      { workOrderNum: '100001700000000000002', totalHours: 49 },
    ],
  ];

  const result = collectUrgentTicketsFromPages(pages, 48);

  assert.deepEqual(result.urgent.map(t => t.workOrderNum), ['100001700000000000001']);
});

test('isAscendingByTotalHours requires non-decreasing ticket order', () => {
  assert.equal(isAscendingByTotalHours([
    { totalHours: 1 },
    { totalHours: 1 },
    { totalHours: 2.5 },
  ]), true);

  assert.equal(isAscendingByTotalHours([
    { totalHours: 2 },
    { totalHours: 1 },
  ]), false);
});

test('clickNextPage 先向下滚动再物理点击，不使用 Vue emit', () => {
  const source = fs.readFileSync(SOURCE_PATH, 'utf8');
  const start = source.indexOf('async function clickNextPage');
  const end = source.indexOf('\nasync function readUrgentAfterSaleList', start);
  assert.notEqual(start, -1);
  assert.notEqual(end, -1);

  const body = source.slice(start, end);
  assert.doesNotMatch(body, /\$emit/);
  assert.match(body, /mouseWheel/);
  assert.match(body, /dispatchMouseEvent/);
  assert.match(body, /mousePressed/);
});

test('normalizePaginationState preserves active current page and visible page rects', () => {
  const result = normalizePaginationState({
    nextButton: {
      visible: true,
      disabled: false,
      rect: { left: 120, top: 300, width: 28, height: 28, centerX: 134, centerY: 314 },
    },
    pages: [
      { text: '1', active: true, visible: true, rect: { left: 40, top: 300, width: 28, height: 28, centerX: 54, centerY: 314 } },
      { text: '2', active: false, visible: true, rect: { left: 72, top: 300, width: 28, height: 28, centerX: 86, centerY: 314 } },
      { text: '...', active: false, visible: true, rect: { left: 104, top: 300, width: 28, height: 28, centerX: 118, centerY: 314 } },
    ],
  });

  assert.equal(result.currentPage, 1);
  assert.equal(result.hasNext, true);
  assert.deepEqual(result.pages, [
    { text: '1', active: true, rect: { left: 40, top: 300, width: 28, height: 28, centerX: 54, centerY: 314 } },
    { text: '2', active: false, rect: { left: 72, top: 300, width: 28, height: 28, centerX: 86, centerY: 314 } },
    { text: '...', active: false, rect: { left: 104, top: 300, width: 28, height: 28, centerX: 118, centerY: 314 } },
  ]);
});

test('readUrgentAfterSaleList returns structured totalCount from pagination text', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => ({
    tickets: [],
    pagination: {
      totalText: '共 21 条',
      nextButton: {
        found: true,
        visible: true,
        disabled: true,
        rect: null,
      },
      pages: [
        { text: '3', active: true, rect: null },
      ],
    },
    sortValue: '按逾期时间最近排序',
  });

  try {
    const result = await readUrgentAfterSaleList({ targetId: 'test-target' });
    assert.equal(result.totalCount, 21);
    assert.equal(result.complete, true);
  } finally {
    cdp.eval = originalEval;
  }
});

test('readUrgentAfterSaleList 主入口返回的平台阶段已随48小时清单留存', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => ({
    tickets: [{
      workOrderNum: '100001700000000000001',
      type: '换货',
      status: '商家-待商家二次发货',
      totalHours: 1,
    }],
    loading: false,
    pagination: {
      totalText: '共1条',
      nextButton: { found: true, visible: true, disabled: true, rect: null },
      pages: [{ text: '1', active: true, rect: null }],
    },
    sortValue: '按逾期时间最近排序',
  });

  try {
    const result = await readUrgentAfterSaleList({ targetId: 'test-target' });
    assert.equal(result.urgent.length, 1);
    assert.equal(result.urgent[0].platformStage.raw, '商家-待商家二次发货');
    assert.equal(result.urgent[0].platformStage.readState, 'read');
  } finally {
    cdp.eval = originalEval;
  }
});

test('totalCount推导有3页但当前仅第1页且next禁用时complete=false', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => ({ tickets: [], loading: false, pagination: {
    totalText: '共21条', nextButton: { found: true, visible: true, disabled: true, rect: null },
    pages: [{ text: '1', active: true, rect: null }],
  } });
  try {
    const result = await readUrgentAfterSaleList({ targetId: 'test-target' });
    assert.equal(result.complete, false);
  } finally { cdp.eval = originalEval; }
});

test('列表仍loading时即使遇到阈值外工单也不得complete', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => ({
    tickets: [{ workOrderNum: '100001700000000000001', totalHours: 49 }], loading: true,
    pagination: { totalText: '共1条', nextButton: { found: true, visible: true, disabled: true, rect: null }, pages: [{ text: '1', active: true }] },
  });
  try {
    await assert.rejects(readUrgentAfterSaleList({ targetId: 'test-target' }), /loading|加载/);
  } finally { cdp.eval = originalEval; }
});

test('有工单号但倒计时解析失败时停止冻结清单，不静默跳过', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => ({
    tickets: [{ workOrderNum: '100001700000000000001', remaining: '未知倒计时', totalHours: null }],
    loading: false,
    pagination: { totalText: '共1条', nextButton: { found: true, visible: true, disabled: true, rect: null }, pages: [{ text: '1', active: true }] },
  });
  try {
    await assert.rejects(readUrgentAfterSaleList({ targetId: 'test-target' }), /倒计时解析失败/);
  } finally { cdp.eval = originalEval; }
});

test('中间页loading且hasNext时立即停止，不收集也不点击下一页', async () => {
  const originalEval = cdp.eval;
  const originalCall = cdp.cdpCall;
  let clicks = 0;
  cdp.eval = async () => ({
    tickets: [{ workOrderNum: '100001700000000000001', totalHours: 1 }], loading: true,
    pagination: {
      totalText: '共21条', nextButton: { found: true, visible: true, disabled: false, rect: { centerX: 10, centerY: 10 } },
      pages: [{ text: '1', active: true }],
    },
  });
  cdp.cdpCall = async () => { clicks += 1; };
  try {
    await assert.rejects(readUrgentAfterSaleList({ targetId: 'test-target' }), /loading|加载/);
    assert.equal(clicks, 0);
  } finally { cdp.eval = originalEval; cdp.cdpCall = originalCall; }
});
