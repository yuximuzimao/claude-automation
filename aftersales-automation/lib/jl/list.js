'use strict';
/**
 * WHAT: 鲸灵工单列表扫描（≤48小时）
 * WHERE: scan-all.js → CLI list 命令 → 此模块
 * WHY: 扫描窗口定位有串位历史（§18），必须用 Math.max 修正
 * ENTRY: cli.js: list 命令, scan-all.js: 定时扫描
 */
const cdp = require('../cdp');
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
      // 倒计时（多级正则：精确到分钟，向后兼容无分钟/无天的格式）
      if (rec.days === undefined) {
        var tm;
        // 优先级1：完整格式 "X天 X小时 X分"
        tm = line.match(/(\\d+)\\s*天\\s*(\\d+)\\s*小时\\s*(\\d+)\\s*分/);
        if (tm) {
          rec.days = parseInt(tm[1]);
          rec.hours = parseInt(tm[2]);
          rec.minutes = parseInt(tm[3]);
          rec.totalHours = rec.days * 24 + rec.hours + rec.minutes / 60;
        } else {
          // 优先级2：无分钟 "X天 X小时"
          tm = line.match(/(\\d+)\\s*天\\s*(\\d+)\\s*小时/);
          if (tm) {
            rec.days = parseInt(tm[1]);
            rec.hours = parseInt(tm[2]);
            rec.totalHours = rec.days * 24 + rec.hours;
          } else {
            // 优先级3：无天 "X小时 X分"
            tm = line.match(/(\\d+)\\s*小时\\s*(\\d+)\\s*分/);
            if (tm) {
              rec.days = 0;
              rec.hours = parseInt(tm[1]);
              rec.minutes = parseInt(tm[2]);
              rec.totalHours = rec.hours + rec.minutes / 60;
            } else {
              // 优先级4：仅小时 "X小时"
              tm = line.match(/(\\d+)\\s*小时/);
              if (tm) {
                rec.days = 0;
                rec.hours = parseInt(tm[1]);
                rec.totalHours = rec.hours;
              }
            }
          }
        }
        if (rec.totalHours !== undefined) {
          rec.deadlineAt = new Date(Date.now() + rec.totalHours * 3600000).toISOString();
        } else {
          rec.urgencySource = 'text-fallback';
        }
      }
      // 售后类型（只取第一个匹配）
      if (!rec.type) {
        if (line.includes('退货退款')) rec.type = '退货退款';
        else if (line.includes('仅退款')) rec.type = '仅退款';
        else if (line.includes('换货')) rec.type = '换货';
      }
    }

    if ((rec.totalHours !== undefined || rec.urgencySource === 'text-fallback') && rec.type) workOrders.push(rec);
  }

  // 按剩余时间升序（最紧急在前）
  workOrders.sort(function(a, b){ if (a.totalHours == null) return 1; if (b.totalHours == null) return -1; return a.totalHours - b.totalHours; });
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

// 点击"待商家处理"筛选标签（确保只读该状态下的工单）
// 页面左侧有状态标签列表，找含"待商家处理"文本的标签并点击
const CLICK_PENDING_FILTER_JS = `(function(){
  var candidates = Array.from(document.querySelectorAll('span, div, li, a, p'));
  for (var i = 0; i < candidates.length; i++) {
    var el = candidates[i];
    if (el.children.length > 0) continue;
    var txt = el.textContent.trim();
    if (/^待商家处理/.test(txt)) {
      el.click();
      return 'clicked:' + txt;
    }
  }
  return 'not-found';
})()`;

// 一步完成：全页导航到工单列表 + 等待加载 + 检查登录
// 合并了原来的 reloadAndCheckLogin + navigate 两步（从 3 次刷新减少到 1 次）
async function navigateAndCheckLogin(targetId) {
  await cdp.navigate(targetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');

  await waitFor(
    async () => {
      const state = await cdp.eval(targetId, 'document.readyState');
      return state === 'complete';
    },
    { timeoutMs: 20000, intervalMs: 500, label: '页面加载完成' }
  );

  // 等待 Vue 应用初始化（确保后续 Vue Router 操作可用）
  await waitFor(
    async () => {
      try {
        const ready = await cdp.eval(targetId, `!!(document.querySelector('#app') && document.querySelector('#app').__vue__)`);
        return ready || null;
      } catch { return null; }
    },
    { timeoutMs: 10000, intervalMs: 1000, label: 'Vue 应用初始化' }
  );

  const url = await cdp.eval(targetId, 'window.location.href');
  if (!url.includes('jlsupp.com') || url.includes('login') || url.includes('sso')) {
    throw new Error(`鲸灵登录已失效，当前URL: ${url}，请手动重新登录后再试`);
  }
}

async function listTickets(targetId, maxHours) {
  try {
    await navigateAndCheckLogin(targetId);

    // 点击"待商家处理"筛选标签（确保只读该状态，不混入其他状态工单）
    try {
      const clickRes = await cdp.eval(targetId, CLICK_PENDING_FILTER_JS);
      if (clickRes && clickRes !== 'not-found') {
        await sleep(1500); // 等待筛选后列表刷新
      }
    } catch (e) { /* non-critical */ }

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
    const urgent = deduped.filter(t => t.totalHours != null && t.totalHours <= threshold);

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
