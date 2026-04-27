'use strict';
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { ok, fail } = require('../result');
const { sleep, waitFor } = require('../wait');

// 读工单列表：返回所有工单，带倒计时信息
// 解析策略：先定位所有工单号行，再按区间扫描各字段，避免字段顺序依赖导致的串位
const READ_LIST_JS = `(function(){
  var text = document.body.innerText;
  var lines = text.split('\\n').map(function(l){ return l.trim(); });
  var workOrders = [];

  // 第一步：找所有工单号的行号
  var positions = [];
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/1000017\\d{10,}/);
    if (m) positions.push({ idx: i, num: m[0] });
  }

  // 第二步：按区间扫描（从上一条末尾到下一条开头），避免跨票串位
  for (var t = 0; t < positions.length; t++) {
    var center = positions[t].idx;
    var winStart = Math.max(t > 0 ? positions[t-1].idx + 1 : 0, center - 3);
    var winEnd = t + 1 < positions.length ? positions[t+1].idx : Math.min(lines.length, center + 25);
    var rec = { workOrderNum: positions[t].num };

    for (var i = winStart; i < winEnd; i++) {
      var line = lines[i];
      // 倒计时（只取第一个匹配）
      if (rec.days === undefined) {
        var tm = line.match(/(\\d+)\\s*天\\s*(\\d+)\\s*小时/);
        if (tm) {
          rec.days = parseInt(tm[1]);
          rec.hours = parseInt(tm[2]);
          rec.totalHours = rec.days * 24 + rec.hours;
          rec.deadlineAt = new Date(Date.now() + rec.totalHours * 3600000).toISOString();
        }
      }
      // 售后类型（只取第一个匹配）
      if (!rec.type) {
        if (line.includes('退货退款')) rec.type = '退货退款';
        else if (line.includes('仅退款')) rec.type = '仅退款';
        else if (line.includes('换货')) rec.type = '换货';
      }
    }

    if (rec.totalHours !== undefined && rec.type) workOrders.push(rec);
  }

  // 按剩余时间升序（最紧急在前）
  workOrders.sort(function(a, b){ return a.totalHours - b.totalHours; });
  return JSON.stringify(workOrders);
})()`;

// 读分页信息（Element UI el-pagination）
const READ_PAGINATION_JS = `(function(){
  var pag = document.querySelector('.el-pagination');
  if (!pag) return JSON.stringify({ hasNext: false, currentPage: 1, totalItems: null });
  var nextBtn = pag.querySelector('.btn-next');
  var active = pag.querySelector('.el-pager .active');
  var total = pag.querySelector('.el-pagination__total');
  var totalMatch = total && total.textContent.match(/(\\d+)/);
  return JSON.stringify({
    hasNext: nextBtn ? !nextBtn.disabled : false,
    currentPage: active ? parseInt(active.textContent) : 1,
    totalItems: totalMatch ? parseInt(totalMatch[1]) : null
  });
})()`;

// 读取"待商家处理"筛选按钮的数字
const READ_FILTER_COUNT_JS = `(function(){
  var bodyText = document.body.innerText;
  var m = bodyText.match(/待商家处理\\s*(\\d+)/);
  return JSON.stringify({ filterCount: m ? parseInt(m[1]) : null });
})()`;

// 点击下一页
const CLICK_NEXT_PAGE_JS = `(function(){
  var btn = document.querySelector('.el-pagination .btn-next');
  if (btn && !btn.disabled) { btn.click(); return 'clicked'; }
  return 'no-next';
})()`;

// 刷新页面并等待加载完成，检查鲸灵登录状态
async function reloadAndCheckLogin(targetId) {
  await cdp.eval(targetId, 'location.reload()');
  await sleep(3000);

  await waitFor(
    async () => {
      const state = await cdp.eval(targetId, 'document.readyState');
      return state === 'complete';
    },
    { timeoutMs: 15000, intervalMs: 500, label: '页面刷新完成' }
  );

  const url = await cdp.eval(targetId, 'window.location.href');
  if (!url.includes('jlsupp.com') || url.includes('login') || url.includes('sso')) {
    throw new Error(`鲸灵登录已失效，当前URL: ${url}，请手动重新登录后再试`);
  }
}

async function listTickets(targetId, maxHours) {
  try {
    await reloadAndCheckLogin(targetId);
    await navigate(targetId, '/business/after-sale-list');

    // 读取"待商家处理"筛选按钮数字
    let filterCount = null;
    try {
      const fc = await cdp.eval(targetId, READ_FILTER_COUNT_JS);
      filterCount = fc && fc.filterCount;
    } catch (e) { /* non-critical */ }

    // 读第一页
    let allOrders = [];
    const page1 = await cdp.eval(targetId, READ_LIST_JS);
    allOrders = allOrders.concat(page1);

    // 翻页读取后续页面
    const MAX_PAGES = 20;
    for (let page = 2; page <= MAX_PAGES; page++) {
      const pag = await cdp.eval(targetId, READ_PAGINATION_JS);
      if (!pag.hasNext) break;

      const clickResult = await cdp.eval(targetId, CLICK_NEXT_PAGE_JS);
      if (clickResult !== 'clicked') break;

      // 等新页面渲染完成（当前页码变化）
      await sleep(1500);
      await waitFor(
        async () => {
          const p = await cdp.eval(targetId, READ_PAGINATION_JS);
          return p.currentPage === page;
        },
        { timeoutMs: 8000, intervalMs: 500, label: `翻页到第${page}页` }
      );

      const pageOrders = await cdp.eval(targetId, READ_LIST_JS);
      allOrders = allOrders.concat(pageOrders);
    }

    // 按 workOrderNum 去重（页面边界可能重叠）
    const seen = new Set();
    const deduped = [];
    for (const order of allOrders) {
      if (!seen.has(order.workOrderNum)) {
        seen.add(order.workOrderNum);
        deduped.push(order);
      }
    }

    const threshold = maxHours !== undefined ? maxHours : 48;
    const urgent = deduped.filter(t => t.totalHours <= threshold);

    // 数量校验
    let mismatchWarning = null;
    if (filterCount !== null && filterCount !== deduped.length) {
      mismatchWarning = `待商家处理显示 ${filterCount} 条，实际采集 ${deduped.length} 条`;
    }

    return ok({ urgent, totalCollected: deduped.length, filterCount, mismatchWarning });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { listTickets };
