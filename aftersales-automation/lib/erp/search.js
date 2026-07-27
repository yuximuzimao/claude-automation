'use strict';
/**
 * WHAT: ERP 订单搜索 + READ_ROWS_JS 解析订单行（含订单状态）
 * WHERE: collect.js 数据采集 → CLI erp-search 命令 → 此模块
 * WHY: 订单状态解析缺失终态会导致空值传播到 infer.js → escalate 误报
 * ENTRY: cli.js: erp-search 命令, collect.js: 采集 ERP 订单数据
 */
const cdp = require('../cdp');
const {
  navigateErp,
  forceReloadErpPage,
  checkLogin,
  recoverLogin,
  CLOSE_ALL_DIALOGS_JS,
} = require('./navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

function parsePlatformOrderIds(text) {
  return String(text || '')
    .split(/[；;]/)
    .map(id => id.trim())
    .filter(Boolean);
}

function validatePlatformOrderRows(rows, subOrderId) {
  const expected = String(subOrderId);
  rows.forEach((row, index) => {
    const ids = Array.isArray(row.platformOrderIds)
      ? row.platformOrderIds.map(String)
      : parsePlatformOrderIds(row.platformTradeText);
    if (!ids.length) {
      throw new Error(`ERP搜索结果第${index + 1}行未读取到平台交易号`);
    }
    if (!ids.includes(expected)) {
      throw new Error(`ERP搜索结果第${index + 1}行平台交易号不包含搜索子订单 ${expected}（实际：${ids.join('；')}）`);
    }
  });
}

// 填入子订单号并搜索，返回所有行信息
function makeSearchJS(subOrderId) {
  const expected = JSON.stringify(String(subOrderId));
  return `(function(){
    // 找可见的搜索输入框（过滤隐藏元素，见错误#35）
    var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
      var r = i.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    // 用 placeholder 精确匹配搜索框（见 docs/ops-tech.md #3, 坑#35）
    var inp = inputs.find(function(i){ return i.placeholder && i.placeholder.includes('系统单号'); });
    // 禁止 fallback：找不到精确字段直接报错，不能填错位置
    if (!inp) return JSON.stringify({error:'未找到系统单号搜索框，当前页面可见input placeholders: ' + inputs.map(function(i){return i.placeholder;}).join('|')});
    inp.click();
    inp.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');
    document.execCommand('insertText', false, ${expected});
    if (inp.value !== ${expected}) return JSON.stringify({error:'填值失败: ' + inp.value, placeholder: inp.placeholder});
    ['keydown','keypress','keyup'].forEach(function(type){
      inp.dispatchEvent(new KeyboardEvent(type, {key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
    });
    return JSON.stringify({filled: inp.value, placeholder: inp.placeholder, enterSent: true});
  })()`;
}

// 确保 mixKey radio 已勾选（见 docs/ops-tech.md #4）
const CHECK_MIXKEY_JS = `(function(){
  var radio = document.querySelector('input[value="mixKey"]');
  return JSON.stringify({exists: !!radio, checked: radio ? radio.checked : false});
})()`;

const READ_ORDER_PAGE_READINESS_JS = `(function(){
  var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
    var r = i.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  var searchInput = inputs.find(function(i){
    return i.placeholder && i.placeholder.includes('系统单号');
  });
  var radio = document.querySelector('input[value="mixKey"]');
  var sessionExpired = !!document.querySelector('.inner-login-wrapper');
  var masks = Array.from(document.querySelectorAll('.el-loading-mask'));
  var loading = masks.some(function(m){
    var s = window.getComputedStyle(m);
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
  });
  return JSON.stringify({
    ready: !!searchInput && !!radio && radio.checked && !loading && !sessionExpired,
    hasSearchInput: !!searchInput,
    searchValue: searchInput ? searchInput.value : null,
    mixKeyExists: !!radio,
    mixKeyChecked: radio ? radio.checked : false,
    loading: loading,
    sessionExpired: sessionExpired
  });
})()`;

// 读取搜索结果所有行
const READ_ROWS_JS = `(function(){
  var countMatch = document.body.innerText.match(/共(\\d+)条/);
  var totalCount = countMatch ? parseInt(countMatch[1]) : 0;
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'));
  return JSON.stringify({
    totalCount: totalCount,
    rows: rows.map(function(row){
      var text = row.innerText;
      var platformCell = row.querySelector('.trade-cell.trade-ptid[data-field="ptid"]') || row.querySelector('.trade-cell.trade-ptid');
      var platformTradeText = platformCell ? platformCell.innerText.trim() : '';
      var platformOrderIds = platformCell
        ? Array.from(platformCell.querySelectorAll('span')).map(function(span){ return span.innerText.trim(); }).filter(Boolean)
        : [];
      if (!platformOrderIds.length && platformTradeText) {
        platformOrderIds = platformTradeText.split(/[；;]/).map(function(id){ return id.trim(); }).filter(Boolean);
      }
      // 内部单号（ERP内部编号，纯数字9位左右）
      var internalId = (text.match(/\\t(\\d{9,12})\\t/) || [])[1];
      // 快递单号：提取所有"物流 复制"前的快递单号（分包时同一行可能有多个）
      var trackingMatches = Array.from(text.matchAll(/(\\S+)\\n物流\\n复制/g));
      var trackings = trackingMatches.map(function(m){ return m[1]; }).filter(Boolean);
      var tracking = trackings[0] || null;
      // 状态
      var status = '';
      if (text.includes('待审核')) status = '待审核';
      else if (text.includes('待打印')) status = '待打印快递单';
      else if (text.includes('待发货')) status = '待发货';
      else if (text.includes('卖家已发货')) status = '卖家已发货';
      else if (text.includes('交易成功')) status = '交易成功';
      else if (text.includes('交易关闭')) status = '交易关闭';
      return { internalId, platformTradeText, platformOrderIds, tracking, trackings, status, textSnippet: text.substring(0, 150) };
    })
  });
})()`;

async function ensureOrderPageReady(targetId) {
  await retry(async () => {
    const mk = await cdp.eval(targetId, CHECK_MIXKEY_JS);
    if (!mk.exists) throw new Error('mixKey radio 不存在');
    if (!mk.checked) {
      await cdp.clickAt(targetId, 'input[value="mixKey"]');
      await sleep(800);
    }
    const readiness = await cdp.eval(targetId, READ_ORDER_PAGE_READINESS_JS);
    if (!readiness.ready) {
      throw new Error(
        `订单管理页未就绪（搜索框=${readiness.hasSearchInput ? '有' : '无'}，` +
        `mixKey=${readiness.mixKeyChecked ? '已选' : '未选'}，` +
        `loading=${readiness.loading ? '是' : '否'}，登录浮层=${readiness.sessionExpired ? '有' : '无'}）`
      );
    }
  }, { maxRetries: 8, delayMs: 1200, label: 'ERP订单页 readiness' });
  return cdp.eval(targetId, READ_ORDER_PAGE_READINESS_JS);
}

async function prepareErpOrderPage(targetId, options = {}) {
  if (options.forceReload) {
    await forceReloadErpPage(targetId, '订单管理');
  } else {
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) await recoverLogin(targetId);
    await cdp.eval(targetId, CLOSE_ALL_DIALOGS_JS);
    await navigateErp(targetId, '订单管理');
  }
  const readiness = await ensureOrderPageReady(targetId);
  return { targetId, page: '订单管理', reloaded: !!options.forceReload, readiness };
}

async function performSearchAttempt(targetId, subOrderId, options) {
  // 保留已验证的原搜索动作：激活输入框、同一 eval 填值并 Enter。
  await cdp.clickAt(targetId, 'input.el-input__inner');
  await sleep(800);

  const FINGERPRINT_JS = `(function(){
    var items = Array.from(document.querySelectorAll('.module-trade-list-item'));
    return items.map(function(r){ return r.innerText.substring(0,30); }).join('|');
  })()`;
  const prevFingerprint = await cdp.eval(targetId, FINGERPRINT_JS);

  const fill = await cdp.eval(targetId, makeSearchJS(subOrderId));
  if (fill.error) throw new Error(fill.error);
  if (!fill.placeholder || !fill.placeholder.includes('系统单号')) {
    throw new Error(`填入字段不正确，placeholder: ${fill.placeholder}，期望含「系统单号」`);
  }

  let newFingerprint = '';
  for (let w = 0; w < 20; w++) {
    await sleep(500);
    newFingerprint = await cdp.eval(targetId, FINGERPRINT_JS);
    if (!prevFingerprint && newFingerprint) break;
    if (prevFingerprint && newFingerprint && newFingerprint !== prevFingerprint) break;
  }
  if (newFingerprint === prevFingerprint) {
    const countText = await cdp.eval(targetId, `(document.body.innerText.match(/共\\d+条/) || [''])[0]`);
    if (!countText) throw new Error('搜索未执行（指纹未变且无共N条文字）');
  }

  const rows = await cdp.eval(targetId, READ_ROWS_JS);
  if (options.validatePlatformOrderId !== false) {
    validatePlatformOrderRows(rows.rows || [], subOrderId);
  }
  return rows;
}

async function runSearchWithSingleRecovery(searchAttempt, recoverPage, onFirstFailure = () => {}) {
  try {
    return await searchAttempt(0);
  } catch (firstError) {
    onFirstFailure(firstError);
    await recoverPage(firstError);
    return searchAttempt(1);
  }
}

async function erpSearch(targetId, subOrderId, options = {}) {
  try {
    await prepareErpOrderPage(targetId);

    const rows = await runSearchWithSingleRecovery(
      () => performSearchAttempt(targetId, subOrderId, options),
      () => prepareErpOrderPage(targetId, { forceReload: true }),
      error => {
        console.warn(
          `[erp-search] 子订单 ${subOrderId} 首次搜索未形成可信结果，` +
          `强制刷新订单页后重试一次：${error.message}`
        );
      }
    );

    return ok({ subOrderId, rows });
  } catch (e) {
    return fail(e);
  }
}

module.exports = {
  erpSearch,
  prepareErpOrderPage,
  parsePlatformOrderIds,
  validatePlatformOrderRows,
  runSearchWithSingleRecovery,
  makeSearchJS,
};
