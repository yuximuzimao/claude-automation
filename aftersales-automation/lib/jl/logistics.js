'use strict';
/**
 * WHAT: 读取鲸灵工单物流信息
 * WHERE: collect.js 数据采集 → CLI logistics 命令 → 此模块
 * WHY: 物流是判断退回成功/拦截成功的唯一依据
 * ENTRY: cli.js: logistics 命令, collect.js: 采集物流数据
 */
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { sleep, waitFor } = require('../wait');
const { ok, fail } = require('../result');

// Step 0: 展开所有折叠的子订单（「查看剩余子订单(N)」按钮）
const EXPAND_SUB_ORDERS_JS = `(function(){
  var btns = Array.from(document.querySelectorAll('button')).filter(function(b){
    return b.textContent.trim().includes('查看剩余子订单') && b.getBoundingClientRect().width > 0;
  });
  btns.forEach(function(b){ b.click(); });
  return btns.length;
})()`;

// Step 1: 统计当前可见的「查看物流」按钮数量
const COUNT_LOGISTICS_BTNS_JS = `(function(){
  var btns = Array.from(document.querySelectorAll('button')).filter(function(b){
    return b.textContent.trim() === '查看物流' && b.getBoundingClientRect().width > 0;
  });
  return btns.length;
})()`;

// Step 2: 点击第 idx 个「查看物流」按钮
function makeClickNthLogisticsBtnJS(idx) {
  return `(function(){
    var btns = Array.from(document.querySelectorAll('button')).filter(function(b){
      return b.textContent.trim() === '查看物流' && b.getBoundingClientRect().width > 0;
    });
    if (!btns[${idx}]) return JSON.stringify({error:'未找到第${idx+1}个查看物流按钮'});
    btns[${idx}].click();
    return 'clicked';
  })()`;
}

const READ_LOGISTICS_TABS_JS = `(function(){
  var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!dialogs.length) return JSON.stringify({error:'物流弹窗未打开'});
  // 取最后一个（最新打开的）弹窗，避免读到上一个未完成关闭的弹窗
  var dialog = dialogs[dialogs.length - 1];
  var tabs = Array.from(dialog.querySelectorAll('.el-tabs__item')).map(function(t){
    return { name: t.textContent.trim(), active: t.classList.contains('is-active'), el: t };
  });
  return JSON.stringify({
    tabCount: tabs.length,
    tabs: tabs.map(function(t){ return {name: t.name, active: t.active}; }),
    currentText: dialog.innerText.substring(0, 2000)
  });
})()`;

function makeClickTabJS(tabName) {
  return `(function(){
    var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
      return window.getComputedStyle(d).display !== 'none';
    });
    var dialog = dialogs[dialogs.length - 1];
    var tab = Array.from(dialog.querySelectorAll('.el-tabs__item')).find(function(t){
      return t.textContent.trim() === '${tabName}';
    });
    if (!tab) return 'not found';
    tab.click();
    return 'clicked';
  })()`;
}

const CLOSE_DIALOG_JS = `(function(){
  var closeBtns = Array.from(document.querySelectorAll('.el-dialog__headerbtn, .el-icon-close'));
  var btn = closeBtns.find(function(b){ return b.getBoundingClientRect().width > 0; });
  if (btn) btn.click();
  return 'closed';
})()`;

// 当前可见弹窗数量（用于检测弹窗是否已关闭：关闭前记录数量，关闭后等数量减少）
const VISIBLE_DIALOG_COUNT_JS = `Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
  return window.getComputedStyle(d).display !== 'none';
}).length`;

async function getLogistics(targetId, workOrderNum) {
  try {
    await navigate(targetId, '/business/after-sale-detail', { workOrderNum });

    // Step 0: 展开折叠的子订单
    const expandCount = await cdp.eval(targetId, EXPAND_SUB_ORDERS_JS);
    if (expandCount > 0) await sleep(1500);

    // Step 1: 统计所有「查看物流」按钮
    const btnCount = await cdp.eval(targetId, COUNT_LOGISTICS_BTNS_JS);
    if (!btnCount) throw new Error('未找到查看物流按钮');

    const packages = [];

    // Step 2: 逐个子订单读取物流
    for (let btnIdx = 0; btnIdx < btnCount; btnIdx++) {
      const clickResult = await cdp.eval(targetId, makeClickNthLogisticsBtnJS(btnIdx));
      if (typeof clickResult === 'object' && clickResult.error) {
        packages.push({ tab: `子订单${btnIdx + 1}`, error: clickResult.error });
        continue;
      }
      await sleep(1500);

      const tabsData = await cdp.eval(targetId, READ_LOGISTICS_TABS_JS);
      if (tabsData.error) {
        packages.push({ tab: `子订单${btnIdx + 1}`, error: tabsData.error });
        continue;
      }

      // 读取当前激活 tab
      packages.push({ tab: tabsData.tabs[0]?.name || `包裹${packages.length + 1}`, text: tabsData.currentText });

      // 如有多个 tab（同一子订单多包裹），逐一切换
      for (let i = 1; i < tabsData.tabCount; i++) {
        const tabName = tabsData.tabs[i]?.name;
        if (!tabName) continue;
        await cdp.eval(targetId, makeClickTabJS(tabName));
        await sleep(800);
        const freshData = await cdp.eval(targetId, READ_LOGISTICS_TABS_JS);
        packages.push({ tab: tabName, text: freshData.currentText });
      }

      // 关闭前记录当前弹窗数，等数量减少（不要求「全部关闭」，避免页面有持久弹窗导致超时）
      const beforeClose = await cdp.eval(targetId, VISIBLE_DIALOG_COUNT_JS);
      await cdp.eval(targetId, CLOSE_DIALOG_JS);
      await waitFor(
        async () => {
          const cur = await cdp.eval(targetId, VISIBLE_DIALOG_COUNT_JS);
          return cur < beforeClose;
        },
        { timeoutMs: 5000, intervalMs: 300, label: '等待物流弹窗关闭' }
      );
    }

    return ok({ packages });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { getLogistics };
