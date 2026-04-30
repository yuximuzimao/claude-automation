'use strict';
/**
 * 第二步：读取货号 SKU 列表
 *
 * 四层筛选：①左侧店铺 ②精确搜索 ③平台商家编码 ④输入货号回车
 * 结果写入 sku-records.json（stage=skus_read）
 */
const path = require('path');
const fs = require('fs');
const cdp = require('../cdp');
const { sleep, waitFor } = require('../wait');
const { ensureCorrPage } = require('./ensure-corr-page');
const { readTableRows } = require('./read-table-rows');
const { safeWriteJson } = require('../utils/safe-write');

const SKU_RECORDS_PATH = path.join(__dirname, '../../data/sku-records.json');

/**
 * 在主页（非 dialog）的 el-select 中选值
 * @param {string} erpId
 * @param {number} selectIdx - 从 0 开始的索引（非 dialog 的 el-select）
 * @param {string} optionText
 */
async function _setMainPageSelect(erpId, selectIdx, optionText) {
  // 先读当前值，已正确就跳过
  const currentVal = await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(!sel) return "";' +
    '  var inp=sel.querySelector("input");' +
    '  return inp?inp.value:"";' +
    '})()'
  );
  if (currentVal === optionText) return;

  // 点击展开下拉
  await cdp.eval(erpId,
    '(function(){' +
    '  var sels=Array.from(document.querySelectorAll(".el-select")).filter(function(s){' +
    '    return !s.closest(".el-dialog__wrapper");' +
    '  });' +
    '  var sel=sels[' + selectIdx + '];' +
    '  if(sel) sel.click();' +
    '})()'
  );
  await sleep(400);

  // 选中目标选项
  await cdp.eval(erpId,
    '(function(){' +
    '  var items=document.querySelectorAll(".el-select-dropdown__item");' +
    '  for(var i=0;i<items.length;i++){' +
    '    if(items[i].innerText.trim()===' + JSON.stringify(optionText) + '&&items[i].getBoundingClientRect().height>0){' +
    '      items[i].click();return;' +
    '    }' +
    '  }' +
    '})()'
  );
  await sleep(300);
}

/**
 * @param {string} erpId
 * @param {string} shopName
 * @param {string} productCode
 * @returns {Promise<{ok: true, data: {skuCount, matchedCount, unmatchedCount}}>}
 */
async function readSkus(erpId, shopName, productCode) {
  await ensureCorrPage(erpId);

  // 0. 等待页面渲染完成（确保 form-item[4] 的搜索输入框存在）
  await waitFor(async () => {
    const ready = await cdp.eval(erpId,
      '(function(){' +
      '  var items=Array.from(document.querySelectorAll(".el-form-item")).filter(function(f){return !f.closest(".el-dialog__wrapper")});' +
      '  return items.length>=5&&items[4].querySelector("input")?"ready":"not-ready";' +
      '})()'
    );
    return ready === 'ready';
  }, { timeoutMs: 10000, intervalMs: 500, label: '等搜索输入框就绪' });

  // 1. 点击左侧店铺
  const shopClicked = await cdp.eval(erpId,
    '(function(){' +
    '  var spans=document.querySelectorAll("span");' +
    '  for(var i=0;i<spans.length;i++){' +
    '    if(spans[i].innerText.trim()===' + JSON.stringify(shopName) + '&&spans[i].className.includes("el-tooltip")){' +
    '      spans[i].click();return "clicked";' +
    '    }' +
    '  }' +
    '  return "not-found";' +
    '})()'
  );
  if (shopClicked !== 'clicked') throw new Error(`左侧店铺「${shopName}」未找到`);
  await sleep(1500);

  // 2. 设搜索下拉：精确搜索（[4]）+ 平台商家编码（[5]）
  //    索引排除 dialog 内的 select 后：2=店铺, 3=平台商品, 4=精确搜索, 5=平台商家编码
  await _setMainPageSelect(erpId, 4, '精确搜索');
  await _setMainPageSelect(erpId, 5, '平台商家编码');

  // 3. 输入货号 + 回车
  //    搜索输入框在 el-input-popup-editor 内（form-item[6]），不是 el-select
  const inputResult = await cdp.eval(erpId,
    '(function(){' +
    '  var editor=document.querySelector(".el-input-popup-editor");' +
    '  if(!editor) return "editor-not-found";' +
    '  var inp=editor.querySelector("input");' +
    '  if(!inp) return "input-not-found";' +
    '  inp.value=' + JSON.stringify(productCode) + ';' +
    '  inp.dispatchEvent(new Event("input",{bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keydown",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  inp.dispatchEvent(new KeyboardEvent("keyup",{key:"Enter",keyCode:13,bubbles:true}));' +
    '  return "triggered";' +
    '})()'
  );
  if (inputResult !== 'triggered') throw new Error('搜索输入框未找到: ' + inputResult);
  await sleep(3500);

  // 4. 验证至少有 1 行结果
  const rowCount = await cdp.eval(erpId,
    '(function(){return document.querySelectorAll(".el-table__body-wrapper .el-table__body tbody tr.el-table__row").length;})()'
  );
  if (!rowCount || rowCount === 0) {
    throw new Error(`搜索货号「${productCode}」无结果，请检查货号和店铺是否正确`);
  }

  // 5. 读取子行数据（readTableRows 内置展开+等待+校验）
  const subRows = await readTableRows(erpId, {
    fields: ['platformCode', 'skuName', 'imgUrl', 'erpCode', 'erpName'],
    expectedProductCode: productCode,
  });

  if (!subRows.length) throw new Error(`货号「${productCode}」展开后无子行`);

  // 6. 构建 sku-records.json 新格式
  const skus = {};
  let matchedCount = 0;
  let unmatchedCount = 0;

  for (const row of subRows) {
    const hasErp = !!row.erpCode;
    const matchStatus = hasErp ? 'matched-original' : 'unmatched';
    if (hasErp) matchedCount++;
    else unmatchedCount++;

    skus[row.platformCode] = {
      platformCode: row.platformCode,
      skuName: row.skuName,
      productCode,
      shopName,
      imgUrl: row.imgUrl || null,
      erpCode: row.erpCode || null,
      erpName: row.erpName || null,
      recognition: null,
      itemType: null,
      matchStatus,
      archiveType: null,
      archiveTitle: null,
      subItems: null,
      comparisonResult: null,
      comparisonDetail: null,
    };
  }

  const record = { stage: 'skus_read', shopName, productCode, skus };
  safeWriteJson(SKU_RECORDS_PATH, record);

  console.error(`[read-skus] ${productCode}：${subRows.length} SKU，已匹配 ${matchedCount}，待匹配 ${unmatchedCount}`);
  return { ok: true, data: { skuCount: subRows.length, matchedCount, unmatchedCount } };
}

module.exports = { readSkus };
