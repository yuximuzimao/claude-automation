'use strict';
/**
 * WHAT: ERP 订单物流读取（逐行或全部）
 * WHERE: collect.js 物流采集 → CLI erp-logistics/erp-logistics-all → 此模块
 * WHY: ERP 物流是判断发货状态和物流进度的唯一权威数据源
 * ENTRY: cli.js: erp-logistics / erp-logistics-all 命令
 */
const cdp = require('../cdp');
const { sleep, waitFor, retry } = require('../wait');
const { ok, fail } = require('../result');
const { checkLogin, recoverLogin } = require('./navigate');

// 展开订单行并打开 show_detail_dialog 读物流
function makeOpenDialogJS(rowIndex) {
  return `(function(){
    var rows = Array.from(document.querySelectorAll('.module-trade-list-item'));
    var row = rows[${rowIndex}];
    if (!row) return JSON.stringify({error:'行 ${rowIndex} 不存在，共 ' + rows.length + ' 行'});
    // 展开（如果未展开）
    var isExpanded = !!row.querySelector('.module-trade-list-item-row2');
    if (!isExpanded) {
      var trigger = row.querySelector('.J_Trigger_Show_Orders');
      if (trigger) trigger.click();
    }
    return JSON.stringify({expanded: isExpanded, rowText: row.innerText.substring(0, 100)});
  })()`;
}

function makeClickDetailJS(rowIndex) {
  return `(function(){
    var rows = Array.from(document.querySelectorAll('.module-trade-list-item'));
    var row = rows[${rowIndex}];
    if (!row) return JSON.stringify({error:'行不存在'});
    var link = row.querySelector('a[data-name=show_detail_dialog][data-sid]');
    if (!link) return JSON.stringify({error:'show_detail_dialog 链接未找到'});
    link.click();
    return JSON.stringify({clicked: true, sid: link.getAttribute('data-sid')});
  })()`;
}

const READ_LOGISTICS_JS = `(function(){
  var container = document.querySelector('.js-logistics-container');
  if (!container) return JSON.stringify({error:'物流容器未打开'});
  var navBox = document.querySelector('.box-nav.box-toogle-el');
  var tracking = navBox ? (navBox.innerText.match(/运单号[：:]\s*([\\w]+)/) || [])[1] : '';
  return JSON.stringify({
    tracking: tracking || '',
    logisticsText: container.innerText.substring(0, 3000)
  });
})()`;

const CLOSE_DETAIL_JS = `(function(){
  // 关闭最顶层的 trade-detail-dialog（Element UI，关闭按钮 class=el-dialog__closeBtn）
  var wrappers = Array.from(document.querySelectorAll('.el-dialog__wrapper.trade-detail-dialog')).filter(function(e){
    return e.getBoundingClientRect().width > 0;
  });
  if (!wrappers.length) return 'none';
  var last = wrappers[wrappers.length - 1];
  var btn = last.querySelector('.el-dialog__closeBtn');
  if (btn) { btn.click(); return 'closed'; }
  return 'btn not found';
})()`;

// 检测还剩多少层 trade-detail-dialog
const DIALOG_COUNT_JS = `Array.from(document.querySelectorAll('.el-dialog__wrapper.trade-detail-dialog')).filter(function(e){
  return e.getBoundingClientRect().width > 0;
}).length`;

async function readErpLogistics(targetId, rowIndex) {
  try {
    // 登录检查 + 自动恢复
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) {
      await recoverLogin(targetId);
    }
    // 展开行
    const expand = await cdp.eval(targetId, makeOpenDialogJS(rowIndex));
    if (expand.error) throw new Error(expand.error);
    if (!expand.expanded) await sleep(2000); // 等待展开动画

    // 打开订单详情弹窗
    const click = await cdp.eval(targetId, makeClickDetailJS(rowIndex));
    if (click.error) throw new Error(click.error);

    // 等待物流容器出现（最多 10s）
    await waitFor(
      async () => cdp.eval(targetId, `!!document.querySelector('.js-logistics-container')`),
      { timeoutMs: 10000, intervalMs: 500, label: '等待物流容器' }
    );

    // 读物流
    const log = await cdp.eval(targetId, READ_LOGISTICS_JS);
    if (log.error) throw new Error(log.error);

    // 关闭弹窗，逐层清除直到全部消失（最多等 8s）
    for (let i = 0; i < 16; i++) {
      const count = await cdp.eval(targetId, DIALOG_COUNT_JS);
      if (!count) break;
      await cdp.eval(targetId, CLOSE_DETAIL_JS);
      await sleep(500);
    }

    return ok({ rowIndex, tracking: log.tracking, logisticsText: log.logisticsText });
  } catch (e) {
    return fail(e);
  }
}

// 读取所有行的物流信息（遍历每行展开→详情→读物流→关闭）
async function readAllErpLogistics(targetId) {
  try {
    // 登录检查
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) await recoverLogin(targetId);

    // 获取总行数
    const rowCount = await cdp.eval(targetId,
      `Array.from(document.querySelectorAll('.module-trade-list-item')).length`
    );
    if (!rowCount || rowCount === 0) return ok({ results: [], note: '无ERP行' });

    const results = [];
    for (let i = 0; i < rowCount; i++) {
      try {
        const r = await readErpLogistics(targetId, i);
        if (r.success) {
          results.push(r.data);
        } else {
          results.push({ rowIndex: i, error: r.error });
        }
      } catch (e) {
        results.push({ rowIndex: i, error: e.message });
      }
    }
    return ok({ results });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { readErpLogistics, readAllErpLogistics };
