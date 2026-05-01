'use strict';
const cdp = require('./cdp');
const { sleep, retry } = require('./wait');
const { navigateErp } = require('./navigate');

// 直接移植自售后工单项目 lib/product/archive.js
// 方法：DOM 输入法（模拟用户在「主商家编码」框打字）+ 精确查询下拉 + 遍历父组件找 handleQuery

const SET_EXACT_QUERY_JS =
  '(function(){' +
  '  var inputs=Array.from(document.querySelectorAll("input.el-input__inner")).filter(function(i){' +
  '    var r=i.getBoundingClientRect();return r.width>0&&r.height>0;' +
  '  });' +
  '  var qt=inputs.find(function(i){return i.placeholder==="查询类型";});' +
  '  if(!qt) return JSON.stringify({error:"查询类型下拉不存在"});' +
  '  if(qt.value==="精确查询") return JSON.stringify({alreadySet:true});' +
  '  var sel=qt.closest(".el-select");' +
  '  if(sel) sel.click();' +
  '  return JSON.stringify({opened:true});' +
  '})()';

const CLICK_EXACT_OPTION_JS =
  '(function(){' +
  '  var li=Array.from(document.querySelectorAll("li.el-select-dropdown__item")).find(function(e){' +
  '    var r=e.getBoundingClientRect();' +
  '    return e.textContent.trim()==="精确查询"&&r.width>0;' +
  '  });' +
  '  if(!li){' +
  '    var span=Array.from(document.querySelectorAll("span")).find(function(e){' +
  '      var r=e.getBoundingClientRect();' +
  '      return e.textContent.trim()==="精确查询"&&e.children.length===0&&r.width>0;' +
  '    });' +
  '    if(!span) return JSON.stringify({error:"精确查询选项不可见"});' +
  '    span.click();return JSON.stringify({clicked:true,via:"span"});' +
  '  }' +
  '  li.click();return JSON.stringify({clicked:true,via:"li"});' +
  '})()';

function makeSearchSpecCodeJS(specCode) {
  const escaped = JSON.stringify(specCode);
  return '(function(){' +
    '  var inputs=Array.from(document.querySelectorAll("input.el-input__inner")).filter(function(i){' +
    '    var r=i.getBoundingClientRect();return r.width>0&&r.height>0;' +
    '  });' +
    '  var mainInp=inputs.find(function(i){return i.placeholder==="主商家编码";});' +
    '  if(!mainInp) return JSON.stringify({error:"主商家编码输入框不存在"});' +
    '  mainInp.value=' + escaped + ';' +
    '  mainInp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  mainInp.dispatchEvent(new Event("change",{bubbles:true}));' +
    '  var el=mainInp;var sv=null;' +
    '  for(var i=0;i<12;i++){' +
    '    if(!el) break;' +
    '    var v=el.__vue__;' +
    '    if(v&&typeof v.handleQuery==="function"){sv=v;break;}' +
    '    el=el.parentElement;' +
    '  }' +
    '  if(!sv) return JSON.stringify({error:"未找到 handleQuery"});' +
    '  sv.handleQuery();' +
    '  return JSON.stringify({searched:' + escaped + '});' +
    '})()';
}

const READ_DATALIST_JS =
  '(function(){' +
  '  var el=document.querySelector(".el-input__inner[placeholder=\\"主商家编码\\"]");' +
  '  if(!el) return JSON.stringify({error:"未找到输入框"});' +
  '  var v=el;var sv=null;' +
  '  for(var i=0;i<12;i++){' +
  '    if(!v) break;' +
  '    var vm=v.__vue__;' +
  '    if(vm&&vm.dataList){sv=vm;break;}' +
  '    v=v.parentElement;' +
  '  }' +
  '  if(!sv||!sv.dataList||!sv.dataList.length){' +
  '    return JSON.stringify({error:"dataList 为空",count:sv?sv.dataList.length:-1});' +
  '  }' +
  '  var item=sv.dataList[0];' +
  '  return JSON.stringify({outerId:item.outerId,title:item.title,type:item.type,subItemNum:item.subItemNum||0});' +
  '})()';

/**
 * 初始化：导航到档案V2页面并等待加载完成
 * reload → 登录检测 → hash 验证（移植自售后项目 navigateErp）
 */
async function initArchiveComp(erpId) {
  await navigateErp(erpId, '商品档案V2');
  await sleep(1000);
  // 清空所有列头筛选条件（防止上次操作遗留"普通商品"等筛选）
  const cleared = await cdp.eval(erpId,
    '(function(){' +
    '  var btn = Array.from(document.querySelectorAll("button, span")).find(function(b){' +
    '    return b.innerText && b.innerText.trim() === "清空条件" && b.getBoundingClientRect().width > 0;' +
    '  });' +
    '  if(!btn) return JSON.stringify({skipped:"清空条件 not found"});' +
    '  btn.click(); return JSON.stringify({cleared:true});' +
    '})()'
  );
  console.error('[archive] 清空条件:', cleared);
  await sleep(1500);
  console.error('[archive] 页面就绪');
}

/**
 * 查询单个 ERP 编码（主商家编码），移植自售后项目
 * @param {string} erpId
 * @param {string} erpCode
 * @returns {Promise<{outerId,title,type,subItemNum}|null>}
 */
async function queryArchive(erpId, erpCode) {
  if (!erpCode) return null;

  // Step 1: 确保精确查询模式
  await retry(async () => {
    const set = await cdp.eval(erpId, SET_EXACT_QUERY_JS);
    if (set.error) throw new Error(set.error);
    if (!set.alreadySet) {
      await sleep(600);
      const click = await cdp.eval(erpId, CLICK_EXACT_OPTION_JS);
      if (click.error) throw new Error(click.error);
      await sleep(500);
    }
  }, { maxRetries: 3, delayMs: 800, label: 'set exact query' });

  // Step 2: 输入编码并搜索，读取结果
  const item = await retry(async () => {
    const search = await cdp.eval(erpId, makeSearchSpecCodeJS(erpCode));
    if (search.error) throw new Error(search.error);
    await sleep(3500);
    const d = await cdp.eval(erpId, READ_DATALIST_JS);
    if (d.error && d.count === 0) return null; // 档案里找不到该编码
    if (d.error) throw new Error(d.error);
    return d;
  }, { maxRetries: 3, delayMs: 2000, label: `queryArchive ${erpCode}` });

  return item || null;
}

// 点击子商品数字链接（a.ml_15）展开单品明细弹窗
function makeClickSubItemLinkJS(subItemNum) {
  return '(function(){' +
    '  var el=Array.from(document.querySelectorAll("a.ml_15")).find(function(a){' +
    '    var r=a.getBoundingClientRect();' +
    '    return a.innerText.trim()===' + JSON.stringify(String(subItemNum)) + '&&r.width>0;' +
    '  });' +
    '  if(!el) return JSON.stringify({error:"subItem link not found for num=' + subItemNum + '"});' +
    '  el.click();return JSON.stringify({clicked:true});' +
    '})()';
}

// 读子商品明细表格（列定义: [1]=商品名称, [3]=商家编码, [10]=组合数量）
// ⚠️ 必须限定在可见 dialog 内读取，防止读到主页面的行
const READ_SUB_ITEMS_JS =
  '(function(){' +
  '  var dialogs=Array.from(document.querySelectorAll(".el-dialog__wrapper")).filter(function(d){' +
  '    return window.getComputedStyle(d).display!=="none";' +
  '  });' +
  '  if(!dialogs.length) return JSON.stringify({error:"子商品弹窗未打开"});' +
  '  var dialog=dialogs[dialogs.length-1];' +
  '  var rows=Array.from(dialog.querySelectorAll("tr.el-table__row"));' +
  '  var items=[];' +
  '  rows.forEach(function(r){' +
  '    var cells=Array.from(r.querySelectorAll("td")).map(function(td){return td.innerText.trim();});' +
  '    if(cells[1]&&cells[3]&&cells[10]&&!isNaN(parseInt(cells[10]))){' +
  '      items.push({name:cells[1],specCode:cells[3],qty:parseInt(cells[10])});' +
  '    }' +
  '  });' +
  '  return JSON.stringify(items.length?items:{error:"弹窗内未找到子商品行"});' +
  '})()';

// 关闭子商品弹窗（⚠️ 关闭按钮是 el-dialog__closeBtn，不是 el-dialog__headerbtn）
const CLOSE_SUB_DIALOG_JS =
  '(function(){' +
  '  var visible=Array.from(document.querySelectorAll(".el-dialog__wrapper")).filter(function(d){' +
  '    return window.getComputedStyle(d).display!=="none";' +
  '  });' +
  '  if(!visible.length) return JSON.stringify({skipped:"no visible dialog"});' +
  '  var btn=visible[0].querySelector("button.el-dialog__closeBtn");' +
  '  if(!btn) return JSON.stringify({skipped:"no closeBtn"});' +
  '  btn.click();return JSON.stringify({closed:true});' +
  '})()';

/**
 * 读取组合装的子品明细
 * @param {string} erpId
 * @param {number} subItemNum - 子品数量（用于定位点击链接）
 * @returns {Promise<Array<{name, specCode, qty}>>}
 */
async function querySubItems(erpId, subItemNum) {
  try {
    const clickRes = await cdp.eval(erpId, makeClickSubItemLinkJS(subItemNum));
    if (clickRes && clickRes.error) {
      console.error(`[archive] ⚠️ 点击子品链接失败: ${clickRes.error}`);
      return [];
    }
    await sleep(1500);
    const raw = await cdp.eval(erpId, READ_SUB_ITEMS_JS);
    return Array.isArray(raw) ? raw : [];
  } finally {
    await cdp.eval(erpId, CLOSE_SUB_DIALOG_JS);
    await sleep(600);
  }
}

module.exports = { initArchiveComp, queryArchive, querySubItems };
