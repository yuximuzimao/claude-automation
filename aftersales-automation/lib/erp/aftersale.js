'use strict';
/**
 * WHAT: ERP 售后工单搜索（按退货快递单号查）
 * WHERE: collect.js 退货核验 → CLI erp-aftersale 命令 → 此模块
 * WHY: 退货退款必须到 ERP 售后工单新版验收，展开所有行逐项核对
 * ENTRY: cli.js: erp-aftersale 命令, collect.js: 退货采集
 */
const cdp = require('../cdp');
const { navigateErp, CLOSE_ALL_DIALOGS_JS } = require('./navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 填退回快递单号并点查询
function makeSearchTrackingJS(tracking) {
  return `(function(){
    var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
      var r = i.getBoundingClientRect(); return r.width > 0 && r.height > 0;
    });
    var inp = inputs.find(function(i){ return i.placeholder === '退回快递单号'; });
    if (!inp) return JSON.stringify({error:'未找到退回快递单号输入框'});
    inp.click(); inp.focus();
    document.execCommand('selectAll');
    document.execCommand('insertText', false, '${tracking}');
    var btn = Array.from(document.querySelectorAll('button')).find(function(b){
      return b.innerText.trim() === '查询' && b.getBoundingClientRect().width > 0;
    });
    if (!btn) return JSON.stringify({error:'未找到查询按钮', filled: inp.value});
    btn.click();
    return JSON.stringify({searched: inp.value});
  })()`;
}

// 读所有主行（有展开图标）和已展开的明细行
// 明细行在展开容器 TR (nextSibling, class="") 内的嵌套 table 中，不是顶层 sibling
const READ_AFTERSALE_ROWS_JS = `(function(){
  var allRows = Array.from(document.querySelectorAll('tr.el-table__row'));

  // 主行：有展开图标
  var mainRows = allRows.filter(function(r){ return r.querySelector('.el-table__expand-icon'); });
  if (!mainRows.length) return JSON.stringify({error:'未找到工单行'});

  var result = [];
  for (var mi = 0; mi < mainRows.length; mi++) {
    var mr = mainRows[mi];
    var cells = Array.from(mr.querySelectorAll('td')).map(function(td){ return td.innerText.trim(); });
    // 列定义（0-based）: 0=expand, 1=序号, 3=售后工单号, 4=工单来源, 5=平台订单号,
    //   6=售后类型, 8=货物状态, 12=快递单号, 18=实退数量
    var rec = {
      erpOrderId: cells[3] || '',
      source: cells[4] || '',
      platformOrderId: cells[5] || '',
      goodsStatus: cells[8] || '',
      tracking: cells[12] || '',
      returnQty: parseInt(cells[18]) || 0,
      isExpanded: mr.classList.contains('expanded'),
      items: []
    };

    // 明细行在展开容器 TR（nextSibling，class=""）内的嵌套 table 的 tr.el-table__row 中
    if (rec.isExpanded) {
      var container = mr.nextElementSibling;
      if (container && container.tagName === 'TR' && !container.classList.contains('el-table__row')) {
        var itemRows = Array.from(container.querySelectorAll('tr.el-table__row'));
        itemRows.forEach(function(ir){
          var tds = Array.from(ir.querySelectorAll('td'));
          var dc = tds.map(function(td){ return td.innerText.trim(); });
          // 列定义: [2]=商品名称, [4]=商品简称, [5]=主商家编码(specCode), [8]=申请数(qty)
          // ⚠️ [9]=数量（良品）, [10]=数量（次品）是 el-input-number 组件，值在 input.value 而非 innerText
          if (dc[1] === '退货' && dc[2]) {
            var rawCode = dc[5] || '';
            var specCode = rawCode.split(' ')[0];  // 去掉" 正常"等后缀
            var qtyGoodInp = tds[9] ? tds[9].querySelector('input') : null;
            var qtyBadInp = tds[10] ? tds[10].querySelector('input') : null;
            rec.items.push({
              name: dc[2],
              shortTitle: dc[4] || '',
              specCode: specCode,
              qty: parseInt(dc[8]) || 0,
              qtyGood: parseInt(qtyGoodInp ? qtyGoodInp.value : '') || 0,
              qtyBad: parseInt(qtyBadInp ? qtyBadInp.value : '') || 0
            });
          }
        });
      }
    }

    result.push(rec);
  }
  return JSON.stringify(result);
})()`;

// 展开所有货物状态=卖家已收到退货的主行
const EXPAND_RECEIVED_ROWS_JS = `(function(){
  var expanded = 0;
  Array.from(document.querySelectorAll('tr.el-table__row')).forEach(function(r){
    if (!r.querySelector('.el-table__expand-icon')) return;
    var cells = Array.from(r.querySelectorAll('td')).map(function(td){ return td.innerText.trim(); });
    var goodsStatus = cells[8] || '';
    if (goodsStatus.includes('已收到退货') && !r.classList.contains('expanded')) {
      r.querySelector('.el-table__expand-icon').click();
      expanded++;
    }
  });
  return JSON.stringify({expanded: expanded});
})()`;

async function erpAftersale(targetId, tracking) {
  try {
    // 清理残留弹窗
    await cdp.eval(targetId, CLOSE_ALL_DIALOGS_JS);

    await navigateErp(targetId, '售后工单新版');
    // navigateErp 已内含 waitForPageContent 轮询，无需额外 sleep

    // 搜索退货快递单号
    await retry(async () => {
      const search = await cdp.eval(targetId, makeSearchTrackingJS(tracking));
      if (search.error) throw new Error(search.error);
      await sleep(3000);
      const hasResult = await cdp.eval(targetId, `document.body.innerText.includes('${tracking}')`);
      if (!hasResult) throw new Error(`搜索结果未包含快递单号 ${tracking}`);
    }, { maxRetries: 3, delayMs: 2000, label: `erp-aftersale ${tracking}` });

    // 展开已收到退货的行
    await retry(async () => {
      const exp = await cdp.eval(targetId, EXPAND_RECEIVED_ROWS_JS);
      if (exp.error) throw new Error(exp.error);
    }, { maxRetries: 3, delayMs: 1500, label: `expand-received-rows ${tracking}` });
    await sleep(2500);

    // 读取所有行数据
    const rows = await retry(async () => {
      const r = await cdp.eval(targetId, READ_AFTERSALE_ROWS_JS);
      if (r.error) throw new Error(r.error);
      return r;
    }, { maxRetries: 3, delayMs: 1500, label: `read-aftersale-rows ${tracking}` });

    return ok({ tracking, rows });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { erpAftersale };
