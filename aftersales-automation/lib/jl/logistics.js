'use strict';
/**
 * WHAT: 读取鲸灵工单物流信息
 * WHERE: collect.js 数据采集 → CLI logistics 命令 → 此模块
 * WHY: 物流是判断退回成功/拦截成功的唯一依据
 * ENTRY: cli.js: logistics 命令, collect.js: 采集物流数据
 */
const cdp = require('../cdp');
const { navigate } = require('./navigate');
const { sleep } = require('../wait');
const { ok, fail } = require('../result');

// 读取鲸灵物流弹窗（多包裹多 tab）
const OPEN_LOGISTICS_JS = `(function(){
  var btns = Array.from(document.querySelectorAll('button.el-button--text.el-button--mini, a, button'));
  var btn = btns.find(function(b){
    return b.textContent.trim() === '查看物流' && b.getBoundingClientRect().width > 0;
  });
  if (!btn) return JSON.stringify({error:'未找到查看物流按钮'});
  btn.click();
  return 'clicked';
})()`;

const READ_LOGISTICS_TABS_JS = `(function(){
  var dialogs = Array.from(document.querySelectorAll('.el-dialog__wrapper')).filter(function(d){
    return window.getComputedStyle(d).display !== 'none';
  });
  if (!dialogs.length) return JSON.stringify({error:'物流弹窗未打开'});
  var dialog = dialogs[0];
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
    var dialog = dialogs[0];
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

async function getLogistics(targetId, workOrderNum) {
  try {
    await navigate(targetId, '/business/after-sale-detail', { workOrderNum });
    await cdp.eval(targetId, OPEN_LOGISTICS_JS);
    await sleep(2000);

    const tabsRaw = await cdp.eval(targetId, READ_LOGISTICS_TABS_JS);
    const tabsData = tabsRaw;
    if (tabsData.error) throw new Error(tabsData.error);

    const packages = [];
    // 读取第一个 tab（已激活）
    packages.push({ tab: tabsData.tabs[0]?.name || '包裹1', text: tabsData.currentText });

    // 如有多个 tab，逐一切换读取
    for (let i = 1; i < tabsData.tabCount; i++) {
      const tabName = tabsData.tabs[i]?.name;
      if (!tabName) continue;
      await cdp.eval(targetId, makeClickTabJS(tabName));
      await sleep(1000);
      const freshRaw = await cdp.eval(targetId, READ_LOGISTICS_TABS_JS);
      const freshData = freshRaw;
      packages.push({ tab: tabName, text: freshData.currentText });
    }

    await cdp.eval(targetId, CLOSE_DIALOG_JS);

    return ok({ packages });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { getLogistics };
