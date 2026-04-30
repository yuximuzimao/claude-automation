'use strict';
/**
 * 确保浏览器在商品对应表页面 + 智能判断链
 *
 * ensureCorrPage: 检测 hash，不在则 navigateErp，在则清空搜索条件（重置 UI 状态）
 * canSkipSearch:  严格 4 项校验，全通过才允许跳过搜索
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');
const { sleep } = require('../wait');
const { navigateErp } = require('../navigate');

const CORR_HASH = '#/prod/prod_correspondence_next/';
const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * 确保当前在商品对应表页面
 * - 若不在：full navigateErp
 * - 若已在：清空搜索框（从干净状态开始），不做 reload（节省时间）
 */
async function ensureCorrPage(erpId) {
  const hash = await cdp.eval(erpId, 'window.location.hash');
  if (hash !== CORR_HASH) {
    await navigateErp(erpId, '商品对应表');
  } else {
    // 已在对应表，只清空搜索条件（el-input-popup-editor 内的输入框）
    await cdp.eval(erpId,
      '(function(){' +
      '  var editor=document.querySelector(".el-input-popup-editor");' +
      '  if(!editor) return;' +
      '  var inp=editor.querySelector("input");' +
      '  if(!inp) return;' +
      '  inp.value="";' +
      '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
      '})()'
    );
    await sleep(300);
  }
}

/**
 * 严格 4 项校验：全部通过才返回 true
 * 1. 当前搜索输入框值 = productCode
 * 2. 表格首行 productCode = productCode
 * 3. 子行数量 = expectedSkuCount
 * 4. 当前行已展开
 *
 * @param {string} erpId
 * @param {string} shopName
 * @param {string} productCode
 * @param {number} expectedSkuCount - 来自 sku-records.json，不信任内存
 */
async function canSkipSearch(erpId, shopName, productCode, expectedSkuCount) {
  try {
    const result = await cdp.eval(erpId,
      '(function(){' +
      // 检查 1：搜索输入框值（el-input-popup-editor 内）
      '  var editor=document.querySelector(".el-input-popup-editor");' +
      '  var searchInp=editor?editor.querySelector("input"):null;' +
      '  var c1=searchInp&&searchInp.value.trim()===' + JSON.stringify(productCode) + ';' +
      // 检查 2：首行 productCode
      '  var rows=document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row");' +
      '  var c2=false;' +
      '  if(rows.length>0){' +
      '    var tds=rows[0].querySelectorAll("td");' +
      '    c2=tds[6]&&tds[6].innerText.trim()===' + JSON.stringify(productCode) + ';' +
      '  }' +
      // 检查 3：子行数量
      '  var ec=document.querySelector(".el-table__expanded-cell");' +
      '  var subCount=ec?ec.querySelectorAll("tbody tr").length:0;' +
      '  var c3=subCount===' + expectedSkuCount + ';' +
      // 检查 4：已展开
      '  var c4=!!document.querySelector(".el-table__expand-icon--expanded");' +
      '  return JSON.stringify({c1:!!c1,c2:!!c2,c3:c3,c4:c4,subCount:subCount});' +
      '})()'
    );
    const checks = typeof result === 'string' ? JSON.parse(result) : result;
    const ok = checks.c1 && checks.c2 && checks.c3 && checks.c4;
    if (!ok) {
      console.error(`[canSkipSearch] 跳过条件不满足: ${JSON.stringify(checks)}`);
    }
    return ok;
  } catch {
    return false;
  }
}

module.exports = { ensureCorrPage, canSkipSearch };
